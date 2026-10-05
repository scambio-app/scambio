"""Process harness: refuses real buses and always injects fake pactl."""

import logging
import os
import sys
from pathlib import Path

from gi.repository import GLib

import scambio.api

scambio.api.BUS_NAME = "app.scambio.Test"
from scambio.core.service import run, schedule  # noqa: E402

for key in ("DBUS_SYSTEM_BUS_ADDRESS", "DBUS_SESSION_BUS_ADDRESS"):
    assert "dbusmock_data_" in os.environ[key], f"Unsafe bus: {key}"
root = Path(sys.argv[1])
assert (root / "pulse/events").exists()
logging.basicConfig(level=logging.DEBUG)


def accelerated(milliseconds, callback):
    return GLib.timeout_add(max(1, milliseconds // 100), callback)


raise SystemExit(
    run(
        root / "config.toml",
        root / "state.json",
        [
            sys.executable,
            str(Path(__file__).with_name("fake_pactl.py")),
            str(root / "pulse"),
        ],
        timer=accelerated if "--accelerated" in sys.argv else schedule,
    )
)
