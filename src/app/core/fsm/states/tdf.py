"""Band Group Factor 키워드 기반 TDF 자동 적용 상태."""
from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import TYPE_CHECKING

from app.core.fsm.base import State, StateResult
from app.core.fsm.equipment import is_equipment_connected
from app.core.fsm.states.measurement.common import measurement_start_state_for

if TYPE_CHECKING:
    from app.core.fsm.context import SessionContext

logger = logging.getLogger(__name__)


def resolve_tdf_file_name(
    tdf_file_names: Sequence[str],
    factor_keyword: str,
) -> str:
    """Factor 키워드를 포함하는 유일한 TDF 파일명을 반환한다."""

    if not factor_keyword:
        raise ValueError("Factor 키워드가 비어 있습니다.")

    matches = [
        file_name
        for file_name in tdf_file_names
        if factor_keyword in file_name
    ]
    if not matches:
        raise ValueError(
            f"Factor 키워드 '{factor_keyword}'와 일치하는 TDF 파일이 없습니다."
        )
    if len(matches) > 1:
        raise ValueError(
            f"Factor 키워드 '{factor_keyword}'와 일치하는 TDF 파일이 "
            f"{len(matches)}개입니다: {matches}"
        )
    return matches[0]


def _emit_error(ctx: "SessionContext", message: str) -> None:
    logger.error(message)
    if ctx.events is not None:
        ctx.events.error.emit(message)


def _emit_active_tdf_file_changed(
    ctx: "SessionContext",
    tdf_file_name: str,
) -> None:
    if ctx.events is None:
        return
    signal = getattr(ctx.events, "active_tdf_file_changed", None)
    if signal is not None:
        signal.emit(tdf_file_name)


def _emit_tdf_file_list_changed(
    ctx: "SessionContext",
    tdf_file_names: Sequence[str],
) -> None:
    if ctx.events is None:
        return
    signal = getattr(ctx.events, "tdf_file_list_changed", None)
    if signal is not None:
        signal.emit(list(tdf_file_names))


class ApplyTdfState(State):
    """현재 Test Case의 Factor에 맞는 TDF를 측정 전에 적용한다."""

    name = "ApplyTdf"

    def run(self, ctx: "SessionContext") -> StateResult:
        factor_keyword = ctx.current_case.factor_keyword
        if ctx.last_applied_factor_keyword == factor_keyword:
            logger.info("동일 Factor TDF 적용 생략: %s", factor_keyword)
            return StateResult.OK

        if not is_equipment_connected(ctx, "FSV40"):
            logger.warning(
                "TDF 자동 적용 스킵: FSV40이 선택 또는 연결되지 않았습니다."
            )
            return StateResult.OK

        try:
            tdf_file_names = ctx.commands.get_tdf_list(ctx.client)
            _emit_tdf_file_list_changed(ctx, tdf_file_names)
            tdf_file_name = resolve_tdf_file_name(
                tdf_file_names,
                factor_keyword,
            )
            applied = ctx.commands.set_tdf(
                ctx.client,
                tdf_file_name=tdf_file_name,
            )
        except Exception as exc:
            _emit_error(ctx, f"TDF 자동 적용 실패: {exc}")
            return StateResult.FAIL

        if not applied:
            _emit_error(
                ctx,
                "TDF 자동 적용 실패: "
                f"set_tdf returned false ({tdf_file_name})",
            )
            return StateResult.FAIL

        ctx.last_applied_factor_keyword = factor_keyword
        _emit_active_tdf_file_changed(ctx, tdf_file_name)
        logger.info(
            "TDF 자동 적용 완료: Factor=%s, file=%s",
            factor_keyword,
            tdf_file_name,
        )
        return StateResult.OK

    def next_state(
        self, ctx: "SessionContext", result: StateResult
    ) -> str | None:
        if result is not StateResult.OK:
            return None
        return measurement_start_state_for(ctx.current_case.test_type)
