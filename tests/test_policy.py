from dataclasses import replace

import pytest

from scambio.config import Policy
from scambio.core.policy import Context, Event, step

# One named case per table row; branches and procedures are checked below.
CASES = [
    (
        "G1",
        {"blocked_until_silence": True},
        Event("AudioActive", False),
        "unavailable",
        [],
    ),
    ("G2", {}, Event("DeviceSinkAppeared", "bt"), "unavailable", []),
    ("G3", {}, Event("Locked", True), "unavailable", []),
    ("G4", {}, Event("Sleep", True), "unavailable", ["StartTimer"]),
    ("G5", {}, Event("TimerFired", "SLEEP"), "unavailable", ["ReleaseSleepInhibitor"]),
    ("G6", {}, Event("SetPriority", True), "unavailable", ["SavePriority"]),
    (
        "G7",
        {"state": "released"},
        Event("Switch"),
        "connecting",
        ["SavePriority", "Connect"],
    ),
    (
        "G8",
        {"state": "on_pc", "sleeping": True},
        Event("Availability", False),
        "unavailable",
        ["RestoreRouting", "ReleaseSleepInhibitor"],
    ),
    ("G9", {"state": "on_pc"}, Event("AudioBackend", False), "on_pc", ["EmitError"]),
    (
        "G10",
        {"state": "releasing", "sleeping": True},
        Event("DisconnectResult"),
        "released",
        ["ReleaseSleepInhibitor"],
    ),
    ("G11", {}, Event("Availability", True), "released", ["EmitTransition"]),
    ("G12", {"state": "released"}, Event("ConnectResult"), "released", []),
    (
        "R1",
        {"state": "released"},
        Event("AudioActive", True),
        "released",
        ["StartTimer"],
    ),
    (
        "R2",
        {"state": "released"},
        Event("AudioActive", False),
        "released",
        ["CancelTimer"],
    ),
    (
        "R3",
        {"state": "released"},
        Event("Sleep", True),
        "released",
        ["ReleaseSleepInhibitor"],
    ),
    (
        "R4",
        {"state": "released", "audio_active": True},
        Event("TimerFired", "GRAB_DELAY"),
        "connecting",
        ["Connect"],
    ),
    (
        "R5",
        {"state": "released"},
        Event("DeviceConnected", True),
        "connecting",
        ["StartTimer"],
    ),
    ("R6", {"state": "released"}, Event("Switch"), "connecting", ["Connect"]),
    (
        "C1",
        {"state": "connecting"},
        Event("ConnectResult"),
        "connecting",
        ["StartTimer"],
    ),
    (
        "C2",
        {"state": "connecting"},
        Event("ConnectResult", "org.bluez.Error.InProgress"),
        "connecting",
        [],
    ),
    (
        "C3",
        {"state": "connecting", "device_connected": True},
        Event("DeviceSinkAppeared", "bt"),
        "on_pc",
        ["RouteToDevice"],
    ),
    (
        "C4",
        {"state": "connecting"},
        Event("ConnectResult", "org.bluez.Error.Failed"),
        "released",
        ["EmitError"],
    ),
    (
        "C5",
        {"state": "connecting"},
        Event("TimerFired", "CONNECT"),
        "releasing",
        ["Disconnect"],
    ),
    (
        "C6",
        {"state": "connecting", "origin": "self"},
        Event("TimerFired", "SINK"),
        "releasing",
        ["Disconnect"],
    ),
    (
        "C7",
        {"state": "connecting", "origin": "external"},
        Event("TimerFired", "SINK"),
        "on_pc",
        ["EmitError"],
    ),
    (
        "C8",
        {"state": "connecting", "origin": "self"},
        Event("DeviceConnected", False),
        "released",
        ["EmitError"],
    ),
    (
        "C9",
        {"state": "connecting"},
        Event("SetPriority", True),
        "connecting",
        ["SavePriority"],
    ),
    (
        "C10",
        {"state": "connecting", "pending": "release"},
        Event("Switch"),
        "connecting",
        ["SavePriority"],
    ),
    ("O1", {"state": "on_pc"}, Event("AudioActive", False), "on_pc", ["StartTimer"]),
    ("O2", {"state": "on_pc"}, Event("AudioActive", True), "on_pc", ["CancelTimer"]),
    (
        "O3",
        {"state": "on_pc"},
        Event("TimerFired", "IDLE"),
        "releasing",
        ["Disconnect"],
    ),
    ("O4", {"state": "on_pc"}, Event("Locked", True), "releasing", ["Disconnect"]),
    ("O5", {"state": "on_pc"}, Event("Sleep", True), "releasing", ["Disconnect"]),
    (
        "O6",
        {"state": "on_pc"},
        Event("Switch"),
        "releasing",
        ["Disconnect", "SavePriority"],
    ),
    ("O7", {"state": "on_pc"}, Event("SetPriority", True), "releasing", ["Disconnect"]),
    (
        "O8",
        {"state": "on_pc"},
        Event("DeviceConnected", False),
        "released",
        ["RestoreRouting"],
    ),
    (
        "O9",
        {"state": "on_pc", "device_connected": True},
        Event("DeviceSinkGone"),
        "on_pc",
        ["StartTimer"],
    ),
    (
        "O10",
        {"state": "on_pc"},
        Event("DeviceSinkAppeared", "bt"),
        "on_pc",
        ["RouteToDevice"],
    ),
    (
        "O11",
        {"state": "on_pc"},
        Event("TimerFired", "SINK"),
        "releasing",
        ["EmitError", "Disconnect"],
    ),
    (
        "L1",
        {"state": "releasing"},
        Event("DisconnectResult"),
        "released",
        ["CancelTimer"],
    ),
    (
        "L2",
        {"state": "releasing", "device_connected": True},
        Event("DisconnectResult", "failed"),
        "on_pc",
        ["EmitError", "RouteToDevice"],
    ),
    ("L3", {"state": "releasing"}, Event("Switch"), "releasing", ["SavePriority"]),
    (
        "L4",
        {"state": "releasing", "pending": "grab"},
        Event("Switch"),
        "releasing",
        ["SavePriority"],
    ),
    ("U1", {}, Event("Availability", True), "released", ["EmitTransition"]),
    ("U2", {}, Event("Switch"), "unavailable", ["EmitError"]),
]


@pytest.mark.parametrize(
    "rule,values,event,state,expected", CASES, ids=[r[0] for r in CASES]
)
def test_rules(rule, values, event, state, expected):
    original = Context(**values)
    c, actions = step(original, event, Policy())
    assert original == Context(**values)  # no mutation
    assert c.state == state
    names = [a.kind for a in actions]
    assert all(e in names for e in expected)
    if not expected:
        assert not actions
    if event.kind == "AudioActive":
        assert c.audio_active is event.value
        if not event.value:
            assert not c.blocked_until_silence
    if rule == "G2":
        assert c.sink_ready
    if rule == "G3":
        assert c.locked
    if rule == "G4":
        assert c.sleeping
    if rule in {"C10", "L4"}:
        assert c.pending == "none"
    if rule == "C9":
        assert (c.pending, c.pending_reason) == ("release", "priority")
    if rule == "L3":
        assert c.pending == "grab"
    if rule == "U2":
        assert c.priority == original.priority
        assert "SavePriority" not in names
    transitions = [a.transition for a in actions if a.kind == "EmitTransition"]
    assert bool(transitions) == (c.state != original.state)


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
    c, _ = step(c, Event("AudioActive", False), Policy())
    assert not c.blocked_until_silence
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
    c, actions = step(c, event, Policy())
    assert c.state == ("on_pc" if connected else "released")
    assert c.pending == "none"
    assert any(a.kind == "ReleaseSleepInhibitor" for a in actions)
    assert not any(a.kind == "Connect" for a in actions)


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
