# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Fermich srl
"""Fail closed on release key changes, archive tampering and extra permissions."""

import importlib
import json
import time
from pathlib import Path

import pytest


@pytest.fixture
def release_tools(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[1] / "tools"))
    return importlib.import_module("release")


@pytest.mark.parametrize("wrong_key,days", [(True, 365), (False, 89)])
def test_signing_rejects_changed_key_and_approaching_expiry(
    release_tools, monkeypatch, wrong_key, days
):
    release = release_tools
    pub = ["pub"] + [""] * 11
    sub = ["sub"] + [""] * 11
    sub[6], sub[11] = str(int(time.time() + days * 86400)), "s"

    def fingerprint(value):
        return ":".join(["fpr"] + [""] * 8 + [value])

    listing = "\n".join(
        [
            ":".join(pub),
            fingerprint("0" * 40 if wrong_key else release.PRIMARY),
            ":".join(sub),
            fingerprint(release.SIGNER),
        ]
    )
    monkeypatch.setattr(release, "run", lambda *args, **kwargs: listing)
    with pytest.raises(ValueError, match="fingerprint|90 days"):
        release.Signing()


@pytest.mark.parametrize("tamper", ["content", "extra", "symlink"])
def test_archive_refuses_tampering(release_tools, monkeypatch, tmp_path, tamper):
    release = release_tools
    monkeypatch.setattr(release, "ARCHIVE", tmp_path)
    monkeypatch.setattr(release.Signing, "verify", lambda *args, **kwargs: None)
    directory = tmp_path / "1.0.0"
    directory.mkdir()
    artifact = directory / "artifact"
    artifact.write_text("signed bytes")
    (directory / "manifest.json").write_text(
        json.dumps(
            {"version": "1.0.0", "sha256": {"artifact": release.digest(artifact)}}
        )
    )
    (directory / "manifest.json.asc").write_text("signature checked separately")
    assert release.archived() == [directory]
    if tamper == "content":
        artifact.write_text("changed")
    elif tamper == "extra":
        (directory / "unlisted.deb").write_text("not covered")
    else:
        artifact.unlink()
        artifact.symlink_to(directory / "manifest.json")
    with pytest.raises(ValueError, match="Archive|Archived"):
        release.archived()


def test_manifest_permissions_are_exact():
    manifest = Path(__file__).parents[1] / "packaging/flatpak/app.scambio.Scambio.yml"
    permissions = [
        line.strip()[2:]
        for line in manifest.read_text().splitlines()
        if line.strip().startswith("- --")
    ]
    expected = {
        "--share=ipc",
        "--socket=wayland",
        "--socket=fallback-x11",
        "--device=dri",
        "--socket=pulseaudio",
        "--system-talk-name=org.bluez",
        "--system-talk-name=org.freedesktop.login1",
        "--talk-name=org.mpris.MediaPlayer2.*",
        "--talk-name=org.kde.kglobalaccel",
        "--talk-name=org.kde.StatusNotifierWatcher",
        "--talk-name=org.freedesktop.Notifications",
        "--talk-name=org.freedesktop.ScreenSaver",
    }
    assert set(permissions) == expected
    assert len(permissions) == len(expected)


def test_review_candidate_does_not_share_release_directories(release_tools):
    release = release_tools
    dist, archive = release.release_directories()
    candidate_dist, candidate_archive = release.release_directories("audit-1")
    assert dist == release.ROOT / "dist"
    assert archive == Path.home() / ".local/share/scambio-release/archive"
    assert candidate_dist == dist / "candidates/audit-1"
    assert candidate_archive == archive.parent / "candidates/audit-1"
    assert not candidate_archive.is_relative_to(archive)


@pytest.mark.parametrize(
    "candidate", ["", "../archive", "/tmp/release", "x/y", "a" * 65]
)
def test_review_candidate_rejects_invalid_paths(release_tools, candidate):
    with pytest.raises(ValueError, match="identifier"):
        release_tools.release_directories(candidate)


def test_seal_never_replaces_existing_version(release_tools, monkeypatch, tmp_path):
    release = release_tools
    existing, dist = tmp_path / "1.0.0", tmp_path / "dist"
    existing.mkdir()
    dist.mkdir()
    name = "scambio_1.0.0_all.deb"
    (existing / name).write_bytes(b"original sealed candidate")
    (dist / name).write_bytes(b"corrected candidate")
    monkeypatch.setattr(release, "DIST", dist)
    monkeypatch.setattr(release, "check", lambda: "1.0.0")
    monkeypatch.setattr(release, "archived", lambda: [existing])
    with pytest.raises(ValueError, match="Immutable release version"):
        release.seal()
    assert (existing / name).read_bytes() == b"original sealed candidate"


def test_apt_discards_untrusted_staging_packages(release_tools, monkeypatch, tmp_path):
    release = release_tools
    site, dist, previous = (tmp_path / name for name in ("site", "dist", "0.9.0"))
    for directory in (site, dist, previous):
        directory.mkdir()
    pool = site / "apt/pool/unexpected"
    pool.mkdir(parents=True)
    (pool / "injected_99_all.deb").write_bytes(b"untrusted staging")
    (dist / "scambio_1.0.0_all.deb").write_bytes(b"current authenticated package")
    (previous / "scambio_0.9.0_all.deb").write_bytes(b"previous authenticated package")
    monkeypatch.setattr(release, "SITE", site)
    monkeypatch.setattr(release, "DIST", dist)
    monkeypatch.setattr(release, "check", lambda: "1.0.0")
    monkeypatch.setattr(release, "version", lambda: "1.0.0")
    monkeypatch.setattr(release, "archived", lambda: [previous])
    monkeypatch.setattr(release, "latest", lambda: None)
    monkeypatch.setattr(release.Signing, "__init__", lambda self: None)
    monkeypatch.setattr(release.Signing, "verify", lambda *args, **kwargs: None)
    monkeypatch.setattr(release.Signing, "sign", lambda *args, **kwargs: None)

    def run(*args, **kwargs):
        assert sorted(path.name for path in (site / "apt/pool").rglob("*.deb")) == [
            "scambio_0.9.0_all.deb",
            "scambio_1.0.0_all.deb",
        ]
        return ""

    monkeypatch.setattr(release, "run", run)
    release.apt_repo()


def test_candidate_reads_authenticated_published_history(
    release_tools, monkeypatch, tmp_path
):
    release = release_tools
    published, candidate = tmp_path / "published", tmp_path / "candidate"
    monkeypatch.setattr(release, "PUBLISHED_ARCHIVE", published)
    monkeypatch.setattr(release, "ARCHIVE", candidate)
    monkeypatch.setattr(release, "CANDIDATE", "test-rc1")
    monkeypatch.setattr(release.Signing, "verify", lambda *args, **kwargs: None)

    def archive(root, version):
        directory = root / version
        directory.mkdir(parents=True)
        artifact = directory / "artifact"
        artifact.write_text("authenticated bytes " + version)
        (directory / "manifest.json").write_text(
            json.dumps(
                {"version": version, "sha256": {"artifact": release.digest(artifact)}}
            )
        )
        (directory / "manifest.json.asc").write_text("verified separately")
        return directory

    previous = archive(published, "1.0.0")
    current = archive(candidate, "1.0.1")
    assert release.repository_archives() == [previous, current]
    assert release.archived() == [current]  # seal() only sees the candidate archive.
    original = (previous / "artifact").read_bytes()
    archive(candidate, "1.0.0")
    with pytest.raises(ValueError, match="duplicates a published version"):
        release.repository_archives()
    assert (previous / "artifact").read_bytes() == original
    (previous / "artifact").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="hash or path"):
        release.repository_archives()


def test_upgrade_source_requires_a_real_older_release(
    release_tools, monkeypatch, tmp_path
):
    verify = importlib.import_module("verify_release")
    monkeypatch.setattr(verify, "version", lambda: "1.10.0")
    monkeypatch.setattr(verify, "repository_archives", lambda: [])
    with pytest.raises(ValueError, match="No sealed previous"):
        verify.upgrade_source()
    paths = [tmp_path / value for value in ("1.0.0", "1.9.0", "1.10.0", "2.0.0")]
    for path in paths:
        path.mkdir()
        (path / f"scambio_{path.name}_all.deb").write_bytes(b"actual previous package")
    checked = []
    monkeypatch.setattr(verify, "repository_archives", lambda: paths)
    monkeypatch.setattr(verify.Signing, "verify", lambda *args: checked.append(args))
    assert verify.upgrade_source() == paths[1]
    assert checked == [
        (
            paths[1] / "scambio_1.9.0_all.deb",
            paths[1] / "scambio_1.9.0_all.deb.asc",
        )
    ]


def test_copy_sealed_repository_is_writable_without_mutating_source(
    release_tools, tmp_path
):
    source, destination = tmp_path / "sealed", tmp_path / "build"
    source.mkdir()
    (source / ".lock").write_bytes(b"")
    (source / "config").write_text("original config")
    for path in source.iterdir():
        path.chmod(0o444)
    source.chmod(0o555)
    try:
        for _ in range(2):
            release_tools.copy_repository(source, destination)
            assert (destination / "config").read_text() == "original config"
            (destination / ".lock").open("a").close()
            (destination / "config").write_text("updated copy")
            assert (source / "config").read_text() == "original config"
            assert (source / "config").stat().st_mode & 0o777 == 0o444
            assert source.stat().st_mode & 0o777 == 0o555
    finally:
        source.chmod(0o755)
