"""python -m scambio runs the daemon."""

import sys

from scambio.cli import main

raise SystemExit(main(sys.argv[1:] or ["daemon"]))
