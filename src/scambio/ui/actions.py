"""Shared GActions dispatch only through the public daemon client."""

from gi.repository import Gio, GLib

from scambio.ui.client import ScambioClient
from scambio.ui.guard import guarded


def create_actions(client: ScambioClient) -> Gio.SimpleActionGroup:
    group = Gio.SimpleActionGroup()

    @guarded
    def activate(action: Gio.SimpleAction, parameter: GLib.Variant | None) -> None:
        name = action.get_name()
        if name == "switch":
            client.call("Switch")
        elif name == "toggle-priority":
            client.call(
                "SetPriority",
                GLib.Variant("(b)", (not client.props["IphonePriority"],)),
            )
        elif name == "quit":
            client.call("Quit")

    for name in ("switch", "toggle-priority", "quit"):
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", activate)
        group.add_action(action)
    return group
