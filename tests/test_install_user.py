"""Exercise uninstall entirely with a temporary destination and fake systemctl."""

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("installed", [False, True])
def test_uninstall_is_idempotent_without_systemctl(tmp_path, monkeypatch, installed):
    path = Path(__file__).parents[1] / "tools/install_user.py"
    spec = importlib.util.spec_from_file_location("install_user", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    destination = tmp_path / ".config/systemd/user/scambio.service"
    if installed:
        destination.parent.mkdir(parents=True)
        destination.write_text("[Unit]\nDescription=Test\n")
    calls = []

    def run(args, *, check):
        assert args[:2] == ["systemctl", "--user"]
        command = args[2]
        assert command in {"stop", "disable", "daemon-reload"}
        calls.append((command, check))
        code = 0 if destination.exists() or command == "daemon-reload" else 5
        if check and code:
            raise subprocess.CalledProcessError(code, args)
        return subprocess.CompletedProcess(args, code)

    monkeypatch.setattr(module.subprocess, "run", run)
    monkeypatch.setattr(module.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(sys, "argv", [str(path), "uninstall"])
    for _ in range(2):
        module.main()
        assert not destination.exists()
    assert calls == [
        ("stop", False),
        ("disable", False),
        ("daemon-reload", True),
        ("stop", False),
        ("disable", False),
        ("daemon-reload", True),
    ]
