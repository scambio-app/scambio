"""UI commands exercise the real daemon process on isolated mock buses."""

import json
import subprocess
import sys
from pathlib import Path

import dbus
import dbusmock
import pytest
from gi.repository import Gio
from helpers import drain, spin_until
from test_notifications import calls
from test_notifications import notification_server as notification_server
from test_players import player_factory as player_factory
from test_service import client, properties
from test_service import daemon as daemon

from scambio.api import BUS_NAME, INTERFACE, PATH
from scambio.config import TEMPLATE
from scambio.i18n import Translator
from scambio.ui.tray import MENU, MENU_PATH, SNI_PATH, WATCHER

TRAY_NAMES = []


@pytest.fixture(autouse=True)
def tray_watcher():
    """Discover the real daemon's dedicated tray connection as a desktop does."""
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    info = Gio.DBusNodeInfo.new_for_xml(
        '<node><interface name="org.kde.StatusNotifierWatcher">'
        '<method name="RegisterStatusNotifierItem">'
        '<arg type="s" direction="in"/></method></interface></node>'
    ).interfaces[0]
    TRAY_NAMES.clear()

    def registered(connection, sender, path, interface, method, params, invocation):
        assert params.unpack() == (SNI_PATH,)
        TRAY_NAMES.append(sender)
        invocation.return_value(None)

    registration = bus.register_object(
        "/StatusNotifierWatcher", info, registered, None, None
    )
    acquired = []
    owner = Gio.bus_own_name_on_connection(
        bus,
        WATCHER,
        Gio.BusNameOwnerFlags.NONE,
        lambda *args: acquired.append(True),
        None,
    )
    spin_until(lambda: acquired)
    yield
    Gio.bus_unown_name(owner)
    bus.unregister_object(registration)
    TRAY_NAMES.clear()
    drain()


def menu():
    if not TRAY_NAMES:
        raise dbus.DBusException("Tray not registered")
    return dbusmock.BusType.SESSION.get_connection().get_object(
        TRAY_NAMES[-1], MENU_PATH
    )


def wait_tray():
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    ready = []

    def check(*args):
        ready.append(True)

    sub = bus.signal_subscribe(
        BUS_NAME, None, None, None, None, Gio.DBusSignalFlags.NONE, check
    )
    try:

        def exists():
            try:
                menu().GetLayout(
                    0, -1, dbus.Array([], signature="s"), dbus_interface=MENU
                )
                return True
            except dbus.DBusException:
                return False

        spin_until(exists)
    finally:
        bus.signal_unsubscribe(sub)


def test_service_reload_flags_language_and_quit(daemon, tmp_path, notification_server):
    wait_tray()
    path = tmp_path / "config.toml"
    original = path.read_text()
    bus = dbusmock.BusType.SESSION.get_connection()
    api = bus.get_object(BUS_NAME, PATH)
    path.write_text(
        original.replace('language = "auto"', 'language = "de"').replace(
            "notifications = true", "notifications = false"
        )
    )
    api.Reload(dbus_interface=INTERFACE)
    rows = menu().GetLayout(0, -1, dbus.Array([], signature="s"), dbus_interface=MENU)[
        1
    ][2]
    assert rows[3][1]["label"] == Translator("de").tr("tray-action-to-pc")
    api.SetPriority(True, dbus_interface=INTERFACE)
    drain()
    assert calls(notification_server, "Notify") == []
    path.write_text(path.read_text().replace("tray = true", "tray = false"))
    api.Reload(dbus_interface=INTERFACE)
    with pytest.raises(dbus.DBusException):
        menu().GetLayout(0, -1, dbus.Array([], signature="s"), dbus_interface=MENU)
    assert properties()["IphonePriority"]
    path.write_text(original)
    api.Reload(dbus_interface=INTERFACE)
    wait_tray()
    # Client receives a successful reply before process exit.
    api.Quit(dbus_interface=INTERFACE)
    daemon.wait(timeout=5)
    assert daemon.returncode == 0


@pytest.mark.parametrize("kind", ["grab", "release"])
def test_quit_resumes_only_grab(daemon, fake_pactl, tmp_path, player_factory, kind):
    player = player_factory("quit")
    fake_pactl.update(
        {"streams": [{"index": 7, "sink": 1, "corked": False, "properties": {}}]}
    )
    fake_pactl.event()
    spin_until(lambda: player.calls() == ["Pause"])
    if kind == "release":
        fake_pactl.add_sink()
        fake_pactl.event()
        spin_until(lambda: player.calls() == ["Pause", "Play"])
        assert client("switch").returncode == 0
        spin_until(lambda: player.calls() == ["Pause", "Play", "Pause"])
    before = fake_pactl.read()["default"]
    dbusmock.BusType.SESSION.get_connection().get_object(BUS_NAME, PATH).Quit(
        dbus_interface=INTERFACE
    )
    daemon.wait(timeout=5)
    assert daemon.returncode == 0
    assert player.calls() == (
        ["Pause", "Play"] if kind == "grab" else ["Pause", "Play", "Pause"]
    )
    assert fake_pactl.read()["default"] == before
    assert json.loads((tmp_path / "state.json").read_text())["resume_players"] is None


def test_real_service_menu_own_and_external_commands(
    daemon, fake_pactl, notification_server
):
    wait_tray()
    menu().Event(5, "clicked", dbus.Int32(0, variant_level=1), 0, dbus_interface=MENU)
    spin_until(lambda: properties()["IphonePriority"])
    drain()
    assert not calls(notification_server, "Notify")
    assert client("priority", "off").returncode == 0
    spin_until(lambda: len(calls(notification_server, "Notify")) == 1)
    fake_pactl.add_sink()
    fake_pactl.event()
    menu().Event(4, "clicked", dbus.Int32(0, variant_level=1), 0, dbus_interface=MENU)
    spin_until(lambda: properties()["State"] == "on_pc")
    drain()
    assert len(calls(notification_server, "Notify")) == 1
    menu().Event(8, "clicked", dbus.Int32(0, variant_level=1), 0, dbus_interface=MENU)
    daemon.wait(timeout=5)
    assert daemon.returncode == 0


@pytest.mark.parametrize("mode", ["setup", "audio", "bad_design", "bad_catalog", "off"])
def test_process_startup_and_fail_open(
    fake_pactl, bluez_server, notification_server, tmp_path, monkeypatch, mode
):
    config = TEMPLATE
    if mode != "setup":
        config = config.replace('address = ""', 'address = "AA:BB:CC:DD:EE:FF"')
    if mode == "audio":
        fake_pactl.update({"version": "15.0"})
    if mode == "bad_design":
        monkeypatch.setenv("SCAMBIO_DESIGN_DIR", str(tmp_path / "missing"))
    if mode == "bad_catalog":
        monkeypatch.setenv("SCAMBIO_LOCALE_DIR", str(tmp_path / "missing"))
    if mode == "off":
        config = config.replace("tray = true", "tray = false").replace(
            "notifications = true", "notifications = false"
        )
    (tmp_path / "config.toml").write_text(config)
    with (tmp_path / "daemon.log").open("w") as log:
        process = subprocess.Popen(
            [
                sys.executable,
                str(Path(__file__).parent / "fixtures/run_daemon.py"),
                str(tmp_path),
            ],
            stdout=log,
            stderr=log,
        )
        try:
            bus = dbusmock.BusType.SESSION.get_connection()
            spin_until(lambda: bus.name_has_owner(BUS_NAME))
            if mode in {"setup", "audio"}:
                wait_tray()
                spin_until(lambda: calls(notification_server, "Notify"))
                key = (
                    "notify-not-configured-title"
                    if mode == "setup"
                    else "notify-audio-down-title"
                )
                assert calls(notification_server, "Notify")[0][1][3] == Translator().tr(
                    key
                )
            else:
                spin_until(lambda: properties()["State"] == "released")
                drain()
                assert not calls(notification_server, "Notify")
                with pytest.raises(dbus.DBusException):
                    menu().GetLayout(
                        0, -1, dbus.Array([], signature="s"), dbus_interface=MENU
                    )
                if mode != "off":
                    assert "UI disabled" in (tmp_path / "daemon.log").read_text()
            api = bus.get_object(BUS_NAME, PATH)
            api.SetPriority(True, dbus_interface=INTERFACE)
            assert properties()["IphonePriority"]
            api.Quit(dbus_interface=INTERFACE)
            process.wait(timeout=5)
            assert process.returncode == 0
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=5)


def test_cli_language_from_readonly_config(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    path = tmp_path / ".config/scambio/config.toml"
    monkeypatch.setenv("LANGUAGE", "en")
    assert Translator("en").tr("cli-description") in client("--help").stdout
    assert not path.exists()
    path.parent.mkdir(parents=True)
    path.write_text('[ui]\nlanguage = "de"\n')
    assert Translator("de").tr("cli-description") in client("--help").stdout
    assert Translator("de").tr("cli-help-help") in client("switch", "--help").stdout
    assert path.read_text() == '[ui]\nlanguage = "de"\n'


def test_inhibitor_uses_language_at_acquisition():
    from dataclasses import replace

    from scambio.config import Config
    from scambio.core.session import Session

    with dbusmock.SpawnedMock.spawn_with_template(
        "logind", stdout=subprocess.DEVNULL
    ) as mock:
        config = Config(language="de")
        adapter = Session(
            Gio.bus_get_sync(Gio.BusType.SYSTEM, None),
            Gio.bus_get_sync(Gio.BusType.SESSION, None),
            config,
            lambda event: None,
        )
        try:
            adapter._inhibit()
            spin_until(lambda: adapter.fd is not None)
            assert calls(mock.obj, "Inhibit")[-1][1][2] == Translator("de").tr(
                "session-inhibit-reason"
            )
            adapter.reload(replace(config, language="it"))
            # Reload does not replace an existing fd. The next acquisition uses Italian.
            adapter._inhibit()
            spin_until(lambda: adapter.fd is not None)
            assert calls(mock.obj, "Inhibit")[-1][1][2] == Translator("it").tr(
                "session-inhibit-reason"
            )
        finally:
            adapter.close()
