import ast
import json
import os
import signal
import subprocess
import sys
from pathlib import Path

import dbus
import dbusmock
import pytest
from gi.repository import Gio, GLib
from helpers import ADDRESS, SINK, drain, spin_until

from scambio.api import BUS_NAME, INTERFACE, PATH
from scambio.config import TEMPLATE, Config, Device, load
from scambio.core.audio import Audio
from scambio.core.bluez import BlueZ
from scambio.core.policy import Event
from scambio.core.service import Service
from scambio.core.session import Session
from scambio.state import Store


def client(*args):
    return subprocess.run(
        [sys.executable, "-m", "scambio.cli", *args],
        capture_output=True,
        text=True,
        timeout=5,
    )


def properties():
    bus = dbusmock.BusType.SESSION.get_connection()
    return dict(
        bus.get_object(BUS_NAME, PATH).GetAll(
            INTERFACE, dbus_interface="org.freedesktop.DBus.Properties"
        )
    )


@pytest.fixture
def daemon(fake_pactl, bluez_server, tmp_path):
    (tmp_path / "config.toml").write_text(
        TEMPLATE.replace('address = ""', f'address = "{ADDRESS}"')
        .replace("grab_delay_ms = 500", "grab_delay_ms = 0")
        .replace("release_idle_seconds = 120", "release_idle_seconds = 10")
    )
    log = (tmp_path / "daemon.log").open("w")
    process = subprocess.Popen(
        [
            sys.executable,
            str(Path(__file__).parent / "fixtures/run_daemon.py"),
            str(tmp_path),
        ],
        stdout=log,
        stderr=log,
    )
    try:
        bus = dbusmock.BusType.SESSION.get_connection()
        spin_until(lambda: process.poll() is not None or bus.name_has_owner(BUS_NAME))
        assert process.poll() is None, (tmp_path / "daemon.log").read_text()
        spin_until(lambda: str(properties()["State"]) == "released")
        yield process
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)
        log.close()
        assert process.returncode == 0, (tmp_path / "daemon.log").read_text()


def test_cli_missing_and_usage():
    assert client("status").returncode == 3
    assert "systemctl --user start scambio" in client("switch").stderr
    assert client("priority", "invalid").returncode == 2


def test_cli_switch_priority_persistence(daemon, fake_pactl, tmp_path):
    r = client("status", "--json")
    assert r.returncode == 0
    status = json.loads(r.stdout)
    assert status["State"] == "released" and not status["AudioActive"]
    assert set(status) == {
        "State",
        "IphonePriority",
        "AudioActive",
        "Locked",
        "DeviceAddress",
        "DeviceName",
        "DeviceConnected",
        "IdleReleaseAt",
        "LastError",
        "Version",
    }
    fake_pactl.add_sink()
    fake_pactl.event()
    assert client("switch").stdout.strip() == "connecting"
    spin_until(lambda: str(properties()["State"]) == "on_pc")
    assert int(properties()["IdleReleaseAt"]) > GLib.get_real_time()
    assert client("priority", "on").returncode == 0
    spin_until(lambda: str(properties()["State"]) == "released")
    assert client("priority").stdout.strip() == "on"
    assert json.loads((tmp_path / "state.json").read_text())["iphone_priority"]
    assert client("priority", "toggle").returncode == 0
    assert client("priority").stdout.strip() == "off"
    assert client("status").returncode == 0


def test_reload_and_duplicate_and_shutdown(daemon, fake_pactl, tmp_path):
    bus = dbusmock.BusType.SESSION.get_connection()
    obj = bus.get_object(BUS_NAME, PATH)
    original = (tmp_path / "config.toml").read_text()
    (tmp_path / "config.toml").write_text("[policy]\ngrab_delay_ms = -1\n")
    with pytest.raises(dbus.DBusException, match="ConfigInvalid"):
        obj.Reload(dbus_interface=INTERFACE)
    assert str(properties()["LastError"]) == "config_invalid"
    (tmp_path / "config.toml").write_text(
        original.replace(ADDRESS, "11:22:33:44:55:66")
    )
    with pytest.raises(dbus.DBusException, match="RestartRequired"):
        obj.Reload(dbus_interface=INTERFACE)
    assert str(properties()["DeviceAddress"]) == ADDRESS
    (tmp_path / "config.toml").write_text(original)
    obj.Reload(dbus_interface=INTERFACE)
    other = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).parent / "fixtures/run_daemon.py"),
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert other.returncode == 1 and "already running" in other.stderr
    fake_pactl.add_sink()
    fake_pactl.event()
    client("switch")
    spin_until(lambda: str(properties()["State"]) == "on_pc")
    spin_until(lambda: fake_pactl.read()["default"] == SINK)
    daemon.send_signal(signal.SIGHUP)
    drain()
    daemon.terminate()
    daemon.wait(timeout=5)
    assert fake_pactl.read()["default"] == SINK
    assert (
        json.loads((tmp_path / "state.json").read_text())["restore_default_sink"]
        == "speakers"
    )


def test_full_cycle_accelerated(fake_pactl, bluez_server, tmp_path):
    config = Config(device=Device(ADDRESS))
    store = Store(tmp_path / "state.json")
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    system = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    config_file = tmp_path / "config.toml"
    config_file.write_text(
        TEMPLATE.replace('address = ""', f'address = "{ADDRESS}"')
        .replace("grab_delay_ms = 500", "grab_delay_ms = 0")
        .replace("release_idle_seconds = 120", "release_idle_seconds = 10")
    )
    config = load(config_file)

    def factory(emit):
        return (
            BlueZ(system, config, emit),
            Audio(config, store, emit, fake_pactl.command),
            Session(system, bus, config, emit),
        )

    service = Service(
        bus,
        config,
        store,
        config_file,
        factory,
        timer=lambda ms, callback: GLib.timeout_add(max(1, ms // 20), callback),
    )
    seen = []
    listener = bus.signal_subscribe(
        None,
        INTERFACE,
        "Transition",
        PATH,
        None,
        Gio.DBusSignalFlags.NONE,
        lambda *args: seen.append(args[5].unpack()),
    )
    try:
        assert service.start()
        spin_until(lambda: service.initialized)
        fake_pactl.add_sink()
        fake_pactl.update(
            {"streams": [{"index": 3, "sink": 1, "corked": False, "properties": {}}]}
        )
        fake_pactl.event()
        spin_until(lambda: service.ctx.state == "on_pc")
        spin_until(lambda: fake_pactl.read()["default"] == SINK)
        assert not service.idle_release_at
        fake_pactl.update({"streams": []})
        fake_pactl.event()
        spin_until(lambda: service.idle_release_at > 0)
        spin_until(lambda: service.ctx.state == "released")
        assert fake_pactl.read()["default"] == "speakers"
        assert store.value.restore_default_sink is None
        assert service.idle_release_at == 0
        assert any(t[2] == "audio_started" for t in seen)
        assert any(t[2] == "idle_timeout" for t in seen)
        assert not service.timers
    finally:
        bus.signal_unsubscribe(listener)
        service.close()
        drain()


def test_cli_does_not_import_core():
    from scambio import cli

    tree = ast.parse(Path(cli.__file__).read_text())
    core_imports = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module
        and node.module.startswith("scambio.core")
    ]
    assert len(core_imports) == 1
    assert core_imports[0].module == "scambio.core.service"
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; from scambio.cli import main; main(['status']); "
            "assert not any(n.startswith('scambio.core') for n in sys.modules)",
        ],
        capture_output=True,
    )
    assert result.returncode == 0


def test_systemd_render_only():
    import importlib.util

    path = Path(__file__).parents[1] / "tools/install_user.py"
    spec = importlib.util.spec_from_file_location("install_user", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    text = module.render(path.parents[1])
    assert "@REPO@" not in text
    assert "Type=dbus" in text and "BusName=" + BUS_NAME in text
    assert "ExecReload=/bin/kill -HUP $MAINPID" in text


@pytest.mark.parametrize("mode", ["disconnected", "connected", "user_changed"])
def test_startup_restore_after_crash(fake_pactl, bluez_server, tmp_path, mode):
    from helpers import gio_bus

    from scambio.config import Config, Device

    config = Config(device=Device(ADDRESS))
    fake_pactl.add_sink()
    fake_pactl.update({"default": "speakers" if mode == "user_changed" else SINK})
    store = Store(tmp_path / "state.json")
    store.value.restore_default_sink = "speakers"
    store.value.iphone_priority = True
    store.save()
    store.load()
    if mode == "connected":
        dbusmock.BusType.SYSTEM.get_connection().get_object(
            "org.bluez", bluez_server[1]
        ).UpdateProperties(
            "org.bluez.Device1",
            {"Connected": dbus.Boolean(True)},
            dbus_interface=dbusmock.MOCK_IFACE,
        )
    bus, system = gio_bus(Gio.BusType.SESSION), gio_bus(Gio.BusType.SYSTEM)

    def factory(emit):
        return (
            BlueZ(system, config, emit),
            Audio(config, store, emit, fake_pactl.command),
            Session(system, bus, config, emit),
        )

    service = Service(bus, config, store, tmp_path / "config.toml", factory)
    try:
        assert service.start()
        spin_until(lambda: service.initialized)
        spin_until(lambda: not service.audio.routing_busy)
        assert service.ctx.priority
        assert fake_pactl.read()["default"] == (
            SINK if mode == "connected" else "speakers"
        )
        assert store.value.restore_default_sink == (
            "speakers" if mode == "connected" else None
        )
        assert service.ctx.state == ("on_pc" if mode == "connected" else "released")
    finally:
        service.close()
        drain()


def test_unconfigured_service_and_permanent_audio_failure(fake_pactl, tmp_path):
    from helpers import gio_bus

    from scambio.config import Config

    config = Config()
    store = Store(tmp_path / "state.json")
    fake_pactl.update({"version": "15.0"})
    bus, system = gio_bus(Gio.BusType.SESSION), gio_bus(Gio.BusType.SYSTEM)

    def factory(emit):
        return (
            BlueZ(system, config, emit),
            Audio(config, store, emit, fake_pactl.command),
            Session(system, bus, config, emit),
        )

    service = Service(bus, config, store, tmp_path / "config.toml", factory)
    try:
        assert service.start()
        # Priority commands before adapters are ready must not be lost.
        service.event(Event("SetPriority", True))
        spin_until(lambda: service.initialized)
        assert service.ctx.priority
        assert store.value.iphone_priority
        service.event(Event("Switch"))
        assert service.ctx.last_error == "device_unavailable"
        assert service.ctx.state == "unavailable"
        assert service.audio.retry == 0
        assert len(fake_pactl.calls()) == 1
        assert service.ctx.priority
    finally:
        service.close()
        drain()


def test_executor_sleep_deadline_and_late_results(fake_pactl, bluez_server, tmp_path):
    from helpers import gio_bus

    from scambio.config import Config, Device
    from scambio.core.policy import Context

    config = Config(device=Device(ADDRESS))
    store = Store(tmp_path / "state.json")
    bus, system = gio_bus(Gio.BusType.SESSION), gio_bus(Gio.BusType.SYSTEM)

    def factory(emit):
        return (
            BlueZ(system, config, emit),
            Audio(config, store, emit, fake_pactl.command),
            Session(system, bus, config, emit),
        )

    service = Service(
        bus,
        config,
        store,
        tmp_path / "config.toml",
        factory,
        timer=lambda ms, cb: GLib.timeout_add(max(1, ms // 100), cb),
    )
    try:
        service.start()
        spin_until(lambda: service.initialized)
        read_fd, write_fd = os.pipe()
        service.session.fd = write_fd
        service.ctx = Context(state="connecting", origin="self", audio_active=True)
        service.event(Event("Sleep", True))
        assert service.ctx.pending == "release"
        spin_until(lambda: service.session.fd is None)
        assert os.read(read_fd, 1) == b""
        os.close(read_fd)
        service.event(Event("ConnectResult", "org.bluez.Error.Failed"))
        assert service.ctx.state == "released"
        before = service.ctx
        service.event(Event("ConnectResult"))
        assert service.ctx == before
        assert not service.timers
    finally:
        service.close()
        drain()


def test_reload_future_timers_and_property_signals(fake_pactl, bluez_server, tmp_path):
    from helpers import gio_bus

    from scambio.config import ConfigInvalid
    from scambio.core.policy import Action
    from scambio.core.service import RestartRequired

    config_file = tmp_path / "config.toml"
    config_file.write_text(TEMPLATE.replace('address = ""', f'address = "{ADDRESS}"'))
    config = load(config_file)
    store = Store(tmp_path / "state.json")
    bus, system = gio_bus(Gio.BusType.SESSION), gio_bus(Gio.BusType.SYSTEM)

    def factory(emit):
        return (
            BlueZ(system, config, emit),
            Audio(config, store, emit, fake_pactl.command),
            Session(system, bus, config, emit),
        )

    service = Service(bus, config, store, config_file, factory)
    changes = []
    sub = bus.signal_subscribe(
        None,
        "org.freedesktop.DBus.Properties",
        "PropertiesChanged",
        PATH,
        None,
        Gio.DBusSignalFlags.NONE,
        lambda *args: changes.append(args[5].unpack()[1]),
    )
    try:
        service.start()
        spin_until(lambda: service.initialized)
        service._execute(Action("StartTimer", "IDLE", 120000))
        before = service.idle_release_at
        original = config_file.read_text()
        config_file.write_text(
            original.replace("release_idle_seconds = 120", "release_idle_seconds = 30")
        )
        service.reload()
        assert service.config.policy.release_idle_seconds == 30
        assert service.idle_release_at == before
        service._execute(Action("CancelTimer", "IDLE"))
        service._publish()
        service.event(Event("SetPriority", True))
        spin_until(lambda: any(c.get("IphonePriority") is True for c in changes))
        config_file.write_text(original.replace(ADDRESS, "11:22:33:44:55:66"))
        with pytest.raises(RestartRequired):
            service.reload()
        assert service.config.policy.release_idle_seconds == 30
        config_file.write_text("invalid")
        with pytest.raises(ConfigInvalid):
            service.reload()
        spin_until(lambda: any(c.get("LastError") == "config_invalid" for c in changes))
    finally:
        bus.signal_unsubscribe(sub)
        service.close()
        drain()


@pytest.mark.parametrize(
    "values,event,code,detail",
    [
        (
            {"state": "connecting"},
            Event("ConnectResult", "failed"),
            "connect_failed",
            "BlueZ failed to connect the configured device.",
        ),
        (
            {"state": "connecting"},
            Event("TimerFired", "CONNECT"),
            "connect_timeout",
            "The configured device did not connect before the deadline.",
        ),
        (
            {"state": "connecting", "device_connected": True},
            Event("TimerFired", "SINK"),
            "sink_timeout",
            "The device audio sink did not appear before the deadline.",
        ),
        (
            {"state": "on_pc"},
            Event("TimerFired", "SINK"),
            "sink_lost",
            "The device audio sink was lost and did not return before the deadline.",
        ),
        (
            {"state": "releasing", "device_connected": True},
            Event("DisconnectResult", "failed"),
            "disconnect_failed",
            "The device remains connected after the release attempt.",
        ),
        (
            {},
            Event("Switch"),
            "device_unavailable",
            "The configured device is unavailable in BlueZ.",
        ),
        (
            {"state": "released"},
            Event("AudioBackend", False),
            "audio_backend_down",
            "The pactl audio backend is unavailable.",
        ),
    ],
)
def test_error_signal_technical_detail(
    fake_pactl, bluez_server, tmp_path, values, event, code, detail
):
    from helpers import gio_bus

    from scambio.core.policy import Context

    config = Config(device=Device(ADDRESS))
    store = Store(tmp_path / "state.json")
    bus, system, observer = (
        gio_bus(Gio.BusType.SESSION),
        gio_bus(Gio.BusType.SYSTEM),
        gio_bus(Gio.BusType.SESSION),
    )

    def factory(emit):
        return (
            BlueZ(system, config, emit),
            Audio(config, store, emit, fake_pactl.command),
            Session(system, bus, config, emit),
        )

    service = Service(bus, config, store, tmp_path / "config.toml", factory)
    signals = []
    subscription = observer.signal_subscribe(
        None,
        INTERFACE,
        None,
        PATH,
        None,
        Gio.DBusSignalFlags.NONE,
        lambda *args: signals.append((args[4], args[5].unpack())),
    )
    try:
        assert service.start()
        spin_until(lambda: service.initialized)
        drain()
        signals.clear()
        service.ctx = Context(**values)
        service.event(event)
        spin_until(lambda: any(name == "Error" for name, _ in signals))
        assert [params for name, params in signals if name == "Error"] == [
            (code, detail)
        ]
        assert code != detail and service.properties()["LastError"].unpack() == code
        if code == "sink_timeout":
            assert service.ctx.state == "on_pc"
            assert signals == [
                ("Transition", ("connecting", "on_pc", "sink_timeout")),
                ("Error", (code, detail)),
            ]
    finally:
        observer.signal_unsubscribe(subscription)
        service.close()
        drain()
