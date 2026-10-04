"""Audio audit regressions: every process is the injected fake pactl."""

from dataclasses import replace
from pathlib import Path

import pytest
from gi.repository import GLib
from helpers import ADDRESS, SINK, drain, spin_until

from scambio.config import Config, Device, parse
from scambio.core.audio import Audio, JSONStream
from scambio.core.policy import Event
from scambio.state import Store


@pytest.fixture
def audio(fake_pactl, tmp_path):
    config = Config(device=Device(ADDRESS))
    adapter = Audio(
        config, Store(tmp_path / "state.json"), lambda e: None, fake_pactl.command
    )
    adapter.start()
    spin_until(lambda: adapter.ready)
    try:
        yield adapter
    finally:
        adapter.close()
        drain()


def test_json_invalid_utf8_and_complete_malformed_object():
    parser = JSONStream()
    assert parser.feed(b'{"value":"\xff"}') == [{"value": "\ufffd"}]
    for byte in b'{"value":true,"nested":{"text":"}\\"{"},"items":[null]}':
        result = parser.feed(bytes([byte]))
    assert result == [{"value": True, "nested": {"text": '}"{'}, "items": [None]}]
    with pytest.raises(ValueError):
        parser.feed(b'{"broken":}{"on":"sink"}')


@pytest.mark.parametrize("payload", [b"garbage", b'{"broken":}', b'{"on":[]}'])
def test_subscription_read_exception_recovers(audio, fake_pactl, payload):
    events = []
    audio.emit = events.append
    fake_pactl.event(payload)
    spin_until(lambda: audio.backend_down)
    assert events == [Event("AudioBackend", False)]
    assert audio.retry and audio.subscriber is None
    spin_until(
        lambda: not audio.backend_down and audio.subscriber is not None, seconds=4
    )
    spin_until(lambda: not audio.refresh_running)
    fake_pactl.add_sink()
    fake_pactl.event()
    spin_until(lambda: audio.sink == SINK)


def test_single_retry_full_backoff_and_no_orphan(audio, fake_pactl, monkeypatch):
    events, delays, sources = [], [], []
    audio.emit = events.append
    timeout = GLib.timeout_add_seconds

    def schedule(seconds, callback):
        delays.append(seconds)
        source = timeout(60, callback)  # Advance only through explicit test events.
        sources.append(source)
        return source

    monkeypatch.setattr(GLib, "timeout_add_seconds", schedule)
    fake_pactl.update({"down": True})
    # An already scheduled retry is replaced, never abandoned.
    previous = timeout(60, lambda: False)
    audio.retry = previous
    audio._down(audio.generation)
    assert GLib.MainContext.default().find_source_by_id(previous) is None
    for expected in [1, 2, 4, 8, 16, 30, 30]:
        spin_until(
            lambda: (
                audio.retry != 0 and not audio.refresh_running and not audio.children
            )
        )
        source, generation = audio.retry, audio.generation
        assert delays[-1] == expected
        for _ in range(2):
            audio._down(generation)
            audio.refresh()
        assert audio.retry == source and audio.generation == generation
        assert len(events) == len(delays)
        assert GLib.MainContext.default().find_source_by_id(source) is not None
        for obsolete in sources[:-1]:
            assert GLib.MainContext.default().find_source_by_id(obsolete) is None
        GLib.source_remove(source)
        if len(delays) == 7:
            fake_pactl.update({"down": False})
        audio._retry()
    spin_until(lambda: not audio.refresh_running and audio.retry_delay == 1)
    assert delays == [1, 2, 4, 8, 16, 30, 30]
    assert audio.retry == 0 and len(audio.children) == 1
    pid = int(audio.subscriber.get_identifier())
    subscribers = [c["pid"] for c in fake_pactl.calls() if c["args"][-1] == "subscribe"]
    assert subscribers[-1] == pid
    assert all(not Path(f"/proc/{p}").exists() for p in subscribers[:-1])


@pytest.mark.parametrize("mode", ["snapshot_failed", "disabled"])
def test_restore_preserves_target_without_snapshot(audio, fake_pactl, mode):
    audio.store.value.restore_default_sink = "speakers"
    audio.store.save()
    before = audio.store.path.read_bytes()
    fake_pactl.add_sink()
    fake_pactl.update({"default": SINK})
    if mode == "disabled":
        audio.enabled = False
    else:
        fake_pactl.update({"down": True})
    done = []
    audio.restore(lambda: done.append(True))
    spin_until(lambda: done)
    assert audio.store.value.restore_default_sink == "speakers"
    assert audio.store.path.read_bytes() == before
    assert not audio.routing_busy
    # A subsequent reliable snapshot still performs the saved repair.
    audio.enabled = True
    fake_pactl.update({"down": False})
    if audio.backend_down:
        audio._subscribe()
    spin_until(lambda: not audio.refresh_running)
    audio.restore(lambda: done.append(True))
    spin_until(lambda: len(done) == 2)
    assert fake_pactl.read()["default"] == "speakers"
    assert audio.store.value.restore_default_sink is None


def test_empty_restore_never_writes_state(audio, monkeypatch):
    def unexpected_save():
        pytest.fail("Empty restoration must not write state.json")

    monkeypatch.setattr(audio.store, "save", unexpected_save)
    done = []
    audio.restore(lambda: done.append(True))
    assert done == [True] and not audio.routing_busy
    assert not audio.store.path.exists()


@pytest.mark.parametrize("fault", ["missing_index", "spawn", "completion", "save"])
def test_routing_exception_always_finishes_and_drains_queue(
    audio, fake_pactl, monkeypatch, fault
):
    fake_pactl.add_sink()
    if fault == "missing_index":
        fake_pactl.update({"streams": [{"sink": 1, "corked": False}]})
    if fault == "spawn":
        original = audio._run

        def fail(args, callback):
            if args[0] == "set-default-sink":
                raise RuntimeError("Injected spawn failure")
            original(args, callback)

        monkeypatch.setattr(audio, "_run", fail)
    if fault == "save":

        def save():
            raise RuntimeError("Injected persistence failure")

        monkeypatch.setattr(audio.store, "save", save)
    done = []

    def completed():
        done.append(True)
        if fault == "completion":
            raise RuntimeError("Injected consumer failure")

    audio.route(completed)
    audio.route(completed)
    spin_until(lambda: len(done) == 2)
    assert done == [True, True]
    assert not audio.routing_busy and not audio.routing


@pytest.mark.parametrize(
    "command",
    [
        "-f json list sink-inputs",
        "-f json list sinks",
        "get-default-sink",
        "set-default-sink " + SINK,
        "move-sink-input 3 " + SINK,
    ],
)
def test_command_deadline_reaps_child_and_finishes_queue(audio, fake_pactl, command):
    audio.reload(
        replace(
            audio.config,
            backend=replace(audio.config.backend, command_timeout_seconds=1),
        )
    )
    fake_pactl.add_sink()
    fake_pactl.update(
        {
            "hang_commands": [command],
            "streams": [{"index": 3, "sink": 1, "corked": False}],
        }
    )
    done = []
    audio.route(lambda: done.append(True))
    audio.restore(lambda: done.append(True))
    spin_until(lambda: len(done) == 2, seconds=4)
    assert not audio.routing_busy and not audio.routing
    assert not audio.command_timers
    hung = [c for c in fake_pactl.calls() if " ".join(c["args"]) == command]
    assert hung
    assert all(not Path(f"/proc/{c['pid']}").exists() for c in hung)


def test_command_deadline_configuration():
    assert (
        parse(
            {"backend": {"command_timeout_seconds": 7}}
        ).backend.command_timeout_seconds
        == 7
    )
    for value in [0, -1, True, "10"]:
        with pytest.raises(ValueError):
            parse({"backend": {"command_timeout_seconds": value}})
