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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["install", "uninstall"])
    args = parser.parse_args()
    destination = Path.home() / ".config/systemd/user/scambio.service"
    if args.command == "install":
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(render(Path(__file__).resolve().parents[1]))
    else:
        # Missing/inactive units are already in the requested state.
        subprocess.run(["systemctl", "--user", "stop", "scambio"], check=False)
        subprocess.run(["systemctl", "--user", "disable", "scambio"], check=False)
        destination.unlink(missing_ok=True)
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)


if __name__ == "__main__":
    main()
