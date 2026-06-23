"""NR SA/NSA call setup routing helpers."""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.models.enums import Generation

if TYPE_CHECKING:
    from app.core.fsm.context import SessionContext
    from app.models.test_case import TestCase


def nr_call_entry_state_for_case(case: "TestCase") -> str:
    """TestCase generation에 맞는 NR Call 진입 state를 반환한다."""

    if case.generation is Generation.NR_NSA:
        return "LTECallAnchorBeforeNRCall"
    return "NRCallConnect"


def nr_call_entry_state_for(ctx: "SessionContext") -> str:
    """현재 TestCase의 generation에 맞는 NR Call 진입 state를 반환한다."""

    return nr_call_entry_state_for_case(ctx.current_case)


def handover_entry_state_for_case(case: "TestCase") -> str:
    """TestCase generation에 맞는 Handover 진입 state를 반환한다."""

    if case.generation is Generation.NR_NSA:
        return "LTECallAnchorBeforeHandover"
    return "Handover"


def handover_entry_state_for(ctx: "SessionContext") -> str:
    """현재 TestCase의 generation에 맞는 Handover 진입 state를 반환한다."""

    return handover_entry_state_for_case(ctx.current_case)