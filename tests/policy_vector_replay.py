# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Fermich srl
"""Replay the shared JSON contract against the Linux implementation."""

from dataclasses import asdict

from scambio.config import Policy
from scambio.core.policy import Context, step
from tools.policy_vector_format import (
    VirtualClock,
    action_json,
    context_json,
    event_from_json,
    validate_document,
)


def replay(document: dict) -> int:
    validate_document(document)
    count = 0
    for vector in document["vectors"]:
        config = Policy(
            **dict(document["defaults"]["config"], **vector.get("config", {}))
        )
        initial = vector.get("initial", {})
        context = Context(
            **dict(document["defaults"]["context"], **initial.get("context", {}))
        )
        clock = VirtualClock(initial.get("timers"))
        for index, record in enumerate(vector["steps"]):
            where = f"{vector['id']} step {index}"
            event = event_from_json(record["event"])
            if vector["clock"] == "virtual":
                clock.before(record["t_ms"], record["event"])
            following, actions = step(context, event, config)
            actual_actions = [action_json(action) for action in actions]
            assert actual_actions == record["expect"]["actions"], where
            expected = dict(asdict(context), **record["expect"]["changes"])
            assert context_json(following) == expected, where
            if vector["clock"] == "virtual":
                # The executor acts on the implementation's actions, not expected JSON.
                clock.after(actual_actions)
            context = following
            count += 1
    return count
