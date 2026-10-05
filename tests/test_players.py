"""Real Gio RPCs to disposable MPRIS mocks on conftest's private session bus."""

import subprocess
from dataclasses import replace

import dbus
import dbusmock
import pytest
from gi.repository import Gio
from helpers import drain, gio_bus, spin_until

from scambio.config import Backend, Config
from scambio.core.players import PATH, PLAYER, PREFIX, Players
from scambio.state import PlayerRef, ResumePlayers, Store


def bus_id():
    bus = dbusmock.BusType.SESSION.get_connection()
    return str(
        bus.get_object("org.freedesktop.DBus", "/org/freedesktop/DBus").GetId(
            dbus_interface="org.freedesktop.DBus"
        )
    )


class FakePlayer:
    def __init__(self, segment, status="Playing", pause=None, play=None):
        self.name = PREFIX + segment
        self.mock = dbusmock.SpawnedMock.spawn_for_name(
            self.name, PATH, PLAYER, stdout=subprocess.DEVNULL
        )
        self.obj = self.mock.obj
        self.obj.AddProperty(
            PLAYER,
            "PlaybackStatus",
            dbus.String(status),
            dbus_interface=dbusmock.MOCK_IFACE,
        )
        for method, value, code in [
            ("Pause", "Paused", pause),
            ("Play", "Playing", play),
        ]:
            self.obj.AddMethod(
                PLAYER,
                method,
                "",
                "",
                code
                if code is not None
                else f'self.props["{PLAYER}"]["PlaybackStatus"] = "{value}"',
                dbus_interface=dbusmock.MOCK_IFACE,
            )

    def status(self, value):
        self.obj.UpdateProperties(
            PLAYER, {"PlaybackStatus": value}, dbus_interface=dbusmock.MOCK_IFACE
        )

    def calls(self):
        return [
            str(c[1])
            for c in self.obj.GetCalls(dbus_interface=dbusmock.MOCK_IFACE)
            if str(c[1]) in {"Pause", "Play"}
        ]

    def close(self):
        self.mock.terminate()


@pytest.fixture
def player_factory():
    players = []

    def create(*args, **kwargs):
        p = FakePlayer(*args, **kwargs)
        players.append(p)
        return p

    yield create
    for p in players:
        p.close()


@pytest.fixture
def adapter(tmp_path):
    p = Players(
        gio_bus(Gio.BusType.SESSION),
        Config(backend=Backend(player_timeout_ms=100)),
        Store(tmp_path / "state.json"),
    )
    yield p
    p.close()
    drain()


def complete(method, *args):
    done = []
    method(*args, lambda: done.append(True))
    spin_until(lambda: done)
    assert done == [True]


def test_pause_candidates_and_idle(adapter, player_factory):
    playing = player_factory("chromium.instance1")
    paused = player_factory("firefox.instance1", "Paused")
    stopped = player_factory("elisa", "Stopped")
    excluded = [
        player_factory(n)
        for n in [
            "kdeconnect.instance1",
            "playerctld",
            "plasma-browser-integration",
            "VLC.instance2",
        ]
    ]
    adapter.reload(
        replace(
            adapter.config,
            audio=replace(
                adapter.config.audio,
                ignore_players=(*adapter.config.audio.ignore_players, "vlc"),
            ),
        )
    )
    drain()
    assert all(p.calls() == [] for p in [playing, paused, stopped, *excluded])
    complete(adapter.pause, "grab")
    assert playing.calls() == ["Pause"]
    assert all(p.calls() == [] for p in [paused, stopped, *excluded])
    assert len(adapter.held) == 1
    saved = adapter.store.value.resume_players
    assert saved.bus_id == bus_id()
    assert Store(adapter.store.path).load().resume_players == saved
    calls = playing.obj.GetCalls(dbus_interface=dbusmock.MOCK_IFACE)
    drain(150)
    assert playing.obj.GetCalls(dbus_interface=dbusmock.MOCK_IFACE) == calls
    assert not adapter.clients


@pytest.mark.parametrize(
    "status,expected",
    [
        ("Paused", ["Pause", "Play"]),
        ("Playing", ["Pause", "Play"]),
        ("Stopped", ["Pause"]),
    ],
)
def test_resume_status(adapter, player_factory, status, expected):
    p = player_factory("fake")
    complete(adapter.pause, "grab")
    p.status(status)
    complete(adapter.resume)
    assert p.calls() == expected
    assert not adapter.held and adapter.store.value.resume_players is None


def test_reclassification_forget(adapter, player_factory):
    p = player_factory("fake")
    complete(adapter.pause, "grab")
    complete(adapter.pause, "release")
    assert set(adapter.held.values()) == {"release"}
    assert adapter.store.value.resume_players is None
    complete(adapter.pause, "grab")
    assert set(adapter.held.values()) == {"grab"}
    assert len(adapter.store.value.resume_players.players) == 1
    complete(adapter.forget)
    assert p.calls() == ["Pause"] and not adapter.held
    assert adapter.store.value.resume_players is None


def test_owner_replaced_and_name_gone(adapter, player_factory):
    p = player_factory("replace")
    gone = player_factory("gone")
    complete(adapter.pause, "grab")
    p.close()
    gone.close()
    replacement = player_factory("replace", "Paused")
    complete(adapter.resume)
    assert replacement.calls() == []
    assert not adapter.held


@pytest.mark.parametrize(
    "code",
    [
        'raise dbus.exceptions.DBusException("denied", name="org.test.Denied")',
        "import time; time.sleep(0.3)",
    ],
)
def test_pause_error_timeout_does_not_block_others(
    adapter, player_factory, caplog, code
):
    bad = player_factory("bad", pause=code)
    good = player_factory("good")
    complete(adapter.pause, "grab")
    assert {ref.name for ref in adapter.held} == {good.name}
    assert "MPRIS Pause failed" in caplog.text
    assert good.calls() == ["Pause"]
    drain(350)
    assert bad.calls() == ["Pause"]
    assert len(adapter.held) == 1
    complete(adapter.resume)
    assert good.calls() == ["Pause", "Play"]


def test_resume_error_timeout(adapter, player_factory, caplog):
    p = player_factory("bad", play="import time; time.sleep(0.3)")
    complete(adapter.pause, "grab")
    complete(adapter.resume)
    assert not adapter.held and adapter.store.value.resume_players is None
    assert "MPRIS Play failed" in caplog.text
    drain(350)
    assert p.calls() == ["Pause", "Play"]


@pytest.mark.parametrize("same_bus", [False, True])
def test_recover(adapter, player_factory, same_bus):
    p = player_factory("recover", "Paused")
    bus = dbusmock.BusType.SESSION.get_connection()
    adapter.store.value.resume_players = ResumePlayers(
        bus_id() if same_bus else "previous-login",
        (PlayerRef(p.name, str(bus.get_name_owner(p.name))),),
    )
    complete(adapter.recover)
    assert p.calls() == (["Play"] if same_bus else [])
    assert adapter.store.value.resume_players is None


@pytest.mark.parametrize("kind", ["grab", "release"])
def test_shutdown(adapter, player_factory, kind):
    p = player_factory("exit")
    complete(adapter.pause, kind)
    complete(adapter.shutdown)
    assert p.calls() == (["Pause", "Play"] if kind == "grab" else ["Pause"])


def test_empty(adapter):
    complete(adapter.pause, "grab")
    complete(adapter.resume)
    complete(adapter.forget)
    assert not adapter.held


def test_discovery_shares_read_deadline(adapter, player_factory, monkeypatch, caplog):
    from gi.repository import GLib

    p = player_factory("slow_read")
    p.obj.AddMethod(
        "org.freedesktop.DBus.Properties",
        "Get",
        "ss",
        "v",
        'import time; time.sleep(0.07); ret = dbus.String("Playing")',
        dbus_interface=dbusmock.MOCK_IFACE,
    )
    original = adapter._daemon

    def delayed(method, params, done, timeout_ms=None):
        if method == "ListNames":

            def reply(value, error):
                GLib.timeout_add(70, lambda: (done(value, error), False)[1])

            original(method, params, reply, timeout_ms)
        else:
            original(method, params, done, timeout_ms)

    monkeypatch.setattr(adapter, "_daemon", delayed)
    complete(adapter.pause, "grab")
    assert not adapter.held
    assert "MPRIS Get failed" in caplog.text
    drain(150)
    assert p.calls() == []


def test_close_cancels_pending_calls(adapter, player_factory):
    p = player_factory("closed")
    done = []
    adapter.pause("grab", lambda: done.append(True))
    adapter.close()
    drain(150)
    assert not done and not adapter.clients and p.calls() == []
