# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Fermich srl
"""Finite U/T explorations from M01; no scheduler or hardware dependencies."""

import argparse
import inspect
import json
from collections import Counter, deque
from pathlib import Path
from time import perf_counter

from scambio.config import Policy
from scambio.core.policy import Context, Event, step

ROOT = Path(__file__).resolve().parents[1]
TIMERS = (
    "GRAB_DELAY",
    "IDLE",
    "CONNECT",
    "SINK",
    "RELEASE",
    "SLEEP",
    "UNBLOCK",
    "RESUME",
)
BOOLEAN_EVENTS = (
    "AudioActive",
    "DeviceConnected",
    "Locked",
    "Sleep",
    "SetPriority",
    "Availability",
    "AudioBackend",
)
BASE_EVENTS = tuple(
    Event(kind, value) for kind in BOOLEAN_EVENTS for value in (True, False)
) + (
    Event("DeviceSinkAppeared"),
    Event("DeviceSinkGone"),
    Event("Switch"),
    Event("ConnectResult"),
    Event("ConnectResult", "org.bluez.Error.AlreadyConnected"),
    Event("ConnectResult", "org.bluez.Error.InProgress"),
    Event("ConnectResult", "failed"),
    Event("DisconnectResult"),
    Event("DisconnectResult", "failed"),
)


def require_checkout() -> None:
    for symbol, relative in (
        (Context, "src/scambio/core/policy.py"),
        (Policy, "src/scambio/config.py"),
    ):
        if Path(inspect.getfile(symbol)).resolve() != ROOT / relative:
            raise RuntimeError("Use the checkout: PYTHONPATH=src:. or the make target")


def expected_fingerprints() -> dict:
    """Read the immutable normative table, not a second set of expected numbers."""
    result = {}
    for line in (ROOT / "docs/specs/M01-vectors/README.md").read_text().splitlines():
        cells = [cell.strip() for cell in line.split("|")[1:-1]]
        if cells and cells[0] in {"U", "T"}:
            keys = (
                "pairs",
                "contexts",
                "transitions",
                "actions",
                "released",
                "connecting",
                "on_pc",
                "releasing",
                "unavailable",
            )
            result[cells[0]] = {
                key: int(value.replace(" ", ""))
                for key, value in zip(keys, cells[2:], strict=True)
                if value != "—"
            }
    if set(result) != {"U", "T"}:
        raise ValueError("Missing normative U/T table")
    return result


def explore(model: str) -> dict:
    require_checkout()
    if model not in {"U", "T"}:
        raise ValueError(model)
    started = perf_counter()
    config = Policy()
    seeds = [(Context(priority=priority), 0) for priority in (False, True)]
    seen = set(seeds)
    queue = deque(seeds)
    contexts = {context for context, _ in seeds}
    transitions = actions_count = 0
    bits = {timer: 1 << i for i, timer in enumerate(TIMERS)}
    while queue:
        context, active = queue.popleft()
        events = BASE_EVENTS + tuple(
            Event("TimerFired", timer)
            for timer in TIMERS
            if model == "U" or active & bits[timer]
        )
        for event in events:
            mask = active
            if model == "T" and event.kind == "TimerFired":
                mask &= ~bits[event.value]
            following, actions = step(context, event, config)
            if model == "T":
                for action in actions:
                    if action.kind == "StartTimer":
                        mask |= bits[action.value]
                    elif action.kind == "CancelTimer":
                        mask &= ~bits[action.value]
            transitions += 1
            actions_count += len(actions)
            key = (following, mask)
            if key not in seen:
                seen.add(key)
                queue.append(key)
                contexts.add(following)
    return dict(
        pairs=len(seen),
        contexts=len(contexts),
        transitions=transitions,
        actions=actions_count,
        **Counter(context.state for context in contexts),
        malformed_contexts=sum(
            c.pending == "release" and not c.pending_reason for c in contexts
        ),
        seconds=round(perf_counter() - started, 3),
    )


def verify(model: str, actual: dict) -> None:
    expected = expected_fingerprints()[model]
    observed = {key: actual[key] for key in expected}
    if observed != expected or actual["malformed_contexts"]:
        raise ValueError(f"STOP {model}: expected {expected}, observed {actual}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=("U", "T", "all"), default="all")
    args = parser.parse_args()
    for model in ("U", "T") if args.model == "all" else (args.model,):
        result = explore(model)
        print(json.dumps({model: result}, sort_keys=True), flush=True)
        verify(model, result)


if __name__ == "__main__":
    main()
