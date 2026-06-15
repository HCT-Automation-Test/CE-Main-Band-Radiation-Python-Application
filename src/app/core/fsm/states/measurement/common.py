"""3타입 공통 측정 스텝 (Switch Box / SA / Turntable / Reset).

Harmonic, InBand, Bilog 측정 모두가 공유하는 장비 조작 스텝.
- SetSwitchBox → SetupSpectrumAnalyzer → RotateTurntable까지는 동일 경로.
- RotateTurntable에서 test_type에 따라 Measure(Harmonics|InBand|Bilog)로 분기.
- Measure 이후 ResetSwitchBox → CheckNextCase로 복귀.
"""
from __future__ import annotations

import logging
import math
import threading
import time
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import Qt

from app.core.fsm.base import State, StateResult
from app.core.fsm.equipment import is_equipment_connected
from app.models.band_group import find_band_group
from app.models.enums import FilterPath, InputPath, TestType
from app.models.switch_box import (
    display_filter_path,
    display_input_path,
    resolve_filter_path,
)

if TYPE_CHECKING:
    from app.core.fsm.context import SessionContext

logger = logging.getLogger(__name__)

_ROTATION_TIMEOUT_SEC = 300.0
_POLL_INTERVAL_SEC = 0.2
_SETTLING_SEC = 5.0
_PROGRESS_EMIT_INTERVAL_SEC = 0.1

# TODO(spec): 외부 프로그램과 합의 후 command 이름 확정
_TARGET_TURNTABLE = "CO3000"
_COMMAND_TURNTABLE_PROGRESS = "turntable_progress"
_COMMAND_TURNTABLE_COMPLETE = "turntable_complete"
_COMMAND_EQUIPMENT_ERROR = "equipment_error"
_TRACE_MODE_LOAD_SA_RANGE_SETTING = "Max Hold"


def _emit_error(ctx: "SessionContext", message: str) -> None:
    logger.error(message)
    if ctx.events is not None:
        ctx.events.error.emit(message)


def _emit_spectrum_analyzer_info(
    ctx: "SessionContext",
    info: dict[str, object],
) -> None:
    if ctx.events is None:
        return
    signal = getattr(ctx.events, "spectrum_analyzer_info_changed", None)
    if signal is not None:
        signal.emit(info)


def _emit_switch_box_info(
    ctx: "SessionContext",
    *,
    input_path: InputPath,
    filter_path: FilterPath,
) -> None:
    if ctx.events is None:
        return
    signal = getattr(ctx.events, "switch_box_info_changed", None)
    if signal is not None:
        signal.emit(
            {
                "mast": display_input_path(input_path),
                "filter": display_filter_path(filter_path),
            }
        )


def _emit_turntable_info(
    ctx: "SessionContext",
    info: dict[str, object],
) -> None:
    if ctx.events is None:
        return
    signal = getattr(ctx.events, "turntable_info_changed", None)
    if signal is not None:
        signal.emit(info)


def _saturation_time_sec(ctx: "SessionContext") -> float:
    """현재 세션의 Saturation Time을 초 단위로 반환한다."""
    if ctx.settings is None:
        return _SETTLING_SEC
    return float(ctx.settings.saturation_time_sec)


def _wait_for_saturation_time(ctx: "SessionContext") -> bool:
    """SA 안정화를 위해 Saturation Time만큼 대기한다."""
    deadline = time.monotonic() + max(0.0, _saturation_time_sec(ctx))
    while True:
        if ctx.stopped or ctx.current_case_stop_requested:
            return False
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return True
        time.sleep(min(_POLL_INTERVAL_SEC, remaining))


class SetupSpectrumAnalyzerStartupLevelState(State):
    """시험 시작 전 FSV40 Atten/Next Peak Search Level을 1회 설정한다."""

    name = "SetupSpectrumAnalyzerStartupLevel"

    def run(self, ctx: "SessionContext") -> StateResult:
        if ctx.settings is None:
            _emit_error(
                ctx,
                "Spectrum Analyzer Startup Level 설정 실패: settings is required",
            )
            return StateResult.FAIL

        if not is_equipment_connected(ctx, "FSV40"):
            _emit_error(
                ctx,
                "Spectrum Analyzer Startup Level 설정 스킵: FSV40이 연결되어 있지 않습니다.",
            )
            return StateResult.OK

        try:
            configured = ctx.commands.setup_sa_startup_levels(
                ctx.client,
                atten_level_db=ctx.settings.atten_level_db,
                next_peak_search_level_db=ctx.settings.next_peak_search_level_db,
            )
        except Exception as exc:
            _emit_error(ctx, f"Spectrum Analyzer Startup Level 설정 실패: {exc}")
            return StateResult.FAIL

        if configured:
            return StateResult.OK

        _emit_error(
            ctx,
            "Spectrum Analyzer Startup Level 설정 실패: "
            "setup_sa_startup_levels returned false",
        )
        return StateResult.FAIL

    def next_state(
        self, ctx: "SessionContext", result: StateResult
    ) -> str | None:
        if result is not StateResult.OK:
            return None
        return "NRCallConnect"


class SetSwitchBoxState(State):
    """§4.4 — Switch Box의 입력 경로/필터를 TestRange에 맞게 전환한다."""

    name = "SetSwitchBox"

    def run(self, ctx: "SessionContext") -> StateResult:
        if not is_equipment_connected(ctx, "Switch Box"):
            _emit_error(ctx, "Switch Box RF 경로 설정 스킵: Switch Box가 연결되어 있지 않습니다.")
            return StateResult.OK

        test_case = ctx.current_case
        test_range = test_case.range_definition
        try:
            filter_path = resolve_filter_path(
                test_range.filter_mode,
                test_case.band.value,
            )
            configured = ctx.commands.set_switch_box(
                ctx.client,
                input_path=test_range.input_path,
                filter_path=filter_path,
            )
        except Exception as exc:
            _emit_error(ctx, f"Switch Box RF 경로 설정 실패: {exc}")
            return StateResult.FAIL

        if configured:
            _emit_switch_box_info(
                ctx,
                input_path=test_range.input_path,
                filter_path=filter_path,
            )
            return StateResult.OK

        _emit_error(ctx, "Switch Box RF 경로 설정 실패: set_switch_box returned false")
        return StateResult.FAIL

    def next_state(
        self, ctx: "SessionContext", result: StateResult
    ) -> str | None:
        if result is not StateResult.OK:
            return None
        return "SetupSpectrumAnalyzer"


class SetupSpectrumAnalyzerState(State):
    """§4.5 — FSV40에 TestRange(Start/Stop/RBW/VBW/Limit/SweepPoint)을 로드한다."""

    name = "SetupSpectrumAnalyzer"

    def run(self, ctx: "SessionContext") -> StateResult:
        if not is_equipment_connected(ctx, "FSV40"):
            _emit_error(ctx, "Spectrum Analyzer 설정 스킵: FSV40이 연결되어 있지 않습니다.")
            return StateResult.OK

        test_range = ctx.current_case.range_definition
        try:
            configured = ctx.commands.setup_sa(ctx.client, test_range=test_range)
        except Exception as exc:
            _emit_error(ctx, f"Spectrum Analyzer 설정 실패: {exc}")
            return StateResult.FAIL

        if configured:
            _emit_spectrum_analyzer_info(
                ctx,
                {
                    "start_freq": test_range.start_freq,
                    "stop_freq": test_range.stop_freq,
                    "trace_mode": _TRACE_MODE_LOAD_SA_RANGE_SETTING,
                    "rbw": test_range.rbw,
                    "vbw": test_range.vbw,
                    "sweep_point": test_range.sweep_point,
                    "limit": test_range.limit,
                },
            )
            if not _wait_for_saturation_time(ctx):
                return StateResult.FAIL
            return StateResult.OK

        _emit_error(ctx, "Spectrum Analyzer 설정 실패: setup_sa returned false")
        return StateResult.FAIL

    def next_state(
        self, ctx: "SessionContext", result: StateResult
    ) -> str | None:
        if result is not StateResult.OK:
            return None
        return "RotateTurntable"


class RotateTurntableState(State):
    """§4.6 — CO3000 턴테이블을 0↔360 토글 각도로 회전시킨다."""

    name = "RotateTurntable"

    def __init__(self) -> None:
        self._completed = threading.Event()
        self._failed_reason: str | None = None
        self._target_angle: float = 0.0
        self._ctx: SessionContext | None = None
        self._pending_progress_angle: float | None = None
        self._last_progress_emit_monotonic: float = 0.0
        self._handled_event_objects: list[Any] = []

    def enter(self, ctx: "SessionContext") -> None:
        self._completed.clear()
        self._failed_reason = None
        self._ctx = ctx
        self._pending_progress_angle = None
        self._last_progress_emit_monotonic = 0.0
        self._handled_event_objects.clear()
        self._discard_buffered_turntable_events(ctx)
        if ctx.client is not None:
            ctx.client.event_received.connect(
                self._on_event_received, Qt.DirectConnection
            )

    def exit(self, ctx: "SessionContext") -> None:
        if ctx.client is not None:
            try:
                ctx.client.event_received.disconnect(self._on_event_received)
            except (RuntimeError, TypeError):
                pass
        self._discard_buffered_turntable_events(ctx)
        self._handled_event_objects.clear()
        self._ctx = None

    def run(self, ctx: "SessionContext") -> StateResult:
        self._target_angle = 360.0 if ctx.current_angle == 0 else 0.0
        if not is_equipment_connected(ctx, "CO3000"):
            _emit_error(ctx, "Turntable 회전 스킵: CO3000이 연결되어 있지 않습니다.")
            return StateResult.OK

        try:
            band_group = find_band_group(ctx.current_case.band.value)
        except ValueError as exc:
            _emit_error(ctx, f"BandGroup 조회 실패: {exc}")
            return StateResult.FAIL
        speed = band_group.turntable_speed

        try:
            ctx.commands.rotate_turntable(
                ctx.client, angle=self._target_angle, turntable_speed=speed
            )
        except Exception as exc:
            _emit_error(ctx, f"턴테이블 회전 명령 실패: {exc}")
            return StateResult.FAIL

        _emit_turntable_info(
            ctx,
            {
                "target_angle": self._target_angle,
                "setting_speed": speed,
            },
        )
        ctx.events.progress.emit(0)

        deadline = time.monotonic() + _ROTATION_TIMEOUT_SEC
        self._drain_buffered_events(ctx)
        while not self._completed.wait(_POLL_INTERVAL_SEC):
            self._drain_buffered_events(ctx)
            self._emit_pending_progress_angle(force=False)
            if self._completed.is_set():
                break
            if ctx.stopped or ctx.current_case_stop_requested:
                self._send_stop(ctx)
                return StateResult.FAIL
            if time.monotonic() > deadline:
                _emit_error(ctx, "턴테이블 회전 타임아웃")
                self._send_stop(ctx)
                return StateResult.FAIL

        if self._failed_reason is not None:
            _emit_error(ctx, f"턴테이블 회전 실패: {self._failed_reason}")
            return StateResult.FAIL

        ctx.current_angle = self._target_angle
        _emit_turntable_info(ctx, {"current_angle": self._target_angle})
        ctx.events.progress.emit(100)

        if not _wait_for_saturation_time(ctx):
            return StateResult.FAIL
        return StateResult.OK

    def next_state(
        self, ctx: "SessionContext", result: StateResult
    ) -> str | None:
        if result is not StateResult.OK:
            return None
        return measurement_start_state_for(ctx.current_case.test_type, after_rotate=True)

    def _on_event_received(self, event: Any) -> None:
        if getattr(event, "target", None) != _TARGET_TURNTABLE:
            return

        if not self._mark_event_handled(event):
            return

        self._handle_turntable_event(event)

    def _handle_turntable_event(self, event: Any) -> None:
        command = getattr(event, "command", None)
        if command == _COMMAND_TURNTABLE_PROGRESS:
            self._record_progress_angle(event)
            self._emit_pending_progress_angle(force=False)
            return
        if command == _COMMAND_TURNTABLE_COMPLETE:
            self._emit_pending_progress_angle(force=True)
            self._completed.set()
        elif command == _COMMAND_EQUIPMENT_ERROR:
            self._emit_pending_progress_angle(force=True)
            params = getattr(event, "params", {}) or {}
            self._failed_reason = str(params.get("message", "unknown"))
            self._completed.set()

    def _drain_buffered_events(self, ctx: "SessionContext") -> None:
        events = self._pop_buffered_turntable_events(ctx)
        control_events: list[Any] = []
        for event in events:
            if not self._mark_event_handled(event):
                continue
            if getattr(event, "command", None) == _COMMAND_TURNTABLE_PROGRESS:
                self._record_progress_angle(event)
                continue
            control_events.append(event)

        self._emit_pending_progress_angle(force=False)

        for event in control_events:
            self._handle_turntable_event(event)

    def _discard_buffered_turntable_events(self, ctx: "SessionContext") -> None:
        self._pop_buffered_turntable_events(ctx)

    def _pop_buffered_turntable_events(self, ctx: "SessionContext") -> list[Any]:
        pop_events = getattr(ctx.client, "pop_events", None)
        if pop_events is None:
            return []

        try:
            return list(pop_events(self._is_turntable_event))
        except Exception as exc:
            logger.warning("TCP event buffer read failed: %s", exc)
            return []

    def _is_turntable_event(self, event: Any) -> bool:
        return (
            getattr(event, "target", None) == _TARGET_TURNTABLE
            and getattr(event, "command", None)
            in {
                _COMMAND_TURNTABLE_PROGRESS,
                _COMMAND_TURNTABLE_COMPLETE,
                _COMMAND_EQUIPMENT_ERROR,
            }
        )

    def _mark_event_handled(self, event: Any) -> bool:
        if any(handled_event is event for handled_event in self._handled_event_objects):
            return False
        self._handled_event_objects.append(event)
        return True

    def _send_stop(self, ctx: "SessionContext") -> None:
        try:
            ctx.commands.stop_turntable(ctx.client)
        except Exception as exc:
            _emit_error(ctx, f"턴테이블 정지 명령 실패: {exc}")

    def _record_progress_angle(self, event: Any) -> None:
        current_angle = self._progress_angle_from_event(event)
        if current_angle is None:
            return
        self._pending_progress_angle = current_angle

    def _emit_pending_progress_angle(self, *, force: bool) -> None:
        ctx = self._ctx
        if ctx is None or self._pending_progress_angle is None:
            return

        now = time.monotonic()
        if (
            not force
            and self._last_progress_emit_monotonic > 0
            and now - self._last_progress_emit_monotonic < _PROGRESS_EMIT_INTERVAL_SEC
        ):
            return

        current_angle = self._pending_progress_angle
        self._pending_progress_angle = None
        self._last_progress_emit_monotonic = now
        _emit_turntable_info(ctx, {"current_angle": current_angle})

    def _progress_angle_from_event(self, event: Any) -> float | None:
        params = getattr(event, "params", {}) or {}
        try:
            current_angle = float(params["Current Angle"])
        except (KeyError, TypeError, ValueError):
            return None
        if not math.isfinite(current_angle):
            return None
        return current_angle


class InitialTurntableZeroState(RotateTurntableState):
    """시험 시작 전 CO3000 턴테이블을 0도로 정렬한다."""

    name = "InitialTurntableZero"

    def run(self, ctx: "SessionContext") -> StateResult:
        self._target_angle = 0.0
        if not is_equipment_connected(ctx, "CO3000"):
            _emit_error(
                ctx,
                "Turntable 초기 0도 정렬 스킵: CO3000가 연결되어 있지 않습니다.",
            )
            return StateResult.OK

        try:
            ctx.commands.rotate_turntable(
                ctx.client,
                angle=self._target_angle,
                turntable_speed=4,
            )
        except Exception as exc:
            _emit_error(ctx, f"Turntable 초기 0도 정렬 명령 실패: {exc}")
            return StateResult.FAIL

        _emit_turntable_info(
            ctx,
            {
                "target_angle": self._target_angle,
                "setting_speed": 4,
            },
        )
        ctx.events.progress.emit(0)

        deadline = time.monotonic() + _ROTATION_TIMEOUT_SEC
        self._drain_buffered_events(ctx)
        while not self._completed.wait(_POLL_INTERVAL_SEC):
            self._drain_buffered_events(ctx)
            self._emit_pending_progress_angle(force=False)
            if self._completed.is_set():
                break
            if ctx.stopped or ctx.current_case_stop_requested:
                self._send_stop(ctx)
                return StateResult.FAIL
            if time.monotonic() > deadline:
                _emit_error(ctx, "Turntable 초기 0도 정렬 타임아웃")
                self._send_stop(ctx)
                return StateResult.FAIL

        if self._failed_reason is not None:
            _emit_error(ctx, f"Turntable 초기 0도 정렬 실패: {self._failed_reason}")
            return StateResult.FAIL

        ctx.current_angle = self._target_angle
        _emit_turntable_info(ctx, {"current_angle": self._target_angle})
        ctx.events.progress.emit(100)
        return StateResult.OK

    def next_state(
        self, ctx: "SessionContext", result: StateResult
    ) -> str | None:
        if result is not StateResult.OK:
            return None
        return "AntPolChange"


class ResetSwitchBoxState(State):
    """§4.8 — Switch Box를 기본 경로로 복원한다(시퀀스 정리)."""

    name = "ResetSwitchBox"

    def run(self, ctx: "SessionContext") -> StateResult:
        if not is_equipment_connected(ctx, "Switch Box"):
            _emit_error(ctx, "Switch Box 기본 경로 복원 스킵: Switch Box가 연결되어 있지 않습니다.")
            return StateResult.OK

        try:
            configured = ctx.commands.set_switch_box(
                ctx.client,
                input_path=InputPath.INPUT1,
                filter_path=FilterPath.THRU,
            )
        except Exception as exc:
            _emit_error(ctx, f"Switch Box 기본 경로 복원 실패: {exc}")
            return StateResult.FAIL

        if configured:
            _emit_switch_box_info(
                ctx,
                input_path=InputPath.INPUT1,
                filter_path=FilterPath.THRU,
            )
            return StateResult.OK

        _emit_error(ctx, "Switch Box 기본 경로 복원 실패: set_switch_box returned false")
        return StateResult.FAIL

    def next_state(
        self, ctx: "SessionContext", result: StateResult
    ) -> str | None:
        if result is not StateResult.OK:
            return None
        return "CheckNextCase"


def measurement_start_state_for(
    test_type: TestType, *, after_rotate: bool = False
) -> str:
    """test_type에 해당하는 측정 시작 state 이름을 반환한다.

    - after_rotate=False (기본): NRCallConnect / TestTypeChange 등에서 측정 시퀀스로 진입할 때.
      Harmonic은 MeasureFundamental부터 시작, InBand/Bilog는 공유 SetSwitchBox부터 시작.
    - after_rotate=True: RotateTurntable 이후 실제 측정 state로 분기할 때.
    """
    if after_rotate:
        mapping = {
            TestType.HARMONIC: "MeasureHarmonics",
            TestType.INBAND: "MeasureInBand",
            TestType.BILOG: "MeasureBilog",
        }
    else:
        mapping = {
            TestType.HARMONIC: "MeasureFundamental",
            TestType.INBAND: "SetSwitchBox",
            TestType.BILOG: "SetSwitchBox",
        }
    try:
        return mapping[test_type]
    except KeyError as exc:
        raise ValueError(f"unknown test_type: {test_type!r}") from exc
