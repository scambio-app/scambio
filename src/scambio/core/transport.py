# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Fermich srl
"""Gio boundary: asynchronous D-Bus calls and owned subscriptions."""

from collections.abc import Callable
from typing import Any

from gi.repository import Gio, GLib

Reply = Callable[[Any, str], None]


class BusClient:
    def __init__(self, bus: Gio.DBusConnection, name: str, timeout_ms: int) -> None:
        self.bus = bus
        self.name = name
        self.timeout_ms = timeout_ms
        self.subscriptions: list[int] = []
        self.cancel = Gio.Cancellable()
        self.closed = False

    def call(
        self,
        path: str,
        interface: str,
        method: str,
        params: GLib.Variant | None,
        callback: Reply,
        timeout_ms: int | None = None,
    ) -> None:
        def finished(bus: Gio.DBusConnection, result: Gio.AsyncResult) -> None:
            try:
                reply = bus.call_finish(result).unpack()
            except GLib.Error as exc:
                if not self.closed:
                    callback(None, Gio.DBusError.get_remote_error(exc) or str(exc))
            else:
                if not self.closed:
                    callback(reply, "")

        self.bus.call(
            self.name,
            path,
            interface,
            method,
            params,
            None,
            Gio.DBusCallFlags.NO_AUTO_START,
            timeout_ms or self.timeout_ms,
            self.cancel,
            finished,
        )

    def subscribe(
        self,
        interface: str,
        signal: str,
        callback: Callable[..., None],
        path: str | None = None,
        sender: str | None = None,
        arg0: str | None = None,
    ) -> None:
        self.subscriptions.append(
            self.bus.signal_subscribe(
                sender or self.name,
                interface,
                signal,
                path,
                arg0,
                Gio.DBusSignalFlags.NONE,
                callback,
            )
        )

    def watch_owner(self, callback: Callable[[], None]) -> None:
        self.subscribe(
            "org.freedesktop.DBus",
            "NameOwnerChanged",
            lambda *_: callback(),
            "/org/freedesktop/DBus",
            "org.freedesktop.DBus",
            self.name,
        )

    def close(self) -> None:
        self.closed = True
        self.cancel.cancel()
        for sub in self.subscriptions:
            self.bus.signal_unsubscribe(sub)
        self.subscriptions.clear()
