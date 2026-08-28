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
    InitialTurntableZeroState,
    PrepareFundamentalSwitchBoxBeforeCallState,
    PrepareFundamentalSwitchBoxState,
    RotateTurntableState,
    SetupSpectrumAnalyzerStartupLevelState,
    measurement_start_state_for,
)
from app.core.fsm.states.measurement.bilog import MeasureBilogManualState, MeasureBilogState
from app.core.fsm.states.measurement.harmonic import (
    MeasureHarmonicPrecisionState,
    MeasureFundamentalState,
    MeasureHarmonicsManualState,
    MeasureHarmonicsState,
)
from app.core.fsm.states.measurement.inband import MeasureInBandManualState, MeasureInBandState
from app.core.fsm.states.nr_setup import NRCallConnectState
from app.core.fsm.states.session import IdleState
from app.core.fsm.states.transition import AntPolChangeState
from app.models.enums import (
    AntennaPol,
    DUTAxis,
    Generation,
    LTEBand,
    Modulation,
    NRBand,
    RBAllocation,
    TestChannel,
    TestType,
)
from app.models.measurement_result import HarmonicPrecisionCandidate
from app.models.test_case import TestCase


def _make_case(
    test_type: TestType, generation: Generation = Generation.NR_SA
) -> TestCase:
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
        generation=generation,
        anchor_band=LTEBand.B1 if generation is Generation.NR_NSA else None,
    )


def _make_ctx(
    test_type: TestType, generation: Generation = Generation.NR_SA
) -> SessionContext:
    return SessionContext(
        queue=[_make_case(test_type, generation)],
        commands=None,
        events=None,  # type: ignore[arg-type]
    )


@pytest.mark.parametrize(
    ("test_type", "expected"),
    [
        (TestType.HARMONIC, "ApplyTdf"),
        (TestType.INBAND, "ApplyTdf"),
        (TestType.BILOG, "ApplyTdf"),
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


@pytest.mark.parametrize(("start_index", "current_index"), [(0, 0), (1, 1)])
def test_first_nsa_case_routes_directly_to_nr_call(
    start_index: int,
    current_index: int,
) -> None:
    cases = [
        _make_case(TestType.HARMONIC, Generation.NR_NSA),
        _make_case(TestType.HARMONIC, Generation.NR_NSA),
    ]
    ctx = SessionContext(
        queue=cases,
        commands=None,
        events=None,  # type: ignore[arg-type]
        start_index=start_index,
        current_index=current_index,
    )

    assert (
        PrepareFundamentalSwitchBoxBeforeCallState().next_state(ctx, StateResult.OK)
        == "NRCallConnect"
    )


def test_measure_fundamental_goes_to_set_switch_box() -> None:
    ctx = _make_ctx(TestType.HARMONIC)
    assert MeasureFundamentalState().next_state(ctx, StateResult.OK) == "SetSwitchBox"


def test_setup_spectrum_analyzer_startup_level_goes_to_nr_call_connect() -> None:
    ctx = _make_ctx(TestType.HARMONIC)
    assert (
        SetupSpectrumAnalyzerStartupLevelState().next_state(ctx, StateResult.OK)
        == "PrepareFundamentalSwitchBoxBeforeCall"
    )


def test_fundamental_switch_box_prepare_routes_to_expected_next_state() -> None:
    ctx = _make_ctx(TestType.HARMONIC)

    assert (
        PrepareFundamentalSwitchBoxBeforeCallState().next_state(ctx, StateResult.OK)
        == "NRCallConnect"
    )
    assert (
        PrepareFundamentalSwitchBoxState().next_state(ctx, StateResult.OK)
        == "MeasureFundamental"
    )


def test_idle_routes_through_report_preparation_before_turntable_zero() -> None:
    ctx = _make_ctx(TestType.HARMONIC)

    assert IdleState().next_state(ctx, StateResult.OK) == "PrepareReport"
    assert (
        InitialTurntableZeroState().next_state(ctx, StateResult.OK)
        == "AntPolChange"
    )
    assert (
        AntPolChangeState().next_state(ctx, StateResult.OK)
        == "SetupSpectrumAnalyzerStartupLevel"
    )


@pytest.mark.parametrize(
    ("state_factory", "test_type", "expected"),
    [
        (MeasureHarmonicPrecisionState, TestType.HARMONIC, "ResetSwitchBox"),
        (MeasureInBandState, TestType.INBAND, "ResetSwitchBox"),
        (MeasureInBandManualState, TestType.INBAND, "ResetSwitchBox"),
        (MeasureBilogState, TestType.BILOG, "ResetSwitchBox"),
        (MeasureBilogManualState, TestType.BILOG, "ResetSwitchBox"),
    ],
)
def test_measurement_states_route_to_expected_next_state(
    state_factory: type, test_type: TestType, expected: str
) -> None:
    ctx = _make_ctx(test_type)
    assert state_factory().next_state(ctx, StateResult.OK) == expected


def test_measure_harmonics_routes_to_reset_switch_box_without_precision_candidates() -> None:
    ctx = _make_ctx(TestType.HARMONIC)

    assert MeasureHarmonicsState().next_state(ctx, StateResult.OK) == "ResetSwitchBox"


def test_measure_harmonics_routes_to_precision_with_candidates() -> None:
    ctx = _make_ctx(TestType.HARMONIC)
    ctx.harmonic_precision_candidates = [
        HarmonicPrecisionCandidate(
            order=2,
            amplitude_dbm=-32.5,
            peak_frequency_mhz=7088.35,
        )
    ]

    assert (
        MeasureHarmonicsState().next_state(ctx, StateResult.OK)
        == "MeasureHarmonicPrecision"
    )


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
    assert (
        measurement_start_state_for(
            TestType.HARMONIC,
            after_rotate=True,
            manual_marker=True,
        )
        == "MeasureHarmonicsManual"
    )
    assert (
        measurement_start_state_for(
            TestType.INBAND,
            after_rotate=True,
            manual_marker=True,
        )
        == "MeasureInBandManual"
    )
    assert (
        measurement_start_state_for(
            TestType.BILOG,
            after_rotate=True,
            manual_marker=True,
        )
        == "MeasureBilogManual"
    )


def test_build_session_engine_registers_all_states_without_duplicates() -> None:
    ctx = _make_ctx(TestType.HARMONIC)
    engine = build_session_engine(ctx)

    expected_state_names = {
        "SessionInit",
        "Idle",
        "PrepareReport",
        "CheckNextCase",
        "TestEnd",
        "NRCallConnect",
        "NRCallDisconnected",
        "ApplyTdf",
        "AntPolChange",
        "Handover",
        "NSAHandover",
        "RecallChange",
        "DUTAxisChange",
        "TestTypeChange",
        "InitialTurntableZero",
        "SetupSpectrumAnalyzerStartupLevel",
        "PrepareFundamentalSwitchBoxBeforeCall",
        "PrepareFundamentalSwitchBox",
        "SetSwitchBox",
        "SetupSpectrumAnalyzer",
        "RotateTurntable",
        "ResetSwitchBox",
        "MeasureFundamental",
        "MeasureHarmonics",
        "MeasureHarmonicsManual",
        "MeasureHarmonicPrecision",
        "MeasureInBand",
        "MeasureInBandManual",
        "MeasureBilog",
        "MeasureBilogManual",
    }
    registered = set(engine._states.keys())  # noqa: SLF001 — 내부 등록 확인 목적
    assert expected_state_names <= registered, (
        f"등록 누락: {expected_state_names - registered}"
    )
    assert "LTECallAnchorBeforeNRCall" not in registered
    assert "LTECallAnchorBeforeHandover" not in registered

