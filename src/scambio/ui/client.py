"""Asynchronous client, preserving the daemon's signal order and own-call window."""

import logging
from collections.abc import Callable
from typing import Any

from gi.repository import Gio, GLib

from scambio.api import INTERFACE, introspection_xml
from scambio.ui.guard import guarded

LOG = logging.getLogger(__name__)
Listener = Callable[[str, Any], None]


class ScambioClient:
    def __init__(
        self,
        connection: Gio.DBusConnection,
        bus_name: str,
        path: str,
        ready: Callable[[], None],
        timeout_ms: int,
    ) -> None:
        self.connection, self.bus_name, self.path = connection, bus_name, path
        self.ready, self.timeout_ms = ready, timeout_ms
        self.props: dict[str, Any] = {}
        self.listeners: list[Listener] = []
        self.proxy: Gio.DBusProxy | None = None
        self.handlers: list[int] = []
        self.pending = 0
        self.closed = False
        self.cancel = Gio.Cancellable()
        info = Gio.DBusNodeInfo.new_for_xml(introspection_xml()).interfaces[0]
        Gio.DBusProxy.new(
            connection,
            Gio.DBusProxyFlags.DO_NOT_AUTO_START,
            info,
            bus_name,
            path,
            INTERFACE,
            self.cancel,
            self._ready,
        )

    @guarded
    def _ready(self, source: Any, result: Gio.AsyncResult) -> None:
        try:
            proxy = Gio.DBusProxy.new_finish(result)
        except GLib.Error as exc:
            LOG.debug("Cannot read daemon properties: %s", exc)
            return
        if self.closed:
            return
        self.proxy = proxy
        self.props = {
            key: value.unpack()
            for key in proxy.get_cached_property_names() or []
            if (value := proxy.get_cached_property(key)) is not None
        }
        if not self.props:
            LOG.error("Daemon returned no initial properties")
            return
        self.handlers = [
            proxy.connect("g-properties-changed", self._properties),
            proxy.connect("g-signal", self._signal),
        ]
        self.ready()

    def emit(self, event: str, value: Any) -> None:
        for listener in tuple(self.listeners):
            guarded(listener)(event, value)

    @guarded
    def _properties(
        self, proxy: Gio.DBusProxy, changed: GLib.Variant, invalidated: list[str]
    ) -> None:
        if self.closed:
            return
        before = self.props.copy()
        self.props.update(changed.unpack())
        for key in invalidated:
            self.props.pop(key, None)
        self.emit("PropertiesChanged", (before, self.pending > 0))

    @guarded
    def _signal(
        self, proxy: Gio.DBusProxy, sender: str, name: str, params: GLib.Variant
    ) -> None:
        if not self.closed:
            self.emit(name, params.unpack())

    def call(
        self,
        method: str,
        parameters: GLib.Variant | None = None,
        on_reply: Callable[[Any], None] | None = None,
        on_error: Callable[[str], None] | None = None,
    ) -> None:
        if self.closed or self.proxy is None:
            return
        self.pending += 1

        @guarded
        def done(proxy: Gio.DBusProxy, result: Gio.AsyncResult) -> None:
            self.pending -= 1
            try:
                reply = proxy.call_finish(result)
            except GLib.Error as exc:
                LOG.debug("UI command %s failed: %s", method, exc)
                if on_error and not self.closed:
                    on_error(Gio.DBusError.get_remote_error(exc) or str(exc))
            else:
                if on_reply and not self.closed:
                    on_reply(reply.unpack())

        try:
            self.proxy.call(
                method,
                parameters,
                Gio.DBusCallFlags.NO_AUTO_START,
                self.timeout_ms,
                self.cancel,
                done,
            )
        except Exception:
            self.pending -= 1
            raise

    def stop(self) -> None:
        self.closed = True
        self.cancel.cancel()
        if self.proxy:
            for handler in self.handlers:
                self.proxy.disconnect(handler)
        self.handlers.clear()
        self.listeners.clear()
