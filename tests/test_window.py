import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


def run_window(tmp_path, scenario="normal"):
    env = dict(
        os.environ,
        HOME=str(tmp_path),
        SCAMBIO_TEST_ROOT=str(tmp_path),
        SCAMBIO_TEST_SCENARIO=scenario,
        GSK_RENDERER="cairo",
        GDK_BACKEND="x11",
        GTK_A11Y="none",
        LANG="C",
        LC_ALL="C",
        LANGUAGE="",
        XDG_CONFIG_HOME=str(tmp_path / ".config"),
        XDG_DATA_HOME=str(tmp_path / ".local/share"),
        XDG_CACHE_HOME=str(tmp_path / ".cache"),
    )
    result = subprocess.run(
        [
            "xvfb-run",
            "-a",
            "dbus-run-session",
            "--",
            sys.executable,
            str(Path(__file__).parent / "fixtures/run_settings.py"),
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result


def test_real_gtk_on_private_display_and_buses(tmp_path):
    result = run_window(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (
        "Traceback" not in result.stderr and "UI callback failed" not in result.stderr
    )
    evidence = json.loads(result.stdout.strip().splitlines()[-1])
    assert evidence["gtk_real"] and evidence["private_buses"]
    assert evidence["ids"] == 21


@pytest.mark.parametrize(
    "scenario", ["startup-counts", "desktop-errors", "no-display", "initially-absent"]
)
def test_audit_window_boundaries(tmp_path, scenario):
    result = run_window(tmp_path, scenario)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize(
    "target", ["title", "disabled-text", "language_row", "device_row"]
)
def test_text_check_detects_any_catalog_key(tmp_path, target):
    result = run_window(tmp_path, "text-leak:" + target)
    assert result.returncode == 0, result.stdout + result.stderr


def test_layout_translation_check_detects_wrong_language(tmp_path):
    result = run_window(tmp_path, "wrong-translation")
    assert result.returncode == 0, result.stdout + result.stderr


def test_window_harness_uses_public_owner_lifecycle():
    import ast

    tree = ast.parse((Path(__file__).parent / "fixtures/run_settings.py").read_text())
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "_appeared"
        for node in ast.walk(tree)
    )
