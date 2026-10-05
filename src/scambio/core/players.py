"""On-demand MPRIS control. No subscriptions, subprocesses or periodic work."""

import logging
from collections.abc import Callable
from functools import partial
from typing import Any, Literal

from gi.repository import Gio, GLib

from scambio.config import Config
from scambio.core.ports import Done
from scambio.core.transport import BusClient
from scambio.state import PlayerRef, ResumePlayers, Store

LOG = logging.getLogger(__name__)
PREFIX = "org.mpris.MediaPlayer2."
PATH = "/org/mpris/MediaPlayer2"
PLAYER = "org.mpris.MediaPlayer2.Player"
DBUS = "org.freedesktop.DBus"
Kind = Literal["grab", "release"]


class Players:
    def __init__(self, bus: Gio.DBusConnection, config: Config, store: Store) -> None:
        self.bus, self.config, self.store = bus, config, store
        self.held: dict[PlayerRef, Kind] = {}
        self.bus_id = ""
        self.clients: set[BusClient] = set()
        self.closed = False

    def reload(self, config: Config) -> None:
        self.config = config

    def _call(
        self,
        name: str,
        path: str,
        interface: str,
        method: str,
        params: GLib.Variant | None,
        done: Callable[[Any, str], None],
        timeout_ms: int | None = None,
    ) -> None:
        client = BusClient(
            self.bus, name, timeout_ms or self.config.backend.player_timeout_ms
        )
        self.clients.add(client)

        def finish(reply: Any, error: str) -> None:
            self.clients.discard(client)
            client.close()
            if error:
                LOG.warning("MPRIS %s failed for %s: %s", method, name, error)
            done(reply, error)

        client.call(path, interface, method, params, finish)

    def _daemon(
        self,
        method: str,
        params: GLib.Variant | None,
        done: Callable[[Any, str], None],
        timeout_ms: int | None = None,
    ) -> None:
        self._call(
            DBUS, "/org/freedesktop/DBus", DBUS, method, params, done, timeout_ms
        )

    def _identity(self, done: Done) -> None:
        if self.bus_id:
            done()
            return

        def received(reply: Any, error: str) -> None:
            if not error:
                self.bus_id = str(reply[0])
            done()

        self._daemon("GetId", None, received)

    def _save(self) -> None:
        refs = tuple(ref for ref, kind in self.held.items() if kind == "grab")
        value = ResumePlayers(self.bus_id, refs) if refs and self.bus_id else None
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
        remaining = (deadline - GLib.get_monotonic_time() + 999) // 1000
        if remaining <= 0:
            LOG.warning("MPRIS read deadline expired for %s", name)
            done("", "")
            return
        # Read owner and status concurrently. Commands target the unique owner,
        # never a replacement that acquires the well-known name in the meantime.
        values: dict[str, str] = {}

        def received(key: str, reply: Any, error: str) -> None:
            values[key] = str(reply[0]) if not error else ""
            if len(values) == 2:
                done(values["owner"], values["status"])

        self._daemon(
            "GetNameOwner",
            GLib.Variant("(s)", (name,)),
            lambda reply, err: received("owner", reply, err),
            remaining,
        )
        self._call(
            owner or name,
            PATH,
            "org.freedesktop.DBus.Properties",
            "Get",
            GLib.Variant("(ss)", (PLAYER, "PlaybackStatus")),
            lambda reply, err: received("status", reply, err),
            remaining,
        )

    def _read_deadline(self) -> int:
        return (
            int(GLib.get_monotonic_time())
            + self.config.backend.player_timeout_ms * 1000
        )

    def pause(self, kind: Kind, done: Done) -> None:
        deadline = self._read_deadline()
        self.held = dict.fromkeys(self.held, kind)
        self._save()
        # Discovery shares the read budget; no additional watchdog or idle work.
        discovery: dict[str, object] = {}

        def ready() -> None:
            if len(discovery) != 2:
                return
            names = discovery["names"]
            assert isinstance(names, list)
            candidates = [
                str(name)
                for name in names
                if str(name).startswith(PREFIX)
                and str(name)[len(PREFIX) :].split(".", 1)[0].casefold()
                not in self.config.audio.ignore_players
            ]
            pending = len(candidates)
            if not pending:
                done()
                return

            def finished() -> None:
                nonlocal pending
                pending -= 1
                if not pending:
                    done()

            def read(name: str, owner: str, status: str) -> None:
                if not owner or status != "Playing":
                    finished()
                    return
                ref = PlayerRef(name, owner)

                def paused(reply: Any, error: str) -> None:
                    if not error:
                        self.held[ref] = kind
                        self._save()
                        LOG.info("Paused player %s", name)
                    finished()

                self._call(owner, PATH, PLAYER, "Pause", None, paused)

            for name in candidates:
                self._read(name, None, partial(read, name), deadline)

        def names(reply: Any, error: str) -> None:
            discovery["names"] = [] if error else reply[0]
            ready()

        def identified() -> None:
            discovery["id"] = self.bus_id
            ready()

        self._identity(identified)
        self._daemon("ListNames", None, names)

    def resume(self, done: Done, *, deadline: int | None = None) -> None:
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
            if owner != ref.owner or status not in {"Paused", "Playing"}:
                finished()
                return

            def played(reply: Any, error: str) -> None:
                if not error:
                    LOG.info("Resumed player %s", ref.name)
                finished()

            self._call(ref.owner, PATH, PLAYER, "Play", None, played)

        for ref in tuple(self.held):
            self._read(ref.name, ref.owner, partial(read, ref), deadline)

    def forget(self, done: Done) -> None:
        self.held.clear()
        self._save()
        done()

    def recover(self, done: Done) -> None:
        deadline = self._read_deadline()
        saved = self.store.value.resume_players
        if saved is None:
            done()
            return

        def identified() -> None:
            if saved.bus_id == self.bus_id:
                self.held = dict.fromkeys(saved.players, "grab")
                self.resume(done, deadline=deadline)
            else:
                self.forget(done)

        self._identity(identified)

    def shutdown(self, done: Done) -> None:
        self.held = {ref: kind for ref, kind in self.held.items() if kind == "grab"}
        self.resume(done)

    def close(self) -> None:
        self.closed = True
        for client in tuple(self.clients):
            client.close()
        self.clients.clear()
