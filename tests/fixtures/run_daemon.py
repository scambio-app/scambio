# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Fermich srl
"""Process harness: refuses real buses and always injects fake pactl."""

import json
import logging
import os
import sys
from pathlib import Path

from gi.repository import Gio, GLib

import scambio.api

scambio.api.BUS_NAME = "app.scambio.Test"
from scambio.core.service import run, schedule  # noqa: E402

for key in ("DBUS_SYSTEM_BUS_ADDRESS", "DBUS_SESSION_BUS_ADDRESS"):
    assert "dbusmock_data_" in os.environ[key], f"Unsafe bus: {key}"
root = Path(sys.argv[1])
assert (root / "pulse/events").exists()
logging.basicConfig(level=logging.DEBUG)

if "--audit-shutdown" in sys.argv:
    original_call = Gio.DBusConnection.call
    original_flush = Gio.DBusConnection.flush

    def record(event, **details):
        with (root / "shutdown.jsonl").open("a") as out:
            out.write(json.dumps({"event": event, **details}) + "\n")

    def traced_call(connection, *args):
        if args[3] == "setInactive":
            record("setInactive", flags=int(args[6]))
        return original_call(connection, *args)

    def traced_flush(connection, *args):
        record("flush")
        return original_flush(connection, *args)

    Gio.DBusConnection.call = traced_call
    Gio.DBusConnection.flush = traced_flush


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
