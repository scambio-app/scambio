import subprocess
from dataclasses import replace

import dbus
import dbusmock
import pytest
from gi.repository import Gio, GLib
from helpers import ADDRESS, drain, spin_until
from test_service import client, properties
from test_service import daemon as shared_daemon
from test_service_players import executor as shared_executor
from test_tray import rpc

from scambio.api import BUS_NAME, INTERFACE, PATH
from scambio.config import TEMPLATE, load
from scambio.core.bluez import ADAPTER, AUDIO_UUIDS, DEVICE, BlueZ

daemon = shared_daemon
executor = shared_executor


def set_config(connection, values):
    return rpc(connection, BUS_NAME, INTERFACE, "SetConfig", "(a{sv})", (values,), PATH)


@pytest.fixture
def running_executor(executor):
    service, ports = executor
    service.config_file.write_text(
        TEMPLATE.replace('address = ""', f'address = "{ADDRESS}"')
    )
    service.cgroup = lambda: "0::/user.slice/test.scope\n"
    service.ctx = replace(service.ctx, state="released")
    assert service.start()
    yield service, ports


def test_config_signal_before_reply(daemon, tmp_path):
    events = []
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    sub = bus.signal_subscribe(
        BUS_NAME,
        "org.freedesktop.DBus.Properties",
        "PropertiesChanged",
        PATH,
        None,
        Gio.DBusSignalFlags.NONE,
        lambda *args: (
            events.append("Config") if "Config" in args[-1].unpack()[1] else None
        ),
    )
    try:

        def done(conn, result):
            conn.call_finish(result)
            events.append("reply")

        bus.call(
            BUS_NAME,
            PATH,
            INTERFACE,
            "SetConfig",
            GLib.Variant(
                "(a{sv})", ({"policy.release_idle_seconds": GLib.Variant("i", 180)},)
            ),
            None,
            Gio.DBusCallFlags.NO_AUTO_START,
            1000,
            None,
            done,
        )
        spin_until(lambda: "reply" in events)
        assert events == ["Config", "reply"]
        assert properties()["Config"]["policy.release_idle_seconds"] == 180
        assert load(tmp_path / "config.toml").policy.release_idle_seconds == 180
        assert "policy.release_idle_seconds=180" in client("status").stdout
    finally:
        bus.signal_unsubscribe(sub)


@pytest.mark.parametrize(
    "values",
    [
        {"ui.tray": GLib.Variant("i", 0)},
        {"policy.release_idle_seconds": GLib.Variant("x", 180)},
        {"shortcut.preferred": GLib.Variant("s", "")},
        {"ui.language": GLib.Variant("s", "fr")},
    ],
)
def test_rejection_has_no_error_signal_or_last_error(running_executor, values):
    service, _ = running_executor
    before = service.config_file.read_bytes()
    error_before = service.ctx.last_error
    events = []
    sub = service.bus.signal_subscribe(
        BUS_NAME,
        INTERFACE,
        "Error",
        PATH,
        None,
        Gio.DBusSignalFlags.NONE,
        lambda *args: events.append(args),
    )
    try:
        with pytest.raises(GLib.Error) as exc:
            set_config(service.bus, values)
        assert Gio.DBusError.get_remote_error(exc.value).endswith(".ConfigInvalid")
        drain()
        assert not events
        assert service.ctx.last_error == error_before
        assert service.config_file.read_bytes() == before
    finally:
        service.bus.signal_unsubscribe(sub)


@pytest.mark.parametrize("state", ["connecting", "on_pc", "releasing"])
@pytest.mark.parametrize("external", [False, True])
def test_busy_checks_merged_device(running_executor, state, external):
    service, _ = running_executor
    service.ctx = replace(service.ctx, state=state)
    other = "11:22:33:44:55:66"
    if external:
        service.config_file.write_text(
            service.config_file.read_text().replace(ADDRESS, other)
        )
        values = {"ui.tray": GLib.Variant("b", False)}
    else:
        values = {"device.address": GLib.Variant("s", other)}
    before = service.config_file.read_bytes()
    with pytest.raises(GLib.Error) as exc:
        set_config(service.bus, values)
    assert Gio.DBusError.get_remote_error(exc.value).endswith(".DeviceBusy")
    assert service.config_file.read_bytes() == before


def test_device_change_shuts_down_before_reexec_without_systemd(running_executor):
    service, _ = running_executor
    restarted = []
    service.restart_done = lambda: restarted.append((service.closed, service.owned))
    set_config(service.bus, {"device.address": GLib.Variant("s", "11:22:33:44:55:66")})
    spin_until(lambda: restarted)
    assert restarted == [(True, False)]
    assert service.config.device.address == ADDRESS
    assert load(service.config_file).device.address == "11:22:33:44:55:66"


def test_invalid_file_is_not_rewritten(running_executor):
    service, _ = running_executor
    service.config_file.write_bytes(b"[broken TOML\r\n")
    previous = service.ctx.last_error
    with pytest.raises(GLib.Error) as exc:
        set_config(service.bus, {"ui.tray": GLib.Variant("b", False)})
    assert Gio.DBusError.get_remote_error(exc.value).endswith(".ConfigInvalid")
    assert service.config_file.read_bytes() == b"[broken TOML\r\n"
    assert service.ctx.last_error == previous


def test_restart_failure_keeps_daemon_and_written_file(running_executor, caplog):
    service, _ = running_executor
    service.cgroup = lambda: "0::/test/scambio.service\n"
    set_config(service.bus, {"device.address": GLib.Variant("s", "11:22:33:44:55:66")})
    spin_until(lambda: "Cannot restart scambio.service" in caplog.text)
    assert not service.closed and service.config.device.address == ADDRESS
    assert load(service.config_file).device.address == "11:22:33:44:55:66"


def test_list_devices_public_method(daemon, bluez_server):
    _, device, _ = bluez_server
    dbusmock.BusType.SYSTEM.get_connection().get_object(
        "org.bluez", device
    ).UpdateProperties(
        DEVICE,
        {"UUIDs": dbus.Array(list(AUDIO_UUIDS), signature="s")},
        dbus_interface=dbusmock.MOCK_IFACE,
    )
    reply = rpc(
        Gio.bus_get_sync(Gio.BusType.SESSION, None),
        BUS_NAME,
        INTERFACE,
        "ListDevices",
        path=PATH,
    ).unpack()[0]
    assert reply == [(ADDRESS, "Test headset")]


def test_restart_unit_after_success(running_executor):
    service, _ = running_executor
    service.cgroup = lambda: "0::/user.slice/app.slice/scambio.service\n"
    with dbusmock.SpawnedMock.spawn_for_name(
        "org.freedesktop.systemd1",
        "/org/freedesktop/systemd1",
        "org.freedesktop.systemd1.Manager",
        stdout=subprocess.DEVNULL,
    ) as mock:
        mock.obj.AddMethod(
            "org.freedesktop.systemd1.Manager",
            "RestartUnit",
            "ss",
            "o",
            'ret = "/job/1"',
            dbus_interface=dbusmock.MOCK_IFACE,
        )
        set_config(
            service.bus, {"device.address": GLib.Variant("s", "11:22:33:44:55:66")}
        )
        spin_until(
            lambda: mock.obj.GetMethodCalls(
                "RestartUnit", dbus_interface=dbusmock.MOCK_IFACE
            )
        )
        assert mock.obj.GetMethodCalls(
            "RestartUnit", dbus_interface=dbusmock.MOCK_IFACE
        )[0][1] == ["scambio.service", "replace"]
        assert service.config.device.address == ADDRESS


def test_ui_apply_and_reload_config(running_executor):
    service, _ = running_executor
    applied = []

    class UI:
        def apply_config(self, config):
            applied.append(config)

        def stop(self):
            pass

    service.ui = UI()
    set_config(
        service.bus,
        {"ui.tray": GLib.Variant("b", False), "ui.language": GLib.Variant("s", "de")},
    )
    assert not applied[-1].tray and applied[-1].language == "de"
    assert service.properties()["Config"].unpack()["ui.language"] == "de"
    service.config_file.write_text(
        service.config_file.read_text().replace('"de"', '"it"')
    )
    service.reload()
    assert applied[-1].language == "it"
    assert service.properties()["Config"].unpack()["ui.language"] == "it"


def test_list_devices_filters_sorts_deduplicates(bluez_server):
    mock, _, adapter_path = bluez_server
    system = dbusmock.BusType.SYSTEM.get_connection()
    mock.obj.AddAdapter("hci1", "second", dbus_interface="org.bluez.Mock")
    specs = [
        ("hci0", "00:00:00:00:00:01", "zulu", True, list(AUDIO_UUIDS)),
        ("hci0", "00:00:00:00:00:02", "Alpha", True, [next(iter(AUDIO_UUIDS))]),
        ("hci1", "00:00:00:00:00:01", "duplicate", True, list(AUDIO_UUIDS)),
        ("hci0", "00:00:00:00:00:03", "unpaired", False, list(AUDIO_UUIDS)),
        ("hci0", "00:00:00:00:00:04", "non-audio", True, ["unrelated"]),
    ]
    for adapter, address, alias, paired, uuids in specs:
        path = mock.obj.AddDevice(
            adapter, address, alias, dbus_interface="org.bluez.Mock"
        )
        system.get_object("org.bluez", path).UpdateProperties(
            DEVICE,
            {"Paired": dbus.Boolean(paired), "UUIDs": dbus.Array(uuids, signature="s")},
            dbus_interface=dbusmock.MOCK_IFACE,
        )
    from scambio.config import Config

    bluez = BlueZ(
        Gio.bus_get_sync(Gio.BusType.SYSTEM, None), Config(), lambda event: None
    )
    try:
        found = []
        bluez.list_devices(found.append)
        spin_until(lambda: found)
        assert found[0] == [
            ("00:00:00:00:00:02", "Alpha"),
            ("00:00:00:00:00:01", "zulu"),
        ]
        for path in (adapter_path, "/org/bluez/hci1"):
            system.get_object("org.bluez", path).UpdateProperties(
                ADAPTER,
                {"Powered": dbus.Boolean(False)},
                dbus_interface=dbusmock.MOCK_IFACE,
            )
        found.clear()
        bluez.list_devices(found.append)
        spin_until(lambda: found)
        assert found == [[]]
    finally:
        bluez.close()


def test_list_devices_without_bluez():
    from scambio.config import Config

    bluez = BlueZ(
        Gio.bus_get_sync(Gio.BusType.SYSTEM, None), Config(), lambda event: None
    )
    found = []
    try:
        bluez.list_devices(found.append)
        spin_until(lambda: found)
        assert found == [[]]
    finally:
        bluez.close()


def test_unexpected_set_config_exception_returns_failed(
    running_executor, monkeypatch, caplog
):
    service, _ = running_executor

    def fail(changes):
        raise RuntimeError("unexpected write failure")

    monkeypatch.setattr(service, "set_config", fail)
    with pytest.raises(GLib.Error) as error:
        set_config(service.bus, {"ui.tray": GLib.Variant("b", False)})
    assert (
        Gio.DBusError.get_remote_error(error.value)
        == "org.freedesktop.DBus.Error.Failed"
    )
    assert any(
        record.exc_info and "SetConfig" in record.message for record in caplog.records
    )
