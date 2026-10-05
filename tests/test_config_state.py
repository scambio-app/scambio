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
