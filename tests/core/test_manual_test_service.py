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
    def __init__(self, temp_dir: Path) -> None:
        self.temp_dir = temp_dir
        self.calls: list[tuple[object, ...]] = []
        self.result = True
        self.error: Exception | None = None
        self.on_rotate: Any | None = None
        self.on_stop: Any | None = None

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

    def set_antenna_pol(
        self,
        _client: Any,
        *,
        pol: AntennaPol,
        input_path: InputPath,
    ) -> bool:
        return self._record("set_antenna_pol", pol, input_path)

    def get_screenshot(self, _client: Any) -> bool:
        result = self._record("get_screenshot")
        if result:
            self.temp_dir.mkdir(parents=True, exist_ok=True)
            (self.temp_dir / "screenshot.png").write_bytes(
                b"\x89PNG\r\n\x1a\nfixture"
            )
        return result


class _EventClient(QObject):
    event_received = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self._events: list[object] = []

    def buffer_event(self, event: object) -> None:
        self._events.append(event)

    def pop_events(self, predicate) -> list[object]:
        matched = [event for event in self._events if predicate(event)]
        self._events = [event for event in self._events if not predicate(event)]
        return matched

    def deliver(self, event: object, *, buffer: bool = False) -> None:
        if buffer:
            self.buffer_event(event)
        self.event_received.emit(event)


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


@pytest.mark.parametrize(
    ("equipment_state", "expected"),
    [
        ({}, ManualTestCapabilities()),
        (
            {"FSV40": True},
            ManualTestCapabilities(fsv40=True, marker=True, capture=True),
        ),
        (
            {"CO3000": True},
            ManualTestCapabilities(turntable=True, mast_3m=True),
        ),
        (
            {"3D Controller": True},
            ManualTestCapabilities(mast_1m=True),
        ),
        (
            {"FSV40": True, "CO3000": True},
            ManualTestCapabilities(
                fsv40=True,
                marker=True,
                capture=True,
                turntable=True,
                mast_3m=True,
            ),
        ),
    ],
)
def test_manual_capabilities_use_only_equipment_connection_state(
    equipment_state: dict[str, bool],
    expected: ManualTestCapabilities,
) -> None:
    assert manual_test_capabilities(equipment_state) == expected


def test_manual_service_runs_command_synchronously_and_releases_state(
    tmp_path: Path,
) -> None:
    commands = _Commands(tmp_path)
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

    assert service.clear_trace()

    assert commands.calls == [("clear_trace",)]
    assert signals == [
        ("running", True),
        ("started", "Trace Clear", True, "Trace Clear"),
        ("finished", "Trace Clear", True),
        ("running", False),
    ]
    assert not service.is_running
    assert service.current_operation is None


@pytest.mark.parametrize(
    ("result", "error", "message"),
    [
        (False, None, "Trace Clear returned false"),
        (True, RuntimeError("transport failed"), "transport failed"),
    ],
)
def test_manual_service_reports_failure_and_releases_state(
    tmp_path: Path,
    result: bool,
    error: Exception | None,
    message: str,
) -> None:
    commands = _Commands(tmp_path)
    commands.result = result
    commands.error = error
    service = ManualTestService(client=object(), commands=commands)
    failures: list[tuple[str, str]] = []
    running: list[bool] = []
    service.operation_failed.connect(
        lambda name, detail: failures.append((name, detail))
    )
    service.running_changed.connect(running.append)

    assert not service.clear_trace()

    assert failures == [("Trace Clear", message)]
    assert running == [True, False]
    assert not service.is_running
    assert service.current_operation is None


def test_manual_service_rejects_reentrant_command(tmp_path: Path) -> None:
    commands = _Commands(tmp_path)
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


def test_manual_service_guard_rejects_before_command(tmp_path: Path) -> None:
    commands = _Commands(tmp_path)
    service = ManualTestService(
        client=object(),
        commands=commands,
        operation_guard=lambda: "다른 작업 진행 중",
    )
    failures: list[tuple[str, str]] = []
    service.operation_failed.connect(
        lambda name, message: failures.append((name, message))
    )

    assert not service.clear_trace()

    assert commands.calls == []
    assert failures == [("Trace Clear", "다른 작업 진행 중")]


def test_manual_service_shutdown_rejects_new_command(tmp_path: Path) -> None:
    commands = _Commands(tmp_path)
    service = ManualTestService(client=object(), commands=commands)
    failures: list[tuple[str, str]] = []
    service.operation_failed.connect(
        lambda name, message: failures.append((name, message))
    )

    service.shutdown()

    assert not service.preset_sa()
    assert commands.calls == []
    assert failures == [("FSV40 Preset", MANUAL_SERVICE_SHUTTING_DOWN_MESSAGE)]


def test_manual_service_applies_settings_once(tmp_path: Path) -> None:
    commands = _Commands(tmp_path)
    service = ManualTestService(client=object(), commands=commands)

    assert service.apply_sa_settings(_settings())

    assert commands.calls == [
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
        )
    ]


@pytest.mark.parametrize(
    ("method_name", "command_name"),
    [
        ("marker_peak", "marker_peak"),
        ("marker_next", "marker_next"),
        ("marker_off", "marker_off"),
        ("marker_auto_max", "marker_auto_max"),
        ("marker_set_center", "marker_set_center"),
    ],
)
def test_manual_marker_commands_are_direct(
    tmp_path: Path,
    method_name: str,
    command_name: str,
) -> None:
    commands = _Commands(tmp_path)
    service = ManualTestService(client=object(), commands=commands)

    method = getattr(service, method_name)
    assert method(2, 3.5)

    assert commands.calls == [
        (command_name, {"marker_index": 2, "excursion": 3.5})
    ]


def test_manual_turntable_waits_for_progress_and_complete_event(
    tmp_path: Path,
) -> None:
    commands = _Commands(tmp_path)
    client = _EventClient()
    service = ManualTestService(client=client, commands=commands)
    info: list[dict[str, object]] = []
    finished: list[str] = []
    service.turntable_info_changed.connect(info.append)
    service.operation_finished.connect(finished.append)

    assert service.move_turntable(angle=360.0, speed=6)
    assert service.is_running
    assert service.is_turntable_running
    assert finished == []

    client.deliver(
        _turntable_event("turntable_progress", {"Current Angle": 120.0})
    )
    assert service.is_running
    client.deliver(_turntable_event("turntable_complete"))

    assert commands.calls == [("rotate_turntable", 360.0, 6)]
    assert info == [
        {"target_angle": 360.0, "current_angle": None, "speed": 6},
        {"target_angle": 360.0, "current_angle": 120.0, "speed": 6},
        {"target_angle": 360.0, "current_angle": 360.0, "speed": 6},
    ]
    assert finished == ["Turntable 360°"]
    assert not service.is_running
    assert not service.is_turntable_running


def test_manual_turntable_consumes_immediate_buffered_event_once(
    tmp_path: Path,
) -> None:
    commands = _Commands(tmp_path)
    client = _EventClient()
    service = ManualTestService(client=client, commands=commands)
    finished: list[str] = []
    service.operation_finished.connect(finished.append)
    complete = _turntable_event("turntable_complete", event_id="fixed")

    commands.on_rotate = lambda: client.deliver(complete, buffer=True)

    assert service.move_turntable(angle=0.0, speed=6)

    assert finished == ["Turntable 0°"]
    assert not service.is_running
    assert client.pop_events(lambda _event: True) == []


def test_manual_turntable_ignores_late_signal_duplicate_from_previous_move(
    tmp_path: Path,
) -> None:
    commands = _Commands(tmp_path)
    client = _EventClient()
    service = ManualTestService(client=client, commands=commands)
    first_complete = _turntable_event("turntable_complete", event_id="reused")
    second_complete = _turntable_event("turntable_complete", event_id="reused")
    commands.on_rotate = lambda: client.buffer_event(first_complete)

    assert service.move_turntable(angle=0.0, speed=6)
    assert not service.is_running

    commands.on_rotate = None
    assert service.move_turntable(angle=360.0, speed=6)
    client.event_received.emit(first_complete)
    assert service.is_running

    client.deliver(second_complete)
    assert not service.is_running


def test_manual_turntable_accepts_reused_or_empty_event_ids_for_50_moves(
    tmp_path: Path,
) -> None:
    commands = _Commands(tmp_path)
    client = _EventClient()
    service = ManualTestService(client=client, commands=commands)
    finished: list[str] = []
    service.operation_finished.connect(finished.append)

    event_ids = ("fixed", "", "fixed", "repeated")
    for index in range(50):
        angle = 0.0 if index % 2 == 0 else 360.0
        event_id = event_ids[index % len(event_ids)]
        commands.on_rotate = lambda event_id=event_id: client.deliver(
            _turntable_event("turntable_complete", event_id=event_id),
            buffer=True,
        )

        assert service.move_turntable(angle=angle, speed=6)
        assert not service.is_running

    assert len(finished) == 50
    assert len([call for call in commands.calls if call[0] == "rotate_turntable"]) == 50


def test_manual_turntable_equipment_error_fails_and_releases_state(
    tmp_path: Path,
) -> None:
    commands = _Commands(tmp_path)
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


def test_manual_turntable_stop_cancels_active_move(tmp_path: Path) -> None:
    commands = _Commands(tmp_path)
    client = _EventClient()
    service = ManualTestService(client=client, commands=commands)
    cancelled: list[str] = []
    service.operation_cancelled.connect(cancelled.append)

    assert service.move_turntable(angle=360.0, speed=6)
    assert service.request_stop()

    assert commands.calls == [
        ("rotate_turntable", 360.0, 6),
        ("stop_turntable",),
    ]
    assert cancelled == ["Turntable 360°"]
    assert not service.is_running
    assert not service.request_stop()


def test_manual_turntable_stop_does_not_duplicate_terminal_event(
    tmp_path: Path,
) -> None:
    commands = _Commands(tmp_path)
    client = _EventClient()
    service = ManualTestService(client=client, commands=commands)
    finished: list[str] = []
    cancelled: list[str] = []
    service.operation_finished.connect(finished.append)
    service.operation_cancelled.connect(cancelled.append)
    commands.on_stop = lambda: client.deliver(
        _turntable_event("turntable_complete")
    )

    assert service.move_turntable(angle=360.0, speed=6)
    assert service.request_stop()

    assert finished == ["Turntable 360°"]
    assert cancelled == []
    assert not service.is_running


def test_manual_turntable_stop_failure_keeps_move_active(tmp_path: Path) -> None:
    commands = _Commands(tmp_path)
    client = _EventClient()
    service = ManualTestService(client=client, commands=commands)
    failures: list[tuple[str, str]] = []
    service.operation_failed.connect(
        lambda name, message: failures.append((name, message))
    )

    assert service.move_turntable(angle=360.0, speed=6)
    commands.error = RuntimeError("transport disconnected")

    assert not service.request_stop()
    assert service.is_turntable_running
    assert failures == [
        ("Turntable Stop", "Turntable 정지 실패: transport disconnected")
    ]

    commands.error = None
    client.deliver(_turntable_event("turntable_complete"))
    assert not service.is_running


def test_manual_turntable_timeout_stops_and_fails(tmp_path: Path) -> None:
    commands = _Commands(tmp_path)
    client = _EventClient()
    service = ManualTestService(
        client=client,
        commands=commands,
        turntable_timeout_sec=0.01,
    )
    failures: list[tuple[str, str]] = []
    service.operation_failed.connect(
        lambda name, message: failures.append((name, message))
    )

    assert service.move_turntable(angle=360.0, speed=6)
    service._turntable_timeout_timer.timeout.emit()

    assert commands.calls == [
        ("rotate_turntable", 360.0, 6),
        ("stop_turntable",),
    ]
    assert failures == [("Turntable 360°", "Turntable 회전 타임아웃")]


def test_manual_turntable_shutdown_stops_and_releases_state(tmp_path: Path) -> None:
    commands = _Commands(tmp_path)
    client = _EventClient()
    service = ManualTestService(client=client, commands=commands)

    assert service.move_turntable(angle=360.0, speed=6)

    service.shutdown()

    assert commands.calls == [
        ("rotate_turntable", 360.0, 6),
        ("stop_turntable",),
    ]
    assert not service.is_running
    assert not service.clear_trace()


@pytest.mark.parametrize(
    ("angle", "speed"),
    [(180.0, 6), (360.0, 0), (360.0, True)],
)
def test_manual_turntable_rejects_invalid_request(
    tmp_path: Path,
    angle: float,
    speed: int,
) -> None:
    commands = _Commands(tmp_path)
    service = ManualTestService(client=object(), commands=commands)

    with pytest.raises(ValueError):
        service.move_turntable(angle=angle, speed=speed)

    assert commands.calls == []


def test_manual_mast_command_uses_existing_input_path_mapping(tmp_path: Path) -> None:
    commands = _Commands(tmp_path)
    service = ManualTestService(client=object(), commands=commands)

    assert service.set_mast_polarization(
        mast=ManualMast.HORN_3M,
        polarization=AntennaPol.H,
    )

    assert commands.calls == [
        ("set_antenna_pol", AntennaPol.H, InputPath.INPUT2)
    ]


def test_manual_single_capture_saves_one_screenshot(tmp_path: Path) -> None:
    temp_dir = tmp_path / "temp"
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    commands = _Commands(temp_dir)
    service = ManualTestService(
        client=object(),
        commands=commands,
        temp_dir=temp_dir,
    )
    saved: list[str] = []
    service.screenshot_saved.connect(saved.append)

    assert service.capture_single(directory=output_dir, base_name="capture")

    destination = output_dir / "capture.png"
    assert commands.calls == [("get_screenshot",)]
    assert saved == [str(destination)]
    assert destination.read_bytes() == b"\x89PNG\r\n\x1a\nfixture"


def test_manual_single_capture_collision_sends_no_command(tmp_path: Path) -> None:
    temp_dir = tmp_path / "temp"
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    destination = output_dir / "capture.png"
    destination.write_bytes(b"existing")
    commands = _Commands(temp_dir)
    service = ManualTestService(
        client=object(),
        commands=commands,
        temp_dir=temp_dir,
    )
    failures: list[tuple[str, str]] = []
    service.operation_failed.connect(
        lambda name, message: failures.append((name, message))
    )

    assert not service.capture_single(directory=output_dir, base_name="capture")

    assert commands.calls == []
    assert failures and "capture.png" in failures[0][1]
