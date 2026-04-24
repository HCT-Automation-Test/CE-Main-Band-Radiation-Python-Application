"""In-Band 측정 상태.

공유 스텝 (SetSwitchBox / SetupSpectrumAnalyzer / RotateTurntable / ResetSwitchBox)
은 `measurement.common`에 정의되어 있다. In-Band는 MeasureFundamental 단계 없이
공유 스텝을 거쳐 `MeasureInBand`에서 실제 측정을 수행한다.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.fsm.base import State, StateResult
from app.core.fsm.states.measurement.reporting import append_and_write_report
from app.models.measurement_result import InbandResult

if TYPE_CHECKING:
    from app.core.fsm.context import SessionContext


class MeasureInBandState(State):
    """In-Band 측정. RotateTurntable 이후 진입, 완료 시 ResetSwitchBox로 복귀."""

    name = "MeasureInBand"

    def run(self, ctx: "SessionContext") -> StateResult:
        # calls: net.commands.measure_inband(client, ...)
        # TODO(spec): In-Band 측정 파라미터/반환 스키마
        result = InbandResult()
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
