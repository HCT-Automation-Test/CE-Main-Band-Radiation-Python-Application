"""Manual Test 장비 작업의 비동기 수명주기 서비스."""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot

logger = logging.getLogger(__name__)

OperationGuard = Callable[[], str | None]
MANUAL_OPERATION_IN_PROGRESS_MESSAGE = "Manual Test 작업이 진행 중입니다."
MANUAL_SERVICE_SHUTTING_DOWN_MESSAGE = "Manual Test 서비스를 종료하는 중입니다."
_SHUTDOWN_WAIT_MS = 1000
_DETACHED_THREADS: list[QThread] = []


@dataclass(frozen=True)
class ManualTestCapabilities:
    """장비 연결 상태로만 계산하는 Manual Test 기능 집합."""

    fsv40: bool = False
    marker: bool = False
    capture: bool = False
    turntable: bool = False
    mast_1m: bool = False
    mast_3m: bool = False
    semi_auto: bool = False


def manual_test_capabilities(
    equipment_state: dict[str, bool],
) -> ManualTestCapabilities:
    """장비별 연결 상태에서 Manual Test capability를 계산한다."""

    fsv40 = equipment_state.get("FSV40") is True
    co3000 = equipment_state.get("CO3000") is True
    controller_3d = equipment_state.get("3D Controller") is True
    return ManualTestCapabilities(
        fsv40=fsv40,
        marker=fsv40,
        capture=fsv40,
        turntable=co3000,
        mast_1m=controller_3d,
        mast_3m=co3000,
        semi_auto=fsv40 and co3000,
    )


class ManualOperationContext:
    """Manual operation callback에 제공하는 최소 취소/진행 API."""

    def __init__(
        self,
        cancel_event: threading.Event,
        step_reporter: Callable[[str], None],
    ) -> None:
        self._cancel_event = cancel_event
        self._step_reporter = step_reporter

    @property
    def cancel_requested(self) -> bool:
        return self._cancel_event.is_set()

    def report_step(self, message: str) -> None:
        """현재 operation 단계를 UI에 전달한다."""

        self._step_reporter(message)

    def wait(self, timeout_s: float) -> bool:
        """취소에 반응하며 대기하고 정상 대기 완료 여부를 반환한다."""

        return not self._cancel_event.wait(max(0.0, timeout_s))


ManualOperation = Callable[[ManualOperationContext], None]


def _disconnect_safely(signal: Signal, slot: object) -> None:
    try:
        signal.disconnect(slot)
    except (RuntimeError, TypeError):
        pass


def _forget_detached_thread(thread: QThread) -> None:
    if thread in _DETACHED_THREADS:
        _DETACHED_THREADS.remove(thread)
    thread.deleteLater()


class _ManualOperationWorker(QObject):
    started = Signal(str)
    step_changed = Signal(str)
    finished = Signal(str)
    failed = Signal(str, str)
    cancelled = Signal(str)
    done = Signal()

    def __init__(
        self,
        *,
        operation_name: str,
        operation: ManualOperation,
        cancel_event: threading.Event,
    ) -> None:
        super().__init__()
        self._operation_name = operation_name
        self._operation = operation
        self._cancel_event = cancel_event

    @Slot()
    def run(self) -> None:
        try:
            self.started.emit(self._operation_name)
            if self._cancel_event.is_set():
                self.cancelled.emit(self._operation_name)
                return

            context = ManualOperationContext(
                self._cancel_event,
                self.step_changed.emit,
            )
            self._operation(context)
            if self._cancel_event.is_set():
                self.cancelled.emit(self._operation_name)
            else:
                self.finished.emit(self._operation_name)
        except Exception as exc:
            if self._cancel_event.is_set():
                self.cancelled.emit(self._operation_name)
            else:
                logger.exception("Manual Test 작업 실패: %s", self._operation_name)
                self.failed.emit(self._operation_name, str(exc))
        finally:
            self.done.emit()


class ManualTestService(QObject):
    """Manual 장비 operation을 하나씩 비동기로 실행한다."""

    operation_started = Signal(str)
    step_changed = Signal(str)
    operation_finished = Signal(str)
    operation_failed = Signal(str, str)
    operation_cancelled = Signal(str)
    running_changed = Signal(bool)
    capabilities_changed = Signal(object)

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        operation_guard: OperationGuard | None = None,
    ) -> None:
        super().__init__(parent)
        self._operation_guard = operation_guard
        self._thread: QThread | None = None
        self._worker: _ManualOperationWorker | None = None
        self._cancel_event: threading.Event | None = None
        self._current_operation: str | None = None
        self._capabilities = ManualTestCapabilities()
        self._shutting_down = False

    @property
    def is_running(self) -> bool:
        return self._thread is not None

    @property
    def current_operation(self) -> str | None:
        return self._current_operation

    @property
    def cancel_requested(self) -> bool:
        return self._cancel_event is not None and self._cancel_event.is_set()

    @property
    def capabilities(self) -> ManualTestCapabilities:
        return self._capabilities

    def set_equipment_state(self, equipment_state: dict[str, bool]) -> None:
        """연결 상태만 사용해 capability를 갱신한다."""

        capabilities = manual_test_capabilities(equipment_state)
        if capabilities == self._capabilities:
            return
        self._capabilities = capabilities
        self.capabilities_changed.emit(capabilities)

    def start_operation(
        self,
        name: str,
        operation: ManualOperation,
    ) -> bool:
        """operation을 즉시 선점하고 worker thread에서 시작한다."""

        if self._shutting_down:
            self.operation_failed.emit(name, MANUAL_SERVICE_SHUTTING_DOWN_MESSAGE)
            return False
        if self._thread is not None:
            self.operation_failed.emit(name, MANUAL_OPERATION_IN_PROGRESS_MESSAGE)
            return False
        if self._operation_guard is not None:
            block_reason = self._operation_guard()
            if block_reason:
                self.operation_failed.emit(name, block_reason)
                return False

        cancel_event = threading.Event()
        thread = QThread(self)
        worker = _ManualOperationWorker(
            operation_name=name,
            operation=operation,
            cancel_event=cancel_event,
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.started.connect(self._on_operation_started)
        worker.step_changed.connect(self._on_step_changed)
        worker.finished.connect(self._on_operation_finished)
        worker.failed.connect(self._on_operation_failed)
        worker.cancelled.connect(self._on_operation_cancelled)
        worker.done.connect(thread.quit, Qt.ConnectionType.DirectConnection)
        worker.done.connect(worker.deleteLater)
        thread.finished.connect(self._on_thread_finished)
        thread.finished.connect(thread.deleteLater)

        self._thread = thread
        self._worker = worker
        self._cancel_event = cancel_event
        self._current_operation = name
        self.running_changed.emit(True)
        thread.start()
        return True

    def request_stop(self) -> None:
        """현재 operation이 다음 단계로 진행하지 않도록 취소를 요청한다."""

        if self._cancel_event is not None:
            self._cancel_event.set()

    def shutdown(self) -> None:
        """신규 작업을 막고 실행 중 worker를 유한 시간 동안 정리한다."""

        if self._shutting_down:
            return
        self._shutting_down = True
        self.request_stop()

        thread = self._thread
        if thread is None:
            return

        _disconnect_safely(thread.finished, self._on_thread_finished)
        _disconnect_safely(thread.finished, thread.deleteLater)
        thread.quit()
        if not thread.wait(_SHUTDOWN_WAIT_MS):
            logger.error("Manual Test worker thread did not stop cleanly")
            thread.setParent(None)
            _DETACHED_THREADS.append(thread)
            thread.finished.connect(
                lambda thread=thread: _forget_detached_thread(thread),
            )
        else:
            thread.deleteLater()
        self._clear_running_state()

    @Slot()
    def _on_thread_finished(self) -> None:
        thread = self.sender()
        if thread is not self._thread:
            return
        self._clear_running_state()

    @Slot(str)
    def _on_operation_started(self, operation_name: str) -> None:
        if not self._shutting_down:
            self.operation_started.emit(operation_name)

    @Slot(str)
    def _on_step_changed(self, message: str) -> None:
        if not self._shutting_down:
            self.step_changed.emit(message)

    @Slot(str)
    def _on_operation_finished(self, operation_name: str) -> None:
        if not self._shutting_down:
            self.operation_finished.emit(operation_name)

    @Slot(str, str)
    def _on_operation_failed(self, operation_name: str, message: str) -> None:
        if not self._shutting_down:
            self.operation_failed.emit(operation_name, message)

    @Slot(str)
    def _on_operation_cancelled(self, operation_name: str) -> None:
        if not self._shutting_down:
            self.operation_cancelled.emit(operation_name)

    def _clear_running_state(self) -> None:
        was_running = self._thread is not None
        self._thread = None
        self._worker = None
        self._cancel_event = None
        self._current_operation = None
        if was_running:
            self.running_changed.emit(False)
