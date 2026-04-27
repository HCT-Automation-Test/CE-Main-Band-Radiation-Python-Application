from __future__ import annotations

from typing import Any

from app.core.fsm.base import StateResult
from app.core.fsm.context import SessionContext
from app.core.fsm.states.nr_setup import NRCallConnectState
from app.models.enums import (
    AntennaPol,
    DUTAxis,
    Modulation,
    NRBand,
    RBAllocation,
    TestChannel as ChannelEnum,
    TestType as MeasurementTestType,
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


class _Commands:
    def __init__(self, connected: bool) -> None:
        self.connected = connected
        self.calls: list[tuple[Any, dict[str, Any]]] = []

    def setup_mt8000(self, client: Any, **params: Any) -> bool:
        self.calls.append((client, params))
        return self.connected


def _make_case() -> TestCase:
    return TestCase(
        band=NRBand.N78,
        bandwidth=100.0,
        test_type=MeasurementTestType.HARMONIC,
        modulation=Modulation.QPSK,
        rb_allocation=RBAllocation.INNER_FULL,
        test_channel=ChannelEnum.MID,
        antenna_pol=AntennaPol.H,
        dut_axis=DUTAxis.X,
    )


def test_nr_call_connect_calls_setup_mt8000_with_current_case_params() -> None:
    commands = _Commands(connected=True)
    client = object()
    ctx = SessionContext(
        queue=[_make_case()],
        commands=commands,
        events=_Events(),  # type: ignore[arg-type]
        client=client,
    )

    result = NRCallConnectState().run(ctx)

    assert result is StateResult.OK
    assert commands.calls == [
        (
            client,
            {
                "band": 78,
                "bw": 100,
                "modulation": Modulation.QPSK,
                "rb_size": 135,
                "rb_offset": 67,
                "channel": 636666,
            },
        )
    ]


def test_nr_call_connect_returns_fail_and_emits_error_on_false_result() -> None:
    commands = _Commands(connected=False)
    events = _Events()
    ctx = SessionContext(
        queue=[_make_case()],
        commands=commands,
        events=events,  # type: ignore[arg-type]
    )
    state = NRCallConnectState()

    result = state.run(ctx)

    assert result is StateResult.FAIL
    assert state.next_state(ctx, result) is None
    assert events.error.messages == [
        "NR Call 연결 실패: setup_mt8000 returned false"
    ]
