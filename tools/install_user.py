"""Explicit developer install; never enables or starts the unit on install."""

import argparse
import subprocess
from pathlib import Path


def render(repo: Path) -> str:
    # systemd specifier expansion and quoted ExecStart syntax.
    escaped = (
        str(repo.resolve()).replace("%", "%%").replace("\\", "\\\\").replace('"', '\\"')
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
    value = str(path.resolve())
    for char in ("\\", '"', "$", "`"):
        value = value.replace(char, "\\" + char)
    return '"' + desktop_value(value.replace("%", "%%")) + '"'


def render_desktop(repo: Path) -> str:
    executable = repo.resolve() / ".venv/bin/scambio"
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
    executable = str(repo.resolve() / ".venv/bin/scambio")
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
    args = parser.parse_args()
    destination = Path.home() / ".config/systemd/user/scambio.service"
    desktop = Path.home() / ".local/share/applications/app.scambio.Scambio.desktop"
    service = (
        Path.home()
        / ".local/share/dbus-1/services/app.scambio.Scambio.Settings.service"
    )
    if args.command == "install":
        repo = Path(__file__).resolve().parents[1]
        for path, text in (
            (destination, render(repo)),
            (desktop, render_desktop(repo)),
            (service, render_dbus_service(repo)),
        ):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
    else:
        # Missing/inactive units are already in the requested state.
        subprocess.run(["systemctl", "--user", "stop", "scambio"], check=False)
        subprocess.run(["systemctl", "--user", "disable", "scambio"], check=False)
        destination.unlink(missing_ok=True)
        desktop.unlink(missing_ok=True)
        service.unlink(missing_ok=True)
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)


if __name__ == "__main__":
    main()
