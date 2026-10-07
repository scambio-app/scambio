# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Fermich srl

import os
import stat

import pytest

from scambio.files import read_text, write_text


def test_private_creation_and_atomic_replacement(tmp_path, monkeypatch):
    path = tmp_path / "private/state.json"
    calls = []
    original = os.fsync

    def synced(fd):
        calls.append(stat.S_ISDIR(os.fstat(fd).st_mode))
        original(fd)

    monkeypatch.setattr(os, "fsync", synced)
    write_text(path, "old", exclusive=True)
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert calls == [False, True]
    with path.open() as old:
        write_text(path, "new")
        assert old.read() == "old"
    assert read_text(path, 3) == "new"
    with pytest.raises(ValueError, match="size limit"):
        read_text(path, 2)
    with pytest.raises(FileExistsError):
        write_text(path, "overwrite", exclusive=True)
    assert path.read_text() == "new"
    assert list(path.parent.iterdir()) == [path]


def test_file_symlink_read_policy_and_write_refusal(tmp_path):
    target = tmp_path / "target"
    target.write_text("original")
    link = tmp_path / "link"
    link.symlink_to(target)
    with pytest.raises(OSError):
        read_text(link, 100)
    assert read_text(link, 100, symlink=True) == "original"
    with pytest.raises(OSError):
        write_text(link, "changed")
    assert target.read_text() == "original"


def test_parent_symlink_is_rejected(tmp_path):
    actual = tmp_path / "actual"
    actual.mkdir()
    (actual / "state.json").write_text("original")
    link = tmp_path / "link"
    link.symlink_to(actual, target_is_directory=True)
    with pytest.raises(OSError):
        read_text(link / "state.json", 100)
    with pytest.raises(OSError):
        write_text(link / "state.json", "changed")
    assert (actual / "state.json").read_text() == "original"


def test_fifo_is_rejected_without_waiting(tmp_path):
    path = tmp_path / "fifo"
    os.mkfifo(path)
    with pytest.raises(ValueError, match="not regular"):
        read_text(path, 100)
    with pytest.raises(OSError):
        write_text(path, "data")


def test_failed_replace_keeps_old_data_and_removes_temp(tmp_path, monkeypatch):
    path = tmp_path / "state.json"
    path.write_text("old")

    def fail(*args, **kwargs):
        raise OSError("simulated full disk")

    monkeypatch.setattr(os, "replace", fail)
    with pytest.raises(OSError, match="full disk"):
        write_text(path, "new")
    assert path.read_text() == "old"
    assert list(tmp_path.iterdir()) == [path]


def test_config_cap_applies_to_load_edit_and_cli(tmp_path):
    from scambio.config import ConfigInvalid, load, prepare_update
    from scambio.files import CONFIG_LIMIT
    from scambio.i18n import cli_translator

    path = tmp_path / "config.toml"
    original = "# " + "x" * CONFIG_LIMIT
    path.write_text(original)
    with pytest.raises(ConfigInvalid, match="size limit"):
        load(path)
    with pytest.raises(ConfigInvalid, match="size limit"):
        prepare_update(path, {"ui.tray": False})
    cli_translator(path)
    assert path.read_text() == original


def test_state_cap_and_symlink_do_not_overwrite_target(tmp_path):
    from scambio.files import STATE_LIMIT
    from scambio.state import State, Store

    path = tmp_path / "state.json"
    path.write_text(" " * (STATE_LIMIT + 1))
    store = Store(path)
    assert store.load() == State()
    store.value.restore_default_sink = "x" * STATE_LIMIT
    with pytest.raises(OSError, match="size limit"):
        store.save()
    target = tmp_path / "target"
    target.write_text("original")
    path.unlink()
    path.symlink_to(target)
    assert store.load() == State()
    with pytest.raises(OSError):
        store.save()
    assert target.read_text() == "original"
