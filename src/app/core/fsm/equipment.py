"""챔버 현장 테스트용 FSM 장비 상태 helper."""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.instrument_connection import REQUIRED_EQUIPMENT_NAMES

if TYPE_CHECKING:
    from app.core.fsm.context import SessionContext


KNOWN_EQUIPMENT_NAMES = frozenset(REQUIRED_EQUIPMENT_NAMES)


def is_equipment_connected(ctx: "SessionContext", equipment_name: str) -> bool:
    """선택 연결된 known 장비가 현재 사용 가능한지 확인한다."""

    if not ctx.equipment_state:
        return True
    if equipment_name not in KNOWN_EQUIPMENT_NAMES:
        return False
    return bool(ctx.equipment_state.get(equipment_name))


def connected_known_equipment(states: dict[str, object]) -> dict[str, bool]:
    """known 장비 상태만 추려 bool 값으로 정규화한다."""

    return {
        name: bool(states[name])
        for name in REQUIRED_EQUIPMENT_NAMES
        if name in states
    }
