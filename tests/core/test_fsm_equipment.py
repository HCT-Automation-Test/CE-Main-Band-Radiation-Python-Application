from __future__ import annotations

from app.core.fsm.context import SessionContext
from app.core.fsm.equipment import is_equipment_connected


def _make_ctx() -> SessionContext:
    return SessionContext(queue=[], commands=object(), events=object())


def test_is_equipment_connected_returns_false_for_empty_state() -> None:
    ctx = _make_ctx()

    assert not is_equipment_connected(ctx, "FSV40")


def test_is_equipment_connected_returns_false_for_unknown_equipment() -> None:
    ctx = _make_ctx()
    ctx.equipment_state = {"FSV40": True}

    assert not is_equipment_connected(ctx, "Unknown Device")


def test_is_equipment_connected_returns_known_equipment_state() -> None:
    ctx = _make_ctx()
    ctx.equipment_state = {"FSV40": True, "MT8000A": False}

    assert is_equipment_connected(ctx, "FSV40")
    assert not is_equipment_connected(ctx, "MT8000A")
    assert not is_equipment_connected(ctx, "CO3000")
