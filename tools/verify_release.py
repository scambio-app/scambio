# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Fermich srl
"""Install local artifacts in disposable Docker and Flatpak installations."""

import argparse
import configparser
import functools
import http.server
import json
import os
import shutil
import subprocess
import tempfile
import threading
from contextlib import ExitStack
from pathlib import Path

import dbusmock
from release import (
    APP,
    DIST,
    KEY,
    ROOT,
    SITE,
    Signing,
    digest,
    repository_archives,
    run,
    seal,
    version,
)

DOCKER_SCRIPT = r"""
set -eu
export DEBIAN_FRONTEND=noninteractive
printf '#!/bin/sh\nexit 101\n' > /usr/sbin/policy-rc.d
chmod 755 /usr/sbin/policy-rc.d
apt-get update
apt-get install -y --no-install-recommends ca-certificates
if [ "$SCAMBIO_TEST_SYSTEMD" = yes ]; then
    apt-get install -y --no-install-recommends systemd
else
    # dconf accepts either session-bus provider; select the non-systemd one.
    printf '%s\n' 'Package: systemd systemd-sysv libpam-systemd' \
        'Pin: version *' 'Pin-Priority: -1' \
        > /etc/apt/preferences.d/scambio-test-no-systemd
    apt-get install -y --no-install-recommends dbus-x11
    test ! -e /usr/bin/systemctl
fi
mkdir -p /root/.config/scambio /root/.local/share/scambio
printf '[device]\nprofile = "generic"\n' > /root/.config/scambio/config.toml
cp /root/.config/scambio/config.toml /tmp/original-config.toml
printf 'sentinel\n' > /root/.local/share/scambio/state.json
apt-get install -y --no-install-recommends /previous/scambio_*_all.deb
test "$(scambio --version)" = "$SCAMBIO_PREVIOUS_VERSION"
sed -i "s|https://scambio.app/apt|$SCAMBIO_TEST_APT|" \
    /etc/apt/sources.list.d/scambio.sources
apt-get update -o APT::Update::Error-Mode=any
apt-cache policy scambio
apt-get install -y --no-install-recommends --only-upgrade scambio
test "$(scambio --version)" = "$SCAMBIO_EXPECTED_VERSION"
python3 -I -c '
from pathlib import Path
from scambio.config import Config, load, parse, resolve_profile
assert Config().audio.ignore_apps == ("sd_dummy", "speech-dispatcher-dummy")
assert Config().device.profile == "auto"
assert load(Path("/root/.config/scambio/config.toml")).device.profile == "generic"
assert load(Path("/tmp/clean-config/config.toml")).device.profile == "auto"
assert resolve_profile("auto", "Oakley Meta") == "meta_glasses"
assert resolve_profile("generic", "Oakley Meta") == "generic"
explicit = parse({"policy": {"resume_delay_ms": 0}})
assert explicit.resume_delay_explicit and explicit.policy.resume_delay_ms == 0
'
if [ "$SCAMBIO_TEST_SYSTEMD" = yes ]; then
    test -L /etc/systemd/user/graphical-session.target.wants/scambio.service
else
    test ! -e /usr/bin/systemctl
    test ! -L /etc/systemd/user/graphical-session.target.wants/scambio.service
fi
test ! -e /etc/apt/sources.list.d/scambio.sources.dpkg-new
cmp /root/.config/scambio/config.toml /tmp/original-config.toml
sed -i "s|https://scambio.app/apt|$SCAMBIO_TEST_APT|" \
    /etc/apt/sources.list.d/scambio.sources
apt-get update -o APT::Update::Error-Mode=any
apt-cache policy scambio
if [ "$SCAMBIO_TEST_SYSTEMD" = yes ]; then
    mkdir -m 700 /tmp/scambio-systemd-runtime
    XDG_RUNTIME_DIR=/tmp/scambio-systemd-runtime \
        systemd-analyze --user verify /usr/lib/systemd/user/scambio.service
fi
apt-get remove -y scambio
test ! -e /etc/apt/sources.list.d/scambio.sources
test ! -L /etc/systemd/user/graphical-session.target.wants/scambio.service
test "$(cat /root/.local/share/scambio/state.json)" = sentinel
apt-get purge -y scambio
apt-get install -y --no-install-recommends /artifacts/scambio_*_all.deb
test "$(scambio --version)" = "$SCAMBIO_EXPECTED_VERSION"
apt-get purge -y scambio
test ! -e /usr/bin/scambio
cmp /root/.config/scambio/config.toml /tmp/original-config.toml
if [ "$SCAMBIO_TEST_SYSTEMD" = no ]; then test ! -e /usr/bin/systemctl; fi
printf 'PASS package lifecycle %s -> %s (systemd=%s)\n' \
    "$SCAMBIO_PREVIOUS_VERSION" "$SCAMBIO_EXPECTED_VERSION" "$SCAMBIO_TEST_SYSTEMD"
"""


def permissions(text):
    config = configparser.ConfigParser(interpolation=None)
    config.optionxform = str
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
            # Flatpak renders fallback-x11 as both bits; the manifest permits
            # only fallback-x11, and this exact rendering is the golden result.
            "sockets": {"wayland", "fallback-x11", "x11", "pulseaudio"},
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


def upgrade_source():
    """Require an authenticated, genuinely older release, never a relabelled build."""
    current = tuple(map(int, version().split(".")))
    candidates = [
        directory
        for directory in repository_archives()
        if tuple(map(int, directory.name.split("."))) < current
    ]
    if not candidates:
        raise ValueError(
            "No sealed previous release available for upgrade verification"
        )
    source = max(candidates, key=lambda path: tuple(map(int, path.name.split("."))))
    package = source / f"scambio_{source.name}_all.deb"
    Signing.verify(package, Path(str(package) + ".asc"))
    print(f"Upgrade baseline: sealed {source.name}; deb SHA256 {digest(package)}")
    return source


def docker(previous):
    handler = functools.partial(
        http.server.SimpleHTTPRequestHandler, directory=str(SITE)
    )
    with http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler) as server:
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            for image, systemd in (
                ("ubuntu:24.04", "yes"),
                ("debian:13", "yes"),
                ("ubuntu:24.04", "no"),
                ("debian:13", "no"),
            ):
                run(
                    "docker",
                    "run",
                    "--rm",
                    "--network=host",
                    "--mount",
                    f"type=bind,src={DIST},dst=/artifacts,readonly",
                    "--mount",
                    f"type=bind,src={previous},dst=/previous,readonly",
                    "--env",
                    f"SCAMBIO_PREVIOUS_VERSION={previous.name}",
                    "--env",
                    f"SCAMBIO_EXPECTED_VERSION={version()}",
                    "--env",
                    f"SCAMBIO_TEST_SYSTEMD={systemd}",
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


def flatpak(previous):
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
            str(previous / "ostree"),
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
        flatpak_version(env, previous.name)
        old_commit = run(
            "flatpak", "--user", "info", "--show-commit", APP, env=env, capture=True
        ).strip()
        assert old_commit == (previous / "ostree.commit").read_text().strip()
        run(
            "flatpak",
            "--user",
            "remote-modify",
            f"--url={SITE / 'flatpak/repo'}",
            "scambio-test",
            env=env,
        )
        run(
            "flatpak",
            "--user",
            "update",
            "--noninteractive",
            "--no-deps",
            "--no-related",
            APP,
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
        flatpak_version(env, version())
        negative_bus_access(env)
        for reinstall in (True, False):
            run("flatpak", "--user", "uninstall", "--noninteractive", APP, env=env)
            result = subprocess.run(
                ["flatpak", "--user", "info", APP], env=env, capture_output=True
            )
            assert result.returncode != 0
            if reinstall:
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
                flatpak_version(env, version())
        print(f"PASS Flatpak lifecycle {previous.name} -> {version()}")


def flatpak_version(env, expected):
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
    assert result.strip() == expected, result


def negative_bus_access(environment):
    """Prove denial even when the forbidden names exist on the host test buses."""
    with (
        dbusmock.PrivateDBus(dbusmock.BusType.SYSTEM) as system,
        dbusmock.PrivateDBus(dbusmock.BusType.SESSION) as session,
    ):
        with ExitStack() as mocks:
            names = [
                ("--system", "org.freedesktop.UPower", dbusmock.BusType.SYSTEM),
                ("--session", "org.freedesktop.systemd1", dbusmock.BusType.SESSION),
                ("--session", "org.freedesktop.Flatpak", dbusmock.BusType.SESSION),
            ]
            for _scope, name, bustype in names:
                mocks.enter_context(
                    dbusmock.SpawnedMock.spawn_for_name(
                        name, "/", name, bustype=bustype, stdout=subprocess.DEVNULL
                    )
                )
            env = {
                **environment,
                "DBUS_SYSTEM_BUS_ADDRESS": system.address,
                "DBUS_SESSION_BUS_ADDRESS": session.address,
            }
            for scope, name, _bus in names:
                result = subprocess.run(
                    [
                        "flatpak",
                        "run",
                        "--user",
                        "--no-documents-portal",
                        "--command=gdbus",
                        APP + "//stable",
                        "call",
                        scope,
                        "--dest",
                        name,
                        "--object-path",
                        "/",
                        "--method",
                        "org.freedesktop.DBus.Peer.Ping",
                    ],
                    env=env,
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                assert result.returncode != 0
                assert any(
                    error in result.stderr
                    for error in ("ServiceUnknown", "AccessDenied")
                ), result.stderr
                print(f"Denied {scope} {name}: {result.stderr.strip()}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage-site", action="store_true")
    args = parser.parse_args()
    verify_files()
    previous = upgrade_source()
    docker(previous)
    flatpak(previous)
    if not args.stage_site:
        return
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
