# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Fermich srl
"""Explicit developer install; never enables or starts the unit on install."""

import argparse
import shutil
import subprocess
from pathlib import Path

from scambio.files import write_text


def checked_path(path: Path) -> Path:
    if any(char in str(path) for char in "\r\n\0"):
        raise ValueError("Installation paths must not contain CR, LF or NUL")
    return path.resolve()


def packaged_installation() -> bool:
    if Path("/usr/bin/scambio").exists():
        return True
    flatpak = shutil.which("flatpak", path="/usr/bin:/bin")
    if flatpak:
        for scope in ("--user", "--system"):
            if (
                subprocess.run(
                    [flatpak, scope, "info", "app.scambio.Scambio"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                ).returncode
                == 0
            ):
                return True
    return False


def render(repo: Path) -> str:
    # systemd specifier expansion and quoted ExecStart syntax.
    escaped = (
        str(checked_path(repo))
        .replace("%", "%%")
        .replace("\\", "\\\\")
        .replace('"', '\\"')
    )

    return (
        (repo / "packaging/systemd/scambio.service")
        .read_text()
        .replace("@REPO@", escaped)
    )


def desktop_value(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )


def desktop_exec(path: Path) -> str:
    value = str(checked_path(path))
    for char in ("\\", '"', "$", "`"):
        value = value.replace(char, "\\" + char)
    return '"' + desktop_value(value.replace("%", "%%")) + '"'


def render_desktop(repo: Path) -> str:
    executable = checked_path(repo) / ".venv/bin/scambio"
    return (
        (repo / "design/desktop/app.scambio.Scambio.desktop.in")
        .read_text()
        .replace("TryExec=@EXEC@", "TryExec=" + desktop_value(str(executable)))
        .replace("@EXEC@", desktop_exec(executable))
        .replace(
            "@ICON@",
            desktop_value(
                str(
                    repo.resolve()
                    / "design/icons/hicolor/scalable/apps/app.scambio.Scambio.svg"
                )
            ),
        )
    )


def render_dbus_service(repo: Path) -> str:
    executable = str(checked_path(repo) / ".venv/bin/scambio")
    for char in ("\\", '"', "$", "`"):
        executable = executable.replace(char, "\\" + char)
    return (
        "[D-BUS Service]\nName=app.scambio.Scambio.Settings\nExec="
        + '"'
        + executable
        + '"'
        + " settings --gapplication-service\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["install", "uninstall"])
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    destination = Path.home() / ".config/systemd/user/scambio.service"
    desktop = Path.home() / ".local/share/applications/app.scambio.Scambio.desktop"
    service = (
        Path.home()
        / ".local/share/dbus-1/services/app.scambio.Scambio.Settings.service"
    )
    if args.command == "install":
        if not args.force and packaged_installation():
            parser.error(
                "A packaged Scambio installation exists; use --force for development"
            )
        repo = Path(__file__).resolve().parents[1]
        for path, text in (
            (destination, render(repo)),
            (desktop, render_desktop(repo)),
            (service, render_dbus_service(repo)),
        ):
            checked_path(path.parent)
            write_text(path, text)
    else:
        # Missing/inactive units are already in the requested state.
        subprocess.run(["/usr/bin/systemctl", "--user", "stop", "scambio"], check=False)
        subprocess.run(
            ["/usr/bin/systemctl", "--user", "disable", "scambio"], check=False
        )
        destination.unlink(missing_ok=True)
        desktop.unlink(missing_ok=True)
        service.unlink(missing_ok=True)
    subprocess.run(["/usr/bin/systemctl", "--user", "daemon-reload"], check=True)


if __name__ == "__main__":
    main()
