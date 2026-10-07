# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Fermich srl
"""Resolve checkout and installed assets without writing outside application data."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def data_dir() -> Path:
    if override := os.environ.get("SCAMBIO_DATA_DIR"):
        return Path(override).resolve()
    if (ROOT / "pyproject.toml").is_file() and (ROOT / "src").is_dir():
        return ROOT
    for prefix in (Path("/app"), Path(sys.prefix), Path("/usr")):
        candidate = prefix / "share/scambio"
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError("Scambio data directory is missing")


def _checkout() -> bool:
    return (
        not os.environ.get("SCAMBIO_DATA_DIR")
        and (ROOT / "pyproject.toml").is_file()
        and (ROOT / "src").is_dir()
    )


def design_dir() -> Path:
    if override := os.environ.get("SCAMBIO_DESIGN_DIR"):
        return Path(override).resolve()
    return data_dir() / "design"


def locale_dir() -> Path:
    if override := os.environ.get("SCAMBIO_LOCALE_DIR"):
        return Path(override).resolve()
    return data_dir() / ("build/locale" if _checkout() else "locale")


def ui_file() -> Path:
    return data_dir() / (
        "build/ui/settings-window.ui" if _checkout() else "ui/settings-window.ui"
    )


def user_config_dir() -> Path:
    from gi.repository import GLib

    return Path(GLib.get_user_config_dir()) / "scambio"


def user_data_dir() -> Path:
    from gi.repository import GLib

    return Path(GLib.get_user_data_dir()) / "scambio"
