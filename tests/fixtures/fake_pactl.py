#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Fermich srl
"""Controllable blocking event source. Never invokes a real audio backend."""

import json
import os
import signal
import sys
from pathlib import Path

root = Path(sys.argv[1])
args = sys.argv[2:]
with (root / "calls").open("a") as log:
    log.write(
        json.dumps(
            {"args": args, "locale": os.environ.get("LC_ALL"), "pid": os.getpid()}
        )
        + "\n"
    )
state = json.loads((root / "snapshot.json").read_text())
if " ".join(args) in state.get("hang_commands", []):
    signal.pause()
if args == ["--version"]:
    print("pactl " + state.get("version", "16.1"))
elif args == ["-f", "json", "subscribe"]:
    if state.get("down"):
        sys.exit(1)
    fd = os.open(root / "events", os.O_RDWR)
    (root / "subscriber.pid").write_text(str(os.getpid()))
    while True:
        data = os.read(fd, 65536)
        if data == b"EXIT":
            break
        os.write(1, data)
elif state.get("down"):
    sys.exit(1)
elif args == ["-f", "json", "list", "sink-inputs"]:
    print(json.dumps(state["streams"]))
elif args == ["-f", "json", "list", "sinks"]:
    print(json.dumps(state["sinks"]))
elif args == ["get-default-sink"]:
    print(state["default"])
else:
    if state.get("fail_route"):
        sys.exit(1)
    if args[0] == "set-default-sink":
        state["default"] = args[1]
    elif args[0] == "move-sink-input":
        index = next(s["index"] for s in state["sinks"] if s["name"] == args[2])
        for stream in state["streams"]:
            if str(stream["index"]) == args[1]:
                stream["sink"] = index
    else:
        sys.exit(2)
    tmp = root / f"snapshot-{os.getpid()}.tmp"
    tmp.write_text(json.dumps(state))
    tmp.replace(root / "snapshot.json")
