# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Fermich srl
"""Real GTK, nested private buses with no activatable services, disposable HOME."""

import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import dbus
import dbusmock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from helpers import drain, spin_until  # noqa: E402

assert os.environ["GDK_BACKEND"] == "x11"
assert os.environ["GSK_RENDERER"] == "cairo"
assert os.environ["GTK_A11Y"] == "none"
root = Path(os.environ["SCAMBIO_TEST_ROOT"])
assert Path.home() == root
scenario = os.environ.get("SCAMBIO_TEST_SCENARIO", "normal")

with ExitStack() as stack:
    system = stack.enter_context(dbusmock.PrivateDBus(dbusmock.BusType.SYSTEM))
    session = stack.enter_context(dbusmock.PrivateDBus(dbusmock.BusType.SESSION))
    assert os.environ["DBUS_SYSTEM_BUS_ADDRESS"] == system.address
    assert os.environ["DBUS_SESSION_BUS_ADDRESS"] == session.address
    # Both buses refuse activation of installed desktop/backend services.
    session_bus = dbusmock.BusType.SESSION.get_connection()
    assert not [
        str(name)
        for name in session_bus.list_activatable_names()
        if str(name) != "org.freedesktop.DBus"
    ]

    from test_i18n import po_entries

    from scambio.api import INTERFACE, PATH, SETTINGS_ACTIVE
    from scambio.paths import design_dir, ui_file

    if scenario == "no-display":
        env = dict(os.environ)
        env.pop("DISPLAY", None)
        env.pop("WAYLAND_DISPLAY", None)
        result = subprocess.run(
            [sys.executable, "-m", "scambio.cli", "settings"],
            env=env,
            capture_output=True,
            text=True,
            timeout=5,
        )
        from scambio.i18n import Translator

        assert result.returncode == 1, result.stderr
        assert result.stderr.strip() == Translator("en").tr("cli-error-gtk-missing"), (
            result.stderr
        )
        assert "Traceback" not in result.stderr
        sys.exit(0)

    from scambio.ui.window import IDS, Adw, Application, Gio, GLib, Gtk

    name = "app.scambio.WindowTest"
    config = root / ".config/scambio/config.toml"
    config.parent.mkdir(parents=True)
    config.write_text('[ui]\nlanguage="de"\n')
    initial = config.read_bytes()
    mock = stack.enter_context(
        dbusmock.SpawnedMock.spawn_for_name(
            name, PATH, INTERFACE, stdout=subprocess.DEVNULL
        )
    )
    values = {
        "State": "released",
        "DeviceAddress": "AA:BB:CC:DD:EE:FF",
        "DeviceName": "Test headset",
        "IphonePriority": dbus.Boolean(False),
        "Version": "0.1.0",
        "AudioActive": dbus.Boolean(False),
        "IdleReleaseAt": dbus.UInt64(0),
        "Shortcut": "<Super>g",
        "ShortcutLabel": "",
        "ShortcutState": "active",
        "ShortcutBackend": "kglobalaccel",
        "ShortcutOwner": "",
        "Config": dbus.Dictionary(
            {
                "device.address": "AA:BB:CC:DD:EE:FF",
                "policy.release_idle_seconds": dbus.Int32(120),
                "ui.tray": dbus.Boolean(True),
                "ui.notifications": dbus.Boolean(True),
                "ui.language": "de",
                "shortcut.preferred": "<Super>g",
            },
            signature="sv",
        ),
    }
    mock.obj.AddProperties(INTERFACE, values, dbus_interface=dbusmock.MOCK_IFACE)
    mock.obj.AddMethods(
        INTERFACE,
        [
            (
                "SetPriority",
                "b",
                "",
                f'self.UpdateProperties("{INTERFACE}", dict(IphonePriority=args[0]))',
            ),
            (
                "SetConfig",
                "a{sv}",
                "",
                f'''values = dict(self.props["{INTERFACE}"]["Config"])
values.update(args[0])
self.UpdateProperties("{INTERFACE}",
    {{"Config": dbus.Dictionary(values, signature="sv")}})''',
            ),
            (
                "ListDevices",
                "",
                "a(ss)",
                'ret = [("AA:BB:CC:DD:EE:FF", "Test headset")]',
            ),
            ("RetryShortcut", "", "", ""),
            ("Switch", "", "s", 'ret = "connecting"'),
        ],
        dbus_interface=dbusmock.MOCK_IFACE,
    )
    # A real owner disappearance, followed by return, must recover the window.
    mock.obj.AddMethod(
        INTERFACE,
        "Vanish",
        "",
        "",
        f'self._connection.release_name("{name}")',
        dbus_interface=dbusmock.MOCK_IFACE,
    )
    mock.obj.AddMethod(
        INTERFACE,
        "Return",
        "",
        "",
        f'self._connection.request_name("{name}")',
        dbus_interface=dbusmock.MOCK_IFACE,
    )
    if scenario == "initially-absent":
        mock.obj.Vanish(dbus_interface=INTERFACE)
    activation_calls = []
    original_call = Gio.DBusConnection.call

    def record_call(connection, destination, path, interface, method, params, *args):
        if method in {"StartServiceByName", "StartUnit"}:
            activation_calls.append((destination, path, interface, method, params))
        return original_call(
            connection, destination, path, interface, method, params, *args
        )

    stack.enter_context(patch.object(Gio.DBusConnection, "call", record_call))
    app = Application(config, bus_name=name)
    app.register(None)
    if scenario == "startup-counts":
        values["ShortcutState"] = "conflict"
        mock.obj.UpdateProperties(
            INTERFACE, {"ShortcutState": "conflict"}, dbus_interface=dbusmock.MOCK_IFACE
        )
    # Simulated focus is fixed before the proxy starts; no synthetic owner callback.
    with patch.object(
        Gtk.Window, "is_active", return_value=scenario == "startup-counts"
    ):
        app.activate()
        window = app.window
        if scenario == "initially-absent":
            spin_until(lambda: window.client.proxy is not None)
            assert window.daemon_banner.get_revealed()
            assert not window.status_group.get_sensitive()
            assert config.read_bytes() == initial
            assert len(activation_calls) == 1
            destination, path, interface, method, params = activation_calls[0]
            assert destination == interface == "org.freedesktop.DBus"
            assert path == "/org/freedesktop/DBus"
            assert method == "StartServiceByName"
            assert params.get_type_string() == "(su)"
            assert params.unpack() == (name, 0)
            app.lookup_action("start-daemon").activate(None)
            assert len(activation_calls) == 2
            mock.obj.Return(dbus_interface=INTERFACE)
        spin_until(lambda: window.client.available and window.model.devices)
        drain()
    if scenario == "startup-counts":
        assert not activation_calls
        counts = {
            method: len(
                mock.obj.GetMethodCalls(method, dbus_interface=dbusmock.MOCK_IFACE)
            )
            for method in ("ListDevices", "RetryShortcut")
        }
        assert counts == {"ListDevices": 1, "RetryShortcut": 1}, counts
        window.close()
        app.quit()
        sys.exit(0)
    spin_until(lambda: window.client.available and window.model.devices)
    assert not window.daemon_banner.get_revealed()
    assert window.get_title() == app.tr.tr("settings-window-title")
    assert window.tray_row.get_title() == app.tr.tr("settings-tray")
    assert window.language_row.get_selected() == 3
    assert window.status_group.get_sensitive()
    assert window.device_row.get_model().get_string(0) == "Test headset"
    types = {
        "toast_overlay": Adw.ToastOverlay,
        "daemon_banner": Adw.Banner,
        "status_icon": Gtk.Image,
        "status_row": Adw.ActionRow,
        "switch_button": Gtk.Button,
        "priority_row": Adw.SwitchRow,
        "device_row": Adw.ComboRow,
        "release_idle_row": Adw.SpinRow,
        "shortcut_row": Adw.ActionRow,
        "shortcut_label": Gtk.ShortcutLabel,
        "shortcut_change_button": Gtk.Button,
        "tray_row": Adw.SwitchRow,
        "notifications_row": Adw.SwitchRow,
        "language_row": Adw.ComboRow,
        "config_row": Adw.ActionRow,
        "config_open_button": Gtk.Button,
        "version_label": Gtk.Label,
    }
    for widget_id in IDS:
        assert isinstance(
            window.controls[widget_id], types.get(widget_id, Adw.PreferencesGroup)
        )
    for action in ("switch", "change-shortcut", "open-config", "start-daemon"):
        assert app.lookup_action(action) is not None

    catalog = po_entries(design_dir() / "i18n/scambio.pot")
    german = po_entries(design_dir() / "i18n/de.po")

    def visible_texts(widget):
        for prop in widget.list_properties():
            if prop.name in {
                "title",
                "label",
                "subtitle",
                "tooltip-text",
                "disabled-text",
                "button-label",
            }:
                value = widget.get_property(prop.name)
                if isinstance(value, str):
                    assert value not in catalog, value
        if isinstance(widget, Adw.ComboRow):
            model = widget.get_model()
            if model is not None:
                for index in range(model.get_n_items()):
                    assert model.get_string(index) not in catalog
        child = widget.get_first_child()
        while child is not None:
            visible_texts(child)
            child = child.get_next_sibling()

    def layout_translations():
        checked = 0
        root_xml = ET.parse(ui_file()).getroot()
        for element in root_xml.iter():
            if element.tag not in {"object", "template"}:
                continue
            for prop in element.findall("property"):
                if prop.get("translatable") not in {"yes", "true", "1"}:
                    continue
                obj = (
                    window
                    if element.tag == "template"
                    else window.controls[element.get("id")]
                )
                assert obj.get_property(prop.get("name")) == german[prop.text], (
                    element.get("id"),
                    prop.text,
                )
                checked += 1
            # GtkStringList model entries are not widget properties.
            for prop in element.findall("property[@name='model']"):
                items = prop.findall("object/items/item")
                obj = window.controls[element.get("id")].get_model()
                for index, item in enumerate(items):
                    if item.get("translatable") in {"yes", "true", "1"}:
                        assert obj.get_string(index) == german[item.text], item.text
                        checked += 1
        return checked

    if scenario == "wrong-translation":
        from scambio.i18n import Translator

        window.config_row.set_subtitle(Translator("en").tr("settings-config-subtitle"))
        try:
            layout_translations()
        except AssertionError:
            pass
        else:
            raise AssertionError("Translation checker missed English layout text")
        window.close()
        app.quit()
        sys.exit(0)

    if scenario.startswith("text-leak:"):
        target = scenario.split(":", 1)[1]
        key = "cli-error-gtk-missing"
        if target == "title":
            window.tray_row.set_title(key)
        elif target == "disabled-text":
            window.shortcut_label.set_disabled_text(key)
        else:
            window.controls[target].get_model().append(key)
        try:
            visible_texts(window)
        except AssertionError:
            pass
        else:
            raise AssertionError("Text checker missed catalog key in " + target)
        window.close()
        app.quit()
        sys.exit(0)

    visible_texts(window)
    translated_count = layout_translations()

    def calls(method):
        return mock.obj.GetMethodCalls(method, dbus_interface=dbusmock.MOCK_IFACE)

    assert not calls("SetConfig") and not calls("SetPriority")
    window.priority_row.set_active(True)
    spin_until(lambda: not window.model.pending and calls("SetPriority"))
    assert calls("SetPriority")[0][1] == [True]
    assert len(calls("SetPriority")) == 1
    window.release_idle_row.set_value(3)
    window.release_idle_row.set_value(4)
    window.release_idle_row.set_value(5)
    spin_until(lambda: not window.model.pending)
    assert calls("SetConfig")[-1][1][0]["policy.release_idle_seconds"] == 300
    assert window.release_idle_row.get_value() == 5
    count = len(calls("SetConfig"))
    window.tray_row.set_active(False)
    spin_until(lambda: not window.model.pending)
    assert len(calls("SetConfig")) == count + 1
    assert not calls("SetConfig")[-1][1][0]["ui.tray"]
    window.set_active_presence(True)
    spin_until(lambda: session_bus.name_has_owner(SETTINGS_ACTIVE))
    window.set_active_presence(False)
    spin_until(lambda: not session_bus.name_has_owner(SETTINGS_ACTIVE))
    second = subprocess.Popen(
        [sys.executable, "-m", "scambio.cli", "settings"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    spin_until(lambda: second.poll() is not None)
    out, err = second.communicate(timeout=5)
    assert second.returncode == 0, out + err
    assert app.window is window
    assert len(app.get_windows()) == 1
    mock.obj.Vanish(dbus_interface=INTERFACE)
    spin_until(lambda: window.daemon_banner.get_revealed())
    assert len(activation_calls) == (2 if scenario == "initially-absent" else 0)
    mock.obj.Return(dbus_interface=INTERFACE)
    spin_until(lambda: not window.daemon_banner.get_revealed())
    assert window.release_idle_row.get_value() == 5
    assert not window.tray_row.get_active()
    assert config.read_bytes() == initial
    if scenario == "desktop-errors":
        toasts = []

        class Overlay:
            def add_toast(self, toast):
                toasts.append(toast.get_title())

        window.controls["toast_overlay"] = Overlay()
        for boundary in ("file", "uri"):
            for domain, code, message, ignored in (
                (
                    Gtk.dialog_error_quark(),
                    Gtk.DialogError.DISMISSED,
                    "Dismissed",
                    True,
                ),
                (
                    Gtk.dialog_error_quark(),
                    Gtk.DialogError.CANCELLED,
                    "Cancelled",
                    True,
                ),
                (Gio.io_error_quark(), Gio.IOErrorEnum.CANCELLED, "Cancelled", True),
                (
                    Gio.io_error_quark(),
                    Gio.IOErrorEnum.FAILED,
                    "Cannot open report.txt",
                    False,
                ),
            ):
                toasts.clear()
                exc = GLib.Error.new_literal(domain, message, code)

                class Launcher:
                    def launch_finish(self, result, error=exc):
                        raise error

                if boundary == "file":
                    window._launched(Launcher(), None)
                else:
                    with patch.object(
                        Gio.AppInfo, "launch_default_for_uri_finish", side_effect=exc
                    ):
                        window._uri_opened(None, None)
                expected = (
                    []
                    if ignored
                    else [app.tr.tr("settings-error-generic", error=message)]
                )
                assert toasts == expected, (boundary, message, toasts)

    drain()
    fields = Path("/proc/self/stat").read_text().split(")", 1)[1].split()
    print(
        json.dumps(
            {
                "gtk_real": True,
                "gtk_version": [
                    Gtk.get_major_version(),
                    Gtk.get_minor_version(),
                    Gtk.get_micro_version(),
                ],
                "adw_version": [
                    Adw.get_major_version(),
                    Adw.get_minor_version(),
                    Adw.get_micro_version(),
                ],
                "language": "de",
                "ids": len(IDS),
                "layout_translations": translated_count,
                "rss_kib": int(fields[21]) * os.sysconf("SC_PAGE_SIZE") // 1024,
                "private_buses": True,
                "display": os.environ["DISPLAY"],
            }
        )
    )
    window.close()
    spin_until(lambda: not session_bus.name_has_owner(SETTINGS_ACTIVE))
    app.quit()
