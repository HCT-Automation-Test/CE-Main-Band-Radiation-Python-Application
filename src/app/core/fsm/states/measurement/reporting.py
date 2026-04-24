"""측정 결과 리포트 작성 보조 함수."""
from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

from app.core.fsm.base import StateResult
from app.models.measurement_result import MeasurementResult

if TYPE_CHECKING:
    from app.core.fsm.context import SessionContext
    from app.report.report_writer import ReportWriter

logger = logging.getLogger(__name__)


def append_and_write_report(
    ctx: "SessionContext",
    result: MeasurementResult,
    write_report: Callable[["ReportWriter"], bool],
    false_message: str,
) -> StateResult:
    """결과 히스토리에 추가한 뒤, writer가 있으면 리포트에 기록한다."""
    ctx.results.append(result)

    writer = ctx.report_writer
    if writer is None:
        return StateResult.OK

    try:
        written = write_report(writer)
    except Exception as exc:
        _emit_error(ctx, f"리포트 작성 실패: {exc}")
        return StateResult.FAIL

    if written:
        return StateResult.OK

    _emit_error(ctx, false_message)
    return StateResult.FAIL


def _emit_error(ctx: "SessionContext", message: str) -> None:
    logger.error(message)
    if ctx.events is not None:
        ctx.events.error.emit(message)
