# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Fermich srl
"""Automatic profiles through the parser, private BlueZ bus and daemon API."""

import json
import logging
import tomllib

import dbus
import dbusmock
import pytest
from gi.repository import Gio, GLib
from helpers import ADDRESS, drain, gio_bus, spin_until
from test_service import client
from test_service import daemon as shared_daemon
from test_tray import rpc

from scambio.api import BUS_NAME, INTERFACE, PATH
from scambio.config import TEMPLATE, Config, load, parse, resolve_profile, template
from scambio.core.audio import Audio
from scambio.core.bluez import DEVICE, BlueZ
from scambio.core.policy import Context, Event
from scambio.core.service import Service
from scambio.core.session import Session
from scambio.state import Store

daemon = shared_daemon
OTHER = "11:22:33:44:55:66"


@pytest.mark.parametrize(
    "name,expected",
    [
        ("Oakley Meta 002Z", "meta_glasses"),
        ("Ray-Ban Meta 1A2B", "meta_glasses"),
        ("RayBan Stories", "meta_glasses"),
        ("oAkLeY", "meta_glasses"),
        ("ray-ban", "meta_glasses"),
        ("mEtA", "meta_glasses"),
        ("My (Meta) glasses", "meta_glasses"),
        ("Meta Quest", "meta_glasses"),
        ("Metallica Buds", "generic"),
        ("WH-1000XM5", "generic"),
        ("metaverse", "generic"),
        ("somemeta", "generic"),
        ("", "generic"),
    ],
)
def test_name_matching(name, expected):
    assert resolve_profile("auto", name) == expected
    for explicit in ("generic", "meta_glasses"):
        assert resolve_profile(explicit, name) == explicit


def test_auto_defaults_and_localized_templates(tmp_path):
    assert Config().device.profile == parse({}).device.profile == "auto"
    assert parse(tomllib.loads(TEMPLATE)) == Config()
    for language in ("it", "en", "de"):
        text = template(language)
        assert 'profile = "auto"' in text
        assert parse(tomllib.loads(text)) == Config()
        comment = text.split('profile = "auto"')[0].splitlines()[-1]
        assert all(value in comment for value in ("auto", "generic", "meta_glasses"))
    path = tmp_path / "config.toml"
    assert load(path) == Config()


@pytest.mark.parametrize("profile", ["auto", "generic", "meta_glasses"])
@pytest.mark.parametrize("delay", [None, 0, 37])
def test_profile_parser_preserves_explicit_timing(profile, delay):
    config = parse(
        {
            "device": {"profile": profile},
            "policy": {} if delay is None else {"resume_delay_ms": delay},
        }
    )
    assert config.device.profile == profile
    assert config.resume_delay_explicit is (delay is not None)
    assert config.policy.resume_delay_ms == (
        delay if delay is not None else 2000 if profile == "meta_glasses" else 0
    )


@pytest.fixture
def profile_service(bluez_server, fake_pactl, tmp_path):
    services = []

    def create(address=ADDRESS, profile="auto", delay=None):
        config_file = tmp_path / "config.toml"
        config_file.write_text(
            f'[device]\naddress = "{address}"\nprofile = "{profile}"\n'
            '[ui]\ntray = false\nnotifications = false\n[shortcut]\npreferred = ""\n'
            + (f"[policy]\nresume_delay_ms = {delay}\n" if delay is not None else "")
        )
        config = load(config_file)
        store = Store(tmp_path / "state.json")
        system, session = gio_bus(Gio.BusType.SYSTEM), gio_bus(Gio.BusType.SESSION)

        def factory(emit):
            return (
                BlueZ(system, config, emit),
                Audio(config, store, emit, fake_pactl.command),
                Session(system, session, config, emit),
            )

        service = Service(session, config, store, config_file, factory)
        services.append(service)
        assert service.start()
        spin_until(lambda: service.initialized)
        return service

    yield create
    for service in services:
        service.close()
    drain()


def update_name(path, **values):
    dbusmock.BusType.SYSTEM.get_connection().get_object(
        "org.bluez", path
    ).UpdateProperties(DEVICE, values, dbus_interface=dbusmock.MOCK_IFACE)


def read_properties(service):
    return rpc(
        service.bus,
        BUS_NAME,
        "org.freedesktop.DBus.Properties",
        "GetAll",
        "(s)",
        (INTERFACE,),
        PATH,
    )[0]


def test_bluez_alias_api_signals_and_log_once(profile_service, bluez_server, caplog):
    caplog.set_level(logging.INFO)
    mock, path, _ = bluez_server
    update_name(path, Alias="Oakley Meta 002Z")
    service = profile_service()
    before = service.config_file.read_bytes()
    assert read_properties(service)["DeviceProfile"] == "meta_glasses"
    assert read_properties(service)["DeviceProfileSource"] == "auto"
    assert service.policy.resume_delay_ms == 2000
    changes = []
    sub = service.bus.signal_subscribe(
        BUS_NAME,
        "org.freedesktop.DBus.Properties",
        "PropertiesChanged",
        PATH,
        INTERFACE,
        Gio.DBusSignalFlags.NONE,
        lambda *args: changes.append(args[-1].unpack()[1]),
    )
    try:
        update_name(path, Alias="RayBan Stories")
        spin_until(lambda: service.name == "RayBan Stories")
        update_name(path, Alias="RayBan Stories")
        service.reload()
        drain()
        assert caplog.text.count("device profile: meta_glasses (auto, from name)") == 1
        assert "name='Oakley Meta 002Z'" in caplog.text
        assert not any("DeviceProfile" in change for change in changes)
        update_name(path, Alias="WH-1000XM5")
        spin_until(
            lambda: any(change.get("DeviceProfile") == "generic" for change in changes)
        )
        assert service.policy.resume_delay_ms == 0
        assert read_properties(service)["DeviceProfile"] == "generic"
        other = mock.obj.AddDevice(
            "hci0", OTHER, "Oakley Meta", dbus_interface="org.bluez.Mock"
        )
        update_name(other, Alias="Meta unrelated")
        drain()
        assert service.profile == "generic"
        assert OTHER not in caplog.text and "Meta unrelated" not in caplog.text
        assert service.config_file.read_bytes() == before
    finally:
        service.bus.signal_unsubscribe(sub)


def test_unknown_device_appearance_and_removal(profile_service, bluez_server):
    mock, _, _ = bluez_server
    service = profile_service(address=OTHER)
    assert service.profile == "generic" and service.policy.resume_delay_ms == 0
    path = mock.obj.AddDevice(
        "hci0", OTHER, "Ray-Ban Meta", dbus_interface="org.bluez.Mock"
    )
    spin_until(lambda: service.profile == "meta_glasses")
    mock.obj.EmitSignal(
        "org.freedesktop.DBus.ObjectManager",
        "InterfacesRemoved",
        "oas",
        [dbus.ObjectPath(path), [DEVICE]],
        dbus_interface=dbusmock.MOCK_IFACE,
    )
    spin_until(lambda: service.profile == "generic")
    assert service.name == "" and service.policy.resume_delay_ms == 0


def test_name_fallback_and_empty_alias(profile_service, bluez_server):
    mock, path, _ = bluez_server
    update_name(path, Name="RayBan Stories", Alias="")
    service = profile_service()
    assert service.profile == "generic"
    device = dbusmock.BusType.SYSTEM.get_connection().get_object("org.bluez", path)
    device.EmitSignal(
        "org.freedesktop.DBus.Properties",
        "PropertiesChanged",
        "sa{sv}as",
        [DEVICE, dbus.Dictionary({}, signature="sv"), ["Alias"]],
        dbus_interface=dbusmock.MOCK_IFACE,
    )
    spin_until(lambda: service.profile == "meta_glasses")
    assert service.name == "RayBan Stories"
    update_name(path, Name="Metallica Buds")
    spin_until(lambda: service.profile == "generic")
    device.EmitSignal(
        "org.freedesktop.DBus.Properties",
        "PropertiesChanged",
        "sa{sv}as",
        [DEVICE, dbus.Dictionary({}, signature="sv"), ["Name"]],
        dbus_interface=dbusmock.MOCK_IFACE,
    )
    spin_until(lambda: service.name == "")
    assert service.profile == "generic"


@pytest.mark.parametrize("profile", ["auto", "generic", "meta_glasses"])
@pytest.mark.parametrize("delay", [None, 0, 37])
def test_effective_timing_and_explicit_precedence(
    profile_service, bluez_server, profile, delay
):
    _, path, _ = bluez_server
    update_name(path, Alias="Oakley Meta")
    service = profile_service(profile=profile, delay=delay)
    expected = "generic" if profile == "generic" else "meta_glasses"
    assert service.profile == expected
    assert service.profile_source == ("auto" if profile == "auto" else "config")
    assert service.policy.resume_delay_ms == (
        delay if delay is not None else 0 if expected == "generic" else 2000
    )
    update_name(path, Alias="WH-1000XM5")
    spin_until(lambda: service.name == "WH-1000XM5")
    expected = "meta_glasses" if profile == "meta_glasses" else "generic"
    assert service.profile == expected
    assert service.policy.resume_delay_ms == (
        delay if delay is not None else 0 if expected == "generic" else 2000
    )


def test_reload_source_signal_and_preserve_pending_resume(
    profile_service, bluez_server
):
    _, path, _ = bluez_server
    update_name(path, Alias="Oakley Meta")
    service = profile_service()
    durations = []

    def schedule(milliseconds, callback):
        durations.append(milliseconds)
        return GLib.timeout_add(60000, callback)

    service.schedule = schedule
    service.ctx = Context(state="connecting", held=True, device_connected=True)
    service.event(Event("DeviceSinkAppeared"))
    timer = service.timers["RESUME"]
    assert durations[-1] == 2000
    update_name(path, Alias="WH-1000XM5")
    spin_until(lambda: service.profile == "generic")
    assert service.timers["RESUME"] == timer and durations == [2000]
    service._cancel_timer("RESUME")
    service.ctx = Context(state="connecting", held=True, device_connected=True)
    service.event(Event("DeviceSinkAppeared"))
    assert durations[-1] == 0
    changes = []
    sub = service.bus.signal_subscribe(
        BUS_NAME,
        "org.freedesktop.DBus.Properties",
        "PropertiesChanged",
        PATH,
        INTERFACE,
        Gio.DBusSignalFlags.NONE,
        lambda *args: changes.append(args[-1].unpack()[1]),
    )
    try:
        service.config_file.write_text(
            service.config_file.read_text().replace(
                'profile = "auto"', 'profile = "generic"'
            )
        )
        current = service.timers["RESUME"]
        service.reload()
        spin_until(
            lambda: any(
                change.get("DeviceProfileSource") == "config" for change in changes
            )
        )
        assert service.profile == "generic" and service.timers["RESUME"] == current
        assert not any("DeviceProfile" in change for change in changes)
        service.config_file.write_text(
            service.config_file.read_text().replace(
                'profile = "generic"', 'profile = "meta_glasses"'
            )
            + "[policy]\nresume_delay_ms = 37\n"
        )
        service.reload()
        assert (
            service.profile == "meta_glasses" and service.policy.resume_delay_ms == 37
        )
        assert service.timers["RESUME"] == current
    finally:
        service.bus.signal_unsubscribe(sub)


def test_bluez_restart_clears_automatic_profile(profile_service, bluez_server):
    mock, path, _ = bluez_server
    update_name(path, Alias="Oakley Meta")
    service = profile_service()
    mock.terminate()
    spin_until(lambda: service.profile == "generic")
    from helpers import bluez_mock

    replacement, new_path, _ = bluez_mock()
    try:
        update_name(new_path, Alias="RayBan Stories")
        spin_until(lambda: service.profile == "meta_glasses")
    finally:
        replacement.terminate()


def test_cli_prints_effective_profile(daemon, bluez_server):
    _, path, _ = bluez_server
    update_name(path, Alias="Oakley Meta")
    from test_service import properties

    spin_until(lambda: properties()["DeviceProfile"] == "meta_glasses")
    result = client("status")
    assert result.returncode == 0
    assert "DeviceProfile: meta_glasses" in result.stdout
    assert "DeviceProfileSource: auto" in result.stdout
    assert (
        json.loads(client("status", "--json").stdout)["DeviceProfile"] == "meta_glasses"
    )


def test_changed_address_resolves_on_restart(profile_service, bluez_server):
    mock, path, _ = bluez_server
    update_name(path, Alias="Oakley Meta")
    mock.obj.AddDevice("hci0", OTHER, "WH-1000XM5", dbus_interface="org.bluez.Mock")
    service = profile_service()
    assert service.profile == "meta_glasses"
    assert service.set_config({"device.address": OTHER})
    assert load(service.config_file).device.address == OTHER
    assert (
        service.config.device.address == ADDRESS
    )  # Existing API restarts to apply it.
    service.close()
    second = profile_service(address=OTHER)
    assert second.name == "WH-1000XM5" and second.profile == "generic"


def test_explicit_generic_existing_file_is_not_migrated(profile_service):
    service = profile_service(profile="generic")
    before = service.config_file.read_bytes()
    service.event(Event("DeviceName", "Oakley Meta"))
    service.reload()
    assert service.profile == "generic" and service.profile_source == "config"
    assert service.config_file.read_bytes() == before


def test_recognition_uses_full_name_while_display_is_bounded(
    profile_service, bluez_server
):
    _, path, _ = bluez_server
    prefix = "a" * 70
    update_name(path, Alias=prefix + " Meta")
    service = profile_service()
    assert service.profile == "meta_glasses"
    assert len(service.name) == 64
    assert read_properties(service)["DeviceName"] == prefix[:63] + "…"
    update_name(path, Alias=prefix + " Buds")
    spin_until(lambda: service.profile == "generic")
    assert service.name == prefix[:63] + "…"
