# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Fermich srl
import subprocess

import dbus
import dbusmock
import pytest
from gi.repository import Gio
from helpers import drain, spin_until

from scambio.api import INTERFACE, PATH, SETTINGS_ACTIVE
from scambio.i18n import Translator
from scambio.paths import design_dir
from scambio.ui.actions import create_actions
from scambio.ui.client import ScambioClient
from scambio.ui.notify import NAME, Notifications
from scambio.ui.presentation import Design

NAME_TEST = "app.scambio.UiTest"


@pytest.fixture
def ui_client():
    with dbusmock.SpawnedMock.spawn_for_name(
        NAME_TEST, PATH, INTERFACE, stdout=subprocess.DEVNULL
    ) as mock:
        props = {
            "State": "released",
            "DeviceAddress": "AA:BB:CC:DD:EE:FF",
            "DeviceName": "A_&<B>",
            "IphonePriority": dbus.Boolean(False),
            "AudioActive": dbus.Boolean(False),
            "IdleReleaseAt": dbus.UInt64(0),
            "LastError": "",
        }
        mock.obj.AddProperties(INTERFACE, props, dbus_interface=dbusmock.MOCK_IFACE)
        mock.obj.AddMethods(
            INTERFACE,
            [
                (
                    "Switch",
                    "",
                    "s",
                    'ret = self.props["app.scambio.Scambio1"]["State"]',
                ),
                (
                    "SetPriority",
                    "b",
                    "",
                    'self.UpdateProperties("app.scambio.Scambio1", '
                    "dict(IphonePriority=args[0]))",
                ),
                ("Quit", "", "", ""),
            ],
            dbus_interface=dbusmock.MOCK_IFACE,
        )
        ready = []
        client = ScambioClient(
            Gio.bus_get_sync(Gio.BusType.SESSION, None),
            NAME_TEST,
            PATH,
            lambda: ready.append(True),
            1000,
        )
        spin_until(lambda: ready)
        yield client, mock.obj
        client.stop()
        drain()


@pytest.fixture
def notification_server():
    with dbusmock.SpawnedMock.spawn_with_template(
        "notification_daemon", stdout=subprocess.DEVNULL
    ) as mock:
        yield mock.obj


@pytest.fixture
def notices(ui_client, notification_server, tmp_path):
    client, obj = ui_client
    changed = []
    n = Notifications(
        client,
        Design.load(design_dir() / "ui/tray.json"),
        Translator("en"),
        tmp_path / "config.toml",
        lambda: changed.append(True),
        True,
    )
    yield n, client, obj, notification_server, changed
    n.stop()


def calls(obj, method):
    return obj.GetMethodCalls(method, dbus_interface=dbusmock.MOCK_IFACE)


def emit(obj, interface, name, signature, values):
    obj.EmitSignal(
        interface, name, signature, values, dbus_interface=dbusmock.MOCK_IFACE
    )


def update(obj, **props):
    obj.UpdateProperties(INTERFACE, props, dbus_interface=dbusmock.MOCK_IFACE)


def error(obj, code):
    emit(obj, INTERFACE, "Error", "ss", [code, "technical detail"])
    update(obj, LastError=code)


def sent(n):
    spin_until(lambda: not n.busy and not n.queue)


@pytest.mark.parametrize(
    "code",
    [
        "connect_failed",
        "connect_timeout",
        "sink_timeout",
        "sink_lost",
        "disconnect_failed",
        "device_unavailable",
        "device_not_configured",
        "config_invalid",
        "audio_backend_down",
    ],
)
def test_error_payloads(notices, code):
    n, client, obj, server, changed = notices
    if code == "audio_backend_down":
        client.props["LastError"] = code
        n.startup()
    else:
        error(obj, code)
    spin_until(lambda: len(calls(server, "Notify")) == 1)
    sent(n)
    args = calls(server, "Notify")[0][1]
    entry = n.data["errors"][code]
    assert args[0] == n.data["app_name"] and args[1] == 0
    assert args[2] == str(design_dir() / "icons" / n.design.data["app_icon"])
    assert args[3] == n.tr.tr(entry["title"], device="A_&<B>")
    assert args[4] == n.tr.tr(entry["body"], device="A_&<B>")
    action = entry.get("action")
    assert list(args[5]) == (
        [] if not action else [action, n.tr.tr(n.data["actions"][action]["label"])]
    )
    assert isinstance(args[6]["urgency"], dbus.Byte)
    assert isinstance(args[6]["category"], dbus.String)
    assert args[7] == n.data["expire_timeout"]
    if code in n.design.data["error_overlay"]["detail"]:
        assert n.active_error == code and changed


@pytest.mark.parametrize(
    "priority,switch", [(True, True), (False, True), (True, False), (False, False)]
)
def test_priority_correlation(notices, priority, switch):
    n, client, obj, server, _ = notices
    update(obj, IphonePriority=dbus.Boolean(not priority))
    drain()
    sent(n)
    count = len(calls(server, "Notify"))
    if switch:
        emit(obj, INTERFACE, "Transition", "sss", ["on_pc", "releasing", "switch"])
    update(obj, IphonePriority=dbus.Boolean(priority))
    spin_until(lambda: len(calls(server, "Notify")) == count + 1)
    sent(n)
    args = calls(server, "Notify")[-1][1]
    key = ("on" if priority else "off") + ("_with_switch" if switch else "")
    assert args[3] == n.tr.tr(n.data["priority"][key]["title"], device="A_&<B>")
    assert isinstance(args[6]["transient"], dbus.Boolean) and args[6]["transient"]
    assert "&amp;&lt;B&gt;" in args[4] if not switch else True


def test_own_window_and_no_stale_suppression(notices):
    n, client, obj, server, _ = notices
    group = create_actions(client)
    group.activate_action("toggle-priority", None)
    spin_until(lambda: client.props["IphonePriority"] and client.pending == 0)
    assert not calls(server, "Notify")
    group.activate_action("switch", None)  # No priority change, still finishes window.
    spin_until(lambda: client.pending == 0)
    update(obj, IphonePriority=dbus.Boolean(False))
    spin_until(lambda: len(calls(server, "Notify")) == 1)
    update(obj, State="connecting")
    drain()
    update(obj, IphonePriority=dbus.Boolean(True))  # C9, no Transition.
    spin_until(lambda: len(calls(server, "Notify")) == 2)
    assert calls(server, "Notify")[-1][1][3] == n.tr.tr("notify-priority-on-title")


def test_error_lifetime_replacement_and_foreign_ids(notices):
    n, client, obj, server, _ = notices
    error(obj, "connect_failed")
    spin_until(lambda: n.issued)
    first = n.families["grab"]
    error(obj, "connect_failed")
    drain()
    assert len(calls(server, "Notify")) == 1
    emit(server, NAME, "NotificationClosed", "uu", [first + 999, 2])
    emit(server, NAME, "ActionInvoked", "us", [first + 999, "retry"])
    drain()
    assert n.active_error and not calls(obj, "Switch")
    error(obj, "sink_lost")
    spin_until(lambda: len(calls(server, "Notify")) == 2)
    sent(n)
    assert calls(server, "Notify")[-1][1][1] == first
    current = n.families["grab"]
    emit(server, NAME, "NotificationClosed", "uu", [current, 1])
    spin_until(lambda: current not in n.issued)
    assert n.active_error
    n.seen()
    error(obj, "sink_lost")
    spin_until(lambda: len(calls(server, "Notify")) == 3)
    sent(n)
    assert calls(server, "Notify")[-1][1][1] == 0
    current = n.families["grab"]
    emit(server, NAME, "NotificationClosed", "uu", [current, 2])
    spin_until(lambda: not n.active_error)
    error(obj, "connect_failed")
    spin_until(lambda: n.active_error)
    update(obj, LastError="")
    spin_until(lambda: not n.active_error)


@pytest.mark.parametrize("valid", [True, False])
@pytest.mark.parametrize("action", ["retry", "undo-switch"])
def test_notification_actions(notices, valid, action):
    n, client, obj, server, _ = notices
    if action == "retry":
        error(obj, "connect_failed")
        family = "grab"
    else:
        emit(obj, INTERFACE, "Transition", "sss", ["on_pc", "releasing", "switch"])
        update(obj, State="released", IphonePriority=dbus.Boolean(True))
        family = "priority"
    spin_until(lambda: family in n.families)
    if not valid:
        update(obj, State="on_pc")
        drain()
    notice_id = n.families[family]
    count = len(calls(server, "Notify"))
    emit(server, NAME, "ActionInvoked", "us", [notice_id, action])
    spin_until(lambda: calls(server, "CloseNotification"))
    drain()
    assert len(calls(obj, "Switch")) == int(valid)
    assert len(calls(server, "Notify")) == count


def test_startup_runtime_audio_once_and_disabled(notices):
    n, client, obj, server, _ = notices
    error(obj, "audio_backend_down")
    drain()
    assert not calls(server, "Notify")
    client.props["LastError"] = "device_not_configured"
    n.startup()
    sent(n)
    error(obj, "device_not_configured")
    drain()
    assert len(calls(server, "Notify")) == 1
    n.configure(n.tr, False)
    error(obj, "connect_failed")
    update(obj, IphonePriority=dbus.Boolean(True))
    drain()
    assert n.active_error == "connect_failed"
    assert len(calls(server, "Notify")) == 1


def test_portal_and_default_action(notices):
    n, client, obj, server, _ = notices
    with dbusmock.SpawnedMock.spawn_for_name(
        "org.freedesktop.portal.Desktop",
        "/org/freedesktop/portal/desktop",
        "org.freedesktop.portal.OpenURI",
        stdout=subprocess.DEVNULL,
    ) as portal:
        portal.obj.AddMethod(
            "org.freedesktop.portal.OpenURI",
            "OpenURI",
            "ssa{sv}",
            "o",
            'ret = "/request"',
            dbus_interface=dbusmock.MOCK_IFACE,
        )
        error(obj, "config_invalid")
        spin_until(lambda: "setup" in n.families)
        notice_id = n.families["setup"]
        emit(server, NAME, "ActionInvoked", "us", [notice_id, "default"])
        spin_until(lambda: not n.active_error)
        assert not calls(portal.obj, "OpenURI")
        emit(server, NAME, "ActionInvoked", "us", [notice_id, "open-config"])
        spin_until(lambda: calls(portal.obj, "OpenURI"))
        assert calls(portal.obj, "OpenURI")[0][1][1] == n.config_file.as_uri()


def test_callback_exception_does_not_break_next_listener(ui_client, caplog):
    client, obj = ui_client
    events = []

    def broken(*args):
        raise ValueError("injected")

    client.listeners.extend([broken, lambda *args: events.append(args)])
    update(obj, IphonePriority=dbus.Boolean(True))
    spin_until(lambda: events)
    assert "UI callback failed" in caplog.text
    update(obj, IphonePriority=dbus.Boolean(False))
    spin_until(lambda: len(events) == 2)


def test_button_priority_change_is_own(notices):
    n, client, obj, server, _ = notices
    emit(obj, INTERFACE, "Transition", "sss", ["on_pc", "releasing", "switch"])
    update(obj, State="released", IphonePriority=dbus.Boolean(True))
    spin_until(lambda: "priority" in n.families)
    obj.AddMethod(
        INTERFACE,
        "Switch",
        "",
        "s",
        'self.UpdateProperties("app.scambio.Scambio1", '
        'dict(IphonePriority=dbus.Boolean(False))); ret = "connecting"',
        dbus_interface=dbusmock.MOCK_IFACE,
    )
    notice_id = n.families["priority"]
    emit(server, NAME, "ActionInvoked", "us", [notice_id, "undo-switch"])
    spin_until(lambda: not client.props["IphonePriority"] and client.pending == 0)
    assert len(calls(server, "Notify")) == 1


def test_automatic_transitions_are_silent(notices):
    n, client, obj, server, _ = notices
    for before, after, reason in [
        ("released", "connecting", "audio_started"),
        ("connecting", "on_pc", "connected"),
        ("on_pc", "releasing", "idle_timeout"),
        ("releasing", "released", "locked"),
        ("on_pc", "released", "sleep"),
        ("released", "on_pc", "external_connect"),
    ]:
        emit(obj, INTERFACE, "Transition", "sss", [before, after, reason])
        update(obj, State=after)
    drain()
    assert not calls(server, "Notify")


def test_foreground_window_suppresses_only_priority(notices):
    n, client, obj, server, _ = notices
    with dbusmock.SpawnedMock.spawn_for_name(
        SETTINGS_ACTIVE, "/test", "app.scambio.ActiveTest", stdout=subprocess.DEVNULL
    ):
        spin_until(lambda: n.foreground)
        update(obj, IphonePriority=dbus.Boolean(True))
        drain()
        assert not calls(server, "Notify")
        error(obj, "connect_failed")
        spin_until(lambda: calls(server, "Notify"))
        sent(n)
        assert n.families.keys() == {"grab"}
    spin_until(lambda: not n.foreground)
    update(obj, IphonePriority=dbus.Boolean(False))
    spin_until(lambda: "priority" in n.families)


def test_absent_notification_server_no_retry(ui_client, tmp_path, caplog):
    import logging

    caplog.set_level(logging.DEBUG)
    client, obj = ui_client
    n = Notifications(
        client,
        Design.load(design_dir() / "ui/tray.json"),
        Translator("en"),
        tmp_path / "config.toml",
        lambda: None,
        True,
    )
    try:
        error(obj, "connect_failed")
        spin_until(lambda: "Notification unavailable" in caplog.text)
        assert not n.busy and not n.queue and not n.issued
        with dbusmock.SpawnedMock.spawn_with_template(
            "notification_daemon", stdout=subprocess.DEVNULL
        ) as server:
            drain()
            assert not calls(server.obj, "Notify")
            n.seen()
            error(obj, "connect_failed")
            spin_until(lambda: calls(server.obj, "Notify"))
    finally:
        n.stop()


def test_old_error_notification_does_not_clear_new_error(notices):
    n, client, obj, server, _ = notices
    error(obj, "connect_failed")
    spin_until(lambda: "grab" in n.families)
    old = n.families["grab"]
    error(obj, "config_invalid")
    spin_until(lambda: "setup" in n.families)
    emit(server, NAME, "NotificationClosed", "uu", [old, 2])
    drain()
    assert n.active_error == "config_invalid"


@pytest.mark.parametrize(
    "name,key",
    [
        ("DeviceUnavailable", "cli-error-device-unavailable"),
        ("ConfigInvalid", "cli-error-config-invalid"),
        ("RestartRequired", "cli-error-restart-required"),
        ("Unexpected", "cli-dbus-error"),
    ],
)
def test_cli_dbus_error_keys(ui_client, tmp_path, monkeypatch, capsys, name, key):
    from scambio import cli

    client, obj = ui_client
    error_name = INTERFACE + ".Error." + name
    obj.AddMethod(
        INTERFACE,
        "Switch",
        "",
        "s",
        f'raise dbus.exceptions.DBusException("private details", name={error_name!r})',
        dbus_interface=dbusmock.MOCK_IFACE,
    )
    path = tmp_path / "config.toml"
    path.write_text('[ui]\nlanguage = "de"\n')
    monkeypatch.setattr(cli, "BUS_NAME", client.bus_name)
    monkeypatch.setattr(cli, "config_path", lambda: path)
    assert cli.main(["switch"]) == 1
    assert capsys.readouterr().err.strip() == Translator("de").tr(key, error=error_name)
