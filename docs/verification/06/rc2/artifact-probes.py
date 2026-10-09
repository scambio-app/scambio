# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Fermich srl
"""Measure installed rc2 artifacts on private buses and check their icons."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import dbusmock

EVIDENCE = Path(__file__).resolve().parent
DIST = Path(sys.argv[2]).resolve()
APP = "app.scambio.Scambio"
MODE = sys.argv[1]

PROBE = r"""
import json, os, signal, sys, tempfile, time
from pathlib import Path
from gi.repository import GLib
import scambio
from scambio.core.service import run

for name in ("DBUS_SYSTEM_BUS_ADDRESS", "DBUS_SESSION_BUS_ADDRESS"):
    assert "dbusmock_data_" in os.environ[name] or Path("/.flatpak-info").exists(), name
fake = (
    "import sys,signal; args=sys.argv[1:]; "
    "signal.pause() if 'subscribe' in args else "
    "print('pactl 17.0' if args==['--version'] else "
    "'default' if args==['get-default-sink'] else '[]')"
)
root = Path(tempfile.mkdtemp(prefix="scambio-rc2-idle-"))
(root / "config.toml").write_text('[shortcut]\npreferred = ""\n')
(root / "state.json").write_text("{}")


def usage():
    fields = Path("/proc/self/stat").read_text().split(")", 1)[1].split()
    return {
        "cpu_seconds": (int(fields[11]) + int(fields[12])) / os.sysconf("SC_CLK_TCK"),
        "rss_kib": int(fields[21]) * os.sysconf("SC_PAGE_SIZE") // 1024,
    }


def begin():
    before = usage()
    start = time.monotonic()
    print("MEASUREMENT_STARTED", flush=True)

    def end():
        after = usage()
        elapsed = time.monotonic() - start
        print(
            "RESULT "
            + json.dumps(
                {
                    "version": scambio.__version__,
                    "module": scambio.__file__,
                    "elapsed_seconds": elapsed,
                    "before": before,
                    "after": after,
                    "cpu_percent": 100
                    * (after["cpu_seconds"] - before["cpu_seconds"])
                    / elapsed,
                    "environment": (
                        "Private system/session buses; no device configured; "
                        "healthy injected pactl; UI enabled"
                    ),
                    "method": (
                        "Two /proc/self/stat endpoint samples, "
                        "600 seconds apart; no sampling loop"
                    ),
                }
            ),
            flush=True,
        )
        os.kill(os.getpid(), signal.SIGTERM)
        return False

    GLib.timeout_add(600000, end)
    return False


GLib.timeout_add(1000, begin)
raise SystemExit(
    run(root / "config.toml", root / "state.json", [sys.executable, "-I", "-c", fake])
)
"""


def run(*args, env=None, capture=False):
    print(
        "+",
        *map(str, args[: args.index("-c") + 1] if "-c" in args else args),
        flush=True,
    )
    return subprocess.run(
        list(map(str, args)),
        check=True,
        env=env,
        text=True,
        stdout=subprocess.PIPE if capture else None,
    ).stdout


with tempfile.TemporaryDirectory(prefix="scambio-rc2-artifact-") as tmp:
    root = Path(tmp)
    env = dict(os.environ)
    if MODE == "deb":
        package = DIST / "scambio_1.0.1_all.deb"
        run("dpkg-deb", "--extract", package, root / "extracted")
        run(sys.executable, "-m", "venv", "--system-site-packages", root / "venv")
        python = root / "venv/bin/python"
        purelib = Path(
            run(
                python,
                "-I",
                "-c",
                "import sysconfig; print(sysconfig.get_path('purelib'))",
                capture=True,
            ).strip()
        )
        shutil.copytree(
            root / "extracted/usr/lib/python3/dist-packages",
            purelib,
            dirs_exist_ok=True,
        )
        env["SCAMBIO_DATA_DIR"] = str(root / "extracted/usr/share/scambio")
        command = [str(python), "-I", "-c", PROBE]
        provenance = {"deb_sha256": hashlib.sha256(package.read_bytes()).hexdigest()}
    else:
        installation = root / "installation"
        installation.mkdir()
        (installation / "runtime").symlink_to(
            Path.home() / ".local/share/flatpak/runtime"
        )
        env["FLATPAK_USER_DIR"] = str(installation)
        run(
            "flatpak",
            "--user",
            "remote-add",
            "--gpg-import="
            + str(DIST.parents[2] / "packaging/keys/scambio-archive-keyring.gpg"),
            "scambio-rc2",
            str(DIST / "site/flatpak/repo"),
            env=env,
        )
        run(
            "flatpak",
            "--user",
            "install",
            "--noninteractive",
            "--no-deps",
            "--no-related",
            "scambio-rc2",
            APP + "//stable",
            env=env,
        )
        commit = run(
            "flatpak", "--user", "info", "--show-commit", APP, env=env, capture=True
        ).strip()
        location = Path(
            run(
                "flatpak",
                "--user",
                "info",
                "--show-location",
                APP,
                env=env,
                capture=True,
            ).strip()
        )
        run(
            sys.executable,
            EVIDENCE / "check-icons.py",
            location / "files",
            EVIDENCE / "expected-icons.json",
        )
        exported = location / "export/share/applications" / f"{APP}.desktop"
        run("desktop-file-validate", exported)
        assert "Icon=" + APP in exported.read_text()
        for rel in (
            "scalable/apps/app.scambio.Scambio.svg",
            "symbolic/apps/app.scambio.Scambio-symbolic.svg",
        ):
            assert (location / "export/share/icons/hicolor" / rel).read_bytes() == (
                location / "files/share/icons/hicolor" / rel
            ).read_bytes()
        command = [
            "flatpak",
            "run",
            "--user",
            "--no-documents-portal",
            "--command=python3",
            APP + "//stable",
            "-I",
            "-c",
            PROBE,
        ]
        provenance = {"ostree_commit": commit}
    with (
        dbusmock.PrivateDBus(dbusmock.BusType.SYSTEM) as system,
        dbusmock.PrivateDBus(dbusmock.BusType.SESSION) as session,
    ):
        assert (
            "dbusmock_data_" in system.address and "dbusmock_data_" in session.address
        )
        env.update(
            DBUS_SYSTEM_BUS_ADDRESS=system.address,
            DBUS_SESSION_BUS_ADDRESS=session.address,
        )
        result = run(*command, env=env, capture=True)
        print(result, flush=True)
        record = json.loads(
            next(line[7:] for line in result.splitlines() if line.startswith("RESULT "))
        )
        assert record["elapsed_seconds"] >= 600 and record["version"] == "1.0.1"
        record.update(provenance)
        (EVIDENCE / f"idle-{MODE}.json").write_text(json.dumps(record, indent=2) + "\n")
    if MODE == "flatpak":
        run("flatpak", "--user", "uninstall", "--noninteractive", APP, env=env)
