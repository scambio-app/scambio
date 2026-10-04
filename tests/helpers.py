import json
import os
import subprocess
import sys
from pathlib import Path

import dbus
import dbusmock
from gi.repository import Gio, GLib

ADDRESS = "AA:BB:CC:DD:EE:FF"
SINK = "bluez_output.AA_BB_CC_DD_EE_FF.1"


def spin_until(predicate, seconds=5):
    loop = GLib.MainLoop()
    timed_out = []

    def check():
        if predicate():
            loop.quit()
            return False
        return True

    def timeout():
        timed_out.append(True)
        loop.quit()
        return False

    check_id = GLib.timeout_add(5, check)
    timeout_id = GLib.timeout_add(int(seconds * 1000), timeout)
    loop.run()
    if timed_out:
        GLib.source_remove(check_id)
    else:
        GLib.source_remove(timeout_id)
    assert not timed_out, "Timed out waiting for test event"


def drain(milliseconds=50):
    loop = GLib.MainLoop()
    GLib.timeout_add(milliseconds, lambda: (loop.quit(), False)[1])
    loop.run()


def gio_bus(kind):
    return Gio.bus_get_sync(kind, None)


class FakePactl:
    def __init__(self, root):
        self.root = root
        root.mkdir()
        os.mkfifo(root / "events")
        self.fd = os.open(root / "events", os.O_RDWR | os.O_NONBLOCK)
        self.command = [
            sys.executable,
            str(Path(__file__).parent / "fixtures/fake_pactl.py"),
            str(root),
        ]
        self.update(
            {
                "sinks": [{"index": 1, "name": "speakers", "properties": {}}],
                "streams": [],
                "default": "speakers",
            }
        )

    def read(self):
        return json.loads((self.root / "snapshot.json").read_text())

    def update(self, values):
        path = self.root / "snapshot.json"
        state = self.read() if path.exists() else {}
        state.update(values)
        tmp = self.root / "test-snapshot.tmp"
        tmp.write_text(json.dumps(state))
        tmp.replace(path)

    def event(self, raw=b'{"event":"change","on":"sink-input","index":1}'):
        os.write(self.fd, raw)

    def calls(self):
        path = self.root / "calls"
        return (
            [json.loads(line) for line in path.read_text().splitlines()]
            if path.exists()
            else []
        )

    def add_sink(self):
        self.update(
            {
                "sinks": self.read()["sinks"]
                + [
                    {
                        "index": 2,
                        "name": SINK,
                        "properties": {"api.bluez5.address": ADDRESS},
                    }
                ]
            }
        )

    def close(self):
        os.close(self.fd)


def bluez_mock():
    mock = dbusmock.SpawnedMock.spawn_with_template("bluez5", stdout=subprocess.DEVNULL)
    iface = dbus.Interface(mock.obj, "org.bluez.Mock")
    adapter = str(iface.AddAdapter("hci0", "Test adapter"))
    device = str(iface.AddDevice("hci0", ADDRESS, "Test headset"))
    bus = dbusmock.BusType.SYSTEM.get_connection()
    dev = bus.get_object("org.bluez", device)
    dev.UpdateProperties(
        "org.bluez.Device1",
        {"Paired": dbus.Boolean(True)},
        dbus_interface=dbusmock.MOCK_IFACE,
    )
    return mock, device, adapter
