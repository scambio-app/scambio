# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Fermich srl
"""Ten-minute endpoint measurements of installed artifacts on private buses."""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import dbusmock
from release import APP, DIST, KEY, digest, run, version

PROBE = r'''
import atexit, json, os, shutil, signal, sys, tempfile, time
from pathlib import Path
from gi.repository import GLib
from scambio.core.service import run
import scambio

root = Path(tempfile.mkdtemp(prefix="scambio-artifact-idle-"))
atexit.register(shutil.rmtree, root)
pactl = root / "pactl.py"
pactl.write_text("""import signal,sys
args = sys.argv[1:]
if args == ['--version']: print('pactl 17.0')
elif args == ['-f', 'json', 'subscribe']: signal.pause()
elif args[:3] == ['-f', 'json', 'list']: print('[]')
elif args == ['get-default-sink']: print('default')
else: sys.exit(1)
""")
os.environ['XDG_CONFIG_HOME'] = str(root / 'config')
os.environ['XDG_DATA_HOME'] = str(root / 'data')
measurement = {}

def usage():
    stat = Path('/proc/self/stat').read_text().split(')', 1)[1].split()
    return {
        'cpu_seconds': (int(stat[11]) + int(stat[12])) / os.sysconf('SC_CLK_TCK'),
        'rss_kib': int(stat[21]) * os.sysconf('SC_PAGE_SIZE') // 1024,
    }

def finish():
    elapsed = time.monotonic() - measurement['start']
    end = usage()
    result = {
        'version': scambio.__version__, 'module': scambio.__file__,
        'elapsed_seconds': elapsed, 'before': measurement['before'], 'after': end,
        'cpu_percent': 100 * (
            end['cpu_seconds'] - measurement['before']['cpu_seconds']) / elapsed,
        'environment': ('Private system/session buses; no device configured; '
                        'healthy injected pactl; UI enabled'),
        'method': ('Two /proc/self/stat endpoint samples, 600 seconds apart; '
                   'no sampling loop'),
    }
    print(json.dumps(result), flush=True)
    os.kill(os.getpid(), signal.SIGTERM)
    return False

def start():
    measurement.update(start=time.monotonic(), before=usage())
    print('MEASUREMENT_STARTED', flush=True)
    GLib.timeout_add(600000, finish)
    return False

GLib.timeout_add_seconds(3, start)
raise SystemExit(run(root / 'config.toml', root / 'state.json',
                     pactl=[sys.executable, str(pactl)]))
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("format", choices=["deb", "flatpak"])
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    with (
        tempfile.TemporaryDirectory(prefix="scambio-artifact-measure-") as temporary,
        dbusmock.PrivateDBus(dbusmock.BusType.SYSTEM),
        dbusmock.PrivateDBus(dbusmock.BusType.SESSION),
    ):
        root = Path(temporary)
        env = dict(os.environ)
        if args.format == "deb":
            package = DIST / f"scambio_{version()}_all.deb"
            run("dpkg-deb", "--extract", package, root / "extracted")
            venv = root / "venv"
            run(sys.executable, "-m", "venv", "--system-site-packages", venv)
            python = venv / "bin/python"
            purelib = Path(
                run(
                    python,
                    "-I",
                    "-c",
                    "import sysconfig;print(sysconfig.get_path('purelib'))",
                    capture=True,
                ).strip()
            )
            shutil.copytree(
                root / "extracted/usr/lib/python3/dist-packages",
                purelib,
                dirs_exist_ok=True,
            )
            shutil.copytree(
                root / "extracted/usr/share/scambio", venv / "share/scambio"
            )
            command = [str(python), "-I", "-c", PROBE]
            artifact = {"deb_sha256": digest(package)}
        else:
            installation = root / "flatpak"
            installation.mkdir()
            (installation / "runtime").symlink_to(
                Path.home() / ".local/share/flatpak/runtime"
            )
            env["FLATPAK_USER_DIR"] = str(installation)
            run(
                "flatpak",
                "--user",
                "remote-add",
                f"--gpg-import={KEY}",
                "scambio-test",
                DIST / "flatpak-repo",
                env=env,
            )
            run(
                "flatpak",
                "--user",
                "install",
                "--noninteractive",
                "--no-deps",
                "--no-related",
                "scambio-test",
                APP + "//stable",
                env=env,
            )
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
            artifact = {
                "ostree_commit": run(
                    "flatpak",
                    "--user",
                    "info",
                    "--show-commit",
                    APP,
                    env=env,
                    capture=True,
                ).strip()
            }
        process = subprocess.Popen(command, env=env, text=True, stdout=subprocess.PIPE)
        try:
            assert process.stdout is not None
            result = None
            for line in process.stdout:
                print(line, end="", flush=True)
                if line.startswith("{"):
                    result = json.loads(line)
            if process.wait(timeout=15) != 0 or result is None:
                raise RuntimeError("Artifact measurement did not complete")
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps({**artifact, **result}, indent=2) + "\n")
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=15)


if __name__ == "__main__":
    main()
