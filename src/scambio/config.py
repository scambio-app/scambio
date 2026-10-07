"""Validated TOML configuration with narrowly scoped, lossless edits."""

import copy
import json
import logging
import os
import re
import stat
import tempfile
import tomllib
from collections.abc import Iterator
from dataclasses import dataclass, field, fields
from pathlib import Path

from scambio.i18n import Translator
from scambio.paths import user_config_dir

LOG = logging.getLogger(__name__)
RESUME_DEFAULTS = {"generic": 0, "meta_glasses": 2000}
WINDOW_KEYS = {
    "device.address": str,
    "policy.release_idle_seconds": int,
    "ui.tray": bool,
    "ui.notifications": bool,
    "ui.language": str,
}


class ConfigInvalid(ValueError):
    """The file cannot be applied without changing its contents."""


@dataclass(frozen=True)
class Device:
    address: str = ""
    profile: str = "generic"


@dataclass(frozen=True)
class Policy:
    grab_delay_ms: int = 500
    release_idle_seconds: int = 120
    connect_timeout_seconds: int = 10
    sink_timeout_seconds: int = 5
    sleep_release_timeout_seconds: int = 4
    unblock_silence_seconds: int = 10
    resume_delay_ms: int = 0


@dataclass(frozen=True)
class Audio:
    ignore_roles: tuple[str, ...] = ("event", "notification", "test")
    ignore_apps: tuple[str, ...] = ()
    ignore_players: tuple[str, ...] = (
        "kdeconnect",
        "plasma-browser-integration",
        "playerctld",
    )


@dataclass(frozen=True)
class Backend:
    coalesce_ms: int = 50
    retry_initial_seconds: int = 1
    retry_max_seconds: int = 30
    dbus_margin_seconds: int = 5
    dbus_timeout_seconds: int = 10
    command_timeout_seconds: int = 10
    player_timeout_ms: int = 1000


@dataclass(frozen=True)
class Config:
    device: Device = field(default_factory=Device)
    policy: Policy = field(default_factory=Policy)
    audio: Audio = field(default_factory=Audio)
    backend: Backend = field(default_factory=Backend)
    shortcut: str = "<Super>g"
    language: str = "auto"
    tray: bool = True
    notifications: bool = True


TEMPLATE = """[device]
address = ""
profile = "generic"

[policy]
grab_delay_ms = 500
release_idle_seconds = 120
connect_timeout_seconds = 10
sink_timeout_seconds = 5
sleep_release_timeout_seconds = 4
unblock_silence_seconds = 10
# resume_delay_ms = 2000

[audio]
ignore_roles = ["event", "notification", "test"]
ignore_apps = []
ignore_players = ["kdeconnect", "plasma-browser-integration", "playerctld"]

[shortcut]
preferred = "<Super>g"

[ui]
language = "auto"
tray = true
notifications = true

[backend]
coalesce_ms = 50
retry_initial_seconds = 1
retry_max_seconds = 30
dbus_margin_seconds = 5
dbus_timeout_seconds = 10
command_timeout_seconds = 10
player_timeout_ms = 1000
"""

CONFIG_COMMENTS = {
    "device.address": "config-device-address",
    "device.profile": "config-device-profile",
    "policy.grab_delay_ms": "config-policy-grab-delay",
    "policy.release_idle_seconds": "config-policy-release-idle",
    "policy.connect_timeout_seconds": "config-policy-connect-timeout",
    "policy.sink_timeout_seconds": "config-policy-sink-timeout",
    "policy.sleep_release_timeout_seconds": "config-policy-sleep-timeout",
    "policy.unblock_silence_seconds": "config-policy-unblock",
    "policy.resume_delay_ms": "config-policy-resume-delay",
    "audio.ignore_roles": "config-audio-ignore-roles",
    "audio.ignore_apps": "config-audio-ignore-apps",
    "audio.ignore_players": "config-audio-ignore-players",
    "shortcut.preferred": "config-shortcut-preferred",
    "ui.language": "config-ui-language",
    "ui.tray": "config-ui-tray",
    "ui.notifications": "config-ui-notifications",
}


def template(language: str = "auto") -> str:
    tr = Translator(language).tr
    lines = ["# " + tr("config-header")]
    section = ""
    for line in TEMPLATE.splitlines():
        if line.startswith("["):
            section = line[1:-1]
            if section == "backend":
                lines.append("# " + tr("config-backend-header"))
        elif "=" in line and section != "backend":
            key = line.lstrip("# ").split("=", 1)[0].strip()
            lines.extend(
                "# " + text
                for text in tr(CONFIG_COMMENTS[section + "." + key]).splitlines()
            )
        lines.append(line)
    return "\n".join(lines) + "\n"


def config_path() -> Path:
    return user_config_dir() / "config.toml"


def load(path: Path | None = None) -> Config:
    path = path or config_path()
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("x") as out:
                out.write(template())
        except FileExistsError:
            pass
    try:
        data = tomllib.loads(path.read_text())
        return parse(data)
    except (OSError, ValueError, TypeError) as exc:
        raise ConfigInvalid(str(exc)) from exc


def parse(data: dict[str, object]) -> Config:
    known = {"device", "policy", "audio", "shortcut", "ui", "backend"}
    for key in data.keys() - known:
        LOG.warning("Unknown configuration section: %s", key)

    def section(name: str, keys: set[str]) -> dict[str, object]:
        raw = data.get(name, {})
        if not isinstance(raw, dict):
            raise ConfigInvalid(f"{name}: expected table")
        for key in raw.keys() - keys:
            LOG.warning("Unknown configuration key: %s.%s", name, key)
        return {str(k): v for k, v in raw.items() if k in keys}

    def string(raw: dict[str, object], key: str, default: str) -> str:
        value = raw.get(key, default)
        if not isinstance(value, str):
            raise ConfigInvalid(f"{key}: expected string")
        return value

    def integer(
        raw: dict[str, object], key: str, default: int, lo: int, hi: int
    ) -> int:
        value = raw.get(key, default)
        if type(value) is not int or not lo <= value <= hi:
            raise ConfigInvalid(f"{key}: expected integer in {lo}..{hi}")
        return value

    d = section("device", {"address", "profile"})
    address = string(d, "address", "").upper()
    if address and not re.fullmatch(r"(?:[0-9A-F]{2}:){5}[0-9A-F]{2}", address):
        raise ConfigInvalid("address: invalid Bluetooth address")
    profile = string(d, "profile", "generic")
    if profile not in {"generic", "meta_glasses"}:
        raise ConfigInvalid("profile: unknown device profile")
    p = section("policy", {f.name for f in fields(Policy)})
    policy = Policy(
        integer(p, "grab_delay_ms", 500, 0, 10000),
        integer(p, "release_idle_seconds", 120, 10, 3600),
        integer(p, "connect_timeout_seconds", 10, 2, 60),
        integer(p, "sink_timeout_seconds", 5, 1, 30),
        integer(p, "sleep_release_timeout_seconds", 4, 1, 10),
        integer(p, "unblock_silence_seconds", 10, 1, 120),
        integer(p, "resume_delay_ms", RESUME_DEFAULTS[profile], 0, 10000),
    )
    a = section("audio", {f.name for f in fields(Audio)})

    def strings(key: str, default: tuple[str, ...]) -> tuple[str, ...]:
        value = a.get(key, list(default))
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            raise ConfigInvalid(f"{key}: expected string array")
        return tuple(str(v).casefold() for v in value)

    audio = Audio(
        strings("ignore_roles", Audio().ignore_roles),
        strings("ignore_apps", ()),
        strings("ignore_players", Audio().ignore_players),
    )
    b = section("backend", {f.name for f in fields(Backend)})
    backend = Backend(
        **{
            f.name: integer(
                b,
                f.name,
                getattr(Backend(), f.name),
                100 if f.name == "player_timeout_ms" else 1,
                5000 if f.name == "player_timeout_ms" else 60000,
            )
            for f in fields(Backend)
        }
    )
    if backend.retry_initial_seconds > backend.retry_max_seconds:
        raise ConfigInvalid("retry_initial_seconds exceeds retry_max_seconds")
    shortcut = string(section("shortcut", {"preferred"}), "preferred", "<Super>g")
    ui = section("ui", {"language", "tray", "notifications"})
    language = string(ui, "language", "auto")
    for key in ("tray", "notifications"):
        if type(ui.get(key, True)) is not bool:
            raise ConfigInvalid(f"{key}: expected boolean")
    if language not in {"auto", "it", "en", "de"}:
        raise ConfigInvalid("language: unsupported language")
    return Config(
        Device(address, profile),
        policy,
        audio,
        backend,
        shortcut,
        language,
        bool(ui.get("tray", True)),
        bool(ui.get("notifications", True)),
    )


def window_values(config: Config) -> dict[str, str | int | bool]:
    return {
        "device.address": config.device.address,
        "policy.release_idle_seconds": config.policy.release_idle_seconds,
        "ui.tray": config.tray,
        "ui.notifications": config.notifications,
        "ui.language": config.language,
        "shortcut.preferred": config.shortcut,
    }


def _statements(lines: list[str]) -> Iterator[tuple[int, int, str]]:
    """Use the TOML parser to delimit statements, including untouched multiline values.

    Parsing each logical statement prevents a '[ui]' inside a multiline string
    or an array from being mistaken for a table header. No TOML serializer is used.
    """
    start = 0
    buffer = ""
    for end, line in enumerate(lines, 1):
        buffer += line
        try:
            tomllib.loads(buffer)
        except tomllib.TOMLDecodeError:
            continue
        yield start, end, buffer
        start, buffer = end, ""
    if buffer:
        raise ConfigInvalid("Unsupported TOML statement")


def _replace_value(
    text: str, section: str, key: str, value: object, data: dict[str, object]
) -> str:
    lines = text.splitlines(keepends=True)
    newline = "\r\n" if "\r\n" in text else "\n"
    table = ""
    insertion: int | None = None
    target: tuple[int, re.Match[str]] | None = None
    encoded = json.dumps(value, ensure_ascii=False)
    scalar = r"""(?:"(?:[^"\\\r\n]|\\.)*"|'[^'\r\n]*'|[^\s#'"\[\{]+)"""
    assignment = re.compile(
        r"^([ \t]*"
        + re.escape(key)
        + r"[ \t]*=[ \t]*)("
        + scalar
        + r")([ \t]*(?:#[^\r\n]*)?(?:\r?\n)?)$"
    )
    for start, end, statement in _statements(lines):
        stripped = statement.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("["):
            header = re.fullmatch(
                r"\[\s*([A-Za-z0-9_-]+)\s*\]\s*(?:#[^\r\n]*)?", stripped
            )
            table = header[1] if header else ""
            if table == section:
                insertion = end
        elif table == section:
            insertion = end
            match = assignment.fullmatch(statement)
            if match:
                target = start, match
    if target:
        index, match = target
        lines[index] = match[1] + encoded + match[3]
    else:
        raw_section = data.get(section, {})
        if (isinstance(raw_section, dict) and key in raw_section) or (
            section in data and insertion is None
        ):
            LOG.warning("Cannot edit %s.%s: unsupported TOML form", section, key)
            raise ConfigInvalid("Unsupported TOML form for " + section + "." + key)
        line = key + " = " + encoded + newline
        if insertion is None:
            if lines and not lines[-1].endswith("\n"):
                lines[-1] += newline
            lines.extend([newline, "[" + section + "]" + newline, line])
        else:
            if insertion and not lines[insertion - 1].endswith("\n"):
                lines[insertion - 1] += newline
            lines.insert(insertion, line)
    return "".join(lines)


@dataclass(frozen=True)
class ConfigEdit:
    path: Path
    text: str
    config: Config
    mode: int

    def write(self) -> None:
        """Commit only after the service's DeviceBusy check."""
        path = self.path.resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=".config-", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as out:
                os.fchmod(out.fileno(), self.mode)
                out.write(self.text.encode("utf-8"))
                out.flush()
                os.fsync(out.fileno())
            os.replace(name, path)
        finally:
            if os.path.exists(name):
                os.unlink(name)


def prepare_update(
    path: Path, changes: dict[str, object], language: str = "auto"
) -> ConfigEdit:
    for key, value in changes.items():
        if key not in WINDOW_KEYS or type(value) is not WINDOW_KEYS[key]:
            raise ConfigInvalid("Unsupported configuration key or type: " + key)
    try:
        text = path.read_bytes().decode("utf-8")
        mode = stat.S_IMODE(path.stat().st_mode)
    except FileNotFoundError:
        text, mode = template(language), 0o600
    except (OSError, UnicodeError) as exc:
        raise ConfigInvalid(str(exc)) from exc
    try:
        data = tomllib.loads(text)
        merged = copy.deepcopy(data)
        for name, value in changes.items():
            section, key = name.split(".")
            table = merged.setdefault(section, {})
            if not isinstance(table, dict):
                raise ConfigInvalid("Expected table: " + section)
            table[key] = value
        config = parse(merged)
        for name, value in changes.items():
            section, key = name.split(".")
            text = _replace_value(text, section, key, value, tomllib.loads(text))
        if tomllib.loads(text) != merged:
            raise ConfigInvalid("TOML edit changed unrelated values")
    except (ValueError, TypeError) as exc:
        raise ConfigInvalid(str(exc)) from exc
    return ConfigEdit(path, text, config, mode)
