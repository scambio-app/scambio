# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Fermich srl
"""Build and verify local release artifacts; never deploy, push or create tags."""

import argparse
import base64
import gzip
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import tomllib
import xml.etree.ElementTree as ET
from email.utils import formatdate
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def release_directories(candidate=None):
    """Keep review candidates separate from the immutable release archive."""
    home = Path.home() / ".local/share/scambio-release"
    if candidate is None:
        return ROOT / "dist", home / "archive"
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", candidate):
        raise ValueError("Invalid SCAMBIO_RELEASE_CANDIDATE identifier")
    return ROOT / "dist/candidates" / candidate, home / "candidates" / candidate


CANDIDATE = os.environ.get("SCAMBIO_RELEASE_CANDIDATE")
DIST, ARCHIVE = release_directories(CANDIDATE)
PUBLISHED_ARCHIVE = release_directories()[1]
SITE = DIST / "site"
PRIMARY = "24A30DBED8973273A486CC7386C8855E1251E7E2"
SIGNER = "4C23A6729A5750DDFC8745E305499CD6ECB01DE7"
KEY = ROOT / "packaging/keys/scambio-archive-keyring.gpg"
APP = "app.scambio.Scambio"
VERSION_RE = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")


def run(*args, cwd=ROOT, env=None, capture=False):
    print("+", " ".join(map(str, args)), flush=True)
    return subprocess.run(
        list(map(str, args)),
        cwd=cwd,
        env=env,
        check=True,
        stdout=subprocess.PIPE if capture else None,
        text=True,
    ).stdout


def version():
    value = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    if not VERSION_RE.fullmatch(value):
        raise ValueError("Release version must have the form X.Y.Z")
    return value


def digest(path):
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def check():
    if run("git", "status", "--porcelain", capture=True).strip():
        raise ValueError("Release builds require a clean working tree")
    value = version()
    if run("git", "tag", "--list", "v" + value, capture=True).strip():
        raise ValueError("Release tag already exists")
    metainfo = ET.parse(ROOT / f"design/metainfo/{APP}.metainfo.xml")
    if metainfo.find("./releases/release").get("version") != value:
        raise ValueError("Metainfo version differs from pyproject.toml")
    if f"## [{value}] - " not in (ROOT / "CHANGELOG.md").read_text():
        raise ValueError("CHANGELOG version differs from pyproject.toml")
    return value


class Signing:
    def __init__(self):
        self.home = Path(
            os.environ.get(
                "SCAMBIO_GNUPGHOME",
                str(Path.home() / ".local/share/scambio-release/gnupg"),
            )
        )
        self.command = ["gpg", "--homedir", str(self.home), "--batch"]
        with tempfile.TemporaryDirectory(prefix="scambio-key-check-") as temporary:
            result = run(
                "gpg",
                "--homedir",
                temporary,
                "--batch",
                "--with-colons",
                "--show-keys",
                KEY,
                capture=True,
            )
        fingerprints = []
        expiry = 0
        preceding = []
        for line in result.splitlines():
            fields = line.split(":")
            if fields[0] in {"pub", "sub"}:
                preceding = fields
            elif fields[0] == "fpr":
                fingerprints.append(fields[9])
                if fields[9] == SIGNER:
                    if preceding[0] != "sub" or "s" not in preceding[11].lower():
                        raise ValueError("Expected a signing subkey")
                    expiry = int(preceding[6] or "0")
        if not fingerprints or fingerprints[0] != PRIMARY or SIGNER not in fingerprints:
            raise ValueError("Unexpected release public-key fingerprint")
        if expiry <= time.time() + 90 * 86400:
            raise ValueError("Release signing subkey expires within 90 days")

    def sign(self, path, *, clear=False, output=None, armor=True):
        destination = output or Path(str(path) + ".asc")
        run(
            *self.command,
            "--yes",
            "--local-user",
            SIGNER + "!",
            *(["--armor"] if armor else []),
            "--output",
            destination,
            "--clearsign" if clear else "--detach-sign",
            path,
        )
        self.verify(path, destination, clear=clear)

    @staticmethod
    def verify(path, signature, *, clear=False):
        with tempfile.TemporaryDirectory(prefix="scambio-verify-key-") as temporary:
            run(
                "gpgv",
                "--homedir",
                temporary,
                "--keyring",
                KEY,
                signature,
                *([] if clear else [path]),
            )


def dist():
    value = check()
    DIST.mkdir(parents=True, exist_ok=True)
    tarball = DIST / f"scambio-{value}.tar.gz"
    raw = subprocess.check_output(
        ["git", "archive", "--format=tar", f"--prefix=scambio-{value}/", "HEAD"],
        cwd=ROOT,
    )
    tarball.write_bytes(gzip.compress(raw, mtime=0))
    Signing().sign(tarball)
    checksums()


def checksums():
    artifacts = sorted(
        [*DIST.glob("scambio-*.tar.gz"), *DIST.glob("scambio_*_all.deb")]
    )
    (DIST / "SHA256SUMS").write_text(
        "".join(f"{digest(p)}  {p.name}\n" for p in artifacts)
    )
    Signing().sign(DIST / "SHA256SUMS")


def deb():
    value = check()
    dist()
    epoch = run("git", "show", "-s", "--format=%ct", "HEAD", capture=True).strip()
    with tempfile.TemporaryDirectory(prefix="scambio-deb-") as temporary:
        work = Path(temporary)
        with tarfile.open(DIST / f"scambio-{value}.tar.gz") as archive:
            archive.extractall(work, filter="data")
        source, target = work / f"scambio-{value}", work / "root"
        environment = {**os.environ, "SOURCE_DATE_EPOCH": epoch}
        run(
            "make",
            "install",
            "PREFIX=/usr",
            f"DESTDIR={target}",
            "SYSTEMD_USER_UNIT=1",
            "PYTHON_LIB=lib/python3/dist-packages",
            f"PYTHON={sys.executable}",
            cwd=source,
            env=environment,
        )
        for origin, relative in (
            (
                source / "packaging/debian/lintian-overrides",
                "usr/share/lintian/overrides/scambio",
            ),
            (
                source / "packaging/debian/scambio.sources",
                "etc/apt/sources.list.d/scambio.sources",
            ),
            (KEY, "usr/share/keyrings/scambio-archive-keyring.gpg"),
            (source / "packaging/debian/copyright", "usr/share/doc/scambio/copyright"),
        ):
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(origin, destination)
        metadata = target / "DEBIAN"
        metadata.mkdir()
        size = (
            sum(p.stat().st_size for p in target.rglob("*") if p.is_file()) // 1024 + 1
        )
        control = (source / "packaging/debian/control").read_text()
        (metadata / "control").write_text(
            control.replace("@VERSION@", value).replace("@SIZE@", str(size))
        )
        for name in ("postinst", "prerm", "postrm"):
            shutil.copyfile(source / "packaging/debian" / name, metadata / name)
            (metadata / name).chmod(0o755)
        changelog = (
            f"scambio ({value}) stable; urgency=medium\n\n"
            "  * Package the public Linux release.\n\n"
            " -- Fermich srl <hello@scambio.app>  "
            f"{formatdate(int(epoch))}\n"
        )
        (target / "usr/share/doc/scambio/changelog.gz").write_bytes(
            gzip.compress(changelog.encode(), mtime=0)
        )
        package = DIST / f"scambio_{value}_all.deb"
        for item in target.rglob("*"):
            if item.is_dir():
                item.chmod(0o755)
            elif item.parent == metadata or item == target / "usr/bin/scambio":
                item.chmod(0o644 if item.name == "control" else 0o755)
            else:
                item.chmod(0o644)
        run(
            "dpkg-deb",
            "--root-owner-group",
            "--build",
            target,
            package,
            env=environment,
        )
        run("lintian", "--fail-on", "error", package)
    Signing().sign(package)
    checksums()


def archived(root=None):
    root = ARCHIVE if root is None else root
    if not root.exists():
        return []
    found = []
    for directory in sorted(root.iterdir()):
        if (
            directory.is_symlink()
            or not directory.is_dir()
            or not VERSION_RE.fullmatch(directory.name)
        ):
            raise ValueError("Unexpected entry in immutable release archive")
        manifest = directory / "manifest.json"
        Signing.verify(manifest, directory / "manifest.json.asc")
        record = json.loads(manifest.read_text())
        if record["version"] != directory.name:
            raise ValueError("Archived version does not match its directory")
        entries = record["sha256"]
        actual = {
            str(path.relative_to(directory))
            for path in directory.rglob("*")
            if path.is_file() or path.is_symlink()
        } - {"manifest.json", "manifest.json.asc"}
        if actual != set(entries):
            raise ValueError("Archive has missing or unlisted artifacts")
        for relative, expected in entries.items():
            path = Path(relative)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("Invalid archived artifact path")
            item = directory / path
            if (
                any(parent.is_symlink() for parent in [item, *item.parents])
                or digest(item) != expected
            ):
                raise ValueError("Archived artifact hash or path verification failed")
        found.append(directory)
    return found


def repository_archives():
    """Read published history into a candidate, while sealing only in ARCHIVE."""
    current = archived()
    if not CANDIDATE:
        return current
    previous = archived(PUBLISHED_ARCHIVE)
    versions = {directory.name for directory in previous}
    if any(directory.name in versions for directory in current):
        raise ValueError("Candidate archive duplicates a published version")
    return previous + current


def latest():
    value = version()
    package = DIST / f"scambio_{value}_all.deb"
    (SITE / "download").mkdir(parents=True, exist_ok=True)
    (SITE / "download/latest.json").write_text(
        json.dumps({"version": value, "deb": package.name, "sha256": digest(package)})
        + "\n"
    )
    for path in (
        package,
        Path(str(package) + ".asc"),
        DIST / "SHA256SUMS",
        DIST / "SHA256SUMS.asc",
    ):
        shutil.copyfile(path, SITE / path.name)


def apt_repo():
    check()
    signer = Signing()
    repository = SITE / "apt"
    pool = repository / "pool/main/s/scambio"
    # Staging is derived output, never a source of packages to be signed.
    if (repository / "pool").exists():
        shutil.rmtree(repository / "pool")
    pool.mkdir(parents=True, exist_ok=True)
    copied = {}
    for source in [*repository_archives(), DIST]:
        value = version() if source == DIST else source.name
        for package in [source / f"scambio_{value}_all.deb"]:
            signer.verify(package, Path(str(package) + ".asc"))
            destination = pool / package.name
            checksum = digest(package)
            if package.name in copied and copied[package.name] != checksum:
                raise ValueError("Refusing to replace an existing package version")
            copied[package.name] = checksum
            shutil.copyfile(package, destination)
    binary = repository / "dists/stable/main/binary-all"
    binary.mkdir(parents=True, exist_ok=True)
    packages = run("apt-ftparchive", "packages", "pool", cwd=repository, capture=True)
    packages = (
        "\n".join(
            line
            for line in packages.splitlines()
            if not line.startswith(("MD5sum:", "SHA1:", "SHA512:"))
        )
        + "\n"
    )
    (binary / "Packages").write_text(packages)
    (binary / "Packages.gz").write_bytes(gzip.compress(packages.encode(), mtime=0))
    by_hash = binary / "by-hash/SHA256"
    by_hash.mkdir(parents=True, exist_ok=True)
    for path in (binary / "Packages", binary / "Packages.gz"):
        shutil.copyfile(path, by_hash / digest(path))
    stable = repository / "dists/stable"
    for name in ("Release", "InRelease", "Release.gpg"):
        (stable / name).unlink(missing_ok=True)
    release = run(
        "apt-ftparchive",
        "-o",
        "APT::FTPArchive::Release::MD5=false",
        "-o",
        "APT::FTPArchive::Release::SHA1=false",
        "-o",
        "APT::FTPArchive::Release::SHA512=false",
        "-o",
        "APT::FTPArchive::Release::Acquire-By-Hash=yes",
        "-o",
        "APT::FTPArchive::Release::Codename=stable",
        "-o",
        "APT::FTPArchive::Release::Suite=stable",
        "-o",
        "APT::FTPArchive::Release::Architectures=all",
        "-o",
        "APT::FTPArchive::Release::Components=main",
        "release",
        "dists/stable",
        cwd=repository,
        capture=True,
    )
    (stable / "Release").write_text(release)
    signer.sign(stable / "Release", clear=True, output=stable / "InRelease")
    signer.sign(stable / "Release", output=stable / "Release.gpg", armor=False)
    latest()


def copy_repository(source, destination):
    """Unseal only the derived copy, including OSTree's writable lock/config files."""

    def writable():
        if destination.exists():
            for item in [destination, *destination.rglob("*")]:
                item.chmod(0o755 if item.is_dir() else 0o644)

    writable()  # Also allow retrying an interrupted copy/build.
    shutil.copytree(source, destination, dirs_exist_ok=True)
    writable()


def flatpak():
    value = check()
    dist()
    signer = Signing()
    source = DIST / f"scambio-{value}.tar.gz"
    template = (ROOT / f"packaging/flatpak/{APP}.yml").read_text()
    manifest = DIST / f"{APP}.yml"
    manifest.write_text(
        template.replace("@ARCHIVE@", str(source)).replace("@SHA256@", digest(source))
    )
    repository = DIST / "flatpak-repo"
    for previous in repository_archives():
        copy_repository(previous / "ostree", repository)
    epoch = run("git", "show", "-s", "--format=%ct", "HEAD", capture=True).strip()
    run("flatpak-builder", "--show-manifest", manifest)
    run(
        "flatpak-builder",
        "--user",
        "--force-clean",
        "--disable-download",
        f"--override-source-date-epoch={epoch}",
        f"--repo={DIST / 'flatpak-repo'}",
        f"--gpg-sign={SIGNER}!",
        f"--gpg-homedir={signer.home}",
        "--default-branch=stable",
        DIST / "flatpak-build",
        manifest,
    )
    run(
        "flatpak",
        "build-update-repo",
        "--generate-static-deltas",
        "--prune",
        f"--gpg-sign={SIGNER}!",
        f"--gpg-homedir={signer.home}",
        DIST / "flatpak-repo",
    )


def flatpak_site():
    check()
    repository_archives()
    destination = SITE / "flatpak/repo"
    shutil.copytree(DIST / "flatpak-repo", destination, dirs_exist_ok=True)
    key = base64.b64encode(KEY.read_bytes()).decode()
    url = "https://scambio.app/flatpak/repo"
    (SITE / "flatpak/scambio.flatpakrepo").write_text(
        f"[Flatpak Repo]\nTitle=Scambio\nUrl={url}\nHomepage=https://scambio.app\nGPGKey={key}\n"
    )
    (SITE / "flatpak/scambio.flatpakref").write_text(
        f"[Flatpak Ref]\nName={APP}\nBranch=stable\nTitle=Scambio\nUrl={url}\n"
        "RuntimeRepo=https://dl.flathub.org/repo/flathub.flatpakrepo\n"
        f"GPGKey={key}\nIsRuntime=false\n"
    )
    latest()


def seal():
    """Preserve a verified release once, including its reachable OSTree objects."""
    value = check()
    existing = {path.name: path for path in archived()}
    names = [f"scambio_{value}_all.deb", f"scambio-{value}.tar.gz", "SHA256SUMS"]
    if value in existing:
        for name in names:
            if digest(existing[value] / name) != digest(DIST / name):
                raise ValueError(
                    "Immutable release version already contains different bytes"
                )
        return
    repository = DIST / "flatpak-repo"
    architecture = run("flatpak", "--default-arch", capture=True).strip()
    commit = run(
        "ostree",
        f"--repo={repository}",
        "rev-parse",
        f"app/{APP}/{architecture}/stable",
        capture=True,
    ).strip()
    run("ostree", f"--repo={repository}", "refs", f"--create=archive/v{value}", commit)
    ARCHIVE.mkdir(parents=True, exist_ok=True, mode=0o700)
    destination = ARCHIVE / value
    # A completed version is never replaced. An interrupted archive fails validation
    # on the next run and requires explicit operator inspection.
    destination.mkdir(mode=0o700)
    for name in names:
        for filename in (name, name + ".asc"):
            shutil.copyfile(DIST / filename, destination / filename)
    shutil.copytree(repository, destination / "ostree")
    (destination / "ostree.commit").write_text(commit + "\n")
    manifest = {
        "version": value,
        "candidate": CANDIDATE,
        "source_commit": run("git", "rev-parse", "HEAD", capture=True).strip(),
        "ostree_commit": commit,
        "sha256": {
            str(path.relative_to(destination)): digest(path)
            for path in sorted(destination.rglob("*"))
            if path.is_file()
        },
    }
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    Signing().sign(destination / "manifest.json")
    for path in destination.rglob("*"):
        if path.is_file():
            path.chmod(0o444)
        elif path.is_dir():
            path.chmod(0o555)
    destination.chmod(0o555)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command",
        choices=["check", "dist", "deb", "apt-repo", "flatpak", "flatpak-site"],
    )
    args = parser.parse_args()
    {
        "check": check,
        "dist": dist,
        "deb": deb,
        "apt-repo": apt_repo,
        "flatpak": flatpak,
        "flatpak-site": flatpak_site,
    }[args.command]()


if __name__ == "__main__":
    main()
