# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Fermich srl
import os
import stat
import tomllib

import pytest

from scambio.config import ConfigInvalid, load, prepare_update, template


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
@pytest.mark.parametrize("final", [True, False])
def test_lossless_scalars(tmp_path, newline, final):
    original = '''# custom header
[policy] # keep table
  release_idle_seconds  = 120  # keep inline
# release_idle_seconds = 240
grab_delay_ms=25
# resume_delay_ms = 2000
[ui]
language = 'en' # language
tray=true
[other]
text = """untouched
[policy]
release_idle_seconds = 666
"""
array = [
    "hello", # not a key
]
'''.replace("\n", newline)
    if not final:
        original = original.removesuffix(newline)
    path = tmp_path / "config.toml"
    path.write_bytes(original.encode())
    os.chmod(path, 0o640)
    edit = prepare_update(
        path, {"policy.release_idle_seconds": 180, "ui.language": "de"}
    )
    assert path.read_bytes() == original.encode()
    edit.write()
    expected = original.replace("= 120  #", "= 180  #").replace("'en' #", '"de" #')
    assert path.read_bytes() == expected.encode()
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert load(path).policy.release_idle_seconds == 180
    assert list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize(
    "source,expected",
    [
        (
            '[ui]\n# tray=true\nlanguage="en"\n# tail\n',
            '[ui]\n# tray=true\nlanguage="en"\ntray = false\n# tail\n',
        ),
        ("[ui]\n# tail\n", "[ui]\ntray = false\n# tail\n"),
        ("[ui]", "[ui]\ntray = false\n"),
        (
            "[policy]\nrelease_idle_seconds=180",
            "[policy]\nrelease_idle_seconds=180\n\n[ui]\ntray = false\n",
        ),
        ('[ui]\nlanguage="en"', '[ui]\nlanguage="en"\ntray = false\n'),
    ],
)
def test_missing_key_or_table(tmp_path, source, expected):
    path = tmp_path / "config.toml"
    path.write_text(source)
    prepare_update(path, {"ui.tray": False}).write()
    assert path.read_text() == expected


@pytest.mark.parametrize(
    "source,changes",
    [
        ("ui.tray=true\n", {"ui.tray": False}),
        ("ui = {tray=true}\n", {"ui.tray": False}),
        ('ui = {language="en"}\n', {"ui.tray": False}),
        ('["ui"]\ntray=true\n', {"ui.tray": False}),
        ('[ui]\n"tray" = true\n', {"ui.tray": False}),
        ("[ui]\n'language' = 'en'\n", {"ui.language": "de"}),
        ('[ui]\nlanguage = """en"""\n', {"ui.language": "de"}),
        ('[ui]\nlanguage = """\\\nen"""\n', {"ui.language": "de"}),
        ("[ui\ntray=true", {"ui.tray": False}),
    ],
)
def test_unsupported_forms_leave_bytes_intact(tmp_path, source, changes):
    path = tmp_path / "config.toml"
    path.write_text(source)
    before = path.read_bytes()
    with pytest.raises(ConfigInvalid):
        prepare_update(path, changes)
    assert path.read_bytes() == before


@pytest.mark.parametrize(
    "changes",
    [
        {"shortcut.preferred": "<Alt>g"},
        {"other": True},
        {"ui.tray": 1},
        {"policy.release_idle_seconds": True},
        {"policy.release_idle_seconds": 3601},
        {"ui.language": "fr"},
        {"device.address": "invalid"},
    ],
)
def test_rejected_values(tmp_path, changes):
    path = tmp_path / "config.toml"
    path.write_text(template("en"))
    before = path.read_bytes()
    with pytest.raises(ConfigInvalid):
        prepare_update(path, changes)
    assert path.read_bytes() == before


@pytest.mark.parametrize("language", ["it", "en", "de"])
def test_translated_model_and_missing_file(tmp_path, language):
    path = tmp_path / "nested/config.toml"
    edit = prepare_update(path, {"ui.notifications": False}, language)
    assert not path.exists()
    edit.write()
    assert path.read_text() == template(language).replace(
        "notifications = true", "notifications = false"
    )
    assert not load(path).notifications
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_merge_reads_file_and_preserves_unknowns(tmp_path):
    path = tmp_path / "config.toml"
    source = '[device]\naddress="aa:bb:cc:dd:ee:ff"\n[future]\nv={a=1}\n'
    path.write_text(source)
    edit = prepare_update(path, {"ui.tray": False, "ui.language": "de"})
    assert edit.config.device.address == "AA:BB:CC:DD:EE:FF"
    edit.write()
    assert tomllib.loads(path.read_text())["future"] == {"v": {"a": 1}}
    assert path.read_text().startswith(source)


def test_write_preserves_relative_symlink_and_makes_target_private(tmp_path):
    target = tmp_path / "actual" / "settings.toml"
    target.parent.mkdir()
    target.write_text("[ui]\ntray = true # preserved\n")
    target.chmod(0o640)
    link = tmp_path / "config.toml"
    link.symlink_to("actual/settings.toml")
    prepare_update(link, {"ui.tray": False}).write()
    assert link.is_symlink()
    assert os.readlink(link) == "actual/settings.toml"
    assert target.read_text() == "[ui]\ntray = false # preserved\n"
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert list(target.parent.iterdir()) == [target]
