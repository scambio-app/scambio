import itertools
import json
import logging
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import dbus
import dbusmock
import pytest
from gi.repository import Gio
from helpers import drain, spin_until
from test_notifications import NAME_TEST, calls, emit
from test_notifications import ui_client as shared_ui_client
from test_service import daemon as shared_daemon
from test_service import properties

from scambio.api import BUS_NAME, INTERFACE, PATH
from scambio.config import TEMPLATE, Config, parse
from scambio.core.shortcut_keys import KEYS, MODIFIERS, from_qt, parse_key
from scambio.core.shortcuts import (
    COMPONENT,
    KGA,
    KIFACE,
    KPATH,
    PIFACE,
    PORTAL,
    PPATH,
    Shortcuts,
)
from scambio.i18n import Translator
from scambio.state import Shortcut, State, Store

ui_client = shared_ui_client
daemon = shared_daemon


def test_key_roundtrips():
    for bits in itertools.product((False, True), repeat=4):
        mods = [m for m, present in zip(MODIFIERS, bits, strict=True) if present]
        for key, code in KEYS.items():
            if not mods and not (key.startswith("f") and len(key) > 1):
                continue
            text = "".join(f"<{m[1]}>" for m in mods) + key
            value = parse_key(text)
            assert value.qt == code | sum(m[0] for m in mods)
            assert from_qt(value.qt) == (value.gtk, "")
            assert parse_key(value.gtk) == value
            assert value.xdg == "+".join(
                [m[2] for m in mods] + [value.gtk.rsplit(">", 1)[-1]]
            )


@pytest.mark.parametrize(
    "text,canonical",
    [
        ("<mEtA>G", "<Super>g"),
        ("<Primary><CTRL>A", "<Control>a"),
        ("<alt><shift>f12", "<Alt><Shift>F12"),
        ("F1", "F1"),
        ("<super>SPACE", "<Super>space"),
    ],
)
def test_key_aliases(text, canonical):
    assert parse_key(text).gtk == canonical


@pytest.mark.parametrize(
    "text",
    [
        "Meta+G",
        "g",
        "1",
        "space",
        "F0",
        "F13",
        "<Hyper>g",
        "<Super>",
        "<Alt>é",
        "<Alt>g ",
        "<Super>Return",
    ],
)
def test_invalid_keys_are_not_invalid_config(text):
    assert parse({"shortcut": {"preferred": text}}).shortcut == text
    with pytest.raises(ValueError):
        parse_key(text)


def test_unknown_qt_keys():
    assert parse_key("") is None
    assert from_qt(0x0C000000 | 0x01000007) == ("", "Ctrl+Alt+Del")
    assert from_qt(0x10000000 | 0x01000013) == ("", "Meta+Up")
    assert from_qt(0x10000000 | 0x1234) == ("", "Meta+0x1234")


@pytest.mark.parametrize("value", [[], 1, {}, {"preferred": 3}])
def test_malformed_shortcut_state(tmp_path, caplog, value):
    p = tmp_path / "state.json"
    p.write_text(json.dumps(dict(version=1, iphone_priority=True, shortcut=value)))
    assert Store(p).load() == State(iphone_priority=True)
    assert "malformed shortcut" in caplog.text


@pytest.fixture
def kga():
    with dbusmock.SpawnedMock.spawn_for_name(
        KGA, KPATH, KIFACE, stdout=subprocess.DEVNULL
    ) as mock:
        mock.obj.AddMethods(
            KIFACE,
            [
                ("doRegister", "as", "", ""),
                ("getComponent", "s", "o", 'ret = "/component/test"'),
                ("setShortcut", "asaiu", "ai", "ret = args[1]"),
                ("setInactive", "as", "", ""),
                (
                    "action",
                    "i",
                    "as",
                    'ret = ["other", "test", "Other component", "Other action"]',
                ),
            ],
            dbus_interface=dbusmock.MOCK_IFACE,
        )
        mock.obj.AddObject(
            "/component/test",
            "org.kde.kglobalaccel.Component",
            {},
            [],
            dbus_interface=dbusmock.MOCK_IFACE,
        )
        yield mock.obj


@pytest.fixture
def shortcut_factory(ui_client, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "TEST")
    adapters = []

    def create(config=None, saved=None, desktop="TEST"):
        monkeypatch.setenv("XDG_CURRENT_DESKTOP", desktop)
        config = config or Config()
        store = Store(tmp_path / f"state{len(adapters)}.json")
        store.value.shortcut = saved
        adapter = Shortcuts(
            Gio.bus_get_sync(Gio.BusType.SESSION, None),
            config,
            store,
            lambda: None,
            bus_name=NAME_TEST,
        )
        adapters.append(adapter)
        adapter.start()
        spin_until(lambda: adapter.client.proxy is not None)
        return adapter

    yield create
    for adapter in adapters:
        adapter.close()
    drain()


def state(adapter, value):
    spin_until(lambda: adapter.values["ShortcutState"] == value)


def set_result(kga, values):
    kga.AddMethod(
        KIFACE,
        "setShortcut",
        "asaiu",
        "ai",
        f"ret = {values!r}",
        dbus_interface=dbusmock.MOCK_IFACE,
    )


@pytest.mark.parametrize("saved,flag", [(None, 6), (Shortcut("<Super>g"), 2)])
def test_register_flags_and_store(kga, shortcut_factory, saved, flag):
    adapter = shortcut_factory(saved=saved)
    state(adapter, "active")
    assert adapter.values["ShortcutBackend"] == "kglobalaccel"
    assert adapter.values["Shortcut"] == "<Super>g"
    assert calls(kga, "setShortcut")[-1][1][2] == flag
    assert adapter.store.value.shortcut == Shortcut("<Super>g")
    if flag == 6:
        assert Store(adapter.store.path).load().shortcut == Shortcut("<Super>g")


@pytest.mark.parametrize("values", [[], [0]])
@pytest.mark.parametrize(
    "saved,expected", [(None, "conflict"), (Shortcut("<Super>g"), "unbound")]
)
def test_refusal_and_retry(kga, shortcut_factory, values, saved, expected):
    set_result(kga, values)
    adapter = shortcut_factory(saved=saved)
    spin_until(lambda: calls(kga, "setShortcut"))
    state(adapter, expected)
    drain()
    assert adapter.values["ShortcutOwner"] == (
        "Other action" if expected == "conflict" else ""
    )
    set_result(kga, [0, 0x10000047, 0x10000048])
    replies = []
    adapter.retry(lambda: replies.append(dict(adapter.values)))
    spin_until(lambda: replies)
    assert replies[0]["ShortcutState"] == "active"
    assert adapter.values["Shortcut"] == "<Super>g"


def test_foreign_change_survives_conflict_and_restart(kga, shortcut_factory):
    set_result(kga, [0])
    adapter = shortcut_factory()
    state(adapter, "conflict")
    emit(
        kga,
        KIFACE,
        "yourShortcutsChanged",
        "asa(ai)",
        [[COMPONENT, "switch", "", ""], [([0x10000000 | 0x01000039, 0, 0, 0],)]],
    )
    state(adapter, "active")
    assert adapter.values["Shortcut"] == "<Super>F10"
    saved = Store(adapter.store.path).load().shortcut
    adapter.close()
    second = shortcut_factory(saved=saved)
    spin_until(lambda: len(calls(kga, "setShortcut")) == 2)
    assert calls(kga, "setShortcut")[-1][1][2] == 2
    state(second, "unbound")


def test_foreign_unbind_and_unknown_key(kga, shortcut_factory):
    adapter = shortcut_factory()
    state(adapter, "active")
    emit(
        kga,
        KIFACE,
        "yourShortcutsChanged",
        "asa(ai)",
        [[COMPONENT, "switch"], [([0x0C000000 | 0x01000007, 0, 0, 0],)]],
    )
    spin_until(lambda: adapter.values["ShortcutLabel"] == "Ctrl+Alt+Del")
    assert adapter.values["Shortcut"] == ""
    emit(
        kga,
        KIFACE,
        "yourShortcutsChanged",
        "asa(ai)",
        [[COMPONENT, "switch"], dbus.Array([], signature="(ai)")],
    )
    state(adapter, "unbound")
    adapter.retry()
    spin_until(lambda: len(calls(kga, "setShortcut")) == 2)
    assert calls(kga, "setShortcut")[-1][1][2] == 2


def test_language_preference_disable_shutdown(kga, shortcut_factory):
    adapter = shortcut_factory()
    state(adapter, "active")
    adapter.reload(replace(adapter.config, language="de"))
    spin_until(lambda: len(calls(kga, "setShortcut")) == 2)
    assert calls(kga, "doRegister")[-1][1][0][3] == Translator("de").tr(
        "shortcut-switch-name"
    )
    assert calls(kga, "setShortcut")[-1][1][2] == 2
    adapter.reload(replace(adapter.config, shortcut="<Alt>F5"))
    spin_until(lambda: adapter.values["Shortcut"] == "<Alt>F5")
    assert calls(kga, "setShortcut")[-1][1][2] == 6
    adapter.reload(replace(adapter.config, shortcut=""))
    state(adapter, "unbound")
    spin_until(lambda: calls(kga, "setInactive"))
    count = len(calls(kga, "setInactive"))
    adapter.close()
    spin_until(lambda: len(calls(kga, "setInactive")) == count + 1)


def test_invalid_binding_warns_without_register(kga, shortcut_factory, caplog):
    adapter = shortcut_factory(replace(Config(), shortcut="Meta+G"))
    spin_until(lambda: calls(kga, "setInactive"))
    assert adapter.values["ShortcutState"] == "unbound"
    assert not calls(kga, "doRegister")
    assert "Invalid shortcut.preferred" in caplog.text


def test_press_calls_public_api_and_handles_unavailable(
    kga, shortcut_factory, ui_client, caplog
):
    caplog.set_level(logging.INFO)
    adapter = shortcut_factory()
    state(adapter, "active")
    component = dbusmock.BusType.SESSION.get_connection().get_object(
        KGA, "/component/test"
    )
    emit(
        component,
        "org.kde.kglobalaccel.Component",
        "globalShortcutPressed",
        "ssx",
        [COMPONENT, "other", 1],
    )
    drain()
    assert not calls(ui_client[1], "Switch")
    emit(
        component,
        "org.kde.kglobalaccel.Component",
        "globalShortcutPressed",
        "ssx",
        [COMPONENT, "switch", 1],
    )
    spin_until(lambda: calls(ui_client[1], "Switch"))
    ui_client[1].AddMethod(
        INTERFACE,
        "Switch",
        "",
        "s",
        'raise dbus.exceptions.DBusException("no device", '
        f'name="{INTERFACE}.Error.DeviceUnavailable")',
        dbus_interface=dbusmock.MOCK_IFACE,
    )
    emit(
        component,
        "org.kde.kglobalaccel.Component",
        "globalShortcutPressed",
        "ssx",
        [COMPONENT, "switch", 2],
    )
    spin_until(lambda: "configured device unavailable" in caplog.text)


def test_no_backend(shortcut_factory):
    adapter = shortcut_factory()
    state(adapter, "unsupported")
    assert adapter.values["ShortcutBackend"] == "none"


def test_kde_without_owner(shortcut_factory, monkeypatch):
    adapter = shortcut_factory(desktop="KDE")
    spin_until(lambda: adapter.values["ShortcutBackend"] == "kglobalaccel")


@pytest.fixture
def portal():
    with dbusmock.SpawnedMock.spawn_for_name(
        PORTAL, PPATH, PIFACE, stdout=subprocess.DEVNULL
    ) as mock:
        mock.obj.AddProperty(
            PIFACE, "version", dbus.UInt32(1), dbus_interface=dbusmock.MOCK_IFACE
        )
        # Requests respond inside the method, before its reply reaches the client.
        # The sender token is provided through the request path prefix property.
        sender = (
            Gio.bus_get_sync(Gio.BusType.SESSION, None)
            .get_unique_name()[1:]
            .replace(".", "_")
        )
        request = PPATH + "/request/" + sender + "/"
        create = f"""ret = {request!r} + str(args[0]["handle_token"])
self.AddObject(ret, "org.freedesktop.portal.Request", {{}}, [("Close", "", "", "")])
self.AddObject("/session/test", "org.freedesktop.portal.Session", {{}},
               [("Close", "", "", "")])
objects[ret].EmitSignal("org.freedesktop.portal.Request", "Response",
    "ua{{sv}}", [0, {{"session_handle": dbus.ObjectPath("/session/test")}}])"""
        bind = f"""ret = {request!r} + str(args[3]["handle_token"])
self.AddObject(ret, "org.freedesktop.portal.Request", {{}}, [("Close", "", "", "")])
objects[ret].EmitSignal("org.freedesktop.portal.Request", "Response", "ua{{sv}}",
    [0, {{"shortcuts": dbus.Array(
        [("switch", {{"trigger_description": "Super+G"}})],
        signature="(sa{{sv}})")}}])"""
        mock.obj.AddMethods(
            PIFACE,
            [
                ("CreateSession", "a{sv}", "o", create),
                ("BindShortcuts", "oa(sa{sv})sa{sv}", "o", bind),
            ],
            dbus_interface=dbusmock.MOCK_IFACE,
        )
        yield mock.obj


def test_portal_immediate_responses_events_close(portal, shortcut_factory, ui_client):
    adapter = shortcut_factory()
    state(adapter, "active")
    assert adapter.values["ShortcutBackend"] == "portal"
    assert adapter.values["Shortcut"] == ""
    assert adapter.values["ShortcutLabel"] == "Super+G"
    assert (
        calls(portal, "BindShortcuts")[0][1][1][0][1]["preferred_trigger"] == "LOGO+g"
    )
    emit(
        portal,
        PIFACE,
        "Activated",
        "osta{sv}",
        ["/session/test", "switch", 1, dbus.Dictionary({}, signature="sv")],
    )
    spin_until(lambda: calls(ui_client[1], "Switch"))
    emit(
        portal,
        PIFACE,
        "ShortcutsChanged",
        "oa(sa{sv})",
        ["/session/test", [("switch", {"trigger_description": "Ctrl+G"})]],
    )
    spin_until(lambda: adapter.values["ShortcutLabel"] == "Ctrl+G")
    session = dbusmock.BusType.SESSION.get_connection().get_object(
        PORTAL, "/session/test"
    )
    emit(session, "org.freedesktop.portal.Session", "Closed", "", [])
    state(adapter, "unbound")
    assert adapter.session == ""


@pytest.mark.parametrize("method", ["doRegister", "setShortcut"])
def test_unknown_method_fallback(kga, portal, shortcut_factory, method):
    signature = "as" if method == "doRegister" else "asaiu"
    kga.AddMethod(
        KIFACE,
        method,
        signature,
        "" if method == "doRegister" else "ai",
        'raise dbus.exceptions.DBusException("unsupported", '
        'name="org.freedesktop.DBus.Error.UnknownMethod")',
        dbus_interface=dbusmock.MOCK_IFACE,
    )
    adapter = shortcut_factory()
    state(adapter, "active")
    assert adapter.values["ShortcutBackend"] == "portal"


def test_dbus_error_preserves_active(kga, shortcut_factory, caplog):
    adapter = shortcut_factory()
    state(adapter, "active")
    kga.AddMethod(
        KIFACE,
        "doRegister",
        "as",
        "",
        'raise dbus.exceptions.DBusException("failed", '
        'name="org.freedesktop.DBus.Error.Failed")',
        dbus_interface=dbusmock.MOCK_IFACE,
    )
    finished = []
    adapter.retry(lambda: finished.append(True))
    spin_until(lambda: finished)
    assert adapter.values["ShortcutState"] == "active"
    assert "operation failed" in caplog.text


def test_owner_loss_and_return(kga, shortcut_factory):
    adapter = shortcut_factory()
    state(adapter, "active")
    # Replace the well-known name on the same mock connection, without a timer.
    code = 'self._connection.release_name("org.kde.kglobalaccel")'
    kga.AddMethod(KIFACE, "Vanish", "", "", code, dbus_interface=dbusmock.MOCK_IFACE)
    kga.AddMethod(
        KIFACE,
        "Return",
        "",
        "",
        'self._connection.request_name("org.kde.kglobalaccel")',
        dbus_interface=dbusmock.MOCK_IFACE,
    )
    kga.Vanish(dbus_interface=KIFACE)
    state(adapter, "unbound")
    kga.Return(dbus_interface=KIFACE)
    state(adapter, "active")
    assert calls(kga, "setShortcut")[-1][1][2] == 2


@pytest.mark.parametrize("result", [1, 2])
def test_portal_rejected_response(portal, shortcut_factory, result):
    sender = (
        Gio.bus_get_sync(Gio.BusType.SESSION, None)
        .get_unique_name()[1:]
        .replace(".", "_")
    )
    code = f"""ret = {PPATH + "/request/" + sender + "/"!r} + args[0]["handle_token"]
self.AddObject(ret, "org.freedesktop.portal.Request", {{}}, [])
objects[ret].EmitSignal("org.freedesktop.portal.Request", "Response", "ua{{sv}}",
                       [{result}, dbus.Dictionary({{}}, signature="sv")])"""
    portal.AddMethod(
        PIFACE, "CreateSession", "a{sv}", "o", code, dbus_interface=dbusmock.MOCK_IFACE
    )
    adapter = shortcut_factory()
    spin_until(lambda: calls(portal, "CreateSession"))
    drain()
    assert adapter.values["ShortcutState"] == "unbound"
    assert not adapter.requests
    assert not calls(portal, "BindShortcuts")


def test_portal_shutdown_and_empty_shortcuts(portal, shortcut_factory):
    adapter = shortcut_factory()
    state(adapter, "active")
    emit(
        portal,
        PIFACE,
        "ShortcutsChanged",
        "oa(sa{sv})",
        ["/session/test", dbus.Array([], signature="(sa{sv})")],
    )
    state(adapter, "unbound")
    session = dbusmock.BusType.SESSION.get_connection().get_object(
        PORTAL, "/session/test"
    )
    adapter.close()
    spin_until(lambda: calls(session, "Close"))


def test_service_shortcut_properties_reload_retry_and_quit(kga, daemon, tmp_path):
    from gi.repository import GLib

    spin_until(lambda: properties()["ShortcutState"] == "active")
    cfg = tmp_path / "config.toml"
    cfg.write_text(cfg.read_text().replace("<Super>g", "<Alt>F5"))
    bus = dbusmock.BusType.SESSION.get_connection()
    obj = bus.get_object(BUS_NAME, PATH)
    obj.Reload(dbus_interface=INTERFACE)
    spin_until(lambda: properties()["Shortcut"] == "<Alt>F5")
    assert calls(kga, "setShortcut")[-1][1][2] == 6
    set_result(kga, [0x10000048])
    events = []
    connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    sub = connection.signal_subscribe(
        BUS_NAME,
        "org.freedesktop.DBus.Properties",
        "PropertiesChanged",
        PATH,
        None,
        Gio.DBusSignalFlags.NONE,
        lambda *args: (
            events.append("property") if "Shortcut" in args[-1].unpack()[1] else None
        ),
    )
    try:

        def done(conn, result):
            conn.call_finish(result)
            events.append("reply")

        connection.call(
            BUS_NAME,
            PATH,
            INTERFACE,
            "RetryShortcut",
            None,
            GLib.VariantType.new("()"),
            Gio.DBusCallFlags.NO_AUTO_START,
            1000,
            None,
            done,
        )
        spin_until(lambda: "reply" in events)
        assert events == ["property", "reply"]
    finally:
        connection.signal_unsubscribe(sub)
    assert properties()["Shortcut"] == "<Super>h"
    obj.Quit(dbus_interface=INTERFACE)
    daemon.wait(timeout=5)
    assert calls(kga, "setInactive")


def test_foreign_unbind_after_conflict_persists_desktop_choice(kga, shortcut_factory):
    set_result(kga, [0])
    adapter = shortcut_factory()
    state(adapter, "conflict")
    assert adapter.store.value.shortcut is None
    emit(
        kga,
        KIFACE,
        "yourShortcutsChanged",
        "asa(ai)",
        [[COMPONENT, "switch"], dbus.Array([], signature="(ai)")],
    )
    state(adapter, "unbound")
    saved = Store(adapter.store.path).load().shortcut
    assert saved == Shortcut("<Super>g")
    adapter.close()
    second = shortcut_factory(saved=saved)
    state(second, "unbound")
    spin_until(lambda: len(calls(kga, "setShortcut")) == 2)
    assert calls(kga, "setShortcut")[-1][1][2] == 2


@pytest.mark.parametrize("preferred", ["", "Meta+G"])
def test_no_backend_is_unsupported_for_disabled_preference(shortcut_factory, preferred):
    adapter = shortcut_factory(replace(Config(), shortcut=preferred))
    spin_until(lambda: not adapter.selecting)
    assert adapter.values["ShortcutBackend"] == "none"
    assert adapter.values["ShortcutState"] == "unsupported"
    adapter.retry()
    assert adapter.values["ShortcutState"] == "unsupported"


@pytest.mark.parametrize("method", ["Quit", "SIGTERM"])
def test_shutdown_inactive_no_auto_start_before_flush(
    kga, fake_pactl, bluez_server, tmp_path, method
):
    (tmp_path / "config.toml").write_text(TEMPLATE)
    with (tmp_path / "audit-daemon.log").open("w") as log:
        process = subprocess.Popen(
            [
                sys.executable,
                str(Path(__file__).parent / "fixtures/run_daemon.py"),
                str(tmp_path),
                "--audit-shutdown",
            ],
            stdout=log,
            stderr=log,
        )
        try:
            spin_until(
                lambda: dbusmock.BusType.SESSION.get_connection().name_has_owner(
                    BUS_NAME
                )
            )
            spin_until(lambda: properties()["ShortcutState"] == "active")
            if method == "Quit":
                dbusmock.BusType.SESSION.get_connection().get_object(
                    BUS_NAME, PATH
                ).Quit(dbus_interface=INTERFACE)
            else:
                process.terminate()
            process.wait(timeout=5)
            assert process.returncode == 0, (tmp_path / "audit-daemon.log").read_text()
            events = [
                json.loads(line)
                for line in (tmp_path / "shutdown.jsonl").read_text().splitlines()
            ]
            assert events == [
                {"event": "setInactive", "flags": int(Gio.DBusCallFlags.NO_AUTO_START)},
                {"event": "flush"},
            ]
            assert calls(kga, "setInactive")
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=5)
