"""Public wire contract shared by client and service, without core imports."""

from importlib.resources import files

BUS_NAME = "app.scambio.Scambio"
PATH = "/app/scambio/Scambio"
INTERFACE = "app.scambio.Scambio1"


def introspection_xml() -> str:
    return files("scambio").joinpath("core/dbus/app.scambio.Scambio1.xml").read_text()
