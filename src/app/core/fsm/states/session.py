"""세션 제어 상태: Init, Idle, CheckNextCase, TestEnd."""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.fsm.base import State, StateResult

if TYPE_CHECKING:
    from app.core.fsm.context import SessionContext


class SessionInitState(State):
    """모든 장비 연결 상태를 확인한다."""

    name = "SessionInit"

    def run(self, ctx: "SessionContext") -> StateResult:
        # TODO(spec): 장비 4종(MT8000A, FSV40, SwitchBox, CO3000) 연결 확인
        raise NotImplementedError("spec TODO")

    def next_state(
        self, ctx: "SessionContext", result: StateResult
    ) -> str | None:
        return "Idle"


class IdleState(State):
    """시험 시작 대기 상태. 사용자가 TC 큐를 구성한 뒤 시험을 시작한다."""

    name = "Idle"

    def run(self, ctx: "SessionContext") -> StateResult:
        # TODO(spec): 사용자 시험 시작 이벤트 대기
        raise NotImplementedError("spec TODO")

    def next_state(
        self, ctx: "SessionContext", result: StateResult
    ) -> str | None:
        return "NRCallConnect"


class CheckNextCaseState(State):
    """다음 TC 정보를 확인하고 적절한 전환 상태로 분기한다."""

    name = "CheckNextCase"

    def run(self, ctx: "SessionContext") -> StateResult:
        # TODO(spec): 현재 TC 결과 저장, 다음 TC 존재 여부 확인
        raise NotImplementedError("spec TODO")

    def next_state(
        self, ctx: "SessionContext", result: StateResult
    ) -> str | None:
        # TODO(spec): prev/curr TC 비교 후 분기 (위에서부터 우선순위)
        # - 큐 종료 → "TestEnd"
        # - Band 변경 + Recall 필요 → "RecallChange"
        # - Band 변경 → "Handover"
        # - DUT Axis 변경 → "DUTAxisChange"
        # - AntPol 변경 → "AntPolChange"
        # - test_type만 변경 → "TestTypeChange"
        # - 모두 동일 → TODO(spec): 동일 설정 재측정 시나리오
        raise NotImplementedError("spec TODO")


class TestEndState(State):
    """모든 시험이 완료되었음을 알린다. Idle로 복귀."""

    name = "TestEnd"

    def run(self, ctx: "SessionContext") -> StateResult:
        # TODO(spec): 최종 결과 집계, 리포트 생성 트리거
        raise NotImplementedError("spec TODO")

    def next_state(
        self, ctx: "SessionContext", result: StateResult
    ) -> str | None:
        return "Idle"
