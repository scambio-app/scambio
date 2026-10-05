"""Spec 02 §3.1.4: exact effects, flows and exhaustive finite traces."""

from collections import defaultdict
from dataclasses import replace
from itertools import product

import pytest
from test_policy import ENTER, GRAB, RELEASE, SLEEP_RELEASE, cancel, start, transition

from scambio.config import Policy
from scambio.core.policy import Action as A
from scambio.core.policy import Context, Event, step

CFG = Policy(resume_delay_ms=2000)


def exact(c, event, changes, actions):
    assert step(c, event, CFG) == (replace(c, **changes), actions)


@pytest.mark.parametrize("active,held", [(False, False), (True, False), (False, True)])
def test_grab(active, held):
    c = Context(state="releasing", pending="grab", audio_active=active, held=held)
    exact(
        c,
        Event("DisconnectResult"),
        dict(
            state="connecting",
            pending="none",
            origin="self",
            reason="switch",
            held=active or held,
        ),
        [
            *cancel("RELEASE"),
            *([A("PausePlayers", "grab")] if active or held else []),
            *GRAB,
            transition("releasing", "connecting", "switch"),
        ],
    )


@pytest.mark.parametrize("active,held", [(True, False), (False, True), (False, False)])
@pytest.mark.parametrize(
    "kind,reason,prefix,changes",
    [
        ("Locked", "locked", [], {"locked": True}),
        ("Sleep", "sleep", [start("SLEEP", 4000)], {"sleeping": True}),
        ("Switch", "switch", [A("SavePriority", True)], {"priority": True}),
        ("SetPriority", "priority", [A("SavePriority", True)], {"priority": True}),
    ],
)
def test_release_p(active, held, kind, reason, prefix, changes):
    c = Context(state="on_pc", routed=True, audio_active=active, held=held)
    exact(
        c,
        Event(kind, True),
        dict(
            changes, state="releasing", routed=False, reason=reason, held=active or held
        ),
        [
            *prefix,
            *RELEASE[:5],
            *([A("PausePlayers", "release")] if active or held else []),
            *RELEASE[5:],
            transition("on_pc", "releasing", reason),
        ],
    )


@pytest.mark.parametrize(
    "row,event,connected,target,code",
    [
        ("C4", Event("ConnectResult", "failed"), False, "released", "connect_failed"),
        ("C4", Event("ConnectResult", "failed"), True, "releasing", "connect_failed"),
        ("C5", Event("TimerFired", "CONNECT"), False, "releasing", "connect_timeout"),
        ("C6", Event("TimerFired", "SINK"), True, "releasing", "sink_timeout"),
        ("C8", Event("DeviceConnected", False), False, "released", "connect_failed"),
        ("O11", Event("TimerFired", "SINK"), True, "releasing", "sink_lost"),
    ],
)
@pytest.mark.parametrize("pending", ["none", "release"])
@pytest.mark.parametrize("active", [False, True])
def test_error_outcomes(row, event, connected, target, code, pending, active):
    c = Context(
        state="on_pc" if row == "O11" else "connecting",
        origin="self",
        held=True,
        audio_active=active,
        pending=pending,
        device_connected=connected,
        routed=connected,
    )
    outcome = A("ForgetPlayers" if pending == "release" else "ResumePlayers")
    unblock = [] if active else [start("UNBLOCK", 10000)]
    prefix = [*ENTER, A("EmitError", code)] if row == "C8" else [A("EmitError", code)]
    suffix = (
        [*RELEASE[:6], outcome, *RELEASE[6:]]
        if target == "releasing"
        else [*([] if row == "C8" else ENTER), outcome]
    )
    exact(
        c,
        event,
        dict(
            state=target,
            reason=code,
            last_error=code,
            held=False,
            pending="none",
            blocked_until_silence=True,
            routed=False if target == "releasing" else c.routed,
        ),
        [*prefix, *unblock, *suffix, transition(c.state, target, code)],
    )


@pytest.mark.parametrize("active", [False, True])
def test_entry_and_o1(active):
    c = Context(
        state="connecting", device_connected=True, held=True, audio_active=active
    )
    exact(
        c,
        Event("DeviceSinkAppeared"),
        dict(state="on_pc", sink_ready=True, routed=True),
        [
            *ENTER,
            A("RouteToDevice"),
            start("RESUME", 2000),
            transition("connecting", "on_pc"),
        ],
    )
    c = replace(c, state="on_pc")
    exact(c, Event("AudioActive", False), {"audio_active": False}, [])


@pytest.mark.parametrize("held,active", list(product([False, True], repeat=2)))
def test_o8(held, active):
    c = Context(
        state="on_pc",
        device_connected=True,
        routed=True,
        held=held,
        audio_active=active,
    )
    outcome = (
        [A("ResumePlayers")]
        if held
        else [A("PausePlayers", "release"), A("ForgetPlayers")]
        if active
        else []
    )
    exact(
        c,
        Event("DeviceConnected", False),
        dict(
            state="released",
            device_connected=False,
            routed=False,
            held=False,
            blocked_until_silence=active or held,
            reason="external_disconnect",
        ),
        [
            *cancel("IDLE", "SINK", "RESUME"),
            A("RestoreRouting"),
            *([start("UNBLOCK", 10000)] if held and not active else []),
            *outcome,
            transition("on_pc", "released", "external_disconnect"),
        ],
    )


def test_o9_o10_during_resume():
    c = Context(
        state="on_pc", device_connected=True, routed=True, sink_ready=True, held=True
    )
    exact(
        c,
        Event("DeviceSinkGone"),
        dict(routed=False, sink_ready=False),
        [start("SINK", 5000)],
    )
    c = replace(c, routed=False, sink_ready=False)
    exact(c, Event("TimerFired", "RESUME"), {}, [])
    exact(
        c,
        Event("DeviceSinkAppeared"),
        dict(routed=True, sink_ready=True),
        [*cancel("SINK"), A("RouteToDevice"), start("RESUME", 2000)],
    )


@pytest.mark.parametrize("routed,active", list(product([False, True], repeat=2)))
def test_o12(routed, active):
    c = Context(state="on_pc", routed=routed, audio_active=active, held=True)
    exact(
        c,
        Event("TimerFired", "RESUME"),
        {"held": False} if routed else {},
        [A("ResumePlayers"), *([] if active else [start("IDLE", 120000)])]
        if routed
        else [],
    )


@pytest.mark.parametrize(
    "state", ["released", "unavailable", "connecting", "releasing"]
)
def test_resume_late(state):
    c = Context(state=state)
    exact(c, Event("TimerFired", "RESUME"), {}, [])


@pytest.mark.parametrize(
    "locked,sleeping,active", list(product([False, True], repeat=3))
)
def test_l2(locked, sleeping, active):
    c = Context(
        state="releasing",
        held=True,
        device_connected=True,
        pending="grab",
        locked=locked,
        sleeping=sleeping,
        audio_active=active,
    )
    exact(
        c,
        Event("DisconnectResult", "failed"),
        dict(
            state="on_pc",
            held=False,
            pending="none",
            routed=True,
            last_error="disconnect_failed",
            reason="disconnect_failed",
        ),
        [
            *cancel("RELEASE"),
            A("EmitError", "disconnect_failed"),
            *(SLEEP_RELEASE if sleeping else []),
            A("RouteToDevice"),
            A("ForgetPlayers" if locked or sleeping else "ResumePlayers"),
            *([] if active else [start("IDLE", 120000)]),
            transition("releasing", "on_pc", "disconnect_failed"),
        ],
    )


def test_l1_forgets():
    c = Context(state="releasing", held=True)
    exact(
        c,
        Event("DisconnectResult"),
        dict(state="released", held=False),
        [*cancel("RELEASE"), A("ForgetPlayers"), transition("releasing", "released")],
    )


@pytest.mark.parametrize(
    "state", ["released", "unavailable", "connecting", "on_pc", "releasing"]
)
@pytest.mark.parametrize("pending", ["none", "release"])
def test_g8(state, pending):
    held = state in {"connecting", "on_pc", "releasing"}
    c = Context(state=state, held=held, pending=pending, routed=True)
    pre = [start("UNBLOCK", 10000)] if held else []
    pauses = (
        [A("PausePlayers", "release"), A("ForgetPlayers")]
        if state in {"on_pc", "releasing"}
        else []
    )
    outcome = (
        [A("ForgetPlayers" if pending == "release" else "ResumePlayers")]
        if state == "connecting"
        else []
    )
    exact(
        c,
        Event("Availability", False),
        dict(
            state="unavailable",
            held=False,
            pending="none",
            routed=False,
            blocked_until_silence=held,
        ),
        [
            *pre,
            *cancel("GRAB_DELAY", "IDLE", "CONNECT", "SINK", "RELEASE", "RESUME"),
            *pauses,
            A("RestoreRouting"),
            *outcome,
            *([] if state == "unavailable" else [transition(state, "unavailable")]),
        ],
    )


def test_switch_during_grab_and_double_switch_release():
    c = Context(state="released", audio_active=True)
    c, _ = step(c, Event("TimerFired", "GRAB_DELAY"), CFG)
    c, _ = step(c, Event("AudioActive", False), CFG)
    c, _ = step(c, Event("Switch"), CFG)
    c, _ = step(c, Event("DeviceConnected", True), CFG)
    c, actions = step(c, Event("DeviceSinkAppeared"), CFG)
    assert c.state == "releasing" and c.held
    assert A("PausePlayers", "release") in actions and A("ResumePlayers") not in actions
    c, _ = step(c, Event("Switch"), CFG)
    c, actions = step(c, Event("DisconnectResult"), CFG)
    assert c.state == "connecting" and c.held
    assert A("PausePlayers", "grab") in actions
    c, _ = step(c, Event("DeviceConnected", True), CFG)
    c, actions = step(c, Event("TimerFired", "RESUME"), CFG)
    assert c.state == "on_pc" and not c.held and A("ResumePlayers") in actions


def test_exhaustive_six_events():
    # Merge identical (context, obligation) prefixes with dynamic programming.
    # Counts retain every word, including repeats and out-of-state timer events: 18**6.
    events = (
        [Event("AudioActive", v) for v in [True, False]]
        + [
            Event("TimerFired", t)
            for t in ["GRAB_DELAY", "CONNECT", "SINK", "RESUME", "RELEASE", "IDLE"]
        ]
        + [Event("ConnectResult", v) for v in ["", "Failed"]]
        + [Event("DeviceConnected", v) for v in [True, False]]
        + [
            Event("DeviceSinkAppeared"),
            Event("DeviceSinkGone"),
            Event("DisconnectResult"),
            Event("Locked", True),
            Event("Switch"),
            Event("Availability", False),
        ]
    )
    frontier = {(Context(state="released", audio_active=True), False): 1}
    for _ in range(6):
        following = defaultdict(int)
        for (c, owed), count in frontier.items():
            for event in events:
                nxt, actions = step(c, event, CFG)
                debt = owed
                for action in actions:
                    if action == A("PausePlayers", "grab"):
                        debt = True
                    elif action.kind in {"ResumePlayers", "ForgetPlayers"}:
                        debt = False
                assert nxt.state not in {"released", "unavailable"} or not nxt.held
                assert not debt or nxt.held
                # Every unresolved grab has a finite cleanup path, even on failure.
                if debt:
                    end, cleanup = step(nxt, Event("Availability", False), CFG)
                    assert not end.held
                    assert any(
                        a.kind in {"ResumePlayers", "ForgetPlayers"} for a in cleanup
                    )
                # A user release cannot resume in that transition, except L2.
                if (
                    c.state == "releasing"
                    and c.held
                    and any(a.kind == "ResumePlayers" for a in actions)
                ):
                    assert nxt.state == "on_pc" and not (c.locked or c.sleeping)
                following[nxt, debt] += count
        frontier = following
    assert sum(frontier.values()) == len(events) ** 6 == 34_012_224
