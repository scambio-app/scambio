import builtins
import sys
from types import SimpleNamespace

import pytest

from scambio import cli
from scambio.i18n import Translator


@pytest.mark.parametrize("service", [False, True])
def test_settings_passes_service_flag_without_loading_gtk(monkeypatch, service):
    calls = []
    monkeypatch.setitem(
        sys.modules,
        "scambio.ui.window",
        SimpleNamespace(run=lambda flag: calls.append(flag) or 7),
    )
    assert cli.main(["settings", *(["--gapplication-service"] if service else [])]) == 7
    assert calls == [service]


def test_settings_service_flag_hidden(capsys):
    with pytest.raises(SystemExit) as result:
        cli.main(["settings", "--help"])
    assert result.value.code == 0
    assert "gapplication-service" not in capsys.readouterr().out


@pytest.mark.parametrize("error", [ImportError, ValueError])
def test_settings_missing_gtk_is_localized(monkeypatch, capsys, error):
    original = builtins.__import__

    def importing(name, *args, **kwargs):
        if name == "scambio.ui.window":
            raise error("unavailable")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", importing)
    monkeypatch.setattr(cli, "cli_translator", lambda path: Translator("de"))
    assert cli.main(["settings"]) == 1
    assert capsys.readouterr().err.strip() == Translator("de").tr(
        "cli-error-gtk-missing"
    )
