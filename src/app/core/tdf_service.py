"""TDF command 비동기 실행 서비스."""
from __future__ import annotations

import logging
import threading
from typing import Any, Callable, Literal

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot

from app.net import commands as default_commands

logger = logging.getLogger(__name__)

TdfOperation = Literal["get_list", "all_off", "set_tdf"]
OperationGuard = Callable[[], str | None]
TDF_OPERATION_IN_PROGRESS_MESSAGE = "TDF 작업이 이미 진행 중입니다."
_DETACHED_THREADS: list[QThread] = []


def _disconnect_safely(signal: Any, slot: Any) -> None:
    try:
        signal.disconnect(slot)
    except (RuntimeError, TypeError):
        pass


def _forget_detached_thread(thread: QThread) -> None:
    if thread in _DETACHED_THREADS:
        _DETACHED_THREADS.remove(thread)


def _delete_detached_thread(thread: QThread) -> None:
    _forget_detached_thread(thread)
    thread.deleteLater()


class _TdfWorker(QObject):
    """TDF TCP command를 UI thread 밖에서 실행한다."""

    started = Signal()
    list_received = Signal(list)
    finished = Signal(str)
    failed = Signal(str)
    done = Signal()

    def __init__(
        self,
        *,
        client: Any,
        commands: Any,
        operation: TdfOperation,
        tdf_file_name: str = "",
    ) -> None:
        super().__init__()
        self._client = client
        self._commands = commands
        self._operation = operation
        self._tdf_file_name = tdf_file_name
        self._lock = threading.Lock()
        self._cancel_requested = False

    def cancel(self) -> None:
        """실행 중인 TDF 작업에 취소를 요청한다."""

        with self._lock:
            self._cancel_requested = True

    @Slot()
    def run(self) -> None:
        try:
            self.started.emit()
            if self._is_cancel_requested():
                return

            if self._operation == "get_list":
                tdf_file_list = self._commands.get_tdf_list(self._client)
                if self._is_cancel_requested():
                    return
                self.list_received.emit(list(tdf_file_list))
                self.finished.emit("TDF 파일 목록을 가져왔습니다.")
                return

            if self._operation == "all_off":
                self._commands.tdf_all_off(self._client)
                if self._is_cancel_requested():
                    return
                self.finished.emit("모든 TDF를 비활성화했습니다.")
                return

            if self._operation == "set_tdf":
                self._commands.set_tdf(
                    self._client,
                    tdf_file_name=self._tdf_file_name,
                )
                if self._is_cancel_requested():
                    return
                self.finished.emit(f"TDF를 활성화했습니다: {self._tdf_file_name}")
                return

            self.failed.emit(f"지원하지 않는 TDF 작업입니다: {self._operation}")
        except Exception as exc:
            if self._is_cancel_requested():
                return
            logger.exception("TDF 작업 실패")
            self.failed.emit(str(exc))
        finally:
            self.done.emit()

    def _is_cancel_requested(self) -> bool:
        with self._lock:
            return self._cancel_requested


class TdfService(QObject):
    """Test Manager TDF 버튼에서 사용하는 비동기 서비스."""

    operation_started = Signal()
    tdf_list_received = Signal(list)
    operation_finished = Signal(str)
    operation_failed = Signal(str)

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        client: Any,
        commands: Any = default_commands,
        operation_guard: OperationGuard | None = None,
    ) -> None:
        super().__init__(parent)
        self._client = client
        self._commands = commands
        self._operation_guard = operation_guard
        self._thread: QThread | None = None
        self._worker: _TdfWorker | None = None
        self._shutting_down = False

    @property
    def is_running(self) -> bool:
        """TDF worker 실행 여부."""

        return self._thread is not None

    def get_tdf_list(self) -> None:
        """TDF 파일 목록 조회를 시작한다."""

        self._start_operation("get_list")

    def tdf_all_off(self) -> None:
        """모든 TDF 비활성화를 시작한다."""

        self._start_operation("all_off")

    def set_tdf(self, tdf_file_name: str) -> None:
        """선택한 TDF 활성화를 시작한다."""

        self._start_operation("set_tdf", tdf_file_name=tdf_file_name)

    def shutdown(self) -> None:
        """실행 중인 worker thread를 정리한다."""

        if self._shutting_down:
            return
        self._shutting_down = True

        if self._worker is not None:
            self._worker.cancel()
        if self._thread is not None:
            thread = self._thread
            _disconnect_safely(thread.finished, self._on_thread_finished)
            _disconnect_safely(thread.finished, thread.deleteLater)
            thread.quit()
            if not thread.wait(1000):
                logger.error("TDF worker thread did not stop cleanly")
                self._detach_running_thread(thread)
            else:
                thread.deleteLater()
        self._thread = None
        self._worker = None

    def _start_operation(
        self,
        operation: TdfOperation,
        *,
        tdf_file_name: str = "",
    ) -> None:
        if self._shutting_down:
            return
        if self._thread is not None:
            self.operation_failed.emit(TDF_OPERATION_IN_PROGRESS_MESSAGE)
            return
        if self._operation_guard is not None:
            block_reason = self._operation_guard()
            if block_reason:
                self.operation_failed.emit(block_reason)
                return

        thread = QThread(self)
        worker = _TdfWorker(
            client=self._client,
            commands=self._commands,
            operation=operation,
            tdf_file_name=tdf_file_name,
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.started.connect(self._on_operation_started)
        worker.list_received.connect(self._on_tdf_list_received)
        worker.finished.connect(self._on_operation_finished)
        worker.failed.connect(self._on_operation_failed)
        worker.done.connect(thread.quit, Qt.ConnectionType.DirectConnection)
        worker.done.connect(self._on_worker_done, Qt.ConnectionType.DirectConnection)
        worker.done.connect(worker.deleteLater)
        thread.finished.connect(self._on_thread_finished)
        thread.finished.connect(thread.deleteLater)
        self._thread = thread
        self._worker = worker
        thread.start()

    @Slot()
    def _on_operation_started(self) -> None:
        if not self._shutting_down:
            self.operation_started.emit()

    @Slot(list)
    def _on_tdf_list_received(self, tdf_file_list: list[str]) -> None:
        if not self._shutting_down:
            self.tdf_list_received.emit(tdf_file_list)

    @Slot(str)
    def _on_operation_finished(self, message: str) -> None:
        if not self._shutting_down:
            self.operation_finished.emit(message)

    @Slot(str)
    def _on_operation_failed(self, message: str) -> None:
        if not self._shutting_down:
            self.operation_failed.emit(message)

    def _on_thread_finished(self) -> None:
        self._thread = None

    def _on_worker_done(self) -> None:
        self._worker = None

    def _detach_running_thread(self, thread: QThread) -> None:
        thread.setParent(None)
        _DETACHED_THREADS.append(thread)
        thread.finished.connect(
            lambda thread=thread: _delete_detached_thread(thread),
        )
