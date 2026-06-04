"""연속 전환 상태 흐름 헬퍼."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.fsm.context import SessionContext


def next_transition_or(ctx: "SessionContext", fallback_state: str) -> str:
    return ctx.pop_pending_transition_state() or fallback_state
