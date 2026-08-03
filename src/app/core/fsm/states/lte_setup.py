"""LTE 연결 관리 상태: LTECallConnect, LTECallDisconnected."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.core.fsm.base import State, StateResult
from app.core.fsm.equipment import is_equipment_connected
from app.core.fsm.transition_flow import next_transition_or

if TYPE_CHECKING:
    from app.core.fsm.context import SessionContext

logger = logging.getLogger(__name__)
_DEFAULT_CONNECTION_WAITING_TIME_SEC = 5
_USER_ACTION_WAIT_INTERVAL_SEC = 0.1


def _emit_error(ctx: "SessionContext", message: str) -> None:
    logger.error(message)
    if ctx.events is not None:
        ctx.events.error.emit(message)


class LTECallConnectState(State):
    """현재 LTE Test Case 설정으로 MT8000A Call을 연결한다."""

    name = "LTECallConnect"

    def run(self, ctx: "SessionContext") -> StateResult:
        if not is_equipment_connected(ctx, "MT8000A"):
            _emit_error(ctx, "LTE Call 연결 스킵: MT8000A가 연결되어 있지 않습니다.")
            return StateResult.FAIL

        test_case = ctx.current_case
        waiting_time = _DEFAULT_CONNECTION_WAITING_TIME_SEC
        if ctx.settings is not None:
            waiting_time = ctx.settings.connection_waiting_time_sec

        try:
            connected = ctx.commands.setup_lte_mt8000(
                ctx.client,
                bw=test_case.bandwidth,
                ul_channel=test_case.channel_number,
                rb_offset=test_case.rb_offset,
                waiting_time=waiting_time,
            )
        except Exception as exc:
            _emit_error(ctx, f"LTE Call 연결 실패: {exc}")
            return StateResult.FAIL

        if connected:
            return StateResult.OK

        _emit_error(ctx, "LTE Call 연결 실패: setup_lte_mt8000 returned false")
        return StateResult.FAIL

    def next_state(
        self, ctx: "SessionContext", result: StateResult
    ) -> str | None:
        if result is StateResult.OK:
            return next_transition_or(ctx, "ApplyTdf")
        if result is StateResult.FAIL:
            return "LTECallDisconnected"
        return None


class LTECallDisconnectedState(State):
    """LTE Call 단절 시 NR과 동일한 시험원 수동 복구를 요청한다."""

    name = "LTECallDisconnected"

    def run(self, ctx: "SessionContext") -> StateResult:
        ctx.user_action_completed.clear()
        if ctx.events is not None:
            ctx.events.user_action_required.emit("비행기 모드 On/Off 후 확인")

        while not ctx.stopped and not ctx.current_case_stop_requested:
            if ctx.user_action_completed.wait(_USER_ACTION_WAIT_INTERVAL_SEC):
                if ctx.stopped or ctx.current_case_stop_requested:
                    return StateResult.FAIL
                ctx.user_action_completed.clear()
                return StateResult.OK

        return StateResult.FAIL

    def next_state(
        self, ctx: "SessionContext", result: StateResult
    ) -> str | None:
        if result is not StateResult.OK:
            return None
        return "LTECallConnect"
