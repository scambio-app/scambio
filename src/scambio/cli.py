"""Thin D-Bus client. The daemon is imported only by the daemon command."""

import argparse
import gettext
import json
import logging
import sys
from typing import Any, cast

from gi.repository import Gio, GLib

from scambio.api import BUS_NAME, INTERFACE, PATH, introspection_xml

_ = gettext.gettext


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="scambio", description=_("Switch Bluetooth audio between PC and phone")
    )
    commands = parser.add_subparsers(dest="command", required=True)
    daemon = commands.add_parser("daemon", help=_("Run the daemon"))
    daemon.add_argument("--debug", action="store_true", help=_("Enable debug logging"))
    status = commands.add_parser("status", help=_("Show daemon status"))
    status.add_argument("--json", action="store_true", help=_("Output JSON"))
    commands.add_parser("switch", help=_("Switch the device destination"))
    priority = commands.add_parser("priority", help=_("Show or change iPhone priority"))
    priority.add_argument("value", nargs="?", choices=["on", "off", "toggle"])
    args = parser.parse_args(argv)
    if args.command == "daemon":
        from scambio.core.service import run

        logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)
        return run()
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        # Never auto-activate the daemon.
        info = Gio.DBusNodeInfo.new_for_xml(introspection_xml()).interfaces[0]
        proxy = Gio.DBusProxy.new_sync(
            bus,
            Gio.DBusProxyFlags.DO_NOT_AUTO_START
            | Gio.DBusProxyFlags.DO_NOT_LOAD_PROPERTIES,
            info,
            BUS_NAME,
            PATH,
            INTERFACE,
            None,
        )
        if not proxy.get_name_owner():
            print(
                _("Scambio is not running; run systemctl --user start scambio"),
                file=sys.stderr,
            )
            return 3

        def properties() -> dict[str, Any]:
            reply = bus.call_sync(
                BUS_NAME,
                PATH,
                "org.freedesktop.DBus.Properties",
                "GetAll",
                GLib.Variant("(s)", (INTERFACE,)),
                None,
                Gio.DBusCallFlags.NO_AUTO_START,
                -1,
                None,
            )
            return cast(dict[str, Any], reply.unpack()[0])

        if args.command == "status":
            values = properties()
            print(
                json.dumps(values, sort_keys=True)
                if args.json
                else "\n".join(f"{key}: {value}" for key, value in values.items())
            )
        elif args.command == "switch":
            reply = proxy.call_sync(
                "Switch", None, Gio.DBusCallFlags.NO_AUTO_START, -1, None
            )
            print(reply.unpack()[0])
        else:
            enabled = properties()["IphonePriority"]
            if args.value is None:
                print("on" if enabled else "off")
            else:
                enabled = not enabled if args.value == "toggle" else args.value == "on"
                proxy.call_sync(
                    "SetPriority",
                    GLib.Variant("(b)", (enabled,)),
                    Gio.DBusCallFlags.NO_AUTO_START,
                    -1,
                    None,
                )
        return 0
    except GLib.Error as exc:
        print(_("D-Bus error: %(error)s") % {"error": str(exc)}, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
