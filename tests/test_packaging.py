# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Fermich srl
"""Release metadata and repository licensing contracts."""

import subprocess
import sys
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path

from scambio import __version__

ROOT = Path(__file__).parents[1]


def test_version_matches_public_metadata():
    version = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    assert __version__ == version
    metadata = ET.parse(ROOT / "design/metainfo/app.scambio.Scambio.metainfo.xml")
    assert metadata.find("./releases/release").get("version") == version
    assert f"## [{version}] - " in (ROOT / "CHANGELOG.md").read_text()
    result = subprocess.run(
        [sys.executable, "-m", "scambio", "--version"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == version


def test_spdx_headers():
    names = subprocess.check_output(
        [
            "git",
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "src",
            "tests",
            "tools",
        ],
        cwd=ROOT,
        text=True,
    ).splitlines()
    for name in names:
        header = "\n".join((ROOT / name).read_text().splitlines()[:5])
        assert "SPDX-License-Identifier: GPL-3.0-or-later" in header, name
        assert "SPDX-FileCopyrightText: 2026 Fermich srl" in header, name
