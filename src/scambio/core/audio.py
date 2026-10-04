"""Pulse events via async Gio subprocesses; no work without events or recovery."""

import codecs
import json
import logging
import re
from collections import deque
from collections.abc import Callable, Sequence
from typing import Any

from gi.repository import Gio, GLib

from scambio.config import Config
from scambio.core.policy import Event
from scambio.core.ports import Done, Emit
from scambio.state import Store

LOG = logging.getLogger(__name__)


class JSONStream:
    def __init__(self) -> None:
        self.buffer = ""
        self.decoder = json.JSONDecoder()
        self.utf8 = codecs.getincrementaldecoder("utf-8")()

    def feed(self, data: bytes) -> list[dict[str, Any]]:
        self.buffer += self.utf8.decode(data)
        values = []
        while self.buffer.strip():
            self.buffer = self.buffer.lstrip()
            try:
                value, end = self.decoder.raw_decode(self.buffer)
            except json.JSONDecodeError:
                break
            self.buffer = self.buffer[end:]
            if isinstance(value, dict):
                values.append(value)
        return values


def property_text(props: dict[str, Any], key: str) -> str:
    value = props.get(key, "")
    return value if isinstance(value, str) and value != "(null)" else ""


def active_stream(stream: dict[str, Any], config: Config) -> bool:
    props = stream.get("properties", {})
    return (
        stream.get("corked") is False
        and property_text(props, "media.role").casefold()
        not in config.audio.ignore_roles
        and not any(
            property_text(props, k).casefold() in config.audio.ignore_apps
            for k in ("application.name", "application.process.binary")
        )
    )


class Audio:
    def __init__(
        self, config: Config, store: Store, emit: Emit, pactl: Sequence[str]
    ) -> None:
        if not pactl:
            raise ValueError("An explicit pactl command is required")
        self.config, self.store, self.emit = config, store, emit
        self.pactl = list(pactl)
        self.launcher = Gio.SubprocessLauncher.new(
            Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_SILENCE
        )
        self.launcher.setenv("LC_ALL", "C", True)
        self.children: set[Gio.Subprocess] = set()
        self.subscriber: Gio.Subprocess | None = None
        self.closed = False
        self.ready = False
        self.generation = 0
        self.parser = JSONStream()
        self.coalesce = 0
        self.retry = 0
        self.retry_delay = config.backend.retry_initial_seconds
        self.refresh_running = False
        self.refresh_pending = False
        self.snapshot_waiters: list[Callable[[bool], None]] = []
        self.streams: list[dict[str, Any]] = []
        self.sinks: list[dict[str, Any]] = []
        self.default = ""
        self.sink = ""
        self.last_device_sink = ""
        self.active: bool | None = None
        self.force = True
        self.routing: deque[tuple[bool, Done]] = deque()
        self.routing_busy = False

    def reload(self, config: Config) -> None:
        self.config = config
        self._publish()  # Re-evaluate filters immediately without a subprocess.

    def _spawn(self, args: list[str]) -> Gio.Subprocess:
        child = self.launcher.spawnv(self.pactl + args)
        self.children.add(child)
        return child

    def _run(self, args: list[str], callback: Callable[[str, bool], None]) -> None:
        if self.closed:
            return
        try:
            child = self._spawn(args)
        except GLib.Error:
            callback("", False)
            return

        def finished(process: Gio.Subprocess, result: Gio.AsyncResult) -> None:
            self.children.discard(process)
            try:
                _, output, _ = process.communicate_utf8_finish(result)
                ok = process.get_successful()
            except GLib.Error:
                output, ok = "", False
            if not self.closed:
                callback(output or "", ok)

        child.communicate_utf8_async(None, None, finished)

    def start(self) -> None:
        def version(output: str, ok: bool) -> None:
            match = re.search(r"\b(\d+)(?:\.\d+)+", output)
            if not ok or not match or int(match[1]) < 16:
                self.ready = True
                LOG.error("Install pulseaudio-utils (pactl >= 16)")
                self.emit(Event("AudioBackend", False))
                return
            self._subscribe()

        self._run(["--version"], version)

    def _subscribe(self) -> None:
        self.retry = 0
        if self.closed:
            return
        self.generation += 1
        generation = self.generation
        self.parser = JSONStream()
        self.force = True
        try:
            child = self._spawn(["-f", "json", "subscribe"])
        except GLib.Error:
            self._down(generation)
            return
        self.subscriber = child
        stream = child.get_stdout_pipe()
        assert stream is not None

        def read(source: Gio.InputStream, result: Gio.AsyncResult) -> None:
            try:
                data = source.read_bytes_finish(result).get_data()
            except GLib.Error:
                data = b""
            if self.closed or generation != self.generation:
                return
            if not data:
                self._down(generation)
                return
            for event in self.parser.feed(data):
                if event.get("on") in {"sink-input", "sink", "server"}:
                    self._schedule()
            source.read_bytes_async(65536, GLib.PRIORITY_DEFAULT, None, read)

        def exited(process: Gio.Subprocess, result: Gio.AsyncResult) -> None:
            process.wait_finish(result)
            self.children.discard(process)
            if not self.closed:
                self._down(generation)

        child.wait_async(None, exited)
        stream.read_bytes_async(65536, GLib.PRIORITY_DEFAULT, None, read)
        self.refresh()

    def _down(self, generation: int) -> None:
        if self.closed or generation != self.generation:
            return
        self.generation += 1
        if self.subscriber is not None:
            self.subscriber.force_exit()
            self.subscriber = None
        if self.coalesce:
            GLib.source_remove(self.coalesce)
            self.coalesce = 0
        self.ready = True
        self.emit(Event("AudioBackend", False))
        delay = self.retry_delay
        self.retry_delay = min(delay * 2, self.config.backend.retry_max_seconds)
        LOG.warning("Audio backend down; retry in %s seconds", delay)
        self.retry = GLib.timeout_add_seconds(delay, self._retry)

    def _retry(self) -> bool:
        self._subscribe()
        return False

    def _schedule(self) -> None:
        if self.coalesce:
            GLib.source_remove(self.coalesce)
        self.coalesce = GLib.timeout_add(
            self.config.backend.coalesce_ms, self._coalesced
        )

    def _coalesced(self) -> bool:
        self.coalesce = 0
        self.refresh()
        return False

    def refresh(self, done: Callable[[bool], None] | None = None) -> None:
        if done:
            self.snapshot_waiters.append(done)
        if self.refresh_running:
            self.refresh_pending = True
            return
        self.refresh_running = True
        generation = self.generation
        results: list[str] = []
        waiters, self.snapshot_waiters = self.snapshot_waiters, []
        commands = [
            ["-f", "json", "list", "sink-inputs"],
            ["-f", "json", "list", "sinks"],
            ["get-default-sink"],
        ]

        def finish(ok: bool) -> None:
            self.refresh_running = False
            if generation != self.generation:
                ok = False
            if ok:
                try:
                    streams, sinks = json.loads(results[0]), json.loads(results[1])
                    if not isinstance(streams, list) or not isinstance(sinks, list):
                        raise ValueError("Invalid snapshot")
                    self.streams, self.sinks, self.default = (
                        streams,
                        sinks,
                        results[2].strip(),
                    )
                    self.ready = True
                    self.retry_delay = self.config.backend.retry_initial_seconds
                    if self.force:
                        self.emit(Event("AudioBackend", True))
                    self._publish()
                except (ValueError, TypeError, KeyError):
                    ok = False
            if not ok:
                self._down(generation)
            for waiter in waiters:
                waiter(ok)
            if self.refresh_pending or self.snapshot_waiters:
                self.refresh_pending = False
                self.refresh()

        def part(output: str, ok: bool) -> None:
            if not ok:
                finish(False)
                return
            results.append(output)
            if len(results) == len(commands):
                finish(True)
            else:
                self._run(commands[len(results)], part)

        self._run(commands[0], part)

    def _is_device(self, name: str) -> bool:
        prefix = "bluez_output." + self.config.device.address.replace(":", "_")
        return bool(
            self.config.device.address
            and (
                name == self.sink
                or name == self.last_device_sink
                or name.upper().startswith(prefix.upper())
            )
        )

    def _publish(self) -> None:
        active = any(active_stream(s, self.config) for s in self.streams)
        sink = ""
        for candidate in self.sinks:
            props = candidate.get("properties", {})
            address = property_text(props, "api.bluez5.address")
            name = str(candidate.get("name", ""))
            if self.config.device.address and (
                address.upper() == self.config.device.address
                or (
                    not address
                    and name.upper().startswith(
                        "BLUEZ_OUTPUT." + self.config.device.address.replace(":", "_")
                    )
                )
            ):
                sink = name
                break
        old_sink = self.sink
        self.sink = sink
        if sink:
            self.last_device_sink = sink
        if sink != old_sink or self.force:
            self.emit(
                Event("DeviceSinkAppeared", sink) if sink else Event("DeviceSinkGone")
            )
        if active != self.active or self.force:
            self.active = active
            self.emit(Event("AudioActive", active))
        self.force = False

    def route(self, done: Done) -> None:
        self.routing.append((True, done))
        self._route_next()

    def restore(self, done: Done) -> None:
        self.routing.append((False, done))
        self._route_next()

    def _route_next(self) -> None:
        if self.routing_busy or not self.routing or self.closed:
            return
        self.routing_busy = True
        route, done = self.routing.popleft()

        def complete() -> None:
            if not route:
                self.store.value.restore_default_sink = None
                self._save()
            self.routing_busy = False
            done()
            self._route_next()

        def snapshot(ok: bool) -> None:
            old = self.default
            saved = self.store.value.restore_default_sink
            target = self.sink if route else saved
            names = {str(s.get("name", "")) for s in self.sinks}
            if (
                not ok
                or not target
                or target not in names
                or old == target
                or (not route and not self._is_device(old))
            ):
                complete()
                return
            if route and not saved:
                self.store.value.restore_default_sink = old
                if not self._save():
                    complete()  # Never mutate routing without a durable restore target.
                    return
            old_indices = {s["index"] for s in self.sinks if s.get("name") == old}
            commands = [["set-default-sink", target]] + [
                ["move-sink-input", str(s["index"]), target]
                for s in self.streams
                if s.get("sink") in old_indices
            ]

            def command_finished(output: str, success: bool) -> None:
                if not success:
                    LOG.warning("Audio routing command failed")
                if commands:
                    self._run(commands.pop(0), command_finished)
                else:
                    complete()

            self._run(commands.pop(0), command_finished)

        self.refresh(snapshot)

    def _save(self) -> bool:
        try:
            self.store.save()
            return True
        except OSError as exc:
            LOG.warning("Cannot persist routing state: %s", exc)
            return False

    def close(self) -> None:
        self.closed = True
        self.generation += 1
        for source in (self.coalesce, self.retry):
            if source:
                GLib.source_remove(source)
        self.coalesce = self.retry = 0
        for process in tuple(self.children):
            process.force_exit()
            process.wait_async(None, lambda p, r: p.wait_finish(r))
        self.children.clear()
