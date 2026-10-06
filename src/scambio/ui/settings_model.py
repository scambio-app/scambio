"""Pure settings presentation and per-key serialization of immediate edits."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from scambio import __version__
from scambio.i18n import Translator
from scambio.ui.presentation import Design, present

Scalar = str | int | bool
LANGUAGES = ("auto", "it", "en", "de")
EDIT_KEYS = {
    "priority_row": "IphonePriority",
    "device_row": "device.address",
    "release_idle_row": "policy.release_idle_seconds",
    "tray_row": "ui.tray",
    "notifications_row": "ui.notifications",
    "language_row": "ui.language",
}


@dataclass(frozen=True)
class Command:
    method: str
    key: str = ""
    value: Scalar = ""


@dataclass
class Pending:
    sent: Scalar
    wanted: Scalar


@dataclass(frozen=True)
class View:
    widgets: dict[str, dict[str, object]]
    switch_enabled: bool
    device_choices: tuple[tuple[str, str], ...]


class SettingsModel:
    def __init__(
        self,
        design: Design,
        tr: Translator,
        accelerator_label: Callable[[str], str] = str,
    ) -> None:
        self.design, self.tr = design, tr
        self.accelerator_label = accelerator_label
        self.props: dict[str, object] = {}
        self.available = False
        self.restarting = False
        self.devices: list[tuple[str, str]] = []
        self.pending: dict[str, Pending] = {}
        self.saved_device: str | None = None
        self.toasts: list[str] = []

    def presence(self, available: bool) -> None:
        self.available = available
        if available:
            self.restarting = False

    def update(self, props: dict[str, object]) -> bool:
        """Return whether the device list needs a fresh snapshot."""
        changed = any(
            self.props.get(key) != props.get(key)
            for key in ("DeviceAddress", "DeviceName")
        )
        if self.props.get("DeviceAddress") != props.get("DeviceAddress"):
            self.saved_device = None
        self.props = props.copy()
        return changed

    def config(self) -> dict[str, Scalar]:
        raw = self.props.get("Config", {})
        return (
            {str(k): v for k, v in raw.items() if type(v) in {str, int, bool}}
            if isinstance(raw, dict)
            else {}
        )

    def _value(self, key: str, default: Scalar) -> Scalar:
        if key in self.pending:
            return self.pending[key].wanted
        if key == "device.address" and self.saved_device is not None:
            return self.saved_device
        values = self.props if key == "IphonePriority" else self.config()
        return cast(Scalar, values.get(key, default))

    def choices(self) -> tuple[tuple[str, str], ...]:
        address = str(
            self._value("device.address", str(self.props.get("DeviceAddress", "")))
        )
        choices = list(self.devices)
        if not address:
            choices.insert(0, ("", self.tr.tr("settings-device-none")))
        elif address not in [entry[0] for entry in choices]:
            choices.append((address, address))
        return tuple(choices)

    def view(self, now: int) -> View:
        props = (
            self.props
            if self.available
            else {"State": "unavailable", "DeviceAddress": ""}
        )
        status = present(self.design, props, "", now, self.tr)
        widgets: dict[str, dict[str, object]] = {}
        for group in (
            "status_group",
            "device_group",
            "shortcut_group",
            "general_group",
        ):
            widgets[group] = {"sensitive": self.available}
        widgets["daemon_banner"] = {
            "revealed": not self.available and not self.restarting
        }
        widgets["status_icon"] = {
            "icon-name": status.icon
            if self.available
            else self.design.data["icons"]["unavailable"],
            "scambio-dim": not self.available
            or status.icon == self.design.data["icons"]["unavailable"],
        }
        widgets["status_row"] = {
            "title": str(status.menu[1]["label"]).replace("__", "_")
            if self.available
            else self.tr.tr("settings-status-unknown"),
            "subtitle": str(status.menu[2]["label"]).replace("__", "_")
            if self.available
            else "",
        }
        widgets["switch_button"] = {
            "label": str(status.menu[4]["label"]).replace("__", "_")
        }
        widgets["priority_row"] = {"active": bool(self._value("IphonePriority", False))}
        choices = self.choices()
        address = str(
            self._value("device.address", str(self.props.get("DeviceAddress", "")))
        )
        busy = self.props.get("State") not in {"released", "unavailable"}
        widgets["device_row"] = {
            "selected": next(
                (i for i, entry in enumerate(choices) if entry[0] == address), 0
            ),
            "sensitive": self.available and not busy,
            "subtitle": self.tr.tr("settings-device-busy")
            if busy and self.available
            else self.tr.tr("settings-device-empty")
            if not self.devices
            else "",
        }
        widgets["release_idle_row"] = {
            "value": max(
                1, (int(self._value("policy.release_idle_seconds", 120)) + 30) // 60
            )
        }
        shortcut_state = self.props.get("ShortcutState", "unsupported")
        conflict = shortcut_state == "conflict"
        subtitle = self.tr.tr("settings-shortcut-subtitle")
        if conflict:
            subtitle = self.tr.tr(
                "settings-shortcut-conflict",
                shortcut=self.accelerator_label(
                    str(self.config().get("shortcut.preferred", ""))
                ),
                owner=self.props.get("ShortcutOwner", ""),
            )
        elif shortcut_state == "unsupported":
            subtitle = self.tr.tr("settings-shortcut-unsupported")
        widgets["shortcut_row"] = {
            "subtitle": subtitle,
            "scambio-shortcut-conflict": conflict,
        }
        widgets["shortcut_label"] = {
            "accelerator": str(self.props.get("Shortcut", "")),
            "disabled-text": str(self.props.get("ShortcutLabel", ""))
            or self.tr.tr("settings-shortcut-unbound"),
            "visible": self.available and shortcut_state != "unsupported",
        }
        widgets["shortcut_change_button"] = {
            "visible": self.available
            and self.props.get("ShortcutBackend") == "kglobalaccel"
        }
        widgets["tray_row"] = {"active": bool(self._value("ui.tray", True))}
        widgets["notifications_row"] = {
            "active": bool(self._value("ui.notifications", True))
        }
        language = self._value("ui.language", "auto")
        widgets["language_row"] = {
            "selected": LANGUAGES.index(str(language)) if language in LANGUAGES else 0
        }
        widgets["version_label"] = {
            "label": self.tr.tr(
                "settings-version", version=self.props.get("Version", __version__)
            )
        }
        return View(
            widgets, self.available and bool(status.menu[4]["enabled"]), choices
        )

    def _command(self, key: str, value: Scalar) -> Command:
        return Command(
            "SetPriority" if key == "IphonePriority" else "SetConfig", key, value
        )

    def change(self, widget: str, value: Scalar) -> Command | None:
        if not self.available or widget not in EDIT_KEYS:
            return None
        key = EDIT_KEYS[widget]
        if widget == "device_row":
            if self.props.get("State") not in {"released", "unavailable"}:
                return None
            choices = self.choices()
            index = int(value)
            if not 0 <= index < len(choices) or not choices[index][0]:
                return None
            value = choices[index][0]
        elif widget == "release_idle_row":
            value = max(1, min(60, int(value))) * 60
        elif widget == "language_row":
            if not 0 <= int(value) < len(LANGUAGES):
                return None
            value = LANGUAGES[int(value)]
        if value == self._value(key, ""):
            return None
        if key in self.pending:
            self.pending[key].wanted = value
            return None
        self.pending[key] = Pending(value, value)
        return self._command(key, value)

    def complete(self, key: str, error: str = "") -> Command | None:
        pending = self.pending.pop(key, None)
        code = error.rsplit(".", 1)[-1]
        if error:
            text = {
                "ConfigInvalid": "settings-error-invalid",
                "DeviceBusy": "settings-device-busy",
                "RestartRequired": "settings-error-restart-required",
            }.get(code, "settings-error-generic")
            self.toasts.append(self.tr.tr(text, error=code))
            if code == "RestartRequired" and key == "device.address" and pending:
                self.saved_device = str(pending.sent)
        elif key == "device.address":
            self.restarting = True
            if pending:
                self.saved_device = str(pending.sent)
            self.toasts.append(self.tr.tr("settings-device-restarting"))
        elif key == "ui.language":
            self.toasts.append(self.tr.tr("settings-language-next-open"))
        if pending and pending.wanted != pending.sent:
            self.pending[key] = Pending(pending.wanted, pending.wanted)
            return self._command(key, pending.wanted)
        return None

    def activated(self) -> Command | None:
        if self.available and self.props.get("ShortcutState") == "conflict":
            return Command("RetryShortcut")
        return None

    def action(self, name: str) -> Command | None:
        if name == "switch":
            return Command("Switch") if self.view(0).switch_enabled else None
        if name == "change-shortcut":
            return (
                Command("change-shortcut")
                if self.props.get("ShortcutBackend") == "kglobalaccel"
                else None
            )
        if name in {"open-config", "start-daemon"}:
            return Command(name)
        return None
