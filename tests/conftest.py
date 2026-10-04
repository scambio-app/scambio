"""Fail closed: both buses are private before any test module is collected."""

import os

import dbusmock
import pytest

_BUSES = []
_ORIGINAL = {}


def pytest_sessionstart(session):
    for kind in (dbusmock.BusType.SYSTEM, dbusmock.BusType.SESSION):
        key = kind.environ[0]
        _ORIGINAL[key] = os.environ.get(key)
        bus = dbusmock.PrivateDBus(kind)
        bus.start()
        _BUSES.append((key, bus))
    assert_private_buses()


def assert_private_buses():
    assert len(_BUSES) == 2
    for key, bus in _BUSES:
        assert os.environ.get(key) == bus.address, f"Unsafe bus: {key}"
        assert "dbusmock_data_" in bus.address


@pytest.fixture(autouse=True)
def private_bus_guard():
    assert_private_buses()
    yield
    assert_private_buses()


def pytest_sessionfinish(session, exitstatus):
    for key, bus in reversed(_BUSES):
        bus.stop()
        if _ORIGINAL[key] is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = _ORIGINAL[key]
