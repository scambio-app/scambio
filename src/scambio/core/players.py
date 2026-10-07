# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Fermich srl
"""On-demand MPRIS control. No subscriptions, subprocesses or periodic work."""

from collections.abc import Callable
from functools import partial
from typing import Literal

from gi.repository import Gio, GLib

from scambio.config import Config
from scambio.core.ports import Done
from scambio.core.transport import BusClient
from scambio.state import PlayerRef, ResumePlayers, Store
from scambio.text import logger

LOG = logger(__name__)
PREFIX = "org.mpris.MediaPlayer2."
PATH = "/org/mpris/MediaPlayer2"
PLAYER = "org.mpris.MediaPlayer2.Player"
DBUS = "org.freedesktop.DBus"
Kind = Literal["grab", "release"]
Reply = str | tuple[str, ...] | None


def decode_reply(raw: object, method: str) -> Reply:
    """Narrow unpacked Gio values at the transport boundary, without coercion."""
    if not isinstance(raw, tuple):
        raise ValueError("invalid reply envelope")
    if method in {"Pause", "Play"}:
        if raw:
            raise ValueError("expected empty reply")
        return None
    if len(raw) != 1:
        raise ValueError("expected one reply value")
    value: object = raw[0]
    if method == "ListNames":
        if not isinstance(value, (list, tuple)):
            raise ValueError("expected name array")
        names: list[str] = []
        for name in value:
            if not isinstance(name, str):
                raise ValueError("expected bus name string")
            names.append(name)
        return tuple(names)
    if not isinstance(value, str):
        raise ValueError("expected string reply")
    return value


class Players:
    def __init__(self, bus: Gio.DBusConnection, config: Config, store: Store) -> None:
        self.bus, self.config, self.store = bus, config, store
        self.held: dict[PlayerRef, Kind] = {}
        self.bus_id = ""
        self.clients: set[BusClient] = set()
        self.operations: set[Done] = set()
        self.closed = False

    def reload(self, config: Config) -> None:
        self.config = config

    def _completion(self, done: Done) -> Done:
        finished = False

        def complete() -> None:
            nonlocal finished
            if finished:
                return
            finished = True
            self.operations.discard(complete)
            done()

        self.operations.add(complete)
        return complete

    def _call(
        self,
        name: str,
        path: str,
        interface: str,
        method: str,
        params: GLib.Variant | None,
        done: Callable[[Reply, str], None],
        timeout_ms: int | None = None,
        *,
        player: str | None = None,
    ) -> None:
        if self.closed:
            done(None, "closed")
            return
        client = BusClient(
            self.bus, name, timeout_ms or self.config.backend.player_timeout_ms
        )
        self.clients.add(client)

        def finish(raw: object, error: str) -> None:
            self.clients.discard(client)
            client.close()
            if self.closed:
                done(None, "closed")
                return
            reply: Reply = None
            if not error:
                try:
                    reply = decode_reply(raw, method)
                except ValueError:
                    error = "invalid_reply"
            if error:
                # Remote errors and malformed replies may contain titles or URLs.
                LOG.warning(
                    "MPRIS %s failed for %s", method, player or "player discovery"
                )
            done(reply, error)

        client.call(path, interface, method, params, finish)

    def _daemon(
        self,
        method: str,
        params: GLib.Variant | None,
        done: Callable[[Reply, str], None],
        timeout_ms: int | None = None,
        *,
        player: str | None = None,
    ) -> None:
        self._call(
            DBUS,
            "/org/freedesktop/DBus",
            DBUS,
            method,
            params,
            done,
            timeout_ms,
            player=player,
        )

    def _identity(self, done: Done) -> None:
        if self.closed or self.bus_id:
            done()
            return

        def received(reply: Reply, error: str) -> None:
            if not self.closed and not error and isinstance(reply, str):
                self.bus_id = reply
            done()

        self._daemon("GetId", None, received)

    def _save(self) -> None:
        if self.closed:
            return
        if not self.bus_id:
            # Empty startup/shutdown has nothing to persist and needs no identity.
            # Keep the warning when actual recovery data would be at risk.
            if self.held or self.store.value.resume_players is not None:
                LOG.warning(
                    "Cannot update resume_players without a session bus identity"
                )
            return
        refs = tuple(ref for ref, kind in self.held.items() if kind == "grab")
        value = ResumePlayers(self.bus_id, refs) if refs else None
        if value == self.store.value.resume_players:
            return
        self.store.value.resume_players = value
        try:
            self.store.save()
        except OSError as exc:
            LOG.warning("Cannot save held players: %s", exc)

    def _read(
        self,
        name: str,
        owner: str | None,
        done: Callable[[str, str], None],
        deadline: int,
    ) -> None:
        if self.closed:
            done("", "")
            return
        remaining = (deadline - GLib.get_monotonic_time() + 999) // 1000
        if remaining <= 0:
            LOG.warning("MPRIS read deadline expired for %s", name)
            done("", "")
            return
        # Commands target the unique owner, never a replacement process.
        values: dict[str, str] = {}

        def received(key: str, reply: Reply, error: str) -> None:
            if self.closed:
                done("", "")
                return
            values[key] = reply if not error and isinstance(reply, str) else ""
            if len(values) == 2:
                done(values["owner"], values["status"])

        self._daemon(
            "GetNameOwner",
            GLib.Variant("(s)", (name,)),
            lambda reply, err: received("owner", reply, err),
            remaining,
            player=name,
        )
        self._call(
            owner or name,
            PATH,
            "org.freedesktop.DBus.Properties",
            "Get",
            GLib.Variant("(ss)", (PLAYER, "PlaybackStatus")),
            lambda reply, err: received("status", reply, err),
            remaining,
            player=name,
        )

    def _read_deadline(self) -> int:
        return (
            int(GLib.get_monotonic_time())
            + self.config.backend.player_timeout_ms * 1000
        )

    def pause(self, kind: Kind, done: Done) -> None:
        if self.closed:
            done()
            return
        completed = self._completion(done)

        def finish_operation() -> None:
            self._save()
            completed()

        done = finish_operation
        deadline = self._read_deadline()
        self.held = dict.fromkeys(self.held, kind)
        # Discovery shares the read budget; no additional watchdog or idle work.
        candidates: tuple[str, ...] | None = None
        identity_ready = False
        reserved: set[PlayerRef] = set()

        def ready() -> None:
            if self.closed:
                done()
                return
            if candidates is None or not identity_ready:
                return
            names = [
                name
                for name in candidates
                if name.startswith(PREFIX)
                and name[len(PREFIX) :].split(".", 1)[0].casefold()
                not in self.config.audio.ignore_players
            ]
            held_names = {ref.name for ref in self.held}
            room = max(0, self.config.backend.player_max_count - len(self.held))
            names = [name for name in names if name in held_names] + [
                name for name in names if name not in held_names
            ][:room]
            pending = len(names)
            if not pending:
                done()
                return

            def finished() -> None:
                nonlocal pending
                pending -= 1
                if not pending:
                    done()

            def read(name: str, owner: str, status: str) -> None:
                if self.closed:
                    done()
                    return
                if not owner or status != "Playing":
                    finished()
                    return
                ref = PlayerRef(name, owner)
                if ref not in self.held:
                    if (
                        len(self.held) + len(reserved)
                        >= self.config.backend.player_max_count
                    ):
                        finished()
                        return
                    reserved.add(ref)

                def paused(reply: Reply, error: str) -> None:
                    reserved.discard(ref)
                    if self.closed:
                        done()
                        return
                    if not error:
                        self.held[ref] = kind
                        LOG.info("Paused player %s", name)
                    finished()

                self._call(owner, PATH, PLAYER, "Pause", None, paused, player=name)

            for name in names:
                self._read(name, None, partial(read, name), deadline)

        def listed(reply: Reply, error: str) -> None:
            nonlocal candidates
            if self.closed:
                done()
                return
            if not error and isinstance(reply, tuple):
                candidates = reply
            else:
                candidates = ()
                if not error:
                    LOG.warning("MPRIS ListNames returned an invalid name array")
            ready()

        def identified() -> None:
            nonlocal identity_ready
            identity_ready = True
            ready()

        self._identity(identified)
        self._daemon("ListNames", None, listed)

    def resume(self, done: Done, *, deadline: int | None = None) -> None:
        if self.closed:
            done()
            return
        done = self._completion(done)
        deadline = deadline if deadline is not None else self._read_deadline()
        pending = len(self.held)
        if not pending:
            self.forget(done)
            return

        def finished() -> None:
            nonlocal pending
            pending -= 1
            if not pending:
                self.forget(done)

        def read(ref: PlayerRef, owner: str, status: str) -> None:
            if self.closed:
                done()
                return
            if owner != ref.owner or status not in {"Paused", "Playing"}:
                finished()
                return

            def played(reply: Reply, error: str) -> None:
                if self.closed:
                    done()
                    return
                if not error:
                    LOG.info("Resumed player %s", ref.name)
                finished()

            self._call(ref.owner, PATH, PLAYER, "Play", None, played, player=ref.name)

        for ref in tuple(self.held):
            self._read(ref.name, ref.owner, partial(read, ref), deadline)

    def forget(self, done: Done) -> None:
        if not self.closed:
            self.held.clear()
            self._save()
        done()

    def recover(self, done: Done) -> None:
        if self.closed:
            done()
            return
        done = self._completion(done)
        deadline = self._read_deadline()
        saved = self.store.value.resume_players
        if saved is None:
            done()
            return

        def identified() -> None:
            if self.closed:
                done()
            elif not self.bus_id:
                LOG.warning(
                    "Cannot recover resume_players without a session bus identity"
                )
                done()
            elif saved.bus_id == self.bus_id:
                self.held = dict.fromkeys(saved.players, "grab")
                self.resume(done, deadline=deadline)
            else:
                self.forget(done)

        self._identity(identified)

    def shutdown(self, done: Done) -> None:
        if self.closed:
            done()
            return
        self.held = {ref: kind for ref, kind in self.held.items() if kind == "grab"}
        self.resume(done)

    def close(self) -> None:
        self.closed = True
        for client in tuple(self.clients):
            client.close()
        self.clients.clear()
        for done in tuple(self.operations):
            done()
