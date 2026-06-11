"""Bilog 측정 상태.

공유 스텝 (SetSwitchBox / SetupSpectrumAnalyzer / RotateTurntable / ResetSwitchBox)
은 `measurement.common`에 정의되어 있다. Bilog는 MeasureFundamental 단계 없이
공유 스텝을 거쳐 `MeasureBilog`에서 실제 측정을 수행한다.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from app.core.fsm.base import State, StateResult
from app.core.fsm.equipment import is_equipment_connected
from app.core.fsm.states.measurement.reporting import append_and_write_report
from app.models.measurement_result import BilogResult

if TYPE_CHECKING:
    from app.core.fsm.context import SessionContext

_BILOG_SCREENSHOT_NAME = "inband.png"

logger = logging.getLogger(__name__)


def _emit_error(ctx: "SessionContext", message: str) -> None:
    logger.error(message)
    if ctx.events is not None:
        ctx.events.error.emit(message)


def _remove_stale_screenshot(path: Path) -> None:
    """측정 전 기존 스크린샷을 지워 stale 파일 오판을 막는다."""
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        raise ValueError(f"stale 스크린샷 삭제 실패: {path}") from exc


def _recordable_peak(level_dbm: float, threshold_dbm: float) -> float | None:
    if level_dbm > threshold_dbm:
        return level_dbm
    return None


class MeasureBilogState(State):
    """Bilog 측정. RotateTurntable 이후 진입, 완료 시 ResetSwitchBox로 복귀."""

    name = "MeasureBilog"

    def run(self, ctx: "SessionContext") -> StateResult:
        if not is_equipment_connected(ctx, "FSV40"):
            _emit_error(ctx, "Bilog 측정 스킵: FSV40이 연결되어 있지 않습니다.")
            return StateResult.OK

        if ctx.temp_dir is None:
            _emit_error(ctx, "Bilog 스크린샷 경로 생성 실패: temp_dir is not set")
            return StateResult.FAIL

        screenshot_path = ctx.temp_dir / _BILOG_SCREENSHOT_NAME
        threshold_dbm = ctx.current_case.range_definition.limit - 10.0
        try:
            _remove_stale_screenshot(screenshot_path)
            amplitude_dbm = float(
                ctx.commands.measure_bilog(
                    ctx.client,
                    limit=threshold_dbm,
                )
            )
        except Exception as exc:
            _emit_error(ctx, f"Bilog 측정 실패: {exc}")
            return StateResult.FAIL

        if not screenshot_path.is_file():
            _emit_error(
                ctx,
                f"Bilog 스크린샷 저장 실패: {screenshot_path} does not exist",
            )
            return StateResult.FAIL

        result = BilogResult(
            screenshot_path=screenshot_path,
            bilog_peak_level_dbm=_recordable_peak(amplitude_dbm, threshold_dbm),
        )
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
