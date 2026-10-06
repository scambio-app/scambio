import ast
import subprocess
import sys
from pathlib import Path

import pytest

from scambio.i18n import Translator
from scambio.paths import design_dir
from scambio.ui.presentation import Design
from scambio.ui.settings_model import Command, SettingsModel

BASE = {
    "State": "released",
    "DeviceAddress": "AA:BB:CC:DD:EE:FF",
    "DeviceName": "A_B",
    "IphonePriority": False,
    "ShortcutState": "active",
    "Shortcut": "<Super>g",
    "ShortcutLabel": "",
    "ShortcutOwner": "",
    "ShortcutBackend": "kglobalaccel",
    "Config": {
        "device.address": "AA:BB:CC:DD:EE:FF",
        "policy.release_idle_seconds": 120,
        "ui.tray": True,
        "ui.notifications": True,
        "ui.language": "auto",
        "shortcut.preferred": "<Super>g",
    },
}


@pytest.fixture
def model():
    model = SettingsModel(
        Design.load(design_dir() / "ui/tray.json"),
        Translator("en"),
        lambda key: "Super + G",
    )
    model.presence(True)
    model.update(BASE)
    model.devices = [(BASE["DeviceAddress"], "A_B"), ("11:22:33:44:55:66", "second")]
    return model


@pytest.mark.parametrize(
    "state", ["released", "on_pc", "connecting", "releasing", "unavailable"]
)
def test_state_widgets(model, state):
    model.update(BASE | {"State": state})
    view = model.view(0)
    assert view.switch_enabled == (state != "unavailable")
    assert view.widgets["device_row"]["sensitive"] == (
        state in {"released", "unavailable"}
    )
    assert ("Hand back" in view.widgets["switch_button"]["label"]) == (
        state in {"on_pc", "connecting"}
    )
    assert "A_B" in view.widgets["status_row"]["title"]
    assert view.widgets["status_icon"]["scambio-dim"] == (state == "unavailable")


@pytest.mark.parametrize("state", ["active", "conflict", "unbound", "unsupported"])
@pytest.mark.parametrize("backend", ["kglobalaccel", "portal", "none"])
def test_shortcut_states(model, state, backend):
    model.update(
        BASE
        | {"ShortcutState": state, "ShortcutBackend": backend, "ShortcutOwner": "other"}
    )
    widgets = model.view(0).widgets
    assert widgets["shortcut_change_button"]["visible"] == (backend == "kglobalaccel")
    assert widgets["shortcut_label"]["visible"] == (state != "unsupported")
    assert widgets["shortcut_row"]["scambio-shortcut-conflict"] == (state == "conflict")
    assert (model.activated() == Command("RetryShortcut")) == (state == "conflict")
    if state == "conflict":
        assert "other" in widgets["shortcut_row"]["subtitle"]
        assert "Super + G" in widgets["shortcut_row"]["subtitle"]


@pytest.mark.parametrize("seconds,minutes", [(90, 2), (150, 3), (600, 10), (10, 1)])
def test_minutes(model, seconds, minutes):
    model.update(
        BASE | {"Config": BASE["Config"] | {"policy.release_idle_seconds": seconds}}
    )
    assert model.view(0).widgets["release_idle_row"]["value"] == minutes


@pytest.mark.parametrize(
    "language,index", [("auto", 0), ("it", 1), ("en", 2), ("de", 3)]
)
def test_language_indices(model, language, index):
    model.update(BASE | {"Config": BASE["Config"] | {"ui.language": language}})
    assert model.view(0).widgets["language_row"]["selected"] == index


def test_device_missing_none_empty_and_busy(model):
    model.devices = []
    assert model.choices() == ((BASE["DeviceAddress"], BASE["DeviceAddress"]),)
    assert model.view(0).widgets["device_row"]["subtitle"] == model.tr.tr(
        "settings-device-empty"
    )
    model.update(
        BASE | {"DeviceAddress": "", "Config": BASE["Config"] | {"device.address": ""}}
    )
    assert model.choices()[0] == ("", model.tr.tr("settings-device-none"))
    assert model.change("device_row", 0) is None
    model.devices = [("11:22:33:44:55:66", "second")]
    assert model.change("device_row", 1) == Command(
        "SetConfig", "device.address", "11:22:33:44:55:66"
    )
    model.complete("device.address", "DeviceBusy")
    assert model.view(0).widgets["device_row"]["selected"] == 0


@pytest.mark.parametrize(
    "widget,value,method,key,wire",
    [
        ("priority_row", True, "SetPriority", "IphonePriority", True),
        ("release_idle_row", 3, "SetConfig", "policy.release_idle_seconds", 180),
        ("tray_row", False, "SetConfig", "ui.tray", False),
        ("notifications_row", False, "SetConfig", "ui.notifications", False),
        ("language_row", 3, "SetConfig", "ui.language", "de"),
        ("device_row", 1, "SetConfig", "device.address", "11:22:33:44:55:66"),
    ],
)
def test_commands_and_no_echo(model, widget, value, method, key, wire):
    assert model.change(widget, value) == Command(method, key, wire)
    assert model.change(widget, value) is None


def test_rapid_minutes_never_jump_back(model):
    assert model.change("release_idle_row", 3).value == 180
    assert model.change("release_idle_row", 4) is None
    assert model.change("release_idle_row", 5) is None
    model.update(
        BASE | {"Config": BASE["Config"] | {"policy.release_idle_seconds": 180}}
    )
    assert model.view(0).widgets["release_idle_row"]["value"] == 5
    assert model.complete("policy.release_idle_seconds") == Command(
        "SetConfig", "policy.release_idle_seconds", 300
    )
    assert model.view(0).widgets["release_idle_row"]["value"] == 5
    model.update(
        BASE | {"Config": BASE["Config"] | {"policy.release_idle_seconds": 300}}
    )
    assert model.complete("policy.release_idle_seconds") is None
    assert model.view(0).widgets["release_idle_row"]["value"] == 5


def test_errors_and_restart_banner(model):
    model.change("tray_row", False)
    model.update(BASE)
    model.complete("ui.tray", "app.scambio.Scambio1.Error.ConfigInvalid")
    assert model.view(0).widgets["tray_row"]["active"]
    assert model.toasts[-1] == model.tr.tr("settings-error-invalid")
    model.change("device_row", 1)
    model.complete("device.address", "RestartRequired")
    assert (
        model.choices()[model.view(0).widgets["device_row"]["selected"]][0]
        == "11:22:33:44:55:66"
    )
    model.saved_device = None
    model.change("device_row", 1)
    model.complete("device.address")
    model.presence(False)
    assert not model.view(0).widgets["daemon_banner"]["revealed"]
    model.presence(True)
    model.presence(False)
    assert model.view(0).widgets["daemon_banner"]["revealed"]
    assert not model.view(0).switch_enabled
    assert model.view(0).widgets["status_icon"] == {
        "icon-name": model.design.data["icons"]["unavailable"],
        "scambio-dim": True,
    }
    for group in ("status_group", "device_group", "shortcut_group", "general_group"):
        assert not model.view(0).widgets[group]["sensitive"]
    assert not model.view(0).widgets["shortcut_label"]["visible"]


def test_actions_and_pure_import(model):
    assert model.action("switch") == Command("Switch")
    assert model.action("change-shortcut") == Command("change-shortcut")
    assert model.action("open-config") == Command("open-config")
    assert model.action("start-daemon") == Command("start-daemon")
    assert model.action("other") is None
    model.presence(False)
    assert model.change("tray_row", False) is None
    assert model.action("switch") is None
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import scambio.ui.settings_model; "
            'assert "gi" not in sys.modules',
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    for name in ("settings_model.py", "window.py"):
        tree = ast.parse(
            (Path(__file__).parents[1] / "src/scambio/ui" / name).read_text()
        )
        from test_i18n import po_entries

        keys = po_entries(design_dir() / "i18n/scambio.pot")
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and node.value.startswith("settings-")
            ):
                assert node.value in keys
