"""Measure 10 idle minutes on two newly created private buses and fake pactl."""

import json
import os
import subprocess
import sys
import tempfile
import time
from contextlib import ExitStack
from datetime import UTC, datetime
from pathlib import Path

import dbus
import dbusmock
from gi.repository import GLib

from scambio.api import BUS_NAME, INTERFACE, PATH
from scambio.config import TEMPLATE

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tests"))
from helpers import ADDRESS, FakePactl, bluez_mock, spin_until  # noqa: E402


def usage(pid):
    fields = Path(f"/proc/{pid}/stat").read_text().split(")", 1)[1].split()
    return {
        "cpu_seconds": (int(fields[11]) + int(fields[12])) / os.sysconf("SC_CLK_TCK"),
        "rss_kib": int(fields[21]) * os.sysconf("SC_PAGE_SIZE") // 1024,
    }


def main():
    output = REPO / "docs/verification/01/idle.json"
    with ExitStack() as stack:
        root = Path(
            stack.enter_context(tempfile.TemporaryDirectory(prefix="scambio-idle-"))
        )
        system = stack.enter_context(dbusmock.PrivateDBus(dbusmock.BusType.SYSTEM))
        session = stack.enter_context(dbusmock.PrivateDBus(dbusmock.BusType.SESSION))
        assert os.environ["DBUS_SYSTEM_BUS_ADDRESS"] == system.address
        assert os.environ["DBUS_SESSION_BUS_ADDRESS"] == session.address
        mock, _, _ = bluez_mock()
        stack.callback(mock.terminate)
        login = stack.enter_context(
            dbusmock.SpawnedMock.spawn_with_template(
                "logind", stdout=subprocess.DEVNULL
            )
        )
        path = login.obj.AddSession(
            "test",
            "seat0",
            os.getuid(),
            "test",
            True,
            dbus_interface=dbusmock.MOCK_IFACE,
        )
        login.obj.AddObject(
            "/org/freedesktop/login1/user/self",
            "org.freedesktop.login1.User",
            {"Display": dbus.Struct(("test", dbus.ObjectPath(path)), signature="so")},
            [],
            dbus_interface=dbusmock.MOCK_IFACE,
        )
        saver = stack.enter_context(
            dbusmock.SpawnedMock.spawn_for_name(
                "org.freedesktop.ScreenSaver",
                "/org/freedesktop/ScreenSaver",
                "org.freedesktop.ScreenSaver",
                stdout=subprocess.DEVNULL,
            )
        )
        saver.obj.AddMethod(
            "org.freedesktop.ScreenSaver",
            "GetActive",
            "",
            "b",
            "ret = False",
            dbus_interface=dbusmock.MOCK_IFACE,
        )
        fake = FakePactl(root / "pulse")
        stack.callback(fake.close)
        (root / "config.toml").write_text(
            TEMPLATE.replace('address = ""', f'address = "{ADDRESS}"')
        )
        log = stack.enter_context((root / "daemon.log").open("w"))
        process = subprocess.Popen(
            [sys.executable, str(REPO / "tests/fixtures/run_daemon.py"), str(root)],
            stdout=log,
            stderr=log,
        )

        def stop():
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=5)

        stack.callback(stop)
        bus = dbusmock.BusType.SESSION.get_connection()
        spin_until(lambda: bus.name_has_owner(BUS_NAME))

        def properties():
            return bus.get_object(BUS_NAME, PATH).GetAll(
                INTERFACE, dbus_interface="org.freedesktop.DBus.Properties"
            )

        spin_until(
            lambda: (
                properties()["State"] == "released"
                and (root / "pulse/subscriber.pid").exists()
            )
        )
        # One settling delay, then only the two endpoint samples; no sampling loop.
        loop = GLib.MainLoop()
        GLib.timeout_add_seconds(1, lambda: (loop.quit(), False)[1])
        loop.run()
        ids = {
            "daemon": process.pid,
            "fake_pactl": int((root / "pulse/subscriber.pid").read_text()),
        }
        before = {name: usage(pid) for name, pid in ids.items()}
        calls_before = len(fake.calls())
        start = time.monotonic()
        started = datetime.now(UTC).isoformat()
        print(f"Idle measurement started {started}; daemon={process.pid}", flush=True)
        GLib.timeout_add(600000, lambda: (loop.quit(), False)[1])
        loop.run()
        elapsed = time.monotonic() - start
        after = {name: usage(pid) for name, pid in ids.items()}
        result = {
            "environment": (
                "private dbusmock system/session buses; "
                "bluez5/logind/ScreenSaver; fake pactl"
            ),
            "started_utc": started,
            "elapsed_seconds": elapsed,
            "processes": {
                name: {
                    "pid": ids[name],
                    "before": before[name],
                    "after": after[name],
                    "cpu_percent_interval": 100
                    * (after[name]["cpu_seconds"] - before[name]["cpu_seconds"])
                    / elapsed,
                }
                for name in ids
            },
            "pactl_calls_during_idle": len(fake.calls()) - calls_before,
            "state_after": str(properties()["State"]),
            "real_measurement": "Pending GM checklist item 18",
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
