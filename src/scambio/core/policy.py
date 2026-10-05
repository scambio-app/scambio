"""Pure state machine. Timing and all effects belong to the executor."""

from dataclasses import dataclass, replace
from typing import Literal

from scambio.config import Policy

Status = Literal["released", "connecting", "on_pc", "releasing", "unavailable"]


@dataclass(frozen=True)
class Context:
    state: Status = "unavailable"
    priority: bool = False
    audio_active: bool = False
    device_connected: bool = False
    sink_ready: bool = False
    locked: bool = False
    sleeping: bool = False
    blocked_until_silence: bool = False
    pending: Literal["none", "grab", "release"] = "none"
    pending_reason: str = ""
    origin: Literal["self", "external"] = "external"
    routed: bool = False
    reason: str = "availability"
    last_error: str = ""

    @property
    def eligible(self) -> bool:
        return (
            self.audio_active
            and not self.priority
            and not self.locked
            and not self.sleeping
            and not self.blocked_until_silence
        )

    @property
    def destination_pc(self) -> bool:
        return (
            self.state == "on_pc"
            or (self.state == "connecting" and self.pending != "release")
            or (self.state == "releasing" and self.pending == "grab")
        )


@dataclass(frozen=True)
class Event:
    kind: str
    value: bool | str = ""


@dataclass(frozen=True)
class Action:
    kind: str
    value: str | bool = ""
    milliseconds: int = 0
    transition: tuple[str, str, str] = ("", "", "")


def step(ctx: Context, event: Event, config: Policy) -> tuple[Context, list[Action]]:
    c = replace(ctx)
    actions: list[Action] = []
    kind, value = event.kind, event.value
    toward_phone = ctx.destination_pc
    durations = {
        "GRAB_DELAY": config.grab_delay_ms,
        "IDLE": config.release_idle_seconds * 1000,
        "CONNECT": config.connect_timeout_seconds * 1000,
        "RELEASE": config.connect_timeout_seconds * 1000,
        "SINK": config.sink_timeout_seconds * 1000,
        "SLEEP": config.sleep_release_timeout_seconds * 1000,
        "UNBLOCK": config.unblock_silence_seconds * 1000,
    }

    def act(name: str, val: str | bool = "") -> None:
        actions.append(Action(name, val))

    def start(name: str) -> None:
        actions.append(Action("StartTimer", name, durations[name]))

    def cancel(*names: str) -> None:
        actions.extend(Action("CancelTimer", n) for n in names)

    def error(code: str) -> None:
        nonlocal c
        c = replace(c, last_error=code)
        act("EmitError", code)

    def transition(state: Status, reason: str) -> None:
        nonlocal c
        old = c.state
        c = replace(c, state=state, reason=reason)
        if old != state:
            actions.append(Action("EmitTransition", transition=(old, state, reason)))
            if state == "released":  # G10
                c = replace(c, pending="none")
                if c.sleeping:
                    act("ReleaseSleepInhibitor")
                    cancel("SLEEP")
                if c.eligible:
                    start("GRAB_DELAY")

    def grab(reason: str) -> None:
        nonlocal c
        c = replace(c, last_error="", origin="self", pending="none")
        act("Connect")
        start("CONNECT")
        transition("connecting", reason)

    def release(reason: str) -> None:
        nonlocal c
        cancel("IDLE", "GRAB_DELAY", "CONNECT", "SINK")
        act("RestoreRouting")
        c = replace(c, routed=False, pending="none")
        act("Disconnect")
        start("RELEASE")
        transition("releasing", reason)

    def enter(route: bool) -> None:
        nonlocal c
        cancel("CONNECT", "SINK")
        if c.pending == "release":
            release(c.pending_reason)
        elif c.locked:
            release("locked")
        elif c.sleeping:
            release("sleep")
        else:
            if route:
                act("RouteToDevice")
                c = replace(c, routed=True)
            if not c.audio_active:
                start("IDLE")
            c = replace(c, pending="none", last_error="")
            transition("on_pc", c.reason)

    if kind == "AudioActive":
        c = replace(c, audio_active=bool(value))
        if value:
            cancel("UNBLOCK")
        elif c.blocked_until_silence:
            start("UNBLOCK")
    elif kind == "TimerFired" and value == "UNBLOCK":
        c = replace(c, blocked_until_silence=False)
        return c, actions
    elif kind == "DeviceConnected":
        c = replace(c, device_connected=bool(value))
    elif kind in {"DeviceSinkAppeared", "DeviceSinkGone"}:
        c = replace(c, sink_ready=kind == "DeviceSinkAppeared")
    elif kind == "Locked":
        c = replace(c, locked=bool(value))
    elif kind == "Sleep":
        c = replace(c, sleeping=bool(value))
        if value:
            start("SLEEP")
        else:
            cancel("SLEEP")
    elif kind == "TimerFired" and value == "SLEEP":
        act("ReleaseSleepInhibitor")
        return c, actions
    elif kind == "SetPriority":
        c = replace(c, priority=bool(value))
        act("SavePriority", c.priority)
    elif kind == "Switch":
        if c.state == "unavailable":
            error("device_unavailable")
            return c, actions
        c = replace(
            c,
            priority=toward_phone,
            blocked_until_silence=c.blocked_until_silence if toward_phone else False,
        )
        act("SavePriority", c.priority)
    elif kind == "Availability" and not value:
        if c.state in {"on_pc", "connecting", "releasing"}:
            c = replace(c, blocked_until_silence=c.audio_active)
        cancel("GRAB_DELAY", "IDLE", "CONNECT", "SINK", "RELEASE")
        act("RestoreRouting")
        c = replace(c, routed=False, pending="none")
        if c.sleeping:
            act("ReleaseSleepInhibitor")
            cancel("SLEEP")
        transition("unavailable", "availability")
        return c, actions
    elif kind == "AudioBackend":
        if not value:
            error("audio_backend_down")
        return c, actions

    release_reason = {
        "Switch": "switch",
        "SetPriority": "priority",
        "Locked": "locked",
        "Sleep": "sleep",
    }.get(kind, "")
    wants_release = (kind == "Switch" and toward_phone) or (
        kind in {"SetPriority", "Locked", "Sleep"} and value is True
    )
    timer = value if kind == "TimerFired" else ""

    if c.state == "released":
        if kind == "Sleep" and value:
            cancel("GRAB_DELAY", "SLEEP")
            act("ReleaseSleepInhibitor")
        elif (kind == "AudioActive" and not value) or (
            kind in {"SetPriority", "Locked"} and value
        ):
            cancel("GRAB_DELAY")
        elif kind in {"AudioActive", "SetPriority", "Locked", "Sleep"} and c.eligible:
            start("GRAB_DELAY")
        elif timer == "GRAB_DELAY" and c.eligible:
            grab("audio_started")
        elif kind == "DeviceConnected" and value:
            c = replace(c, origin="external", reason="external_connect")
            if c.sink_ready:
                enter(True)
            else:
                start("SINK")
                transition("connecting", c.reason)
        elif kind == "Switch" and not c.locked and not c.sleeping:
            grab("switch")
    elif c.state == "connecting":
        if kind == "ConnectResult":
            if value in {"", "org.bluez.Error.AlreadyConnected"}:
                cancel("CONNECT")
                if c.device_connected and c.sink_ready:
                    enter(True)
                else:
                    start("SINK")
            elif value != "org.bluez.Error.InProgress":
                error("connect_failed")
                c = replace(c, blocked_until_silence=c.audio_active)
                if c.device_connected:
                    release("connect_failed")
                else:
                    cancel("CONNECT", "SINK")
                    transition("released", "connect_failed")
        elif (kind == "DeviceSinkAppeared" and c.device_connected) or (
            kind == "DeviceConnected" and value and c.sink_ready
        ):
            enter(True)
        elif timer in {"CONNECT", "SINK"}:
            code = "connect_timeout" if timer == "CONNECT" else "sink_timeout"
            if timer == "SINK" and c.origin == "external":
                c = replace(c, reason=code)
                enter(False)
                error(code)
            else:
                error(code)
                c = replace(c, blocked_until_silence=c.audio_active)
                release(code)
        elif kind == "DeviceConnected" and not value:
            cancel("CONNECT", "SINK")
            reason = "external_disconnect"
            if c.origin == "self":
                reason = "connect_failed"
                error(reason)
                c = replace(c, blocked_until_silence=c.audio_active)
            transition("released", reason)
        elif wants_release:
            c = replace(c, pending="release", pending_reason=release_reason)
        elif kind == "Switch":
            c = replace(c, pending="none")
    elif c.state == "on_pc":
        if kind == "AudioActive":
            if value:
                cancel("IDLE")
            else:
                start("IDLE")
        elif timer == "IDLE":
            release("idle_timeout")
        elif wants_release:
            release(release_reason)
        elif kind == "DeviceConnected" and not value:
            cancel("IDLE", "SINK")
            act("RestoreRouting")
            c = replace(c, routed=False, blocked_until_silence=c.audio_active)
            transition("released", "external_disconnect")
        elif kind == "DeviceSinkGone" and c.device_connected:
            c = replace(c, routed=False)
            start("SINK")
        elif kind == "DeviceSinkAppeared" and not c.routed:
            cancel("SINK")
            act("RouteToDevice")
            c = replace(c, routed=True)
        elif timer == "SINK":
            error("sink_lost")
            c = replace(c, blocked_until_silence=c.audio_active)
            release("sink_lost")
    elif c.state == "releasing":
        if (
            kind == "DisconnectResult"
            or timer == "RELEASE"
            or (kind == "DeviceConnected" and not value)
        ):
            cancel("RELEASE")
            if (kind == "DisconnectResult" and value == "") or not c.device_connected:
                if c.pending == "grab" and not c.locked and not c.sleeping:
                    grab("switch")
                else:
                    transition("released", c.reason)
            else:
                error("disconnect_failed")
                c = replace(c, pending="none", routed=True)
                if c.sleeping:
                    act("ReleaseSleepInhibitor")
                    cancel("SLEEP")
                act("RouteToDevice")
                if not c.audio_active:
                    start("IDLE")
                transition("on_pc", "disconnect_failed")
        elif wants_release:
            c = replace(c, pending="none")
        elif kind == "Switch":
            c = replace(c, pending="grab")
    elif c.state == "unavailable" and kind == "Availability" and value:
        c = replace(c, origin="external", reason="availability")
        if c.device_connected and c.sink_ready:
            enter(True)
        elif c.device_connected:
            start("SINK")
            transition("connecting", "availability")
        else:
            transition("released", "availability")
    return c, actions
