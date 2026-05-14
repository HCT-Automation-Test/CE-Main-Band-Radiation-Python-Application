from __future__ import annotations

from typing import Any

import pytest

from app.core.fsm.base import StateResult
from app.core.fsm.context import SessionContext
from app.core.fsm.states.transition import AntPolChangeState
from app.models.enums import (
    AntennaPol,
    DUTAntPosition,
    DUTAxis,
    Modulation,
    NRBand,
    RBAllocation,
    TestChannel as NRTestChannel,
    TestType as NRTestType,
)
from app.models.test_case import TestCase


class _SignalRecorder:
    def __init__(self) -> None:
        self.messages: list[Any] = []

    def emit(self, message: Any) -> None:
        self.messages.append(message)


class _Events:
    def __init__(self) -> None:
        self.error = _SignalRecorder()
        self.polarization_info_changed = _SignalRecorder()


class _Commands:
    def __init__(
        self,
        *,
        configured: bool = True,
        exception: Exception | None = None,
    ) -> None:
        self.configured = configured
        self.exception = exception
        self.calls: list[tuple[Any, dict[str, Any]]] = []

    def set_antenna_pol(self, client: Any, **params: Any) -> bool:
        self.calls.append((client, params))
        if self.exception is not None:
            raise self.exception
        return self.configured


def _make_case(
    *,
    band: NRBand = NRBand.N78,
    bandwidth: float = 100.0,
    test_type: NRTestType = NRTestType.HARMONIC,
    antenna_pol: AntennaPol = AntennaPol.H,
) -> TestCase:
    return TestCase(
        band=band,
        bandwidth=bandwidth,
        test_type=test_type,
        modulation=Modulation.QPSK,
        rb_allocation=RBAllocation.INNER_FULL,
        test_channel=NRTestChannel.MID,
        antenna_pol=antenna_pol,
        dut_axis=DUTAxis.X,
        dut_ant_position=DUTAntPosition.UPPER,
    )


def _make_ctx(
    case: TestCase,
    *,
    commands: _Commands | None = None,
) -> tuple[SessionContext, _Commands, _Events, object]:
    client = object()
    events = _Events()
    command_facade = commands if commands is not None else _Commands()
    ctx = SessionContext(
        queue=[case],
        commands=command_facade,
        events=events,  # type: ignore[arg-type]
        client=client,
    )
    return ctx, command_facade, events, client


@pytest.mark.parametrize(
    ("test_type", "expected"),
    [
        (NRTestType.HARMONIC, "MeasureFundamental"),
        (NRTestType.INBAND, "SetSwitchBox"),
        (NRTestType.BILOG, "SetSwitchBox"),
    ],
)
def test_ant_pol_change_uses_temporary_measurement_start_route(
    test_type: NRTestType,
    expected: str,
) -> None:
    ctx, _, _, _ = _make_ctx(_make_case(test_type=test_type))
    state = AntPolChangeState()

    assert state.next_state(ctx, StateResult.OK) == expected
    assert state.next_state(ctx, StateResult.FAIL) is None


@pytest.mark.parametrize(
    ("case", "expected_message"),
    [
        (
            _make_case(
                band=NRBand.N1,
                bandwidth=20.0,
                test_type=NRTestType.HARMONIC,
                antenna_pol=AntennaPol.H,
            ),
            {"polarization_3m": "H", "polarization_1m": "H"},
        ),
        (
            _make_case(
                band=NRBand.N1,
                bandwidth=20.0,
                test_type=NRTestType.HARMONIC,
                antenna_pol=AntennaPol.V,
            ),
            {"polarization_3m": "V", "polarization_1m": "V"},
        ),
        (
            _make_case(
                band=NRBand.N1,
                bandwidth=20.0,
                test_type=NRTestType.BILOG,
                antenna_pol=AntennaPol.H,
            ),
            {"polarization_3m": "H", "polarization_1m": "H"},
        ),
        (
            _make_case(
                band=NRBand.N1,
                bandwidth=20.0,
                test_type=NRTestType.BILOG,
                antenna_pol=AntennaPol.V,
            ),
            {"polarization_3m": "V", "polarization_1m": "V"},
        ),
        (
            _make_case(test_type=NRTestType.HARMONIC, antenna_pol=AntennaPol.V),
            {"polarization_bilog": "0°"},
        ),
        (
            _make_case(test_type=NRTestType.HARMONIC, antenna_pol=AntennaPol.H),
            {"polarization_bilog": "90°"},
        ),
    ],
)
def test_ant_pol_change_sets_pol_and_emits_display_info_for_current_hook(
    case: TestCase,
    expected_message: dict[str, str],
) -> None:
    ctx, commands, events, client = _make_ctx(case)
    input_path = case.range_definition.input_path
    pol = case.antenna_pol

    result = AntPolChangeState().run(ctx)

    assert result is StateResult.OK
    assert commands.calls == [
        (client, {"pol": pol, "input_path": input_path}),
    ]
    assert events.polarization_info_changed.messages == [expected_message]
    assert events.error.messages == []


def test_ant_pol_change_does_not_emit_display_info_on_false_result() -> None:
    command_facade = _Commands(configured=False)
    case = _make_case(
        band=NRBand.N1,
        bandwidth=20.0,
        test_type=NRTestType.HARMONIC,
    )
    ctx, _, events, _ = _make_ctx(case, commands=command_facade)

    result = AntPolChangeState().run(ctx)

    assert result is StateResult.FAIL
    assert events.polarization_info_changed.messages == []
    assert events.error.messages == [
        "Antenna Pol 설정 실패: set_antenna_pol returned false"
    ]


def test_ant_pol_change_does_not_emit_display_info_on_exception() -> None:
    command_facade = _Commands(exception=RuntimeError("instrument timeout"))
    case = _make_case(
        band=NRBand.N1,
        bandwidth=20.0,
        test_type=NRTestType.HARMONIC,
    )
    ctx, _, events, _ = _make_ctx(case, commands=command_facade)

    result = AntPolChangeState().run(ctx)

    assert result is StateResult.FAIL
    assert events.polarization_info_changed.messages == []
    assert events.error.messages == ["Antenna Pol 설정 실패: instrument timeout"]
