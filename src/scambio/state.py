"""Small crash-safe persistent state, independent of user configuration."""

import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

LOG = logging.getLogger(__name__)


@dataclass
class State:
    version: int = 1
    iphone_priority: bool = False
    restore_default_sink: str | None = None


class Store:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path.home() / ".local/share/scambio/state.json"
        self.value = State()

    def load(self) -> State:
        try:
            data = json.loads(self.path.read_text())
            if not isinstance(data, dict) or type(data.get("version")) is not int:
                raise ValueError("invalid state")
            if data["version"] != 1 or type(data.get("iphone_priority")) is not bool:
                raise ValueError("invalid version or priority")
            sink = data.get("restore_default_sink")
            if sink is not None and not isinstance(sink, str):
                raise ValueError("invalid restore sink")
            self.value = State(1, data["iphone_priority"], sink)
        except (OSError, ValueError) as exc:
            LOG.warning("Cannot load state; using defaults: %s", exc)
            self.value = State()
        return self.value

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=".state-", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w") as out:
                json.dump(asdict(self.value), out)
                out.write("\n")
                out.flush()
                os.fsync(out.fileno())
            os.replace(name, self.path)
        finally:
            if os.path.exists(name):
                os.unlink(name)
