"""Harmonic 전용 측정 상태.

공유 스텝(SetSwitchBox / SetupSpectrumAnalyzer / RotateTurntable / ResetSwitchBox)은
`measurement.common`으로 분리되었다.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.fsm.base import State, StateResult
from app.core.fsm.states.measurement.reporting import append_and_write_report
from app.models.measurement_result import FundamentalResult, HarmonicResult

if TYPE_CHECKING:
    from app.core.fsm.context import SessionContext


class MeasureFundamentalState(State):
    """§4.3 — 기본파 주파수를 측정하여 결과에 저장한다."""

    name = "MeasureFundamental"

    def run(self, ctx: "SessionContext") -> StateResult:
        # calls: net.commands.measure_fundamental(client, target_freq=...)
        # TODO(spec): 외부 프로그램의 측정 응답 스키마 확정 후 필드 매핑.
        result = FundamentalResult()
        return append_and_write_report(
            ctx,
            result,
            lambda writer: writer.write_fundamental(ctx.current_case, result),
            "Fundamental 리포트 작성 실패: write_fundamental returned false",
        )

    def next_state(
        self, ctx: "SessionContext", result: StateResult
    ) -> str | None:
        if result is not StateResult.OK:
            return None
        return "SetSwitchBox"


class MeasureHarmonicsState(State):
    """§4.7 — 각 Range에 대해 하모닉 피크를 측정하고 스크린샷을 저장한다."""

    name = "MeasureHarmonics"

    def run(self, ctx: "SessionContext") -> StateResult:
        # calls: net.commands.measure_harmonics(client, fundamental=...)
        # TODO(spec): 외부 프로그램의 측정 응답 스키마 확정 후 필드 매핑.
        result = HarmonicResult()
        return append_and_write_report(
            ctx,
            result,
            lambda writer: writer.write_harmonic(ctx.current_case, result),
            "Harmonic 리포트 작성 실패: write_harmonic returned false",
        )

    def next_state(
        self, ctx: "SessionContext", result: StateResult
    ) -> str | None:
        if result is not StateResult.OK:
            return None
        return "ResetSwitchBox"
