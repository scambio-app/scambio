"""Exercise uninstall entirely with a temporary destination and fake systemctl."""

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import dbus
import dbusmock
import pytest
from gi.repository import Gio, GLib
from helpers import spin_until


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


@pytest.mark.parametrize("folder", ["repo with space", 'repo \\ quote" dollar$ tick`'])
def test_install_launcher_and_activation_service(tmp_path, monkeypatch, folder):
    root = Path(__file__).parents[1]
    spec = importlib.util.spec_from_file_location(
        "install_user", root / "tools/install_user.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    repo = tmp_path / folder
    for name in (
        "packaging/systemd/scambio.service",
        "design/desktop/app.scambio.Scambio.desktop.in",
    ):
        dest = repo / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / name, dest)
    executable = repo / ".venv/bin/scambio"
    executable.parent.mkdir(parents=True)
    marker = tmp_path / "argv.json"
    executable.write_text(
        "#!/usr/bin/python3\nimport json,sys\n"
        + f'open({str(marker)!r}, "w").write(json.dumps(sys.argv))\n'
    )
    executable.chmod(0o755)
    home = tmp_path / "home"
    monkeypatch.setattr(module, "__file__", str(repo / "tools/install_user.py"))
    monkeypatch.setattr(module.Path, "home", lambda: home)
    original_run = subprocess.run
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda args, check: subprocess.CompletedProcess(args, 0),
    )
    monkeypatch.setattr(sys, "argv", ["install_user", "install"])
    module.main()
    desktop = home / ".local/share/applications/app.scambio.Scambio.desktop"
    service = home / ".local/share/dbus-1/services/app.scambio.Scambio.Settings.service"
    validation = original_run(
        ["desktop-file-validate", str(desktop)], capture_output=True, text=True
    )
    assert validation.returncode == 0, validation.stdout + validation.stderr
    launcher = Gio.DesktopAppInfo.new_from_filename(str(desktop))
    assert launcher is not None
    assert launcher.launch([], None)
    spin_until(marker.exists)
    assert json.loads(marker.read_text()) == [str(executable), "settings"]
    keyfile = GLib.KeyFile()
    keyfile.load_from_file(str(service), GLib.KeyFileFlags.NONE)
    assert keyfile.get_string("D-BUS Service", "Name") == "app.scambio.Scambio.Settings"
    assert service.read_text().endswith(" settings --gapplication-service\n")
    assert "@EXEC@" not in desktop.read_text() and "@ICON@" not in desktop.read_text()
    assert (home / ".config/systemd/user/scambio.service").exists()
    monkeypatch.setattr(sys, "argv", ["install_user", "uninstall"])
    module.main()
    assert not desktop.exists() and not service.exists()


def test_literal_percent_is_escaped_per_desktop_entry_spec(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "install_user", Path(__file__).parents[1] / "tools/install_user.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    path = tmp_path / "repo%" / "scambio"
    assert module.desktop_exec(path) == '"' + str(path).replace("%", "%%") + '"'


def test_dbus_activation_executes_path_with_spaces(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "install_user", Path(__file__).parents[1] / "tools/install_user.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    repo = tmp_path / "repo with spaces"
    executable = repo / ".venv/bin/scambio"
    executable.parent.mkdir(parents=True)
    marker = tmp_path / "activation.json"
    executable.write_text(
        "#!/usr/bin/python3\nimport json,sys\n"
        + f'open({str(marker)!r}, "w").write(json.dumps(sys.argv))\nsys.exit(1)\n'
    )
    executable.chmod(0o755)
    # This fake executable deliberately exits without acquiring the name:
    # ChildExited proves that activation executed it, and argv proves quoting.
    import os

    address = os.environ["DBUS_SESSION_BUS_ADDRESS"]
    private = dbusmock.PrivateDBus(dbusmock.BusType.SESSION)
    (private.servicedir / "app.scambio.Scambio.Settings.service").write_text(
        module.render_dbus_service(repo)
    )
    try:
        with private:
            bus = dbus.bus.BusConnection(private.address)
            try:
                with pytest.raises(dbus.exceptions.DBusException) as error:
                    bus.start_service_by_name("app.scambio.Scambio.Settings")
                assert (
                    error.value.get_dbus_name()
                    == "org.freedesktop.DBus.Error.Spawn.ChildExited"
                )
                assert json.loads(marker.read_text()) == [
                    str(executable),
                    "settings",
                    "--gapplication-service",
                ]
            finally:
                bus.close()
    finally:
        os.environ["DBUS_SESSION_BUS_ADDRESS"] = address
