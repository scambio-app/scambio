"""Read assets from the checkout; test overrides never install theme files."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def design_dir() -> Path:
    return Path(os.environ.get("SCAMBIO_DESIGN_DIR", ROOT / "design")).resolve()


def locale_dir() -> Path:
    return Path(os.environ.get("SCAMBIO_LOCALE_DIR", ROOT / "build/locale")).resolve()
