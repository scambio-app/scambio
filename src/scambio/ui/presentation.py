"""Validated design vocabulary and pure projection of public API properties."""

import html
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from scambio.i18n import Translator

STATES = {"released", "connecting", "on_pc", "releasing", "unavailable"}
ACTIONS = {
    "app.switch",
    "app.toggle-priority",
    "app.quit",
    "app.open-settings",
    "app.change-shortcut",
}
ERRORS = {
    "connect_failed",
    "connect_timeout",
    "sink_timeout",
    "sink_lost",
    "disconnect_failed",
    "device_unavailable",
    "device_not_configured",
    "config_invalid",
    "audio_backend_down",
}
Properties = dict[str, Any]


def fields(
    value: Any, required: set[str], optional: set[str] | frozenset[str] = frozenset()
) -> dict[str, Any]:
    if (
        not isinstance(value, dict)
        or not required <= value.keys()
        or value.keys() - required - optional
    ):
        raise ValueError(
            f"Invalid design fields: expected {sorted(required | optional)}"
        )
    return value


def typed(value: Any, kind: type) -> None:
    if type(value) is not kind:
        raise ValueError(f"Expected {kind.__name__}: {value!r}")


def choice(value: Any, choices: set[str]) -> None:
    if not isinstance(value, str) or value not in choices:
        raise ValueError(f"Invalid design value: {value!r}")


def condition(raw: Any, notification: bool = False) -> None:
    allowed = (
        {"state", "state_in", "iphone_priority"}
        if notification
        else {
            "state",
            "device_configured",
            "audio_active",
            "iphone_priority",
            "idle_release",
        }
    )
    obj = fields(raw, set(), allowed)
    for key, value in obj.items():
        if key == "state":
            choice(value, STATES)
        elif key == "state_in":
            typed(value, list)
            if not value:
                raise ValueError("Empty state_in")
            for state in value:
                choice(state, STATES)
        else:
            typed(value, bool)


@dataclass(frozen=True)
class Design:
    data: dict[str, Any]
    keys: frozenset[str]

    @classmethod
    def load(cls, path: Path) -> "Design":
        return cls.validate(json.loads(path.read_text()))

    @classmethod
    def validate(cls, raw: Any) -> "Design":
        data = fields(
            raw,
            {
                "schema",
                "sni",
                "app_icon",
                "icons",
                "presentation",
                "error_overlay",
                "menu",
                "notifications",
            },
            {"comment"},
        )
        if type(data["schema"]) is not int or data["schema"] != 1:
            raise ValueError("Unsupported design schema")
        if "comment" in data:
            typed(data["comment"], str)
        keys: set[str] = {"tray-device-fallback"}

        def text(value: Any) -> None:
            typed(value, str)
            if not value or value.startswith("@"):
                raise ValueError("Invalid text key")
            keys.add(value)

        sni = fields(data["sni"], {"id", "category", "title"})
        for value in sni.values():
            typed(value, str)
        choice(
            sni["category"],
            {"ApplicationStatus", "Communications", "SystemServices", "Hardware"},
        )
        typed(data["app_icon"], str)
        icon_path = Path(data["app_icon"])
        if icon_path.is_absolute() or ".." in icon_path.parts:
            raise ValueError("app_icon must be relative to design/icons")
        typed(data["icons"], dict)
        icons = data["icons"]
        if not icons:
            raise ValueError("No icons")
        for key, value in icons.items():
            typed(key, str)
            typed(value, str)
            if not value or "/" in value or value in {".", ".."}:
                raise ValueError("Invalid icon name")
        typed(data["presentation"], list)
        ids: set[str] = set()
        for raw_rule in data["presentation"]:
            rule = fields(
                raw_rule,
                {"id", "when", "icon", "header", "detail"},
                {"detail_soon", "tooltip_detail"},
            )
            typed(rule["id"], str)
            if rule["id"] in ids:
                raise ValueError("Duplicate presentation id")
            ids.add(rule["id"])
            condition(rule["when"])
            choice(rule["icon"], set(icons))
            for key in ("header", "detail", "detail_soon", "tooltip_detail"):
                if key in rule:
                    text(rule[key])
        if not ids:
            raise ValueError("No presentation rules")
        overlay = fields(data["error_overlay"], {"icon", "skip_rules", "detail"})
        choice(overlay["icon"], set(icons))
        typed(overlay["skip_rules"], list)
        for rule_id in overlay["skip_rules"]:
            choice(rule_id, ids)
        typed(overlay["detail"], dict)
        for code, key in overlay["detail"].items():
            choice(code, ERRORS)
            text(key)
        typed(data["menu"], list)
        menu_ids: set[int] = set()
        names: set[str] = set()
        for raw_item in data["menu"]:
            item = fields(
                raw_item,
                {"id", "name"},
                {
                    "type",
                    "enabled",
                    "enabled_when",
                    "visible",
                    "label",
                    "action",
                    "toggle_type",
                    "toggle_state",
                    "theme_icon",
                },
            )
            typed(item["id"], int)
            typed(item["name"], str)
            if item["id"] <= 0 or item["id"] in menu_ids or item["name"] in names:
                raise ValueError("Invalid or duplicate menu id/name")
            menu_ids.add(item["id"])
            names.add(item["name"])
            for key in ("enabled", "visible"):
                if key in item:
                    typed(item[key], bool)
            for key, choices in {
                "type": {"separator"},
                "enabled_when": {"available"},
                "action": ACTIONS,
                "toggle_type": {"checkmark"},
                "toggle_state": {"iphone_priority"},
            }.items():
                if key in item:
                    choice(item[key], choices)
            if ("toggle_type" in item) != ("toggle_state" in item):
                raise ValueError("Incomplete toggle")
            if "theme_icon" in item:
                typed(item["theme_icon"], str)
            if item.get("type") != "separator" and "label" not in item:
                raise ValueError("Missing menu label")
            if "label" in item:
                label = item["label"]
                if isinstance(label, dict):
                    for value in fields(label, {"to_pc", "to_phone"}).values():
                        text(value)
                elif label not in ("@header", "@detail"):
                    text(label)
        notices = fields(
            data["notifications"],
            {
                "app_name",
                "expire_timeout",
                "urgency",
                "category",
                "errors",
                "priority",
                "actions",
            },
        )
        typed(notices["app_name"], str)
        for key, lo, hi in (
            ("expire_timeout", -(2**31), 2**31 - 1),
            ("urgency", 0, 255),
        ):
            typed(notices[key], int)
            if not lo <= notices[key] <= hi:
                raise ValueError(f"Invalid {key}")
        for value in fields(notices["category"], {"error", "priority"}).values():
            typed(value, str)
        typed(notices["actions"], dict)
        for name, action in notices["actions"].items():
            typed(name, str)
            fields(action, {"label", "call"}, {"valid_when"})
            text(action["label"])
            choice(action["call"], {"Switch", "open-config-file"})
            if "valid_when" in action:
                condition(action["valid_when"], True)
        fields(notices["errors"], ERRORS)
        fields(notices["priority"], {"on", "off", "on_with_switch", "off_with_switch"})
        for entries in (notices["errors"], notices["priority"]):
            for entry in entries.values():
                fields(
                    entry,
                    {"family", "title", "body"},
                    {"action", "once_per_run", "startup_only", "transient"},
                )
                choice(
                    entry["family"],
                    {"grab", "release", "availability", "setup", "priority"},
                )
                text(entry["title"])
                text(entry["body"])
                if "action" in entry:
                    choice(entry["action"], set(notices["actions"]))
                for key in ("once_per_run", "startup_only", "transient"):
                    if key in entry:
                        typed(entry[key], bool)
        return cls(data, frozenset(keys))

    def validate_assets(self, root: Path, tr: Translator) -> None:
        for name in self.data["icons"].values():
            if not (root / "icons/hicolor/scalable/status" / (name + ".svg")).is_file():
                raise ValueError(f"Missing icon: {name}")
        if not (root / "icons" / self.data["app_icon"]).is_file():
            raise ValueError("Missing notification icon")
        for key in self.keys:
            if tr.catalog.gettext(key) == key:
                raise ValueError(f"Missing catalog key: {key}; run make i18n")


def matches(when: dict[str, Any], props: Properties) -> bool:
    values = {
        "state": props.get("State"),
        "device_configured": bool(props.get("DeviceAddress")),
        "audio_active": bool(props.get("AudioActive")),
        "iphone_priority": bool(props.get("IphonePriority")),
        "idle_release": bool(props.get("IdleReleaseAt")),
    }
    return all(
        values["state"] in value if key == "state_in" else values[key] == value
        for key, value in when.items()
    )


@dataclass(frozen=True)
class Model:
    rule: str
    icon: str
    attention: str
    status: str
    title: str
    tooltip: str
    menu: dict[int, Properties]


def present(
    design: Design, props: Properties, error: str, now: int, tr: Translator
) -> Model:
    data = design.data
    rule = next(rule for rule in data["presentation"] if matches(rule["when"], props))
    deadline = int(props.get("IdleReleaseAt", 0))
    remaining = deadline - now
    values = {
        "device": props.get("DeviceName", ""),
        "minutes": (remaining + 59_999_999) // 60_000_000,
        "time": datetime.fromtimestamp(deadline / 1_000_000).strftime("%H:%M"),
    }
    header = tr.tr(rule["header"], **values)
    detail_key = rule["detail"]
    if "detail_soon" in rule and remaining <= 60_000_000:
        detail_key = rule["detail_soon"]
    detail = tr.tr(detail_key, **values)
    tooltip = tr.tr(rule.get("tooltip_detail", detail_key), **values)
    overlay = data["error_overlay"]
    active = error in overlay["detail"] and rule["id"] not in overlay["skip_rules"]
    icon = data["icons"][overlay["icon"] if active else rule["icon"]]
    if active:
        detail = tooltip = tr.tr(overlay["detail"][error], **values)
    menu: dict[int, Properties] = {}
    for item in data["menu"]:
        row: Properties = {
            "enabled": item.get("enabled", True),
            "visible": item.get("visible", True),
        }
        if "type" in item:
            row["type"] = item["type"]
        if "label" in item:
            label = item["label"]
            if isinstance(label, dict):
                label = label[
                    "to_phone"
                    if props.get("State") in {"on_pc", "connecting"}
                    else "to_pc"
                ]
            text = (
                header
                if label == "@header"
                else detail
                if label == "@detail"
                else tr.tr(label, **values)
            )
            row["label"] = text.replace("_", "__")
        if "enabled_when" in item:
            row["enabled"] = props.get("State") != "unavailable" and bool(
                props.get("DeviceAddress")
            )
        if "toggle_type" in item:
            row["toggle-type"] = item["toggle_type"]
            row["toggle-state"] = int(bool(props.get("IphonePriority")))
        if "theme_icon" in item:
            row["icon-name"] = item["theme_icon"]
        menu[item["id"]] = row
    return Model(
        rule["id"],
        icon,
        data["icons"][overlay["icon"]],
        "NeedsAttention" if active else "Active",
        data["sni"]["title"],
        html.escape(header + "\n" + tooltip, quote=False),
        menu,
    )
