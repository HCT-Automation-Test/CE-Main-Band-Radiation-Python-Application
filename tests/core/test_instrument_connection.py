from __future__ import annotations

import threading
from typing import Any

from app.core.instrument_connection import (
    InstrumentConnectionService,
    _DETACHED_THREADS,
    build_equipment_connection_config,
    discover_visa_resources,
)


class _Client:
    def __init__(self) -> None:
        self.connect_calls: list[tuple[str, int]] = []
        self.closed = False

    def connect_to(self, host: str, port: int) -> None:
        self.connect_calls.append((host, port))

    def close(self) -> None:
        self.closed = True


class _Commands:
    def __init__(self, states: dict[str, bool]) -> None:
        self.states = states
        self.calls: list[tuple[Any, Any]] = []

    def connect_equipment(self, client: Any, *, config: Any) -> dict[str, bool]:
        self.calls.append((client, config))
        return self.states


class _BlockingClient(_Client):
    def __init__(self) -> None:
        super().__init__()
        self.closed_event = threading.Event()

    def close(self) -> None:
        super().close()
        self.closed_event.set()


class _BlockingCommands:
    def __init__(self) -> None:
        self.started = threading.Event()
        self.calls = 0

    def connect_equipment(
        self,
        client: _BlockingClient,
        *,
        config: Any,
    ) -> dict[str, bool]:
        _ = config
        self.calls += 1
        self.started.set()
        assert client.closed_event.wait(1.0)
        return {
            "FSV40": True,
            "MT8000A": True,
            "CO3000": True,
            "Switch Box": True,
            "3D Controller": True,
        }


def _connection_config():
    return build_equipment_connection_config(
        mt8000a_visa_resource="MT",
        fsv40_visa_resource="FS",
        co3000_visa_resource="CO",
        controller_3d_visa_resource="3D",
        switch_box_ip_address="192.168.0.10",
        switch_box_port=5000,
    )


def test_build_equipment_connection_config_trims_and_coerces_port() -> None:
    config = build_equipment_connection_config(
        mt8000a_visa_resource=" TCPIP0::192.168.0.3::inst0::INSTR ",
        fsv40_visa_resource=" TCPIP0::192.168.0.2::inst0::INSTR ",
        co3000_visa_resource=" ASRL1::INSTR ",
        controller_3d_visa_resource=" ASRL2::INSTR ",
        switch_box_ip_address=" 192.168.0.10 ",
        switch_box_port="5000",
    )

    assert config.mt8000a_visa_resource == "TCPIP0::192.168.0.3::inst0::INSTR"
    assert config.fsv40_visa_resource == "TCPIP0::192.168.0.2::inst0::INSTR"
    assert config.co3000_visa_resource == "ASRL1::INSTR"
    assert config.controller_3d_visa_resource == "ASRL2::INSTR"
    assert config.switch_box_ip_address == "192.168.0.10"
    assert config.switch_box_port == 5000


def test_discover_visa_resources_uses_provider_and_sorts_values() -> None:
    resources = discover_visa_resources(
        lambda: ("ASRL2::INSTR", "TCPIP0::192.168.0.2::inst0::INSTR")
    )

    assert resources == ["ASRL2::INSTR", "TCPIP0::192.168.0.2::inst0::INSTR"]


def test_instrument_connection_service_discovers_visa_resources_async(qtbot) -> None:
    service = InstrumentConnectionService(
        visa_resource_provider=lambda: (
            "TCPIP0::192.168.0.2::inst0::INSTR",
            "ASRL2::INSTR",
        ),
    )

    with qtbot.waitSignal(service.visa_resources_discovered, timeout=1000) as blocker:
        service.refresh_visa_resources()
    qtbot.waitUntil(lambda: service._discovery_thread is None, timeout=1000)

    assert blocker.args == [
        ["ASRL2::INSTR", "TCPIP0::192.168.0.2::inst0::INSTR"]
    ]


def test_instrument_connection_service_ignores_duplicate_discovery_refresh(
    qtbot,
) -> None:
    started = threading.Event()
    release = threading.Event()
    calls = 0

    def provider() -> tuple[str]:
        nonlocal calls
        calls += 1
        started.set()
        assert release.wait(1.0)
        return ("ASRL1::INSTR",)

    service = InstrumentConnectionService(visa_resource_provider=provider)

    service.refresh_visa_resources()
    qtbot.waitUntil(started.is_set, timeout=1000)
    service.refresh_visa_resources()

    assert calls == 1

    with qtbot.waitSignal(service.visa_resources_discovered, timeout=1000) as blocker:
        release.set()
    qtbot.waitUntil(lambda: service._discovery_thread is None, timeout=1000)

    assert blocker.args == [["ASRL1::INSTR"]]
    assert calls == 1


def test_instrument_connection_service_emits_discovery_failure(qtbot) -> None:
    def provider() -> tuple[str]:
        raise RuntimeError("boom")

    service = InstrumentConnectionService(visa_resource_provider=provider)

    with qtbot.waitSignal(service.visa_discovery_failed, timeout=1000) as blocker:
        service.refresh_visa_resources()
    qtbot.waitUntil(lambda: service._discovery_thread is None, timeout=1000)

    assert blocker.args == ["boom"]


def test_instrument_connection_service_connects_with_config(qtbot) -> None:
    client = _Client()
    commands = _Commands(
        {
            "FSV40": True,
            "MT8000A": True,
            "CO3000": True,
            "Switch Box": False,
            "3D Controller": True,
        }
    )
    service = InstrumentConnectionService(
        client_factory=lambda: client,
        commands=commands,
        tcp_host="127.0.0.10",
        tcp_port=5026,
    )
    config = _connection_config()

    with qtbot.waitSignal(service.connection_finished, timeout=1000) as blocker:
        service.connect_equipment(config)
    qtbot.waitUntil(lambda: service._connection_thread is None, timeout=1000)

    assert blocker.args == [commands.states]
    assert client.connect_calls == [("127.0.0.10", 5026)]
    assert client.closed is True
    assert commands.calls == [(client, config)]


def test_instrument_connection_service_keeps_injected_client_open(qtbot) -> None:
    client = _Client()
    commands = _Commands(
        {
            "FSV40": True,
            "MT8000A": True,
            "CO3000": True,
            "Switch Box": True,
            "3D Controller": True,
        }
    )
    service = InstrumentConnectionService(
        client=client,
        commands=commands,
        tcp_host="127.0.0.10",
        tcp_port=5026,
    )
    config = _connection_config()

    with qtbot.waitSignal(service.connection_finished, timeout=1000) as blocker:
        service.connect_equipment(config)
    qtbot.waitUntil(lambda: service._connection_thread is None, timeout=1000)

    assert blocker.args == [commands.states]
    assert client.connect_calls == [("127.0.0.10", 5026)]
    assert client.closed is False
    assert commands.calls == [(client, config)]


def test_instrument_connection_service_shutdown_cancels_running_connection(
    qtbot,
) -> None:
    client = _BlockingClient()
    commands = _BlockingCommands()
    finished_states = []
    errors = []
    service = InstrumentConnectionService(
        client_factory=lambda: client,
        commands=commands,
    )
    service.connection_finished.connect(finished_states.append)
    service.error_occurred.connect(errors.append)

    service.connect_equipment(_connection_config())
    qtbot.waitUntil(commands.started.is_set, timeout=1000)

    service.shutdown()

    assert client.closed_event.is_set()
    qtbot.waitUntil(lambda: service._connection_thread is None, timeout=1000)
    qtbot.wait(0)

    assert commands.calls == 1
    assert finished_states == []
    assert errors == []


def test_instrument_connection_service_shutdown_does_not_close_injected_client(
    qtbot,
) -> None:
    client = _Client()
    commands = _Commands({"FSV40": True})
    service = InstrumentConnectionService(
        client=client,
        commands=commands,
    )

    service.shutdown()

    assert client.closed is False


def test_instrument_connection_service_shutdown_detaches_blocking_discovery(
    qtbot,
) -> None:
    started = threading.Event()
    release = threading.Event()
    discovered = []
    failures = []

    def provider() -> tuple[str]:
        started.set()
        assert release.wait(2.0)
        return ("ASRL1::INSTR",)

    service = InstrumentConnectionService(visa_resource_provider=provider)
    service.visa_resources_discovered.connect(discovered.append)
    service.visa_discovery_failed.connect(failures.append)

    service.refresh_visa_resources()
    qtbot.waitUntil(started.is_set, timeout=1000)

    service.shutdown()

    assert service._discovery_thread is None
    assert service._discovery_worker is None
    assert _DETACHED_THREADS

    release.set()
    qtbot.waitUntil(lambda: not _DETACHED_THREADS, timeout=3000)
    qtbot.wait(0)

    assert discovered == []
    assert failures == []


def test_instrument_connection_service_ignores_requests_after_shutdown() -> None:
    calls = 0

    def provider() -> tuple[str]:
        nonlocal calls
        calls += 1
        return ("ASRL1::INSTR",)

    commands = _Commands({"FSV40": True})
    service = InstrumentConnectionService(
        client_factory=_Client,
        commands=commands,
        visa_resource_provider=provider,
    )

    service.shutdown()
    service.refresh_visa_resources()
    service.connect_equipment(_connection_config())

    assert calls == 0
    assert commands.calls == []
