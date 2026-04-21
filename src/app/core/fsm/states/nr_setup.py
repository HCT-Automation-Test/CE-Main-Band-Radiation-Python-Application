"""NR 연결 관리 상태: NRCallConnect, NRCallDisconnected."""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.fsm.base import State, StateResult
from app.core.fsm.states.measurement.common import measurement_start_state_for

if TYPE_CHECKING:
    from app.core.fsm.context import SessionContext


class NRCallConnectState(State):
    """MT8000A 풀 Setup 및 NR Call 연결.

    기존 SetupMT8000State + CallConnectState를 통합한다.
    어떤 경로로 진입하든 항상 풀 Setup + 신규 연결을 수행한다.
    """

    name = "NRCallConnect"

    def run(self, ctx: "SessionContext") -> StateResult:
        # calls: net.commands.setup_mt8000(client, band=..., bw=..., channel=..., ...)
        # calls: net.commands.call_connect(client)
        raise NotImplementedError("spec TODO")

    def next_state(
        self, ctx: "SessionContext", result: StateResult
    ) -> str | None:
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
