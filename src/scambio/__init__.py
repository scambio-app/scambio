# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Fermich srl
"""Scambio headless Bluetooth audio switcher."""

from importlib import import_module
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("scambio")
except PackageNotFoundError:
    __version__ = str(import_module("scambio._version").VERSION)
