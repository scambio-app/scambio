import ast
import gettext
import string
import tomllib

import pytest

from scambio.config import CONFIG_COMMENTS, ConfigInvalid, load, parse, template
from scambio.i18n import LANGUAGES, Translator, cli_translator, resolve
from scambio.paths import design_dir, locale_dir


def po_entries(path):
    entries = {}
    key, value, target = "", "", None
    for line in path.read_text().splitlines() + ['msgid ""']:
        if line.startswith("msgid "):
            if key:
                entries[key] = value
            key, value, target = ast.literal_eval(line[6:]), "", "key"
        elif line.startswith("msgstr "):
            value, target = ast.literal_eval(line[7:]), "value"
        elif line.startswith('"'):
            if target == "key":
                key += ast.literal_eval(line)
            elif target == "value":
                value += ast.literal_eval(line)
    return entries


def placeholders(text):
    return {name for _, name, _, _ in string.Formatter().parse(text) if name}


def test_catalog_contract():
    catalogs = {
        code: po_entries(design_dir() / f"i18n/{code}.po") for code in LANGUAGES
    }
    pot = po_entries(design_dir() / "i18n/scambio.pot")
    for code, entries in catalogs.items():
        assert entries.keys() == pot.keys() == catalogs["en"].keys()
        with (locale_dir() / code / "LC_MESSAGES/scambio.mo").open("rb") as f:
            compiled = gettext.GNUTranslations(f)
        for key, text in entries.items():
            assert text and compiled.gettext(key) == text
            assert placeholders(text) == placeholders(catalogs["en"][key])


@pytest.mark.parametrize(
    "env,expected",
    [
        ({"LANGUAGE": "de:it"}, "de"),
        ({"LC_ALL": "C", "LANG": "it_IT.UTF-8"}, "it"),
        ({"LANGUAGE": "fr:it", "LC_ALL": "de_DE"}, "it"),
        ({"LC_ALL": "POSIX"}, "en"),
        ({"LC_MESSAGES": "de_DE.UTF-8"}, "de"),
        ({"LANGUAGE": "C:POSIX:fr", "LANG": "xx"}, "en"),
    ],
)
def test_language(env, expected):
    assert resolve(environ=env) == expected
    assert resolve("en", env) == "en"


def test_fallback_capitalization_and_values():
    tr = Translator("it", strict=True).tr
    assert tr("tray-header-released", device="").startswith("Il dispositivo")
    assert tr("notify-priority-on-title").startswith("Priorità telefono")
    assert Translator("en").tr("notify-priority-on-title").startswith("Phone")
    assert "il dispositivo" in tr("notify-priority-on-body", device="")
    assert tr("tray-header-released", device="A_&<B>").startswith("A_&<B>")


@pytest.mark.parametrize("code", LANGUAGES)
def test_config_comments_and_readonly(tmp_path, monkeypatch, code):
    monkeypatch.setenv("LANGUAGE", code)
    text = template()
    values = tomllib.loads(text)
    assert parse(values) == parse({})
    keys = {
        f"{section}.{key}"
        for section, table in values.items()
        if section != "backend"
        for key in table
    }
    assert keys | {"policy.resume_delay_ms"} == CONFIG_COMMENTS.keys()
    tr = Translator(code).tr
    assert all(tr(key) in text for key in CONFIG_COMMENTS.values())
    path = tmp_path / "config.toml"
    load(path)
    assert path.read_text() == text
    monkeypatch.setenv("LANGUAGE", "en")
    load(path)
    assert path.read_text() == text


def test_cli_config_readonly_and_fallback(tmp_path, monkeypatch):
    monkeypatch.setenv("LANGUAGE", "it")
    path = tmp_path / "config.toml"
    assert cli_translator(path).language == "it"
    assert not path.exists()
    for text in ['[ui]\nlanguage = "de"', "broken [", "ui = 3"]:
        path.write_text(text)
        assert cli_translator(path).language == ("de" if '"de"' in text else "it")
        assert path.read_text() == text
    monkeypatch.setenv("SCAMBIO_LOCALE_DIR", str(tmp_path))
    assert Translator("de").tr("cli-description") == "cli-description"
    with pytest.raises(ValueError, match="make i18n"):
        Translator("de", strict=True)
    english = tmp_path / "en/LC_MESSAGES"
    english.mkdir(parents=True)
    from scambio.paths import ROOT

    (english / "scambio.mo").write_bytes(
        (ROOT / "build/locale/en/LC_MESSAGES/scambio.mo").read_bytes()
    )
    assert Translator("de").tr("cli-description").startswith("Switch Bluetooth")


@pytest.mark.parametrize("key", ["tray", "notifications"])
@pytest.mark.parametrize("value", [0, 1, "false", None, []])
def test_ui_flags_strict(key, value):
    with pytest.raises(ConfigInvalid):
        parse({"ui": {key: value}})


def test_ui_flags():
    assert parse({}).tray and parse({}).notifications
    assert not parse({"ui": {"tray": False}}).tray
    assert not parse({"ui": {"notifications": False}}).notifications


def test_truncated_catalog_falls_back(tmp_path, monkeypatch):
    monkeypatch.setenv("SCAMBIO_LOCALE_DIR", str(tmp_path))
    folder = tmp_path / "de/LC_MESSAGES"
    folder.mkdir(parents=True)
    (folder / "scambio.mo").write_bytes(b"\x00")
    assert Translator("de").tr("cli-description") == "cli-description"
    with pytest.raises(ValueError, match="make i18n"):
        Translator("de", strict=True)
