"""NR 연결 관리 상태: NRCallConnect, NRCallDisconnected."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.core.fsm.base import State, StateResult
from app.core.fsm.states.measurement.common import measurement_start_state_for
from app.models.nr_channel_lookup import resolve_call_channel
from app.models.switch_box import parse_band_number

if TYPE_CHECKING:
    from app.core.fsm.context import SessionContext

logger = logging.getLogger(__name__)


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
        test_case = ctx.current_case
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
        if result is not StateResult.OK:
            return None
        return measurement_start_state_for(ctx.current_case.test_type)


class NRCallDisconnectedState(State):
    """시험 중 NR Call이 끊어진 경우. 시험원의 수동 조작을 요청한다.

    시험원이 DUT 비행기 모드 On/Off 후 시험을 재개하면
    NRCallConnect로 전이하여 재연결한다.
    """

    name = "NRCallDisconnected"

    def run(self, ctx: "SessionContext") -> StateResult:
        # calls: ctx.events.user_action_required.emit("비행기 모드 On/Off 후 확인")
        # TODO(spec): 사용자 확인 대기 메커니즘
        raise NotImplementedError("spec TODO")

    def next_state(
        self, ctx: "SessionContext", result: StateResult
    ) -> str | None:
        return "NRCallConnect"
