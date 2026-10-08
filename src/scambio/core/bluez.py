# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Fermich srl
"""Only the configured, paired BlueZ device is ever acted on."""

from collections.abc import Callable
from typing import Any

from gi.repository import Gio

from scambio.config import Config
from scambio.core.policy import Event
from scambio.core.ports import Emit
from scambio.core.transport import BusClient
from scambio.text import display_text

DEVICE = "org.bluez.Device1"
ADAPTER = "org.bluez.Adapter1"
PROPERTIES = "org.freedesktop.DBus.Properties"
MANAGER = "org.freedesktop.DBus.ObjectManager"
AUDIO_UUIDS = {
    "0000110b-0000-1000-8000-00805f9b34fb",
    "0000111e-0000-1000-8000-00805f9b34fb",
    "00001108-0000-1000-8000-00805f9b34fb",
}


class BlueZ:
    def __init__(self, bus: Gio.DBusConnection, config: Config, emit: Emit) -> None:
        self.config, self.emit = config, emit
        self.client = BusClient(
            bus, "org.bluez", config.backend.dbus_timeout_seconds * 1000
        )
        self.objects: dict[str, Any] = {}
        self.path = ""
        self.name = ""
        self.raw_name = ""
        self.connected = False
        self.available = False
        self.ready = False
        self.generation = 0
        self.operation = 0
        self.loading = False
        self.queued: list[tuple[str, tuple[Any, ...]]] = []

    def reload(self, config: Config) -> None:
        self.config = config
        self.client.timeout_ms = config.backend.dbus_timeout_seconds * 1000

    def start(self) -> None:
        self.client.subscribe(MANAGER, "InterfacesAdded", self._added)
        self.client.subscribe(MANAGER, "InterfacesRemoved", self._removed)
        self.client.subscribe(PROPERTIES, "PropertiesChanged", self._changed)
        self.client.watch_owner(self._attach)
        self._attach()

    def _attach(self) -> None:
        self.generation += 1
        generation = self.generation
        self.operation += 1
        self.loading = True
        self.queued.clear()
        self.objects.clear()
        self.path = ""
        if self.raw_name:
            self.name = ""
            self.raw_name = ""
            self.emit(Event("DeviceName", ""))
        self.available = False
        self.emit(Event("Availability", False))

        def snapshot(reply: Any, error: str) -> None:
            if generation != self.generation:
                return
            self.objects = reply[0] if not error else {}
            self.loading = False
            for kind, args in self.queued:
                self._apply(kind, args)
            self.queued.clear()
            self.ready = True
            self._publish(force=True)

        self.client.call("/", MANAGER, "GetManagedObjects", None, snapshot)

    def _apply(self, kind: str, args: tuple[Any, ...]) -> None:
        if kind == "added":
            path, interfaces = args
            self.objects.setdefault(path, {}).update(interfaces)
        elif kind == "removed":
            path, interfaces = args
            for interface in interfaces:
                self.objects.get(path, {}).pop(interface, None)
        else:
            path, interface, changes, invalidated = args
            props = self.objects.get(path, {}).get(interface)
            if props is not None:
                props.update(changes)
                for name in invalidated:
                    props.pop(name, None)

    def _event(self, kind: str, args: tuple[Any, ...]) -> None:
        if self.loading:
            self.queued.append((kind, args))
        else:
            self._apply(kind, args)
            self._publish()

    def _added(self, *args: Any) -> None:
        self._event("added", tuple(args[5].unpack()))

    def _removed(self, *args: Any) -> None:
        self._event("removed", tuple(args[5].unpack()))

    def _changed(self, *args: Any) -> None:
        interface, changes, invalidated = args[5].unpack()
        self._event("changed", (args[2], interface, changes, invalidated))

    def _publish(self, force: bool = False) -> None:
        path, props = "", {}
        for candidate, interfaces in self.objects.items():
            p = interfaces.get(DEVICE, {})
            if (
                self.config.device.address
                and str(p.get("Address", "")).upper() == self.config.device.address
            ):
                path, props = candidate, p
                break
        self.path = path
        name = str(props.get("Alias", props.get("Name", "")))
        if self.raw_name != name or force:
            self.raw_name = name
            self.name = display_text(name)
            self.emit(Event("DeviceName", name))
        connected = bool(props.get("Connected", False))
        available = bool(
            props.get("Paired", False)
            and self.objects.get(props.get("Adapter", ""), {})
            .get(ADAPTER, {})
            .get("Powered", False)
        )
        # On loss, mark unavailable before Connected(false), avoiding automatic grabs.
        if not available and (self.available or force):
            self.available = False
            self.emit(Event("Availability", False))
        if connected != self.connected or force:
            self.connected = connected
            self.emit(Event("DeviceConnected", connected))
        if available and (not self.available or force):
            self.available = True
            self.emit(Event("Availability", True))

    def _operate(self, method: str, event: str) -> None:
        self.operation += 1
        operation, generation = self.operation, self.generation
        if not self.path or not self.available:
            self.emit(Event(event, "org.bluez.Error.NotReady"))
            return
        timeout = (
            self.config.policy.connect_timeout_seconds
            + self.config.backend.dbus_margin_seconds
        ) * 1000

        def finished(reply: Any, error: str) -> None:
            if operation == self.operation and generation == self.generation:
                self.emit(Event(event, error))

        self.client.call(self.path, DEVICE, method, None, finished, timeout)

    def connect(self) -> None:
        self._operate("Connect", "ConnectResult")

    def disconnect(self) -> None:
        self._operate("Disconnect", "DisconnectResult")

    def list_devices(self, done: Callable[[list[tuple[str, str]]], None]) -> None:
        def received(reply: Any, error: str) -> None:
            objects = reply[0] if not error else {}
            devices: dict[str, str] = {}
            for interfaces in objects.values():
                props = interfaces.get(DEVICE, {})
                powered = (
                    objects.get(props.get("Adapter", ""), {})
                    .get(ADAPTER, {})
                    .get("Powered", False)
                )
                uuids = {str(v).lower() for v in props.get("UUIDs", [])}
                address = str(props.get("Address", "")).upper()
                if powered and props.get("Paired") and uuids & AUDIO_UUIDS and address:
                    devices.setdefault(address, display_text(props.get("Alias", "")))
            done(sorted(devices.items(), key=lambda item: item[1].casefold()))

        self.client.call("/", MANAGER, "GetManagedObjects", None, received)

    def close(self) -> None:
        self.operation += 1
        self.client.close()
