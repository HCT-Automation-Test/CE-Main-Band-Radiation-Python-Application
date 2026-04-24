"""Harmonic 전용 측정 상태.

공유 스텝(SetSwitchBox / SetupSpectrumAnalyzer / RotateTurntable / ResetSwitchBox)은
`measurement.common`으로 분리되어 있다.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.core.fsm.base import State, StateResult
from app.core.fsm.states.measurement.reporting import append_and_write_report
from app.models.measurement_result import FundamentalResult, HarmonicResult
from app.models.nr_channel_lookup import resolve_target_frequency_mhz

if TYPE_CHECKING:
    from app.core.fsm.context import SessionContext

logger = logging.getLogger(__name__)


def _emit_error(ctx: "SessionContext", message: str) -> None:
    logger.error(message)
    if ctx.events is not None:
        ctx.events.error.emit(message)


class MeasureFundamentalState(State):
    """§4.3 기본파 주파수를 측정하여 결과를 저장한다."""

    name = "MeasureFundamental"

    def run(self, ctx: "SessionContext") -> StateResult:
        test_case = ctx.current_case
        try:
            target_frequency_mhz = resolve_target_frequency_mhz(
                test_case.band,
                test_case.bandwidth,
                test_case.test_channel,
            )
        except Exception as exc:
            _emit_error(ctx, f"Fundamental 측정 준비 실패: {exc}")
            return StateResult.FAIL

        if ctx.temp_dir is None:
            _emit_error(
                ctx,
                "Fundamental 스크린샷 경로 생성 실패: temp_dir is not set",
            )
            return StateResult.FAIL

        try:
            fundamental_frequency_mhz = float(
                ctx.commands.measure_fundamental(
                    ctx.client,
                    target_freq=target_frequency_mhz,
                )
            )
        except Exception as exc:
            _emit_error(ctx, f"Fundamental 측정 실패: {exc}")
            return StateResult.FAIL

        result = FundamentalResult(
            screenshot_path=ctx.temp_dir / "fundamental.png",
            fundamental_frequency_mhz=fundamental_frequency_mhz,
        )
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
    """§4.7 각 Range의 고조파를 측정하고 스크린샷을 저장한다."""

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
