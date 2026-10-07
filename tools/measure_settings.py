# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Fermich srl
"""One RSS sample of the real settings window on private buses and Xvfb."""

import argparse
import hashlib
import json
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tests"))
from test_window import run_window  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="scambio-window-") as root:
        result = run_window(Path(root))
    if result.returncode or "Traceback" in result.stderr:
        raise RuntimeError(result.stdout + result.stderr)
    evidence = json.loads(result.stdout.strip().splitlines()[-1])
    evidence["measured_utc"] = datetime.now(UTC).isoformat()
    evidence["method"] = (
        "/proc/self/stat RSS, open real GTK window after integration checks; "
        "includes in-process dbusmock and harness imports; GSK_RENDERER=cairo; "
        "GTK_A11Y=none; temporary HOME; no installed services activatable"
    )
    evidence["source_sha256"] = {
        name: hashlib.sha256((REPO / name).read_bytes()).hexdigest()
        for name in (
            "src/scambio/ui/window.py",
            "src/scambio/ui/settings_model.py",
            "src/scambio/ui/client.py",
            "tests/fixtures/run_settings.py",
            "tests/test_window.py",
        )
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
