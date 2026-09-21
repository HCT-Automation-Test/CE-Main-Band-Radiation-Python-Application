"""Manual Test FSV40 command 서비스."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

from PySide6.QtCore import QObject, Signal

from app.models.manual_test import ManualSaSettings
from app.net import commands as default_commands

logger = logging.getLogger(__name__)

OperationGuard = Callable[[], str | None]
ManualOperation = Callable[[], None]
MANUAL_OPERATION_IN_PROGRESS_MESSAGE = "Manual Test 작업이 진행 중입니다."
MANUAL_SERVICE_SHUTTING_DOWN_MESSAGE = "Manual Test 서비스를 종료하는 중입니다."


@dataclass(frozen=True)
class ManualTestCapabilities:
    """현재 구현된 Manual Test 기능의 장비 연결 상태."""

    fsv40: bool = False
    marker: bool = False


def manual_test_capabilities(
    equipment_state: dict[str, bool],
) -> ManualTestCapabilities:
    """FSV40 연결 상태에서 현재 Manual capability를 계산한다."""

    fsv40 = equipment_state.get("FSV40") is True
    return ManualTestCapabilities(fsv40=fsv40, marker=fsv40)


class ManualTestService(QObject):
    """FSV40 Manual command를 호출 스레드에서 하나씩 실행한다."""

    operation_started = Signal(str)
    operation_finished = Signal(str)
    operation_failed = Signal(str, str)
    running_changed = Signal(bool)
    capabilities_changed = Signal(object)

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        client: Any | None = None,
        commands: Any = default_commands,
        operation_guard: OperationGuard | None = None,
    ) -> None:
        super().__init__(parent)
        self._client = client
        self._commands = commands
        self._operation_guard = operation_guard
        self._running = False
        self._current_operation: str | None = None
        self._capabilities = ManualTestCapabilities()
        self._shutting_down = False

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def current_operation(self) -> str | None:
        return self._current_operation

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

    def marker_auto_max(self, marker_index: int) -> bool:
        return self._run_marker_command(
            "Marker Auto Max",
            self._commands.marker_auto_max,
            marker_index,
            0.0,
        )

    def marker_set_center(self, marker_index: int) -> bool:
        return self._run_marker_command(
            "Marker to Center",
            self._commands.marker_set_center,
            marker_index,
            0.0,
        )

    def shutdown(self) -> None:
        """신규 Manual command를 막는다."""

        self._shutting_down = True

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

    def _require_client(self) -> Any:
        if self._client is None:
            raise RuntimeError("Manual Test client is not configured")
        return self._client

    @staticmethod
    def _require_true(result: object, command_name: str) -> None:
        if not bool(result):
            raise RuntimeError(f"{command_name} returned false")
