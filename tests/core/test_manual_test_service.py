from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from PySide6.QtCore import QObject, Signal

from app.core.manual_test_service import (
    MANUAL_OPERATION_IN_PROGRESS_MESSAGE,
    MANUAL_SERVICE_SHUTTING_DOWN_MESSAGE,
    ManualTestCapabilities,
    ManualTestService,
    manual_test_capabilities,
)
from app.models.enums import AntennaPol, InputPath
from app.models.manual_test import ManualMast, ManualSaSettings


class _Commands:
    def __init__(self, temp_dir: Path | None = None) -> None:
        self.calls: list[tuple[object, ...]] = []
        self.temp_dir = temp_dir
        self.result = True
        self.error: Exception | None = None
        self.on_rotate: Any | None = None
        self.on_stop: Any | None = None
        self.turntable_angle = 90.0

    def _record(self, *call: object) -> bool:
        self.calls.append(call)
        if self.error is not None:
            raise self.error
        return self.result

    def setup_sa_manual(self, _client: Any, **params: object) -> bool:
        return self._record("setup_sa_manual", params)

    def preset_sa(self, _client: Any) -> bool:
        return self._record("preset_sa")

    def clear_trace(self, _client: Any) -> bool:
        return self._record("clear_trace")

    def marker_peak(self, _client: Any, **params: object) -> bool:
        return self._record("marker_peak", params)

    def marker_next(self, _client: Any, **params: object) -> bool:
        return self._record("marker_next", params)

    def marker_off(self, _client: Any, **params: object) -> bool:
        return self._record("marker_off", params)

    def marker_all_off(self, _client: Any) -> bool:
        return self._record("marker_all_off")

    def marker_auto_max(self, _client: Any, **params: object) -> bool:
        return self._record("marker_auto_max", params)

    def marker_set_center(self, _client: Any, **params: object) -> bool:
        return self._record("marker_set_center", params)

    def rotate_turntable(
        self,
        _client: Any,
        *,
        angle: float,
        turntable_speed: int,
    ) -> None:
        self._record("rotate_turntable", angle, turntable_speed)
        if self.on_rotate is not None:
            self.on_rotate()

    def stop_turntable(self, _client: Any) -> None:
        self._record("stop_turntable")
        if self.on_stop is not None:
            self.on_stop()

    def get_turntable_angle(self, _client: Any) -> float:
        self.calls.append(("get_turntable_angle",))
        if self.error is not None:
            raise self.error
        return self.turntable_angle

    def get_screenshot(self, _client: Any) -> bool:
        result = self._record("get_screenshot")
        if result and self.temp_dir is not None:
            self.temp_dir.mkdir(parents=True, exist_ok=True)
            (self.temp_dir / "screenshot.png").write_bytes(
                b"\x89PNG\r\n\x1a\nfixture"
            )
        return result

    def set_antenna_pol(
        self,
        _client: Any,
        *,
        pol: AntennaPol,
        input_path: InputPath,
    ) -> bool:
        return self._record("set_antenna_pol", pol, input_path)


class _EventClient(QObject):
    event_received = Signal(object)

    def deliver(self, event: object) -> None:
        self.event_received.emit(event)


class _ManualTimer:
    def __init__(self, timeout: Any) -> None:
        self._timeout = timeout
        self.active = False
        self.interval_ms: int | None = None

    def start(self, interval_ms: int) -> None:
        self.active = True
        self.interval_ms = interval_ms

    def stop(self) -> None:
        self.active = False

    def isActive(self) -> bool:  # noqa: N802
        return self.active

    def fire(self) -> None:
        assert self.active
        self.active = False
        self._timeout()


def _replace_saturation_timer(service: ManualTestService) -> _ManualTimer:
    timer = _ManualTimer(service._on_saturation_elapsed)
    service._saturation_timer = timer
    return timer


def _replace_turntable_timeout_timer(service: ManualTestService) -> _ManualTimer:
    timer = _ManualTimer(service._on_turntable_timeout)
    service._turntable_timeout_timer = timer
    return timer


def _replace_capture_timer(service: ManualTestService) -> _ManualTimer:
    timer = _ManualTimer(service._on_capture_timer)
    service._capture_timer = timer
    return timer


def _turntable_event(
    command: str,
    params: dict[str, object] | None = None,
    *,
    event_id: str = "event",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=event_id,
        target="CO3000",
        command=command,
        params=params or {},
    )


def _settings() -> ManualSaSettings:
    return ManualSaSettings(
        start_frequency_mhz=1000.0,
        stop_frequency_mhz=12750.0,
        rbw_mhz=1.0,
        vbw_mhz=3.0,
        sweep_point=30001,
        sweep_time_sec=0.1,
        saturation_time_sec=2.5,
        atten_level_db=0.0,
        detector_mode="RMS",
        limit_dbm=-30.0,
    )


def _run_fsv40_operation(
    service: ManualTestService,
    operation: str,
) -> bool:
    if operation == "set":
        return service.apply_sa_settings(_settings())
    if operation == "preset":
        return service.preset_sa()
    if operation == "trace_clear":
        return service.clear_trace()
    raise AssertionError(f"Unknown FSV40 operation: {operation}")


_FSV40_OPERATIONS = (
    (
        "set",
        "FSV40 Set",
        (
            "setup_sa_manual",
            {
                "start_frequency_mhz": 1000.0,
                "stop_frequency_mhz": 12750.0,
                "rbw_mhz": 1.0,
                "vbw_mhz": 3.0,
                "sweep_point": 30001,
                "sweep_time_sec": 0.1,
                "atten_level_db": 0.0,
                "detector_mode": "RMS",
                "limit_dbm": -30.0,
            },
        ),
        "Load SA Manual Setting returned false",
    ),
    ("preset", "FSV40 Preset", ("preset_sa",), "FSV40 Preset returned false"),
    ("trace_clear", "Trace Clear", ("clear_trace",), "Trace Clear returned false"),
)


def _run_marker_operation(
    service: ManualTestService,
    operation: str,
) -> bool:
    if operation == "peak":
        return service.marker_peak(2, 3.5)
    if operation == "next":
        return service.marker_next(2, 3.5)
    if operation == "off":
        return service.marker_off(2, 3.5)
    if operation == "all_off":
        return service.marker_all_off()
    if operation == "auto":
        return service.marker_auto_max(2)
    if operation == "center":
        return service.marker_set_center(2)
    raise AssertionError(f"Unknown Marker operation: {operation}")


_MARKER_OPERATIONS = (
    (
        "peak",
        "Marker Peak",
        ("marker_peak", {"marker_index": 2, "excursion": 3.5}),
        "Marker Peak returned false",
    ),
    (
        "next",
        "Marker Next",
        ("marker_next", {"marker_index": 2, "excursion": 3.5}),
        "Marker Next returned false",
    ),
    (
        "off",
        "Marker OFF",
        ("marker_off", {"marker_index": 2, "excursion": 3.5}),
        "Marker OFF returned false",
    ),
    (
        "all_off",
        "Marker ALL OFF",
        ("marker_all_off",),
        "Marker ALL OFF returned false",
    ),
    (
        "auto",
        "Marker Auto Max",
        ("marker_auto_max", {"marker_index": 2, "excursion": 0.0}),
        "Marker Auto Max returned false",
    ),
    (
        "center",
        "Marker to Center",
        ("marker_set_center", {"marker_index": 2, "excursion": 0.0}),
        "Marker to Center returned false",
    ),
)


@pytest.mark.parametrize(
    ("equipment_state", "expected"),
    [
        ({}, ManualTestCapabilities()),
        ({"FSV40": True}, ManualTestCapabilities(fsv40=True, marker=True)),
        ({"FSV40": False}, ManualTestCapabilities()),
        (
            {"CO3000": True},
            ManualTestCapabilities(turntable=True, mast_3m=True),
        ),
        (
            {"3D Controller": True},
            ManualTestCapabilities(mast_1m=True),
        ),
    ],
)
def test_manual_capabilities_follow_equipment_connections(
    equipment_state: dict[str, bool],
    expected: ManualTestCapabilities,
) -> None:
    assert manual_test_capabilities(equipment_state) == expected


@pytest.mark.parametrize(
    ("operation", "operation_name", "expected_call", "_false_message"),
    _FSV40_OPERATIONS,
)
def test_manual_fsv40_command_runs_once_and_releases_state(
    operation: str,
    operation_name: str,
    expected_call: tuple[object, ...],
    _false_message: str,
) -> None:
    commands = _Commands()
    service = ManualTestService(client=object(), commands=commands)
    signals: list[tuple[object, ...]] = []
    service.running_changed.connect(lambda active: signals.append(("running", active)))
    service.operation_started.connect(
        lambda name: signals.append(
            ("started", name, service.is_running, service.current_operation)
        )
    )
    service.operation_finished.connect(
        lambda name: signals.append(("finished", name, service.is_running))
    )

    assert _run_fsv40_operation(service, operation)

    assert commands.calls == [expected_call]
    assert signals == [
        ("running", True),
        ("started", operation_name, True, operation_name),
        ("finished", operation_name, True),
        ("running", False),
    ]
    assert not service.is_running
    assert service.current_operation is None


@pytest.mark.parametrize(
    ("error", "error_message"),
    [
        (None, None),
        (RuntimeError("transport failed"), "transport failed"),
    ],
)
@pytest.mark.parametrize(
    ("operation", "operation_name", "expected_call", "false_message"),
    _FSV40_OPERATIONS,
)
def test_manual_fsv40_command_failure_releases_state(
    operation: str,
    operation_name: str,
    expected_call: tuple[object, ...],
    false_message: str,
    error: Exception | None,
    error_message: str | None,
) -> None:
    commands = _Commands()
    commands.result = False if error is None else True
    commands.error = error
    service = ManualTestService(client=object(), commands=commands)
    failures: list[tuple[str, str]] = []
    running: list[bool] = []
    service.operation_failed.connect(
        lambda name, detail: failures.append((name, detail))
    )
    service.running_changed.connect(running.append)

    assert not _run_fsv40_operation(service, operation)

    assert commands.calls == [expected_call]
    assert failures == [(operation_name, error_message or false_message)]
    assert running == [True, False]
    assert not service.is_running
    assert service.current_operation is None


def test_manual_service_rejects_reentrant_command() -> None:
    commands = _Commands()
    service = ManualTestService(client=object(), commands=commands)
    failures: list[tuple[str, str]] = []
    nested_results: list[bool] = []
    service.operation_failed.connect(
        lambda name, message: failures.append((name, message))
    )
    service.operation_started.connect(
        lambda _name: nested_results.append(service.preset_sa())
    )

    assert service.clear_trace()

    assert commands.calls == [("clear_trace",)]
    assert nested_results == [False]
    assert failures == [("FSV40 Preset", MANUAL_OPERATION_IN_PROGRESS_MESSAGE)]


@pytest.mark.parametrize(
    ("operation", "operation_name", "_expected_call", "_false_message"),
    _FSV40_OPERATIONS,
)
def test_manual_fsv40_guard_rejects_before_command(
    operation: str,
    operation_name: str,
    _expected_call: tuple[object, ...],
    _false_message: str,
) -> None:
    commands = _Commands()
    service = ManualTestService(
        client=object(),
        commands=commands,
        operation_guard=lambda: "다른 작업 진행 중",
    )
    failures: list[tuple[str, str]] = []
    service.operation_failed.connect(
        lambda name, message: failures.append((name, message))
    )

    assert not _run_fsv40_operation(service, operation)

    assert commands.calls == []
    assert failures == [(operation_name, "다른 작업 진행 중")]
    assert not service.is_running
    assert service.current_operation is None


def test_manual_service_shutdown_rejects_new_command() -> None:
    commands = _Commands()
    service = ManualTestService(client=object(), commands=commands)
    failures: list[tuple[str, str]] = []
    service.operation_failed.connect(
        lambda name, message: failures.append((name, message))
    )

    service.shutdown()

    assert not service.preset_sa()
    assert commands.calls == []
    assert failures == [("FSV40 Preset", MANUAL_SERVICE_SHUTTING_DOWN_MESSAGE)]


@pytest.mark.parametrize(
    ("operation", "operation_name", "expected_call", "_false_message"),
    _MARKER_OPERATIONS,
)
def test_manual_marker_command_runs_once_and_releases_state(
    operation: str,
    operation_name: str,
    expected_call: tuple[object, ...],
    _false_message: str,
) -> None:
    commands = _Commands()
    service = ManualTestService(client=object(), commands=commands)
    finished: list[str] = []
    service.operation_finished.connect(finished.append)

    assert _run_marker_operation(service, operation)

    assert commands.calls == [expected_call]
    assert finished == [operation_name]
    assert not service.is_running
    assert service.current_operation is None


@pytest.mark.parametrize(
    ("error", "error_message"),
    [
        (None, None),
        (RuntimeError("transport failed"), "transport failed"),
    ],
)
@pytest.mark.parametrize(
    ("operation", "operation_name", "expected_call", "false_message"),
    _MARKER_OPERATIONS,
)
def test_manual_marker_command_failure_releases_state(
    operation: str,
    operation_name: str,
    expected_call: tuple[object, ...],
    false_message: str,
    error: Exception | None,
    error_message: str | None,
) -> None:
    commands = _Commands()
    commands.result = False if error is None else True
    commands.error = error
    service = ManualTestService(client=object(), commands=commands)
    failures: list[tuple[str, str]] = []
    service.operation_failed.connect(
        lambda name, detail: failures.append((name, detail))
    )

    assert not _run_marker_operation(service, operation)

    assert commands.calls == [expected_call]
    assert failures == [(operation_name, error_message or false_message)]
    assert not service.is_running
    assert service.current_operation is None


@pytest.mark.parametrize(
    ("operation", "operation_name", "_expected_call", "_false_message"),
    _MARKER_OPERATIONS,
)
def test_manual_marker_guard_rejects_before_command(
    operation: str,
    operation_name: str,
    _expected_call: tuple[object, ...],
    _false_message: str,
) -> None:
    commands = _Commands()
    service = ManualTestService(
        client=object(),
        commands=commands,
        operation_guard=lambda: "다른 작업 진행 중",
    )
    failures: list[tuple[str, str]] = []
    service.operation_failed.connect(
        lambda name, message: failures.append((name, message))
    )

    assert not _run_marker_operation(service, operation)

    assert commands.calls == []
    assert failures == [(operation_name, "다른 작업 진행 중")]
    assert not service.is_running
    assert service.current_operation is None


def test_manual_turntable_waits_for_progress_and_complete_event() -> None:
    commands = _Commands()
    client = _EventClient()
    service = ManualTestService(client=client, commands=commands)
    timer = _replace_turntable_timeout_timer(service)
    info: list[dict[str, object]] = []
    finished: list[str] = []
    service.turntable_info_changed.connect(info.append)
    service.operation_finished.connect(finished.append)

    assert service.move_turntable(angle=360.0, speed=4)
    assert service.is_running
    assert service.is_turntable_running
    assert timer.active
    assert finished == []

    client.deliver(
        SimpleNamespace(target="FSV40", command="turntable_complete", params={})
    )
    client.deliver(
        _turntable_event("turntable_progress", {"Current Angle": 120.0})
    )
    assert service.is_running

    client.deliver(_turntable_event("turntable_complete"))

    assert commands.calls == [("rotate_turntable", 360.0, 4)]
    assert info == [
        {"target_angle": 360.0, "current_angle": None, "speed": 4},
        {"target_angle": 360.0, "current_angle": 120.0, "speed": 4},
        {"target_angle": 360.0, "current_angle": 360.0, "speed": 4},
    ]
    assert finished == ["Turntable 360°"]
    assert not timer.active
    assert not service.is_running
    assert not service.is_turntable_running

    client.deliver(_turntable_event("turntable_complete"))
    assert finished == ["Turntable 360°"]


def test_manual_turntable_handles_immediate_complete_event_once() -> None:
    commands = _Commands()
    client = _EventClient()
    service = ManualTestService(client=client, commands=commands)
    timer = _replace_turntable_timeout_timer(service)
    finished: list[str] = []
    service.operation_finished.connect(finished.append)
    commands.on_rotate = lambda: client.deliver(
        _turntable_event("turntable_complete", event_id="fixed")
    )

    assert service.move_turntable(angle=0.0, speed=6)

    assert commands.calls == [("rotate_turntable", 0.0, 6)]
    assert finished == ["Turntable 0°"]
    assert not timer.active
    assert not service.is_running


def test_manual_turntable_accepts_reused_or_empty_event_ids_for_50_moves() -> None:
    commands = _Commands()
    client = _EventClient()
    service = ManualTestService(client=client, commands=commands)
    finished: list[str] = []
    service.operation_finished.connect(finished.append)
    event_ids = ("fixed", "", "fixed", "repeated")

    for index in range(50):
        angle = 0.0 if index % 2 == 0 else 360.0
        assert service.move_turntable(angle=angle, speed=6)
        client.deliver(
            _turntable_event(
                "turntable_complete",
                event_id=event_ids[index % len(event_ids)],
            )
        )
        assert not service.is_running

    assert len(finished) == 50
    assert len(commands.calls) == 50


def test_manual_turntable_equipment_error_fails_and_releases_state() -> None:
    commands = _Commands()
    client = _EventClient()
    service = ManualTestService(client=client, commands=commands)
    failures: list[tuple[str, str]] = []
    service.operation_failed.connect(
        lambda name, message: failures.append((name, message))
    )

    assert service.move_turntable(angle=360.0, speed=6)
    client.deliver(
        _turntable_event("equipment_error", {"message": "drive fault"})
    )

    assert failures == [("Turntable 360°", "Turntable 회전 실패: drive fault")]
    assert not service.is_running
    assert not service.is_turntable_running


@pytest.mark.parametrize("stop_fails", [False, True])
def test_manual_turntable_timeout_stops_and_releases_state(
    stop_fails: bool,
) -> None:
    commands = _Commands()
    client = _EventClient()
    service = ManualTestService(client=client, commands=commands)
    timer = _replace_turntable_timeout_timer(service)
    failures: list[tuple[str, str]] = []
    service.operation_failed.connect(
        lambda name, message: failures.append((name, message))
    )

    assert service.move_turntable(angle=360.0, speed=6)
    assert timer.active
    assert timer.interval_ms == 300_000

    def fail_stop() -> None:
        raise RuntimeError("stop failed")

    if stop_fails:
        commands.on_stop = fail_stop
    timer.fire()

    assert commands.calls == [
        ("rotate_turntable", 360.0, 6),
        ("stop_turntable",),
    ]
    assert failures == [("Turntable 360°", "Turntable 회전 타임아웃")]
    assert not service.is_running
    assert not service.is_turntable_running


def test_manual_turntable_command_error_releases_state() -> None:
    commands = _Commands()
    commands.error = RuntimeError("transport failed")
    client = _EventClient()
    service = ManualTestService(client=client, commands=commands)
    failures: list[tuple[str, str]] = []
    service.operation_failed.connect(
        lambda name, message: failures.append((name, message))
    )

    assert not service.move_turntable(angle=360.0, speed=6)

    assert commands.calls == [("rotate_turntable", 360.0, 6)]
    assert failures == [("Turntable 360°", "transport failed")]
    assert not service.is_running
    assert not service.is_turntable_running


def test_manual_turntable_guard_rejects_before_command() -> None:
    commands = _Commands()
    service = ManualTestService(
        client=_EventClient(),
        commands=commands,
        operation_guard=lambda: "다른 작업 진행 중",
    )

    assert not service.move_turntable(angle=360.0, speed=6)

    assert commands.calls == []
    assert not service.is_running


@pytest.mark.parametrize(
    ("angle", "speed"),
    [(180.0, 6), (360.0, 0), (360.0, True)],
)
def test_manual_turntable_rejects_invalid_request(
    angle: float,
    speed: int,
) -> None:
    commands = _Commands()
    service = ManualTestService(client=_EventClient(), commands=commands)

    with pytest.raises(ValueError):
        service.move_turntable(angle=angle, speed=speed)

    assert commands.calls == []


def test_manual_turntable_stop_is_independent_of_operation_guard() -> None:
    commands = _Commands()
    service = ManualTestService(
        client=object(),
        commands=commands,
        operation_guard=lambda: "다른 작업 진행 중",
    )
    finished: list[str] = []
    service.operation_finished.connect(finished.append)

    assert service.request_stop()

    assert commands.calls == [("stop_turntable",)]
    assert finished == ["Turntable Stop"]
    assert not service.is_running


def test_manual_turntable_stop_releases_active_move() -> None:
    commands = _Commands()
    client = _EventClient()
    service = ManualTestService(client=client, commands=commands)
    finished: list[str] = []
    service.operation_finished.connect(finished.append)

    assert service.move_turntable(angle=360.0, speed=6)
    assert service.request_stop()

    assert commands.calls == [
        ("rotate_turntable", 360.0, 6),
        ("stop_turntable",),
    ]
    assert finished == ["Turntable Stop"]
    assert not service.is_running
    assert not service.is_turntable_running

    client.deliver(_turntable_event("turntable_complete"))
    assert finished == ["Turntable Stop"]


def test_manual_turntable_stop_failure_keeps_move_active() -> None:
    commands = _Commands()
    client = _EventClient()
    service = ManualTestService(client=client, commands=commands)
    failures: list[tuple[str, str]] = []
    service.operation_failed.connect(
        lambda name, message: failures.append((name, message))
    )

    assert service.move_turntable(angle=360.0, speed=6)
    commands.error = RuntimeError("stop failed")

    assert not service.request_stop()

    assert failures == [("Turntable Stop", "stop failed")]
    assert service.is_turntable_running

    commands.error = None
    client.deliver(_turntable_event("turntable_complete"))
    assert not service.is_running


@pytest.mark.parametrize(
    ("current_angle", "reference_angle", "target_angle", "event_id"),
    [
        (90.0, 0.0, 360.0, "fixed"),
        (180.0, 0.0, 360.0, ""),
        (270.0, 360.0, 0.0, "repeated"),
    ],
)
def test_manual_semi_auto_runs_order_with_same_speed(
    current_angle: float,
    reference_angle: float,
    target_angle: float,
    event_id: str,
) -> None:
    commands = _Commands()
    commands.turntable_angle = current_angle
    client = _EventClient()
    service = ManualTestService(client=client, commands=commands)
    timer = _replace_saturation_timer(service)
    finished: list[str] = []
    info: list[dict[str, object]] = []
    service.operation_finished.connect(finished.append)
    service.turntable_info_changed.connect(info.append)

    assert service.run_semi_auto(speed=4, saturation_time_sec=1.25)
    assert commands.calls == [
        ("get_turntable_angle",),
        ("rotate_turntable", reference_angle, 4),
    ]
    assert service.is_running
    assert service.is_turntable_running

    client.deliver(
        _turntable_event(
            "turntable_progress",
            {"Current Angle": 45.0},
            event_id=event_id,
        )
    )
    client.deliver(
        _turntable_event("turntable_complete", event_id=event_id)
    )

    assert commands.calls == [
        ("get_turntable_angle",),
        ("rotate_turntable", reference_angle, 4),
        ("clear_trace",),
    ]
    assert timer.active
    assert timer.interval_ms == 1250
    assert service.is_running
    assert not service.is_turntable_running

    client.deliver(
        _turntable_event("turntable_complete", event_id=event_id)
    )
    assert commands.calls[-1] == ("clear_trace",)

    timer.fire()
    assert commands.calls[-1] == ("rotate_turntable", target_angle, 4)
    assert service.is_turntable_running

    client.deliver(
        _turntable_event(
            "turntable_progress",
            {"current_angle": 300.0},
            event_id=event_id,
        )
    )
    client.deliver(
        _turntable_event("turntable_complete", event_id=event_id)
    )

    assert finished == ["Semi Auto"]
    assert not service.is_running
    assert service.current_operation is None
    assert info[-1] == {
        "target_angle": target_angle,
        "current_angle": target_angle,
        "speed": 4,
    }


@pytest.mark.parametrize(
    ("current_angle", "target_angle"),
    [(0.0, 360.0), (360.0, 0.0)],
)
def test_manual_semi_auto_skips_move_at_reference_angle(
    current_angle: float,
    target_angle: float,
) -> None:
    commands = _Commands()
    commands.turntable_angle = current_angle
    client = _EventClient()
    service = ManualTestService(client=client, commands=commands)
    saturation_timer = _replace_saturation_timer(service)
    turntable_timer = _replace_turntable_timeout_timer(service)

    assert service.run_semi_auto(speed=4, saturation_time_sec=1.0)

    assert commands.calls == [
        ("get_turntable_angle",),
        ("clear_trace",),
    ]
    assert saturation_timer.active
    assert not turntable_timer.active

    saturation_timer.fire()
    assert commands.calls[-1] == ("rotate_turntable", target_angle, 4)
    assert turntable_timer.active

    client.deliver(_turntable_event("turntable_complete"))
    assert not service.is_running


def test_manual_semi_auto_zero_saturation_uses_next_timer_tick() -> None:
    commands = _Commands()
    client = _EventClient()
    service = ManualTestService(client=client, commands=commands)
    timer = _replace_saturation_timer(service)

    assert service.run_semi_auto(speed=3, saturation_time_sec=0.0)
    client.deliver(_turntable_event("turntable_complete"))

    assert timer.active
    assert timer.interval_ms == 0
    assert commands.calls[-1] == ("clear_trace",)

    timer.fire()
    assert commands.calls[-1] == ("rotate_turntable", 360.0, 3)


@pytest.mark.parametrize(
    "saturation_time_sec",
    [-1.0, float("nan"), float("inf"), True],
)
def test_manual_semi_auto_rejects_invalid_saturation_before_command(
    saturation_time_sec: float,
) -> None:
    commands = _Commands()
    service = ManualTestService(client=_EventClient(), commands=commands)

    with pytest.raises(ValueError):
        service.run_semi_auto(
            speed=6,
            saturation_time_sec=saturation_time_sec,
        )

    assert commands.calls == []
    assert not service.is_running


@pytest.mark.parametrize("speed", [0, -1, True])
def test_manual_semi_auto_rejects_invalid_speed_before_command(
    speed: int,
) -> None:
    commands = _Commands()
    service = ManualTestService(client=_EventClient(), commands=commands)

    with pytest.raises(ValueError):
        service.run_semi_auto(speed=speed, saturation_time_sec=5.0)

    assert commands.calls == []
    assert not service.is_running


def test_manual_semi_auto_guard_rejects_before_command() -> None:
    commands = _Commands()
    service = ManualTestService(
        client=_EventClient(),
        commands=commands,
        operation_guard=lambda: "다른 작업 진행 중",
    )

    assert not service.run_semi_auto(speed=6, saturation_time_sec=5.0)

    assert commands.calls == []
    assert not service.is_running


def test_manual_semi_auto_angle_query_failure_releases_state() -> None:
    commands = _Commands()
    commands.error = RuntimeError("angle failed")
    service = ManualTestService(client=_EventClient(), commands=commands)
    failures: list[tuple[str, str]] = []
    service.operation_failed.connect(
        lambda name, message: failures.append((name, message))
    )

    assert not service.run_semi_auto(speed=6, saturation_time_sec=5.0)

    assert commands.calls == [("get_turntable_angle",)]
    assert failures == [("Semi Auto", "angle failed")]
    assert not service.is_running
    assert service.current_operation is None


def test_manual_semi_auto_initial_move_failure_releases_state() -> None:
    commands = _Commands()
    client = _EventClient()
    service = ManualTestService(client=client, commands=commands)
    failures: list[tuple[str, str]] = []
    service.operation_failed.connect(
        lambda name, message: failures.append((name, message))
    )

    def fail_rotate(
        _client: Any,
        *,
        angle: float,
        turntable_speed: int,
    ) -> None:
        commands.calls.append(("rotate_turntable", angle, turntable_speed))
        raise RuntimeError("initial move failed")

    commands.rotate_turntable = fail_rotate

    assert not service.run_semi_auto(speed=6, saturation_time_sec=5.0)

    assert commands.calls == [
        ("get_turntable_angle",),
        ("rotate_turntable", 0.0, 6),
    ]
    assert failures == [("Semi Auto", "initial move failed")]
    assert not service.is_running
    assert not service.is_turntable_running


@pytest.mark.parametrize(
    ("result", "error", "message"),
    [
        (False, None, "Clear Trace returned false"),
        (True, RuntimeError("clear failed"), "clear failed"),
    ],
)
def test_manual_semi_auto_trace_clear_failure_releases_state(
    result: bool,
    error: Exception | None,
    message: str,
) -> None:
    commands = _Commands()
    client = _EventClient()
    service = ManualTestService(client=client, commands=commands)
    timer = _replace_saturation_timer(service)
    failures: list[tuple[str, str]] = []
    service.operation_failed.connect(
        lambda name, detail: failures.append((name, detail))
    )
    assert service.run_semi_auto(speed=6, saturation_time_sec=5.0)
    commands.result = result
    commands.error = error

    client.deliver(_turntable_event("turntable_complete"))

    assert failures == [("Semi Auto", message)]
    assert not timer.active
    assert not service.is_running
    assert not service.is_turntable_running


def test_manual_semi_auto_final_move_failure_releases_state() -> None:
    commands = _Commands()
    client = _EventClient()
    service = ManualTestService(client=client, commands=commands)
    timer = _replace_saturation_timer(service)
    failures: list[tuple[str, str]] = []
    service.operation_failed.connect(
        lambda name, message: failures.append((name, message))
    )
    assert service.run_semi_auto(speed=6, saturation_time_sec=5.0)
    client.deliver(_turntable_event("turntable_complete"))
    commands.error = RuntimeError("final move failed")

    timer.fire()

    assert commands.calls[-1] == ("rotate_turntable", 360.0, 6)
    assert failures == [("Semi Auto", "final move failed")]
    assert not service.is_running
    assert not service.is_turntable_running


@pytest.mark.parametrize("after_timer", [False, True])
def test_manual_semi_auto_equipment_error_releases_state(
    after_timer: bool,
) -> None:
    commands = _Commands()
    client = _EventClient()
    service = ManualTestService(client=client, commands=commands)
    timer = _replace_saturation_timer(service)
    failures: list[tuple[str, str]] = []
    service.operation_failed.connect(
        lambda name, message: failures.append((name, message))
    )
    assert service.run_semi_auto(speed=6, saturation_time_sec=5.0)
    if after_timer:
        client.deliver(_turntable_event("turntable_complete"))
        timer.fire()

    client.deliver(
        _turntable_event("equipment_error", {"message": "drive fault"})
    )

    assert failures == [("Semi Auto", "Turntable 회전 실패: drive fault")]
    assert not service.is_running
    assert not service.is_turntable_running


@pytest.mark.parametrize("after_saturation", [False, True])
def test_manual_semi_auto_rotation_timeout_stops_and_releases_state(
    after_saturation: bool,
) -> None:
    commands = _Commands()
    client = _EventClient()
    service = ManualTestService(client=client, commands=commands)
    saturation_timer = _replace_saturation_timer(service)
    turntable_timer = _replace_turntable_timeout_timer(service)
    failures: list[tuple[str, str]] = []
    service.operation_failed.connect(
        lambda name, message: failures.append((name, message))
    )

    assert service.run_semi_auto(speed=6, saturation_time_sec=5.0)
    if after_saturation:
        client.deliver(_turntable_event("turntable_complete"))
        saturation_timer.fire()

    assert turntable_timer.active
    assert turntable_timer.interval_ms == 300_000
    turntable_timer.fire()

    assert commands.calls[-1] == ("stop_turntable",)
    assert failures == [("Semi Auto", "Turntable 회전 타임아웃")]
    assert not service.is_running
    assert not service.is_turntable_running


@pytest.mark.parametrize("after_timer", [False, True])
def test_manual_semi_auto_stop_during_rotation_sends_once(
    after_timer: bool,
) -> None:
    commands = _Commands()
    client = _EventClient()
    service = ManualTestService(client=client, commands=commands)
    timer = _replace_saturation_timer(service)
    if after_timer:
        assert service.run_semi_auto(speed=6, saturation_time_sec=5.0)
        client.deliver(_turntable_event("turntable_complete"))
        timer.fire()
    else:
        assert service.run_semi_auto(speed=6, saturation_time_sec=5.0)

    assert service.request_stop()

    assert commands.calls[-1] == ("stop_turntable",)
    assert sum(call == ("stop_turntable",) for call in commands.calls) == 1
    assert not service.is_running
    assert not service.is_turntable_running


def test_manual_semi_auto_stop_failure_keeps_rotation_active() -> None:
    commands = _Commands()
    client = _EventClient()
    service = ManualTestService(client=client, commands=commands)
    _replace_saturation_timer(service)
    assert service.run_semi_auto(speed=6, saturation_time_sec=5.0)
    commands.error = RuntimeError("stop failed")

    assert not service.request_stop()

    assert service.is_running
    assert service.is_turntable_running

    commands.error = None
    assert service.request_stop()
    assert not service.is_running


def test_manual_semi_auto_stop_during_saturation_only_cancels_timer() -> None:
    commands = _Commands()
    client = _EventClient()
    service = ManualTestService(client=client, commands=commands)
    timer = _replace_saturation_timer(service)
    finished: list[str] = []
    service.operation_finished.connect(finished.append)
    assert service.run_semi_auto(speed=6, saturation_time_sec=5.0)
    client.deliver(_turntable_event("turntable_complete"))
    calls_before_stop = list(commands.calls)

    assert service.request_stop()

    assert commands.calls == calls_before_stop
    assert not timer.active
    assert finished == ["Turntable Stop"]
    assert not service.is_running


@pytest.mark.parametrize(
    ("mast", "polarization", "input_path"),
    [
        (ManualMast.BILOG_3M, AntennaPol.V, InputPath.INPUT1),
        (ManualMast.BILOG_3M, AntennaPol.H, InputPath.INPUT1),
        (ManualMast.HORN_3M, AntennaPol.V, InputPath.INPUT2),
        (ManualMast.HORN_3M, AntennaPol.H, InputPath.INPUT2),
        (ManualMast.MAST_1M, AntennaPol.V, InputPath.INPUT3),
        (ManualMast.MAST_1M, AntennaPol.H, InputPath.INPUT3),
    ],
)
def test_manual_mast_uses_existing_input_path_mapping(
    mast: ManualMast,
    polarization: AntennaPol,
    input_path: InputPath,
) -> None:
    commands = _Commands()
    service = ManualTestService(client=object(), commands=commands)

    assert service.set_mast_polarization(
        mast=mast,
        polarization=polarization,
    )

    assert commands.calls == [
        ("set_antenna_pol", polarization, input_path)
    ]
    assert not service.is_running


@pytest.mark.parametrize(
    ("result", "error", "message"),
    [
        (False, None, "Change Ant Pol returned false"),
        (True, RuntimeError("transport failed"), "transport failed"),
    ],
)
def test_manual_mast_failure_releases_state(
    result: bool,
    error: Exception | None,
    message: str,
) -> None:
    commands = _Commands()
    commands.result = result
    commands.error = error
    service = ManualTestService(client=object(), commands=commands)
    failures: list[tuple[str, str]] = []
    service.operation_failed.connect(
        lambda name, detail: failures.append((name, detail))
    )

    assert not service.set_mast_polarization(
        mast=ManualMast.HORN_3M,
        polarization=AntennaPol.H,
    )

    assert failures == [("Mast Polarization", message)]
    assert not service.is_running
    assert service.current_operation is None


def test_manual_mast_guard_rejects_before_command() -> None:
    commands = _Commands()
    service = ManualTestService(
        client=object(),
        commands=commands,
        operation_guard=lambda: "다른 작업 진행 중",
    )

    assert not service.set_mast_polarization(
        mast=ManualMast.HORN_3M,
        polarization=AntennaPol.H,
    )

    assert commands.calls == []
    assert not service.is_running


def test_manual_single_capture_saves_and_emits_path(tmp_path: Path) -> None:
    temp_dir = tmp_path / "temp"
    commands = _Commands(temp_dir)
    service = ManualTestService(
        client=object(),
        commands=commands,
        temp_dir=temp_dir,
    )
    saved: list[str] = []
    service.screenshot_saved.connect(saved.append)

    assert service.capture_single(directory=tmp_path, base_name="capture")

    destination = tmp_path / "capture.png"
    assert commands.calls == [("get_screenshot",)]
    assert destination.is_file()
    assert saved == [str(destination)]
    assert not service.is_running


def test_manual_single_capture_collision_sends_no_command(tmp_path: Path) -> None:
    destination = tmp_path / "capture.png"
    destination.write_bytes(b"existing")
    commands = _Commands(tmp_path / "temp")
    service = ManualTestService(
        client=object(),
        commands=commands,
        temp_dir=tmp_path / "temp",
    )

    assert not service.capture_single(directory=tmp_path, base_name="capture")

    assert commands.calls == []
    assert destination.read_bytes() == b"existing"
    assert not service.is_running


@pytest.mark.parametrize(
    ("result", "error", "message"),
    [
        (False, None, "Get Screenshot returned false"),
        (True, RuntimeError("capture failed"), "capture failed"),
    ],
)
def test_manual_single_capture_command_failure_releases_state(
    tmp_path: Path,
    result: bool,
    error: Exception | None,
    message: str,
) -> None:
    temp_dir = tmp_path / "temp"
    commands = _Commands(temp_dir)
    commands.result = result
    commands.error = error
    service = ManualTestService(
        client=object(),
        commands=commands,
        temp_dir=temp_dir,
    )
    failures: list[tuple[str, str]] = []
    service.operation_failed.connect(
        lambda name, detail: failures.append((name, detail))
    )

    assert not service.capture_single(directory=tmp_path, base_name="capture")

    assert commands.calls == [("get_screenshot",)]
    assert failures == [("Single Capture", message)]
    assert not (tmp_path / "capture.png").exists()
    assert not service.is_running


def test_manual_capture_many_preserves_command_and_signal_order(
    tmp_path: Path,
) -> None:
    temp_dir = tmp_path / "temp"
    commands = _Commands(temp_dir)
    service = ManualTestService(
        client=object(),
        commands=commands,
        temp_dir=temp_dir,
    )
    timer = _replace_capture_timer(service)
    saved: list[str] = []
    service.screenshot_saved.connect(saved.append)

    assert service.capture_many(
        directory=tmp_path,
        base_name="capture",
        interval_sec=1.5,
        shot_count=3,
    )

    assert commands.calls == [("get_screenshot",), ("clear_trace",)]
    assert timer.interval_ms == 1500
    assert service.is_running

    timer.fire()
    assert commands.calls == [
        ("get_screenshot",),
        ("clear_trace",),
        ("get_screenshot",),
        ("clear_trace",),
    ]
    assert service.is_running

    timer.fire()
    assert commands.calls[-1] == ("get_screenshot",)
    assert [Path(path).name for path in saved] == [
        "capture_001.png",
        "capture_002.png",
        "capture_003.png",
    ]
    assert not service.is_running


def test_manual_capture_many_one_shot_uses_numbered_name(tmp_path: Path) -> None:
    temp_dir = tmp_path / "temp"
    commands = _Commands(temp_dir)
    service = ManualTestService(
        client=object(),
        commands=commands,
        temp_dir=temp_dir,
    )
    timer = _replace_capture_timer(service)

    assert service.capture_many(
        directory=tmp_path,
        base_name="capture",
        interval_sec=10.0,
        shot_count=1,
    )

    assert commands.calls == [("get_screenshot",)]
    assert (tmp_path / "capture_001.png").is_file()
    assert not timer.active
    assert not service.is_running


def test_manual_capture_many_preflight_checks_every_path(tmp_path: Path) -> None:
    (tmp_path / "capture_002.png").write_bytes(b"existing")
    temp_dir = tmp_path / "temp"
    commands = _Commands(temp_dir)
    service = ManualTestService(
        client=object(),
        commands=commands,
        temp_dir=temp_dir,
    )

    assert not service.capture_many(
        directory=tmp_path,
        base_name="capture",
        interval_sec=0.0,
        shot_count=3,
    )

    assert commands.calls == []
    assert not (tmp_path / "capture_001.png").exists()
    assert not service.is_running


def test_manual_capture_many_failure_preserves_saved_files(tmp_path: Path) -> None:
    temp_dir = tmp_path / "temp"
    commands = _Commands(temp_dir)
    service = ManualTestService(
        client=object(),
        commands=commands,
        temp_dir=temp_dir,
    )
    timer = _replace_capture_timer(service)

    assert service.capture_many(
        directory=tmp_path,
        base_name="capture",
        interval_sec=0.0,
        shot_count=3,
    )
    commands.result = False
    timer.fire()

    assert (tmp_path / "capture_001.png").is_file()
    assert not (tmp_path / "capture_002.png").exists()
    assert not (tmp_path / "capture_003.png").exists()
    assert not service.is_running


@pytest.mark.parametrize("interval_sec", [-1.0, float("nan"), True])
def test_manual_capture_many_rejects_invalid_interval(
    tmp_path: Path,
    interval_sec: float,
) -> None:
    commands = _Commands(tmp_path / "temp")
    service = ManualTestService(client=object(), commands=commands)

    with pytest.raises(ValueError):
        service.capture_many(
            directory=tmp_path,
            base_name="capture",
            interval_sec=interval_sec,
            shot_count=2,
        )

    assert commands.calls == []


def test_manual_capture_guard_rejects_before_command(tmp_path: Path) -> None:
    commands = _Commands(tmp_path / "temp")
    service = ManualTestService(
        client=object(),
        commands=commands,
        operation_guard=lambda: "다른 작업 진행 중",
    )

    assert not service.capture_many(
        directory=tmp_path,
        base_name="capture",
        interval_sec=0.0,
        shot_count=2,
    )

    assert commands.calls == []
