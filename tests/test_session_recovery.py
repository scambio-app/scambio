# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Fermich srl
"""Inhibitor ownership across private logind restarts and pending replies."""

import os
import subprocess

import dbus
import dbusmock
import pytest
from gi.repository import Gio
from helpers import drain, gio_bus, spin_until

from scambio.config import Config
from scambio.core.session import LOGIN, MANAGER, ROOT, Session


def logind():
    return dbusmock.SpawnedMock.spawn_with_template("logind", stdout=subprocess.DEVNULL)


def sleep_signal(login, value):
    login.obj.EmitSignal(
        MANAGER, "PrepareForSleep", "b", [value], dbus_interface=dbusmock.MOCK_IFACE
    )


def inhibit_calls(login):
    return login.obj.GetMethodCalls("Inhibit", dbus_interface=dbusmock.MOCK_IFACE)


def test_logind_restart_and_display_change_during_sleep():
    login = logind()
    adapter = Session(
        gio_bus(Gio.BusType.SYSTEM),
        gio_bus(Gio.BusType.SESSION),
        Config(),
        lambda event: None,
    )
    try:
        adapter.start()
        spin_until(lambda: adapter.ready and adapter.fd is not None)
        sleep_signal(login, True)
        spin_until(lambda: adapter.sleeping)
        old_fd = adapter.fd
        adapter.release_inhibitor()
        with pytest.raises(OSError):
            os.fstat(old_fd)
        generation = adapter.login_generation
        login.terminate()
        spin_until(lambda: adapter.login_generation > generation)
        generation = adapter.login_generation
        login = logind()
        spin_until(lambda: adapter.login_generation > generation)
        drain()
        assert adapter.fd is None and len(inhibit_calls(login)) == 0
        # The User.Display path uses the same attach logic as owner recovery.
        login.obj.AddObject(
            ROOT + "/user/self",
            LOGIN + ".User",
            {"Display": dbus.Struct(("", dbus.ObjectPath("/")), signature="so")},
            [],
            dbus_interface=dbusmock.MOCK_IFACE,
        )
        user = dbusmock.BusType.SYSTEM.get_connection().get_object(
            LOGIN, ROOT + "/user/self"
        )
        generation = adapter.login_generation
        user.UpdateProperties(
            LOGIN + ".User",
            {"Display": dbus.Struct(("other", dbus.ObjectPath("/")), signature="so")},
            dbus_interface=dbusmock.MOCK_IFACE,
        )
        spin_until(lambda: adapter.login_generation > generation)
        drain()
        assert adapter.fd is None and len(inhibit_calls(login)) == 0
        sleep_signal(login, False)
        spin_until(lambda: adapter.fd is not None)
        assert not adapter.sleeping and len(inhibit_calls(login)) == 1
        descriptor = adapter.fd
        sleep_signal(login, False)
        drain()
        assert adapter.fd == descriptor and len(inhibit_calls(login)) == 1
    finally:
        adapter.close()
        login.terminate()
        drain()


def test_inhibitor_reply_arriving_during_sleep_is_closed(monkeypatch):
    login = logind()
    adapter = Session(
        gio_bus(Gio.BusType.SYSTEM),
        gio_bus(Gio.BusType.SESSION),
        Config(),
        lambda event: None,
    )
    pending = []
    try:
        adapter.start()
        spin_until(lambda: adapter.ready and adapter.fd is not None)
        original = adapter.login.bus.call_with_unix_fd_list

        def delayed(*args):
            callback = args[-1]
            original(
                *args[:-1], lambda bus, result: pending.append((callback, bus, result))
            )

        with monkeypatch.context() as patch:
            patch.setattr(adapter.login.bus, "call_with_unix_fd_list", delayed)
            adapter._inhibit()
            spin_until(lambda: pending)
            sleep_signal(login, True)
            spin_until(lambda: adapter.sleeping)
            closed = []
            close = os.close

            def record_close(fd):
                closed.append(fd)
                close(fd)

            patch.setattr(os, "close", record_close)
            callback, bus, result = pending.pop()
            callback(bus, result)
            assert adapter.fd is None and len(closed) == 1
            with pytest.raises(OSError):
                os.fstat(closed[0])
        sleep_signal(login, False)
        spin_until(lambda: adapter.fd is not None)
    finally:
        adapter.close()
        login.terminate()
        drain()
