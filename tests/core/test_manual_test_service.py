from __future__ import annotations

import threading

import pytest

from app.core.manual_test_service import (
    MANUAL_OPERATION_IN_PROGRESS_MESSAGE,
    ManualTestCapabilities,
    ManualTestService,
    _DETACHED_THREADS,
    manual_test_capabilities,
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
