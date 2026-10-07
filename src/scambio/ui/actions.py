# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Fermich srl
"""Shared GActions dispatch only through the public daemon client."""

from gi.repository import Gio, GLib

from scambio.api import SETTINGS_BUS_NAME, SETTINGS_PATH
from scambio.text import logger
from scambio.ui.client import ScambioClient
from scambio.ui.guard import guarded

LOG = logger(__name__)


def open_settings(client: ScambioClient) -> None:
    @guarded
    def done(bus: Gio.DBusConnection, result: Gio.AsyncResult) -> None:
        try:
            bus.call_finish(result)
        except GLib.Error as exc:
            if (
                Gio.DBusError.get_remote_error(exc)
                == "org.freedesktop.DBus.Error.ServiceUnknown"
            ):
                LOG.warning("Cannot open settings: eseguire make install-user")
            else:
                LOG.warning("Cannot open settings: %s", exc)

    client.connection.call(
        SETTINGS_BUS_NAME,
        SETTINGS_PATH,
        "org.freedesktop.Application",
        "Activate",
        GLib.Variant("(a{sv})", ({},)),
        None,
        Gio.DBusCallFlags.NONE,
        client.timeout_ms,
        None,
        done,
    )


def create_actions(client: ScambioClient) -> Gio.SimpleActionGroup:
    group = Gio.SimpleActionGroup()

    @guarded
    def activate(action: Gio.SimpleAction, parameter: GLib.Variant | None) -> None:
        name = action.get_name()
        if name == "switch":
            client.call("Switch")
        elif name == "toggle-priority":
            client.call(
                "SetPriority",
                GLib.Variant("(b)", (not client.props["IphonePriority"],)),
            )
        elif name == "quit":
            client.call("Quit")
        elif name == "open-settings":
            open_settings(client)

    for name in ("switch", "toggle-priority", "quit", "open-settings"):
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", activate)
        group.add_action(action)
    return group
