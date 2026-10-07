# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Fermich srl
"""Install local artifacts in disposable Docker and Flatpak installations."""

import configparser
import functools
import http.server
import json
import os
import shutil
import tempfile
import threading
from pathlib import Path

from release import APP, DIST, KEY, ROOT, SITE, Signing, digest, run, seal, version

DOCKER_SCRIPT = r"""
set -eu
export DEBIAN_FRONTEND=noninteractive
printf '#!/bin/sh\nexit 101\n' > /usr/sbin/policy-rc.d
chmod 755 /usr/sbin/policy-rc.d
apt-get update
apt-get install -y --no-install-recommends systemd ca-certificates
dpkg-deb -R /artifacts/scambio_*_all.deb /tmp/old-scambio
sed -i 's/^Version: .*/Version: 0.9.0/' /tmp/old-scambio/DEBIAN/control
dpkg-deb --root-owner-group --build /tmp/old-scambio /tmp/scambio_0.9.0_all.deb
mkdir -p /root/.config/scambio /root/.local/share/scambio
printf 'sentinel\n' > /root/.config/scambio/config.toml
printf 'sentinel\n' > /root/.local/share/scambio/state.json
apt-get install -y /tmp/scambio_0.9.0_all.deb
apt-get install -y /artifacts/scambio_*_all.deb
test "$(scambio --version)" = "$SCAMBIO_EXPECTED_VERSION"
test -L /etc/systemd/user/graphical-session.target.wants/scambio.service
test ! -e /etc/apt/sources.list.d/scambio.sources.dpkg-new
test "$(cat /root/.config/scambio/config.toml)" = sentinel
sed -i "s|https://scambio.app/apt|$SCAMBIO_TEST_APT|" \
    /etc/apt/sources.list.d/scambio.sources
apt-get update -o APT::Update::Error-Mode=any
apt-cache policy scambio
systemd-analyze --user verify /usr/lib/systemd/user/scambio.service
apt-get remove -y scambio
test ! -e /etc/apt/sources.list.d/scambio.sources
test ! -L /etc/systemd/user/graphical-session.target.wants/scambio.service
test "$(cat /root/.local/share/scambio/state.json)" = sentinel
apt-get purge -y scambio
apt-get install -y /artifacts/scambio_*_all.deb
test "$(scambio --version)" = "$SCAMBIO_EXPECTED_VERSION"
apt-get purge -y scambio
test ! -e /usr/bin/scambio
test "$(cat /root/.config/scambio/config.toml)" = sentinel
"""


def permissions(text):
    config = configparser.ConfigParser(interpolation=None)
    config.read_string(text)
    observed = {
        section: {
            key: set(value.rstrip(";").split(";"))
            for key, value in config[section].items()
        }
        for section in config.sections()
    }
    expected = {
        "Context": {
            "shared": {"ipc"},
            "sockets": {"wayland", "fallback-x11", "pulseaudio"},
            "devices": {"dri"},
        },
        "Session Bus Policy": {
            name: {"talk"}
            for name in (
                "org.mpris.MediaPlayer2.*",
                "org.kde.kglobalaccel",
                "org.kde.StatusNotifierWatcher",
                "org.freedesktop.Notifications",
                "org.freedesktop.ScreenSaver",
            )
        },
        "System Bus Policy": {
            "org.bluez": {"talk"},
            "org.freedesktop.login1": {"talk"},
        },
    }
    if observed != expected:
        raise ValueError(f"Flatpak permissions differ from decision 153: {observed!r}")


def verify_files():
    value = version()
    signer = Signing()
    for name in (f"scambio_{value}_all.deb", f"scambio-{value}.tar.gz", "SHA256SUMS"):
        signer.verify(DIST / name, DIST / (name + ".asc"))
    run("sha256sum", "--check", "SHA256SUMS", cwd=DIST)
    stable = SITE / "apt/dists/stable"
    signer.verify(stable / "Release", stable / "InRelease", clear=True)
    signer.verify(stable / "Release", stable / "Release.gpg")
    release = (stable / "Release").read_text()
    assert "Acquire-By-Hash: yes" in release and "Date:" in release
    assert all(item not in release for item in ("MD5", "SHA1", "Valid-Until"))
    latest = json.loads((SITE / "download/latest.json").read_text())
    assert latest == {
        "version": value,
        "deb": f"scambio_{value}_all.deb",
        "sha256": digest(DIST / f"scambio_{value}_all.deb"),
    }
    run(
        "appstreamcli",
        "validate",
        "--pedantic",
        "--no-net",
        ROOT / f"design/metainfo/{APP}.metainfo.xml",
    )


def docker():
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(SITE)
    )
    with http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler) as server:
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            for image in ("ubuntu:24.04", "debian:13"):
                run(
                    "docker",
                    "run",
                    "--rm",
                    "--network=host",
                    "--mount",
                    f"type=bind,src={DIST},dst=/artifacts,readonly",
                    "--env",
                    f"SCAMBIO_EXPECTED_VERSION={version()}",
                    "--env",
                    f"SCAMBIO_TEST_APT=http://127.0.0.1:{server.server_port}/apt",
                    image,
                    "sh",
                    "-c",
                    DOCKER_SCRIPT,
                )
        finally:
            server.shutdown()
            worker.join()


def flatpak():
    with tempfile.TemporaryDirectory(prefix="scambio-flatpak-verify-") as temporary:
        installation = Path(temporary) / "installation"
        installation.mkdir()
        # Runtimes are already installed; reuse their deployment read-only.
        # All application deployment/repo operations target the temporary directory.
        runtimes = Path.home() / ".local/share/flatpak/runtime"
        (installation / "runtime").symlink_to(runtimes)
        env = {**os.environ, "FLATPAK_USER_DIR": str(installation)}
        run(
            "flatpak",
            "--user",
            "remote-add",
            f"--gpg-import={KEY}",
            "scambio-test",
            str(SITE / "flatpak/repo"),
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
        shown = run(
            "flatpak",
            "--user",
            "info",
            "--show-permissions",
            APP,
            env=env,
            capture=True,
        )
        print(shown)
        permissions(shown)
        result = run(
            "flatpak",
            "run",
            "--user",
            "--no-documents-portal",
            "--command=scambio",
            APP + "//stable",
            "--version",
            env=env,
            capture=True,
        )
        assert result.strip() == version(), result


def main():
    verify_files()
    docker()
    flatpak()
    seal()
    destination = ROOT.parent / "scambio-site/public"
    for directory in ("apt", "flatpak", "download"):
        shutil.copytree(SITE / directory, destination / directory, dirs_exist_ok=True)
    for item in SITE.iterdir():
        if item.is_file():
            shutil.copyfile(item, destination / item.name)
    (destination / ".well-known").mkdir(exist_ok=True)


if __name__ == "__main__":
    main()
