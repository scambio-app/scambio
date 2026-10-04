"""python -m scambio runs the daemon."""

import sys

from scambio.cli import main

raise SystemExit(main(["daemon", *sys.argv[1:]]))
