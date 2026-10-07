# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-FileCopyrightText: 2026 Fermich srl
import json
from dataclasses import replace

import pytest

from scambio.config import Config, ConfigInvalid, load, parse
from scambio.state import State, Store


def test_template_and_readonly(tmp_path):
    path = tmp_path / "config.toml"
    assert load(path) == Config()
    original = path.read_bytes()
    load(path)
    assert path.read_bytes() == original


def test_dummy_audio_defaults_and_explicit_override(tmp_path):
    expected = ("sd_dummy", "speech-dispatcher-dummy")
    assert Config().audio.ignore_apps == expected
    assert parse({}).audio.ignore_apps == expected
    assert load(tmp_path / "config.toml").audio.ignore_apps == expected
    assert parse({"audio": {"ignore_apps": []}}).audio.ignore_apps == ()
    assert parse({"audio": {"ignore_apps": ["Custom"]}}).audio.ignore_apps == (
        "custom",
    )


@pytest.mark.parametrize(
    "data",
    [
        {"device": {"address": "bad"}},
        {"device": {"profile": "other"}},
        {"policy": {"grab_delay_ms": True}},
        {"policy": {"grab_delay_ms": -1}},
        {"policy": {"release_idle_seconds": 9}},
        {"policy": {"connect_timeout_seconds": 61}},
        {"policy": {"sink_timeout_seconds": 0}},
        {"policy": {"sleep_release_timeout_seconds": 11}},
        {"audio": {"ignore_roles": "event"}},
        {"audio": {"ignore_apps": [1]}},
        {"ui": {"language": "fr"}},
        {"shortcut": {"preferred": 3}},
        {"policy": []},
        {"backend": {"retry_initial_seconds": 31}},
    ],
)
def test_invalid(data):
    with pytest.raises(ConfigInvalid):
        parse(data)


def test_unknown_and_normalization(caplog):
    cfg = parse(
        {
            "future": {},
            "device": {"address": "aa:bb:cc:dd:ee:ff", "extra": 1},
            "audio": {"ignore_apps": ["PLAYER"]},
        }
    )
    assert cfg.device.address == "AA:BB:CC:DD:EE:FF"
    assert cfg.audio.ignore_apps == ("player",)
    assert "Unknown configuration" in caplog.text


def test_parse_failure_keeps_file(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text("invalid [[")
    with pytest.raises(ConfigInvalid):
        load(p)
    assert p.read_text() == "invalid [["


def test_state_roundtrip_and_corruption(tmp_path):
    store = Store(tmp_path / "state.json")
    assert store.load() == State()
    store.value = replace(
        store.value, iphone_priority=True, restore_default_sink="speakers"
    )
    store.save()
    assert Store(store.path).load() == store.value
    assert json.loads(store.path.read_text())["version"] == 1
    assert list(tmp_path.iterdir()) == [store.path]
    for broken in ["{", "[]", '{"version":2}', '{"version":1,"iphone_priority":1}']:
        store.path.write_text(broken)
        assert store.load() == State()


def test_policy_defaults_and_existing_config(tmp_path):
    import tomllib

    from scambio.config import Policy

    path = tmp_path / "config.toml"
    config = load(path)
    generated = tomllib.loads(path.read_text())["policy"]
    assert config.policy == parse({}).policy == Policy()
    assert config.policy.grab_delay_ms == generated["grab_delay_ms"] == 500
    assert (
        config.policy.unblock_silence_seconds
        == generated["unblock_silence_seconds"]
        == 10
    )
    # An explicit previous value still belongs to the user; no file migration.
    path.write_text("[policy]\ngrab_delay_ms = 1000\n")
    before = path.read_bytes()
    assert load(path).policy == replace(Policy(), grab_delay_ms=1000)
    assert path.read_bytes() == before


@pytest.mark.parametrize("seconds", [1, 10, 120])
def test_unblock_silence_valid(seconds):
    from scambio.config import Policy

    assert parse({"policy": {"unblock_silence_seconds": seconds}}).policy == replace(
        Policy(), unblock_silence_seconds=seconds
    )


@pytest.mark.parametrize("seconds", [0, -1, 121, True, False, 1.5, "10", None])
def test_unblock_silence_invalid(seconds):
    with pytest.raises(ConfigInvalid, match="unblock_silence_seconds"):
        parse({"policy": {"unblock_silence_seconds": seconds}})


@pytest.mark.parametrize("profile,delay", [("generic", 0), ("meta_glasses", 2000)])
def test_player_config_profile_reload(tmp_path, profile, delay):
    p = tmp_path / "config.toml"
    p.write_text(f'[device]\nprofile = "{profile}"\n')
    assert load(p).policy.resume_delay_ms == delay
    p.write_text(p.read_text() + "[policy]\nresume_delay_ms = 37\n")
    assert load(p).policy.resume_delay_ms == 37
    assert parse({"audio": {"ignore_players": ["VLC"]}}).audio.ignore_players == (
        "vlc",
    )


@pytest.mark.parametrize(
    "section,key,values",
    [
        ("policy", "resume_delay_ms", [-1, 10001, True, "0", 1.5]),
        ("backend", "player_timeout_ms", [99, 5001, False, "1000", 1.5]),
        ("audio", "ignore_players", ["vlc", [3]]),
    ],
)
def test_player_config_invalid(section, key, values):
    for value in values:
        with pytest.raises(ConfigInvalid):
            parse({section: {key: value}})


@pytest.mark.parametrize(
    "key,section,values",
    [
        ("resume_delay_ms", "policy", [0, 10000]),
        ("player_timeout_ms", "backend", [100, 5000]),
    ],
)
def test_player_config_bounds(key, section, values):
    for value in values:
        assert getattr(getattr(parse({section: {key: value}}), section), key) == value


def test_resume_state(tmp_path, caplog):
    from scambio.state import PlayerRef, ResumePlayers

    store = Store(tmp_path / "state.json")
    base = dict(version=1, iphone_priority=True, restore_default_sink="speakers")
    for malformed in [
        [],
        3,
        {},
        {"bus_id": "a", "players": [{}]},
        {"bus_id": "a", "players": [{"name": "other", "owner": ":1.2"}]},
    ]:
        store.path.write_text(json.dumps(dict(base, resume_players=malformed)))
        assert store.load() == State(1, True, "speakers")
        assert "Ignoring malformed resume_players" in caplog.text
    store.path.write_text(json.dumps(base))
    assert store.load() == State(1, True, "speakers")
    store.value.resume_players = ResumePlayers(
        "bus", (PlayerRef("org.mpris.MediaPlayer2.fake", ":1.2"),)
    )
    store.save()
    assert Store(store.path).load() == store.value
