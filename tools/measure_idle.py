"""Measure 10 idle minutes on two newly created private buses and fake pactl."""

import argparse
import hashlib
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

from scambio.api import INTERFACE, PATH
from scambio.config import TEMPLATE

BUS_NAME = "app.scambio.Test"

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tests"))
from helpers import ADDRESS, FakePactl, bluez_mock, spin_until  # noqa: E402
from test_players import FakePlayer  # noqa: E402


def usage(pid):
    fields = Path(f"/proc/{pid}/stat").read_text().split(")", 1)[1].split()
    return {
        "cpu_seconds": (int(fields[11]) + int(fields[12])) / os.sysconf("SC_CLK_TCK"),
        "rss_kib": int(fields[21]) * os.sysconf("SC_PAGE_SIZE") // 1024,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", type=Path, default=REPO / "docs/verification/01/idle.json"
    )
    parser.add_argument("--ui", action="store_true")
    parser.add_argument("--shortcuts", action="store_true")
    args = parser.parse_args()
    output = args.output
    source_hashes = {
        name: hashlib.sha256((REPO / name).read_bytes()).hexdigest()
        for name in (
            "src/scambio/config.py",
            "src/scambio/state.py",
            "src/scambio/core/policy.py",
            "src/scambio/core/players.py",
            "src/scambio/core/service.py",
            "src/scambio/core/shortcuts.py",
            "src/scambio/core/shortcut_keys.py",
            "src/scambio/core/bluez.py",
            "src/scambio/api.py",
            "tests/fixtures/run_daemon.py",
            "src/scambio/i18n.py",
            "src/scambio/paths.py",
            "src/scambio/ui/__init__.py",
            "src/scambio/ui/client.py",
            "src/scambio/ui/actions.py",
            "src/scambio/ui/guard.py",
            "src/scambio/ui/notify.py",
            "src/scambio/ui/presentation.py",
            "src/scambio/ui/tray.py",
        )
    }
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
        watcher = notifications = None
        if args.ui:
            watcher = stack.enter_context(
                dbusmock.SpawnedMock.spawn_for_name(
                    "org.kde.StatusNotifierWatcher",
                    "/StatusNotifierWatcher",
                    "org.kde.StatusNotifierWatcher",
                    stdout=subprocess.DEVNULL,
                )
            )
            watcher.obj.AddMethod(
                "org.kde.StatusNotifierWatcher",
                "RegisterStatusNotifierItem",
                "s",
                "",
                "",
                dbus_interface=dbusmock.MOCK_IFACE,
            )
            notifications = stack.enter_context(
                dbusmock.SpawnedMock.spawn_with_template(
                    "notification_daemon", stdout=subprocess.DEVNULL
                )
            )
        kga = None
        if args.shortcuts:
            kga = stack.enter_context(
                dbusmock.SpawnedMock.spawn_for_name(
                    "org.kde.kglobalaccel",
                    "/kglobalaccel",
                    "org.kde.KGlobalAccel",
                    stdout=subprocess.DEVNULL,
                )
            )
            kga.obj.AddMethods(
                "org.kde.KGlobalAccel",
                [
                    ("doRegister", "as", "", ""),
                    ("getComponent", "s", "o", 'ret = "/component/test"'),
                    ("setShortcut", "asaiu", "ai", "ret = args[1]"),
                    ("setInactive", "as", "", ""),
                ],
                dbus_interface=dbusmock.MOCK_IFACE,
            )
            kga.obj.AddObject(
                "/component/test",
                "org.kde.kglobalaccel.Component",
                {},
                [],
                dbus_interface=dbusmock.MOCK_IFACE,
            )
        player = FakePlayer("idle", "Paused")
        stack.callback(player.close)
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
        if watcher:
            spin_until(
                lambda: watcher.obj.GetMethodCalls(
                    "RegisterStatusNotifierItem", dbus_interface=dbusmock.MOCK_IFACE
                )
            )
        if kga:
            spin_until(lambda: properties()["ShortcutState"] == "active")
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
        player_calls_before = len(
            player.obj.GetCalls(dbus_interface=dbusmock.MOCK_IFACE)
        )
        ui_calls_before = {
            name: len(mock.obj.GetCalls(dbus_interface=dbusmock.MOCK_IFACE))
            for name, mock in (
                ("watcher", watcher),
                ("notifications", notifications),
                ("kglobalaccel", kga),
            )
            if mock is not None
        }
        start = time.monotonic()
        started = datetime.now(UTC).isoformat()
        print(f"Idle measurement started {started}; daemon={process.pid}", flush=True)
        GLib.timeout_add(600000, lambda: (loop.quit(), False)[1])
        loop.run()
        elapsed = time.monotonic() - start
        after = {name: usage(pid) for name, pid in ids.items()}
        result = {
            "source_sha256": source_hashes,
            "environment": (
                "private dbusmock system/session buses; "
                "bluez5/logind/ScreenSaver/MPRIS; fake pactl; app.scambio.Test"
                + ("; SNI watcher/notifications mocks" if args.ui else "")
                + ("; KGlobalAccel mock active" if args.shortcuts else "")
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
            "mpris_calls_during_idle": len(
                player.obj.GetCalls(dbus_interface=dbusmock.MOCK_IFACE)
            )
            - player_calls_before,
            "state_after": str(properties()["State"]),
            "ui_enabled": args.ui,
            "shortcut_state_after": str(properties()["ShortcutState"]),
            "ui_calls_during_idle": {
                name: len(mock.obj.GetCalls(dbus_interface=dbusmock.MOCK_IFACE))
                - ui_calls_before[name]
                for name, mock in (
                    ("watcher", watcher),
                    ("notifications", notifications),
                    ("kglobalaccel", kga),
                )
                if mock is not None
            },
            "real_measurement": "Private buses; GM desktop/hardware proof separate",
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
