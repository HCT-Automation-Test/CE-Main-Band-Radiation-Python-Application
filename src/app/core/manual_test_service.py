"""Manual Test 장비 작업의 비동기 수명주기 서비스."""
from __future__ import annotations

import logging
import math
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from typing import Callable

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot

from app.models.enums import AntennaPol
from app.models.manual_test import ManualMast, ManualSaSettings
from app.net import commands as default_commands
from app.report.manual_screenshot_store import (
    build_manual_screenshot_paths,
    ensure_manual_screenshot_paths_available,
    save_manual_screenshot,
)

logger = logging.getLogger(__name__)

OperationGuard = Callable[[], str | None]
MANUAL_OPERATION_IN_PROGRESS_MESSAGE = "Manual Test 작업이 진행 중입니다."
MANUAL_SERVICE_SHUTTING_DOWN_MESSAGE = "Manual Test 서비스를 종료하는 중입니다."
_SHUTDOWN_WAIT_MS = 1000
_TURNTABLE_POLL_SEC = 0.1
_DEFAULT_TURNTABLE_TIMEOUT_SEC = 300.0
_TURNTABLE_EVENT_COMMANDS = {
    "turntable_progress",
    "turntable_complete",
    "equipment_error",
}
_DETACHED_THREADS: list[QThread] = []


class _ManualStopError(RuntimeError):
    """Stop 요청 실패를 일반 취소와 구분한다."""


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
        except _ManualStopError as exc:
            logger.exception("Manual Test Stop 실패: %s", self._operation_name)
            self.failed.emit(self._operation_name, str(exc))
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
    applied_settings_changed = Signal(object)
    screenshot_saved = Signal(str)
    turntable_info_changed = Signal(object)

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        client: Any | None = None,
        commands: Any = default_commands,
        temp_dir: Path = Path("temp"),
        operation_guard: OperationGuard | None = None,
        turntable_timeout_sec: float = _DEFAULT_TURNTABLE_TIMEOUT_SEC,
    ) -> None:
        super().__init__(parent)
        self._client = client
        self._commands = commands
        self._temp_dir = Path(temp_dir)
        self._operation_guard = operation_guard
        self._turntable_timeout_sec = float(turntable_timeout_sec)
        self._thread: QThread | None = None
        self._worker: _ManualOperationWorker | None = None
        self._cancel_event: threading.Event | None = None
        self._current_operation: str | None = None
        self._capabilities = ManualTestCapabilities()
        self._applied_saturation_time_sec: float | None = None
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

    @property
    def applied_saturation_time_sec(self) -> float | None:
        """마지막으로 Set 성공한 Saturation Time을 반환한다."""

        return self._applied_saturation_time_sec

    def set_equipment_state(self, equipment_state: dict[str, bool]) -> None:
        """연결 상태만 사용해 capability를 갱신한다."""

        capabilities = manual_test_capabilities(equipment_state)
        if not capabilities.fsv40 and self._applied_saturation_time_sec is not None:
            self.invalidate_applied_settings()
        if capabilities == self._capabilities:
            return
        self._capabilities = capabilities
        self.capabilities_changed.emit(capabilities)

    def invalidate_applied_settings(self) -> None:
        """재연결/Preset 이후 이전 Set 적용값을 폐기한다."""

        self._applied_saturation_time_sec = None
        self.applied_settings_changed.emit(None)

    def apply_sa_settings(self, settings: ManualSaSettings) -> bool:
        """FSV40 설정을 적용하고 성공한 Saturation Time을 보관한다."""

        if not self._ensure_capability(
            operation="FSV40 Set",
            available=self._capabilities.fsv40,
            equipment="FSV40",
        ):
            return False

        def operation(context: ManualOperationContext) -> None:
            context.report_step("FSV40 Manual 설정 적용 중")
            ok = self._commands.setup_sa_manual(
                self._require_client(),
                start_frequency_mhz=settings.start_frequency_mhz,
                stop_frequency_mhz=settings.stop_frequency_mhz,
                rbw_mhz=settings.rbw_mhz,
                vbw_mhz=settings.vbw_mhz,
                sweep_point=settings.sweep_point,
                sweep_time_sec=settings.sweep_time_sec,
                atten_level_db=settings.atten_level_db,
                detector_mode=settings.detector_mode,
                limit_dbm=settings.limit_dbm,
            )
            self._require_true(ok, "Load SA Manual Setting")
            self._applied_saturation_time_sec = settings.saturation_time_sec
            self.applied_settings_changed.emit(settings.saturation_time_sec)

        return self.start_operation("FSV40 Set", operation)

    def preset_sa(self) -> bool:
        if not self._ensure_capability(
            operation="FSV40 Preset",
            available=self._capabilities.fsv40,
            equipment="FSV40",
        ):
            return False

        def operation(context: ManualOperationContext) -> None:
            context.report_step("FSV40 Preset 실행 중")
            self._require_true(
                self._commands.preset_sa(self._require_client()),
                "FSV40 Preset",
            )
            self._applied_saturation_time_sec = None
            self.applied_settings_changed.emit(None)

        return self.start_operation("FSV40 Preset", operation)

    def clear_trace(self) -> bool:
        if not self._ensure_capability(
            operation="Trace Clear",
            available=self._capabilities.fsv40,
            equipment="FSV40",
        ):
            return False
        return self._start_simple_command("Trace Clear", self._commands.clear_trace)

    def marker_peak(self, marker_index: int, excursion: float) -> bool:
        return self._start_marker_command(
            "Marker Peak",
            self._commands.marker_peak,
            marker_index,
            excursion,
        )

    def marker_next(self, marker_index: int, excursion: float) -> bool:
        return self._start_marker_command(
            "Marker Next",
            self._commands.marker_next,
            marker_index,
            excursion,
        )

    def marker_off(self, marker_index: int, excursion: float) -> bool:
        return self._start_marker_command(
            "Marker OFF",
            self._commands.marker_off,
            marker_index,
            excursion,
        )

    def marker_all_off(self) -> bool:
        if not self._ensure_capability(
            operation="Marker ALL OFF",
            available=self._capabilities.marker,
            equipment="FSV40",
        ):
            return False
        return self._start_simple_command(
            "Marker ALL OFF",
            self._commands.marker_all_off,
        )

    def marker_auto_max(self, marker_index: int) -> bool:
        return self._start_marker_command(
            "Marker Auto Max",
            self._commands.marker_auto_max,
            marker_index,
            0.0,
        )

    def marker_set_center(self, marker_index: int) -> bool:
        return self._start_marker_command(
            "Marker to Center",
            self._commands.marker_set_center,
            marker_index,
            0.0,
        )

    def move_turntable(self, *, angle: float, speed: int) -> bool:
        """Turntable 이동 명령을 보내고 완료 Event까지 기다린다."""

        self._validate_turntable_request(angle=angle, speed=speed)
        return self.start_operation(
            f"Turntable {angle:g}°",
            lambda context: self._rotate_and_wait(context, angle=angle, speed=speed),
        )

    def set_mast_polarization(
        self,
        *,
        mast: ManualMast,
        polarization: AntennaPol,
    ) -> bool:
        """선택 Mast와 편파를 기존 InputPath 계약으로 변환한다."""

        def operation(context: ManualOperationContext) -> None:
            context.report_step(f"{mast.value} {polarization.value} 편파 설정 중")
            ok = self._commands.set_antenna_pol(
                self._require_client(),
                pol=polarization,
                input_path=mast.input_path,
            )
            self._require_true(ok, "Change Ant Pol")

        return self.start_operation("Mast Polarization", operation)

    def run_semi_auto(self, *, speed: int) -> bool:
        """현재 각도 기준 정렬부터 반대 기준점 회전까지 순차 실행한다."""

        self._validate_turntable_request(angle=0.0, speed=speed)
        if self._applied_saturation_time_sec is None:
            self.operation_failed.emit(
                "Semi Auto",
                "먼저 FSV40 Set을 완료하세요.",
            )
            return False

        saturation_time_sec = self._applied_saturation_time_sec

        def operation(context: ManualOperationContext) -> None:
            context.report_step("Turntable 현재 각도 조회 중")
            current_angle = self._commands.get_turntable_angle(self._require_client())
            reference_angle = 0.0 if current_angle <= 180.0 else 360.0
            self._rotate_and_wait(context, angle=reference_angle, speed=6)
            if context.cancel_requested:
                return

            context.report_step("Trace Clear / Max Hold 적용 중")
            self._require_true(
                self._commands.clear_trace(self._require_client()),
                "Clear Trace",
            )
            context.report_step(f"Saturation 대기 중 ({saturation_time_sec:g}s)")
            if not context.wait(saturation_time_sec):
                return

            target_angle = 360.0 if reference_angle == 0.0 else 0.0
            self._rotate_and_wait(context, angle=target_angle, speed=speed)

        return self.start_operation("Semi Auto", operation)

    def capture_single(self, *, directory: Path, base_name: str) -> bool:
        """현재 FSV40 화면을 한 장 저장한다."""

        paths = build_manual_screenshot_paths(
            directory=directory,
            base_name=base_name,
            shot_count=1,
            numbered=False,
        )
        return self.start_operation(
            "Single Capture",
            lambda context: self._capture_sequence(context, paths=paths, interval_sec=0),
        )

    def capture_many(
        self,
        *,
        directory: Path,
        base_name: str,
        interval_sec: float,
        shot_count: int,
    ) -> bool:
        """충돌을 먼저 확인한 뒤 N장의 Screenshot을 순차 저장한다."""

        if (
            isinstance(interval_sec, bool)
            or not isinstance(interval_sec, int | float)
            or not math.isfinite(float(interval_sec))
            or interval_sec < 0
        ):
            raise ValueError("Interval은 0 이상이어야 합니다.")
        paths = build_manual_screenshot_paths(
            directory=directory,
            base_name=base_name,
            shot_count=shot_count,
            numbered=True,
        )
        return self.start_operation(
            "N-Capture",
            lambda context: self._capture_sequence(
                context,
                paths=paths,
                interval_sec=interval_sec,
            ),
        )

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

    def _start_simple_command(self, name: str, command: Callable[[Any], bool]) -> bool:
        def operation(context: ManualOperationContext) -> None:
            context.report_step(f"{name} 실행 중")
            self._require_true(command(self._require_client()), name)

        return self.start_operation(name, operation)

    def _start_marker_command(
        self,
        name: str,
        command: Callable[..., bool],
        marker_index: int,
        excursion: float,
    ) -> bool:
        if not self._ensure_capability(
            operation=name,
            available=self._capabilities.marker,
            equipment="FSV40",
        ):
            return False

        def operation(context: ManualOperationContext) -> None:
            context.report_step(f"{name} 실행 중")
            ok = command(
                self._require_client(),
                marker_index=marker_index,
                excursion=excursion,
            )
            self._require_true(ok, name)

        return self.start_operation(name, operation)

    def _capture_sequence(
        self,
        context: ManualOperationContext,
        *,
        paths: tuple[Path, ...],
        interval_sec: float,
    ) -> None:
        ensure_manual_screenshot_paths_available(paths)
        for index, destination in enumerate(paths):
            if context.cancel_requested:
                return
            if index > 0:
                context.report_step(f"Capture {index + 1}/{len(paths)} Trace Clear")
                self._require_true(
                    self._commands.clear_trace(self._require_client()),
                    "Clear Trace",
                )
                if not context.wait(interval_sec):
                    return
            context.report_step(f"Capture {index + 1}/{len(paths)} 저장 중")
            self._capture_to(context, destination)

    def _capture_to(
        self,
        context: ManualOperationContext,
        destination: Path,
    ) -> None:
        self._temp_dir.mkdir(parents=True, exist_ok=True)
        source = self._temp_dir / "screenshot.png"
        try:
            source.unlink(missing_ok=True)
        except OSError as exc:
            raise ValueError(f"stale Screenshot 제거 실패: {source}") from exc
        self._require_true(
            self._commands.get_screenshot(self._require_client()),
            "Get Screenshot",
        )
        if context.cancel_requested:
            return
        saved = save_manual_screenshot(
            source_path=source,
            destination_path=destination,
        )
        self.screenshot_saved.emit(str(saved))

    def _rotate_and_wait(
        self,
        context: ManualOperationContext,
        *,
        angle: float,
        speed: int,
    ) -> None:
        client = self._require_client()
        completed = threading.Event()
        failed_reason: list[str] = []

        def is_turntable_event(event: Any) -> bool:
            return (
                getattr(event, "target", None) == "CO3000"
                and getattr(event, "command", None) in _TURNTABLE_EVENT_COMMANDS
            )

        def handle_event(event: Any) -> None:
            if not is_turntable_event(event):
                return
            command = getattr(event, "command", None)
            params = getattr(event, "params", {}) or {}
            if command == "turntable_progress":
                current_angle = params.get("Current Angle", params.get("current_angle"))
                self.turntable_info_changed.emit(
                    {"target_angle": angle, "current_angle": current_angle, "speed": speed}
                )
            elif command == "equipment_error":
                failed_reason.append(str(params.get("message", "unknown")))
                completed.set()
            elif command == "turntable_complete":
                completed.set()

        pop_events = getattr(client, "pop_events", None)
        if callable(pop_events):
            pop_events(is_turntable_event)
        event_signal = getattr(client, "event_received", None)
        if event_signal is None:
            raise RuntimeError("Turntable Event signal is not available")
        event_signal.connect(handle_event, Qt.ConnectionType.DirectConnection)
        try:
            context.report_step(f"Turntable {angle:g}° 이동 중")
            if context.cancel_requested:
                return
            self._commands.rotate_turntable(client, angle=angle, turntable_speed=speed)
            self.turntable_info_changed.emit(
                {"target_angle": angle, "current_angle": None, "speed": speed}
            )
            deadline = time.monotonic() + self._turntable_timeout_sec
            while not completed.wait(_TURNTABLE_POLL_SEC):
                if context.cancel_requested:
                    self._stop_turntable(client)
                    return
                if time.monotonic() >= deadline:
                    self._stop_turntable(client)
                    raise TimeoutError("Turntable 회전 타임아웃")
            if failed_reason:
                raise RuntimeError(f"Turntable 회전 실패: {failed_reason[-1]}")
            self.turntable_info_changed.emit(
                {"target_angle": angle, "current_angle": angle, "speed": speed}
            )
        finally:
            _disconnect_safely(event_signal, handle_event)

    def _stop_turntable(self, client: Any) -> None:
        try:
            self._commands.stop_turntable(client)
        except Exception as exc:
            raise _ManualStopError(f"Turntable 정지 실패: {exc}") from exc

    def _require_client(self) -> Any:
        if self._client is None:
            raise RuntimeError("Manual Test client is not configured")
        return self._client

    def _ensure_capability(
        self,
        *,
        operation: str,
        available: bool,
        equipment: str,
    ) -> bool:
        """필요 장비가 없으면 worker 생성 전에 operation을 거부한다."""

        if available:
            return True
        self.operation_failed.emit(operation, f"{equipment} 연결이 필요합니다.")
        return False

    @staticmethod
    def _validate_turntable_request(*, angle: float, speed: int) -> None:
        if angle not in (0, 0.0, 360, 360.0):
            raise ValueError("Turntable 목표 각도는 0° 또는 360°여야 합니다.")
        if isinstance(speed, bool) or not isinstance(speed, int) or speed <= 0:
            raise ValueError("Turntable Speed는 0보다 큰 정수여야 합니다.")

    @staticmethod
    def _require_true(result: object, command_name: str) -> None:
        if not bool(result):
            raise RuntimeError(f"{command_name} returned false")

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
