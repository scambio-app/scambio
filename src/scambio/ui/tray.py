"""SNI and dbusmenu exports on the daemon's single Gio connection."""

import logging
import os
from collections.abc import Callable
from importlib.resources import files
from typing import Any

from gi.repository import Gio, GLib

from scambio.paths import design_dir
from scambio.ui.guard import guarded
from scambio.ui.presentation import Design, Model

LOG = logging.getLogger(__name__)
SNI = "org.kde.StatusNotifierItem"
MENU = "com.canonical.dbusmenu"
SNI_PATH = "/StatusNotifierItem"
MENU_PATH = "/MenuBar"
WATCHER = "org.kde.StatusNotifierWatcher"


def variants(values: dict[str, Any]) -> dict[str, GLib.Variant]:
    return {
        key: GLib.Variant(
            "b" if type(value) is bool else "i" if type(value) is int else "s", value
        )
        for key, value in values.items()
    }


class Tray:
    def __init__(
        self,
        connection: Gio.DBusConnection,
        design: Design,
        model: Model,
        actions: Gio.SimpleActionGroup,
        opened: Callable[[], None],
        timeout_ms: int,
    ) -> None:
        self.bus, self.design, self.model = connection, design, model
        self.actions, self.opened, self.timeout_ms = actions, opened, timeout_ms
        self.revision = 1
        self.registrations: list[int] = []
        self.watch = 0
        self.owner_id = 0
        self.owned = False
        self.watcher_owner = ""
        self.name = f"org.kde.StatusNotifierItem-{os.getpid()}-1"
        self.closed = False
        self.cancel = Gio.Cancellable()
        try:
            for path, interface in ((SNI_PATH, SNI), (MENU_PATH, MENU)):
                xml = (
                    files("scambio").joinpath(f"core/dbus/{interface}.xml").read_text()
                )
                info = Gio.DBusNodeInfo.new_for_xml(xml).interfaces[0]
                self.registrations.append(
                    self.bus.register_object(path, info, self._method, self._get, None)
                )
            self.watch = Gio.bus_watch_name_on_connection(
                self.bus,
                WATCHER,
                Gio.BusNameWatcherFlags.NONE,
                self._appeared,
                self._vanished,
            )
            self.owner_id = Gio.bus_own_name_on_connection(
                self.bus,
                self.name,
                Gio.BusNameOwnerFlags.DO_NOT_QUEUE,
                self._name_acquired,
                self._name_lost,
            )
        except Exception:
            self.stop()
            raise

    @guarded
    def _appeared(self, bus: Gio.DBusConnection, name: str, owner: str) -> None:
        self.watcher_owner = owner
        self._register()

    @guarded
    def _name_acquired(self, bus: Gio.DBusConnection, name: str) -> None:
        self.owned = True
        self._register()

    @guarded
    def _name_lost(self, bus: Gio.DBusConnection, name: str) -> None:
        self.owned = False

    def _register(self) -> None:
        if self.closed or not self.owned or not self.watcher_owner:
            return

        @guarded
        def done(bus: Gio.DBusConnection, result: Gio.AsyncResult) -> None:
            try:
                bus.call_finish(result)
            except GLib.Error as exc:
                LOG.debug("Cannot register tray: %s", exc)

        self.bus.call(
            WATCHER,
            "/StatusNotifierWatcher",
            WATCHER,
            "RegisterStatusNotifierItem",
            GLib.Variant("(s)", (self.name,)),
            None,
            Gio.DBusCallFlags.NO_AUTO_START,
            self.timeout_ms,
            self.cancel,
            done,
        )

    @guarded
    def _vanished(self, *args: Any) -> None:
        self.watcher_owner = ""
        if not self.closed:
            LOG.info("StatusNotifierWatcher absent; tray unavailable")

    def sni_properties(self) -> dict[str, GLib.Variant]:
        model, sni = self.model, self.design.data["sni"]
        props = {
            key: GLib.Variant("s", value)
            for key, value in {
                "Category": sni["category"],
                "Id": sni["id"],
                "Title": model.title,
                "Status": model.status,
                "IconName": model.icon,
                "IconThemePath": str(design_dir() / "icons"),
                "OverlayIconName": "",
                "AttentionIconName": model.attention,
                "AttentionMovieName": "",
            }.items()
        }
        props.update(
            {
                key: GLib.Variant("a(iiay)", [])
                for key in ("IconPixmap", "OverlayIconPixmap", "AttentionIconPixmap")
            }
        )
        props.update(
            {
                "WindowId": GLib.Variant("i", 0),
                "ItemIsMenu": GLib.Variant("b", True),
                "Menu": GLib.Variant("o", MENU_PATH),
                "ToolTip": GLib.Variant(
                    "(sa(iiay)ss)", (model.icon, [], model.title, model.tooltip)
                ),
            }
        )
        return props

    @guarded
    def _get(
        self, bus: Gio.DBusConnection, sender: str, path: str, interface: str, prop: str
    ) -> GLib.Variant:
        if interface == SNI:
            return self.sni_properties()[prop]
        return {
            "Version": GLib.Variant("u", 3),
            "TextDirection": GLib.Variant("s", "ltr"),
            "Status": GLib.Variant("s", "normal"),
            "IconThemePath": GLib.Variant("as", []),
        }[prop]

    def update(self, model: Model) -> None:
        old = self.model
        self.model = model
        if self.closed or old == model:
            return
        for signal, changed in (
            ("NewIcon", old.icon != model.icon),
            ("NewAttentionIcon", old.attention != model.attention),
            ("NewTitle", old.title != model.title),
            (
                "NewToolTip",
                (old.icon, old.title, old.tooltip)
                != (model.icon, model.title, model.tooltip),
            ),
            ("NewStatus", old.status != model.status),
        ):
            if changed:
                self.bus.emit_signal(
                    None,
                    SNI_PATH,
                    SNI,
                    signal,
                    GLib.Variant("(s)", (model.status,))
                    if signal == "NewStatus"
                    else None,
                )
        updated, removed = [], []
        for item_id, props in model.menu.items():
            previous = old.menu.get(item_id, {})
            diff = {
                key: value for key, value in props.items() if previous.get(key) != value
            }
            if diff:
                updated.append((item_id, variants(diff)))
            missing = list(previous.keys() - props.keys())
            if missing:
                removed.append((item_id, missing))
        if updated or removed:
            self.bus.emit_signal(
                None,
                MENU_PATH,
                MENU,
                "ItemsPropertiesUpdated",
                GLib.Variant("(a(ia{sv})a(ias))", (updated, removed)),
            )
        if any(
            old.menu.get(key, {}).get("visible") != props.get("visible")
            for key, props in model.menu.items()
        ):
            self.revision = (self.revision + 1) % (2**32)
            self.bus.emit_signal(
                None,
                MENU_PATH,
                MENU,
                "LayoutUpdated",
                GLib.Variant("(ui)", (self.revision, 0)),
            )

    def properties(self, item_id: int, names: list[str]) -> dict[str, GLib.Variant]:
        values = (
            {"children-display": "submenu"}
            if item_id == 0
            else self.model.menu[item_id]
        )
        return variants(
            {key: value for key, value in values.items() if not names or key in names}
        )

    def about(self, item_id: int) -> bool:
        before = self.model
        if item_id == 0:
            self.opened()
        elif item_id not in self.model.menu:
            raise KeyError(item_id)
        return before != self.model

    def event(self, item_id: int, event: str) -> None:
        if item_id == 0 and event == "opened":
            self.opened()
        elif event == "clicked" and item_id in self.model.menu:
            row = self.model.menu[item_id]
            if not row.get("visible", True) or not row.get("enabled", True):
                return
            item = next(
                item for item in self.design.data["menu"] if item["id"] == item_id
            )
            action = item.get("action", "").removeprefix("app.")
            if self.actions.has_action(action):
                self.actions.activate_action(action, None)

    def _dispatch(self, method: str, args: Any) -> GLib.Variant | None:
        if method == "GetLayout":
            parent, depth, names = args
            props = self.properties(parent, names)
            children = []
            if parent == 0 and depth != 0:
                children = [
                    GLib.Variant("(ia{sv}av)", (key, self.properties(key, names), []))
                    for key in self.model.menu
                ]
            return GLib.Variant(
                "(u(ia{sv}av))", (self.revision, (parent, props, children))
            )
        if method == "GetGroupProperties":
            ids, names = args
            return GLib.Variant(
                "(a(ia{sv}))",
                (
                    [
                        (key, self.properties(key, names))
                        for key in ids or [0, *self.model.menu]
                        if key == 0 or key in self.model.menu
                    ],
                ),
            )
        if method == "GetProperty":
            return GLib.Variant("(v)", (self.properties(args[0], [args[1]])[args[1]],))
        if method == "AboutToShow":
            return GLib.Variant("(b)", (self.about(args[0]),))
        if method == "AboutToShowGroup":
            updated, errors = [], []
            for key in args[0]:
                if key != 0 and key not in self.model.menu:
                    errors.append(key)
                elif self.about(key):
                    updated.append(key)
            return GLib.Variant("(aiai)", (updated, errors))
        if method == "Event":
            if args[0] != 0 and args[0] not in self.model.menu:
                raise KeyError(args[0])
            self.event(args[0], args[1])
            return None
        if method == "EventGroup":
            errors = []
            for key, event, _data, _timestamp in args[0]:
                if key != 0 and key not in self.model.menu:
                    errors.append(key)
                else:
                    self.event(key, event)
            return GLib.Variant("(ai)", (errors,))
        raise KeyError(method)

    def _method(
        self,
        bus: Gio.DBusConnection,
        sender: str,
        path: str,
        interface: str,
        method: str,
        params: GLib.Variant,
        invocation: Gio.DBusMethodInvocation,
    ) -> None:
        try:
            if interface == SNI and method == "Activate":
                # Plasma 5.27 opens the menu only when Activate fails (decision 85).
                invocation.return_dbus_error(
                    "org.freedesktop.DBus.Error.NotSupported", "Use the tray menu"
                )
                return
            result = (
                None if interface == SNI else self._dispatch(method, params.unpack())
            )
            invocation.return_value(result)
        except Exception:
            LOG.exception("Tray method failed: %s", method)
            invocation.return_dbus_error(
                "org.freedesktop.DBus.Error.Failed", "Invalid tray request"
            )

    def stop(self) -> None:
        self.closed = True
        self.cancel.cancel()
        if self.watch:
            Gio.bus_unwatch_name(self.watch)
            self.watch = 0
        for registration in self.registrations:
            self.bus.unregister_object(registration)
        self.registrations.clear()
        if self.owner_id:
            Gio.bus_unown_name(self.owner_id)
            self.owner_id = 0
