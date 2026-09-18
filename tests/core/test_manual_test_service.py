from __future__ import annotations

import threading
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QObject, Signal

from app.core.manual_test_service import (
    MANUAL_OPERATION_IN_PROGRESS_MESSAGE,
    ManualTestCapabilities,
    ManualTestService,
    _DETACHED_THREADS,
    manual_test_capabilities,
)
from app.models.manual_test import ManualSaSettings


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
                semi_auto=True,
            ),
        ),
    ],
)
def test_manual_capabilities_use_only_equipment_connection_state(
    equipment_state: dict[str, bool],
    expected: ManualTestCapabilities,
) -> None:
    assert manual_test_capabilities(equipment_state) == expected


def test_manual_capabilities_ignore_non_equipment_state() -> None:
    capabilities = manual_test_capabilities(
        {
            "FSV40": True,
            "TestCase": False,
            "Call": False,
            "RF Filter": False,
            "Queue": False,
        }
    )

    assert capabilities == ManualTestCapabilities(
        fsv40=True,
        marker=True,
        capture=True,
    )


def test_manual_service_runs_operation_and_reports_progress(qtbot) -> None:
    service = ManualTestService()
    steps: list[str] = []
    finished: list[str] = []
    running: list[bool] = []
    service.step_changed.connect(steps.append)
    service.operation_finished.connect(finished.append)
    service.running_changed.connect(running.append)

    assert service.start_operation(
        "FSV40 Set",
        lambda context: context.report_step("설정 적용"),
    )
    assert service.is_running
    assert service.current_operation == "FSV40 Set"

    qtbot.waitUntil(lambda: not service.is_running, timeout=1000)

    assert steps == ["설정 적용"]
    assert finished == ["FSV40 Set"]
    assert running == [True, False]
    assert service.current_operation is None


@pytest.mark.parametrize("error", [RuntimeError("boom"), TimeoutError("timeout")])
def test_manual_service_recovers_after_error(qtbot, error: Exception) -> None:
    service = ManualTestService()
    failures: list[tuple[str, str]] = []
    service.operation_failed.connect(
        lambda operation, message: failures.append((operation, message)),
    )

    def fail(_context) -> None:
        raise error

    assert service.start_operation("실패 작업", fail)
    qtbot.waitUntil(lambda: not service.is_running, timeout=1000)

    assert failures == [("실패 작업", str(error))]
    assert service.start_operation("재시도", lambda _context: None)
    qtbot.waitUntil(lambda: not service.is_running, timeout=1000)


def test_manual_stop_keeps_busy_until_worker_finishes(qtbot) -> None:
    service = ManualTestService()
    entered = threading.Event()
    release = threading.Event()
    steps: list[str] = []
    cancelled: list[str] = []
    failures: list[tuple[str, str]] = []
    service.operation_cancelled.connect(cancelled.append)
    service.operation_failed.connect(
        lambda operation, message: failures.append((operation, message)),
    )

    def operation(context) -> None:
        steps.append("step_1")
        entered.set()
        release.wait(2.0)
        if context.cancel_requested:
            return
        steps.append("step_2")

    assert service.start_operation("다단계 작업", operation)
    qtbot.waitUntil(entered.is_set, timeout=1000)

    service.request_stop()

    assert service.cancel_requested
    assert service.is_running
    assert not service.start_operation("경쟁 작업", lambda _context: None)
    assert failures[-1] == ("경쟁 작업", MANUAL_OPERATION_IN_PROGRESS_MESSAGE)

    release.set()
    qtbot.waitUntil(lambda: not service.is_running, timeout=1000)

    assert steps == ["step_1"]
    assert cancelled == ["다단계 작업"]


def test_manual_service_guard_rejects_before_operation_runs() -> None:
    calls: list[str] = []
    service = ManualTestService(operation_guard=lambda: "다른 작업 진행 중")
    failures: list[tuple[str, str]] = []
    service.operation_failed.connect(
        lambda operation, message: failures.append((operation, message)),
    )

    accepted = service.start_operation(
        "차단 작업",
        lambda _context: calls.append("command"),
    )

    assert not accepted
    assert calls == []
    assert failures == [("차단 작업", "다른 작업 진행 중")]
    assert not service.is_running


def test_manual_service_shutdown_cancels_and_rejects_new_work(qtbot) -> None:
    service = ManualTestService()
    entered = threading.Event()

    def operation(context) -> None:
        entered.set()
        context.wait(5.0)

    assert service.start_operation("종료 대기", operation)
    qtbot.waitUntil(entered.is_set, timeout=1000)

    service.shutdown()

    assert not service.is_running
    assert not service.start_operation("신규 작업", lambda _context: None)


def test_manual_shutdown_preserves_blocked_thread_until_it_finishes(qtbot) -> None:
    service = ManualTestService()
    entered = threading.Event()
    release = threading.Event()
    detached_count = len(_DETACHED_THREADS)

    def operation(_context) -> None:
        entered.set()
        release.wait(5.0)

    assert service.start_operation("지연 종료", operation)
    qtbot.waitUntil(entered.is_set, timeout=1000)

    service.shutdown()

    assert len(_DETACHED_THREADS) == detached_count + 1
    assert not service.start_operation("신규 작업", lambda _context: None)

    release.set()
    qtbot.waitUntil(
        lambda: len(_DETACHED_THREADS) == detached_count,
        timeout=1000,
    )


class _EventClient(QObject):
    event_received = Signal(object)

    def pop_events(self, _predicate) -> list[object]:
        return []


class _ManualCommands:
    def __init__(self, client: _EventClient, temp_dir: Path) -> None:
        self.client = client
        self.temp_dir = temp_dir
        self.calls: list[tuple[object, ...]] = []
        self.emit_turntable_complete = True

    def setup_sa_manual(self, _client, **params) -> bool:
        self.calls.append(("setup_sa_manual", params))
        return True

    def preset_sa(self, _client) -> bool:
        self.calls.append(("preset_sa",))
        return True

    def clear_trace(self, _client) -> bool:
        self.calls.append(("clear_trace",))
        return True

    def get_screenshot(self, _client) -> bool:
        self.calls.append(("get_screenshot",))
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        (self.temp_dir / "screenshot.png").write_bytes(
            b"\x89PNG\r\n\x1a\nfixture"
        )
        return True

    def get_turntable_angle(self, _client) -> float:
        self.calls.append(("get_turntable_angle",))
        return 90.0

    def rotate_turntable(self, _client, *, angle: float, turntable_speed: int) -> None:
        self.calls.append(("rotate_turntable", angle, turntable_speed))
        if self.emit_turntable_complete:
            self.client.event_received.emit(
                SimpleNamespace(
                    target="CO3000",
                    command="turntable_complete",
                    params={},
                )
            )

    def stop_turntable(self, _client) -> None:
        self.calls.append(("stop_turntable",))


def _manual_settings(*, saturation_time_sec: float = 0.0) -> ManualSaSettings:
    return ManualSaSettings(
        start_frequency_mhz=1000.0,
        stop_frequency_mhz=12750.0,
        rbw_mhz=1.0,
        vbw_mhz=3.0,
        sweep_point=30001,
        sweep_time_sec=0.1,
        saturation_time_sec=saturation_time_sec,
        atten_level_db=0.0,
        detector_mode="RMS",
        limit_dbm=-30.0,
    )


def test_manual_service_applies_settings_and_remembers_saturation(
    qtbot,
    tmp_path: Path,
) -> None:
    client = _EventClient()
    commands = _ManualCommands(client, tmp_path)
    service = ManualTestService(client=client, commands=commands, temp_dir=tmp_path)

    assert service.apply_sa_settings(_manual_settings(saturation_time_sec=2.5))
    qtbot.waitUntil(lambda: not service.is_running, timeout=1000)

    assert service.applied_saturation_time_sec == 2.5
    assert commands.calls[0][0] == "setup_sa_manual"


def test_manual_service_capture_many_preserves_order(
    qtbot,
    tmp_path: Path,
) -> None:
    client = _EventClient()
    temp_dir = tmp_path / "temp"
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    commands = _ManualCommands(client, temp_dir)
    service = ManualTestService(client=client, commands=commands, temp_dir=temp_dir)
    saved: list[str] = []
    service.screenshot_saved.connect(saved.append)

    assert service.capture_many(
        directory=output_dir,
        base_name="capture",
        interval_sec=0,
        shot_count=3,
    )
    qtbot.waitUntil(lambda: not service.is_running, timeout=1000)

    assert [Path(path).name for path in saved] == [
        "capture_001.png",
        "capture_002.png",
        "capture_003.png",
    ]
    assert [call[0] for call in commands.calls] == [
        "get_screenshot",
        "clear_trace",
        "get_screenshot",
        "clear_trace",
        "get_screenshot",
    ]


def test_manual_service_capture_preflight_sends_no_command_on_collision(
    qtbot,
    tmp_path: Path,
) -> None:
    client = _EventClient()
    temp_dir = tmp_path / "temp"
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "capture_002.png").write_bytes(b"existing")
    commands = _ManualCommands(client, temp_dir)
    service = ManualTestService(client=client, commands=commands, temp_dir=temp_dir)
    failures: list[tuple[str, str]] = []
    service.operation_failed.connect(
        lambda operation, message: failures.append((operation, message)),
    )

    assert service.capture_many(
        directory=output_dir,
        base_name="capture",
        interval_sec=0,
        shot_count=3,
    )
    qtbot.waitUntil(lambda: not service.is_running, timeout=1000)

    assert commands.calls == []
    assert failures and "capture_002.png" in failures[0][1]


def test_manual_service_semi_auto_uses_applied_saturation_and_rotation_order(
    qtbot,
    tmp_path: Path,
) -> None:
    client = _EventClient()
    commands = _ManualCommands(client, tmp_path)
    service = ManualTestService(client=client, commands=commands, temp_dir=tmp_path)
    assert service.apply_sa_settings(_manual_settings())
    qtbot.waitUntil(lambda: not service.is_running, timeout=1000)
    commands.calls.clear()

    assert service.run_semi_auto(speed=4)
    qtbot.waitUntil(lambda: not service.is_running, timeout=1000)

    assert commands.calls == [
        ("get_turntable_angle",),
        ("rotate_turntable", 0.0, 6),
        ("clear_trace",),
        ("rotate_turntable", 360.0, 4),
    ]


def test_manual_service_stop_stops_active_turntable(qtbot, tmp_path: Path) -> None:
    client = _EventClient()
    commands = _ManualCommands(client, tmp_path)
    commands.emit_turntable_complete = False
    service = ManualTestService(
        client=client,
        commands=commands,
        temp_dir=tmp_path,
        turntable_timeout_sec=5.0,
    )
    cancelled: list[str] = []
    failures: list[tuple[str, str]] = []
    service.operation_cancelled.connect(cancelled.append)
    service.operation_failed.connect(
        lambda operation, message: failures.append((operation, message)),
    )

    assert service.move_turntable(angle=360.0, speed=6)
    qtbot.waitUntil(
        lambda: any(call[0] == "rotate_turntable" for call in commands.calls),
        timeout=1000,
    )
    service.request_stop()
    qtbot.waitUntil(lambda: not service.is_running, timeout=1000)

    assert ("stop_turntable",) in commands.calls
    assert cancelled == ["Turntable 360°"]
    assert failures == []


def test_manual_service_reports_stop_command_failure(qtbot, tmp_path: Path) -> None:
    client = _EventClient()
    commands = _ManualCommands(client, tmp_path)
    commands.emit_turntable_complete = False
    service = ManualTestService(
        client=client,
        commands=commands,
        temp_dir=tmp_path,
        turntable_timeout_sec=5.0,
    )
    cancelled: list[str] = []
    failures: list[tuple[str, str]] = []
    service.operation_cancelled.connect(cancelled.append)
    service.operation_failed.connect(
        lambda operation, message: failures.append((operation, message)),
    )

    def fail_stop(_client) -> None:
        commands.calls.append(("stop_turntable",))
        raise RuntimeError("transport disconnected")

    commands.stop_turntable = fail_stop

    assert service.move_turntable(angle=360.0, speed=6)
    qtbot.waitUntil(
        lambda: any(call[0] == "rotate_turntable" for call in commands.calls),
        timeout=1000,
    )
    service.request_stop()
    qtbot.waitUntil(lambda: not service.is_running, timeout=1000)

    assert cancelled == []
    assert failures == [
        ("Turntable 360°", "Turntable 정지 실패: transport disconnected"),
    ]


def test_manual_service_timeout_stops_turntable_and_reports_failure(
    qtbot,
    tmp_path: Path,
) -> None:
    client = _EventClient()
    commands = _ManualCommands(client, tmp_path)
    commands.emit_turntable_complete = False
    service = ManualTestService(
        client=client,
        commands=commands,
        temp_dir=tmp_path,
        turntable_timeout_sec=0.01,
    )
    failures: list[tuple[str, str]] = []
    service.operation_failed.connect(
        lambda operation, message: failures.append((operation, message)),
    )

    assert service.move_turntable(angle=360.0, speed=6)
    qtbot.waitUntil(lambda: not service.is_running, timeout=1000)

    assert ("stop_turntable",) in commands.calls
    assert failures == [("Turntable 360°", "Turntable 회전 타임아웃")]


def test_manual_service_stop_during_angle_query_skips_rotation(
    qtbot,
    tmp_path: Path,
) -> None:
    client = _EventClient()
    commands = _ManualCommands(client, tmp_path)
    service = ManualTestService(client=client, commands=commands, temp_dir=tmp_path)
    assert service.apply_sa_settings(_manual_settings())
    qtbot.waitUntil(lambda: not service.is_running, timeout=1000)
    commands.calls.clear()

    query_started = threading.Event()
    release_query = threading.Event()

    def get_turntable_angle(_client) -> float:
        commands.calls.append(("get_turntable_angle",))
        query_started.set()
        release_query.wait(2.0)
        return 90.0

    commands.get_turntable_angle = get_turntable_angle

    assert service.run_semi_auto(speed=6)
    qtbot.waitUntil(query_started.is_set, timeout=1000)
    service.request_stop()
    release_query.set()
    qtbot.waitUntil(lambda: not service.is_running, timeout=1000)

    assert commands.calls == [("get_turntable_angle",)]
