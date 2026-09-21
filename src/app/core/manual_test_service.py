"""Manual Test 장비 작업의 timer/event 기반 수명주기 서비스."""
from __future__ import annotations

import logging
import math
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QObject, QTimer, Qt, Signal, Slot

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
FSV40_NOT_CONNECTED_MESSAGE = "FSV40이 연결되어 있지 않습니다."
_DEFAULT_TURNTABLE_TIMEOUT_SEC = 300.0
_MAX_QT_TIMER_INTERVAL_MS = 2_147_483_647
_TURNTABLE_EVENT_COMMANDS = {
    "turntable_progress",
    "turntable_complete",
    "equipment_error",
}


class _ManualStopError(RuntimeError):
    """Stop 요청 실패를 일반 취소와 구분한다."""


class _OperationKind(Enum):
    SA_SET = auto()
    SA_PRESET = auto()
    SIMPLE = auto()
    MARKER = auto()
    MOVE = auto()
    MAST = auto()
    SEMI_AUTO = auto()
    CAPTURE = auto()


class _OperationPhase(Enum):
    IDLE = auto()
    STEP_PENDING = auto()
    WAIT_DELAY = auto()
    WAIT_TURNTABLE = auto()


class _OperationStep(Enum):
    APPLY_SA = auto()
    PRESET_SA = auto()
    SIMPLE_COMMAND = auto()
    MARKER_COMMAND = auto()
    SET_MAST = auto()
    START_MOVE = auto()
    SEMI_QUERY_ANGLE = auto()
    SEMI_ALIGN = auto()
    SEMI_CLEAR_TRACE = auto()
    SEMI_FINAL_MOVE = auto()
    CAPTURE_SHOT = auto()
    FINISH = auto()


@dataclass
class _OperationState:
    name: str
    kind: _OperationKind
    phase: _OperationPhase
    step: _OperationStep
    generation: int
    data: dict[str, Any] = field(default_factory=dict)
    after_rotation: _OperationStep | None = None
    rotation_target: float | None = None
    rotation_speed: int | None = None


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


def _disconnect_safely(signal: Signal, slot: object) -> None:
    try:
        signal.disconnect(slot)
    except (RuntimeError, TypeError):
        pass


class ManualTestService(QObject):
    """Manual 장비 operation을 하나씩 timer/event 단계로 실행한다."""

    operation_started = Signal(str)
    step_changed = Signal(str)
    operation_finished = Signal(str)
    operation_failed = Signal(str, str)
    operation_cancelled = Signal(str)
    running_changed = Signal(bool)
    capabilities_changed = Signal(object)
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
        self._state: _OperationState | None = None
        self._generation = 0
        self._cancel_requested = False
        self._step_deadline: float | None = None
        self._turntable_deadline: float | None = None
        self._capabilities = ManualTestCapabilities()
        self._shutting_down = False
        self._handled_event_ids: deque[str] = deque(maxlen=1000)
        self._handled_event_objects: deque[Any] = deque(maxlen=1000)

        self._step_timer = QTimer(self)
        self._step_timer.setSingleShot(True)
        self._step_timer.timeout.connect(self._on_step_timer)
        self._turntable_timeout_timer = QTimer(self)
        self._turntable_timeout_timer.setSingleShot(True)
        self._turntable_timeout_timer.timeout.connect(self._on_turntable_timeout)

        self._event_signal: Signal | None = None
        event_signal = getattr(client, "event_received", None)
        if event_signal is not None:
            event_signal.connect(
                self._on_client_event,
                Qt.ConnectionType.QueuedConnection,
            )
            self._event_signal = event_signal

    @property
    def is_running(self) -> bool:
        return self._state is not None

    @property
    def current_operation(self) -> str | None:
        return self._state.name if self._state is not None else None

    @property
    def cancel_requested(self) -> bool:
        return self._cancel_requested

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

    def apply_sa_settings(self, settings: ManualSaSettings) -> bool:
        if not self._require_capability(
            "FSV40 Set",
            available=self._capabilities.fsv40,
            message=FSV40_NOT_CONNECTED_MESSAGE,
        ):
            return False
        return self._begin_operation(
            "FSV40 Set",
            _OperationKind.SA_SET,
            _OperationStep.APPLY_SA,
            {"settings": settings},
        )

    def preset_sa(self) -> bool:
        if not self._require_capability(
            "FSV40 Preset",
            available=self._capabilities.fsv40,
            message=FSV40_NOT_CONNECTED_MESSAGE,
        ):
            return False
        return self._begin_operation(
            "FSV40 Preset",
            _OperationKind.SA_PRESET,
            _OperationStep.PRESET_SA,
        )

    def clear_trace(self) -> bool:
        if not self._require_capability(
            "Trace Clear",
            available=self._capabilities.fsv40,
            message=FSV40_NOT_CONNECTED_MESSAGE,
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
        return self._start_simple_command(
            "Marker ALL OFF",
            self._commands.marker_all_off,
        )

    def marker_auto_max(self, marker_index: int, excursion: float) -> bool:
        return self._start_marker_command(
            "Marker Auto Max",
            self._commands.marker_auto_max,
            marker_index,
            excursion,
        )

    def marker_set_center(self, marker_index: int, excursion: float) -> bool:
        return self._start_marker_command(
            "Marker to Center",
            self._commands.marker_set_center,
            marker_index,
            excursion,
        )

    def move_turntable(self, *, angle: float, speed: int) -> bool:
        self._validate_turntable_request(angle=angle, speed=speed)
        return self._begin_operation(
            f"Turntable {angle:g}°",
            _OperationKind.MOVE,
            _OperationStep.START_MOVE,
            {"angle": angle, "speed": speed},
        )

    def set_mast_polarization(
        self,
        *,
        mast: ManualMast,
        polarization: AntennaPol,
    ) -> bool:
        return self._begin_operation(
            "Mast Polarization",
            _OperationKind.MAST,
            _OperationStep.SET_MAST,
            {"mast": mast, "polarization": polarization},
        )

    def run_semi_auto(self, *, speed: int, saturation_time_sec: float) -> bool:
        self._validate_turntable_request(angle=0.0, speed=speed)
        self._validate_nonnegative_delay(
            saturation_time_sec,
            field_name="Saturation Time",
        )
        return self._begin_operation(
            "Semi Auto",
            _OperationKind.SEMI_AUTO,
            _OperationStep.SEMI_QUERY_ANGLE,
            {
                "speed": speed,
                "saturation_time_sec": float(saturation_time_sec),
            },
        )

    def capture_single(self, *, directory: Path, base_name: str) -> bool:
        paths = build_manual_screenshot_paths(
            directory=directory,
            base_name=base_name,
            shot_count=1,
            numbered=False,
        )
        return self._start_capture("Single Capture", paths=paths, interval_sec=0)

    def capture_many(
        self,
        *,
        directory: Path,
        base_name: str,
        interval_sec: float,
        shot_count: int,
    ) -> bool:
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
        return self._start_capture(
            "N-Capture",
            paths=paths,
            interval_sec=float(interval_sec),
        )

    def request_stop(self) -> None:
        """현재 operation을 취소하고 회전 중이면 Stop command를 보낸다."""

        state = self._state
        if state is None:
            return
        self._cancel_requested = True
        self._step_timer.stop()
        self._step_deadline = None
        if state.phase is _OperationPhase.WAIT_TURNTABLE:
            try:
                self._stop_turntable(self._require_client())
            except Exception as exc:
                self._terminate(state, "failed", exc)
                return
        self._terminate(state, "cancelled")

    def _begin_operation(
        self,
        name: str,
        kind: _OperationKind,
        first_step: _OperationStep,
        data: dict[str, Any] | None = None,
    ) -> bool:
        if self._shutting_down:
            self.operation_failed.emit(name, MANUAL_SERVICE_SHUTTING_DOWN_MESSAGE)
            return False
        if self._state is not None:
            self.operation_failed.emit(name, MANUAL_OPERATION_IN_PROGRESS_MESSAGE)
            return False
        if self._operation_guard is not None:
            block_reason = self._operation_guard()
            if block_reason:
                self.operation_failed.emit(name, block_reason)
                return False

        self._generation += 1
        state = _OperationState(
            name=name,
            kind=kind,
            phase=_OperationPhase.STEP_PENDING,
            step=first_step,
            generation=self._generation,
            data=dict(data or {}),
        )
        self._state = state
        self._cancel_requested = False
        self.running_changed.emit(True)
        self.operation_started.emit(name)
        self._schedule_step(state, first_step)
        return True

    def _start_simple_command(self, name: str, command: Callable[[Any], bool]) -> bool:
        return self._begin_operation(
            name,
            _OperationKind.SIMPLE,
            _OperationStep.SIMPLE_COMMAND,
            {"command": command},
        )

    def _start_marker_command(
        self,
        name: str,
        command: Callable[..., bool],
        marker_index: int,
        excursion: float,
    ) -> bool:
        return self._begin_operation(
            name,
            _OperationKind.MARKER,
            _OperationStep.MARKER_COMMAND,
            {
                "command": command,
                "marker_index": marker_index,
                "excursion": excursion,
            },
        )

    def _start_capture(
        self,
        name: str,
        *,
        paths: tuple[Path, ...],
        interval_sec: float,
    ) -> bool:
        return self._begin_operation(
            name,
            _OperationKind.CAPTURE,
            _OperationStep.CAPTURE_SHOT,
            {
                "paths": paths,
                "interval_sec": interval_sec,
                "capture_index": 0,
                "preflight_complete": False,
            },
        )

    def _schedule_step(
        self,
        state: _OperationState,
        step: _OperationStep,
        *,
        delay_sec: float = 0.0,
    ) -> None:
        if not self._is_active(state):
            return
        state.step = step
        delay_sec = max(0.0, float(delay_sec))
        self._step_deadline = time.monotonic() + delay_sec
        state.phase = (
            _OperationPhase.WAIT_DELAY
            if delay_sec > 0
            else _OperationPhase.STEP_PENDING
        )
        self._start_step_timer()

    def _start_step_timer(self) -> None:
        if self._step_deadline is None:
            return
        remaining = max(0.0, self._step_deadline - time.monotonic())
        self._step_timer.start(
            min(math.ceil(remaining * 1000), _MAX_QT_TIMER_INTERVAL_MS)
        )

    @Slot()
    def _on_step_timer(self) -> None:
        state = self._state
        if state is None or self._shutting_down or self._cancel_requested:
            return
        if self._step_deadline is not None and time.monotonic() < self._step_deadline:
            self._start_step_timer()
            return
        self._step_deadline = None
        state.phase = _OperationPhase.STEP_PENDING
        try:
            self._execute_step(state)
        except Exception as exc:
            if self._is_active(state):
                self._terminate(state, "failed", exc)

    def _execute_step(self, state: _OperationState) -> None:
        if not self._is_active(state):
            return
        step = state.step
        if step is _OperationStep.APPLY_SA:
            self._execute_apply_sa(state)
        elif step is _OperationStep.PRESET_SA:
            self._execute_preset_sa(state)
        elif step is _OperationStep.SIMPLE_COMMAND:
            self._execute_simple_command(state)
        elif step is _OperationStep.MARKER_COMMAND:
            self._execute_marker_command(state)
        elif step is _OperationStep.SET_MAST:
            self._execute_set_mast(state)
        elif step is _OperationStep.START_MOVE:
            self._start_rotation(
                state,
                angle=float(state.data["angle"]),
                speed=int(state.data["speed"]),
                after_rotation=_OperationStep.FINISH,
            )
        elif step is _OperationStep.SEMI_QUERY_ANGLE:
            self._execute_semi_query(state)
        elif step is _OperationStep.SEMI_ALIGN:
            self._execute_semi_align(state)
        elif step is _OperationStep.SEMI_CLEAR_TRACE:
            self._execute_semi_clear(state)
        elif step is _OperationStep.SEMI_FINAL_MOVE:
            self._execute_semi_final_move(state)
        elif step is _OperationStep.CAPTURE_SHOT:
            self._execute_capture_shot(state)
        elif step is _OperationStep.FINISH:
            self._terminate(state, "finished")
        else:
            raise RuntimeError(f"Unknown Manual Test step: {step}")

    def _execute_apply_sa(self, state: _OperationState) -> None:
        settings = state.data["settings"]
        self.step_changed.emit("FSV40 Manual 설정 적용 중")
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
        if not self._is_active(state):
            return
        self._terminate(state, "finished")

    def _execute_preset_sa(self, state: _OperationState) -> None:
        self.step_changed.emit("FSV40 Preset 실행 중")
        self._require_true(
            self._commands.preset_sa(self._require_client()),
            "FSV40 Preset",
        )
        if not self._is_active(state):
            return
        self._terminate(state, "finished")

    def _execute_simple_command(self, state: _OperationState) -> None:
        self.step_changed.emit(f"{state.name} 실행 중")
        self._require_true(
            state.data["command"](self._require_client()),
            state.name,
        )
        if self._is_active(state):
            self._terminate(state, "finished")

    def _execute_marker_command(self, state: _OperationState) -> None:
        self.step_changed.emit(f"{state.name} 실행 중")
        ok = state.data["command"](
            self._require_client(),
            marker_index=state.data["marker_index"],
            excursion=state.data["excursion"],
        )
        self._require_true(ok, state.name)
        if self._is_active(state):
            self._terminate(state, "finished")

    def _execute_set_mast(self, state: _OperationState) -> None:
        mast = state.data["mast"]
        polarization = state.data["polarization"]
        self.step_changed.emit(f"{mast.value} {polarization.value} 편파 설정 중")
        ok = self._commands.set_antenna_pol(
            self._require_client(),
            pol=polarization,
            input_path=mast.input_path,
        )
        self._require_true(ok, "Change Ant Pol")
        if self._is_active(state):
            self._terminate(state, "finished")

    def _execute_semi_query(self, state: _OperationState) -> None:
        self.step_changed.emit("Turntable 현재 각도 조회 중")
        current_angle = self._commands.get_turntable_angle(self._require_client())
        if not self._is_active(state):
            return
        reference_angle = 0.0 if current_angle <= 180.0 else 360.0
        state.data["reference_angle"] = reference_angle
        state.data["target_angle"] = 360.0 if reference_angle == 0.0 else 0.0
        self._schedule_step(state, _OperationStep.SEMI_ALIGN)

    def _execute_semi_align(self, state: _OperationState) -> None:
        self._start_rotation(
            state,
            angle=float(state.data["reference_angle"]),
            speed=6,
            after_rotation=_OperationStep.SEMI_CLEAR_TRACE,
        )

    def _execute_semi_clear(self, state: _OperationState) -> None:
        self.step_changed.emit("Trace Clear / Max Hold 적용 중")
        self._require_true(
            self._commands.clear_trace(self._require_client()),
            "Clear Trace",
        )
        if not self._is_active(state):
            return
        saturation_time_sec = float(state.data["saturation_time_sec"])
        self.step_changed.emit(f"Saturation 대기 중 ({saturation_time_sec:g}s)")
        self._schedule_step(
            state,
            _OperationStep.SEMI_FINAL_MOVE,
            delay_sec=saturation_time_sec,
        )

    def _execute_semi_final_move(self, state: _OperationState) -> None:
        self._start_rotation(
            state,
            angle=float(state.data["target_angle"]),
            speed=int(state.data["speed"]),
            after_rotation=_OperationStep.FINISH,
        )

    def _execute_capture_shot(self, state: _OperationState) -> None:
        paths: tuple[Path, ...] = state.data["paths"]
        if not state.data["preflight_complete"]:
            ensure_manual_screenshot_paths_available(paths)
            state.data["preflight_complete"] = True

        index = int(state.data["capture_index"])
        self.step_changed.emit(f"Capture {index + 1}/{len(paths)} 저장 중")
        self._capture_to(paths[index])
        if not self._is_active(state):
            return
        next_index = index + 1
        if next_index >= len(paths):
            self._terminate(state, "finished")
            return

        self.step_changed.emit(f"Capture {next_index + 1}/{len(paths)} Trace Clear")
        self._require_true(
            self._commands.clear_trace(self._require_client()),
            "Clear Trace",
        )
        if not self._is_active(state):
            return
        state.data["capture_index"] = next_index
        self._schedule_step(
            state,
            _OperationStep.CAPTURE_SHOT,
            delay_sec=float(state.data["interval_sec"]),
        )

    def _capture_to(self, destination: Path) -> None:
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
        saved = save_manual_screenshot(
            source_path=source,
            destination_path=destination,
        )
        self.screenshot_saved.emit(str(saved))

    def _start_rotation(
        self,
        state: _OperationState,
        *,
        angle: float,
        speed: int,
        after_rotation: _OperationStep,
    ) -> None:
        if not self._is_active(state):
            return
        client = self._require_client()
        self._discard_buffered_turntable_events(client)
        state.phase = _OperationPhase.WAIT_TURNTABLE
        state.rotation_target = angle
        state.rotation_speed = speed
        state.after_rotation = after_rotation
        self.step_changed.emit(f"Turntable {angle:g}° 이동 중")
        try:
            self._commands.rotate_turntable(
                client,
                angle=angle,
                turntable_speed=speed,
            )
        except Exception as exc:
            stop_error = self._try_stop_turntable(client)
            if stop_error is not None:
                raise RuntimeError(
                    f"{exc}; Turntable 정지 실패: {stop_error}"
                ) from exc
            raise
        if not self._is_active(state):
            return
        self.turntable_info_changed.emit(
            {"target_angle": angle, "current_angle": None, "speed": speed}
        )
        self._turntable_deadline = time.monotonic() + max(
            0.0,
            self._turntable_timeout_sec,
        )
        self._start_turntable_timeout_timer()
        self._drain_buffered_turntable_events(client)

    def _start_turntable_timeout_timer(self) -> None:
        if self._turntable_deadline is None:
            return
        remaining = max(0.0, self._turntable_deadline - time.monotonic())
        self._turntable_timeout_timer.start(
            min(math.ceil(remaining * 1000), _MAX_QT_TIMER_INTERVAL_MS)
        )

    @Slot(object)
    def _on_client_event(self, event: Any) -> None:
        if not self._is_turntable_event(event):
            return
        if not self._mark_event_handled(event):
            return
        state = self._state
        if state is None or state.phase is not _OperationPhase.WAIT_TURNTABLE:
            return

        command = getattr(event, "command", None)
        params = getattr(event, "params", {}) or {}
        if command == "turntable_progress":
            current_angle = params.get("Current Angle", params.get("current_angle"))
            self.turntable_info_changed.emit(
                {
                    "target_angle": state.rotation_target,
                    "current_angle": current_angle,
                    "speed": state.rotation_speed,
                }
            )
            return
        if command == "equipment_error":
            reason = str(params.get("message", "unknown"))
            stop_error = self._try_stop_turntable(self._require_client())
            message = f"Turntable 회전 실패: {reason}"
            if stop_error is not None:
                message = f"{message}; Turntable 정지 실패: {stop_error}"
            self._terminate(state, "failed", RuntimeError(message))
            return
        if command != "turntable_complete":
            return

        angle = state.rotation_target
        speed = state.rotation_speed
        next_step = state.after_rotation
        self._clear_rotation_wait(state)
        self.turntable_info_changed.emit(
            {"target_angle": angle, "current_angle": angle, "speed": speed}
        )
        if next_step is None:
            self._terminate(state, "failed", RuntimeError("회전 후속 단계가 없습니다."))
            return
        self._schedule_step(state, next_step)

    @Slot()
    def _on_turntable_timeout(self) -> None:
        state = self._state
        if state is None or state.phase is not _OperationPhase.WAIT_TURNTABLE:
            return
        if (
            self._turntable_deadline is not None
            and time.monotonic() < self._turntable_deadline
        ):
            self._start_turntable_timeout_timer()
            return
        stop_error = self._try_stop_turntable(self._require_client())
        if stop_error is not None:
            self._terminate(
                state,
                "failed",
                _ManualStopError(f"Turntable 정지 실패: {stop_error}"),
            )
            return
        self._terminate(state, "failed", TimeoutError("Turntable 회전 타임아웃"))

    @staticmethod
    def _is_turntable_event(event: Any) -> bool:
        return (
            getattr(event, "target", None) == "CO3000"
            and getattr(event, "command", None) in _TURNTABLE_EVENT_COMMANDS
        )

    def _pop_buffered_turntable_events(self, client: Any) -> list[Any]:
        pop_events = getattr(client, "pop_events", None)
        if not callable(pop_events):
            return []
        try:
            return list(pop_events(self._is_turntable_event))
        except Exception as exc:
            logger.warning("TCP turntable event buffer read failed: %s", exc)
            return []

    def _discard_buffered_turntable_events(self, client: Any) -> None:
        for event in self._pop_buffered_turntable_events(client):
            self._mark_event_handled(event)

    def _drain_buffered_turntable_events(self, client: Any) -> None:
        for event in self._pop_buffered_turntable_events(client):
            self._on_client_event(event)

    def _mark_event_handled(self, event: Any) -> bool:
        event_id = getattr(event, "id", None)
        if event_id is not None:
            normalized_id = str(event_id)
            if normalized_id in self._handled_event_ids:
                return False
            self._handled_event_ids.append(normalized_id)
            return True
        if any(item is event for item in self._handled_event_objects):
            return False
        self._handled_event_objects.append(event)
        return True

    def _clear_rotation_wait(self, state: _OperationState) -> None:
        self._turntable_timeout_timer.stop()
        self._turntable_deadline = None
        state.rotation_target = None
        state.rotation_speed = None
        state.after_rotation = None

    def _stop_turntable(self, client: Any) -> None:
        try:
            self._commands.stop_turntable(client)
        except Exception as exc:
            raise _ManualStopError(f"Turntable 정지 실패: {exc}") from exc

    def _try_stop_turntable(self, client: Any) -> Exception | None:
        try:
            self._commands.stop_turntable(client)
        except Exception as exc:
            return exc
        return None

    def _terminate(
        self,
        state: _OperationState,
        outcome: str,
        error: Exception | None = None,
    ) -> None:
        if not self._is_active(state):
            return
        self._step_timer.stop()
        self._turntable_timeout_timer.stop()
        self._step_deadline = None
        self._turntable_deadline = None
        self._clear_rotation_wait(state)
        self._state = None
        self._cancel_requested = False

        if not self._shutting_down:
            if outcome == "finished":
                self.operation_finished.emit(state.name)
            elif outcome == "cancelled":
                self.operation_cancelled.emit(state.name)
            elif outcome == "failed":
                message = str(error) if error is not None else "unknown error"
                if error is not None:
                    logger.error(
                        "Manual Test 작업 실패: %s: %s",
                        state.name,
                        message,
                        exc_info=(type(error), error, error.__traceback__),
                    )
                self.operation_failed.emit(state.name, message)
        self.running_changed.emit(False)

    def _is_active(self, state: _OperationState) -> bool:
        return self._state is state and not self._shutting_down

    def _require_client(self) -> Any:
        if self._client is None:
            raise RuntimeError("Manual Test client is not configured")
        return self._client

    @staticmethod
    def _validate_turntable_request(*, angle: float, speed: int) -> None:
        if angle not in (0, 0.0, 360, 360.0):
            raise ValueError("Turntable 목표 각도는 0° 또는 360°여야 합니다.")
        if isinstance(speed, bool) or not isinstance(speed, int) or speed <= 0:
            raise ValueError("Turntable Speed는 0보다 큰 정수여야 합니다.")

    @staticmethod
    def _validate_nonnegative_delay(value: float, *, field_name: str) -> None:
        if (
            isinstance(value, bool)
            or not isinstance(value, int | float)
            or not math.isfinite(float(value))
            or value < 0
        ):
            raise ValueError(f"{field_name}은 0 이상의 유한한 숫자여야 합니다.")

    def _require_capability(
        self,
        operation_name: str,
        *,
        available: bool,
        message: str,
    ) -> bool:
        if available:
            return True
        self.operation_failed.emit(operation_name, message)
        return False

    @staticmethod
    def _require_true(result: object, command_name: str) -> None:
        if not bool(result):
            raise RuntimeError(f"{command_name} returned false")

    def shutdown(self) -> None:
        """신규 작업을 막고 timer와 client event 연결을 정리한다."""

        if self._shutting_down:
            return
        self._shutting_down = True
        state = self._state
        if state is not None and state.phase is _OperationPhase.WAIT_TURNTABLE:
            stop_error = self._try_stop_turntable(self._require_client())
            if stop_error is not None:
                logger.error("Manual Test 종료 중 Turntable 정지 실패: %s", stop_error)
        self._step_timer.stop()
        self._turntable_timeout_timer.stop()
        self._step_deadline = None
        self._turntable_deadline = None
        if self._event_signal is not None:
            _disconnect_safely(self._event_signal, self._on_client_event)
            self._event_signal = None
        if state is not None:
            self._clear_rotation_wait(state)
            self._state = None
            self._cancel_requested = False
            self.running_changed.emit(False)
