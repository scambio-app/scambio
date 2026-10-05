from dataclasses import replace

import pytest

from scambio.config import Policy
from scambio.core.policy import Action, Context, Event, step


# Explicit expectations from spec §3.1.5. These constants describe action records,
# not calls to the policy or an alternative state machine.
def cancel(*names):
    return [Action("CancelTimer", name) for name in names]


def start(name, milliseconds):
    return Action("StartTimer", name, milliseconds)


def transition(before, after, reason="availability"):
    return Action("EmitTransition", transition=(before, after, reason))


ENTER = cancel("CONNECT", "SINK")
RELEASE = [
    *cancel("IDLE", "GRAB_DELAY", "CONNECT", "SINK", "RESUME"),
    Action("RestoreRouting"),
    Action("Disconnect"),
    start("RELEASE", 10000),
]
GRAB = [Action("Connect"), start("CONNECT", 10000)]
SLEEP_RELEASE = [Action("ReleaseSleepInhibitor"), *cancel("SLEEP")]

# name, initial context, event, context changes, complete ordered actions
CASES = [
    (
        "G1",
        {"blocked_until_silence": True, "audio_active": True},
        Event("AudioActive", False),
        {"audio_active": False},
        [start("UNBLOCK", 10000)],
    ),
    (
        "G1b",
        {"blocked_until_silence": True},
        Event("TimerFired", "UNBLOCK"),
        {"blocked_until_silence": False},
        [],
    ),
    ("G2", {}, Event("DeviceSinkAppeared", "bt"), {"sink_ready": True}, []),
    (
        "G2-connected",
        {},
        Event("DeviceConnected", True),
        {"device_connected": True},
        [],
    ),
    (
        "G2-gone",
        {"sink_ready": True},
        Event("DeviceSinkGone"),
        {"sink_ready": False},
        [],
    ),
    ("G3", {}, Event("Locked", True), {"locked": True}, []),
    ("G4", {}, Event("Sleep", True), {"sleeping": True}, [start("SLEEP", 4000)]),
    (
        "G4-wake",
        {"sleeping": True},
        Event("Sleep", False),
        {"sleeping": False},
        cancel("SLEEP"),
    ),
    (
        "G5",
        {"sleeping": True},
        Event("TimerFired", "SLEEP"),
        {},
        [Action("ReleaseSleepInhibitor")],
    ),
    (
        "G6",
        {},
        Event("SetPriority", True),
        {"priority": True},
        [Action("SavePriority", True)],
    ),
    (
        "G7",
        {
            "state": "released",
            "priority": True,
            "blocked_until_silence": True,
            "last_error": "connect_failed",
        },
        Event("Switch"),
        {
            "state": "connecting",
            "priority": False,
            "blocked_until_silence": False,
            "last_error": "",
            "origin": "self",
            "reason": "switch",
        },
        [
            Action("SavePriority", False),
            *GRAB,
            transition("released", "connecting", "switch"),
        ],
    ),
    (
        "G8",
        {"state": "on_pc", "sleeping": True, "routed": True, "pending": "grab"},
        Event("Availability", False),
        {"state": "unavailable", "routed": False, "pending": "none"},
        [
            *cancel("GRAB_DELAY", "IDLE", "CONNECT", "SINK", "RELEASE", "RESUME"),
            Action("RestoreRouting"),
            *SLEEP_RELEASE,
            transition("on_pc", "unavailable"),
        ],
    ),
    (
        "G9",
        {
            "state": "on_pc",
            "audio_active": True,
            "device_connected": True,
            "sink_ready": True,
            "priority": True,
            "routed": True,
            "pending": "release",
            "pending_reason": "priority",
            "origin": "self",
            "reason": "switch",
            "blocked_until_silence": True,
        },
        Event("AudioBackend", False),
        {"last_error": "audio_backend_down"},
        [Action("EmitError", "audio_backend_down")],
    ),
    (
        "G9-recovered",
        {
            "state": "on_pc",
            "audio_active": True,
            "device_connected": True,
            "routed": True,
            "last_error": "audio_backend_down",
        },
        Event("AudioBackend", True),
        {},
        [],
    ),
    (
        "G10",
        {"state": "releasing", "sleeping": True, "pending": "grab"},
        Event("DisconnectResult"),
        {"state": "released", "pending": "none"},
        [*cancel("RELEASE"), transition("releasing", "released"), *SLEEP_RELEASE],
    ),
    (
        "G10-eligible",
        {"state": "releasing", "audio_active": True},
        Event("DisconnectResult"),
        {"state": "released"},
        [
            *cancel("RELEASE"),
            transition("releasing", "released"),
            start("GRAB_DELAY", 500),
        ],
    ),
    (
        "G11",
        {},
        Event("Availability", True),
        {"state": "released"},
        [transition("unavailable", "released")],
    ),
    (
        "G12",
        {
            "state": "released",
            "last_error": "connect_failed",
            "blocked_until_silence": True,
        },
        Event("ConnectResult"),
        {},
        [],
    ),
    (
        "R1",
        {"state": "released"},
        Event("AudioActive", True),
        {"audio_active": True},
        [*cancel("UNBLOCK"), start("GRAB_DELAY", 500)],
    ),
    (
        "R2",
        {"state": "released", "audio_active": True, "blocked_until_silence": True},
        Event("AudioActive", False),
        {"audio_active": False},
        [start("UNBLOCK", 10000), *cancel("GRAB_DELAY")],
    ),
    (
        "R2-priority",
        {"state": "released"},
        Event("SetPriority", True),
        {"priority": True},
        [Action("SavePriority", True), *cancel("GRAB_DELAY")],
    ),
    (
        "R2-locked",
        {"state": "released"},
        Event("Locked", True),
        {"locked": True},
        cancel("GRAB_DELAY"),
    ),
    (
        "R3",
        {"state": "released"},
        Event("Sleep", True),
        {"sleeping": True},
        [
            start("SLEEP", 4000),
            *cancel("GRAB_DELAY", "SLEEP"),
            Action("ReleaseSleepInhibitor"),
        ],
    ),
    (
        "R4",
        {"state": "released", "audio_active": True, "last_error": "sink_timeout"},
        Event("TimerFired", "GRAB_DELAY"),
        {
            "state": "connecting",
            "origin": "self",
            "last_error": "",
            "reason": "audio_started",
            "held": True,
        },
        [
            Action("PausePlayers", "grab"),
            *GRAB,
            transition("released", "connecting", "audio_started"),
        ],
    ),
    (
        "R5",
        {"state": "released"},
        Event("DeviceConnected", True),
        {"state": "connecting", "device_connected": True, "reason": "external_connect"},
        [start("SINK", 5000), transition("released", "connecting", "external_connect")],
    ),
    (
        "R5-sink-ready",
        {
            "state": "released",
            "sink_ready": True,
            "priority": True,
            "origin": "self",
            "last_error": "connect_failed",
        },
        Event("DeviceConnected", True),
        {
            "state": "on_pc",
            "device_connected": True,
            "origin": "external",
            "reason": "external_connect",
            "last_error": "",
            "routed": True,
        },
        [
            *ENTER,
            Action("RouteToDevice"),
            start("IDLE", 120000),
            transition("released", "on_pc", "external_connect"),
        ],
    ),
    (
        "R6",
        {"state": "released"},
        Event("Switch"),
        {"state": "connecting", "origin": "self", "reason": "switch"},
        [
            Action("SavePriority", False),
            *GRAB,
            transition("released", "connecting", "switch"),
        ],
    ),
    (
        "R6-locked",
        {
            "state": "released",
            "locked": True,
            "priority": True,
            "blocked_until_silence": True,
        },
        Event("Switch"),
        {"priority": False, "blocked_until_silence": False},
        [Action("SavePriority", False)],
    ),
    (
        "R6-sleeping",
        {
            "state": "released",
            "sleeping": True,
            "priority": True,
            "blocked_until_silence": True,
        },
        Event("Switch"),
        {"priority": False, "blocked_until_silence": False},
        [Action("SavePriority", False)],
    ),
    (
        "C1",
        {"state": "connecting"},
        Event("ConnectResult"),
        {},
        [*cancel("CONNECT"), start("SINK", 5000)],
    ),
    (
        "C2",
        {"state": "connecting"},
        Event("ConnectResult", "org.bluez.Error.InProgress"),
        {},
        [],
    ),
    (
        "C3",
        {
            "state": "connecting",
            "device_connected": True,
            "last_error": "connect_failed",
        },
        Event("DeviceSinkAppeared", "bt"),
        {"state": "on_pc", "sink_ready": True, "routed": True, "last_error": ""},
        [
            *ENTER,
            Action("RouteToDevice"),
            start("IDLE", 120000),
            transition("connecting", "on_pc"),
        ],
    ),
    (
        "C3-connected",
        {"state": "connecting", "sink_ready": True, "audio_active": True},
        Event("DeviceConnected", True),
        {"state": "on_pc", "device_connected": True, "routed": True},
        [*ENTER, Action("RouteToDevice"), transition("connecting", "on_pc")],
    ),
    (
        "C4",
        {"state": "connecting", "audio_active": True, "pending": "release"},
        Event("ConnectResult", "org.bluez.Error.Failed"),
        {
            "state": "released",
            "blocked_until_silence": True,
            "pending": "none",
            "reason": "connect_failed",
            "last_error": "connect_failed",
        },
        [
            Action("EmitError", "connect_failed"),
            *ENTER,
            transition("connecting", "released", "connect_failed"),
        ],
    ),
    (
        "C4-connected",
        {
            "state": "connecting",
            "device_connected": True,
            "audio_active": True,
            "routed": True,
        },
        Event("ConnectResult", "org.bluez.Error.Failed"),
        {
            "state": "releasing",
            "blocked_until_silence": True,
            "routed": False,
            "reason": "connect_failed",
            "last_error": "connect_failed",
        },
        [
            Action("EmitError", "connect_failed"),
            *RELEASE,
            transition("connecting", "releasing", "connect_failed"),
        ],
    ),
    (
        "C5",
        {"state": "connecting", "audio_active": True},
        Event("TimerFired", "CONNECT"),
        {
            "state": "releasing",
            "blocked_until_silence": True,
            "reason": "connect_timeout",
            "last_error": "connect_timeout",
        },
        [
            Action("EmitError", "connect_timeout"),
            *RELEASE,
            transition("connecting", "releasing", "connect_timeout"),
        ],
    ),
    (
        "C6",
        {"state": "connecting", "origin": "self", "audio_active": True},
        Event("TimerFired", "SINK"),
        {
            "state": "releasing",
            "blocked_until_silence": True,
            "reason": "sink_timeout",
            "last_error": "sink_timeout",
        },
        [
            Action("EmitError", "sink_timeout"),
            *RELEASE,
            transition("connecting", "releasing", "sink_timeout"),
        ],
    ),
    (
        "C7",
        {"state": "connecting", "origin": "external", "device_connected": True},
        Event("TimerFired", "SINK"),
        {"state": "on_pc", "reason": "sink_timeout", "last_error": "sink_timeout"},
        [
            *ENTER,
            start("IDLE", 120000),
            transition("connecting", "on_pc", "sink_timeout"),
            Action("EmitError", "sink_timeout"),
        ],
    ),
    (
        "C8",
        {
            "state": "connecting",
            "origin": "self",
            "device_connected": True,
            "audio_active": True,
        },
        Event("DeviceConnected", False),
        {
            "state": "released",
            "device_connected": False,
            "blocked_until_silence": True,
            "reason": "connect_failed",
            "last_error": "connect_failed",
        },
        [
            *ENTER,
            Action("EmitError", "connect_failed"),
            transition("connecting", "released", "connect_failed"),
        ],
    ),
    (
        "C8-external",
        {"state": "connecting", "device_connected": True, "audio_active": True},
        Event("DeviceConnected", False),
        {
            "state": "released",
            "device_connected": False,
            "reason": "external_disconnect",
        },
        [
            *ENTER,
            transition("connecting", "released", "external_disconnect"),
            start("GRAB_DELAY", 500),
        ],
    ),
    (
        "C9",
        {"state": "connecting"},
        Event("SetPriority", True),
        {"priority": True, "pending": "release", "pending_reason": "priority"},
        [Action("SavePriority", True)],
    ),
    (
        "C10",
        {
            "state": "connecting",
            "priority": True,
            "pending": "release",
            "pending_reason": "priority",
            "blocked_until_silence": True,
        },
        Event("Switch"),
        {"priority": False, "blocked_until_silence": False, "pending": "none"},
        [Action("SavePriority", False)],
    ),
    (
        "O1",
        {"state": "on_pc", "audio_active": True},
        Event("AudioActive", False),
        {"audio_active": False},
        [start("IDLE", 120000)],
    ),
    (
        "O2",
        {"state": "on_pc"},
        Event("AudioActive", True),
        {"audio_active": True},
        cancel("UNBLOCK", "IDLE"),
    ),
    (
        "O3",
        {"state": "on_pc", "routed": True},
        Event("TimerFired", "IDLE"),
        {"state": "releasing", "routed": False, "reason": "idle_timeout"},
        [*RELEASE, transition("on_pc", "releasing", "idle_timeout")],
    ),
    (
        "O4",
        {"state": "on_pc", "routed": True},
        Event("Locked", True),
        {"state": "releasing", "locked": True, "routed": False, "reason": "locked"},
        [*RELEASE, transition("on_pc", "releasing", "locked")],
    ),
    (
        "O5",
        {"state": "on_pc", "routed": True},
        Event("Sleep", True),
        {"state": "releasing", "sleeping": True, "routed": False, "reason": "sleep"},
        [start("SLEEP", 4000), *RELEASE, transition("on_pc", "releasing", "sleep")],
    ),
    (
        "O6",
        {"state": "on_pc", "routed": True, "blocked_until_silence": True},
        Event("Switch"),
        {"state": "releasing", "priority": True, "routed": False, "reason": "switch"},
        [
            Action("SavePriority", True),
            *RELEASE,
            transition("on_pc", "releasing", "switch"),
        ],
    ),
    (
        "O7",
        {"state": "on_pc", "routed": True},
        Event("SetPriority", True),
        {"state": "releasing", "priority": True, "routed": False, "reason": "priority"},
        [
            Action("SavePriority", True),
            *RELEASE,
            transition("on_pc", "releasing", "priority"),
        ],
    ),
    (
        "O8",
        {
            "state": "on_pc",
            "routed": True,
            "device_connected": True,
            "audio_active": True,
        },
        Event("DeviceConnected", False),
        {
            "state": "released",
            "device_connected": False,
            "routed": False,
            "blocked_until_silence": True,
            "reason": "external_disconnect",
        },
        [
            *cancel("IDLE", "SINK", "RESUME"),
            Action("RestoreRouting"),
            Action("PausePlayers", "release"),
            Action("ForgetPlayers"),
            transition("on_pc", "released", "external_disconnect"),
        ],
    ),
    (
        "O9",
        {
            "state": "on_pc",
            "device_connected": True,
            "routed": True,
            "sink_ready": True,
        },
        Event("DeviceSinkGone"),
        {"sink_ready": False, "routed": False},
        [start("SINK", 5000)],
    ),
    (
        "O10",
        {"state": "on_pc"},
        Event("DeviceSinkAppeared", "bt"),
        {"sink_ready": True, "routed": True},
        [*cancel("SINK"), Action("RouteToDevice")],
    ),
    (
        "O11",
        {"state": "on_pc", "routed": True, "audio_active": True},
        Event("TimerFired", "SINK"),
        {
            "state": "releasing",
            "routed": False,
            "blocked_until_silence": True,
            "reason": "sink_lost",
            "last_error": "sink_lost",
        },
        [
            Action("EmitError", "sink_lost"),
            *RELEASE,
            transition("on_pc", "releasing", "sink_lost"),
        ],
    ),
    (
        "L1",
        {"state": "releasing"},
        Event("DisconnectResult"),
        {"state": "released"},
        [*cancel("RELEASE"), transition("releasing", "released")],
    ),
    (
        "L1-wait-connected",
        {"state": "releasing", "device_connected": True, "pending": "grab"},
        Event("DisconnectResult"),
        {},
        [],
    ),
    (
        "L1-disconnected",
        {"state": "releasing", "device_connected": True},
        Event("DeviceConnected", False),
        {"state": "released", "device_connected": False},
        [*cancel("RELEASE"), transition("releasing", "released")],
    ),
    (
        "L1-grab-locked",
        {"state": "releasing", "pending": "grab", "locked": True, "audio_active": True},
        Event("DisconnectResult"),
        {"state": "released", "pending": "none"},
        [*cancel("RELEASE"), transition("releasing", "released")],
    ),
    (
        "L2",
        {"state": "releasing", "device_connected": True, "pending": "grab"},
        Event("DisconnectResult", "failed"),
        {
            "state": "on_pc",
            "pending": "none",
            "routed": True,
            "reason": "disconnect_failed",
            "last_error": "disconnect_failed",
        },
        [
            *cancel("RELEASE"),
            Action("EmitError", "disconnect_failed"),
            Action("RouteToDevice"),
            start("IDLE", 120000),
            transition("releasing", "on_pc", "disconnect_failed"),
        ],
    ),
    (
        "L2-timeout",
        {"state": "releasing", "device_connected": True, "pending": "grab"},
        Event("TimerFired", "RELEASE"),
        {
            "state": "on_pc",
            "pending": "none",
            "routed": True,
            "reason": "disconnect_failed",
            "last_error": "disconnect_failed",
        },
        [
            *cancel("RELEASE"),
            Action("EmitError", "disconnect_failed"),
            Action("RouteToDevice"),
            start("IDLE", 120000),
            transition("releasing", "on_pc", "disconnect_failed"),
        ],
    ),
    (
        "L3",
        {"state": "releasing", "priority": True, "blocked_until_silence": True},
        Event("Switch"),
        {"pending": "grab", "priority": False, "blocked_until_silence": False},
        [Action("SavePriority", False)],
    ),
    (
        "L4",
        {"state": "releasing", "pending": "grab", "blocked_until_silence": True},
        Event("Switch"),
        {"pending": "none", "priority": True},
        [Action("SavePriority", True)],
    ),
    (
        "L4-priority",
        {"state": "releasing", "pending": "grab"},
        Event("SetPriority", True),
        {"pending": "none", "priority": True},
        [Action("SavePriority", True)],
    ),
    (
        "L4-locked",
        {"state": "releasing", "pending": "grab"},
        Event("Locked", True),
        {"pending": "none", "locked": True},
        [],
    ),
    (
        "L4-sleeping",
        {"state": "releasing", "pending": "grab"},
        Event("Sleep", True),
        {"pending": "none", "sleeping": True},
        [start("SLEEP", 4000)],
    ),
    (
        "U1",
        {"origin": "self"},
        Event("Availability", True),
        {"state": "released", "origin": "external"},
        [transition("unavailable", "released")],
    ),
    (
        "U1-connected",
        {"device_connected": True, "origin": "self"},
        Event("Availability", True),
        {"state": "connecting", "origin": "external"},
        [start("SINK", 5000), transition("unavailable", "connecting")],
    ),
    (
        "U1-sink-ready",
        {
            "device_connected": True,
            "sink_ready": True,
            "priority": True,
            "origin": "self",
            "last_error": "connect_failed",
        },
        Event("Availability", True),
        {"state": "on_pc", "origin": "external", "routed": True, "last_error": ""},
        [
            *ENTER,
            Action("RouteToDevice"),
            start("IDLE", 120000),
            transition("unavailable", "on_pc"),
        ],
    ),
    (
        "U2",
        {"priority": True, "blocked_until_silence": True},
        Event("Switch"),
        {"last_error": "device_unavailable"},
        [Action("EmitError", "device_unavailable")],
    ),
]


def assert_step(values, event, changes, actions, config=None):
    original = Context(**values)
    assert step(original, event, config or Policy()) == (
        replace(original, **changes),
        actions,
    )
    assert original == Context(**values)


@pytest.mark.parametrize(
    "rule,values,event,changes,actions", CASES, ids=[r[0] for r in CASES]
)
def test_rules(rule, values, event, changes, actions):
    assert_step(values, event, changes, actions)


@pytest.mark.parametrize("rule", ["C4", "C8", "C8-external", "O8", "U1"])
def test_sleeping_exits_release_inhibitor(rule):
    _, values, event, changes, actions = next(case for case in CASES if case[0] == rule)
    # G10 releases after the transition; sleeping forbids GRAB_DELAY.
    expected = [action for action in actions if action != start("GRAB_DELAY", 500)]
    assert_step(
        {**values, "sleeping": True}, event, changes, [*expected, *SLEEP_RELEASE]
    )


@pytest.mark.parametrize(
    "state,events",
    [
        (
            "released",
            [
                Event("ConnectResult"),
                Event("DisconnectResult", "failed"),
                *[
                    Event("TimerFired", timer)
                    for timer in ("CONNECT", "SINK", "RELEASE", "IDLE")
                ],
            ],
        ),
        (
            "on_pc",
            [
                Event("ConnectResult", "failed"),
                Event("DisconnectResult"),
                *[
                    Event("TimerFired", timer)
                    for timer in ("CONNECT", "RELEASE", "GRAB_DELAY")
                ],
            ],
        ),
        (
            "connecting",
            [
                Event("DisconnectResult"),
                Event("TimerFired", "IDLE"),
                Event("TimerFired", "RELEASE"),
                Event("TimerFired", "GRAB_DELAY"),
            ],
        ),
        (
            "releasing",
            [
                Event("ConnectResult"),
                Event("TimerFired", "CONNECT"),
                Event("TimerFired", "SINK"),
                Event("TimerFired", "IDLE"),
                Event("TimerFired", "GRAB_DELAY"),
            ],
        ),
        (
            "unavailable",
            [
                Event("ConnectResult"),
                Event("DisconnectResult"),
                *[
                    Event("TimerFired", timer)
                    for timer in ("CONNECT", "SINK", "RELEASE", "IDLE", "GRAB_DELAY")
                ],
            ],
        ),
    ],
)
def test_obsolete_results_and_timers(state, events):
    for event in events:
        assert_step(
            {
                "state": state,
                "last_error": "connect_failed",
                "blocked_until_silence": True,
            },
            event,
            {},
            [],
        )


def test_late_connect_result_after_c4():
    before = Context(state="connecting", origin="self", audio_active=True)
    after, actions = step(before, Event("ConnectResult", "failed"), Policy())
    assert after == replace(
        before,
        state="released",
        reason="connect_failed",
        last_error="connect_failed",
        blocked_until_silence=True,
    )
    assert actions == [
        Action("EmitError", "connect_failed"),
        *ENTER,
        transition("connecting", "released", "connect_failed"),
    ]
    for result in [
        "",
        "failed",
        "org.bluez.Error.AlreadyConnected",
        "org.bluez.Error.InProgress",
    ]:
        assert step(after, Event("ConnectResult", result), Policy()) == (after, [])


@pytest.mark.parametrize("state", ["connecting", "releasing"])
def test_double_switch(state):
    c = Context(state=state)
    c, _ = step(c, Event("Switch"), Policy())
    c, _ = step(c, Event("Switch"), Policy())
    assert c.pending == "none"
    assert c.destination_pc == (state == "connecting")


@pytest.mark.parametrize(
    "field", ["priority", "locked", "sleeping", "blocked_until_silence"]
)
def test_automatic_guards(field):
    c = replace(Context(state="released", audio_active=True), **{field: True})
    assert not step(c, Event("TimerFired", "GRAB_DELAY"), Policy())[1]


@pytest.mark.parametrize(
    "pending,locked,sleeping,reason",
    [
        ("release", False, False, "priority"),
        ("none", True, False, "locked"),
        ("none", False, True, "sleep"),
    ],
)
def test_entry_defers_to_release(pending, locked, sleeping, reason):
    c = Context(
        state="connecting",
        pending=pending,
        pending_reason="priority",
        locked=locked,
        sleeping=sleeping,
        device_connected=True,
    )
    c, actions = step(c, Event("DeviceSinkAppeared", "bt"), Policy())
    assert c.state == "releasing" and c.reason == reason
    assert "RouteToDevice" not in [a.kind for a in actions]


def test_external_adoption_and_timeout():
    c = Context(priority=True, device_connected=True, sink_ready=True)
    c, actions = step(c, Event("Availability", True), Policy())
    assert c.state == "on_pc" and c.priority and c.routed
    assert any(a.value == "IDLE" for a in actions)
    c = Context(state="connecting", origin="external", device_connected=True)
    c, actions = step(c, Event("TimerFired", "SINK"), Policy())
    assert c.state == "on_pc" and not c.routed
    assert not any(a.kind == "Disconnect" for a in actions)
    c, _ = step(c, Event("DeviceSinkAppeared", "bt"), Policy())
    assert c.routed


@pytest.mark.parametrize(
    "event", [Event("ConnectResult", "failed"), Event("TimerFired", "CONNECT")]
)
def test_failure_blocks_until_silence(event):
    c = Context(state="connecting", origin="self", audio_active=True)
    c, _ = step(c, event, Policy())
    assert c.blocked_until_silence
    if c.state == "releasing":
        c, _ = step(c, Event("DisconnectResult"), Policy())
    assert not step(c, Event("TimerFired", "GRAB_DELAY"), Policy())[1]
    before = c
    c, actions = step(c, Event("AudioActive", False), Policy())
    assert c == replace(before, audio_active=False)
    assert actions == [start("UNBLOCK", 10000), *cancel("GRAB_DELAY")]
    before = c
    c, actions = step(c, Event("TimerFired", "UNBLOCK"), Policy())
    assert c == replace(before, blocked_until_silence=False)
    assert actions == []
    c, actions = step(c, Event("AudioActive", True), Policy())
    assert any(a.value == "GRAB_DELAY" for a in actions)


@pytest.mark.parametrize(
    "event", [Event("DisconnectResult", "failed"), Event("TimerFired", "RELEASE")]
)
@pytest.mark.parametrize("connected", [False, True])
def test_release_completion_branches(event, connected):
    c = Context(
        state="releasing", device_connected=connected, sleeping=True, pending="grab"
    )
    changes = dict(state="on_pc" if connected else "released", pending="none")
    if connected:
        changes.update(
            routed=True, reason="disconnect_failed", last_error="disconnect_failed"
        )
    assert step(c, event, Policy()) == (
        replace(c, **changes),
        [
            *cancel("RELEASE"),
            Action("EmitError", "disconnect_failed"),
            *SLEEP_RELEASE,
            Action("RouteToDevice"),
            start("IDLE", 120000),
            transition("releasing", "on_pc", "disconnect_failed"),
        ]
        if connected
        else [*cancel("RELEASE"), transition("releasing", "released"), *SLEEP_RELEASE],
    )


def test_pending_grab_and_configured_timers():
    c = Context(state="releasing", pending="grab")
    c, actions = step(c, Event("DisconnectResult"), Policy(connect_timeout_seconds=23))
    assert c.state == "connecting"
    assert any(a.value == "CONNECT" and a.milliseconds == 23000 for a in actions)
    assert c.last_error == ""


def test_policy_import_has_no_gi():
    import ast
    import inspect

    from scambio.core import policy

    tree = ast.parse(inspect.getsource(policy))
    imports = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    assert not any(n and n.startswith("gi") for n in imports)


@pytest.mark.parametrize("value", ["", "org.bluez.Error.AlreadyConnected"])
@pytest.mark.parametrize("connected,sink", [(True, True), (True, False), (False, True)])
def test_connect_success_combinations(value, connected, sink):
    c = Context(
        state="connecting",
        device_connected=connected,
        sink_ready=sink,
        last_error="connect_failed",
    )
    c, actions = step(c, Event("ConnectResult", value), Policy())
    assert c.state == ("on_pc" if connected and sink else "connecting")
    if connected and sink:
        assert c.last_error == "" and c.routed
    else:
        assert any(a.kind == "StartTimer" and a.value == "SINK" for a in actions)


@pytest.mark.parametrize(
    "kind,reason",
    [
        ("Switch", "switch"),
        ("SetPriority", "priority"),
        ("Locked", "locked"),
        ("Sleep", "sleep"),
    ],
)
def test_pending_release_reasons(kind, reason):
    c, actions = step(Context(state="connecting"), Event(kind, True), Policy())
    assert (c.pending, c.pending_reason) == ("release", reason)
    assert not any(a.kind == "Disconnect" for a in actions)


@pytest.mark.parametrize(
    "event",
    [
        Event("AudioActive", True),
        Event("SetPriority", False),
        Event("Locked", False),
        Event("Sleep", False),
    ],
)
def test_released_automatic_triggers(event):
    c, actions = step(
        Context(state="released", audio_active=True), event, Policy(grab_delay_ms=0)
    )
    assert c.state == "released"
    assert any(
        a.kind == "StartTimer" and a.value == "GRAB_DELAY" and a.milliseconds == 0
        for a in actions
    )


@pytest.mark.parametrize(
    "state", ["released", "connecting", "on_pc", "releasing", "unavailable"]
)
def test_sleep_inhibitor_availability_every_state(state):
    c = Context(state=state, sleeping=True, pending="grab", routed=True)
    c, actions = step(c, Event("Availability", False), Policy())
    assert c.state == "unavailable" and not c.routed and c.pending == "none"
    assert any(a.kind == "ReleaseSleepInhibitor" for a in actions)
    assert {a.value for a in actions if a.kind == "CancelTimer"} == {
        "GRAB_DELAY",
        "IDLE",
        "CONNECT",
        "SINK",
        "RELEASE",
        "SLEEP",
        "RESUME",
    }


@pytest.mark.parametrize(
    "state", ["released", "connecting", "on_pc", "releasing", "unavailable"]
)
@pytest.mark.parametrize("blocked", [False, True])
def test_unblock_expiry_all_states(state, blocked):
    before = Context(
        state=state,
        blocked_until_silence=blocked,
        pending="release",
        pending_reason="locked",
        locked=True,
        sleeping=True,
        priority=True,
        last_error="sink_lost",
    )
    assert step(before, Event("TimerFired", "UNBLOCK"), Policy()) == (
        replace(before, blocked_until_silence=False),
        [],
    )


@pytest.mark.parametrize("seconds", [1, 10, 120])
def test_unblock_timer_duration_and_cancellation(seconds):
    before = Context(state="released", audio_active=True, blocked_until_silence=True)
    silent = replace(before, audio_active=False)
    assert step(
        before, Event("AudioActive", False), Policy(unblock_silence_seconds=seconds)
    ) == (silent, [start("UNBLOCK", seconds * 1000), *cancel("GRAB_DELAY")])
    assert step(silent, Event("AudioActive", True), Policy()) == (
        before,
        cancel("UNBLOCK"),
    )
    unblocked = replace(silent, blocked_until_silence=False)
    assert step(unblocked, Event("AudioActive", False), Policy()) == (
        unblocked,
        cancel("GRAB_DELAY"),
    )


def test_m8_stream_gap_keeps_block_until_continuous_silence():
    before = Context(
        state="on_pc",
        audio_active=True,
        device_connected=True,
        sink_ready=True,
        routed=True,
    )
    released = replace(
        before,
        state="released",
        device_connected=False,
        routed=False,
        blocked_until_silence=True,
        reason="external_disconnect",
    )
    assert step(before, Event("DeviceConnected", False), Policy()) == (
        released,
        [
            *cancel("IDLE", "SINK", "RESUME"),
            Action("RestoreRouting"),
            Action("PausePlayers", "release"),
            Action("ForgetPlayers"),
            transition("on_pc", "released", "external_disconnect"),
        ],
    )
    silent = replace(released, audio_active=False)
    assert step(released, Event("AudioActive", False), Policy()) == (
        silent,
        [start("UNBLOCK", 10000), *cancel("GRAB_DELAY")],
    )
    # At 2 s the executor has not emitted the 10 s deadline (integration below).
    assert step(silent, Event("AudioActive", True), Policy()) == (
        released,
        cancel("UNBLOCK"),
    )
    assert step(released, Event("TimerFired", "GRAB_DELAY"), Policy()) == (released, [])
    assert step(released, Event("AudioActive", False), Policy()) == (
        silent,
        [start("UNBLOCK", 10000), *cancel("GRAB_DELAY")],
    )
    cleared = replace(silent, blocked_until_silence=False)
    assert step(silent, Event("TimerFired", "UNBLOCK"), Policy()) == (cleared, [])
    audible = replace(cleared, audio_active=True)
    assert step(cleared, Event("AudioActive", True), Policy()) == (
        audible,
        [*cancel("UNBLOCK"), start("GRAB_DELAY", 500)],
    )
    assert step(audible, Event("TimerFired", "GRAB_DELAY"), Policy()) == (
        replace(
            audible,
            state="connecting",
            origin="self",
            reason="audio_started",
            held=True,
        ),
        [
            Action("PausePlayers", "grab"),
            *GRAB,
            transition("released", "connecting", "audio_started"),
        ],
    )


@pytest.mark.parametrize("state", ["on_pc", "connecting", "releasing"])
@pytest.mark.parametrize("active", [False, True])
def test_availability_loss_sets_block_from_audio(state, active):
    before = Context(
        state=state,
        audio_active=active,
        blocked_until_silence=not active,
        routed=True,
        pending="grab",
        sleeping=True,
    )
    assert step(before, Event("Availability", False), Policy()) == (
        replace(
            before,
            state="unavailable",
            routed=False,
            pending="none",
            blocked_until_silence=active,
        ),
        [
            *cancel("GRAB_DELAY", "IDLE", "CONNECT", "SINK", "RELEASE", "RESUME"),
            *(
                [Action("PausePlayers", "release"), Action("ForgetPlayers")]
                if active and state in {"on_pc", "releasing"}
                else []
            ),
            Action("RestoreRouting"),
            *SLEEP_RELEASE,
            transition(state, "unavailable"),
        ],
    )


@pytest.mark.parametrize("state", ["released", "unavailable"])
@pytest.mark.parametrize("blocked", [False, True])
def test_availability_loss_preserves_existing_block_in_other_states(state, blocked):
    before = Context(
        state=state, audio_active=not blocked, blocked_until_silence=blocked
    )
    expected = [
        *cancel("GRAB_DELAY", "IDLE", "CONNECT", "SINK", "RELEASE", "RESUME"),
        Action("RestoreRouting"),
    ]
    if state == "released":
        expected.append(transition("released", "unavailable"))
    assert step(before, Event("Availability", False), Policy()) == (
        replace(before, state="unavailable"),
        expected,
    )


def test_bluetooth_off_on_does_not_reconnect_active_audio():
    before = Context(
        state="on_pc", audio_active=True, device_connected=True, routed=True
    )
    unavailable = replace(
        before, state="unavailable", blocked_until_silence=True, routed=False
    )
    assert step(before, Event("Availability", False), Policy()) == (
        unavailable,
        [
            *cancel("GRAB_DELAY", "IDLE", "CONNECT", "SINK", "RELEASE", "RESUME"),
            Action("PausePlayers", "release"),
            Action("ForgetPlayers"),
            Action("RestoreRouting"),
            transition("on_pc", "unavailable"),
        ],
    )
    # If Connected is still cached, U1 may adopt it but never calls Connect.
    assert step(unavailable, Event("Availability", True), Policy()) == (
        replace(unavailable, state="connecting"),
        [start("SINK", 5000), transition("unavailable", "connecting")],
    )
    disconnected = replace(unavailable, device_connected=False)
    assert step(unavailable, Event("DeviceConnected", False), Policy()) == (
        disconnected,
        [],
    )
    released = replace(disconnected, state="released")
    assert step(disconnected, Event("Availability", True), Policy()) == (
        released,
        [transition("unavailable", "released")],
    )
    assert step(released, Event("AudioActive", True), Policy()) == (
        released,
        cancel("UNBLOCK"),
    )
    assert step(released, Event("TimerFired", "GRAB_DELAY"), Policy()) == (released, [])


@pytest.mark.parametrize(
    "event,changes,prefix,reason",
    [
        (Event("Locked", True), {"locked": True}, [], "locked"),
        (Event("Sleep", True), {"sleeping": True}, [start("SLEEP", 4000)], "sleep"),
        (Event("Switch"), {"priority": True}, [Action("SavePriority", True)], "switch"),
        (
            Event("SetPriority", True),
            {"priority": True},
            [Action("SavePriority", True)],
            "priority",
        ),
        (Event("TimerFired", "IDLE"), {}, [], "idle_timeout"),
    ],
)
def test_release_keeps_unblock_timer(event, changes, prefix, reason):
    before = Context(
        state="on_pc", audio_active=True, blocked_until_silence=True, routed=True
    )
    silent = replace(before, audio_active=False)
    assert step(before, Event("AudioActive", False), Policy()) == (
        silent,
        [start("UNBLOCK", 10000), start("IDLE", 120000)],
    )
    assert step(silent, event, Policy()) == (
        replace(silent, **changes, state="releasing", reason=reason, routed=False),
        [*prefix, *RELEASE, transition("on_pc", "releasing", reason)],
    )
