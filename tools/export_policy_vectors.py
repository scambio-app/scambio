# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Fermich srl
"""Export deterministic M01 vectors. Run with PYTHONPATH=src:. (no gi)."""

import argparse
import itertools
import json
import random
import subprocess
import sys
from collections import Counter
from dataclasses import asdict, replace
from pathlib import Path
from types import ModuleType

from scambio.config import Policy
from scambio.core.policy import Context, Event, step
from tools.policy_fingerprints import BASE_EVENTS, TIMERS, require_checkout
from tools.policy_vector_format import (
    ROOT,
    VirtualClock,
    action_json,
    context_json,
    event_json,
    validate_document,
)

# Provisional; GM owns the final license choice for the shared vectors.
VECTOR_LICENSE = "GPL-3.0-or-later"
SEED = 121217
WALKS = 2000
STEPS = 60
CHUNK_SIZE = 200
REASONS = ("switch", "priority", "locked", "sleep")
DEFAULT_POLICY = Policy()
SOURCE_PATHS = (
    "src/scambio/core/policy.py",
    "src/scambio/config.py",
    "tests/test_policy.py",
    "tests/test_policy_players.py",
)


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def source_metadata(commit: str | None = None) -> dict:
    commit = git("rev-parse", "--verify", f"{commit or 'HEAD'}^{{commit}}")
    # No timestamps or HEAD lookups during pure regeneration: callers can reuse source.
    return {
        "repo": "scambio-linux",
        "commit": commit,
        "generator": (
            "tools/export_policy_vectors.py:v1; "
            f"SPDX-License-Identifier: {VECTOR_LICENSE}; "
            "SPDX-FileCopyrightText: 2026 Fermich srl"
        ),
        "generated_at": git("show", "-s", "--format=%cI", commit),
        "license": VECTOR_LICENSE,
    }


def verify_source(commit: str) -> None:
    require_checkout()
    for name in SOURCE_PATHS:
        content = subprocess.check_output(["git", "show", f"{commit}:{name}"], cwd=ROOT)
        if content != (ROOT / name).read_bytes():
            raise ValueError(
                f"Source differs from {commit}: {name}; commit before export"
            )


def document(vectors: list[dict], source: dict) -> dict:
    return {
        "format": "scambio-policy-vectors",
        "version": 1,
        "source": dict(source),
        "defaults": {"config": asdict(Policy()), "context": context_json(Context())},
        "vectors": vectors,
    }


def record_step(context: Context, event: Event, config: Policy) -> tuple[Context, dict]:
    before = context_json(context)
    following, actions = step(context, event, config)
    after = context_json(following)
    return following, {
        "event": event_json(event),
        "expect": {
            "actions": [action_json(action) for action in actions],
            "changes": {
                key: value for key, value in after.items() if value != before[key]
            },
        },
    }


def test_modules() -> list[ModuleType]:
    """Execute isolated copies without conftest or mutating pytest modules."""
    modules = []
    previous = sys.modules.get("test_policy")
    try:
        for name in ("test_policy", "test_policy_players"):
            path = ROOT / "tests" / f"{name}.py"
            module = ModuleType(name)
            module.__file__ = str(path)
            exec(compile(path.read_bytes(), str(path), "exec"), module.__dict__)
            modules.append(module)
            if name == "test_policy":
                sys.modules[name] = module
    finally:
        if previous is None:
            sys.modules.pop("test_policy", None)
        else:
            sys.modules["test_policy"] = previous
    return modules


def parameter_cases(function: object) -> list[tuple[dict, str]]:
    """The current fixtures use public parametrize marks and plain value lists."""
    dimensions = []
    for mark in getattr(function, "pytestmark", []):
        if mark.name != "parametrize":
            raise ValueError(f"Unsupported fixture mark: {mark.name}")
        names = [name.strip() for name in mark.args[0].split(",")]
        rows = []
        for index, values in enumerate(mark.args[1]):
            values = (values,) if len(names) == 1 else values
            ids = mark.kwargs.get("ids")
            label = (
                ids[index]
                if ids
                else "-".join(
                    str(value)
                    if isinstance(value, (str, int, float, bool)) or value is None
                    else f"{name}{index}"
                    for name, value in zip(names, values, strict=True)
                )
            )
            rows.append((dict(zip(names, values, strict=True)), label))
        dimensions.append(rows)
    return [
        (
            {key: value for values, _ in combination for key, value in values.items()},
            "-".join(label for _, label in combination),
        )
        for combination in itertools.product(*dimensions)
    ]


def captured_cases() -> list[tuple[str, str, list]]:
    result = []
    for module in test_modules():
        for name, function in list(vars(module).items()):
            if not name.startswith("test_") or name in {
                "test_exhaustive_six_events",
                "test_policy_import_has_no_gi",
            }:
                continue
            for index, (arguments, label) in enumerate(parameter_cases(function)):
                calls = []

                def capture(
                    context: Context, event: Event, config: Policy, calls: list = calls
                ) -> tuple:
                    calls.append((context, event, config))
                    return step(context, event, config)

                module.step = capture
                function(**arguments)
                origin = f"tests/{module.__name__}.py::{name}" + (
                    f"[{label}]" if label else ""
                )
                identifier = f"case.{module.__name__}.{name}.{index:03d}"
                result.append((identifier, origin, calls))
    return result


def explicit_vectors() -> list[dict]:
    vectors = []
    for identifier, origin, calls in captured_cases():
        for index, (context, event, config) in enumerate(calls):
            reasons = (
                REASONS
                if context.pending == "release" and not context.pending_reason
                else (None,)
            )
            for reason in reasons:
                initial = replace(context, pending_reason=reason) if reason else context
                _, record = record_step(initial, event, config)
                vectors.append(
                    {
                        "id": f"{identifier}.step-{index:02d}"
                        + (f".reason-{reason}" if reason else ""),
                        "origin": origin
                        + (f" (pending_reason espanso: {reason})" if reason else ""),
                        "clock": "none",
                        "config": asdict(config),
                        "initial": {"context": context_json(initial)},
                        "steps": [record],
                    }
                )
    return vectors


def virtual_flow(
    identifier: str,
    origin: str,
    context: Context,
    events: list,
    config: Policy = DEFAULT_POLICY,
    timers: dict | None = None,
) -> dict:
    clock = VirtualClock(timers)
    initial = {"context": context_json(context)}
    if timers:
        initial["timers"] = dict(timers)
    records = []
    for at, event in events:
        clock.before(at, event_json(event))
        context, record = record_step(context, event, config)
        record["t_ms"] = at
        clock.after(record["expect"]["actions"])
        records.append(record)
    return {
        "id": identifier,
        "origin": origin,
        "clock": "virtual",
        "note": "Tempi virtuali illustrativi, non misure hardware.",
        "initial": initial,
        "config": asdict(config),
        "steps": records,
    }


def flow_vectors() -> list[dict]:
    pc = Context(
        state="on_pc",
        audio_active=True,
        device_connected=True,
        sink_ready=True,
        routed=True,
    )
    return [
        virtual_flow(
            "flow.m8",
            "tests/test_policy.py::test_m8_stream_gap_keeps_block_until_continuous_silence",
            pc,
            [
                (0, Event("DeviceConnected", False)),
                (50, Event("AudioActive", False)),
                (2050, Event("AudioActive", True)),
                (4000, Event("AudioActive", False)),
                (14000, Event("TimerFired", "UNBLOCK")),
                (20000, Event("AudioActive", True)),
                (20500, Event("TimerFired", "GRAB_DELAY")),
            ],
        ),
        virtual_flow(
            "flow.bluetooth-off-on",
            "tests/test_policy.py::test_bluetooth_off_on_does_not_reconnect_active_audio",
            replace(pc, sink_ready=False),
            [
                (0, Event("Availability", False)),
                (50, Event("DeviceConnected", False)),
                (2000, Event("Availability", True)),
                (2050, Event("AudioActive", True)),
            ],
        ),
        virtual_flow(
            "flow.bluetooth-cached-connected",
            "tests/test_policy.py::test_bluetooth_off_on_does_not_reconnect_active_audio",
            replace(pc, sink_ready=False),
            [
                (0, Event("Availability", False)),
                (2000, Event("Availability", True)),
            ],
        ),
        virtual_flow(
            "flow.switch-during-grab",
            "tests/test_policy_players.py::test_switch_during_grab_and_double_switch_release",
            Context(state="released", audio_active=True),
            [
                (500, Event("TimerFired", "GRAB_DELAY")),
                (600, Event("AudioActive", False)),
                (650, Event("Switch")),
                (1700, Event("DeviceConnected", True)),
                (2200, Event("DeviceSinkAppeared")),
                (2300, Event("Switch")),
                (4590, Event("DisconnectResult")),
                (4600, Event("DeviceConnected", False)),
                (6000, Event("DeviceConnected", True)),
                (8000, Event("TimerFired", "RESUME")),
            ],
            Policy(resume_delay_ms=2000),
            {"GRAB_DELAY": 500},
        ),
        virtual_flow(
            "flow.double-switch",
            "tests/test_policy_players.py::test_double_switch_waits_for_disconnect_signal",
            replace(pc, origin="self"),
            [
                (0, Event("Switch")),
                (120, Event("AudioActive", False)),
                (167, Event("Switch")),
                (2390, Event("DisconnectResult")),
                (2396, Event("DeviceSinkGone")),
                (2405, Event("DeviceConnected", False)),
                (3090, Event("ConnectResult")),
                (3101, Event("DeviceConnected", True)),
                (3720, Event("DeviceSinkAppeared")),
                (5720, Event("TimerFired", "RESUME")),
            ],
            Policy(resume_delay_ms=2000),
        ),
    ]


def generate_policy(source: dict) -> dict:
    return document(explicit_vectors() + flow_vectors(), source)


def generate_walk(index: int) -> dict:
    rng = random.Random(f"{SEED}:{index}")
    context = Context(priority=bool(index % 2))
    initial = context_json(context)
    clock = VirtualClock()
    records = []
    for _ in range(STEPS):
        at = clock.now + rng.choice((0, 1, 50, 200, 500, 2000, 10000, 120000))
        event = rng.choice(BASE_EVENTS)
        if clock.timers and min(clock.timers.values()) <= at:
            at = min(clock.timers.values())
            due = [timer for timer in TIMERS if clock.timers.get(timer) == at]
            event = Event("TimerFired", rng.choice(due))
        clock.before(at, event_json(event))
        context, record = record_step(context, event, Policy())
        record["t_ms"] = at
        clock.after(record["expect"]["actions"])
        records.append(record)
    return {
        "id": f"walk.{index:04d}",
        "origin": f"random walk {index}, seed {SEED}:{index}",
        "clock": "virtual",
        "initial": {"context": initial},
        "steps": records,
    }


def coverage(vectors: list[dict]) -> dict:
    counts = Counter()
    timers = Counter()
    for vector in vectors:
        state = vector["initial"]["context"]["state"]
        for record in vector["steps"]:
            event = record["event"]
            counts[f"{state}/{event['type']}"] += 1
            if event["type"] == "TimerFired":
                timers[f"{state}/{event['timer']}"] += 1
            state = record["expect"]["changes"].get("state", state)
    return {
        "walks": len(vectors),
        "steps": sum(counts.values()),
        "state_event": dict(sorted(counts.items())),
        "state_timer": dict(sorted(timers.items())),
    }


def generate_walks(source: dict, start: int, count: int = CHUNK_SIZE) -> dict:
    vectors = [generate_walk(index) for index in range(start, start + count)]
    return document(vectors, dict(source, seed=SEED, coverage=coverage(vectors)))


def serialize(data: dict, compact: bool = False) -> str:
    if not compact:
        # JSON cannot carry header comments. Keep file-level provenance/SPDX metadata
        # in the schema's free-form generator string, visible in the first five lines.
        source = json.dumps(data["source"], ensure_ascii=False)
        body = {key: value for key, value in data.items() if key != "source"}
        return (
            '{\n  "source": '
            + source
            + ",\n"
            + json.dumps(body, ensure_ascii=False, indent=2)[2:]
            + "\n"
        )
    # One vector per line: plain JSON, bounded files, no compression.
    header = json.dumps(
        {key: value for key, value in data.items() if key != "vectors"},
        ensure_ascii=False,
    )
    return (
        header[:-1]
        + ', "vectors": [\n'
        + ",\n".join(
            json.dumps(vector, ensure_ascii=False, separators=(",", ":"))
            for vector in data["vectors"]
        )
        + "\n]}\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-commit", help="Defaults to HEAD; source files must match"
    )
    parser.add_argument("--output", type=Path, default=ROOT / "tests/vectors")
    args = parser.parse_args()
    source = source_metadata(args.source_commit)
    verify_source(source["commit"])
    output = [("policy-v1.json", generate_policy(source), False)]
    for chunk, start in enumerate(range(0, WALKS, CHUNK_SIZE)):
        output.append(
            (f"policy-walks-v1-{chunk:02d}.json", generate_walks(source, start), True)
        )
    covered = {
        key
        for _, data, compact in output
        if compact
        for key in data["source"]["coverage"]["state_event"]
    }
    required = {
        f"{state}/{kind}"
        for state in ("released", "connecting", "on_pc", "releasing", "unavailable")
        for kind in {e.kind for e in BASE_EVENTS} | {"TimerFired"}
    }
    if covered != required:
        raise ValueError(f"Missing state/event coverage: {required - covered}")
    # Validate everything, including clock legality, before writing any artifact.
    for _, data, _ in output:
        validate_document(data)
    args.output.mkdir(parents=True, exist_ok=True)
    for name, data, compact in output:
        content = serialize(data, compact)
        (args.output / name).write_text(content)
        print(f"{name}: {len(data['vectors'])} vectors, {len(content.encode())} bytes")


if __name__ == "__main__":
    main()
