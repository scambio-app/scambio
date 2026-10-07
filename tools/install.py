# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Fermich srl
"""Offline installation into PREFIX, optionally staged beneath DESTDIR."""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

APP = "app.scambio.Scambio"
ROOT = Path(__file__).resolve().parents[1]


def install(prefix: Path, destdir: Path, systemd: bool, python_lib: str) -> None:
    target = destdir / prefix.relative_to("/")
    installed: list[str] = []

    def copy(source: Path, relative: str) -> None:
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        destination.chmod(0o644)
        installed.append(relative)

    def tree(source: Path, relative: str) -> None:
        for item in sorted(source.rglob("*")):
            if item.is_file() and "__pycache__" not in item.parts:
                copy(item, str(Path(relative) / item.relative_to(source)))

    def write(relative: str, value: str, mode: int = 0o644) -> None:
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(value)
        destination.chmod(mode)
        installed.append(relative)

    with tempfile.TemporaryDirectory(prefix="scambio-install-") as temporary:
        stage = Path(temporary)
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--no-index",
                "--no-deps",
                "--no-build-isolation",
                "--ignore-installed",
                "--no-compile",
                "--prefix",
                str(prefix),
                "--root",
                str(stage),
                str(ROOT),
            ],
            check=True,
            env={**os.environ, "PIP_DISABLE_PIP_VERSION_CHECK": "1"},
        )
        library = next(stage.rglob("scambio/__init__.py")).parent.parent
        relative = python_lib or str(
            library.relative_to(stage / prefix.relative_to("/"))
        )
        tree(library, relative)
    write("bin/scambio", '#!/bin/sh\nexec /usr/bin/python3 -I -m scambio "$@"\n', 0o755)
    tree(ROOT / "design", "share/scambio/design")
    tree(ROOT / "build/locale", "share/scambio/locale")
    tree(ROOT / "build/ui", "share/scambio/ui")
    tree(ROOT / "design/icons/hicolor", "share/icons/hicolor")
    desktop = (ROOT / f"design/desktop/{APP}.desktop.in").read_text()
    write(
        f"share/applications/{APP}.desktop",
        desktop.replace("@EXEC@", "scambio").replace("@ICON@", APP),
    )
    copy(
        ROOT / f"design/metainfo/{APP}.metainfo.xml",
        f"share/metainfo/{APP}.metainfo.xml",
    )
    executable = str(prefix / "bin/scambio")
    for name, arguments in (
        (APP, "daemon"),
        (APP + ".Settings", "settings --gapplication-service"),
    ):
        service = f"[D-BUS Service]\nName={name}\nExec={executable} {arguments}\n"
        if systemd and name == APP:
            service += "SystemdService=scambio.service\n"
        write(f"share/dbus-1/services/{name}.service", service)
    if systemd:
        unit = (ROOT / "packaging/systemd/scambio.service").read_text()
        write(
            "lib/systemd/user/scambio.service",
            unit.replace('"@REPO@/.venv/bin/scambio"', executable),
        )
    copy(ROOT / "LICENSE", "share/licenses/scambio/LICENSE")
    if prefix == Path("/app"):
        copy(ROOT / "LICENSE", f"share/licenses/{APP}/LICENSE")
    write("share/scambio/install-manifest.json", json.dumps(installed, indent=2) + "\n")


def uninstall(prefix: Path, destdir: Path) -> None:
    target = destdir / prefix.relative_to("/")
    manifest = target / "share/scambio/install-manifest.json"
    for relative in json.loads(manifest.read_text()):
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("Invalid installed manifest path")
        (target / path).unlink(missing_ok=True)
    manifest.unlink()


def main() -> None:
    os.umask(0o022)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["install", "uninstall"])
    parser.add_argument("--prefix", type=Path, default=Path("/usr/local"))
    parser.add_argument("--destdir", type=Path, default=Path("/"))
    parser.add_argument("--systemd", action="store_true")
    parser.add_argument("--python-lib", default="")
    args = parser.parse_args()
    if not args.prefix.is_absolute() or any(c in str(args.prefix) for c in "\r\n\0"):
        parser.error("PREFIX must be absolute and contain no CR, LF or NUL")
    if args.command == "install":
        install(args.prefix, args.destdir, args.systemd, args.python_lib)
    else:
        uninstall(args.prefix, args.destdir)


if __name__ == "__main__":
    main()
