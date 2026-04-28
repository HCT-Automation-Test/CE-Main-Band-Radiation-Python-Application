"""FSM 라우팅 테스트.

각 상태의 `next_state()`가 test_type에 따라 올바른 다음 상태 이름을 반환하는지
확인한다. `run()` 본문은 spec TODO이므로 호출하지 않으며, 명세 확정과 독립적으로
통과해야 한다.
"""
from __future__ import annotations

import pytest

from app.core.fsm.base import StateResult
from app.core.fsm.context import SessionContext
from app.core.fsm.engine import build_session_engine
from app.core.fsm.states.measurement.common import (
    RotateTurntableState,
    measurement_start_state_for,
)
from app.core.fsm.states.measurement.bilog import MeasureBilogState
from app.core.fsm.states.measurement.harmonic import (
    MeasureFundamentalState,
    MeasureHarmonicsState,
)
from app.core.fsm.states.measurement.inband import MeasureInBandState
from app.core.fsm.states.nr_setup import NRCallConnectState
from app.models.enums import (
    AntennaPol,
    DUTAxis,
    Modulation,
    NRBand,
    RBAllocation,
    TestChannel,
    TestType,
)
from app.models.test_case import TestCase


def _make_case(test_type: TestType) -> TestCase:
    """3타입 모두 지원하는 Band(n78)로 TestCase를 생성한다."""
    return TestCase(
        band=NRBand.N78,
        bandwidth=100.0,
        test_type=test_type,
        modulation=Modulation.QPSK,
        rb_allocation=RBAllocation.INNER_FULL,
        test_channel=TestChannel.MID,
        antenna_pol=AntennaPol.H,
        dut_axis=DUTAxis.X,
        dut_ant_position="Upper",
    )


def _make_ctx(test_type: TestType) -> SessionContext:
    return SessionContext(
        queue=[_make_case(test_type)],
        commands=None,
        events=None,  # type: ignore[arg-type]
    )


@pytest.mark.parametrize(
    ("test_type", "expected"),
    [
        (TestType.HARMONIC, "MeasureFundamental"),
        (TestType.INBAND, "SetSwitchBox"),
        (TestType.BILOG, "SetSwitchBox"),
    ],
)
def test_nr_call_connect_branches_on_test_type(
    test_type: TestType, expected: str
) -> None:
    ctx = _make_ctx(test_type)
    assert NRCallConnectState().next_state(ctx, StateResult.OK) == expected


@pytest.mark.parametrize(
    ("test_type", "expected"),
    [
        (TestType.HARMONIC, "MeasureHarmonics"),
        (TestType.INBAND, "MeasureInBand"),
        (TestType.BILOG, "MeasureBilog"),
    ],
)
def test_rotate_turntable_branches_on_test_type(
    test_type: TestType, expected: str
) -> None:
    ctx = _make_ctx(test_type)
    assert RotateTurntableState().next_state(ctx, StateResult.OK) == expected


def test_measure_fundamental_goes_to_set_switch_box() -> None:
    ctx = _make_ctx(TestType.HARMONIC)
    assert MeasureFundamentalState().next_state(ctx, StateResult.OK) == "SetSwitchBox"


@pytest.mark.parametrize(
    ("state_factory", "test_type"),
    [
        (MeasureHarmonicsState, TestType.HARMONIC),
        (MeasureInBandState, TestType.INBAND),
        (MeasureBilogState, TestType.BILOG),
    ],
)
def test_measurement_states_return_to_reset_switch_box(
    state_factory: type, test_type: TestType
) -> None:
    ctx = _make_ctx(test_type)
    assert state_factory().next_state(ctx, StateResult.OK) == "ResetSwitchBox"


def test_measurement_start_state_for_helper() -> None:
    assert measurement_start_state_for(TestType.HARMONIC) == "MeasureFundamental"
    assert measurement_start_state_for(TestType.INBAND) == "SetSwitchBox"
    assert measurement_start_state_for(TestType.BILOG) == "SetSwitchBox"

    assert (
        measurement_start_state_for(TestType.HARMONIC, after_rotate=True)
        == "MeasureHarmonics"
    )
    assert (
        measurement_start_state_for(TestType.INBAND, after_rotate=True)
        == "MeasureInBand"
    )
    assert (
        measurement_start_state_for(TestType.BILOG, after_rotate=True)
        == "MeasureBilog"
    )


def test_build_session_engine_registers_all_states_without_duplicates() -> None:
    ctx = _make_ctx(TestType.HARMONIC)
    engine = build_session_engine(ctx)

    expected_state_names = {
        "SessionInit",
        "Idle",
        "CheckNextCase",
        "TestEnd",
        "NRCallConnect",
        "NRCallDisconnected",
        "AntPolChange",
        "Handover",
        "RecallChange",
        "DUTAxisChange",
        "TestTypeChange",
        "SetSwitchBox",
        "SetupSpectrumAnalyzer",
        "RotateTurntable",
        "ResetSwitchBox",
        "MeasureFundamental",
        "MeasureHarmonics",
        "MeasureInBand",
        "MeasureBilog",
    }
    registered = set(engine._states.keys())  # noqa: SLF001 — 내부 등록 확인 목적
    assert expected_state_names <= registered, (
        f"등록 누락: {expected_state_names - registered}"
    )
