# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Fermich srl

from pathlib import Path

import pytest

from scambio import paths


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    for key in ("SCAMBIO_DATA_DIR", "SCAMBIO_DESIGN_DIR", "SCAMBIO_LOCALE_DIR"):
        monkeypatch.delenv(key, raising=False)


def test_checkout_assets(tmp_path, monkeypatch):
    (tmp_path / "pyproject.toml").touch()
    (tmp_path / "src").mkdir()
    monkeypatch.setattr(paths, "ROOT", tmp_path)
    assert paths.design_dir() == tmp_path / "design"
    assert paths.locale_dir() == tmp_path / "build/locale"
    assert paths.ui_file() == tmp_path / "build/ui/settings-window.ui"


@pytest.mark.parametrize("prefix", ["/app", "/custom", "/usr"])
def test_installed_prefix_precedence(tmp_path, monkeypatch, prefix):
    monkeypatch.setattr(paths, "ROOT", tmp_path)
    monkeypatch.setattr(paths.sys, "prefix", "/custom")
    candidates = [Path(p) / "share/scambio" for p in ("/app", "/custom", "/usr")]
    expected = Path(prefix) / "share/scambio"
    available = candidates[candidates.index(expected) :]
    monkeypatch.setattr(Path, "is_dir", lambda path: path in available)
    assert paths.data_dir() == expected
    assert paths.design_dir() == expected / "design"
    assert paths.locale_dir() == expected / "locale"
    assert paths.ui_file() == expected / "ui/settings-window.ui"


def test_explicit_data_override_uses_installed_layout(tmp_path, monkeypatch):
    monkeypatch.setenv("SCAMBIO_DATA_DIR", str(tmp_path))
    assert paths.design_dir() == tmp_path / "design"
    assert paths.locale_dir() == tmp_path / "locale"
    assert paths.ui_file() == tmp_path / "ui/settings-window.ui"
    monkeypatch.setenv("SCAMBIO_DESIGN_DIR", str(tmp_path / "custom-design"))
    monkeypatch.setenv("SCAMBIO_LOCALE_DIR", str(tmp_path / "custom-locale"))
    assert paths.design_dir() == tmp_path / "custom-design"
    assert paths.locale_dir() == tmp_path / "custom-locale"


def test_missing_installation_fails_clearly(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "ROOT", tmp_path)
    monkeypatch.setattr(Path, "is_dir", lambda path: False)
    with pytest.raises(FileNotFoundError, match="data directory"):
        paths.data_dir()


def test_xdg_paths_use_glib_and_keep_explicit_overrides(tmp_path, monkeypatch):
    from gi.repository import GLib

    from scambio.config import config_path
    from scambio.state import Store

    monkeypatch.setattr(GLib, "get_user_config_dir", lambda: str(tmp_path / "config"))
    monkeypatch.setattr(GLib, "get_user_data_dir", lambda: str(tmp_path / "data"))
    assert config_path() == tmp_path / "config/scambio/config.toml"
    assert Store().path == tmp_path / "data/scambio/state.json"
    assert Store(tmp_path / "explicit.json").path == tmp_path / "explicit.json"


def test_flatpak_icons_use_host_deployment(tmp_path):
    info = tmp_path / "flatpak-info"
    info.write_text("[Instance]\napp-path=/deployment/files\n")
    assert paths.host_path(Path("/app/share/scambio/design/icons"), info) == Path(
        "/deployment/files/share/scambio/design/icons"
    )
    assert paths.host_path(Path("/usr/share/scambio/design/icons"), info) == Path(
        "/usr/share/scambio/design/icons"
    )


@pytest.mark.parametrize(
    "content", [None, "broken", "[Instance]", "[Instance]\napp-path=relative"]
)
def test_missing_or_invalid_flatpak_info_preserves_path(tmp_path, content):
    info = tmp_path / "flatpak-info"
    if content is not None:
        info.write_text(content)
    path = Path("/app/share/scambio/design/icons")
    assert paths.host_path(path, info) == path
