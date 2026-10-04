"""One GLib loop: policy executor, public D-Bus service and lifecycle."""

import logging
import signal
from collections import deque
from collections.abc import Callable, Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

from gi.repository import Gio, GLib

from scambio import __version__
from scambio.api import BUS_NAME, INTERFACE, PATH, introspection_xml
from scambio.config import Config, ConfigInvalid, config_path, load
from scambio.core.audio import Audio
from scambio.core.bluez import BlueZ
from scambio.core.policy import Action, Context, Event, step
from scambio.core.ports import AudioPort, BluetoothPort, Emit, SessionPort
from scambio.core.session import Session
from scambio.state import Store

LOG = logging.getLogger(__name__)
Schedule = Callable[[int, Callable[[], bool]], int]
Factory = Callable[[Emit], tuple[BluetoothPort, AudioPort, SessionPort]]


def schedule(milliseconds: int, callback: Callable[[], bool]) -> int:
    if milliseconds >= 1000 and milliseconds % 1000 == 0:
        return int(GLib.timeout_add_seconds(milliseconds // 1000, callback))
    return int(GLib.timeout_add(milliseconds, callback))


class Service:
    def __init__(
        self,
        bus: Gio.DBusConnection,
        config: Config,
        store: Store,
        config_file: Path,
        factory: Factory,
        timer: Schedule = schedule,
    ) -> None:
        self.bus, self.config, self.store = bus, config, store
        self.config_file, self.schedule = config_file, timer
        self.ctx = Context(priority=store.value.iphone_priority)
        self.bluez, self.audio, self.session = factory(self.event)
        self.timers: dict[str, int] = {}
        self.idle_release_at = 0
        self.name = ""
        self.closed = False
        self.initialized = False
        self.repairing = False
        self.initial: dict[str, Event] = {}
        self.events: deque[Event] = deque()
        self.processing = False
        self.restore_pending = 0
        self.disconnect_pending = False
        self.registration = 0
        self.owned = False
        self.signals: list[int] = []
        self.info = Gio.DBusNodeInfo.new_for_xml(introspection_xml()).interfaces[0]
        self.published: dict[str, GLib.Variant] = {}

    def start(self) -> bool:
        # Claim before touching adapters; a duplicate instance has no side effects.
        result = self.bus.call_sync(
            "org.freedesktop.DBus",
            "/org/freedesktop/DBus",
            "org.freedesktop.DBus",
            "RequestName",
            GLib.Variant("(su)", (BUS_NAME, 4)),
            GLib.VariantType.new("(u)"),
            Gio.DBusCallFlags.NONE,
            self.config.backend.dbus_timeout_seconds * 1000,
            None,
        )
        if result.unpack()[0] != 1:
            LOG.error("Scambio is already running")
            return False
        self.owned = True
        self.registration = self.bus.register_object(
            PATH, self.info, self._method, self._get, None
        )
        self._publish()
        if not self.config.device.address:
            self._error("device_not_configured", "Configure device.address")
        self.session.start()
        self.bluez.start()
        self.audio.start()
        return True

    def event(self, event: Event) -> None:
        if self.closed:
            return
        if not self.initialized and event.kind in {"Switch", "SetPriority"}:
            self.ctx, actions = step(self.ctx, event, self.config.policy)
            for action in actions:
                self._execute(action)
            self._publish()
            return
        if not self.initialized:
            key = (
                "DeviceSink"
                if event.kind in {"DeviceSinkGone", "DeviceSinkAppeared"}
                else event.kind
            )
            self.initial[key] = event
            if not (self.bluez.ready and self.audio.ready and self.session.ready):
                return
            if self.repairing:
                return
            if self.store.value.restore_default_sink and not self.bluez.connected:
                self.repairing = True
                self.audio.restore(self._initialize)
            else:
                self._initialize()
            return
        self.events.append(event)
        if self.processing:
            return
        self.processing = True
        try:
            while self.events and not self.closed:
                current = self.events.popleft()
                if current.kind == "DeviceName":
                    self.name = str(current.value)
                else:
                    before = self.ctx
                    self.ctx, actions = step(self.ctx, current, self.config.policy)
                    if before == self.ctx and not actions:
                        LOG.debug("Ignored event %s in %s", current, self.ctx.state)
                    for action in actions:
                        self._execute(action)
                self._publish()
        finally:
            self.processing = False

    def _initialize(self) -> None:
        if self.closed:
            return
        self.initialized = True
        # Lock and sleep are known before availability can trigger an adoption/grab.
        for key in (
            "Locked",
            "Sleep",
            "AudioBackend",
            "DeviceName",
            "DeviceSink",
            "AudioActive",
            "DeviceConnected",
            "Availability",
        ):
            if key in self.initial:
                self.event(self.initial[key])
        self.initial.clear()

    def _execute(self, action: Action) -> None:
        kind, value = action.kind, str(action.value)
        if kind == "Connect":
            self.disconnect_pending = False
            self.bluez.connect()
        elif kind == "Disconnect":
            if self.restore_pending:
                self.disconnect_pending = True
            else:
                self.bluez.disconnect()
        elif kind == "RouteToDevice":
            self.audio.route(lambda: None)
        elif kind == "RestoreRouting":
            self.restore_pending += 1

            def restored() -> None:
                self.restore_pending -= 1
                if not self.restore_pending and self.disconnect_pending:
                    self.disconnect_pending = False
                    if not self.closed and self.ctx.state == "releasing":
                        self.bluez.disconnect()

            self.audio.restore(restored)
        elif kind == "StartTimer":
            self._cancel_timer(value)
            if value == "IDLE":
                self.idle_release_at = GLib.get_real_time() + action.milliseconds * 1000
            source = 0

            def fired() -> bool:
                if self.closed or self.timers.get(value) != source:
                    return False
                self.timers.pop(value, None)
                if value == "IDLE":
                    self.idle_release_at = 0
                self.event(Event("TimerFired", value))
                return False

            source = self.schedule(action.milliseconds, fired)
            self.timers[value] = source
        elif kind == "CancelTimer":
            self._cancel_timer(value)
        elif kind == "SavePriority":
            self.store.value.iphone_priority = bool(action.value)
            try:
                self.store.save()
            except OSError as exc:
                LOG.error("Cannot save priority: %s", exc)
        elif kind == "ReleaseSleepInhibitor":
            self.session.release_inhibitor()
        elif kind == "EmitError":
            self._signal("Error", GLib.Variant("(ss)", (value, value)))
        elif kind == "EmitTransition":
            LOG.info("Transition %s -> %s (%s)", *action.transition)
            self._signal("Transition", GLib.Variant("(sss)", action.transition))

    def _cancel_timer(self, name: str) -> None:
        source = self.timers.pop(name, None)
        if source:
            GLib.source_remove(source)
        if name == "IDLE":
            self.idle_release_at = 0

    def _error(self, code: str, detail: str) -> None:
        self.ctx = replace(self.ctx, last_error=code)
        self._signal("Error", GLib.Variant("(ss)", (code, detail)))
        self._publish()

    def _signal(self, name: str, params: GLib.Variant) -> None:
        if self.registration:
            self.bus.emit_signal(None, PATH, INTERFACE, name, params)

    def properties(self) -> dict[str, GLib.Variant]:
        values: dict[str, str | bool | int] = {
            "State": self.ctx.state,
            "IphonePriority": self.ctx.priority,
            "AudioActive": self.ctx.audio_active,
            "Locked": self.ctx.locked,
            "DeviceAddress": self.config.device.address,
            "DeviceName": self.name,
            "DeviceConnected": self.ctx.device_connected,
            "IdleReleaseAt": self.idle_release_at,
            "LastError": self.ctx.last_error,
            "Version": __version__,
        }
        return {
            p.name: GLib.Variant(p.signature, values[p.name])
            for p in self.info.properties
        }

    def _publish(self) -> None:
        values = self.properties()
        changed = {k: v for k, v in values.items() if self.published.get(k) != v}
        self.published = values
        if changed and self.registration:
            self.bus.emit_signal(
                None,
                PATH,
                "org.freedesktop.DBus.Properties",
                "PropertiesChanged",
                GLib.Variant("(sa{sv}as)", (INTERFACE, changed, [])),
            )

    def _get(self, *args: Any) -> GLib.Variant:
        return self.properties()[args[4]]

    def _method(
        self,
        connection: Gio.DBusConnection,
        sender: str,
        path: str,
        interface: str,
        method: str,
        params: GLib.Variant,
        invocation: Gio.DBusMethodInvocation,
    ) -> None:
        try:
            if method == "Switch":
                unavailable = self.ctx.state == "unavailable"
                self.event(Event("Switch"))
                if unavailable:
                    invocation.return_dbus_error(
                        INTERFACE + ".Error.DeviceUnavailable", "Device unavailable"
                    )
                    return
                invocation.return_value(GLib.Variant("(s)", (self.ctx.state,)))
            elif method == "SetPriority":
                self.event(Event("SetPriority", params.unpack()[0]))
                invocation.return_value(None)
            elif method == "Reload":
                self.reload()
                invocation.return_value(None)
        except ConfigInvalid as exc:
            invocation.return_dbus_error(INTERFACE + ".Error.ConfigInvalid", str(exc))
        except RestartRequired as exc:
            invocation.return_dbus_error(INTERFACE + ".Error.RestartRequired", str(exc))

    def reload(self) -> None:
        try:
            config = load(self.config_file)
        except ConfigInvalid as exc:
            self._error("config_invalid", str(exc))
            raise
        if config.device.address != self.config.device.address:
            raise RestartRequired("Changing device.address requires a restart")
        self.config = config
        self.bluez.reload(config)
        self.session.reload(config)
        self.audio.reload(config)
        self._publish()

    def close(self) -> None:
        self.closed = True
        for name in tuple(self.timers):
            self._cancel_timer(name)
        for source in self.signals:
            GLib.source_remove(source)
        self.signals.clear()
        self.session.close()
        self.bluez.close()
        self.audio.close()
        if self.registration:
            self.bus.unregister_object(self.registration)
            self.registration = 0
        if self.owned:
            self.bus.call_sync(
                "org.freedesktop.DBus",
                "/org/freedesktop/DBus",
                "org.freedesktop.DBus",
                "ReleaseName",
                GLib.Variant("(s)", (BUS_NAME,)),
                None,
                Gio.DBusCallFlags.NONE,
                self.config.backend.dbus_timeout_seconds * 1000,
                None,
            )
            self.owned = False


class RestartRequired(ValueError):
    """Reload would change the configured device identity."""


def run(
    config_file: Path | None = None,
    state_file: Path | None = None,
    pactl: Sequence[str] = ("pactl",),
    timer: Schedule = schedule,
) -> int:
    config_file = config_file or config_path()
    try:
        config = load(config_file)
    except ConfigInvalid as exc:
        LOG.error("Invalid configuration: %s", exc)
        return 1
    store = Store(state_file)
    store.load()
    system = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)

    def factory(emit: Emit) -> tuple[BluetoothPort, AudioPort, SessionPort]:
        return (
            BlueZ(system, config, emit),
            Audio(config, store, emit, pactl),
            Session(system, bus, config, emit),
        )

    service = Service(bus, config, store, config_file, factory, timer)
    loop = GLib.MainLoop()
    if not service.start():
        service.close()
        return 1

    def stop() -> bool:
        loop.quit()
        return True

    def reload_config() -> bool:
        try:
            service.reload()
        except (ConfigInvalid, RestartRequired) as exc:
            LOG.warning("Reload rejected: %s", exc)
        return True

    service.signals = [
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signum, callback)
        for signum, callback in (
            (signal.SIGTERM, stop),
            (signal.SIGINT, stop),
            (signal.SIGHUP, reload_config),
        )
    ]
    try:
        loop.run()  # type: ignore[no-untyped-call]  # PyGObject 3.48 stub
    finally:
        service.close()
    return 0
