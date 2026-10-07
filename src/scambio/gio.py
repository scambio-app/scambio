# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Fermich srl
"""Compatibility with both Ubuntu 24.04 GLib and current GLib."""

from typing import Any

from gi.repository import Gio, GLib

try:
    from gi.repository import GLibUnix  # type: ignore[attr-defined]
except ImportError:
    GLibUnix = None


def register_object(bus: Gio.DBusConnection, *args: Any) -> int:
    method = getattr(bus, "register_object_with_closures2", None)
    if method is None:
        method = bus.register_object
    return int(method(*args))


def signal_add(*args: Any) -> int:
    module = GLibUnix
    if module is not None:
        return int(module.signal_add(*args))
    return int(GLib.unix_signal_add(*args))
