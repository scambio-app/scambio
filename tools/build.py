# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Fermich srl
"""Generate the offline version fallback from package metadata."""

from pathlib import Path

from setuptools.command.build_py import build_py


class BuildPy(build_py):
    def run(self):
        super().run()
        if self.editable_mode:
            return
        target = Path(self.build_lib) / "scambio/_version.py"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            "# Generated from pyproject.toml; do not edit.\n"
            + f"VERSION = {self.distribution.get_version()!r}\n"
        )
