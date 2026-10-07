"""Event-driven global shortcuts; every activation uses the public daemon API."""

import logging
import os
import uuid
from collections.abc import Callable
from typing import Any

from gi.repository import Gio, GLib

from scambio.api import BUS_NAME, PATH
from scambio.config import Config
from scambio.core.shortcut_keys import Key, from_qt, parse_key
from scambio.i18n import Translator
from scambio.state import Shortcut, Store
from scambio.ui.client import ScambioClient
from scambio.ui.guard import guarded

LOG = logging.getLogger(__name__)
KGA = "org.kde.kglobalaccel"
KPATH = "/kglobalaccel"
KIFACE = "org.kde.KGlobalAccel"
COMPONENT = "app.scambio.Scambio"
PORTAL = "org.freedesktop.portal.Desktop"
PPATH = "/org/freedesktop/portal/desktop"
PIFACE = "org.freedesktop.portal.GlobalShortcuts"
Reply = Callable[[Any, str], None]


class Shortcuts:
    def __init__(
        self,
        bus: Gio.DBusConnection,
        config: Config,
        store: Store,
        changed: Callable[[], None],
        *,
        bus_name: str = BUS_NAME,
        path: str = PATH,
    ) -> None:
        self.bus, self.config, self.store, self.changed = bus, config, store, changed
        self.values = dict(
            Shortcut="",
            ShortcutLabel="",
            ShortcutState="unsupported",
            ShortcutOwner="",
            ShortcutBackend="none",
        )
        self.client = ScambioClient(
            bus,
            bus_name,
            path,
            lambda: None,
            config.backend.dbus_timeout_seconds * 1000,
        )
        self.cancel = Gio.Cancellable()
        self.closed = False
        self.selecting = False
        self.generation = 0
        self.subscriptions: list[int] = []
        self.kga_subscriptions: list[int] = []
        self.requests: set[str] = set()
        self.session = ""
        self.component = ""
        self.owner_watch = 0
        self.owner = ""
        self.waiters: list[Callable[[], None]] = []

    def _state(
        self, state: str, key: str = "", label: str = "", owner: str = ""
    ) -> None:
        self.values.update(
            ShortcutState=state, Shortcut=key, ShortcutLabel=label, ShortcutOwner=owner
        )
        self.changed()

    def _finish(self) -> None:
        waiters, self.waiters = self.waiters, []
        for done in waiters:
            done()

    def _call(
        self,
        name: str,
        path: str,
        interface: str,
        method: str,
        params: GLib.Variant | None,
        done: Reply,
        *,
        auto_start: bool = True,
    ) -> None:
        generation = self.generation

        @guarded
        def received(bus: Gio.DBusConnection, result: Gio.AsyncResult) -> None:
            reply, error = None, ""
            try:
                reply = bus.call_finish(result).unpack()
            except GLib.Error as exc:
                error = Gio.DBusError.get_remote_error(exc) or str(exc)
            if not self.closed and generation == self.generation:
                done(reply, error)

        self.bus.call(
            name,
            path,
            interface,
            method,
            params,
            None,
            Gio.DBusCallFlags.NONE if auto_start else Gio.DBusCallFlags.NO_AUTO_START,
            self.config.backend.dbus_timeout_seconds * 1000,
            self.cancel,
            received,
        )

    def _subscribe(
        self,
        name: str,
        path: str | None,
        interface: str,
        signal: str,
        callback: Callable[[Any], None],
    ) -> int:
        generation = self.generation

        @guarded
        def received(*args: Any) -> None:
            if not self.closed and (
                generation == self.generation
                or (name == KGA and self.values["ShortcutBackend"] == "kglobalaccel")
            ):
                callback(args[-1].unpack())

        sub = int(
            self.bus.signal_subscribe(
                name, interface, signal, path, None, Gio.DBusSignalFlags.NONE, received
            )
        )
        (self.kga_subscriptions if name == KGA else self.subscriptions).append(sub)
        return sub

    def _clear_kga(self) -> None:
        for sub in self.kga_subscriptions:
            self.bus.signal_unsubscribe(sub)
        self.kga_subscriptions.clear()

    def _reset(self) -> None:
        self.generation += 1
        self.cancel.cancel()
        self.cancel = Gio.Cancellable()
        for sub in self.subscriptions:
            self.bus.signal_unsubscribe(sub)
        self.subscriptions.clear()
        for path in self.requests:
            self._send_close(path, "org.freedesktop.portal.Request")
        self.requests.clear()
        if self.session:
            self._send_close(self.session, "org.freedesktop.portal.Session")
        self.session = ""

    def _send_close(self, path: str, interface: str) -> None:
        self.bus.call(
            PORTAL,
            path,
            interface,
            "Close",
            None,
            None,
            Gio.DBusCallFlags.NO_AUTO_START,
            self.config.backend.dbus_timeout_seconds * 1000,
            None,
            None,
        )

    def start(self) -> None:
        self.selecting = True

        def owner(reply: Any, error: str) -> None:
            if (not error and reply[0]) or "KDE" in os.environ.get(
                "XDG_CURRENT_DESKTOP", ""
            ).upper().split(":"):
                self.values["ShortcutBackend"] = "kglobalaccel"
                self.changed()
                # The initial appearance drives registration; disappearance invalidates
                # outstanding replies. No timers, including while the desktop is absent.
                self.owner_watch = Gio.bus_watch_name_on_connection(
                    self.bus,
                    KGA,
                    Gio.BusNameWatcherFlags.AUTO_START,
                    self._appeared,
                    self._vanished,
                )
            else:
                self._portal_probe()

        self._call(
            "org.freedesktop.DBus",
            "/org/freedesktop/DBus",
            "org.freedesktop.DBus",
            "GetNameOwner",
            GLib.Variant("(s)", (KGA,)),
            owner,
        )

    @guarded
    def _appeared(self, bus: Gio.DBusConnection, name: str, owner: str) -> None:
        if not self.closed:
            self.selecting = False
            self.owner = owner
            self.retry()

    @guarded
    def _vanished(self, bus: Gio.DBusConnection, name: str) -> None:
        if not self.closed:
            self.selecting = False
            self.owner = ""
            self._clear_kga()
            self._reset()
            self._state("unbound")
            self._finish()

    def reload(self, config: Config) -> None:
        changed = (config.shortcut, config.language) != (
            self.config.shortcut,
            self.config.language,
        )
        self.config = config
        self.client.timeout_ms = config.backend.dbus_timeout_seconds * 1000
        if changed:
            self.retry()

    def retry(self, done: Callable[[], None] | None = None) -> None:
        if self.closed:
            if done:
                done()
            return
        if done:
            self.waiters.append(done)
        if self.selecting:
            return
        self._reset()
        try:
            key = parse_key(self.config.shortcut)
        except ValueError:
            LOG.warning("Invalid shortcut.preferred; shortcut disabled")
            key = None
        if self.values["ShortcutBackend"] == "none":
            self._state("unsupported")
            self._finish()
        elif key is None:
            if self.values["ShortcutBackend"] == "kglobalaccel":
                self._inactive()
                self._clear_kga()
            self._state("unbound")
            self._finish()
        elif self.values["ShortcutBackend"] == "kglobalaccel":
            self._register(key)
        elif self.values["ShortcutBackend"] == "portal":
            self._portal_register(key)
        else:
            self._state("unsupported")
            self._finish()

    def _action_id(self) -> list[str]:
        tr = Translator(self.config.language).tr
        return [
            COMPONENT,
            "switch",
            tr("shortcut-component-name"),
            tr("shortcut-switch-name"),
        ]

    def _inactive(self) -> None:
        self.bus.call(
            KGA,
            KPATH,
            KIFACE,
            "setInactive",
            GLib.Variant("(as)", (self._action_id(),)),
            None,
            Gio.DBusCallFlags.NO_AUTO_START,
            self.config.backend.dbus_timeout_seconds * 1000,
            None,
            None,
        )

    def _error(self, error: str, *, fallback: bool = False) -> None:
        LOG.warning("Global shortcut operation failed: %s", error)
        if fallback and error == "org.freedesktop.DBus.Error.UnknownMethod":
            if self.owner_watch:
                Gio.bus_unwatch_name(self.owner_watch)
                self.owner_watch = 0
            self._clear_kga()
            self._reset()
            self._portal_probe()
            return
        if (
            self.values["ShortcutState"] != "active"
            or self.values["ShortcutBackend"] != "kglobalaccel"
        ):
            self._state("unbound")
        self._finish()

    def _remember(self) -> None:
        self.store.value.shortcut = Shortcut(self.config.shortcut)
        try:
            self.store.save()
        except OSError as exc:
            LOG.warning("Cannot save shortcut preference: %s", exc)

    def _active_qt(self, value: int) -> None:
        key, label = from_qt(value)
        self._state("active", key, label)

    def _register(self, key: Key) -> None:
        action_id = self._action_id()
        imposed = self.store.value.shortcut
        force = imposed is None or imposed.preferred != self.config.shortcut

        def owner(reply: Any, error: str) -> None:
            if error:
                LOG.warning("Cannot identify shortcut owner: %s", error)
                label = ""
            else:
                parts = reply[0]
                label = (parts[3] or parts[2]) if len(parts) >= 4 else ""
            self._state("conflict", owner=label)
            self._finish()

        def assigned(reply: Any, error: str) -> None:
            if error:
                self._error(error, fallback=True)
                return
            value = next((int(v) for v in reply[0] if v), 0)
            if value:
                if force:
                    self._remember()
                self._active_qt(value)
            elif force:
                self._call(
                    KGA, KPATH, KIFACE, "action", GLib.Variant("(i)", (key.qt,)), owner
                )
                return
            else:
                self._state("unbound")
            self._finish()

        def component(reply: Any, error: str) -> None:
            if error:
                self._error(error)
                return
            self.component = reply[0]
            self._clear_kga()
            self._subscribe(
                KGA,
                self.component,
                "org.kde.kglobalaccel.Component",
                "globalShortcutPressed",
                self._pressed,
            )
            self._subscribe(KGA, KPATH, KIFACE, "yourShortcutsChanged", self._foreign)
            self._call(
                KGA,
                KPATH,
                KIFACE,
                "setShortcut",
                GLib.Variant("(asaiu)", (action_id, [key.qt], 6 if force else 2)),
                assigned,
            )

        def registered(reply: Any, error: str) -> None:
            if error:
                self._error(error, fallback=True)
            else:
                self._call(
                    KGA,
                    KPATH,
                    KIFACE,
                    "getComponent",
                    GLib.Variant("(s)", (COMPONENT,)),
                    component,
                )

        self._call(
            KGA,
            KPATH,
            KIFACE,
            "doRegister",
            GLib.Variant("(as)", (action_id,)),
            registered,
        )

    def _pressed(self, args: Any) -> None:
        if args[0:2] == (COMPONENT, "switch"):
            self._switch()

    def _foreign(self, args: Any) -> None:
        if list(args[0][:2]) != [COMPONENT, "switch"]:
            return
        sequences = args[1]
        first = sequences[0][0] if sequences else []
        value = next((int(v) for v in first if v), 0)
        # Even removing a binding makes it an explicit desktop choice.
        self._remember()
        if value:
            self._active_qt(value)
        else:
            self._state("unbound")

    def _switch(self) -> None:
        def error(name: str) -> None:
            if name.endswith(".DeviceUnavailable"):
                LOG.info("Shortcut: configured device unavailable")
            else:
                LOG.warning("Shortcut Switch failed: %s", name)

        self.client.call("Switch", on_error=error)

    def _portal_probe(self) -> None:
        self.selecting = True

        def version(reply: Any, error: str) -> None:
            self.selecting = False
            self.values["ShortcutBackend"] = (
                "portal" if not error and reply[0] >= 1 else "none"
            )
            self.retry()

        self._call(
            PORTAL,
            PPATH,
            "org.freedesktop.DBus.Properties",
            "Get",
            GLib.Variant("(ss)", (PIFACE, "version")),
            version,
        )

    def _request(
        self,
        method: str,
        signature: str,
        arguments: tuple[Any, ...],
        options: dict[str, GLib.Variant],
        done: Callable[[Any], None],
    ) -> None:
        token = "scambio_" + uuid.uuid4().hex
        unique_name = self.bus.get_unique_name()
        assert unique_name is not None
        sender = unique_name.lstrip(":").replace(".", "_")
        path = f"{PPATH}/request/{sender}/{token}"
        self.requests.add(path)
        options["handle_token"] = GLib.Variant("s", token)
        responded = False

        def response(args: Any) -> None:
            nonlocal responded
            if responded:
                return
            responded = True
            self.requests.discard(path)
            self.bus.signal_unsubscribe(sub)
            self.subscriptions.remove(sub)
            if args[0] != 0:
                self._state("unbound")
                self._finish()
            else:
                done(args[1])

        sub = self._subscribe(
            PORTAL, path, "org.freedesktop.portal.Request", "Response", response
        )

        def returned(reply: Any, error: str) -> None:
            if responded:
                return
            if error or reply[0] != path:
                self._error(error or "Unexpected portal request path")
                self.requests.discard(path)
                self.bus.signal_unsubscribe(sub)
                self.subscriptions.remove(sub)

        self._call(
            PORTAL,
            PPATH,
            PIFACE,
            method,
            GLib.Variant(signature, (*arguments, options)),
            returned,
        )

    def _portal_register(self, key: Key) -> None:
        def bound(data: Any) -> None:
            self._portal_shortcuts(data.get("shortcuts", []))
            self._finish()

        def created(data: Any) -> None:
            session = data.get("session_handle", "")
            if not isinstance(session, str) or not GLib.Variant.is_object_path(session):
                self._error("Invalid portal session")
                return
            self.session = session
            self._subscribe(
                PORTAL,
                session,
                "org.freedesktop.portal.Session",
                "Closed",
                self._portal_closed,
            )
            self._subscribe(PORTAL, PPATH, PIFACE, "Activated", self._portal_activated)
            self._subscribe(
                PORTAL, PPATH, PIFACE, "ShortcutsChanged", self._portal_changed
            )
            shortcuts = [
                (
                    "switch",
                    {
                        "description": GLib.Variant("s", self._action_id()[3]),
                        "preferred_trigger": GLib.Variant("s", key.xdg),
                    },
                )
            ]
            self._request(
                "BindShortcuts",
                "(oa(sa{sv})sa{sv})",
                (session, shortcuts, ""),
                {},
                bound,
            )

        self._request(
            "CreateSession",
            "(a{sv})",
            (),
            {"session_handle_token": GLib.Variant("s", "scambio_" + uuid.uuid4().hex)},
            created,
        )

    def _portal_shortcuts(self, shortcuts: Any) -> None:
        label = next(
            (
                entry[1].get("trigger_description", "")
                for entry in shortcuts
                if entry[0] == "switch"
            ),
            "",
        )
        self._state("active" if label else "unbound", label=label)

    def _portal_activated(self, args: Any) -> None:
        if args[0] == self.session and args[1] == "switch":
            self._switch()

    def _portal_changed(self, args: Any) -> None:
        if args[0] == self.session:
            self._portal_shortcuts(args[1])

    def _portal_closed(self, args: Any) -> None:
        self.session = ""
        self._reset()
        self._state("unbound")
        self._finish()

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        self._clear_kga()
        if self.values["ShortcutBackend"] == "kglobalaccel":
            self._inactive()
        self._reset()
        if self.owner_watch:
            Gio.bus_unwatch_name(self.owner_watch)
        self.client.stop()
        self._finish()
