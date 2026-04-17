"""시험 간 전환 상태: AntPolChange, Handover, RecallChange, DUTAxisChange."""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.fsm.base import State, StateResult

if TYPE_CHECKING:
    from app.core.fsm.context import SessionContext


class AntPolChangeState(State):
    """안테나 편파(Ant Pol) 변경. 시험원이 물리적으로 변경 후 확인.

    변경 후 Call 연결 상태를 확인하여:
    - Call 유지 시 → MeasureFundamental로 전이
    - Call 끊김 시 → NRCallDisconnected로 전이
    """

    name = "AntPolChange"

    def run(self, ctx: "SessionContext") -> StateResult:
        # calls: ctx.events.user_action_required.emit("Ant Pol 변경: H → V")
        # TODO(spec): 사용자 확인 대기 → Call 상태 확인
        raise NotImplementedError("spec TODO")

    def next_state(
        self, ctx: "SessionContext", result: StateResult
    ) -> str | None:
        # TODO(spec): Call 연결 상태에 따라 분기
        # Call OK → "MeasureFundamental"
        # Call 끊김 → "NRCallDisconnected"
        raise NotImplementedError("spec TODO")


class HandoverState(State):
    """NR Band 간 Handover. Call을 유지한 채 Band를 전환한다.

    Handover 성공 시 → MeasureFundamental로 전이
    Handover 실패(Call 끊김) 시 → NRCallDisconnected로 전이
    """

    name = "Handover"

    def run(self, ctx: "SessionContext") -> StateResult:
        # calls: net.commands.handover(client, from_band=..., to_band=...)
        raise NotImplementedError("spec TODO")

    def next_state(
        self, ctx: "SessionContext", result: StateResult
    ) -> str | None:
        # TODO(spec): Handover 결과에 따라 분기
        # Call OK → "MeasureFundamental"
        # Call 끊김 → "NRCallDisconnected"
        raise NotImplementedError("spec TODO")


class RecallChangeState(State):
    """NR 장비 Recall file 변경. 시험원의 수동 조작을 요청한다.

    Band 변경 과정에서 Recall file 교체가 필요한 경우 사용.
    수동 조작 완료 후 NRCallConnect로 전이하여 풀 Setup + 재연결.
    """

    name = "RecallChange"

    def run(self, ctx: "SessionContext") -> StateResult:
        # calls: ctx.events.user_action_required.emit("Recall file 변경 필요")
        # TODO(spec): 사용자 확인 대기
        raise NotImplementedError("spec TODO")

    def next_state(
        self, ctx: "SessionContext", result: StateResult
    ) -> str | None:
        return "NRCallConnect"


class DUTAxisChangeState(State):
    """DUT Axis 변경. 시험원이 DUT의 Position을 전환 후 확인.

    수동 조작 완료 후 NRCallConnect로 전이하여 풀 Setup + 재연결.
    """

    name = "DUTAxisChange"

    def run(self, ctx: "SessionContext") -> StateResult:
        # calls: ctx.events.user_action_required.emit("DUT Axis 변경: X → Y")
        # TODO(spec): 사용자 확인 대기
        raise NotImplementedError("spec TODO")

    def next_state(
        self, ctx: "SessionContext", result: StateResult
    ) -> str | None:
        return "NRCallConnect"
