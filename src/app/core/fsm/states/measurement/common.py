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

_ROTATION_TIMEOUT_SEC = 60.0
_POLL_INTERVAL_SEC = 0.2
_SETTLING_SEC = 5.0

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


class SetSwitchBoxState(State):
    """§4.4 — Switch Box의 입력 경로/필터를 TestRange에 맞게 전환한다."""

    name = "SetSwitchBox"

    def run(self, ctx: "SessionContext") -> StateResult:
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
                },
            )
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

    def enter(self, ctx: "SessionContext") -> None:
        self._completed.clear()
        self._failed_reason = None
        self._ctx = ctx
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
        self._ctx = None

    def run(self, ctx: "SessionContext") -> StateResult:
        self._target_angle = 360.0 if ctx.current_angle == 0 else 0.0
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
        while not self._completed.wait(_POLL_INTERVAL_SEC):
            if ctx.stopped:
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

        settle_deadline = time.monotonic() + _SETTLING_SEC
        while time.monotonic() < settle_deadline:
            if ctx.stopped:
                return StateResult.FAIL
            time.sleep(_POLL_INTERVAL_SEC)

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

        command = getattr(event, "command", None)
        if command == _COMMAND_TURNTABLE_PROGRESS:
            self._emit_progress_angle(event)
            return
        if command == _COMMAND_TURNTABLE_COMPLETE:
            self._completed.set()
        elif command == _COMMAND_EQUIPMENT_ERROR:
            params = getattr(event, "params", {}) or {}
            self._failed_reason = str(params.get("message", "unknown"))
            self._completed.set()

    def _send_stop(self, ctx: "SessionContext") -> None:
        try:
            ctx.commands.stop_turntable(ctx.client)
        except Exception as exc:
            _emit_error(ctx, f"턴테이블 정지 명령 실패: {exc}")

    def _emit_progress_angle(self, event: Any) -> None:
        ctx = self._ctx
        if ctx is None:
            return

        params = getattr(event, "params", {}) or {}
        try:
            current_angle = float(params["Current Angle"])
        except (KeyError, TypeError, ValueError):
            return
        if not math.isfinite(current_angle):
            return

        _emit_turntable_info(ctx, {"current_angle": current_angle})


class ResetSwitchBoxState(State):
    """§4.8 — Switch Box를 기본 경로로 복원한다(시퀀스 정리)."""

    name = "ResetSwitchBox"

    def run(self, ctx: "SessionContext") -> StateResult:
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
