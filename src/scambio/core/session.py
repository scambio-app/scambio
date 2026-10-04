"""Deduplicated lock sources and logind delay inhibitor on the Gio main loop."""

import logging
import os
from typing import Any

from gi.repository import Gio, GLib

from scambio.config import Config
from scambio.core.policy import Event
from scambio.core.ports import Emit
from scambio.core.transport import BusClient

LOG = logging.getLogger(__name__)
PROPERTIES = "org.freedesktop.DBus.Properties"
LOGIN = "org.freedesktop.login1"
MANAGER = LOGIN + ".Manager"
ROOT = "/org/freedesktop/login1"
SAVER = "org.freedesktop.ScreenSaver"


class Session:
    def __init__(
        self,
        system: Gio.DBusConnection,
        session: Gio.DBusConnection,
        config: Config,
        emit: Emit,
    ) -> None:
        self.emit, self.config = emit, config
        timeout = config.backend.dbus_timeout_seconds * 1000
        self.login = BusClient(system, LOGIN, timeout)
        self.saver = BusClient(session, SAVER, timeout)
        self.sources: dict[str, bool | None] = {"logind": None, "screensaver": None}
        self.initialized: set[str] = set()
        self.locked: bool | None = None
        self.session_path = ""
        self.ready = False
        self.fd: int | None = None
        self.inhibit_generation = 0
        self.login_generation = 0
        self.saver_generation = 0
        self.sleeping = False

    def reload(self, config: Config) -> None:
        self.config = config
        self.login.timeout_ms = self.saver.timeout_ms = (
            config.backend.dbus_timeout_seconds * 1000
        )

    def start(self) -> None:
        self.login.subscribe(PROPERTIES, "PropertiesChanged", self._properties)
        self.login.subscribe(MANAGER, "PrepareForSleep", self._sleep, ROOT)
        self.saver.subscribe(SAVER, "ActiveChanged", self._active)
        self.login.watch_owner(self._attach_login)
        self.saver.watch_owner(self._attach_saver)
        self._attach_login()
        self._attach_saver()

    def _set(self, source: str, value: bool | None) -> None:
        self.sources[source] = value
        self.initialized.add(source)
        self.ready = len(self.initialized) == 2
        combined = any(self.sources.values())
        if self.ready and combined != self.locked:
            self.locked = combined
            LOG.info("Lock source %s: %s", source, combined)
            if all(v is None for v in self.sources.values()):
                LOG.warning("No screen lock source available")
            self.emit(Event("Locked", combined))

    def _attach_login(self) -> None:
        self.login_generation += 1
        generation = self.login_generation
        self.release_inhibitor()
        self._inhibit()

        def display(reply: Any, error: str) -> None:
            if generation != self.login_generation:
                return
            self.session_path = "" if error else str(reply[0][1])
            if not self.session_path or self.session_path == "/":
                self._set("logind", None)
                return
            self._read_locked(generation)

        self.login.call(
            ROOT + "/user/self",
            PROPERTIES,
            "Get",
            GLib.Variant("(ss)", (LOGIN + ".User", "Display")),
            display,
        )

    def _read_locked(self, generation: int) -> None:
        def locked(reply: Any, error: str) -> None:
            if generation == self.login_generation:
                self._set("logind", None if error else bool(reply[0]))

        self.login.call(
            self.session_path,
            PROPERTIES,
            "Get",
            GLib.Variant("(ss)", (LOGIN + ".Session", "LockedHint")),
            locked,
        )

    def _attach_saver(self) -> None:
        self.saver_generation += 1
        generation = self.saver_generation

        def active(reply: Any, error: str) -> None:
            if generation == self.saver_generation:
                self._set("screensaver", None if error else bool(reply[0]))

        self.saver.call(
            "/org/freedesktop/ScreenSaver", SAVER, "GetActive", None, active
        )

    def _active(self, *args: Any) -> None:
        self.saver_generation += 1  # Initial reply cannot overwrite a newer signal.
        self._set("screensaver", bool(args[5].unpack()[0]))

    def _properties(self, *args: Any) -> None:
        interface, changes, invalidated = args[5].unpack()
        if interface == LOGIN + ".User" and "Display" in changes:
            self._attach_login()
        elif args[2] == self.session_path and interface == LOGIN + ".Session":
            if "LockedHint" in changes:
                self.login_generation += 1
                self._set("logind", bool(changes["LockedHint"]))
            elif "LockedHint" in invalidated:
                self._read_locked(self.login_generation)

    def _sleep(self, *args: Any) -> None:
        sleeping = bool(args[5].unpack()[0])
        if sleeping == self.sleeping:
            return
        self.sleeping = sleeping
        self.emit(Event("Sleep", sleeping))
        if not sleeping:
            self._inhibit()

    def _inhibit(self) -> None:
        if self.sleeping or self.login.closed:
            return
        self.release_inhibitor()
        generation = self.inhibit_generation

        def finished(bus: Gio.DBusConnection, result: Gio.AsyncResult) -> None:
            try:
                reply, fds = bus.call_with_unix_fd_list_finish(result)
                fd = fds.get(reply.unpack()[0])
            except GLib.Error as exc:
                LOG.warning("Cannot acquire sleep inhibitor: %s", exc)
                return
            if (
                self.login.closed
                or self.sleeping
                or generation != self.inhibit_generation
            ):
                os.close(fd)
            else:
                self.fd = fd

        self.login.bus.call_with_unix_fd_list(
            LOGIN,
            ROOT,
            MANAGER,
            "Inhibit",
            GLib.Variant(
                "(ssss)",
                ("sleep", "Scambio", "Release Bluetooth device before sleep", "delay"),
            ),
            GLib.VariantType.new("(h)"),
            Gio.DBusCallFlags.NO_AUTO_START,
            self.login.timeout_ms,
            None,
            self.login.cancel,
            finished,
        )

    def release_inhibitor(self) -> None:
        self.inhibit_generation += 1
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def close(self) -> None:
        self.release_inhibitor()
        self.login.close()
        self.saver.close()
