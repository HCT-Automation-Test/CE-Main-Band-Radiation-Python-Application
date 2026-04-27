from __future__ import annotations

from typing import Any

from app.core.fsm.base import StateResult
from app.core.fsm.context import SessionContext
from app.core.fsm.states.measurement.common import (
    ResetSwitchBoxState,
    SetSwitchBoxState,
    SetupSpectrumAnalyzerState,
)
from app.models.enums import (
    AntennaPol,
    DUTAxis,
    FilterPath,
    InputPath,
    Modulation,
    NRBand,
    RBAllocation,
    TestChannel as ChannelEnum,
    TestType as MeasurementTestType,
)
from app.models.test_case import TestCase
from app.models.test_range import TestRange


class _SignalRecorder:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def emit(self, message: str) -> None:
        self.messages.append(message)


class _Events:
    def __init__(self) -> None:
        self.error = _SignalRecorder()


class _Commands:
    def __init__(self, *, switch_box_configured: bool = True, sa_configured: bool = True) -> None:
        self.switch_box_configured = switch_box_configured
        self.sa_configured = sa_configured
        self.switch_box_calls: list[tuple[Any, dict[str, Any]]] = []
        self.setup_sa_calls: list[tuple[Any, TestRange]] = []

    def set_switch_box(self, client: Any, **params: Any) -> bool:
        self.switch_box_calls.append((client, params))
        return self.switch_box_configured

    def setup_sa(self, client: Any, *, test_range: TestRange) -> bool:
        self.setup_sa_calls.append((client, test_range))
        return self.sa_configured


def _make_case(test_type: MeasurementTestType) -> TestCase:
    return TestCase(
        band=NRBand.N78,
        bandwidth=100.0,
        test_type=test_type,
        modulation=Modulation.QPSK,
        rb_allocation=RBAllocation.INNER_FULL,
        test_channel=ChannelEnum.MID,
        antenna_pol=AntennaPol.H,
        dut_axis=DUTAxis.X,
    )


def test_set_switch_box_uses_hpf_filter_path_from_range_definition() -> None:
    commands = _Commands()
    client = object()
    ctx = SessionContext(
        queue=[_make_case(MeasurementTestType.HARMONIC)],
        commands=commands,
        events=_Events(),  # type: ignore[arg-type]
        client=client,
    )

    result = SetSwitchBoxState().run(ctx)

    assert result is StateResult.OK
    assert commands.switch_box_calls == [
        (
            client,
            {
                "input_path": InputPath.INPUT3,
                "filter_path": FilterPath.HPF_6G,
            },
        )
    ]


def test_set_switch_box_resolves_brf_filter_path_by_band() -> None:
    commands = _Commands()
    client = object()
    ctx = SessionContext(
        queue=[_make_case(MeasurementTestType.INBAND)],
        commands=commands,
        events=_Events(),  # type: ignore[arg-type]
        client=client,
    )

    result = SetSwitchBoxState().run(ctx)

    assert result is StateResult.OK
    assert commands.switch_box_calls == [
        (
            client,
            {
                "input_path": InputPath.INPUT3,
                "filter_path": FilterPath.PORT_14,
            },
        )
    ]


def test_set_switch_box_returns_fail_and_stops_on_false_result() -> None:
    commands = _Commands(switch_box_configured=False)
    events = _Events()
    ctx = SessionContext(
        queue=[_make_case(MeasurementTestType.HARMONIC)],
        commands=commands,
        events=events,  # type: ignore[arg-type]
    )
    state = SetSwitchBoxState()

    result = state.run(ctx)

    assert result is StateResult.FAIL
    assert state.next_state(ctx, result) is None
    assert events.error.messages == [
        "Switch Box RF 경로 설정 실패: set_switch_box returned false"
    ]


def test_setup_spectrum_analyzer_uses_current_case_test_range() -> None:
    commands = _Commands()
    client = object()
    case = _make_case(MeasurementTestType.HARMONIC)
    ctx = SessionContext(
        queue=[case],
        commands=commands,
        events=_Events(),  # type: ignore[arg-type]
        client=client,
    )

    result = SetupSpectrumAnalyzerState().run(ctx)

    assert result is StateResult.OK
    assert commands.setup_sa_calls == [(client, case.range_definition)]
    test_range = commands.setup_sa_calls[0][1]
    assert test_range.start_freq == 6000.0
    assert test_range.stop_freq == 18000.0
    assert test_range.rbw == 1.0
    assert test_range.vbw == 3.0
    assert test_range.limit == -30.0
    assert test_range.sweep_point == 30001


def test_setup_spectrum_analyzer_returns_fail_and_stops_on_false_result() -> None:
    commands = _Commands(sa_configured=False)
    events = _Events()
    ctx = SessionContext(
        queue=[_make_case(MeasurementTestType.HARMONIC)],
        commands=commands,
        events=events,  # type: ignore[arg-type]
    )
    state = SetupSpectrumAnalyzerState()

    result = state.run(ctx)

    assert result is StateResult.FAIL
    assert state.next_state(ctx, result) is None
    assert events.error.messages == [
        "Spectrum Analyzer 설정 실패: setup_sa returned false"
    ]


def test_reset_switch_box_uses_input1_and_thru() -> None:
    commands = _Commands()
    client = object()
    ctx = SessionContext(
        queue=[_make_case(MeasurementTestType.HARMONIC)],
        commands=commands,
        events=_Events(),  # type: ignore[arg-type]
        client=client,
    )

    result = ResetSwitchBoxState().run(ctx)

    assert result is StateResult.OK
    assert commands.switch_box_calls == [
        (
            client,
            {
                "input_path": InputPath.INPUT1,
                "filter_path": FilterPath.THRU,
            },
        )
    ]


def test_reset_switch_box_returns_fail_and_stops_on_false_result() -> None:
    commands = _Commands(switch_box_configured=False)
    events = _Events()
    ctx = SessionContext(
        queue=[_make_case(MeasurementTestType.HARMONIC)],
        commands=commands,
        events=events,  # type: ignore[arg-type]
    )
    state = ResetSwitchBoxState()

    result = state.run(ctx)

    assert result is StateResult.FAIL
    assert state.next_state(ctx, result) is None
    assert events.error.messages == [
        "Switch Box 기본 경로 복원 실패: set_switch_box returned false"
    ]
