"""UI lifecycle; all daemon state arrives through its asynchronous D-Bus proxy."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from scambio.config import Config, config_path
from scambio.i18n import LANGUAGES, Translator
from scambio.paths import design_dir
from scambio.ui.guard import guarded
from scambio.ui.presentation import Design, present

if TYPE_CHECKING:
    from gi.repository import Gio

    from scambio.ui.client import ScambioClient
    from scambio.ui.notify import Notifications
    from scambio.ui.tray import Tray

from scambio.text import logger

LOG = logger(__name__)


class Ui:
    def __init__(
        self,
        connection: Gio.DBusConnection,
        config: Config,
        bus_name: str,
        path: str,
        config_file: Path | None = None,
    ) -> None:
        from scambio.ui.client import ScambioClient

        self.connection, self.config = connection, config
        self.config_file = config_file or config_path()
        self.client: ScambioClient | None = None
        self.tray: Tray | None = None
        self.notifications: Notifications | None = None
        self.closed = False
        self.design = Design.load(design_dir() / "ui/tray.json")
        for language in LANGUAGES:
            self.design.validate_assets(design_dir(), Translator(language, strict=True))
        self.tr = Translator(config.language, strict=True)
        self.client = ScambioClient(
            connection,
            bus_name,
            path,
            self._ready,
            config.backend.dbus_timeout_seconds * 1000,
        )

    @guarded
    def _ready(self) -> None:
        from scambio.ui.actions import create_actions
        from scambio.ui.notify import Notifications

        if self.closed or self.client is None:
            return
        self.actions = create_actions(self.client)
        self.notifications = Notifications(
            self.client,
            self.design,
            self.tr,
            self.config_file,
            self.refresh,
            self.config.notifications,
        )
        self.client.listeners.append(self._event)
        self.notifications.startup()
        self.refresh()

    @guarded
    def _event(self, name: str, value: Any) -> None:
        self.refresh()

    @guarded
    def opened(self) -> None:
        if self.notifications:
            self.notifications.seen()
        self.refresh()

    @guarded
    def refresh(self) -> None:
        from gi.repository import GLib

        from scambio.ui.tray import Tray

        if self.closed or self.client is None or self.notifications is None:
            return
        if not self.config.tray:
            if self.tray:
                self.tray.stop()
                self.tray = None
            return
        model = present(
            self.design,
            self.client.props,
            self.notifications.active_error,
            GLib.get_real_time(),
            self.tr,
        )
        if self.tray:
            self.tray.update(model)
        else:
            self.tray = Tray(
                self.connection,
                self.design,
                model,
                self.actions,
                self.opened,
                self.client.timeout_ms,
            )

    @guarded
    def apply_config(self, config: Config) -> None:
        if self.closed:
            return
        tr = Translator(config.language, strict=True)
        self.design.validate_assets(design_dir(), tr)
        self.config, self.tr = config, tr
        if self.client:
            self.client.timeout_ms = config.backend.dbus_timeout_seconds * 1000
        if self.notifications:
            self.notifications.configure(tr, config.notifications)
        if self.tray and self.client:
            self.tray.timeout_ms = self.client.timeout_ms
        self.refresh()

    @guarded
    def stop(self) -> None:
        self.closed = True
        if self.tray:
            self.tray.stop()
            self.tray = None
        if self.notifications:
            self.notifications.stop()
        if self.client:
            self.client.stop()


class DisabledUi:
    """A failed design must not prevent daemon operation or shutdown."""

    def apply_config(self, config: Config) -> None:
        pass

    def stop(self) -> None:
        pass


def start_ui(
    connection: Gio.DBusConnection,
    config: Config,
    bus_name: str,
    path: str,
    config_file: Path | None = None,
) -> Ui | DisabledUi:
    try:
        return Ui(connection, config, bus_name, path, config_file)
    except Exception:
        LOG.exception("UI disabled: invalid design or catalogs; run make i18n")
        return DisabledUi()
