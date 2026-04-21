"""3타입 공통 측정 스텝 (Switch Box / SA / Turntable / Reset).

Harmonic, InBand, Bilog 측정 모두가 공유하는 장비 조작 스텝.
- SetSwitchBox → SetupSpectrumAnalyzer → RotateTurntable까지는 동일 경로.
- RotateTurntable에서 test_type에 따라 Measure(Harmonics|InBand|Bilog)로 분기.
- Measure 이후 ResetSwitchBox → CheckNextCase로 복귀.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.core.fsm.base import State, StateResult
from app.models.enums import FilterPath, InputPath, TestType
from app.models.switch_box import resolve_filter_path

if TYPE_CHECKING:
    from app.core.fsm.context import SessionContext

logger = logging.getLogger(__name__)


def _emit_error(ctx: "SessionContext", message: str) -> None:
    logger.error(message)
    if ctx.events is not None:
        ctx.events.error.emit(message)


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
    """§4.6 — CO3000 턴테이블을 해당 축/각도로 회전시킨다."""

    name = "RotateTurntable"

    def run(self, ctx: "SessionContext") -> StateResult:
        # calls: net.commands.rotate_turntable(client, axis=..., angle=..., turntable_speed=...)
        raise NotImplementedError("spec TODO")

    def next_state(
        self, ctx: "SessionContext", result: StateResult
    ) -> str | None:
        return measurement_start_state_for(ctx.current_case.test_type, after_rotate=True)


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
