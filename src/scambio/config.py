"""Validated, read-only TOML configuration (except initial template creation)."""

import logging
import re
import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path

LOG = logging.getLogger(__name__)


class ConfigInvalid(ValueError):
    """The file cannot be applied without changing its contents."""


@dataclass(frozen=True)
class Device:
    address: str = ""
    profile: str = "generic"


@dataclass(frozen=True)
class Policy:
    grab_delay_ms: int = 1000
    release_idle_seconds: int = 120
    connect_timeout_seconds: int = 10
    sink_timeout_seconds: int = 5
    sleep_release_timeout_seconds: int = 4


@dataclass(frozen=True)
class Audio:
    ignore_roles: tuple[str, ...] = ("event", "notification", "test")
    ignore_apps: tuple[str, ...] = ()


@dataclass(frozen=True)
class Backend:
    coalesce_ms: int = 50
    retry_initial_seconds: int = 1
    retry_max_seconds: int = 30
    dbus_margin_seconds: int = 5
    dbus_timeout_seconds: int = 10
    command_timeout_seconds: int = 10


@dataclass(frozen=True)
class Config:
    device: Device = field(default_factory=Device)
    policy: Policy = field(default_factory=Policy)
    audio: Audio = field(default_factory=Audio)
    backend: Backend = field(default_factory=Backend)
    shortcut: str = "<Super>g"
    language: str = "auto"


TEMPLATE = """# Scambio configuration. Only already paired devices are supported.
[device]
address = "" # Bluetooth address, XX:XX:XX:XX:XX:XX
profile = "generic" # generic or meta_glasses

[policy]
grab_delay_ms = 1000
release_idle_seconds = 120
connect_timeout_seconds = 10
sink_timeout_seconds = 5
sleep_release_timeout_seconds = 4

[audio]
ignore_roles = ["event", "notification", "test"]
ignore_apps = []

[shortcut]
preferred = "<Super>g"

[ui]
language = "auto"

# Optional adapter timing; defaults match the measured backend.
[backend]
coalesce_ms = 50
retry_initial_seconds = 1
retry_max_seconds = 30
dbus_margin_seconds = 5
dbus_timeout_seconds = 10
command_timeout_seconds = 10
"""


def config_path() -> Path:
    return Path.home() / ".config/scambio/config.toml"


def load(path: Path | None = None) -> Config:
    path = path or config_path()
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("x") as out:
                out.write(TEMPLATE)
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
        integer(p, "grab_delay_ms", 1000, 0, 10000),
        integer(p, "release_idle_seconds", 120, 10, 3600),
        integer(p, "connect_timeout_seconds", 10, 2, 60),
        integer(p, "sink_timeout_seconds", 5, 1, 30),
        integer(p, "sleep_release_timeout_seconds", 4, 1, 10),
    )
    a = section("audio", {"ignore_roles", "ignore_apps"})

    def strings(key: str, default: tuple[str, ...]) -> tuple[str, ...]:
        value = a.get(key, list(default))
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            raise ConfigInvalid(f"{key}: expected string array")
        return tuple(str(v).casefold() for v in value)

    audio = Audio(
        strings("ignore_roles", Audio().ignore_roles), strings("ignore_apps", ())
    )
    b = section("backend", {f.name for f in fields(Backend)})
    backend = Backend(
        **{
            f.name: integer(b, f.name, getattr(Backend(), f.name), 1, 60000)
            for f in fields(Backend)
        }
    )
    if backend.retry_initial_seconds > backend.retry_max_seconds:
        raise ConfigInvalid("retry_initial_seconds exceeds retry_max_seconds")
    shortcut = string(section("shortcut", {"preferred"}), "preferred", "<Super>g")
    language = string(section("ui", {"language"}), "language", "auto")
    if language not in {"auto", "it", "en", "de"}:
        raise ConfigInvalid("language: unsupported language")
    return Config(Device(address, profile), policy, audio, backend, shortcut, language)
