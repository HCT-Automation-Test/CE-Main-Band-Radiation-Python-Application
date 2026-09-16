"""Generation별 Call/Handover 진입 상태 라우팅 helper."""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.models.enums import Generation

if TYPE_CHECKING:
    from app.core.fsm.context import SessionContext
    from app.models.test_case import TestCase


def call_entry_state_for_case(case: "TestCase") -> str:
    """TestCase generation에 맞는 Call 진입 state를 반환한다."""

    if case.generation is Generation.LTE:
        return "LTECallConnect"
    if case.generation is Generation.NR_NSA:
        return "NSACallConnect"
    return "NRCallConnect"


def call_entry_state_for(ctx: "SessionContext") -> str:
    """현재 TestCase의 generation에 맞는 Call 진입 state를 반환한다."""

    return call_entry_state_for_case(ctx.current_case)


def initial_call_entry_state_for(ctx: "SessionContext") -> str:
    """첫 실행 TestCase의 generation에 맞는 Call 진입 state를 반환한다."""

    if ctx.current_case.generation is Generation.NR_NSA:
        return "NSACallConnect"
    return call_entry_state_for(ctx)


def handover_entry_state_for_case(case: "TestCase") -> str:
    """TestCase generation에 맞는 Handover 진입 state를 반환한다."""

    if case.generation is Generation.LTE:
        return "LTEHandover"
    return "Handover"


def handover_entry_state_for(ctx: "SessionContext") -> str:
    """현재 TestCase의 generation에 맞는 Handover 진입 state를 반환한다."""

    return handover_entry_state_for_case(ctx.current_case)


def call_disconnected_state_for(ctx: "SessionContext") -> str:
    """현재 TestCase의 generation에 맞는 Call 복구 state를 반환한다."""

    if ctx.current_case.generation is Generation.LTE:
        return "LTECallDisconnected"
    return "NRCallDisconnected"
