# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Fermich srl
import os
import subprocess
from dataclasses import replace

import dbus
import dbusmock
import pytest
from gi.repository import Gio
from helpers import ADDRESS, SINK, drain, gio_bus, spin_until

from scambio.config import Audio as AudioConfig
from scambio.config import Config, Device
from scambio.core.audio import Audio, JSONStream, active_stream
from scambio.core.bluez import BlueZ
from scambio.core.policy import Event
from scambio.core.session import Session
from scambio.state import Store


def cfg():
    return Config(device=Device(ADDRESS))


def test_json_stream():
    parser = JSONStream()
    blob = '{"on":"sink"}{"value":"é"}{"value":"(null)"}'.encode()
    values = []
    for byte in blob:
        values += parser.feed(bytes([byte]))
    assert values == [{"on": "sink"}, {"value": "é"}, {"value": "(null)"}]


@pytest.mark.parametrize(
    "props,corked,expected",
    [
        ({}, False, True),
        ({}, True, False),
        ({"media.role": "notification"}, False, False),
        ({"media.role": "(null)"}, False, True),
        ({"application.name": "PLAYER"}, False, False),
        ({"application.process.binary": "PLAYER"}, False, False),
    ],
)
def test_active(props, corked, expected):
    config = replace(cfg(), audio=AudioConfig(ignore_apps=("player",)))
    assert active_stream({"corked": corked, "properties": props}, config) is expected


@pytest.mark.parametrize("app", ["sd_dummy", "speech-dispatcher-dummy"])
@pytest.mark.parametrize("key", ["application.name", "application.process.binary"])
def test_dummy_audio_is_ignored_by_default(app, key):
    stream = {"corked": False, "properties": {key: app.upper()}}
    assert not active_stream(stream, cfg())
    assert active_stream(stream, replace(cfg(), audio=AudioConfig(ignore_apps=())))
    assert active_stream(
        {"corked": False, "properties": {key: "speech-dispatcher"}}, cfg()
    )


def test_audio_snapshot_coalescing_routing_restore(fake_pactl, tmp_path):
    events = []
    store = Store(tmp_path / "state.json")
    audio = Audio(cfg(), store, events.append, fake_pactl.command)
    try:
        audio.start()
        spin_until(lambda: audio.ready)
        assert Event("AudioActive", False) in events
        assert Event("DeviceSinkGone") in events
        baseline = len(fake_pactl.calls())
        fake_pactl.add_sink()
        fake_pactl.update(
            {"streams": [{"index": 3, "sink": 1, "corked": False, "properties": {}}]}
        )
        for _ in range(20):
            fake_pactl.event()
        spin_until(lambda: audio.sink == SINK and audio.active)
        assert len(fake_pactl.calls()) - baseline == 3
        assert all(c["locale"] == "C" for c in fake_pactl.calls())
        done = []
        audio.route(lambda: done.append(True))
        spin_until(lambda: done)
        assert store.value.restore_default_sink == "speakers"
        assert fake_pactl.read()["default"] == SINK
        assert fake_pactl.read()["streams"][0]["sink"] == 2
        done.clear()
        audio.restore(lambda: done.append(True))
        spin_until(lambda: done)
        assert fake_pactl.read()["default"] == "speakers"
        assert fake_pactl.read()["streams"][0]["sink"] == 1
        assert store.value.restore_default_sink is None
        route_calls = [
            c
            for c in fake_pactl.calls()
            if c["args"][0] in {"set-default-sink", "move-sink-input"}
        ]
        assert len(route_calls) == 4
        done.clear()
        audio.restore(lambda: done.append(True))
        spin_until(lambda: done)
        assert (
            len([c for c in fake_pactl.calls() if c["args"][0] == "set-default-sink"])
            == 2
        )
    finally:
        audio.close()
        drain()


@pytest.mark.parametrize("mode", ["already", "user", "gone", "failure"])
def test_audio_respects_default(fake_pactl, tmp_path, mode):
    fake_pactl.add_sink()
    store = Store(tmp_path / "state.json")
    if mode == "already":
        fake_pactl.update({"default": SINK})
    else:
        store.value.restore_default_sink = "speakers"
        if mode == "gone":
            fake_pactl.update(
                {"sinks": fake_pactl.read()["sinks"][1:], "default": SINK}
            )
        elif mode == "failure":
            fake_pactl.update({"fail_route": True, "default": SINK})
    audio = Audio(cfg(), store, lambda e: None, fake_pactl.command)
    try:
        audio.start()
        spin_until(lambda: audio.ready)
        done = []
        (audio.route if mode == "already" else audio.restore)(lambda: done.append(True))
        spin_until(lambda: done)
        assert store.value.restore_default_sink == (
            "speakers" if mode == "failure" else None
        )
        if mode != "failure":
            assert not any(
                c["args"][0] == "set-default-sink" for c in fake_pactl.calls()
            )
    finally:
        audio.close()
        drain()


def test_audio_restart_reemits_and_no_polling(fake_pactl, tmp_path):
    events = []
    audio = Audio(
        cfg(), Store(tmp_path / "state.json"), events.append, fake_pactl.command
    )
    try:
        audio.start()
        spin_until(lambda: audio.ready)
        baseline = len(fake_pactl.calls())
        drain(150)
        assert len(fake_pactl.calls()) == baseline
        fake_pactl.event(b"EXIT")
        spin_until(lambda: Event("AudioBackend", False) in events)
        spin_until(lambda: events.count(Event("AudioActive", False)) == 2, seconds=4)
        assert events.count(Event("DeviceSinkGone")) == 2
        assert audio.retry_delay == 1
    finally:
        audio.close()
        drain()


@pytest.mark.parametrize("missing", [False, True])
def test_audio_missing_or_old_permanent(fake_pactl, tmp_path, missing):
    fake_pactl.update({"version": "15.0"})
    events = []
    command = [str(tmp_path / "missing-pactl")] if missing else fake_pactl.command
    audio = Audio(cfg(), Store(tmp_path / "state.json"), events.append, command)
    try:
        audio.start()
        spin_until(lambda: audio.ready)
        assert events == [Event("AudioBackend", False)]
        assert audio.retry == 0
    finally:
        audio.close()
        drain()


def test_bluez_selection_connect_power_restart(bluez_server):
    mock, path, adapter = bluez_server
    events = []
    audio_bus = gio_bus(Gio.BusType.SYSTEM)
    bluez = BlueZ(audio_bus, cfg(), events.append)
    bus = dbusmock.BusType.SYSTEM.get_connection()
    try:
        bluez.start()
        spin_until(lambda: bluez.ready and bluez.available)
        assert bluez.path == path and bluez.name == "Test headset"
        bluez.connect()
        spin_until(lambda: Event("ConnectResult", "") in events)
        assert bluez.connected
        bluez.disconnect()
        spin_until(lambda: Event("DisconnectResult", "") in events)
        assert not bluez.connected
        bus.get_object("org.bluez", adapter).UpdateProperties(
            "org.bluez.Adapter1",
            {"Powered": dbus.Boolean(False)},
            dbus_interface=dbusmock.MOCK_IFACE,
        )
        spin_until(lambda: not bluez.available)
        mock.terminate()
        drain()
        from helpers import bluez_mock

        replacement, _, _ = bluez_mock()
        try:
            spin_until(lambda: bluez.available)
            assert bluez.path == path
        finally:
            replacement.terminate()
    finally:
        bluez.close()
        drain()


def test_session_or_dedup_and_inhibitor():
    login = dbusmock.SpawnedMock.spawn_with_template(
        "logind", stdout=subprocess.DEVNULL
    )
    saver = dbusmock.SpawnedMock.spawn_for_name(
        "org.freedesktop.ScreenSaver",
        "/org/freedesktop/ScreenSaver",
        "org.freedesktop.ScreenSaver",
        stdout=subprocess.DEVNULL,
    )
    events = []
    adapter = Session(
        gio_bus(Gio.BusType.SYSTEM), gio_bus(Gio.BusType.SESSION), cfg(), events.append
    )
    try:
        path = str(
            login.obj.AddSession(
                "test",
                "seat0",
                os.getuid(),
                "test",
                True,
                dbus_interface=dbusmock.MOCK_IFACE,
            )
        )
        login.obj.AddObject(
            "/org/freedesktop/login1/user/self",
            "org.freedesktop.login1.User",
            {"Display": dbus.Struct(("test", dbus.ObjectPath(path)), signature="so")},
            [],
            dbus_interface=dbusmock.MOCK_IFACE,
        )
        saver.obj.AddMethod(
            "org.freedesktop.ScreenSaver",
            "GetActive",
            "",
            "b",
            "ret = False",
            dbus_interface=dbusmock.MOCK_IFACE,
        )
        adapter.start()
        spin_until(lambda: adapter.ready and adapter.fd is not None)
        assert events == [Event("Locked", False)]
        session = dbusmock.BusType.SYSTEM.get_connection().get_object(
            "org.freedesktop.login1", path
        )
        session.UpdateProperties(
            "org.freedesktop.login1.Session",
            {"LockedHint": dbus.Boolean(True)},
            dbus_interface=dbusmock.MOCK_IFACE,
        )
        for _ in range(2):
            saver.obj.EmitSignal(
                "org.freedesktop.ScreenSaver",
                "ActiveChanged",
                "b",
                [True],
                dbus_interface=dbusmock.MOCK_IFACE,
            )
        spin_until(lambda: adapter.sources["screensaver"] is True)
        assert events.count(Event("Locked", True)) == 1
        session.UpdateProperties(
            "org.freedesktop.login1.Session",
            {"LockedHint": dbus.Boolean(False)},
            dbus_interface=dbusmock.MOCK_IFACE,
        )
        drain()
        assert adapter.locked
        saver.obj.EmitSignal(
            "org.freedesktop.ScreenSaver",
            "ActiveChanged",
            "b",
            [False],
            dbus_interface=dbusmock.MOCK_IFACE,
        )
        spin_until(lambda: not adapter.locked)
        login.obj.EmitSignal(
            "org.freedesktop.login1.Manager",
            "PrepareForSleep",
            "b",
            [True],
            dbus_interface=dbusmock.MOCK_IFACE,
        )
        spin_until(lambda: Event("Sleep", True) in events)
        fd = adapter.fd
        adapter.release_inhibitor()
        with pytest.raises(OSError):
            os.fstat(fd)
        login.obj.EmitSignal(
            "org.freedesktop.login1.Manager",
            "PrepareForSleep",
            "b",
            [False],
            dbus_interface=dbusmock.MOCK_IFACE,
        )
        spin_until(lambda: adapter.fd is not None)
    finally:
        adapter.close()
        login.terminate()
        saver.terminate()
        drain()


def test_session_missing_sources():
    events = []
    adapter = Session(
        gio_bus(Gio.BusType.SYSTEM), gio_bus(Gio.BusType.SESSION), cfg(), events.append
    )
    try:
        adapter.start()
        spin_until(lambda: adapter.ready)
        assert events == [Event("Locked", False)]
    finally:
        adapter.close()
        drain()


def test_audio_snapshot_inflight_and_backoff(fake_pactl, tmp_path):
    events = []
    audio = Audio(
        cfg(), Store(tmp_path / "state.json"), events.append, fake_pactl.command
    )
    try:
        audio.start()
        spin_until(lambda: audio.ready)
        baseline = len(fake_pactl.calls())
        audio.refresh()
        for _ in range(10):
            audio.refresh()
        spin_until(lambda: not audio.refresh_running)
        assert len(fake_pactl.calls()) - baseline == 6
        fake_pactl.update({"down": True})
        fake_pactl.event(b"EXIT")
        spin_until(lambda: audio.retry_delay == 2)
        spin_until(lambda: audio.retry_delay == 4, seconds=4)
        assert events.count(Event("AudioBackend", False)) >= 2
        fake_pactl.update({"down": False})
        spin_until(lambda: audio.retry_delay == 1, seconds=5)
    finally:
        audio.close()
        drain()


def test_bluez_other_device_alias_pairing_and_removal(bluez_server):
    mock, path, _ = bluez_server
    events = []
    bluez = BlueZ(gio_bus(Gio.BusType.SYSTEM), cfg(), events.append)
    bus = dbusmock.BusType.SYSTEM.get_connection()
    device = bus.get_object("org.bluez", path)
    try:
        bluez.start()
        spin_until(lambda: bluez.ready)
        other = str(
            mock.obj.AddDevice(
                "hci0", "00:11:22:33:44:55", "Other", dbus_interface="org.bluez.Mock"
            )
        )
        bus.get_object("org.bluez", other).UpdateProperties(
            "org.bluez.Device1",
            {"Connected": dbus.Boolean(True)},
            dbus_interface=dbusmock.MOCK_IFACE,
        )
        drain()
        assert not bluez.connected
        device.UpdateProperties(
            "org.bluez.Device1",
            {"Alias": "Renamed"},
            dbus_interface=dbusmock.MOCK_IFACE,
        )
        spin_until(lambda: bluez.name == "Renamed")
        device.UpdateProperties(
            "org.bluez.Device1",
            {"Paired": dbus.Boolean(False)},
            dbus_interface=dbusmock.MOCK_IFACE,
        )
        spin_until(lambda: not bluez.available)
        bluez.connect()
        assert events[-1] == Event("ConnectResult", "org.bluez.Error.NotReady")
        calls = device.GetCalls(dbus_interface=dbusmock.MOCK_IFACE)
        assert not any(
            str(c[1]) in {"Pair", "RemoveDevice", "Connect", "Set"} for c in calls
        )
        mock.obj.EmitSignal(
            "org.freedesktop.DBus.ObjectManager",
            "InterfacesRemoved",
            "oas",
            [dbus.ObjectPath(path), ["org.bluez.Device1"]],
            dbus_interface=dbusmock.MOCK_IFACE,
        )
        spin_until(lambda: not bluez.path)
    finally:
        bluez.close()
        drain()
