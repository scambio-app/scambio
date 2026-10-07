# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Fermich srl
"""Public wire contract shared by client and service, without core imports."""

from importlib.resources import files

BUS_NAME = "app.scambio.Scambio"
PATH = "/app/scambio/Scambio"
INTERFACE = "app.scambio.Scambio1"
SETTINGS_BUS_NAME = "app.scambio.Scambio.Settings"
SETTINGS_PATH = "/app/scambio/Scambio/Settings"
SETTINGS_ACTIVE = SETTINGS_BUS_NAME + ".Active"


def introspection_xml() -> str:
    return files("scambio").joinpath("core/dbus/app.scambio.Scambio1.xml").read_text()
