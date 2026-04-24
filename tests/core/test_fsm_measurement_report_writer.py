from __future__ import annotations

from typing import Any

import pytest

from app.core.fsm.base import StateResult
from app.core.fsm.context import SessionContext
from app.core.fsm.states.measurement.bilog import MeasureBilogState
from app.core.fsm.states.measurement.harmonic import (
    MeasureFundamentalState,
    MeasureHarmonicsState,
)
from app.core.fsm.states.measurement.inband import MeasureInBandState
from app.models.enums import (
    AntennaPol,
    DUTAxis,
    Modulation,
    NRBand,
    RBAllocation,
    TestChannel as ChannelEnum,
    TestType as MeasurementTestType,
)
from app.models.measurement_result import (
    BilogResult,
    FundamentalResult,
    HarmonicResult,
    InbandResult,
)
from app.models.test_case import TestCase


class _SignalRecorder:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def emit(self, message: str) -> None:
        self.messages.append(message)


class _Events:
    def __init__(self) -> None:
        self.error = _SignalRecorder()


class _ReportWriter:
    def __init__(
        self,
        *,
        return_value: bool = True,
        exception: Exception | None = None,
    ) -> None:
        self.return_value = return_value
        self.exception = exception
        self.calls: list[tuple[str, TestCase, object]] = []

    def write_fundamental(
        self,
        test_case: TestCase,
        result: FundamentalResult,
    ) -> bool:
        return self._record("fundamental", test_case, result)

    def write_harmonic(
        self,
        test_case: TestCase,
        result: HarmonicResult,
    ) -> bool:
        return self._record("harmonic", test_case, result)

    def write_inband(
        self,
        test_case: TestCase,
        result: InbandResult,
    ) -> bool:
        return self._record("inband", test_case, result)

    def write_bilog(
        self,
        test_case: TestCase,
        result: BilogResult,
    ) -> bool:
        return self._record("bilog", test_case, result)

    def _record(self, name: str, test_case: TestCase, result: object) -> bool:
        if self.exception is not None:
            raise self.exception
        self.calls.append((name, test_case, result))
        return self.return_value


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


def _make_ctx(
    test_type: MeasurementTestType,
    *,
    report_writer: Any | None = None,
    events: Any | None = None,
) -> SessionContext:
    return SessionContext(
        queue=[_make_case(test_type)],
        commands=None,
        events=events,  # type: ignore[arg-type]
        report_writer=report_writer,
    )


@pytest.mark.parametrize(
    ("state", "test_type", "expected_name", "expected_result_type"),
    [
        (
            MeasureFundamentalState(),
            MeasurementTestType.HARMONIC,
            "fundamental",
            FundamentalResult,
        ),
        (
            MeasureHarmonicsState(),
            MeasurementTestType.HARMONIC,
            "harmonic",
            HarmonicResult,
        ),
        (
            MeasureInBandState(),
            MeasurementTestType.INBAND,
            "inband",
            InbandResult,
        ),
        (MeasureBilogState(), MeasurementTestType.BILOG, "bilog", BilogResult),
    ],
)
def test_measurement_states_call_individual_report_writer_methods(
    state: Any,
    test_type: MeasurementTestType,
    expected_name: str,
    expected_result_type: type,
) -> None:
    report_writer = _ReportWriter()
    ctx = _make_ctx(test_type, report_writer=report_writer)

    result = state.run(ctx)

    assert result is StateResult.OK
    assert len(ctx.results) == 1
    assert isinstance(ctx.results[0], expected_result_type)
    assert report_writer.calls == [(expected_name, ctx.current_case, ctx.results[0])]


def test_measurement_state_returns_fail_when_report_writer_returns_false() -> None:
    report_writer = _ReportWriter(return_value=False)
    events = _Events()
    ctx = _make_ctx(
        MeasurementTestType.INBAND,
        report_writer=report_writer,
        events=events,
    )
    state = MeasureInBandState()

    result = state.run(ctx)

    assert result is StateResult.FAIL
    assert state.next_state(ctx, result) is None
    assert len(ctx.results) == 1
    assert events.error.messages == [
        "In-Band 리포트 작성 실패: write_inband returned false"
    ]


def test_measurement_state_returns_fail_when_report_writer_raises() -> None:
    report_writer = _ReportWriter(exception=RuntimeError("disk full"))
    events = _Events()
    ctx = _make_ctx(
        MeasurementTestType.BILOG,
        report_writer=report_writer,
        events=events,
    )
    state = MeasureBilogState()

    result = state.run(ctx)

    assert result is StateResult.FAIL
    assert state.next_state(ctx, result) is None
    assert len(ctx.results) == 1
    assert events.error.messages == ["리포트 작성 실패: disk full"]


@pytest.mark.parametrize(
    ("state", "test_type", "expected_result_type"),
    [
        (
            MeasureFundamentalState(),
            MeasurementTestType.HARMONIC,
            FundamentalResult,
        ),
        (MeasureHarmonicsState(), MeasurementTestType.HARMONIC, HarmonicResult),
        (MeasureInBandState(), MeasurementTestType.INBAND, InbandResult),
        (MeasureBilogState(), MeasurementTestType.BILOG, BilogResult),
    ],
)
def test_measurement_states_append_result_without_report_writer(
    state: Any,
    test_type: MeasurementTestType,
    expected_result_type: type,
) -> None:
    ctx = _make_ctx(test_type)

    result = state.run(ctx)

    assert result is StateResult.OK
    assert len(ctx.results) == 1
    assert isinstance(ctx.results[0], expected_result_type)
