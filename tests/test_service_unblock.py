"""Real service/adapters on private buses; policy time advances only in the test."""

from dataclasses import replace

import dbus
import dbusmock
import pytest
from gi.repository import Gio, GLib
from helpers import ADDRESS, SINK, drain, gio_bus, spin_until

from scambio.config import Config, Device
from scambio.core.audio import Audio
from scambio.core.bluez import BlueZ
from scambio.core.policy import Context
from scambio.core.service import Service
from scambio.core.session import Session
from scambio.state import Store


class PolicyClock:
    def __init__(self):
        self.now = 0
        self.calls = {}

    def __call__(self, milliseconds, callback):
        # Real source IDs let Service cancel normally. Test time controls dispatch.
        source = GLib.timeout_add(3600000, callback)
        self.calls[source] = (self.now + milliseconds, callback)
        return source

    def advance(self, milliseconds):
        target = self.now + milliseconds
        while True:
            due = [
                (deadline, source, callback)
                for source, (deadline, callback) in self.calls.items()
                if deadline <= target
                and GLib.MainContext.default().find_source_by_id(source) is not None
            ]
            if not due:
                break
            deadline, source, callback = min(due)
            self.now = deadline
            GLib.source_remove(source)
            assert callback() is False
        self.now = target

    def close(self):
        for source in self.calls:
            if GLib.MainContext.default().find_source_by_id(source) is not None:
                GLib.source_remove(source)


@pytest.mark.parametrize("loss", ["case", "bluetooth"])
def test_m8_gap_and_continuous_silence(fake_pactl, bluez_server, tmp_path, loss):
    _, path, adapter_path = bluez_server
    mock_bus = dbusmock.BusType.SYSTEM.get_connection()
    device = mock_bus.get_object("org.bluez", path)
    adapter = mock_bus.get_object("org.bluez", adapter_path)

    def connected(value):
        device.UpdateProperties(
            "org.bluez.Device1",
            {"Connected": dbus.Boolean(value)},
            dbus_interface=dbusmock.MOCK_IFACE,
        )

    def powered(value):
        adapter.UpdateProperties(
            "org.bluez.Adapter1",
            {"Powered": dbus.Boolean(value)},
            dbus_interface=dbusmock.MOCK_IFACE,
        )

    def connects():
        return device.GetMethodCalls("Connect", dbus_interface=dbusmock.MOCK_IFACE)

    connected(True)
    fake_pactl.add_sink()
    fake_pactl.update(
        {"default": SINK, "streams": [{"index": 3, "sink": 2, "corked": False}]}
    )
    config = Config(device=Device(ADDRESS))
    store = Store(tmp_path / "state.json")
    bus, system = gio_bus(Gio.BusType.SESSION), gio_bus(Gio.BusType.SYSTEM)
    clock = PolicyClock()

    def factory(emit):
        return (
            BlueZ(system, config, emit),
            Audio(config, store, emit, fake_pactl.command),
            Session(system, bus, config, emit),
        )

    service = Service(
        bus, config, store, tmp_path / "config.toml", factory, timer=clock
    )
    try:
        assert service.start()
        spin_until(lambda: service.initialized and not service.audio.routing_busy)
        initial = Context(
            state="on_pc",
            audio_active=True,
            device_connected=True,
            sink_ready=True,
            routed=True,
        )
        assert service.ctx == initial
        assert service.timers == {} and len(connects()) == 0
        if loss == "bluetooth":
            powered(False)
            spin_until(lambda: service.ctx.state == "unavailable")
            assert service.ctx == replace(
                initial, state="unavailable", routed=False, blocked_until_silence=True
            )
        connected(False)
        spin_until(lambda: not service.ctx.device_connected)
        if loss == "bluetooth":
            powered(True)
        spin_until(lambda: service.ctx.state == "released")
        reason = "availability" if loss == "bluetooth" else "external_disconnect"
        released = replace(
            initial,
            state="released",
            device_connected=False,
            routed=False,
            blocked_until_silence=True,
            reason=reason,
        )
        assert service.ctx == released
        assert service.timers == {} and len(connects()) == 0

        fake_pactl.update(
            {
                "sinks": [{"index": 1, "name": "speakers", "properties": {}}],
                "default": "speakers",
                "streams": [],
            }
        )
        fake_pactl.event()
        spin_until(lambda: not service.ctx.audio_active)
        silent = replace(released, audio_active=False, sink_ready=False)
        assert service.ctx == silent
        source = service.timers["UNBLOCK"]
        assert service.timers == {"UNBLOCK": source}
        assert clock.calls[source][0] == clock.now + 10000
        stale_callback = clock.calls[source][1]
        clock.advance(2000)
        assert service.ctx == silent and service.timers == {"UNBLOCK": source}

        audible = replace(silent, audio_active=True)
        fake_pactl.update({"streams": [{"index": 4, "sink": 1, "corked": False}]})
        fake_pactl.event()
        spin_until(lambda: service.ctx.audio_active)
        assert service.ctx == audible and service.timers == {}
        assert GLib.MainContext.default().find_source_by_id(source) is None
        clock.advance(10000)
        assert stale_callback() is False
        assert service.ctx == audible and service.timers == {} and len(connects()) == 0

        fake_pactl.update({"streams": []})
        fake_pactl.event()
        spin_until(lambda: not service.ctx.audio_active)
        source = service.timers["UNBLOCK"]
        assert service.ctx == silent and service.timers == {"UNBLOCK": source}
        # A canceled callback must not clear the block or consume its replacement.
        assert stale_callback() is False
        clock.advance(9999)
        assert service.ctx == silent and service.timers == {"UNBLOCK": source}
        clock.advance(1)
        cleared = replace(silent, blocked_until_silence=False)
        assert service.ctx == cleared and service.timers == {} and len(connects()) == 0

        fake_pactl.update({"streams": [{"index": 5, "sink": 1, "corked": False}]})
        fake_pactl.event()
        spin_until(lambda: service.ctx.audio_active)
        assert service.ctx == replace(cleared, audio_active=True)
        source = service.timers["GRAB_DELAY"]
        assert service.timers == {"GRAB_DELAY": source}
        assert clock.calls[source][0] == clock.now + 500
        clock.advance(499)
        assert (
            service.ctx == replace(cleared, audio_active=True) and len(connects()) == 0
        )
        clock.advance(1)
        assert service.ctx == replace(
            cleared,
            audio_active=True,
            state="connecting",
            origin="self",
            reason="audio_started",
            held=True,
        )
        spin_until(lambda: len(connects()) == 1)
    finally:
        service.close()
        clock.close()
        drain()
