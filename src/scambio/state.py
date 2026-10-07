"""Small crash-safe persistent state, independent of user configuration."""

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from scambio.files import STATE_LIMIT, read_text, write_text
from scambio.paths import user_data_dir
from scambio.text import logger

LOG = logger(__name__)


@dataclass(frozen=True)
class PlayerRef:
    name: str
    owner: str


@dataclass(frozen=True)
class ResumePlayers:
    bus_id: str
    players: tuple[PlayerRef, ...]


def parse_resume(raw: object) -> ResumePlayers | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError("expected resume_players object")
    bus_id, players = raw.get("bus_id"), raw.get("players")
    if not isinstance(bus_id, str) or not bus_id or not isinstance(players, list):
        raise ValueError("invalid resume_players bus or players")
    if len(players) > 16:
        raise ValueError("too many saved players")
    refs = []
    for entry in players:
        if not isinstance(entry, dict):
            raise ValueError("invalid player entry")
        name, owner = entry.get("name"), entry.get("owner")
        if (
            not isinstance(name, str)
            or not re.fullmatch(r"org\.mpris\.MediaPlayer2\.[A-Za-z_-][\w.-]*", name)
            or not isinstance(owner, str)
            or not re.fullmatch(r":[0-9]+\.[0-9]+", owner)
        ):
            raise ValueError("invalid player name or owner")
        ref = PlayerRef(name, owner)
        if ref not in refs:
            refs.append(ref)
    return ResumePlayers(bus_id, tuple(refs))


@dataclass
class Shortcut:
    preferred: str


@dataclass
class State:
    version: int = 1
    iphone_priority: bool = False
    restore_default_sink: str | None = None
    resume_players: ResumePlayers | None = None
    shortcut: Shortcut | None = None


class Store:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or user_data_dir() / "state.json"
        self.value = State()

    def load(self) -> State:
        try:
            data = json.loads(read_text(self.path, STATE_LIMIT))
            if not isinstance(data, dict) or type(data.get("version")) is not int:
                raise ValueError("invalid state")
            if data["version"] != 1 or type(data.get("iphone_priority")) is not bool:
                raise ValueError("invalid version or priority")
            sink = data.get("restore_default_sink")
            if sink is not None and not isinstance(sink, str):
                raise ValueError("invalid restore sink")
            self.value = State(1, data["iphone_priority"], sink)
            try:
                self.value.resume_players = parse_resume(data.get("resume_players"))
            except ValueError as exc:
                LOG.warning("Ignoring malformed resume_players: %s", exc)
            shortcut = data.get("shortcut")
            if shortcut is not None:
                if isinstance(shortcut, dict) and isinstance(
                    shortcut.get("preferred"), str
                ):
                    self.value.shortcut = Shortcut(shortcut["preferred"])
                else:
                    LOG.warning("Ignoring malformed shortcut state")
        except (OSError, ValueError) as exc:
            LOG.warning("Cannot load state; using defaults: %s", exc)
            self.value = State()
        return self.value

    def save(self) -> None:
        text = json.dumps(asdict(self.value)) + "\n"
        if len(text.encode("utf-8")) > STATE_LIMIT:
            raise OSError("State exceeds size limit")
        write_text(self.path, text)
