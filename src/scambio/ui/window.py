"""GTK boundary for the separate, single-instance settings application."""

import sys
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import gi
from gi.repository import Gio, GLib

from scambio.api import BUS_NAME, PATH, SETTINGS_ACTIVE, SETTINGS_BUS_NAME
from scambio.config import Config, config_path, parse
from scambio.i18n import Translator, cli_translator
from scambio.paths import design_dir, ui_file
from scambio.ui.client import ScambioClient
from scambio.ui.guard import guarded
from scambio.ui.presentation import Design
from scambio.ui.settings_model import Command, SettingsModel

GLib.set_prgname(SETTINGS_BUS_NAME)
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gtk  # noqa: E402

if (Adw.get_major_version(), Adw.get_minor_version()) < (1, 4):
    raise ImportError("libadwaita >= 1.4 required")

IDS = (
    "toast_overlay",
    "daemon_banner",
    "status_icon",
    "status_row",
    "switch_button",
    "priority_row",
    "device_row",
    "release_idle_row",
    "shortcut_row",
    "shortcut_label",
    "shortcut_change_button",
    "tray_row",
    "notifications_row",
    "language_row",
    "config_row",
    "config_open_button",
    "version_label",
    "status_group",
    "device_group",
    "shortcut_group",
    "general_group",
)


def translated_ui(tr: Translator) -> str:
    root = ET.fromstring(ui_file().read_text())
    for element in root.iter():
        if element.get("translatable") in {"yes", "true", "1"}:
            element.text = tr.tr(element.text or "")
        for key in (
            "translatable",
            "context",
            "comments",
            "translation-domain",
            "domain",
        ):
            element.attrib.pop(key, None)
    return ET.tostring(root, encoding="unicode")


def accelerator_label(text: str) -> str:
    valid, key, mods = Gtk.accelerator_parse(text)
    return str(Gtk.accelerator_get_label(key, mods)) if valid else text


def window_class(tr: Translator) -> Any:
    @Gtk.Template(string=translated_ui(tr))
    class Window(Adw.ApplicationWindow):
        __gtype_name__ = "ScambioSettingsWindow"
        toast_overlay = Gtk.Template.Child()
        daemon_banner = Gtk.Template.Child()
        status_icon = Gtk.Template.Child()
        status_row = Gtk.Template.Child()
        switch_button = Gtk.Template.Child()
        priority_row = Gtk.Template.Child()
        device_row = Gtk.Template.Child()
        release_idle_row = Gtk.Template.Child()
        shortcut_row = Gtk.Template.Child()
        shortcut_label = Gtk.Template.Child()
        shortcut_change_button = Gtk.Template.Child()
        tray_row = Gtk.Template.Child()
        notifications_row = Gtk.Template.Child()
        language_row = Gtk.Template.Child()
        config_row = Gtk.Template.Child()
        config_open_button = Gtk.Template.Child()
        version_label = Gtk.Template.Child()
        status_group = Gtk.Template.Child()
        device_group = Gtk.Template.Child()
        shortcut_group = Gtk.Template.Child()
        general_group = Gtk.Template.Child()

        def __init__(self, app: Any) -> None:
            super().__init__(application=app)
            self.app = app
            self.model = SettingsModel(
                Design.load(design_dir() / "ui/tray.json"), tr, accelerator_label
            )
            self.syncing = False
            self.active_name = 0
            self.closed = False
            self.device_labels: tuple[str, ...] = ()
            self.devices_generation = 0
            self.controls: dict[str, Any] = {name: getattr(self, name) for name in IDS}
            bus = self.app.get_dbus_connection()
            self.client = ScambioClient(
                bus, self.app.bus_name, self.app.path, self._ready, self.app.timeout_ms
            )
            self.client.listeners.append(self._event)
            for widget, prop in (
                ("priority_row", "active"),
                ("device_row", "selected"),
                ("release_idle_row", "value"),
                ("tray_row", "active"),
                ("notifications_row", "active"),
                ("language_row", "selected"),
            ):
                self.controls[widget].connect(
                    "notify::" + prop, self._changed, widget, prop
                )
            self.connect("notify::is-active", self._active_changed)
            self.connect("close-request", self._close_requested)
            self.render()

        @guarded
        def _ready(self) -> None:
            if self.closed:
                return
            self.model.presence(self.client.available)
            self.model.update(self.client.props)
            if self.client.available:
                self._devices()
            self.render()
            if self.is_active():
                self.dispatch(self.model.activated())

        @guarded
        def _event(self, name: str, value: Any) -> None:
            if self.closed:
                return
            if name == "OwnerChanged":
                self.model.presence(bool(value))
            refresh_devices = self.model.update(self.client.props)
            if self.client.available and (
                refresh_devices or (name == "OwnerChanged" and value)
            ):
                self._devices()
            self.render()
            if name == "OwnerChanged" and value and self.is_active():
                self.dispatch(self.model.activated())

        def _devices(self) -> None:
            self.devices_generation += 1
            generation = self.devices_generation

            def received(reply: Any) -> None:
                if not self.closed and generation == self.devices_generation:
                    self.model.devices = [
                        (str(address), str(name)) for address, name in reply[0]
                    ]
                    self.render()

            self.client.call("ListDevices", on_reply=received)

        @guarded
        def _changed(self, widget: Any, spec: Any, name: str, prop: str) -> None:
            if self.syncing or self.closed:
                return
            value = widget.get_property(prop)
            if name == "release_idle_row":
                value = int(value)
            self.dispatch(self.model.change(name, value))
            self.render()

        def render(self) -> None:
            if self.closed:
                return
            view = self.model.view(GLib.get_real_time())
            self.syncing = True
            try:
                labels = tuple(name for _, name in view.device_choices)
                if labels != self.device_labels:
                    self.device_labels = labels
                    self.controls["device_row"].set_model(Gtk.StringList.new(labels))
                for name, properties in view.widgets.items():
                    widget = self.controls[name]
                    for key, value in properties.items():
                        if key.startswith("scambio-"):
                            (
                                widget.add_css_class
                                if value
                                else widget.remove_css_class
                            )(key)
                        else:
                            widget.set_property(key, value)
                self.app.lookup_action("switch").set_enabled(view.switch_enabled)
            finally:
                self.syncing = False
            for text in self.model.toasts:
                self.controls["toast_overlay"].add_toast(Adw.Toast.new(text))
            self.model.toasts.clear()

        def dispatch(self, command: Command | None) -> None:
            if command is None or self.closed:
                return
            if command.method == "open-config":
                launcher = Gtk.FileLauncher.new(
                    Gio.File.new_for_path(str(self.app.config_file))
                )
                launcher.launch(self, None, self._launched)
                return
            if command.method == "change-shortcut":
                Gio.AppInfo.launch_default_for_uri_async(
                    "systemsettings://kcm_keys/app.scambio.Scambio",
                    None,
                    None,
                    self._uri_opened,
                )
                return
            if command.method == "start-daemon":
                self.client.connection.call(
                    "org.freedesktop.systemd1",
                    "/org/freedesktop/systemd1",
                    "org.freedesktop.systemd1.Manager",
                    "StartUnit",
                    GLib.Variant("(ss)", ("scambio.service", "replace")),
                    None,
                    Gio.DBusCallFlags.NONE,
                    self.client.timeout_ms,
                    None,
                    self._started,
                )
                return
            params = None
            if command.method == "SetConfig":
                value = command.value
                variant = GLib.Variant(
                    "b" if type(value) is bool else "i" if type(value) is int else "s",
                    value,
                )
                params = GLib.Variant("(a{sv})", ({command.key: variant},))
            elif command.method == "SetPriority":
                params = GLib.Variant("(b)", (bool(command.value),))

            def finished(error: str = "") -> None:
                if self.closed:
                    return
                self.model.update(self.client.props)
                next_command = self.model.complete(command.key, error)
                self.render()
                self.dispatch(next_command)

            self.client.call(command.method, params, lambda reply: finished(), finished)

        def _desktop_error(self, exc: GLib.Error) -> None:
            if (
                exc.matches(Gio.io_error_quark(), Gio.IOErrorEnum.CANCELLED)
                or exc.matches(Gtk.dialog_error_quark(), Gtk.DialogError.DISMISSED)
                or exc.matches(Gtk.dialog_error_quark(), Gtk.DialogError.CANCELLED)
            ):
                return
            remote = Gio.DBusError.get_remote_error(exc)
            if remote:
                self.model.complete("", remote)
            else:
                self.model.toasts.append(
                    tr.tr("settings-error-generic", error=exc.message)
                )
            self.render()

        @guarded
        def _launched(self, launcher: Any, result: Gio.AsyncResult) -> None:
            try:
                launcher.launch_finish(result)
            except GLib.Error as exc:
                self._desktop_error(exc)

        @guarded
        def _uri_opened(self, source: Any, result: Gio.AsyncResult) -> None:
            try:
                Gio.AppInfo.launch_default_for_uri_finish(result)
            except GLib.Error as exc:
                self._desktop_error(exc)

        @guarded
        def _started(self, bus: Gio.DBusConnection, result: Gio.AsyncResult) -> None:
            try:
                bus.call_finish(result)
            except GLib.Error as exc:
                self._desktop_error(exc)

        @guarded
        def _active_changed(self, *args: Any) -> None:
            self.set_active_presence(self.is_active())

        def set_active_presence(self, active: bool) -> None:
            """Follow focus events; also exercisable on the private display."""
            if active and not self.closed:
                if not self.active_name:
                    self.active_name = Gio.bus_own_name_on_connection(
                        self.client.connection,
                        SETTINGS_ACTIVE,
                        Gio.BusNameOwnerFlags.DO_NOT_QUEUE,
                        None,
                        None,
                    )
                self.render()
                self.dispatch(self.model.activated())
            elif self.active_name:
                Gio.bus_unown_name(self.active_name)
                self.active_name = 0

        def _close_requested(self, *args: Any) -> bool:
            self.shutdown()
            return False

        def shutdown(self) -> None:
            if self.closed:
                return
            self.closed = True
            self.set_active_presence(False)
            self.client.stop()

    return Window


class Application(Adw.Application):
    def __init__(
        self,
        config_file: Path | None = None,
        *,
        bus_name: str = BUS_NAME,
        path: str = PATH,
    ) -> None:
        super().__init__(
            application_id=SETTINGS_BUS_NAME, flags=Gio.ApplicationFlags.DEFAULT_FLAGS
        )
        self.config_file = config_file or config_path()
        self.bus_name, self.path = bus_name, path
        try:
            config = parse(tomllib.loads(self.config_file.read_text()))
        except (OSError, ValueError):
            config = Config()
        self.timeout_ms = config.backend.dbus_timeout_seconds * 1000
        # Read only: opening settings with the daemon absent never creates config.
        self.tr = cli_translator(self.config_file)
        self.window: Any = None
        self.window_type: Any = None

    def do_startup(self) -> None:
        Adw.Application.do_startup(self)
        display = Gdk.Display.get_default()
        if display is None:
            raise RuntimeError("No display")
        Gtk.IconTheme.get_for_display(display).add_search_path(
            str(design_dir() / "icons")
        )
        css = Gtk.CssProvider()
        css.load_from_path(str(design_dir() / "style/scambio.css"))
        Gtk.StyleContext.add_provider_for_display(
            display, css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
        for name in ("switch", "change-shortcut", "open-config", "start-daemon"):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", self._action)
            self.add_action(action)

    def do_activate(self) -> None:
        if self.window is None or self.window.closed:
            if self.window_type is None:
                self.window_type = window_class(self.tr)
            self.window = self.window_type(self)
        self.window.present()

    @guarded
    def _action(self, action: Gio.SimpleAction, params: GLib.Variant | None) -> None:
        if self.window:
            self.window.dispatch(self.window.model.action(action.get_name()))

    def do_shutdown(self) -> None:
        if self.window:
            self.window.shutdown()
        Adw.Application.do_shutdown(self)


def run(service: bool = False) -> int:
    if not Gtk.init_check() or Gdk.Display.get_default() is None:
        print(
            cli_translator(config_path()).tr("cli-error-gtk-missing"), file=sys.stderr
        )
        return 1
    return int(
        Application().run(
            [sys.argv[0], *(["--gapplication-service"] if service else [])]
        )
    )
