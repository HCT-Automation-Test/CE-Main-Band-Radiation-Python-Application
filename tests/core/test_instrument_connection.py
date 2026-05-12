from __future__ import annotations

from typing import Any

from app.core.instrument_connection import (
    InstrumentConnectionService,
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
    config = build_equipment_connection_config(
        mt8000a_visa_resource="MT",
        fsv40_visa_resource="FS",
        co3000_visa_resource="CO",
        controller_3d_visa_resource="3D",
        switch_box_ip_address="192.168.0.10",
        switch_box_port=5000,
    )

    with qtbot.waitSignal(service.connection_finished, timeout=1000) as blocker:
        service.connect_equipment(config)
    qtbot.waitUntil(lambda: service._connection_thread is None, timeout=1000)

    assert blocker.args == [commands.states]
    assert client.connect_calls == [("127.0.0.10", 5026)]
    assert client.closed is True
    assert commands.calls == [(client, config)]
