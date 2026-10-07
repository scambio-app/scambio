# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Fermich srl
"""One Background portal request per Flatpak process, without retries."""

import logging
import uuid
from pathlib import Path
from typing import Any

from gi.repository import Gio, GLib

from scambio.i18n import Translator

LOG = logging.getLogger(__name__)
PORTAL = "org.freedesktop.portal.Desktop"
PATH = "/org/freedesktop/portal/desktop"
REQUEST = "org.freedesktop.portal.Request"


class Background:
    def __init__(self, bus: Gio.DBusConnection, timeout_ms: int) -> None:
        self.bus, self.timeout_ms = bus, timeout_ms
        self.requested = False
        self.finished = False
        self.closed = False
        self.subscription = 0
        self.path = ""
        self.cancel = Gio.Cancellable()

    def start(self, language: str, info_file: Path = Path("/.flatpak-info")) -> None:
        if self.requested or self.closed or not info_file.is_file():
            return
        self.requested = True
        token = "scambio_" + uuid.uuid4().hex
        sender = (self.bus.get_unique_name() or "").lstrip(":").replace(".", "_")
        self.path = f"{PATH}/request/{sender}/{token}"
        self.subscription = self.bus.signal_subscribe(
            PORTAL,
            REQUEST,
            "Response",
            self.path,
            None,
            Gio.DBusSignalFlags.NONE,
            self._response,
        )
        self.bus.call(
            PORTAL,
            PATH,
            "org.freedesktop.portal.Background",
            "RequestBackground",
            GLib.Variant(
                "(sa{sv})",
                (
                    "",
                    {
                        "handle_token": GLib.Variant("s", token),
                        "reason": GLib.Variant(
                            "s", Translator(language).tr("background-reason")
                        ),
                        "autostart": GLib.Variant("b", True),
                        "commandline": GLib.Variant("as", ["scambio", "daemon"]),
                        "dbus-activatable": GLib.Variant("b", False),
                    },
                ),
            ),
            GLib.VariantType.new("(o)"),
            Gio.DBusCallFlags.NONE,
            self.timeout_ms,
            self.cancel,
            self._returned,
        )

    def _finish(self, accepted: bool) -> None:
        if self.finished or self.closed:
            return
        self.finished = True
        if self.subscription:
            self.bus.signal_unsubscribe(self.subscription)
            self.subscription = 0
        if not accepted:
            LOG.info("Background portal did not grant automatic startup")

    def _response(self, *args: Any) -> None:
        code, values = args[5].unpack()
        self._finish(code == 0 and values.get("autostart") is True)

    def _returned(self, bus: Gio.DBusConnection, result: Gio.AsyncResult) -> None:
        try:
            reply = bus.call_finish(result)
            if reply.unpack()[0] != self.path:
                self._finish(False)
        except GLib.Error:
            self._finish(False)

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        self.cancel.cancel()
        if self.subscription:
            self.bus.signal_unsubscribe(self.subscription)
            self.subscription = 0
            self.bus.call(
                PORTAL,
                self.path,
                REQUEST,
                "Close",
                None,
                None,
                Gio.DBusCallFlags.NO_AUTO_START,
                self.timeout_ms,
                None,
                None,
            )
