# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Fermich srl
"""Reproducibility, replay and malformed-input contract for shared Mac vectors."""

import copy
import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from policy_vector_replay import replay

from scambio.core.policy import Action, Context, Event
from tools import export_policy_vectors as export
from tools.policy_fingerprints import BASE_EVENTS, TIMERS, explore, verify
from tools.policy_vector_format import (
    ROOT,
    VirtualClock,
    action_json,
    context_json,
    event_from_json,
    event_json,
    read_document,
    validate_document,
    validate_schema,
)

VECTOR_DIR = ROOT / "tests/vectors"
SEED_DIR = ROOT / "docs/specs/M01-vectors"
CORPUS_FILES = (
    VECTOR_DIR / "policy-v1.json",
    *sorted(VECTOR_DIR.glob("policy-walks-v1-*.json")),
)
SEED_FILES = tuple(sorted(SEED_DIR.glob("flow.*.json"))) + tuple(
    sorted(SEED_DIR.glob("rule.*.json"))
)


def test_policy_regeneration() -> None:
    saved = read_document(VECTOR_DIR / "policy-v1.json")
    source = saved["source"]
    assert source == export.source_metadata(source["commit"])
    export.verify_source(source["commit"])
    regenerated = export.generate_policy(source)
    assert regenerated == saved
    assert export.serialize(regenerated) == (VECTOR_DIR / "policy-v1.json").read_text()
    assert "platform" not in saved


@pytest.mark.parametrize("chunk", range(export.WALKS // export.CHUNK_SIZE))
def test_walk_regeneration(chunk: int) -> None:
    path = VECTOR_DIR / f"policy-walks-v1-{chunk:02d}.json"
    saved = read_document(path)
    source = read_document(VECTOR_DIR / "policy-v1.json")["source"]
    regenerated = export.generate_walks(source, chunk * export.CHUNK_SIZE)
    assert regenerated == saved
    assert export.serialize(regenerated, compact=True) == path.read_text()
    assert "platform" not in saved


@pytest.mark.parametrize("path", CORPUS_FILES + SEED_FILES, ids=lambda path: path.name)
def test_replay(path: Path) -> None:
    assert replay(read_document(path)) > 0


def test_corpus_inventory_coverage_and_expansion() -> None:
    assert len(CORPUS_FILES) == 1 + export.WALKS // export.CHUNK_SIZE
    assert len(SEED_FILES) == 4
    identifiers = set()
    covered = set()
    starts = {False: 0, True: 0}
    steps = 0
    for path in CORPUS_FILES[1:]:
        data = read_document(path)
        assert len(path.read_bytes()) < 5_000_000
        assert data["source"]["coverage"] == export.coverage(data["vectors"])
        assert data["source"]["seed"] == export.SEED
        covered.update(data["source"]["coverage"]["state_event"])
        for vector in data["vectors"]:
            assert vector["id"] not in identifiers
            identifiers.add(vector["id"])
            priority = vector["initial"]["context"]["priority"]
            assert vector["initial"]["context"] == context_json(
                Context(priority=priority)
            )
            starts[priority] += 1
            assert len(vector["steps"]) == export.STEPS
            steps += len(vector["steps"])
    assert starts == {False: 1000, True: 1000}
    assert steps == 120_000
    required = {
        f"{state}/{kind}"
        for state in ("released", "connecting", "on_pc", "releasing", "unavailable")
        for kind in {e.kind for e in BASE_EVENTS} | {"TimerFired"}
    }
    assert covered == required

    vectors = read_document(CORPUS_FILES[0])["vectors"]
    expanded = [v for v in vectors if "pending_reason espanso:" in v.get("origin", "")]
    assert len(expanded) == 76
    groups = {}
    for vector in expanded:
        base, reason = vector["id"].rsplit(".reason-", 1)
        groups.setdefault(base, set()).add(reason)
        assert vector["origin"].endswith(f" (pending_reason espanso: {reason})")
        assert vector["initial"]["context"]["pending_reason"] == reason
    assert len(groups) == 19
    assert all(reasons == set(export.REASONS) for reasons in groups.values())
    calls = export.captured_cases()
    assert sum(len(call_list) for _, _, call_list in calls) == 337
    assert len([v for v in vectors if v["clock"] == "none"]) == 337 - 19 + 76
    assert (
        sum(
            origin.startswith("tests/test_policy.py::test_rules[")
            for _, origin, _ in calls
        )
        == 68
    )


@pytest.mark.policy_fingerprints
@pytest.mark.parametrize("model", ["U", "T"])
def test_normative_fingerprint(model: str) -> None:
    actual = explore(model)
    print(model, json.dumps(actual, sort_keys=True))
    verify(model, actual)
    assert actual["malformed_contexts"] == 0


@pytest.mark.parametrize("kind", ["Switch", "DeviceSinkAppeared", "DeviceSinkGone"])
def test_ignored_event_values(kind: str) -> None:
    assert event_json(Event(kind, "bt")) == {"type": kind}


@pytest.mark.parametrize(
    "kind,raw,result",
    [
        ("ConnectResult", "", "ok"),
        ("ConnectResult", "org.bluez.Error.AlreadyConnected", "already_connected"),
        ("ConnectResult", "org.bluez.Error.InProgress", "in_progress"),
        ("ConnectResult", "org.bluez.Error.Failed", "failed"),
        ("DisconnectResult", "", "ok"),
        ("DisconnectResult", "org.bluez.Error.AlreadyConnected", "failed"),
    ],
)
def test_result_mapping(kind: str, raw: str, result: str) -> None:
    value = {"type": kind, "result": result}
    if result == "failed":
        value["detail"] = raw
    assert event_json(Event(kind, raw)) == value
    if result == "failed":
        value["detail"] = ""
        assert event_from_json(value).value == "failed"


@pytest.mark.parametrize(
    "action,expected",
    [
        (
            Action("StartTimer", "IDLE", 1000),
            {"type": "StartTimer", "timer": "IDLE", "ms": 1000},
        ),
        (Action("CancelTimer", "IDLE"), {"type": "CancelTimer", "timer": "IDLE"}),
        (Action("SavePriority", True), {"type": "SavePriority", "value": True}),
        (
            Action("EmitError", "connect_failed"),
            {"type": "EmitError", "code": "connect_failed"},
        ),
        (Action("PausePlayers", "grab"), {"type": "PausePlayers", "kind": "grab"}),
        (
            Action("EmitTransition", transition=("released", "connecting", "switch")),
            {
                "type": "EmitTransition",
                "from": "released",
                "to": "connecting",
                "reason": "switch",
            },
        ),
    ],
)
def test_action_mapping(action: Action, expected: dict) -> None:
    assert action_json(action) == expected


def simple_document() -> dict:
    return copy.deepcopy(read_document(SEED_DIR / "rule.c7.external-sink-timeout.json"))


@pytest.mark.parametrize(
    "mutation",
    [
        lambda d: d.update(format="unknown"),
        lambda d: d.update(version=True),
        lambda d: d.update(version=2),
        lambda d: d.update(platform="unknown"),
        lambda d: d.update(extra=0),
        lambda d: d["source"].update(commit="not-a-commit"),
        lambda d: d["vectors"].append(copy.deepcopy(d["vectors"][0])),
        lambda d: d["defaults"]["config"].update(release_idle_seconds=9),
        lambda d: d["vectors"][0].update(config={"sink_timeout_seconds": 31}),
        lambda d: d["defaults"]["context"].update(pending="release", pending_reason=""),
        lambda d: d["vectors"][0]["initial"]["context"].update(
            pending="release", pending_reason=""
        ),
        lambda d: d["vectors"][0]["initial"].update(timers={}),
        lambda d: d["vectors"][0]["steps"][0]["expect"]["changes"].update(
            priority=False
        ),
        lambda d: d["vectors"][0]["steps"][0]["expect"]["changes"].update(
            pending="release"
        ),
        lambda d: d["vectors"][0]["steps"][0]["event"].update(value=True),
        lambda d: d["defaults"]["context"].update(automations=True),
        lambda d: d["vectors"][0]["steps"][0].update(
            event={"type": "Switch", "source": "menu"}
        ),
        lambda d: d["vectors"][0]["steps"][0].update(
            event={"type": "SetAutomations", "value": True}
        ),
        lambda d: d["vectors"][0].update(clock="virtual"),
    ],
)
def test_malformed_documents_fail(mutation: object) -> None:
    data = simple_document()
    mutation(data)
    with pytest.raises(ValueError):
        replay(data)


def test_clock_rules_and_action_order() -> None:
    clock = VirtualClock({"SINK": 10, "IDLE": 10})
    clock.before(10, {"type": "Switch"})  # An external event may win a tie.
    clock.after([{"type": "CancelTimer", "timer": "SINK"}])
    clock.before(10, {"type": "TimerFired", "timer": "IDLE"})
    assert clock.timers == {}
    clock.after([{"type": "StartTimer", "timer": "RESUME", "ms": 0}])
    clock.before(10, {"type": "TimerFired", "timer": "RESUME"})
    assert clock.timers == {}
    clock.after(
        [
            {"type": "StartTimer", "timer": "SINK", "ms": 5},
            {"type": "StartTimer", "timer": "SINK", "ms": 9},
        ]
    )
    assert clock.timers == {"SINK": 19}
    with pytest.raises(ValueError, match="deadline"):
        clock.before(20, {"type": "Switch"})
    with pytest.raises(ValueError, match="premature"):
        clock.before(18, {"type": "TimerFired", "timer": "SINK"})
    with pytest.raises(ValueError, match="Non-monotonic"):
        clock.before(9, {"type": "Switch"})
    with pytest.raises(ValueError):
        clock.before(True, {"type": "Switch"})


@pytest.mark.parametrize(
    "change", ["early", "late", "backward", "inactive", "negative", "float", "missing"]
)
def test_replay_rejects_bad_virtual_time(change: str) -> None:
    data = read_document(SEED_DIR / "flow.m8-gap-keeps-block.json")
    steps = data["vectors"][0]["steps"]
    if change == "early":
        steps[4]["t_ms"] = 13999
    elif change == "late":
        steps[4]["t_ms"] = 14001
    elif change == "backward":
        steps[2]["t_ms"] = 49
    elif change == "inactive":
        steps[4]["event"]["timer"] = "SINK"
    elif change == "negative":
        steps[0]["t_ms"] = -1
    elif change == "float":
        steps[0]["t_ms"] = 0.5
    else:
        del steps[0]["t_ms"]
    with pytest.raises(ValueError):
        replay(data)


def test_json_values_and_diagnostics() -> None:
    data = simple_document()
    data["version"] = 1.0  # Equal JSON numeric value, different spelling.
    data["vectors"][0].update(note="ignored", rules=["anything"], origin="diagnostic")
    data["vectors"][0]["steps"][0]["t_ms"] = 123  # ignored with clock none
    assert replay(json.loads(json.dumps(data, sort_keys=True))) == 1
    data["vectors"][0]["steps"][0]["expect"]["actions"].reverse()
    with pytest.raises(AssertionError):
        replay(data)


def test_reject_malformed_context_at_export_boundary() -> None:
    with pytest.raises(ValueError):
        context_json(replace(Context(), pending="release"))


def test_no_gi_in_standalone_exporter() -> None:
    script = """
import sys
class NoGi:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'gi' or fullname.startswith('gi.'):
            raise AssertionError('gi imported')
sys.meta_path.insert(0, NoGi())
from tools.export_policy_vectors import explicit_vectors, generate_walk
assert len(explicit_vectors()) == 394
generate_walk(0)
assert 'gi' not in sys.modules
"""
    subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        cwd=ROOT,
        env=dict(os.environ, PYTHONPATH=f"{ROOT / 'src'}:{ROOT}"),
    )


def test_duplicate_json_keys_and_nonfinite_numbers_fail(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    for content in ('{"version":1,"version":1}', '{"version":NaN}'):
        path.write_text(content)
        with pytest.raises(ValueError):
            read_document(path)
    with pytest.raises(ValueError, match="Unsupported"):
        validate_schema({}, {"not": {}})
    with pytest.raises(ValueError, match="Unsupported"):
        validate_schema({}, {"oneOf": [{"not": {}}, {"type": "object"}]})
    assert set(TIMERS) == set(
        json.loads((SEED_DIR / "schema.json").read_text())["$defs"]["timer"]["enum"]
    )
    validate_document(simple_document())
