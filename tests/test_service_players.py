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
    assert s.ctx.held and s.idle_release_at == 0 and ports.calls == ["connect", "route"]
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
    assert ports.calls == ["connect", "restore", "disconnect"]
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
        assert ports.calls == ["inhibitor"]
    spin_until(lambda: "restore" in ports.calls)
    ports.finish()
    before, release_timer = s.ctx, s.timers["RELEASE"]
    s.event(Event("DisconnectResult"))
    assert s.ctx == before and s.timers["RELEASE"] == release_timer
    s.event(Event("DeviceConnected", False))
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
    assert ports.calls == ["route", "restore", "disconnect"]


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
        spin_until(lambda: p.calls() == ["Pause", "Play"])
        assert client("switch").returncode == 0
        spin_until(lambda: str(properties()["State"]) in {"releasing", "released"})
    daemon.send_signal(signal.SIGTERM)
    daemon.wait(timeout=5)
    assert daemon.returncode == 0
    calls = p.calls()
    if kind == "grab":
        assert calls == ["Pause", "Play"]
    else:
        assert calls == ["Pause", "Play", "Pause"]
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


@pytest.mark.parametrize("queue", ["player", "route"])
@pytest.mark.parametrize("failure", ["raise", "double_done", "done_then_raise"])
def test_queue_completes_once_after_adapter_failure(executor, caplog, queue, failure):
    s, _ = executor
    enqueue = s._queue_player if queue == "player" else lambda op: s._queue_route(op, 0)
    prefix, late, tail, calls = [], [], [], []
    enqueue(prefix.append)

    def operation(done):
        calls.append("operation")
        late.append(done)
        if failure != "raise":
            done()
        if failure == "double_done":
            done()
        else:
            raise RuntimeError("adapter failed")

    enqueue(operation)
    enqueue(tail.append)
    enqueue(lambda done: (calls.append("last"), done()))
    prefix[0]()
    assert calls == ["operation"]
    assert getattr(s, "players_done" if queue == "player" else "routes_done") == 2
    assert getattr(s, queue + "_busy")
    late[0]()  # A stale completion cannot finish the next operation.
    assert calls == ["operation"]
    assert getattr(s, "players_done" if queue == "player" else "routes_done") == 2
    assert getattr(s, queue + "_busy")
    tail[0]()
    assert calls == ["operation", "last"]
    assert getattr(s, "players_done" if queue == "player" else "routes_done") == 4
    assert not getattr(s, queue + "_busy")
    if failure != "double_done":
        assert "operation failed (RuntimeError)" in caplog.text


@pytest.mark.parametrize("failure", ["route", "restore", "both"])
def test_error_release_resumes_after_routing_exception(
    executor, player_factory, monkeypatch, failure
):
    s, ports = executor
    p = player_factory("routing_error")
    complete(s.players.pause, "grab")
    s.ctx = Context(state="connecting", origin="self", held=True, device_connected=True)
    late = []

    def routing(name, done):
        ports.calls.append(name)
        late.append(done)
        if failure in {name, "both"}:
            raise RuntimeError("routing failed")
        done()

    monkeypatch.setattr(ports, "route", lambda done: routing("route", done))
    monkeypatch.setattr(ports, "restore", lambda done: routing("restore", done))
    s._execute(A("RouteToDevice"))
    s.event(Event("TimerFired", "CONNECT"))
    spin_until(lambda: not held(s))
    assert p.calls() == ["Pause", "Play"]
    assert ports.calls == ["route", "restore", "disconnect"]
    assert s.ctx.state == "releasing" and not s.ctx.held
    assert s.routes_done == s.routes_added == 2
    assert s.players_done == s.players_added == 1
    assert s.restore_pending == 0 and not s.disconnect_pending
    for done in late:
        done()
    assert s.routes_done == 2 and s.restore_pending == 0
    assert ports.calls == ["route", "restore", "disconnect"]


def test_stop_without_pending_players_is_immediate(executor):
    s, _ = executor
    done = []
    s.stop(lambda: done.append(True))
    assert done == [True] and s.closed
    assert s.stop_source == s.resume_stop_source == 0


def test_sigterm_during_slow_pause(daemon, fake_pactl, tmp_path, player_factory):
    import time

    import dbusmock
    from test_players import PLAYER

    # Each RPC is below T=400 ms. Pending Pause + resume reads/Play exceed 2T.
    config = tmp_path / "config.toml"
    config.write_text(
        config.read_text().replace(
            "player_timeout_ms = 1000", "player_timeout_ms = 400"
        )
    )
    from scambio.api import INTERFACE, PATH

    bus = dbusmock.BusType.SESSION.get_connection()
    bus.get_object("app.scambio.Test", PATH).Reload(dbus_interface=INTERFACE)
    marker = tmp_path / "pause-started"
    p = player_factory(
        "slow_shutdown",
        pause=(
            f"import pathlib, time; pathlib.Path({str(marker)!r}).touch(); "
            f'time.sleep(0.33); self.props["{PLAYER}"]["PlaybackStatus"] = "Paused"'
        ),
        play=(
            "import time; time.sleep(0.33); "
            f'self.props["{PLAYER}"]["PlaybackStatus"] = "Playing"'
        ),
    )
    p.obj.AddMethod(
        "org.freedesktop.DBus.Properties",
        "Get",
        "ss",
        "v",
        "import time; time.sleep(0.33); "
        f'ret = self.props["{PLAYER}"]["PlaybackStatus"]',
        dbus_interface=dbusmock.MOCK_IFACE,
    )
    fake_pactl.update(
        {"streams": [{"index": 7, "sink": 1, "corked": False, "properties": {}}]}
    )
    fake_pactl.event()
    spin_until(marker.exists)
    started = time.monotonic()
    daemon.send_signal(signal.SIGTERM)
    daemon.wait(timeout=5)
    elapsed = time.monotonic() - started
    assert daemon.returncode == 0
    assert 0.8 < elapsed < 1.6
    assert p.calls() == ["Pause", "Play"]
    assert (
        str(
            p.obj.Get(
                PLAYER,
                "PlaybackStatus",
                dbus_interface="org.freedesktop.DBus.Properties",
            )
        )
        == "Playing"
    )
    assert json.loads((tmp_path / "state.json").read_text())["resume_players"] is None


def test_stop_starts_resume_budget_after_current_operation(executor, monkeypatch):
    from gi.repository import GLib

    s, _ = executor
    current, resumed, timers, removed = [], [], [], []

    def timeout(milliseconds, callback):
        timers.append((milliseconds, callback))
        return len(timers)

    monkeypatch.setattr(GLib, "timeout_add", timeout)
    monkeypatch.setattr(GLib, "source_remove", removed.append)
    monkeypatch.setattr(s.players, "shutdown", resumed.append)
    s._queue_player(current.append)
    done = []
    s.stop(lambda: done.append(True))
    timeout_ms = s.config.backend.player_timeout_ms
    assert [ms for ms, _ in timers] == [4 * timeout_ms]
    assert resumed == [] and done == []
    current[0]()
    assert [ms for ms, _ in timers] == [4 * timeout_ms, 2 * timeout_ms]
    assert len(resumed) == 1 and done == []
    resumed[0]()
    resumed[0]()
    assert done == [True] and removed == [1, 2]
    assert s.players_done == s.players_added == 2
    assert not s.player_busy


def test_double_switch_with_early_disconnect_reply(
    bluez_server, fake_pactl, tmp_path, player_factory, monkeypatch
):
    import dbus
    import dbusmock
    from helpers import SINK

    from scambio.core.audio import Audio
    from scambio.core.bluez import DEVICE, BlueZ
    from scambio.core.session import Session

    device = dbusmock.BusType.SYSTEM.get_connection().get_object(
        "org.bluez", bluez_server[1]
    )
    device.UpdateProperties(
        DEVICE, {"Connected": dbus.Boolean(True)}, dbus_interface=dbusmock.MOCK_IFACE
    )
    # Replies are immediate; the test emits the property changes independently.
    for method in ("Disconnect", "Connect"):
        device.AddMethod(
            DEVICE, method, "", "", "pass", dbus_interface=dbusmock.MOCK_IFACE
        )
    fake_pactl.add_sink()
    fake_pactl.update(
        {"streams": [{"index": 7, "sink": 2, "corked": False, "properties": {}}]}
    )
    p = player_factory("double_switch")
    bus, system = gio_bus(Gio.BusType.SESSION), gio_bus(Gio.BusType.SYSTEM)
    config = Config(device=Device(ADDRESS), policy=Policy(resume_delay_ms=50))
    store = Store(tmp_path / "state.json")
    bluetooth_events = []

    def factory(emit):
        def bluetooth_event(event):
            bluetooth_events.append(event)
            emit(event)

        return (
            BlueZ(system, config, bluetooth_event),
            Audio(config, store, emit, fake_pactl.command),
            Session(system, bus, config, emit),
        )

    s = Service(bus, config, store, tmp_path / "config.toml", factory)
    actions, play_destinations = [], []
    execute, call = s._execute, s.players._call

    def observed_action(action, release_barrier=0):
        actions.append(action)
        execute(action, release_barrier)

    def observed_call(name, path, interface, method, params, done, *args, **kwargs):
        if method == "Play":
            play_destinations.append((s.ctx.state, fake_pactl.read()["default"]))
        call(name, path, interface, method, params, done, *args, **kwargs)

    monkeypatch.setattr(s, "_execute", observed_action)
    monkeypatch.setattr(s.players, "_call", observed_call)

    def device_calls():
        return [
            str(c[1])
            for c in device.GetCalls(dbus_interface=dbusmock.MOCK_IFACE)
            if str(c[1]) in {"Disconnect", "Connect"}
        ]

    try:
        assert s.start()
        spin_until(lambda: s.ctx.state == "on_pc" and not s.audio.routing_busy)
        assert fake_pactl.read()["default"] == SINK
        assert p.calls() == [] and s.ctx.audio_active
        bluetooth_events.clear()
        actions.clear()
        s.event(Event("Switch"))
        release_timer = s.timers["RELEASE"]
        s.event(Event("Switch"))
        spin_until(lambda: Event("DisconnectResult") in bluetooth_events)
        assert bluetooth_events == [Event("DisconnectResult")]
        assert (s.ctx.state, s.ctx.pending, s.ctx.device_connected, s.ctx.held) == (
            "releasing",
            "grab",
            True,
            True,
        )
        assert s.timers["RELEASE"] == release_timer
        assert s.ctx.last_error == "" and not s.ctx.blocked_until_silence
        assert device_calls() == ["Disconnect"] and p.calls() == ["Pause"]
        assert store.value.resume_players is None

        fake_pactl.update({"streams": [], "sinks": fake_pactl.read()["sinks"][:1]})
        fake_pactl.event()
        spin_until(lambda: not s.ctx.audio_active and not s.ctx.sink_ready)
        device.UpdateProperties(
            DEVICE,
            {"Connected": dbus.Boolean(False)},
            dbus_interface=dbusmock.MOCK_IFACE,
        )
        spin_until(lambda: Event("ConnectResult") in bluetooth_events)
        spin_until(lambda: store.value.resume_players is not None)
        assert bluetooth_events == [
            Event("DisconnectResult"),
            Event("DeviceConnected", False),
            Event("ConnectResult"),
        ]
        assert (s.ctx.state, s.ctx.pending, s.ctx.origin, s.ctx.held) == (
            "connecting",
            "none",
            "self",
            True,
        )
        assert "RELEASE" not in s.timers
        assert s.ctx.last_error == "" and not s.ctx.blocked_until_silence
        assert device_calls() == ["Disconnect", "Connect"]
        assert p.calls() == ["Pause"] and play_destinations == []

        device.UpdateProperties(
            DEVICE,
            {"Connected": dbus.Boolean(True)},
            dbus_interface=dbusmock.MOCK_IFACE,
        )
        fake_pactl.add_sink()
        fake_pactl.event()
        spin_until(lambda: not held(s) and p.calls() == ["Pause", "Play"])
        assert (s.ctx.state, s.ctx.origin, s.ctx.reason, s.ctx.last_error) == (
            "on_pc",
            "self",
            "switch",
            "",
        )
        assert not s.ctx.held and not s.ctx.blocked_until_silence
        assert store.value.resume_players is None
        assert device_calls() == ["Disconnect", "Connect"]
        assert play_destinations == [("on_pc", SINK)]
        assert [
            a
            for a in actions
            if a.kind
            in {
                "PausePlayers",
                "ResumePlayers",
                "ForgetPlayers",
                "Connect",
                "Disconnect",
                "RouteToDevice",
                "RestoreRouting",
                "EmitTransition",
                "EmitError",
            }
        ] == [
            A("PausePlayers", "release"),
            A("RestoreRouting"),
            A("Disconnect"),
            A("EmitTransition", transition=("on_pc", "releasing", "switch")),
            A("PausePlayers", "grab"),
            A("Connect"),
            A("EmitTransition", transition=("releasing", "connecting", "switch")),
            A("RouteToDevice"),
            A("EmitTransition", transition=("connecting", "on_pc", "switch")),
            A("ResumePlayers"),
        ]
    finally:
        s.close()
        drain()
