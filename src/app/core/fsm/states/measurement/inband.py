"""In-Band 측정 상태.

공유 스텝 (SetSwitchBox / SetupSpectrumAnalyzer / RotateTurntable / ResetSwitchBox)
은 `measurement.common`에 정의되어 있다. In-Band는 MeasureFundamental 단계 없이
공유 스텝을 거쳐 `MeasureInBand`에서 실제 측정을 수행한다.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.core.fsm.base import State, StateResult
from app.core.fsm.states.measurement.reporting import append_and_write_report
from app.models.measurement_result import InbandResult

if TYPE_CHECKING:
    from app.core.fsm.context import SessionContext

_INBAND_SCREENSHOT_NAME = "inband.png"

logger = logging.getLogger(__name__)


def _emit_error(ctx: "SessionContext", message: str) -> None:
    logger.error(message)
    if ctx.events is not None:
        ctx.events.error.emit(message)


class MeasureInBandState(State):
    """In-Band 측정. RotateTurntable 이후 진입, 완료 시 ResetSwitchBox로 복귀."""

    name = "MeasureInBand"

    def run(self, ctx: "SessionContext") -> StateResult:
        # calls: net.commands.measure_inband(client, ...)
        # TODO(spec): In-Band 측정 파라미터/반환 스키마
        if ctx.temp_dir is None:
            _emit_error(ctx, "In-Band 스크린샷 경로 생성 실패: temp_dir is not set")
            return StateResult.OK

        screenshot_path = ctx.temp_dir / _INBAND_SCREENSHOT_NAME
        if not screenshot_path.is_file():
            _emit_error(
                ctx,
                f"In-Band 스크린샷 저장 실패: {screenshot_path} does not exist",
            )
            return StateResult.OK

        result = InbandResult(screenshot_path=screenshot_path)
        return append_and_write_report(
            ctx,
            result,
            lambda writer: writer.write_inband(ctx.current_case, result),
            "In-Band 리포트 작성 실패: write_inband returned false",
        )

    def next_state(
        self, ctx: "SessionContext", result: StateResult
    ) -> str | None:
        if result is not StateResult.OK:
            return None
        return "ResetSwitchBox"
