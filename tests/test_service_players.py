"""Executor ordering and lifecycle against private-bus MPRIS servers."""

import json
import signal
from dataclasses import replace

import pytest
from gi.repository import Gio
from helpers import ADDRESS, drain, gio_bus, spin_until
from test_players import bus_id, complete
from test_players import player_factory as _player_factory
from test_service import client, properties
from test_service import daemon as _daemon

from scambio.config import TEMPLATE, Config, Device, Policy
from scambio.core.policy import Action as A
from scambio.core.policy import Context, Event
from scambio.core.service import Service
from scambio.state import PlayerRef, ResumePlayers, Store

player_factory = _player_factory
daemon = _daemon


class Ports:
    ready = True
    connected = False
    name = "fake"

    def __init__(self):
        self.calls = []
        self.pending = []

    def start(self):
        self.calls.append("start")

    def route(self, done):
        self.calls.append("route")
        self.pending.append(done)

    def restore(self, done):
        self.calls.append("restore")
        self.pending.append(done)

    def finish(self):
        self.pending.pop(0)()

    def connect(self):
        self.calls.append("connect")

    def disconnect(self):
        self.calls.append("disconnect")

    def release_inhibitor(self):
        self.calls.append("inhibitor")

    def close(self):
        pass

    def reload(self, config):
        pass


@pytest.fixture
def executor(tmp_path):
    ports = Ports()
    cfg = Config(device=Device(ADDRESS), policy=Policy(resume_delay_ms=2000))
    service = Service(
        gio_bus(Gio.BusType.SESSION),
        cfg,
        Store(tmp_path / "state.json"),
        tmp_path / "config.toml",
        lambda emit: (ports, ports, ports),
    )
    service.initialized = True
    yield service, ports
    service.close()
    drain()


def held(service):
    return service.players.held


def test_grab_parallel_connect_resume_after_route(executor, player_factory):
    s, ports = executor
    p = player_factory("pipeline")
    s.ctx = Context(state="released", audio_active=True)
    s.event(Event("TimerFired", "GRAB_DELAY"))
    assert ports.calls == ["connect"] and p.calls() == []
    spin_until(lambda: held(s))
    s.event(Event("AudioActive", False))
    s.event(Event("DeviceConnected", True))
    s.event(Event("DeviceSinkAppeared"))
    assert s.ctx.held and s.idle_release_at == 0 and ports.calls[-1] == "route"
    s.event(Event("TimerFired", "RESUME"))
    drain()
    assert p.calls() == ["Pause"]
    ports.finish()
    spin_until(lambda: p.calls() == ["Pause", "Play"])
    assert not held(s)


def test_release_waits_for_entire_player_prefix(executor, player_factory):
    s, ports = executor
    p = player_factory("pipeline")
    s.ctx = Context(state="releasing")
    s._actions(
        [
            A("PausePlayers", "grab"),
            A("PausePlayers", "release"),
            A("RestoreRouting"),
            A("Disconnect"),
        ]
    )
    assert ports.calls == []
    spin_until(lambda: ports.calls == ["restore"])
    assert p.calls() == ["Pause"]
    assert set(held(s).values()) == {"release"}
    assert s.store.value.resume_players is None
    ports.finish()
    assert ports.calls == ["restore", "disconnect"]


def test_error_while_pause_pending(executor, player_factory):
    s, ports = executor
    p = player_factory("pipeline")
    s.ctx = Context(state="released", audio_active=True)
    s.event(Event("TimerFired", "GRAB_DELAY"))
    s.event(Event("AudioActive", False))
    s.event(Event("TimerFired", "CONNECT"))
    assert ports.calls == ["connect", "restore"]
    assert s.ctx.blocked_until_silence and "UNBLOCK" in s.timers
    spin_until(lambda: held(s))
    assert p.calls() == ["Pause"]
    ports.finish()
    spin_until(lambda: p.calls() == ["Pause", "Play"])
    assert ports.calls[-1] == "disconnect"
    s.event(Event("DisconnectResult"))
    s.event(Event("AudioActive", True))
    assert s.ctx.state == "released" and "GRAB_DELAY" not in s.timers


@pytest.mark.parametrize(
    "event", [Event("Locked", True), Event("Sleep", True), Event("Switch")]
)
def test_release_during_resume_stays_paused(executor, player_factory, event):
    s, ports = executor
    p = player_factory("pipeline")
    complete(s.players.pause, "grab")
    s.ctx = Context(state="on_pc", held=True, routed=True, device_connected=True)
    s.event(event)
    assert s.ctx.state == "releasing" and "RESUME" not in s.timers
    s.event(Event("TimerFired", "RESUME"))
    if event.kind == "Sleep":
        s.event(Event("TimerFired", "SLEEP"))
        assert "inhibitor" in ports.calls
    spin_until(lambda: "restore" in ports.calls)
    ports.finish()
    s.event(Event("DisconnectResult"))
    spin_until(lambda: not held(s))
    assert p.calls() == ["Pause"] and s.store.value.resume_players is None


def test_cross_queue_dependencies_do_not_deadlock(executor, player_factory):
    s, ports = executor
    p = player_factory("pipeline")
    complete(s.players.pause, "grab")
    s.ctx = Context(state="releasing")
    s._actions(
        [
            A("RouteToDevice"),
            A("ResumePlayers"),
            A("PausePlayers", "release"),
            A("RestoreRouting"),
            A("Disconnect"),
        ]
    )
    assert ports.calls == ["route"]
    ports.finish()
    spin_until(lambda: ports.calls == ["route", "restore"])
    assert p.calls() == ["Pause", "Play", "Pause"]
    ports.finish()
    assert ports.calls[-1] == "disconnect"


@pytest.mark.parametrize("same_bus", [True, False])
def test_startup_repair_before_adapters(executor, player_factory, same_bus):
    s, ports = executor
    p = player_factory("pipeline", "Paused")
    from dbusmock import BusType

    owner = str(BusType.SESSION.get_connection().get_name_owner(p.name))
    s.store.value.resume_players = ResumePlayers(
        bus_id() if same_bus else "old", (PlayerRef(p.name, owner),)
    )
    assert s.start()
    assert ports.calls == []
    spin_until(lambda: ports.calls == ["start"] * 3)
    assert p.calls() == (["Play"] if same_bus else [])
    assert s.store.value.resume_players is None


@pytest.mark.parametrize("kind", ["grab", "release"])
def test_stop_settles_pending_pause(executor, player_factory, kind):
    s, ports = executor
    p = player_factory("pipeline")
    s._actions([A("PausePlayers", kind)])
    done = []
    s.stop(lambda: done.append(True))
    spin_until(lambda: done)
    assert s.closed and not s.players.clients
    assert p.calls() == (["Pause", "Play"] if kind == "grab" else ["Pause"])


def test_stop_deadline(executor, player_factory):
    s, ports = executor
    p = player_factory("pipeline")
    complete(s.players.pause, "grab")
    # A stuck player-prefix callback cannot hold shutdown past its deadline.
    s.config = replace(
        s.config, backend=replace(s.config.backend, player_timeout_ms=100)
    )
    s._queue_player(lambda done: ports.pending.append(done))
    done = []
    s.stop(lambda: done.append(True))
    spin_until(lambda: done, seconds=1)
    assert s.closed and p.calls() == ["Pause"]
    assert s.store.value.resume_players is not None  # recover on next startup
    ports.finish()
    drain()
    assert done == [True]


def test_profile_reload_keeps_current_resume_timer(executor):
    s, _ = executor
    s.config_file.write_text(
        TEMPLATE.replace('address = ""', f'address = "{ADDRESS}"').replace(
            'profile = "generic"', 'profile = "meta_glasses"'
        )
    )
    s._execute(A("StartTimer", "RESUME", 3210))
    source = s.timers["RESUME"]
    s.reload()
    assert s.config.policy.resume_delay_ms == 2000 and s.timers["RESUME"] == source
    s.config_file.write_text(
        s.config_file.read_text().replace("meta_glasses", "generic")
    )
    s.reload()
    assert s.config.policy.resume_delay_ms == 0 and s.timers["RESUME"] == source


@pytest.mark.parametrize("kind", ["grab", "release"])
def test_sigterm_process(daemon, fake_pactl, tmp_path, player_factory, kind):
    p = player_factory("pipeline")
    fake_pactl.update(
        {"streams": [{"index": 7, "sink": 1, "corked": False, "properties": {}}]}
    )
    fake_pactl.event()
    spin_until(lambda: p.calls() == ["Pause"])
    if kind == "release":
        fake_pactl.add_sink()
        fake_pactl.event()
        spin_until(lambda: str(properties()["State"]) == "on_pc")
        assert client("switch").returncode == 0
        spin_until(lambda: str(properties()["State"]) in {"releasing", "released"})
    daemon.send_signal(signal.SIGTERM)
    daemon.wait(timeout=5)
    assert daemon.returncode == 0
    calls = p.calls()
    if kind == "grab":
        assert calls == ["Pause", "Play"]
    else:
        assert calls[-1] == "Pause"
    state = json.loads((tmp_path / "state.json").read_text())
    assert state["resume_players"] is None


def test_sigterm_during_releasing(executor, player_factory):
    s, ports = executor
    p = player_factory("pipeline")
    complete(s.players.pause, "grab")
    s.ctx = Context(state="on_pc", held=True, device_connected=True, routed=True)
    s.event(Event("Locked", True))
    assert s.ctx.state == "releasing"
    done = []
    s.stop(lambda: done.append(True))
    spin_until(lambda: done)
    assert p.calls() == ["Pause"]
    assert s.store.value.resume_players is None


@pytest.mark.parametrize("same_bus", [True, False])
def test_startup_repair_process(
    fake_pactl, bluez_server, tmp_path, player_factory, same_bus
):
    import subprocess
    import sys
    from pathlib import Path

    from dbusmock import BusType

    p = player_factory("process_repair", "Paused")
    bus = BusType.SESSION.get_connection()
    store = Store(tmp_path / "state.json")
    store.value.resume_players = ResumePlayers(
        bus_id() if same_bus else "old-login",
        (PlayerRef(p.name, str(bus.get_name_owner(p.name))),),
    )
    store.save()
    (tmp_path / "config.toml").write_text(
        TEMPLATE.replace('address = ""', f'address = "{ADDRESS}"')
    )
    process = subprocess.Popen(
        [
            sys.executable,
            str(Path(__file__).parent / "fixtures/run_daemon.py"),
            str(tmp_path),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        spin_until(lambda: bus.name_has_owner("app.scambio.Test"))
        spin_until(lambda: str(properties()["State"]) == "released")
        assert p.calls() == (["Play"] if same_bus else [])
        assert Store(store.path).load().resume_players is None
    finally:
        process.terminate()
        process.wait(timeout=5)
        assert process.returncode == 0


def test_sigterm_process_while_releasing(
    daemon, bluez_server, fake_pactl, tmp_path, player_factory
):
    import dbusmock

    p = player_factory("process_release")
    # Freeze the mock Disconnect for long enough to deliver SIGTERM in releasing.
    _, device_path, _ = bluez_server
    device = dbusmock.BusType.SYSTEM.get_connection().get_object(
        "org.bluez", device_path
    )
    device.AddMethod(
        "org.bluez.Device1",
        "Disconnect",
        "",
        "",
        "import time; time.sleep(0.5)",
        dbus_interface=dbusmock.MOCK_IFACE,
    )
    fake_pactl.add_sink()
    fake_pactl.update(
        {"streams": [{"index": 7, "sink": 1, "corked": False, "properties": {}}]}
    )
    fake_pactl.event()
    spin_until(lambda: p.calls() == ["Pause", "Play"])
    assert client("switch").returncode == 0
    spin_until(lambda: p.calls() == ["Pause", "Play", "Pause"])
    assert str(properties()["State"]) == "releasing"
    daemon.send_signal(signal.SIGTERM)
    daemon.wait(timeout=5)
    assert daemon.returncode == 0
    assert p.calls() == ["Pause", "Play", "Pause"]
    assert json.loads((tmp_path / "state.json").read_text())["resume_players"] is None


@pytest.mark.parametrize("kind", ["grab", "release"])
def test_stop_supersedes_queued_resume(executor, player_factory, kind):
    s, ports = executor
    p = player_factory("shutdown_race")
    complete(s.players.pause, kind)
    s._actions([A("RouteToDevice"), A("ResumePlayers")])
    done = []
    s.stop(lambda: done.append(True))
    spin_until(lambda: done)
    assert s.closed
    assert p.calls() == (["Pause", "Play"] if kind == "grab" else ["Pause"])
    assert s.store.value.resume_players is None
    ports.finish()
    drain()
    assert done == [True]
