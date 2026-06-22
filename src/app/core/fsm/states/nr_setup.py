"""NR 연결 관리 상태: NRCallConnect, NRCallDisconnected."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.core.fsm.base import State, StateResult
from app.core.fsm.equipment import is_equipment_connected
from app.core.fsm.states.measurement.common import measurement_start_state_for
from app.core.fsm.transition_flow import next_transition_or
from app.models.enums import TestType
from app.models.nr_channel_lookup import resolve_call_channel
from app.models.switch_box import parse_band_number

if TYPE_CHECKING:
    from app.core.fsm.context import SessionContext

logger = logging.getLogger(__name__)
_DEFAULT_CONNECTION_WAITING_TIME_SEC = 5
_USER_ACTION_WAIT_INTERVAL_SEC = 0.1


def _emit_error(ctx: "SessionContext", message: str) -> None:
    logger.error(message)
    if ctx.events is not None:
        ctx.events.error.emit(message)


class NRCallConnectState(State):
    """MT8000A 풀 Setup 및 NR Call 연결.

    기존 SetupMT8000State + CallConnectState를 통합한다.
    어떤 경로로 진입하든 항상 풀 Setup + 신규 연결을 수행한다.
    """

    name = "NRCallConnect"

    def run(self, ctx: "SessionContext") -> StateResult:
        if not is_equipment_connected(ctx, "MT8000A"):
            _emit_error(ctx, "NR Call 연결 스킵: MT8000A가 연결되어 있지 않습니다.")
            return StateResult.FAIL

        test_case = ctx.current_case
        waiting_time = _DEFAULT_CONNECTION_WAITING_TIME_SEC
        if ctx.settings is not None:
            waiting_time = ctx.settings.connection_waiting_time_sec
        try:
            band = parse_band_number(test_case.band.value)
            bw = int(test_case.bandwidth)
            channel = resolve_call_channel(
                test_case.band,
                test_case.bandwidth,
                test_case.test_channel,
            )
            connected = ctx.commands.setup_mt8000(
                ctx.client,
                band=band,
                bw=bw,
                modulation=test_case.modulation,
                rb_size=test_case.rb_size,
                rb_offset=test_case.rb_offset,
                channel=channel,
                waiting_time=waiting_time,
            )
        except Exception as exc:
            _emit_error(ctx, f"NR Call 연결 실패: {exc}")
            return StateResult.FAIL

        if connected:
            return StateResult.OK

        _emit_error(ctx, "NR Call 연결 실패: setup_mt8000 returned false")
        return StateResult.FAIL

    def next_state(
        self, ctx: "SessionContext", result: StateResult
    ) -> str | None:
        if result is StateResult.OK:
            if ctx.current_case.test_type is TestType.HARMONIC:
                return next_transition_or(ctx, "MeasureFundamental")
            return next_transition_or(
                ctx,
                measurement_start_state_for(ctx.current_case.test_type),
            )
        if result is StateResult.FAIL:
            return "NRCallDisconnected"
        return None


class NRCallDisconnectedState(State):
    """시험 중 NR Call이 끊어진 경우. 시험원의 수동 조작을 요청한다.

    시험원이 DUT 비행기 모드 On/Off 후 시험을 재개하면
    NRCallConnect로 전이하여 재연결한다.
    """

    name = "NRCallDisconnected"

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
        return "NRCallConnect"
