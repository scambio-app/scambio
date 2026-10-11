# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Fermich srl
"""Shared JSON boundary and virtual clock for M01 tooling (stdlib only)."""

import json
import re
from dataclasses import asdict
from pathlib import Path

from scambio.core.policy import Action, Context, Event
from tools.policy_fingerprints import BOOLEAN_EVENTS

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "docs/specs/M01-vectors/schema.json").read_text())
CONNECT_RESULTS = {
    "": "ok",
    "org.bluez.Error.AlreadyConnected": "already_connected",
    "org.bluez.Error.InProgress": "in_progress",
}


class UnsupportedSchema(ValueError):
    """Schema evolution requires an explicit update of the validator."""


def is_integer(value: object) -> bool:
    # JSON Schema integers are numeric values, independent of their spelling.
    return type(value) is int or (type(value) is float and value.is_integer())


def context_json(context: Context) -> dict:
    if context.pending == "release" and not context.pending_reason:
        raise ValueError("pending release requires pending_reason")
    return asdict(context)


def event_json(event: Event) -> dict:
    result = {"type": event.kind}
    if event.kind in BOOLEAN_EVENTS:
        result["value"] = event.value
    elif event.kind == "TimerFired":
        result["timer"] = event.value
    elif event.kind in {"ConnectResult", "DisconnectResult"}:
        outcomes = CONNECT_RESULTS if event.kind == "ConnectResult" else {"": "ok"}
        result["result"] = outcomes.get(event.value, "failed")
        if result["result"] == "failed":
            result["detail"] = event.value
    elif event.kind not in {"Switch", "DeviceSinkAppeared", "DeviceSinkGone"}:
        raise ValueError(f"Unknown event: {event}")
    return result


def event_from_json(event: dict) -> Event:
    kind = event["type"]
    if kind in BOOLEAN_EVENTS:
        return Event(kind, event["value"])
    if kind == "TimerFired":
        return Event(kind, event["timer"])
    if kind in {"ConnectResult", "DisconnectResult"}:
        # detail is diagnostic only: it must never turn a failed result into success.
        outcomes = {value: key for key, value in CONNECT_RESULTS.items()}
        return Event(
            kind, "failed" if event["result"] == "failed" else outcomes[event["result"]]
        )
    return Event(kind)


def action_json(action: Action) -> dict:
    result = {"type": action.kind}
    if action.kind in {"StartTimer", "CancelTimer"}:
        result["timer"] = action.value
        if action.kind == "StartTimer":
            result["ms"] = action.milliseconds
    elif action.kind in {"SavePriority", "EmitError", "PausePlayers"}:
        key = {"SavePriority": "value", "EmitError": "code", "PausePlayers": "kind"}[
            action.kind
        ]
        result[key] = action.value
    elif action.kind == "EmitTransition":
        result.update(zip(("from", "to", "reason"), action.transition, strict=True))
    elif action.kind not in {
        "Connect",
        "Disconnect",
        "RouteToDevice",
        "RestoreRouting",
        "ReleaseSleepInhibitor",
        "ResumePlayers",
        "ForgetPlayers",
    }:
        raise ValueError(f"Unknown action: {action}")
    return result


class VirtualClock:
    """M01 §5.3.4: deadlines are absolute; events at a tie follow file order."""

    def __init__(self, timers: dict | None = None) -> None:
        self.timers = dict(timers or {})
        self.now = 0

    def before(self, at: int, event: dict) -> None:
        if not is_integer(at) or at < self.now or at < 0:
            raise ValueError("Non-monotonic or invalid t_ms")
        if any(deadline < at for deadline in self.timers.values()):
            raise ValueError("Timer deadline skipped")
        if event["type"] == "TimerFired":
            timer = event["timer"]
            if self.timers.get(timer) != at:
                raise ValueError(f"Inactive or premature TimerFired({timer})")
            del self.timers[timer]
        self.now = int(at)

    def after(self, actions: list[dict]) -> None:
        for action in actions:
            if action["type"] == "StartTimer":
                self.timers[action["timer"]] = self.now + action["ms"]
            elif action["type"] == "CancelTimer":
                self.timers.pop(action["timer"], None)


def validate_schema(value: object, schema: dict = SCHEMA, path: str = "$") -> None:
    """Interpret exactly the keywords used by the bundled schema, fail closed.

    This is deliberately not a general JSON Schema implementation. Unknown validation
    keywords fail, so a future M01 schema change cannot silently weaken validation.
    """
    supported = {
        "$schema",
        "$id",
        "$defs",
        "title",
        "$ref",
        "type",
        "const",
        "enum",
        "allOf",
        "anyOf",
        "oneOf",
        "if",
        "then",
        "required",
        "properties",
        "additionalProperties",
        "propertyNames",
        "items",
        "minItems",
        "minimum",
        "maximum",
        "pattern",
    }
    if schema.keys() - supported:
        raise UnsupportedSchema(
            f"Unsupported schema keywords: {schema.keys() - supported}"
        )

    def reject(reason: str) -> None:
        raise ValueError(f"{path}: {reason}")

    def matches(branch: dict) -> bool:
        try:
            validate_schema(value, branch, path)
        except UnsupportedSchema:
            raise
        except ValueError:
            return False
        return True

    if "$ref" in schema:
        reference = schema["$ref"]
        if not reference.startswith("#/$defs/"):
            reject("Non-local schema reference")
        validate_schema(value, SCHEMA["$defs"][reference.split("/")[-1]], path)
    if "type" in schema:
        types = {
            "object": dict,
            "array": list,
            "string": str,
            "integer": int,
            "boolean": bool,
        }
        valid_type = (
            is_integer(value)
            if schema["type"] == "integer"
            else type(value) is types[schema["type"]]
        )
        if not valid_type:
            reject(f"Expected {schema['type']}")
    if "const" in schema and (
        isinstance(value, bool) != isinstance(schema["const"], bool)
        or value != schema["const"]
    ):
        reject("Unexpected constant")
    if "enum" in schema and not any(
        isinstance(value, bool) == isinstance(item, bool) and value == item
        for item in schema["enum"]
    ):
        reject("Value outside enum")
    for branch in schema.get("allOf", []):
        validate_schema(value, branch, path)
    for keyword in ("anyOf", "oneOf"):
        if keyword in schema:
            count = sum(matches(branch) for branch in schema[keyword])
            if not count or (keyword == "oneOf" and count != 1):
                reject(keyword)
    if "if" in schema and matches(schema["if"]):
        validate_schema(value, schema["then"], path)
    if isinstance(value, dict):
        if set(schema.get("required", [])) - value.keys():
            reject("Missing required keys")
        properties = schema.get("properties", {})
        for key, item in value.items():
            if "propertyNames" in schema:
                validate_schema(key, schema["propertyNames"], path)
            if key in properties:
                validate_schema(item, properties[key], f"{path}.{key}")
            elif schema.get("additionalProperties") is False:
                reject(f"Unexpected key {key}")
            elif isinstance(schema.get("additionalProperties"), dict):
                validate_schema(item, schema["additionalProperties"], f"{path}.{key}")
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            reject("Too few items")
        if "items" in schema:
            for index, item in enumerate(value):
                validate_schema(item, schema["items"], f"{path}[{index}]")
    if type(value) in (int, float):
        if value < schema.get("minimum", value) or value > schema.get("maximum", value):
            reject("Number outside bounds")
    if (
        isinstance(value, str)
        and "pattern" in schema
        and not re.search(schema["pattern"], value)
    ):
        reject("Pattern mismatch")


def validate_document(document: dict) -> None:
    validate_schema(document)
    if document.get("platform", "shared") != "shared":
        raise ValueError("Linux replay accepts only shared vectors")
    seen = set()
    defaults = document["defaults"]["context"]
    if "automations" in defaults:
        raise ValueError("Mac field in shared context")
    context_json(Context(**defaults))
    for vector in document["vectors"]:
        if vector["id"] in seen:
            raise ValueError(f"Duplicate id: {vector['id']}")
        seen.add(vector["id"])
        initial = vector.get("initial", {})
        if "automations" in initial.get("context", {}):
            raise ValueError("Mac field in shared context")
        context = dict(defaults, **initial.get("context", {}))
        context_json(Context(**context))
        if vector["clock"] == "none" and "timers" in initial:
            raise ValueError("initial.timers forbidden with clock none")
        clock = VirtualClock(initial.get("timers"))
        for record in vector["steps"]:
            event = record["event"]
            if event["type"] == "SetAutomations" or "source" in event:
                raise ValueError("Mac event in shared vector")
            changes = record["expect"]["changes"]
            if "automations" in changes:
                raise ValueError("Mac field in shared context")
            if any(context[key] == value for key, value in changes.items()):
                raise ValueError("Redundant changes entry")
            context.update(changes)
            context_json(Context(**context))
            if vector["clock"] == "virtual":
                clock.before(record["t_ms"], event)
                clock.after(record["expect"]["actions"])


def read_document(path: Path) -> dict:
    def pairs(items: list) -> dict:
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    def invalid_constant(value: str) -> None:
        raise ValueError(f"Invalid JSON constant: {value}")

    return json.loads(
        path.read_text(), object_pairs_hook=pairs, parse_constant=invalid_constant
    )
