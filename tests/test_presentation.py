import ast
import copy
import json
from datetime import datetime
from pathlib import Path

import pytest

from scambio.i18n import LANGUAGES, Translator
from scambio.paths import design_dir
from scambio.ui.presentation import Design, present

BASE = dict(
    State="released",
    DeviceAddress="AA:BB:CC:DD:EE:FF",
    DeviceName="A_&<B>",
    IphonePriority=False,
    AudioActive=False,
    IdleReleaseAt=0,
    LastError="",
)


@pytest.fixture
def design():
    return Design.load(design_dir() / "ui/tray.json")


@pytest.mark.parametrize(
    "props,rule",
    [
        ({"DeviceAddress": ""}, "not_configured"),
        ({"State": "unavailable"}, "unavailable"),
        ({"State": "connecting"}, "connecting"),
        ({"State": "releasing"}, "releasing"),
        ({"State": "on_pc", "AudioActive": True, "IdleReleaseAt": 1}, "on_pc_playing"),
        ({"State": "on_pc", "IdleReleaseAt": 1}, "on_pc_idle"),
        ({"State": "on_pc"}, "on_pc"),
        ({"IphonePriority": True}, "priority"),
        ({}, "released"),
    ],
)
def test_rules(design, props, rule):
    model = present(design, BASE | props, "", 0, Translator("en"))
    assert model.rule == rule
    assert (
        model.icon
        == design.data["icons"][
            next(r for r in design.data["presentation"] if r["id"] == rule)["icon"]
        ]
    )
    assert model.menu[7]["visible"] is True
    assert model.menu[1]["enabled"] is False
    if rule != "not_configured":
        assert "A__&<B>" in model.menu[1]["label"]
        assert "A_&amp;&lt;B&gt;" in model.tooltip


@pytest.mark.parametrize(
    "delta,phrase",
    [
        (120000001, "3 min"),
        (120000000, "2 min"),
        (60000001, "2 min"),
        (60000000, "under a minute"),
        (0, "under a minute"),
        (-1, "under a minute"),
    ],
)
def test_time_boundaries(design, delta, phrase):
    now = 1700000000000000
    deadline = now + delta
    model = present(
        design,
        BASE | {"State": "on_pc", "IdleReleaseAt": deadline},
        "",
        now,
        Translator("en"),
    )
    assert phrase in model.menu[2]["label"]
    assert datetime.fromtimestamp(deadline / 1000000).strftime("%H:%M") in model.tooltip


@pytest.mark.parametrize(
    "state", ["released", "connecting", "on_pc", "releasing", "unavailable"]
)
@pytest.mark.parametrize("configured", [True, False])
@pytest.mark.parametrize("priority", [True, False])
def test_switch_and_toggle(design, state, configured, priority):
    model = present(
        design,
        BASE
        | {
            "State": state,
            "DeviceAddress": "test" if configured else "",
            "IphonePriority": priority,
        },
        "",
        0,
        Translator("en"),
    )
    assert model.menu[4]["enabled"] == (configured and state != "unavailable")
    assert model.menu[4]["label"] == (
        "Hand back to the phone" if state in {"on_pc", "connecting"} else "Move to PC"
    )
    assert type(model.menu[5]["toggle-state"]) is int
    assert model.menu[5]["toggle-state"] == int(priority)


def test_overlay_and_assets(design):
    for lang in LANGUAGES:
        tr = Translator(lang, strict=True)
        design.validate_assets(design_dir(), tr)
        for code, key in design.data["error_overlay"]["detail"].items():
            model = present(design, BASE, code, 0, tr)
            assert model.status == "NeedsAttention"
            assert model.icon == model.attention
            assert model.menu[2]["label"] == tr.tr(key)
            assert tr.tr(key) in model.tooltip
            for props in ({"DeviceAddress": ""}, {"State": "unavailable"}):
                assert present(design, BASE | props, code, 0, tr).status == "Active"


@pytest.mark.parametrize(
    "path,value",
    [
        (("schema",), True),
        (("schema",), 2),
        (("other",), 1),
        (("sni", "category"), "wrong"),
        (("sni", "other"), True),
        (("app_icon",), "/tmp/icon.svg"),
        (("icons", "released"), "../bad"),
        (("presentation", 0, "when", "unknown"), True),
        (("presentation", 0, "when", "state"), "bad"),
        (("presentation", 0, "when", "audio_active"), 1),
        (("presentation", 0, "icon"), "bad"),
        (("presentation", 0, "other"), True),
        (("presentation", 1, "id"), "not_configured"),
        (("error_overlay", "skip_rules"), ["bad"]),
        (("error_overlay", "detail", "bad"), "key"),
        (("menu", 0, "id"), 0),
        (("menu", 0, "id"), True),
        (("menu", 1, "id"), 1),
        (("menu", 0, "enabled"), 1),
        (("menu", 0, "visible"), "yes"),
        (("menu", 3, "action"), "app.invalid"),
        (("menu", 3, "enabled_when"), "always"),
        (("menu", 4, "toggle_state"), "invalid"),
        (("menu", 4, "toggle_type"), "radio"),
        (("notifications", "urgency"), 256),
        (("notifications", "expire_timeout"), 2**31),
        (("notifications", "actions", "retry", "call"), "Connect"),
        (("notifications", "actions", "retry", "valid_when", "state_in"), ["bad"]),
        (("notifications", "errors", "connect_failed", "family"), "bad"),
        (("notifications", "errors", "connect_failed", "action"), "bad"),
        (("notifications", "errors", "connect_failed", "transient"), 1),
    ],
)
def test_invalid_vocabulary(design, path, value):
    raw = copy.deepcopy(design.data)
    obj = raw
    for part in path[:-1]:
        obj = obj[part]
    obj[path[-1]] = value
    with pytest.raises(ValueError):
        Design.validate(raw)


def test_pure_and_no_timers():
    root = Path(__file__).parents[1] / "src/scambio"
    for path in [
        root / "i18n.py",
        root / "ui/presentation.py",
        root / "ui/settings_model.py",
    ]:
        tree = ast.parse(path.read_text())
        assert not any(
            isinstance(n, ast.ImportFrom) and n.module and n.module.startswith("gi")
            for n in ast.walk(tree)
        )
    for path in (root / "ui").glob("*.py"):
        text = path.read_text()
        for forbidden in (
            "scambio.core",
            "timeout_add",
            "time.sleep",
            "bluetoothctl",
        ):
            assert forbidden not in text
        tree = ast.parse(text)
        if path.name != "window.py":
            assert not any(
                isinstance(node, ast.ImportFrom)
                and node.module == "gi.repository"
                and any(alias.name in {"Gtk", "Adw", "Gdk"} for alias in node.names)
                for node in ast.walk(tree)
            )
    assert json.loads((design_dir() / "ui/tray.json").read_text())["schema"] == 1


def test_pure_imports_do_not_load_gi():
    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import scambio.i18n; import scambio.ui.presentation; "
            'assert "gi" not in sys.modules',
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
