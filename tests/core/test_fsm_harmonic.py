from __future__ import annotations

import pytest

from app.core.fsm.base import State, StateResult
from app.core.fsm.context import SessionContext
from app.core.fsm.engine import FSMEngine, build_session_engine


@pytest.mark.skip(reason="spec TODO: 세션 FSM 상세 명세 확정 후")
def test_session_init_to_idle() -> None:
    """SessionInit → Idle 전이 확인."""
    ...


@pytest.mark.skip(reason="spec TODO: 세션 FSM 상세 명세 확정 후")
def test_harmonic_measurement_chain() -> None:
    """MeasureFundamental → ... → ResetSwitchBox → CheckNextCase 전이 확인."""
    ...


@pytest.mark.skip(reason="spec TODO: 세션 FSM 상세 명세 확정 후")
def test_check_next_case_transitions() -> None:
    """CheckNextCase에서 AntPolChange/Handover/RecallChange/DUTAxisChange 분기 확인."""
    ...


@pytest.mark.skip(reason="spec TODO: 세션 FSM 상세 명세 확정 후")
def test_nr_call_disconnected_recovery() -> None:
    """NRCallDisconnected → NRCallConnect 복구 확인."""
    ...
