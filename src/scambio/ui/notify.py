"""Notification families, ordered event correlation and guarded desktop actions."""

import html
import logging
from collections import deque
from collections.abc import Callable
from pathlib import Path
from typing import Any

from gi.repository import Gio, GLib

from scambio.api import SETTINGS_ACTIVE
from scambio.i18n import Translator
from scambio.paths import design_dir
from scambio.ui.client import ScambioClient
from scambio.ui.guard import guarded
from scambio.ui.presentation import Design, matches

LOG = logging.getLogger(__name__)
NAME = "org.freedesktop.Notifications"
PATH = "/org/freedesktop/Notifications"


class Notifications:
    def __init__(
        self,
        client: ScambioClient,
        design: Design,
        tr: Translator,
        config_file: Path,
        changed: Callable[[], None],
        enabled: bool,
    ) -> None:
        self.client, self.design, self.tr = client, design, tr
        self.config_file, self.changed, self.enabled = config_file, changed, enabled
        self.data = design.data["notifications"]
        self.active_error = ""
        self.error_generation = 0
        self.last_signal: tuple[str, Any] = ("", ())
        self.once: set[str] = set()
        self.families: dict[str, int] = {}
        self.issued: dict[int, tuple[str, dict[str, Any], int]] = {}
        self.queue: deque[tuple[dict[str, Any], str, int]] = deque()
        self.busy = False
        self.closed = False
        self.foreground = False
        self.cancel = Gio.Cancellable()
        self.subscription = client.connection.signal_subscribe(
            NAME, NAME, None, PATH, None, Gio.DBusSignalFlags.NONE, self._signal
        )
        client.listeners.append(self.event)
        self.active_watch = Gio.bus_watch_name_on_connection(
            client.connection,
            SETTINGS_ACTIVE,
            Gio.BusNameWatcherFlags.NONE,
            self._active,
            self._inactive,
        )

    @guarded
    def _active(self, *args: Any) -> None:
        self.foreground = True
        self.queue = deque(item for item in self.queue if item[1] != "priority")

    @guarded
    def _inactive(self, *args: Any) -> None:
        self.foreground = False

    def startup(self) -> None:
        code = self.client.props.get("LastError", "")
        if code:
            self.error(code, startup=True)

    def seen(self, generation: int | None = None) -> None:
        if generation is not None and generation != self.error_generation:
            return
        if self.active_error:
            self.active_error = ""
            self.changed()

    def error(self, code: str, startup: bool = False) -> None:
        entry = self.data["errors"].get(code)
        if entry is None or (entry.get("startup_only") and not startup):
            return
        duplicate = self.active_error == code
        if code in self.design.data["error_overlay"]["detail"] and not duplicate:
            self.active_error = code
            self.error_generation += 1
            self.changed()
        if duplicate or (entry.get("once_per_run") and code in self.once):
            return
        if self.enabled:
            self.once.add(code)
            self.send(entry, "error", self.error_generation)

    @guarded
    def event(self, name: str, value: Any) -> None:
        if self.closed:
            return
        previous = self.last_signal
        self.last_signal = (name, value)
        if name == "Error":
            self.error(value[0])
        elif name == "PropertiesChanged":
            before, own = value
            props = self.client.props
            if before.get("LastError") and props.get("LastError") == "":
                self.seen()
            if before.get("IphonePriority") != props.get("IphonePriority") and not own:
                key = "on" if props["IphonePriority"] else "off"
                if previous[0] == "Transition" and previous[1][2] == "switch":
                    key += "_with_switch"
                self.send(self.data["priority"][key], "priority", -1)

    def send(self, entry: dict[str, Any], category: str, generation: int) -> None:
        if (
            self.closed
            or not self.enabled
            or (category == "priority" and self.foreground)
        ):
            return
        self.queue.append((entry, category, generation))
        self._pump()

    def _pump(self) -> None:
        if self.closed or self.busy or not self.queue or not self.enabled:
            return
        entry, category, generation = self.queue.popleft()
        family = entry["family"]
        action = entry.get("action")
        actions = (
            []
            if not action
            else [action, self.tr.tr(self.data["actions"][action]["label"])]
        )
        values = {"device": self.client.props.get("DeviceName", "")}
        hints = {
            "urgency": GLib.Variant("y", self.data["urgency"]),
            "category": GLib.Variant("s", self.data["category"][category]),
        }
        if "transient" in entry:
            hints["transient"] = GLib.Variant("b", entry["transient"])
        params = GLib.Variant(
            "(susssasa{sv}i)",
            (
                self.data["app_name"],
                self.families.get(family, 0),
                str(design_dir() / "icons" / self.design.data["app_icon"]),
                self.tr.tr(entry["title"], **values),
                html.escape(self.tr.tr(entry["body"], **values), quote=False),
                actions,
                hints,
                self.data["expire_timeout"],
            ),
        )
        self.busy = True

        @guarded
        def done(bus: Gio.DBusConnection, result: Gio.AsyncResult) -> None:
            try:
                reply = bus.call_finish(result)
                if not self.closed:
                    notice_id = int(reply.unpack()[0])
                    old = self.families.get(family)
                    if old:
                        self.issued.pop(old, None)
                    self.families[family] = notice_id
                    self.issued[notice_id] = (family, entry, generation)
            except GLib.Error as exc:
                LOG.debug("Notification unavailable: %s", exc)
            finally:
                self.busy = False
                self._pump()

        try:
            self.client.connection.call(
                NAME,
                PATH,
                NAME,
                "Notify",
                params,
                GLib.VariantType.new("(u)"),
                Gio.DBusCallFlags.NO_AUTO_START,
                self.client.timeout_ms,
                self.cancel,
                done,
            )
        except Exception:
            self.busy = False
            raise

    @guarded
    def _signal(self, *args: Any) -> None:
        if self.closed:
            return
        name, params = args[4], args[5].unpack()
        notice_id = params[0]
        notice = self.issued.get(notice_id)
        if notice is None:
            return
        family, entry, generation = notice
        if name == "NotificationClosed":
            self.issued.pop(notice_id, None)
            if self.families.get(family) == notice_id:
                self.families.pop(family, None)
            if params[1] == 2:
                self.seen(generation)
        elif name == "ActionInvoked":
            self.seen(generation)
            action_name = params[1]
            if action_name == "default":
                return
            if action_name != entry.get("action"):
                return
            action = self.data["actions"][action_name]
            if self.enabled and matches(
                action.get("valid_when", {}), self.client.props
            ):
                if action["call"] == "Switch":
                    self.client.call("Switch")
                else:
                    self._open_config()
            self._call(
                NAME, PATH, NAME, "CloseNotification", GLib.Variant("(u)", (notice_id,))
            )

    def _call(
        self, name: str, path: str, interface: str, method: str, params: GLib.Variant
    ) -> None:
        @guarded
        def done(bus: Gio.DBusConnection, result: Gio.AsyncResult) -> None:
            try:
                bus.call_finish(result)
            except GLib.Error as exc:
                LOG.debug("Desktop call %s failed: %s", method, exc)

        self.client.connection.call(
            name,
            path,
            interface,
            method,
            params,
            None,
            Gio.DBusCallFlags.NO_AUTO_START,
            self.client.timeout_ms,
            self.cancel,
            done,
        )

    def _open_config(self) -> None:
        self._call(
            "org.freedesktop.portal.Desktop",
            "/org/freedesktop/portal/desktop",
            "org.freedesktop.portal.OpenURI",
            "OpenURI",
            GLib.Variant("(ssa{sv})", ("", self.config_file.resolve().as_uri(), {})),
        )

    def configure(self, tr: Translator, enabled: bool) -> None:
        self.tr, self.enabled = tr, enabled
        if not enabled:
            self.queue.clear()

    def stop(self) -> None:
        self.closed = True
        self.cancel.cancel()
        self.queue.clear()
        self.client.connection.signal_unsubscribe(self.subscription)
        Gio.bus_unwatch_name(self.active_watch)
        if self.event in self.client.listeners:
            self.client.listeners.remove(self.event)
