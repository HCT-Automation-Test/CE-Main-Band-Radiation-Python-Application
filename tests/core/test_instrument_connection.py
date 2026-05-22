from __future__ import annotations

import threading
from typing import Any

import pytest

from app.core import instrument_set
from app.core.instrument_connection import (
    InstrumentConnectionService,
    _DETACHED_THREADS,
    build_equipment_connection_config,
    disconnected_equipment_state,
    describe_equipment_not_ready,
    discover_visa_resources,
    is_required_equipment_ready,
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


class _InstrumentSetSignal:
    def __init__(self) -> None:
        self._slots: list[Any] = []
        self.connected = threading.Event()

    @property
    def slot_count(self) -> int:
        return len(self._slots)

    def connect(self, slot: Any, *args: Any, **kwargs: Any) -> None:
        _ = args, kwargs
        self._slots.append(slot)
        self.connected.set()

    def disconnect(self, slot: Any) -> None:
        self._slots.remove(slot)

    def emit(self, event: Any) -> None:
        for slot in list(self._slots):
            slot(event)


class _InstrumentSetClient:
    def __init__(self) -> None:
        self.event_received = _InstrumentSetSignal()
        self._event_buffer: list[_InstrumentSetEvent] = []
        self.pop_calls = 0
        self.connect_calls: list[tuple[str, int]] = []
        self.closed = False

    def connect_to(self, host: str, port: int) -> None:
        self.connect_calls.append((host, port))

    def close(self) -> None:
        self.closed = True

    def buffer_event(self, event: "_InstrumentSetEvent") -> None:
        self._event_buffer.append(event)

    def pop_events(self, predicate: Any) -> list["_InstrumentSetEvent"]:
        self.pop_calls += 1
        matched: list[_InstrumentSetEvent] = []
        remaining: list[_InstrumentSetEvent] = []
        for event in self._event_buffer:
            if predicate(event):
                matched.append(event)
            else:
                remaining.append(event)
        self._event_buffer = remaining
        return matched


class _InstrumentSetEvent:
    def __init__(
        self,
        *,
        target: str = "CO3000",
        command: str = instrument_set.COMMAND_SET_REFERENCE_COMPLETE,
        params: dict[str, Any] | None = None,
    ) -> None:
        self.target = target
        self.command = command
        self.params = params or {}


class _EquipmentSetCommands:
    def __init__(self) -> None:
        self.calls: list[str] = []
        self.co3000_called = threading.Event()
        self.fsv40_called = threading.Event()

    def set_reference_co3000(self, client: Any) -> bool:
        _ = client
        self.calls.append("CO3000 Set Reference")
        self.co3000_called.set()
        return True

    def self_align_fsv40(self, client: Any) -> bool:
        _ = client
        self.calls.append("FSV40 Self Alignment")
        self.fsv40_called.set()
        return True


def _connection_config():
    return build_equipment_connection_config(
        mt8000a_visa_resource="MT",
        fsv40_visa_resource="FS",
        co3000_visa_resource="CO",
        controller_3d_visa_resource="3D",
        switch_box_ip_address="192.168.0.10",
        switch_box_port=5000,
    )


def _ready_equipment_state() -> dict[str, bool]:
    return {
        "FSV40": True,
        "MT8000A": True,
        "CO3000": True,
        "Switch Box": True,
        "3D Controller": True,
    }


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


def test_required_equipment_readiness_requires_all_targets() -> None:
    states = {
        "FSV40": True,
        "MT8000A": True,
        "CO3000": True,
        "Switch Box": True,
        "3D Controller": True,
        "Extra Device": False,
    }

    assert is_required_equipment_ready(states)
    assert not is_required_equipment_ready({"FSV40": True})
    assert describe_equipment_not_ready({"FSV40": True}) == (
        "missing equipment: MT8000A, CO3000, Switch Box, 3D Controller"
    )


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


def test_instrument_connection_service_guard_blocks_connection(qtbot) -> None:
    client = _Client()
    commands = _Commands({"FSV40": True})
    service = InstrumentConnectionService(
        client_factory=lambda: client,
        commands=commands,
        connection_guard=lambda: "blocked",
    )

    with qtbot.waitSignal(service.error_occurred, timeout=1000) as blocker:
        service.connect_equipment(_connection_config())

    assert blocker.args == ["blocked"]
    assert service._connection_thread is None
    assert client.connect_calls == []
    assert commands.calls == []


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


def test_instrument_connection_service_sets_equipment_in_sequence(qtbot) -> None:
    client = _InstrumentSetClient()
    commands = _EquipmentSetCommands()
    service = InstrumentConnectionService(
        client_factory=lambda: client,
        commands=commands,
        tcp_host="127.0.0.10",
        tcp_port=5026,
        instrument_set_timeout_s=1.0,
    )
    steps: list[str] = []
    service.set_step_changed.connect(steps.append)

    with qtbot.waitSignal(service.set_finished, timeout=1000):
        service.set_equipment(_ready_equipment_state())
        qtbot.waitUntil(commands.co3000_called.is_set, timeout=1000)

        assert service.is_setting
        assert commands.calls == ["CO3000 Set Reference"]
        assert steps == ["CO3000 Set Reference 진행 중"]

        qtbot.waitUntil(lambda: client.event_received.slot_count == 1, timeout=1000)
        client.event_received.emit(
            _InstrumentSetEvent(
                target="CO3000",
                command=instrument_set.COMMAND_SET_REFERENCE_COMPLETE,
            )
        )
        qtbot.waitUntil(commands.fsv40_called.is_set, timeout=1000)

        assert commands.calls == [
            "CO3000 Set Reference",
            "FSV40 Self Alignment",
        ]
        assert steps == [
            "CO3000 Set Reference 진행 중",
            "FSV40 Self Alignment 진행 중",
        ]

        qtbot.waitUntil(lambda: client.event_received.slot_count == 1, timeout=1000)
        client.event_received.emit(
            _InstrumentSetEvent(
                target="FSV40",
                command=instrument_set.COMMAND_SELF_ALIGNMENT_COMPLETE,
            )
        )

    qtbot.waitUntil(lambda: service._set_thread is None, timeout=1000)

    assert not service.is_setting
    assert client.connect_calls == [("127.0.0.10", 5026)]
    assert client.closed is True


def test_instrument_connection_service_uses_buffered_set_complete_events(
    qtbot,
) -> None:
    client = _InstrumentSetClient()
    commands = _EquipmentSetCommands()

    def complete_reference(_client: Any) -> bool:
        commands.calls.append("CO3000 Set Reference")
        commands.co3000_called.set()
        client.buffer_event(
            _InstrumentSetEvent(
                target="CO3000",
                command=instrument_set.COMMAND_SET_REFERENCE_COMPLETE,
            )
        )
        return True

    def complete_alignment(_client: Any) -> bool:
        commands.calls.append("FSV40 Self Alignment")
        commands.fsv40_called.set()
        client.buffer_event(
            _InstrumentSetEvent(
                target="FSV40",
                command=instrument_set.COMMAND_SELF_ALIGNMENT_COMPLETE,
            )
        )
        return True

    commands.set_reference_co3000 = complete_reference  # type: ignore[method-assign]
    commands.self_align_fsv40 = complete_alignment  # type: ignore[method-assign]
    service = InstrumentConnectionService(
        client_factory=lambda: client,
        commands=commands,
        instrument_set_timeout_s=1.0,
    )

    with qtbot.waitSignal(service.set_finished, timeout=1000):
        service.set_equipment(_ready_equipment_state())

    qtbot.waitUntil(lambda: service._set_thread is None, timeout=1000)

    assert commands.calls == [
        "CO3000 Set Reference",
        "FSV40 Self Alignment",
    ]
    assert client.pop_calls >= 2


def test_instrument_connection_service_discards_stale_set_complete_events(
    qtbot,
) -> None:
    client = _InstrumentSetClient()
    client.buffer_event(
        _InstrumentSetEvent(
            target="CO3000",
            command=instrument_set.COMMAND_SET_REFERENCE_COMPLETE,
        )
    )
    commands = _EquipmentSetCommands()
    service = InstrumentConnectionService(
        client_factory=lambda: client,
        commands=commands,
        instrument_set_timeout_s=1.0,
    )

    service.set_equipment(_ready_equipment_state())
    qtbot.waitUntil(commands.co3000_called.is_set, timeout=1000)
    qtbot.waitUntil(lambda: client.pop_calls >= 2, timeout=1000)
    qtbot.wait(100)

    assert commands.calls == ["CO3000 Set Reference"]
    assert not commands.fsv40_called.is_set()

    client.event_received.emit(
        _InstrumentSetEvent(
            target="CO3000",
            command=instrument_set.COMMAND_SET_REFERENCE_COMPLETE,
        )
    )
    qtbot.waitUntil(commands.fsv40_called.is_set, timeout=1000)
    client.event_received.emit(
        _InstrumentSetEvent(
            target="FSV40",
            command=instrument_set.COMMAND_SELF_ALIGNMENT_COMPLETE,
        )
    )
    qtbot.waitUntil(lambda: service._set_thread is None, timeout=1000)

    assert commands.calls == [
        "CO3000 Set Reference",
        "FSV40 Self Alignment",
    ]


def test_instrument_connection_service_rejects_set_when_equipment_not_ready(
    qtbot,
) -> None:
    client = _InstrumentSetClient()
    commands = _EquipmentSetCommands()
    service = InstrumentConnectionService(
        client_factory=lambda: client,
        commands=commands,
    )

    with qtbot.waitSignal(service.set_failed, timeout=1000) as blocker:
        service.set_equipment({"FSV40": True})

    assert blocker.args == [
        "장비 Set 실패: missing equipment: MT8000A, CO3000, Switch Box, "
        "3D Controller"
    ]
    assert service._set_thread is None
    assert client.connect_calls == []
    assert commands.calls == []


def test_instrument_connection_service_rejects_set_while_connecting(qtbot) -> None:
    client = _BlockingClient()
    commands = _BlockingCommands()
    service = InstrumentConnectionService(
        client_factory=lambda: client,
        commands=commands,
    )

    service.connect_equipment(_connection_config())
    qtbot.waitUntil(commands.started.is_set, timeout=1000)

    with qtbot.waitSignal(service.set_failed, timeout=1000) as blocker:
        service.set_equipment(_ready_equipment_state())

    service.shutdown()
    qtbot.waitUntil(lambda: service._connection_thread is None, timeout=1000)

    assert blocker.args == ["장비 연결 요청이 이미 진행 중입니다."]


def test_instrument_connection_service_rejects_connect_while_setting(qtbot) -> None:
    client = _InstrumentSetClient()
    commands = _EquipmentSetCommands()
    service = InstrumentConnectionService(
        client_factory=lambda: client,
        commands=commands,
        instrument_set_timeout_s=1.0,
    )

    service.set_equipment(_ready_equipment_state())
    qtbot.waitUntil(commands.co3000_called.is_set, timeout=1000)

    with qtbot.waitSignal(service.error_occurred, timeout=1000) as blocker:
        service.connect_equipment(_connection_config())

    qtbot.waitUntil(lambda: client.event_received.slot_count == 1, timeout=1000)
    client.event_received.emit(
        _InstrumentSetEvent(
            target="CO3000",
            command=instrument_set.COMMAND_SET_REFERENCE_COMPLETE,
        )
    )
    qtbot.waitUntil(commands.fsv40_called.is_set, timeout=1000)
    client.event_received.emit(
        _InstrumentSetEvent(
            target="FSV40",
            command=instrument_set.COMMAND_SELF_ALIGNMENT_COMPLETE,
        )
    )
    qtbot.waitUntil(lambda: service._set_thread is None, timeout=1000)

    assert blocker.args == ["장비 Set 작업이 이미 진행 중입니다."]
    assert commands.calls == [
        "CO3000 Set Reference",
        "FSV40 Self Alignment",
    ]


def test_instrument_connection_service_rejects_duplicate_set(qtbot) -> None:
    client = _InstrumentSetClient()
    commands = _EquipmentSetCommands()
    service = InstrumentConnectionService(
        client_factory=lambda: client,
        commands=commands,
        instrument_set_timeout_s=1.0,
    )

    service.set_equipment(_ready_equipment_state())
    qtbot.waitUntil(commands.co3000_called.is_set, timeout=1000)

    with qtbot.waitSignal(service.set_failed, timeout=1000) as blocker:
        service.set_equipment(_ready_equipment_state())

    qtbot.waitUntil(lambda: client.event_received.slot_count == 1, timeout=1000)
    client.event_received.emit(
        _InstrumentSetEvent(
            target="CO3000",
            command=instrument_set.COMMAND_SET_REFERENCE_COMPLETE,
        )
    )
    qtbot.waitUntil(commands.fsv40_called.is_set, timeout=1000)
    client.event_received.emit(
        _InstrumentSetEvent(
            target="FSV40",
            command=instrument_set.COMMAND_SELF_ALIGNMENT_COMPLETE,
        )
    )
    qtbot.waitUntil(lambda: service._set_thread is None, timeout=1000)

    assert blocker.args == ["장비 Set 작업이 이미 진행 중입니다."]
    assert commands.calls == [
        "CO3000 Set Reference",
        "FSV40 Self Alignment",
    ]


def test_instrument_connection_service_rejects_set_when_guard_blocks(qtbot) -> None:
    client = _InstrumentSetClient()
    commands = _EquipmentSetCommands()
    service = InstrumentConnectionService(
        client_factory=lambda: client,
        commands=commands,
        connection_guard=lambda: "blocked",
    )

    with qtbot.waitSignal(service.set_failed, timeout=1000) as blocker:
        service.set_equipment(_ready_equipment_state())

    assert blocker.args == ["blocked"]
    assert client.connect_calls == []
    assert commands.calls == []


def test_instrument_connection_service_co3000_timeout_disconnects_equipment(
    qtbot,
) -> None:
    client = _InstrumentSetClient()
    commands = _EquipmentSetCommands()
    service = InstrumentConnectionService(
        client_factory=lambda: client,
        commands=commands,
        instrument_set_timeout_s=0.01,
    )
    failures: list[str] = []
    disconnected: list[dict[str, bool]] = []
    service.set_failed.connect(failures.append)
    service.equipment_disconnected.connect(disconnected.append)

    service.set_equipment(_ready_equipment_state())

    qtbot.waitUntil(lambda: bool(failures), timeout=1000)
    qtbot.waitUntil(lambda: service._set_thread is None, timeout=1000)

    assert failures == [
        "장비 Set timeout: CO3000 Set Reference 완료 event를 수신하지 못했습니다."
    ]
    assert disconnected == [disconnected_equipment_state()]
    assert commands.calls == ["CO3000 Set Reference"]


def test_instrument_connection_service_fsv40_timeout_disconnects_equipment(
    qtbot,
) -> None:
    client = _InstrumentSetClient()
    commands = _EquipmentSetCommands()
    service = InstrumentConnectionService(
        client_factory=lambda: client,
        commands=commands,
        instrument_set_timeout_s=0.01,
    )
    failures: list[str] = []
    disconnected: list[dict[str, bool]] = []
    service.set_failed.connect(failures.append)
    service.equipment_disconnected.connect(disconnected.append)

    service.set_equipment(_ready_equipment_state())
    qtbot.waitUntil(commands.co3000_called.is_set, timeout=1000)
    qtbot.waitUntil(lambda: client.event_received.slot_count == 1, timeout=1000)
    client.event_received.emit(
        _InstrumentSetEvent(
            target="CO3000",
            command=instrument_set.COMMAND_SET_REFERENCE_COMPLETE,
        )
    )

    qtbot.waitUntil(lambda: bool(failures), timeout=1000)
    qtbot.waitUntil(lambda: service._set_thread is None, timeout=1000)

    assert failures == [
        "장비 Set timeout: FSV40 Self Alignment 완료 event를 수신하지 못했습니다."
    ]
    assert disconnected == [disconnected_equipment_state()]
    assert commands.calls == [
        "CO3000 Set Reference",
        "FSV40 Self Alignment",
    ]


def test_instrument_connection_service_equipment_error_disconnects_equipment(
    qtbot,
) -> None:
    client = _InstrumentSetClient()
    commands = _EquipmentSetCommands()
    service = InstrumentConnectionService(
        client_factory=lambda: client,
        commands=commands,
        instrument_set_timeout_s=1.0,
    )
    disconnected: list[dict[str, bool]] = []
    service.equipment_disconnected.connect(disconnected.append)

    service.set_equipment(_ready_equipment_state())
    qtbot.waitUntil(commands.co3000_called.is_set, timeout=1000)

    with qtbot.waitSignal(service.set_failed, timeout=1000) as blocker:
        qtbot.waitUntil(lambda: client.event_received.slot_count == 1, timeout=1000)
        client.event_received.emit(
            _InstrumentSetEvent(
                target="CO3000",
                command=instrument_set.COMMAND_EQUIPMENT_ERROR,
                params={"message": "reference failed"},
            )
        )

    qtbot.waitUntil(lambda: service._set_thread is None, timeout=1000)

    assert blocker.args == [
        "장비 Set 실패: CO3000 / Set Reference failed: reference failed"
    ]
    assert disconnected == [disconnected_equipment_state()]
    assert commands.calls == ["CO3000 Set Reference"]


def test_instrument_connection_service_shutdown_detaches_running_set_worker(
    qtbot,
) -> None:
    release = threading.Event()
    client = _InstrumentSetClient()
    commands = _EquipmentSetCommands()

    def block_after_command(_client: Any) -> bool:
        commands.calls.append("CO3000 Set Reference")
        commands.co3000_called.set()
        assert release.wait(2.0)
        return True

    commands.set_reference_co3000 = block_after_command  # type: ignore[method-assign]
    finished = []
    failures = []
    service = InstrumentConnectionService(
        client_factory=lambda: client,
        commands=commands,
        instrument_set_timeout_s=0.01,
    )
    service.set_finished.connect(lambda: finished.append(True))
    service.set_failed.connect(failures.append)

    service.set_equipment(_ready_equipment_state())
    qtbot.waitUntil(commands.co3000_called.is_set, timeout=1000)

    service.shutdown()

    assert service._set_thread is None
    assert service._set_worker is None
    assert _DETACHED_THREADS

    release.set()
    qtbot.waitUntil(lambda: not _DETACHED_THREADS, timeout=3000)
    qtbot.wait(0)

    assert finished == []
    assert failures == []


def test_instrument_connection_service_shutdown_cancels_waiting_set_worker(
    qtbot,
) -> None:
    client = _InstrumentSetClient()
    commands = _EquipmentSetCommands()
    finished = []
    failures = []
    disconnected = []
    service = InstrumentConnectionService(
        client_factory=lambda: client,
        commands=commands,
        instrument_set_timeout_s=10.0,
    )
    service.set_finished.connect(lambda: finished.append(True))
    service.set_failed.connect(failures.append)
    service.equipment_disconnected.connect(disconnected.append)

    service.set_equipment(_ready_equipment_state())
    qtbot.waitUntil(commands.co3000_called.is_set, timeout=1000)
    qtbot.waitUntil(lambda: client.event_received.slot_count == 1, timeout=1000)

    service.shutdown()

    assert service._set_thread is None
    assert service._set_worker is None
    assert not _DETACHED_THREADS
    assert client.closed is True
    assert finished == []
    assert failures == []
    assert disconnected == []


def test_wait_for_equipment_set_event_returns_on_complete_event() -> None:
    client = _InstrumentSetClient()
    errors: list[BaseException] = []

    thread = _start_instrument_set_wait(client, errors)
    client.event_received.emit(
        _InstrumentSetEvent(command=instrument_set.COMMAND_SET_REFERENCE_COMPLETE)
    )
    thread.join(timeout=1.0)

    assert not thread.is_alive()
    assert errors == []
    assert client.event_received.slot_count == 0


def test_wait_for_equipment_set_event_discards_buffered_complete_by_default() -> None:
    client = _InstrumentSetClient()
    client.buffer_event(
        _InstrumentSetEvent(command=instrument_set.COMMAND_SET_REFERENCE_COMPLETE)
    )

    with pytest.raises(
        instrument_set.InstrumentSetTimeoutError,
        match=r"CO3000 / Set Reference completion timeout",
    ):
        instrument_set.wait_for_equipment_set_event(
            client,
            target="CO3000",
            complete_command=instrument_set.COMMAND_SET_REFERENCE_COMPLETE,
            source_command="Set Reference",
            timeout_s=0.01,
        )

    assert client.event_received.slot_count == 0
    assert client.pop_calls >= 1


def test_wait_for_equipment_set_event_accepts_buffered_complete_when_enabled() -> None:
    client = _InstrumentSetClient()
    client.buffer_event(
        _InstrumentSetEvent(command=instrument_set.COMMAND_SET_REFERENCE_COMPLETE)
    )
    errors: list[BaseException] = []

    thread = _start_instrument_set_wait(client, errors, accept_buffered_events=True)
    thread.join(timeout=1.0)

    assert not thread.is_alive()
    assert errors == []
    assert client.event_received.slot_count == 0
    assert client.pop_calls >= 1


def test_wait_for_equipment_set_event_raises_on_equipment_error_event() -> None:
    client = _InstrumentSetClient()
    errors: list[BaseException] = []

    thread = _start_instrument_set_wait(client, errors)
    client.event_received.emit(
        _InstrumentSetEvent(
            command=instrument_set.COMMAND_EQUIPMENT_ERROR,
            params={"message": "reference failed"},
        )
    )
    thread.join(timeout=1.0)

    assert not thread.is_alive()
    assert len(errors) == 1
    assert isinstance(errors[0], instrument_set.InstrumentSetError)
    assert str(errors[0]) == "CO3000 / Set Reference failed: reference failed"
    assert client.event_received.slot_count == 0


def test_wait_for_equipment_set_event_raises_on_timeout() -> None:
    client = _InstrumentSetClient()

    with pytest.raises(
        instrument_set.InstrumentSetTimeoutError,
        match=r"CO3000 / Set Reference completion timeout",
    ):
        instrument_set.wait_for_equipment_set_event(
            client,
            target="CO3000",
            complete_command=instrument_set.COMMAND_SET_REFERENCE_COMPLETE,
            source_command="Set Reference",
            timeout_s=0.01,
        )

    assert client.event_received.slot_count == 0


def test_wait_for_equipment_set_event_returns_when_cancel_requested() -> None:
    client = _InstrumentSetClient()
    cancel_requested = threading.Event()
    errors: list[BaseException] = []

    thread = _start_instrument_set_wait(
        client,
        errors,
        timeout_s=10.0,
        cancel_requested=cancel_requested.is_set,
    )
    cancel_requested.set()
    thread.join(timeout=1.0)

    assert not thread.is_alive()
    assert errors == []
    assert client.event_received.slot_count == 0


def test_wait_for_equipment_set_event_disconnects_after_buffered_error() -> None:
    client = _InstrumentSetClient()
    errors: list[BaseException] = []

    thread = _start_instrument_set_wait(client, errors)
    client.buffer_event(
        _InstrumentSetEvent(
            command=instrument_set.COMMAND_EQUIPMENT_ERROR,
            params={},
        )
    )
    thread.join(timeout=1.0)

    assert not thread.is_alive()
    assert len(errors) == 1
    assert isinstance(errors[0], instrument_set.InstrumentSetError)
    assert str(errors[0]) == "CO3000 / Set Reference failed"
    assert client.event_received.slot_count == 0


def _start_instrument_set_wait(
    client: _InstrumentSetClient,
    errors: list[BaseException],
    *,
    timeout_s: float = 1.0,
    cancel_requested: Any = None,
    accept_buffered_events: bool = False,
) -> threading.Thread:
    def run() -> None:
        try:
            instrument_set.wait_for_equipment_set_event(
                client,
                target="CO3000",
                complete_command=instrument_set.COMMAND_SET_REFERENCE_COMPLETE,
                source_command="Set Reference",
                timeout_s=timeout_s,
                cancel_requested=cancel_requested,
                accept_buffered_events=accept_buffered_events,
            )
        except BaseException as exc:
            errors.append(exc)

    thread = threading.Thread(target=run)
    thread.start()
    assert client.event_received.connected.wait(1.0)
    return thread
