# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Fermich srl
"""Bounded regular-file reads and durable writes relative to a checked directory."""

import os
import secrets
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

CONFIG_LIMIT = 256 * 1024
STATE_LIMIT = 64 * 1024


@contextmanager
def parent_fd(path: Path, *, create: bool = False) -> Iterator[int]:
    if create:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        yield fd
    finally:
        os.close(fd)


def read_text(path: Path, limit: int, *, symlink: bool = False) -> str:
    with parent_fd(path) as directory:
        flags = os.O_RDONLY | os.O_NONBLOCK
        if not symlink:
            flags |= os.O_NOFOLLOW
        fd = os.open(path.name, flags, dir_fd=directory)
        with os.fdopen(fd, "rb") as source:
            status = os.fstat(source.fileno())
            if not stat.S_ISREG(status.st_mode) or status.st_size > limit:
                raise ValueError(
                    "Application file is not regular or exceeds size limit"
                )
            data = source.read(limit + 1)
            if len(data) > limit:
                raise ValueError("Application file exceeds size limit")
    return data.decode("utf-8")


def write_text(path: Path, text: str, *, exclusive: bool = False) -> None:
    """Refuse symlink destinations, then replace within the pinned parent directory."""
    with parent_fd(path, create=True) as directory:
        try:
            status = os.stat(path.name, dir_fd=directory, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            if not stat.S_ISREG(status.st_mode):
                raise OSError("Application file must be a regular file, not a symlink")
            if exclusive:
                raise FileExistsError(path)
        temporary = ".scambio-" + secrets.token_hex(16)
        fd = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=directory,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as output:
                output.write(text)
                output.flush()
                os.fsync(output.fileno())
            if exclusive:
                # link fails atomically if another process created the destination.
                os.link(
                    temporary,
                    path.name,
                    src_dir_fd=directory,
                    dst_dir_fd=directory,
                    follow_symlinks=False,
                )
            else:
                os.replace(
                    temporary, path.name, src_dir_fd=directory, dst_dir_fd=directory
                )
            os.fsync(directory)
        finally:
            try:
                os.unlink(temporary, dir_fd=directory)
            except FileNotFoundError:
                pass
