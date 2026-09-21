"""Manual Test 장비 command 및 Turntable Event 수명주기 서비스."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QObject, QTimer, Signal

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
ManualOperation = Callable[[], None]
MANUAL_OPERATION_IN_PROGRESS_MESSAGE = "Manual Test 작업이 진행 중입니다."
MANUAL_SERVICE_SHUTTING_DOWN_MESSAGE = "Manual Test 서비스를 종료하는 중입니다."
_DEFAULT_TURNTABLE_TIMEOUT_SEC = 300.0
_TURNTABLE_EVENT_COMMANDS = {
    "turntable_progress",
    "turntable_complete",
    "equipment_error",
}
_MAX_HANDLED_TURNTABLE_EVENTS = 1000


@dataclass(frozen=True)
class ManualTestCapabilities:
    """장비 연결 상태로만 계산하는 Manual Test 기능 집합."""

    fsv40: bool = False
    marker: bool = False
    capture: bool = False
    turntable: bool = False
    mast_1m: bool = False
    mast_3m: bool = False


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
    )


class ManualTestService(QObject):
    """Manual 장비 command를 호출 스레드에서 하나씩 실행한다."""

    operation_started = Signal(str)
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
        self._running = False
        self._current_operation: str | None = None
        self._capabilities = ManualTestCapabilities()
        self._shutting_down = False
        self._turntable_target_angle: float | None = None
        self._turntable_speed: int | None = None
        self._turntable_event_signal: Any | None = None
        self._handled_turntable_events: list[Any] = []
        self._turntable_timeout_timer = QTimer(self)
        self._turntable_timeout_timer.setSingleShot(True)
        self._turntable_timeout_timer.timeout.connect(self._on_turntable_timeout)

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def current_operation(self) -> str | None:
        return self._current_operation

    @property
    def is_turntable_running(self) -> bool:
        return self._running and self._turntable_target_angle is not None

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
        """FSV40 Manual 설정 command를 한 번 호출한다."""

        def operation() -> None:
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

        return self._run_operation("FSV40 Set", operation)

    def preset_sa(self) -> bool:
        return self._run_bool_command("FSV40 Preset", self._commands.preset_sa)

    def clear_trace(self) -> bool:
        return self._run_bool_command("Trace Clear", self._commands.clear_trace)

    def marker_peak(self, marker_index: int, excursion: float) -> bool:
        return self._run_marker_command(
            "Marker Peak",
            self._commands.marker_peak,
            marker_index,
            excursion,
        )

    def marker_next(self, marker_index: int, excursion: float) -> bool:
        return self._run_marker_command(
            "Marker Next",
            self._commands.marker_next,
            marker_index,
            excursion,
        )

    def marker_off(self, marker_index: int, excursion: float) -> bool:
        return self._run_marker_command(
            "Marker OFF",
            self._commands.marker_off,
            marker_index,
            excursion,
        )

    def marker_all_off(self) -> bool:
        return self._run_bool_command(
            "Marker ALL OFF",
            self._commands.marker_all_off,
        )

    def marker_auto_max(self, marker_index: int, excursion: float) -> bool:
        return self._run_marker_command(
            "Marker Auto Max",
            self._commands.marker_auto_max,
            marker_index,
            excursion,
        )

    def marker_set_center(self, marker_index: int, excursion: float) -> bool:
        return self._run_marker_command(
            "Marker to Center",
            self._commands.marker_set_center,
            marker_index,
            excursion,
        )

    def move_turntable(self, *, angle: float, speed: int) -> bool:
        """Turntable 이동 command를 보내고 완료 Event까지 operation을 유지한다."""

        self._validate_turntable_request(angle=angle, speed=speed)
        name = f"Turntable {angle:g}°"
        if not self._begin_operation(name):
            return False

        try:
            client = self._require_client()
            event_signal = getattr(client, "event_received", None)
            if event_signal is None:
                raise RuntimeError("Turntable Event signal is not available")

            self._discard_buffered_turntable_events(client)
            self._turntable_target_angle = angle
            self._turntable_speed = speed
            self._turntable_event_signal = event_signal
            event_signal.connect(self._on_turntable_event)
            self.turntable_info_changed.emit(
                {"target_angle": angle, "current_angle": None, "speed": speed}
            )
            self._commands.rotate_turntable(
                client,
                angle=angle,
                turntable_speed=speed,
            )
            self._drain_buffered_turntable_events(client)
            if self.is_turntable_running:
                timeout_ms = max(1, round(self._turntable_timeout_sec * 1000))
                self._turntable_timeout_timer.start(timeout_ms)
            return True
        except Exception as exc:
            logger.exception("Manual Test 작업 실패: %s", name)
            self._terminate_turntable_failure(str(exc))
            return False

    def request_stop(self) -> bool:
        """진행 중인 Manual Turntable 회전을 중단한다."""

        if not self.is_turntable_running:
            return False
        try:
            self._commands.stop_turntable(self._require_client())
        except Exception as exc:
            logger.exception("Manual Test Turntable Stop 실패")
            self.operation_failed.emit(
                "Turntable Stop",
                f"Turntable 정지 실패: {exc}",
            )
            return False

        if not self.is_turntable_running:
            return True
        name = self._current_operation or "Turntable"
        self._cleanup_turntable_operation()
        self.operation_cancelled.emit(name)
        return True

    def set_mast_polarization(
        self,
        *,
        mast: ManualMast,
        polarization: AntennaPol,
    ) -> bool:
        """선택 Mast와 편파를 기존 InputPath 계약으로 변환한다."""

        def operation() -> None:
            ok = self._commands.set_antenna_pol(
                self._require_client(),
                pol=polarization,
                input_path=mast.input_path,
            )
            self._require_true(ok, "Change Ant Pol")

        return self._run_operation("Mast Polarization", operation)

    def capture_single(self, *, directory: Path, base_name: str) -> bool:
        """현재 FSV40 화면을 한 장 저장한다."""

        paths = build_manual_screenshot_paths(
            directory=directory,
            base_name=base_name,
            shot_count=1,
            numbered=False,
        )

        def operation() -> None:
            ensure_manual_screenshot_paths_available(paths)
            destination = paths[0]
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

        return self._run_operation("Single Capture", operation)

    def shutdown(self) -> None:
        """신규 Manual command를 막고 진행 중인 회전을 정리한다."""

        if self._shutting_down:
            return
        self._shutting_down = True
        if not self.is_turntable_running:
            return
        try:
            self._commands.stop_turntable(self._require_client())
        except Exception:
            logger.exception("Manual Test 종료 중 Turntable Stop 실패")
        self._cleanup_turntable_operation()

    def _run_bool_command(
        self,
        name: str,
        command: Callable[[Any], bool],
    ) -> bool:
        def operation() -> None:
            self._require_true(command(self._require_client()), name)

        return self._run_operation(name, operation)

    def _run_marker_command(
        self,
        name: str,
        command: Callable[..., bool],
        marker_index: int,
        excursion: float,
    ) -> bool:
        def operation() -> None:
            ok = command(
                self._require_client(),
                marker_index=marker_index,
                excursion=excursion,
            )
            self._require_true(ok, name)

        return self._run_operation(name, operation)

    def _run_operation(self, name: str, operation: ManualOperation) -> bool:
        if not self._begin_operation(name):
            return False
        try:
            operation()
        except Exception as exc:
            logger.exception("Manual Test 작업 실패: %s", name)
            self.operation_failed.emit(name, str(exc))
            return False
        else:
            self.operation_finished.emit(name)
            return True
        finally:
            self._finish_operation()

    def _begin_operation(self, name: str) -> bool:
        if self._shutting_down:
            self.operation_failed.emit(name, MANUAL_SERVICE_SHUTTING_DOWN_MESSAGE)
            return False
        if self._running:
            self.operation_failed.emit(name, MANUAL_OPERATION_IN_PROGRESS_MESSAGE)
            return False
        if self._operation_guard is not None:
            block_reason = self._operation_guard()
            if block_reason:
                self.operation_failed.emit(name, block_reason)
                return False

        self._running = True
        self._current_operation = name
        self.running_changed.emit(True)
        self.operation_started.emit(name)
        return True

    def _finish_operation(self) -> None:
        self._running = False
        self._current_operation = None
        self.running_changed.emit(False)

    def _on_turntable_event(self, event: Any) -> None:
        if not self.is_turntable_running or not self._is_turntable_event(event):
            return
        if any(handled is event for handled in self._handled_turntable_events):
            return
        self._handled_turntable_events.append(event)
        if len(self._handled_turntable_events) > _MAX_HANDLED_TURNTABLE_EVENTS:
            del self._handled_turntable_events[0]

        command = getattr(event, "command", None)
        params = getattr(event, "params", {}) or {}
        if command == "turntable_progress":
            if not isinstance(params, dict):
                return
            current_angle = params.get("Current Angle", params.get("current_angle"))
            if current_angle is not None:
                self.turntable_info_changed.emit(
                    {
                        "target_angle": self._turntable_target_angle,
                        "current_angle": current_angle,
                        "speed": self._turntable_speed,
                    }
                )
            return
        if command == "equipment_error":
            message = (
                params.get("message", "unknown")
                if isinstance(params, dict)
                else "unknown"
            )
            self._terminate_turntable_failure(f"Turntable 회전 실패: {message}")
            return
        if command == "turntable_complete":
            name = self._current_operation or "Turntable"
            target_angle = self._turntable_target_angle
            speed = self._turntable_speed
            self.turntable_info_changed.emit(
                {
                    "target_angle": target_angle,
                    "current_angle": target_angle,
                    "speed": speed,
                }
            )
            self._cleanup_turntable_operation()
            self.operation_finished.emit(name)

    def _on_turntable_timeout(self) -> None:
        if not self.is_turntable_running:
            return
        try:
            self._commands.stop_turntable(self._require_client())
        except Exception:
            logger.exception("Manual Test Turntable timeout Stop 실패")
        if not self.is_turntable_running:
            return
        self._terminate_turntable_failure("Turntable 회전 타임아웃")

    def _terminate_turntable_failure(self, message: str) -> None:
        name = self._current_operation or "Turntable"
        self._cleanup_turntable_operation()
        self.operation_failed.emit(name, message)

    def _cleanup_turntable_operation(self) -> None:
        self._turntable_timeout_timer.stop()
        event_signal = self._turntable_event_signal
        self._turntable_event_signal = None
        if event_signal is not None:
            try:
                event_signal.disconnect(self._on_turntable_event)
            except (RuntimeError, TypeError):
                pass
        self._turntable_target_angle = None
        self._turntable_speed = None
        if self._running:
            self._finish_operation()

    def _discard_buffered_turntable_events(self, client: Any) -> None:
        pop_events = getattr(client, "pop_events", None)
        if not callable(pop_events):
            return
        try:
            pop_events(self._is_turntable_event)
        except Exception as exc:
            logger.warning("Manual Turntable event buffer 정리 실패: %s", exc)

    def _drain_buffered_turntable_events(self, client: Any) -> None:
        pop_events = getattr(client, "pop_events", None)
        if not callable(pop_events):
            return
        try:
            events = list(pop_events(self._is_turntable_event))
        except Exception as exc:
            logger.warning("Manual Turntable event buffer 읽기 실패: %s", exc)
            return
        for event in events:
            self._on_turntable_event(event)

    @staticmethod
    def _is_turntable_event(event: Any) -> bool:
        return (
            getattr(event, "target", None) == "CO3000"
            and getattr(event, "command", None) in _TURNTABLE_EVENT_COMMANDS
        )

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
    def _require_true(result: object, command_name: str) -> None:
        if not bool(result):
            raise RuntimeError(f"{command_name} returned false")
