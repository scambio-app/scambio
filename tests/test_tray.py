import copy
import subprocess
from dataclasses import replace

import dbus
import dbusmock
import pytest
from gi.repository import Gio, GLib
from helpers import drain, spin_until
from test_notifications import calls, error, update
from test_notifications import ui_client as ui_client

from scambio.api import SETTINGS_BUS_NAME, SETTINGS_PATH
from scambio.config import Config
from scambio.i18n import Translator
from scambio.paths import design_dir
from scambio.ui import DisabledUi, start_ui
from scambio.ui.actions import create_actions
from scambio.ui.presentation import Design, present
from scambio.ui.tray import MENU, MENU_PATH, SNI, SNI_PATH, WATCHER, Tray


def rpc(bus, destination, interface, method, signature="()", args=(), path=MENU_PATH):
    results = []

    def done(connection, result):
        try:
            results.append(connection.call_finish(result))
        except GLib.Error as exc:
            results.append(exc)

    bus.call(
        destination,
        path,
        interface,
        method,
        GLib.Variant(signature, args),
        None,
        Gio.DBusCallFlags.NO_AUTO_START,
        2000,
        None,
        done,
    )
    spin_until(lambda: results)
    if isinstance(results[0], Exception):
        raise results[0]
    return results[0]


def watcher():
    mock = dbusmock.SpawnedMock.spawn_for_name(
        WATCHER, "/StatusNotifierWatcher", WATCHER, stdout=subprocess.DEVNULL
    )
    mock.obj.AddMethod(
        WATCHER,
        "RegisterStatusNotifierItem",
        "s",
        "",
        "",
        dbus_interface=dbusmock.MOCK_IFACE,
    )
    return mock


@pytest.fixture
def tray(ui_client):
    client, obj = ui_client
    design = Design.load(design_dir() / "ui/tray.json")
    opened = []
    model = present(design, client.props, "", 0, Translator("en"))
    tray = Tray(
        client.connection,
        design,
        model,
        create_actions(client),
        lambda: opened.append(True),
        1000,
    )
    yield tray, client, obj, opened
    tray.stop()
    drain()


def test_watcher_registers_and_restarts(tray):
    tray, client, obj, _ = tray
    for _ in range(2):
        with watcher() as server:
            spin_until(lambda: calls(server.obj, "RegisterStatusNotifierItem"))
            assert calls(server.obj, "RegisterStatusNotifierItem")[0][1] == [tray.name]
        drain()


def test_settings_menu_activation_and_missing_service(tray, caplog):
    item, client, _, _ = tray
    assert item.model.menu[7]["visible"]
    with dbusmock.SpawnedMock.spawn_for_name(
        SETTINGS_BUS_NAME,
        SETTINGS_PATH,
        "org.freedesktop.Application",
        stdout=subprocess.DEVNULL,
    ) as mock:
        mock.obj.AddMethod(
            "org.freedesktop.Application",
            "Activate",
            "a{sv}",
            "",
            "",
            dbus_interface=dbusmock.MOCK_IFACE,
        )
        item.event(7, "clicked")
        spin_until(lambda: calls(mock.obj, "Activate"))
    item.event(7, "clicked")
    spin_until(lambda: "make install-user" in caplog.text)


def test_tray_name_disappears_and_returns(ui_client, tmp_path):
    client, _ = ui_client
    config = Config(notifications=False)
    ui = start_ui(
        client.connection,
        config,
        client.bus_name,
        client.path,
        tmp_path / "config.toml",
    )
    bus = dbusmock.BusType.SESSION.get_connection()
    try:
        with watcher() as server:
            spin_until(
                lambda: ui.tray and calls(server.obj, "RegisterStatusNotifierItem")
            )
            name = ui.tray.name
            assert bus.name_has_owner(name)
            ui.apply_config(replace(config, tray=False))
            spin_until(lambda: not bus.name_has_owner(name))
            ui.apply_config(config)
            spin_until(
                lambda: len(calls(server.obj, "RegisterStatusNotifierItem")) == 2
            )
            assert bus.name_has_owner(name)
            assert calls(server.obj, "RegisterStatusNotifierItem")[-1][1] == [name]
    finally:
        ui.stop()
    spin_until(lambda: not bus.name_has_owner(name))


def test_properties_layout_and_methods(tray):
    tray, client, obj, opened = tray
    bus, dest = client.connection, client.connection.get_unique_name()
    props = rpc(
        bus, dest, "org.freedesktop.DBus.Properties", "GetAll", "(s)", (SNI,), SNI_PATH
    ).unpack()[0]
    assert props["ItemIsMenu"] is True and props["Menu"] == MENU_PATH
    assert props["IconThemePath"] == str(design_dir() / "icons")
    assert props["IconPixmap"] == []
    assert props["ToolTip"][3] == tray.model.tooltip
    layout = rpc(bus, dest, MENU, "GetLayout", "(iias)", (0, -1, [])).unpack()
    assert layout[0] == 1
    assert layout[1][1] == {"children-display": "submenu"}
    children = layout[1][2]
    assert len(children) == 8
    assert children[4][1]["toggle-state"] == 0
    typed = rpc(bus, dest, MENU, "GetProperty", "(is)", (5, "toggle-state"))
    assert typed.get_child_value(0).get_variant().get_type_string() == "i"
    shallow = rpc(bus, dest, MENU, "GetLayout", "(iias)", (0, 0, [])).unpack()
    assert shallow[1][2] == []
    filtered = rpc(
        bus, dest, MENU, "GetGroupProperties", "(aias)", ([1, 4, 999], ["label"])
    ).unpack()[0]
    assert len(filtered) == 2 and set(filtered[0][1]) == {"label"}
    assert rpc(bus, dest, MENU, "AboutToShow", "(i)", (0,)).unpack() == (False,)
    assert opened
    result = rpc(bus, dest, MENU, "AboutToShowGroup", "(ai)", ([0, 999],)).unpack()
    assert result == ([], [999])
    opened_before = list(opened)
    for method, signature, args in [
        ("SecondaryActivate", "(ii)", (0, 0)),
        ("ContextMenu", "(ii)", (0, 0)),
        ("Scroll", "(is)", (1, "vertical")),
    ]:
        rpc(bus, dest, SNI, method, signature, args, SNI_PATH)
    assert opened == opened_before
    for method in ("Switch", "SetPriority", "Quit"):
        assert not calls(obj, method)
    with pytest.raises(GLib.Error):
        rpc(bus, dest, MENU, "GetProperty", "(is)", (999, "label"))
    assert rpc(bus, dest, MENU, "GetLayout", "(iias)", (0, -1, [])).unpack()[0] == 1


@pytest.mark.parametrize(
    "state", ["released", "connecting", "on_pc", "releasing", "unavailable"]
)
def test_activate_not_supported_without_side_effects(tray, state):
    tray, client, obj, opened = tray
    model = present(
        tray.design, client.props | {"State": state}, "", 0, Translator("en")
    )
    tray.update(model)
    bus, dest = client.connection, client.connection.get_unique_name()
    for coordinates in ((0, 0), (-1, 42)):
        with pytest.raises(GLib.Error) as exc:
            rpc(bus, dest, SNI, "Activate", "(ii)", coordinates, SNI_PATH)
        assert Gio.DBusError.get_remote_error(exc.value) == (
            "org.freedesktop.DBus.Error.NotSupported"
        )
    assert not opened
    assert tray.model == model
    for method in ("Switch", "SetPriority", "Quit"):
        assert not calls(obj, method)
    # The host can still retrieve and open the menu after Activate fails.
    assert rpc(bus, dest, MENU, "GetLayout", "(iias)", (0, -1, [])).unpack()[0] == 1
    assert rpc(bus, dest, MENU, "AboutToShow", "(i)", (0,)).unpack() == (False,)
    assert opened == [True]


@pytest.mark.parametrize(
    "item,method", [(4, "Switch"), (5, "SetPriority"), (8, "Quit")]
)
def test_menu_actions(tray, item, method):
    tray, client, obj, _ = tray
    rpc(
        client.connection,
        client.connection.get_unique_name(),
        MENU,
        "Event",
        "(isvu)",
        (item, "clicked", GLib.Variant("i", 0), 0),
    )
    spin_until(lambda: calls(obj, method))
    if item == 5:
        assert calls(obj, method)[0][1] == [True]


def test_disabled_hidden_group_and_opened(tray):
    tray, client, obj, opened = tray
    tray.update(
        present(
            tray.design,
            client.props | {"State": "unavailable"},
            "",
            0,
            Translator("en"),
        )
    )
    rpc(
        client.connection,
        client.connection.get_unique_name(),
        MENU,
        "Event",
        "(isvu)",
        (4, "clicked", GLib.Variant("i", 0), 0),
    )
    result = rpc(
        client.connection,
        client.connection.get_unique_name(),
        MENU,
        "EventGroup",
        "(a(isvu))",
        (
            [
                (7, "clicked", GLib.Variant("i", 0), 0),
                (0, "opened", GLib.Variant("i", 0), 0),
                (999, "clicked", GLib.Variant("i", 0), 0),
            ],
        ),
    ).unpack()
    assert result == ([999],) and opened
    assert not calls(obj, "Switch")


def test_update_signals_and_revision(tray):
    tray, client, obj, _ = tray
    events = []
    bus = client.connection
    sub = bus.signal_subscribe(
        bus.get_unique_name(),
        None,
        None,
        None,
        None,
        Gio.DBusSignalFlags.NONE,
        lambda *args: events.append((args[4], args[5].unpack())),
    )
    try:
        tray.update(tray.model)
        drain()
        assert events == []
        new = present(
            tray.design,
            client.props | {"IphonePriority": True},
            "",
            0,
            Translator("de"),
        )
        tray.update(new)
        spin_until(lambda: any(e[0] == "ItemsPropertiesUpdated" for e in events))
        assert tray.revision == 1
        assert not any(e[0] == "LayoutUpdated" for e in events)
        assert any(e[0] == "NewToolTip" for e in events)
        changed = copy.deepcopy(new.menu)
        changed[7]["visible"] = False
        tray.update(replace(new, menu=changed))
        spin_until(lambda: any(e[0] == "LayoutUpdated" for e in events))
        assert tray.revision == 2
        assert ("LayoutUpdated", (2, 0)) in events
    finally:
        bus.signal_unsubscribe(sub)


@pytest.mark.parametrize("opened_method", ["AboutToShow", "Event"])
def test_ui_error_seen_and_dynamic_minutes(ui_client, tmp_path, opened_method):
    client, obj = ui_client
    ui = start_ui(
        client.connection,
        Config(language="en", notifications=False),
        client.bus_name,
        client.path,
        tmp_path / "config.toml",
    )
    try:
        spin_until(lambda: ui.tray is not None)
        error(obj, "connect_failed")
        spin_until(lambda: ui.notifications.active_error == "connect_failed")
        assert ui.tray.model.status == "NeedsAttention"
        bus, dest = client.connection, client.connection.get_unique_name()
        with pytest.raises(GLib.Error) as exc:
            rpc(bus, dest, SNI, "Activate", "(ii)", (0, 0), SNI_PATH)
        assert Gio.DBusError.get_remote_error(exc.value) == (
            "org.freedesktop.DBus.Error.NotSupported"
        )
        assert ui.notifications.active_error == "connect_failed"
        assert ui.tray.model.status == "NeedsAttention"
        if opened_method == "AboutToShow":
            rpc(bus, dest, MENU, "AboutToShow", "(i)", (0,))
        else:
            rpc(
                bus,
                dest,
                MENU,
                "Event",
                "(isvu)",
                (0, "opened", GLib.Variant("i", 0), 0),
            )
        assert ui.notifications.active_error == ""
        assert ui.tray.model.status == "Active"
        update(
            obj,
            State="on_pc",
            IdleReleaseAt=dbus.UInt64(GLib.get_real_time() + 120000000),
        )
        spin_until(lambda: "2 min" in ui.tray.model.menu[2]["label"])
        # Inject the clock at the GLib boundary; production has no ticking timer.
        from unittest.mock import patch

        with patch.object(
            GLib,
            "get_real_time",
            return_value=GLib.get_real_time() + 61000000,
        ):
            rpc(bus, dest, MENU, "AboutToShow", "(i)", (0,))
        assert "under a minute" in ui.tray.model.menu[2]["label"]
    finally:
        ui.stop()


def test_ui_disabled_flags_reload_language_and_stop(ui_client, tmp_path):
    client, obj = ui_client
    config = Config(language="en", tray=False, notifications=False)
    ui = start_ui(
        client.connection,
        config,
        client.bus_name,
        client.path,
        tmp_path / "config.toml",
    )
    try:
        spin_until(lambda: ui.notifications is not None)
        assert ui.tray is None and not ui.notifications.enabled
        ui.apply_config(replace(config, tray=True, language="de"))
        assert ui.tray is not None
        assert ui.tray.model.menu[4]["label"] == Translator("de").tr(
            "tray-action-to-pc"
        )
        ui.apply_config(config)
        assert ui.tray is None
        with pytest.raises(GLib.Error):
            rpc(
                client.connection,
                client.connection.get_unique_name(),
                MENU,
                "GetLayout",
                "(iias)",
                (0, -1, []),
            )
        ui.apply_config(replace(config, tray=True))
        assert ui.tray
    finally:
        ui.stop()
    assert ui.client.closed


@pytest.mark.parametrize("bad", ["json", "catalog"])
def test_bad_assets_disable_ui(ui_client, tmp_path, monkeypatch, caplog, bad):
    client, obj = ui_client
    if bad == "json":
        (tmp_path / "ui").mkdir()
        (tmp_path / "ui/tray.json").write_text("{bad")
        monkeypatch.setenv("SCAMBIO_DESIGN_DIR", str(tmp_path))
    else:
        monkeypatch.setenv("SCAMBIO_LOCALE_DIR", str(tmp_path))
    ui = start_ui(client.connection, Config(), client.bus_name, client.path)
    assert isinstance(ui, DisabledUi)
    assert "UI disabled" in caplog.text
    ui.apply_config(Config())
    ui.stop()
    client.call("SetPriority", GLib.Variant("(b)", (True,)))
    spin_until(lambda: client.props["IphonePriority"])
