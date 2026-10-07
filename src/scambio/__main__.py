# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Fermich srl
"""python -m scambio runs the daemon."""

import sys

from scambio.cli import main

raise SystemExit(main(sys.argv[1:] or ["daemon"]))
