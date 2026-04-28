"""Bilog 측정 상태.

공유 스텝 (SetSwitchBox / SetupSpectrumAnalyzer / RotateTurntable / ResetSwitchBox)
은 `measurement.common`에 정의되어 있다. Bilog는 MeasureFundamental 단계 없이
공유 스텝을 거쳐 `MeasureBilog`에서 실제 측정을 수행한다.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.core.fsm.base import State, StateResult
from app.core.fsm.states.measurement.reporting import append_and_write_report
from app.models.measurement_result import BilogResult
from app.report.screenshot_store import finalize_sa_screenshot

if TYPE_CHECKING:
    from app.core.fsm.context import SessionContext

_BILOG_SCREENSHOT_NAME = "bilog.png"

logger = logging.getLogger(__name__)


def _emit_error(ctx: "SessionContext", message: str) -> None:
    logger.error(message)
    if ctx.events is not None:
        ctx.events.error.emit(message)


class MeasureBilogState(State):
    """Bilog 측정. RotateTurntable 이후 진입, 완료 시 ResetSwitchBox로 복귀."""

    name = "MeasureBilog"

    def run(self, ctx: "SessionContext") -> StateResult:
        # calls: net.commands.measure_bilog(client, ...)
        # TODO(spec): Bilog 측정 파라미터/반환 스키마
        if ctx.temp_dir is None:
            _emit_error(ctx, "Bilog 스크린샷 경로 생성 실패: temp_dir is not set")
            return StateResult.FAIL

        try:
            screenshot_path = finalize_sa_screenshot(
                source_path=ctx.temp_dir / _BILOG_SCREENSHOT_NAME,
                root_dir=ctx.screenshot_root_dir,
                model_name=ctx.model_name,
                test_case=ctx.current_case,
                events=ctx.events,
            )
        except Exception as exc:
            _emit_error(ctx, f"Bilog 스크린샷 최종 저장 실패: {exc}")
            return StateResult.FAIL

        result = BilogResult(screenshot_path=screenshot_path)
        return append_and_write_report(
            ctx,
            result,
            lambda writer: writer.write_bilog(ctx.current_case, result),
            "Bilog 리포트 작성 실패: write_bilog returned false",
        )

    def next_state(
        self, ctx: "SessionContext", result: StateResult
    ) -> str | None:
        if result is not StateResult.OK:
            return None
        return "ResetSwitchBox"
