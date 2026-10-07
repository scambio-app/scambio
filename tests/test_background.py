# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Fermich srl

import logging

import pytest
from gi.repository import Gio, GLib

from scambio.core.background import PATH, PORTAL, REQUEST, Background
from scambio.core.service import pactl_command, reexec
from scambio.i18n import Translator


class PortalBus:
    def __init__(self):
        self.calls = []
        self.subscriptions = {}

    def get_unique_name(self):
        return ":1.42"

    def signal_subscribe(self, *args):
        self.subscriptions[1] = args
        return 1

    def signal_unsubscribe(self, subscription):
        self.subscriptions.pop(subscription)

    def call(self, *args):
        self.calls.append(args)

    def call_finish(self, result):
        if isinstance(result, Exception):
            raise result
        return result

    def respond(self, code, autostart):
        callback = self.subscriptions[1][-1]
        callback(
            self,
            PORTAL,
            PATH,
            REQUEST,
            "Response",
            GLib.Variant(
                "(ua{sv})", (code, {"autostart": GLib.Variant("b", autostart)})
            ),
        )


@pytest.mark.parametrize("language", ["it", "en", "de"])
@pytest.mark.parametrize("code,autostart", [(0, True), (0, False), (1, False)])
def test_background_once_with_fixed_command(
    tmp_path, caplog, language, code, autostart
):
    caplog.set_level(logging.INFO)
    info = tmp_path / "flatpak-info"
    info.touch()
    bus = PortalBus()
    background = Background(bus, 1234)
    background.start(language, info)
    background.start(language, info)
    assert len(bus.calls) == 1
    destination, path, interface, method, params, _, flags, timeout, _, returned = (
        bus.calls[0]
    )
    assert (destination, path, interface, method) == (
        PORTAL,
        PATH,
        "org.freedesktop.portal.Background",
        "RequestBackground",
    )
    parent, options = params.unpack()
    assert parent == ""
    assert options == {
        "handle_token": background.path.rsplit("/", 1)[-1],
        "reason": Translator(language).tr("background-reason"),
        "autostart": True,
        "commandline": ["scambio", "daemon"],
        "dbus-activatable": False,
    }
    assert timeout == 1234 and flags == Gio.DBusCallFlags.NONE
    # A portal can emit Response before completing the method call.
    bus.respond(code, autostart)
    returned(bus, GLib.Variant("(o)", (background.path,)))
    background.start(language, info)
    assert len(bus.calls) == 1 and not bus.subscriptions
    assert len(caplog.records) == int(code != 0 or not autostart)
    background.close()


def test_host_never_calls_portal(tmp_path):
    bus = PortalBus()
    background = Background(bus, 1000)
    background.start("en", tmp_path / "absent")
    background.close()
    assert not bus.calls and not bus.subscriptions


def test_missing_portal_logs_once_and_never_retries(tmp_path, caplog):
    caplog.set_level(logging.INFO)
    info = tmp_path / "flatpak-info"
    info.touch()
    bus = PortalBus()
    background = Background(bus, 1000)
    background.start("en", info)
    bus.calls[0][-1](bus, GLib.Error("No portal"))
    background.start("en", info)
    background.close()
    assert len(bus.calls) == 1 and len(caplog.records) == 1
    assert not bus.subscriptions


def test_close_cancels_pending_request(tmp_path):
    info = tmp_path / "flatpak-info"
    info.touch()
    bus = PortalBus()
    background = Background(bus, 1000)
    background.start("en", info)
    background.close()
    background.close()
    assert background.cancel.is_cancelled() and not bus.subscriptions
    assert bus.calls[-1][:4] == (PORTAL, background.path, REQUEST, "Close")
    assert len(bus.calls) == 2


def test_reexec_ignores_untrusted_process_arguments(monkeypatch):
    from scambio.core import service

    monkeypatch.setattr(service.sys, "executable", "/trusted/python3")
    monkeypatch.setattr(service.sys, "argv", ["/tmp/evil", "--arbitrary"])
    calls = []
    monkeypatch.setattr(service.os, "execv", lambda *args: calls.append(args))
    reexec()
    executable, args = calls[0]
    assert executable == "/trusted/python3"
    assert args[:5] == [executable, "-I", "-m", "scambio", "daemon"]
    assert args[5:] in ([], ["--debug"])


def test_pactl_uses_only_system_search_path(monkeypatch):
    from scambio.core import service

    calls = []
    monkeypatch.setenv("PATH", "/tmp/untrusted")
    monkeypatch.setattr(
        service.shutil,
        "which",
        lambda name, path: calls.append((name, path)) or "/usr/bin/pactl",
    )
    assert pactl_command() == ("/usr/bin/pactl",)
    assert calls == [("pactl", "/usr/bin:/bin")]
