"""CLI harness with a test name and fail-closed private bus checks."""

import os

import scambio.api

for key in ("DBUS_SYSTEM_BUS_ADDRESS", "DBUS_SESSION_BUS_ADDRESS"):
    assert "dbusmock_data_" in os.environ[key], f"Unsafe bus: {key}"
scambio.api.BUS_NAME = "app.scambio.Test"
from scambio.cli import main  # noqa: E402

raise SystemExit(main())
