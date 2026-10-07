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


def test_generic_install_preserves_shared_icon_theme_and_uninstalls(tmp_path):
    shared_theme = tmp_path / "usr/share/icons/hicolor/index.theme"
    shared_theme.parent.mkdir(parents=True)
    shared_theme.write_text("another package owns this")
    command = [sys.executable, str(ROOT / "tools/install.py")]
    subprocess.run(
        [
            *command,
            "install",
            "--prefix",
            "/usr",
            "--destdir",
            str(tmp_path),
            "--python-lib",
            "lib/python3/dist-packages",
            "--systemd",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert shared_theme.read_text() == "another package owns this"
    data = tmp_path / "usr/share/scambio"
    assert (data / "design/icons/hicolor/index.theme").exists()
    daemon = tmp_path / "usr/share/dbus-1/services/app.scambio.Scambio.service"
    assert "Exec=/usr/bin/scambio daemon\n" in daemon.read_text()
    assert "SystemdService=scambio.service\n" in daemon.read_text()
    assert "python3 -I -m scambio" in (tmp_path / "usr/bin/scambio").read_text()
    subprocess.run(
        [*command, "uninstall", "--prefix", "/usr", "--destdir", str(tmp_path)],
        check=True,
    )
    assert shared_theme.read_text() == "another package owns this"
    assert not daemon.exists()
    assert not (tmp_path / "usr/bin/scambio").exists()
