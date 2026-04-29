from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.fsm.base import StateResult
from app.core.fsm.context import SessionContext
from app.core.fsm.states.session import (
    CheckNextCaseState,
    IdleState,
    SessionInitState,
    TestEndState,
)
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


class _SignalRecorder:
    def __init__(self) -> None:
        self.values: list[Any] = []

    def emit(self, value: Any) -> None:
        self.values.append(value)


class _Events:
    def __init__(self) -> None:
        self.error = _SignalRecorder()
        self.tc_started = _SignalRecorder()
        self.tc_finished = _SignalRecorder()


class _Client:
    def __init__(self) -> None:
        self.connect_calls: list[tuple[str, int]] = []

    def connect_to(self, host: str, port: int) -> None:
        self.connect_calls.append((host, port))


class _Commands:
    def __init__(self, response: object = True) -> None:
        self.response = response
        self.connect_calls: list[Any] = []

    def connect_equipment(self, client: Any) -> object:
        self.connect_calls.append(client)
        return self.response


def _make_case(
    test_type: TestType = TestType.HARMONIC,
    *,
    band: NRBand = NRBand.N78,
    antenna_pol: AntennaPol = AntennaPol.H,
    dut_axis: DUTAxis = DUTAxis.X,
) -> TestCase:
    return TestCase(
        band=band,
        bandwidth=100.0,
        test_type=test_type,
        modulation=Modulation.QPSK,
        rb_allocation=RBAllocation.INNER_FULL,
        test_channel=TestChannel.MID,
        antenna_pol=antenna_pol,
        dut_axis=dut_axis,
        dut_ant_position="Upper",
    )


def test_session_init_connects_client_and_equipment() -> None:
    events = _Events()
    client = _Client()
    commands = _Commands(response={"mt8000a": True, "fsv40": True})
    ctx = SessionContext(
        queue=[],
        commands=commands,
        events=events,  # type: ignore[arg-type]
        client=client,
        tcp_host="127.0.0.1",
        tcp_port=5025,
    )
    ctx.equipment_connect_requested.set()

    result = SessionInitState().run(ctx)

    assert result is StateResult.OK
    assert client.connect_calls == [("127.0.0.1", 5025)]
    assert commands.connect_calls == [client]
    assert ctx.equipment_state == {"mt8000a": True, "fsv40": True}


def test_session_init_retries_when_connection_fails() -> None:
    events = _Events()
    ctx = SessionContext(
        queue=[],
        commands=_Commands(response=False),
        events=events,  # type: ignore[arg-type]
        client=_Client(),
    )
    ctx.equipment_connect_requested.set()

    result = SessionInitState().run(ctx)

    assert result is StateResult.RETRY
    assert events.error.values == [
        "장비 연결 실패: connect_equipment returned false"
    ]


def test_session_init_retries_when_any_equipment_status_is_false() -> None:
    events = _Events()
    ctx = SessionContext(
        queue=[],
        commands=_Commands(response={"mt8000a": True, "fsv40": False}),
        events=events,  # type: ignore[arg-type]
        client=_Client(),
    )
    ctx.equipment_connect_requested.set()

    result = SessionInitState().run(ctx)

    assert result is StateResult.RETRY
    assert ctx.equipment_state == {"mt8000a": True, "fsv40": False}
    assert events.error.values == [
        "장비 연결 실패: connect_equipment returned false"
    ]


def test_idle_waits_for_start_request_and_validates_context(tmp_path: Path) -> None:
    events = _Events()
    ctx = SessionContext(
        queue=[_make_case()],
        commands=object(),
        events=events,  # type: ignore[arg-type]
        report_writer=object(),  # type: ignore[arg-type]
        temp_dir=tmp_path,
        model_name="SM-000",
        template_path=tmp_path / "template.xlsx",
        screenshot_root_dir=tmp_path / "screenshots",
    )
    ctx.test_start_requested.set()

    result = IdleState().run(ctx)

    assert result is StateResult.OK
    assert events.tc_started.values == [0]
    assert IdleState().next_state(ctx, result) == "NRCallConnect"


def test_idle_retries_without_report_writer(tmp_path: Path) -> None:
    events = _Events()
    ctx = SessionContext(
        queue=[_make_case()],
        commands=object(),
        events=events,  # type: ignore[arg-type]
        temp_dir=tmp_path,
        model_name="SM-000",
        template_path=tmp_path / "template.xlsx",
        screenshot_root_dir=tmp_path / "screenshots",
    )
    ctx.test_start_requested.set()

    result = IdleState().run(ctx)

    assert result is StateResult.RETRY
    assert events.error.values == ["시험 시작 실패: report_writer is not set"]


def test_check_next_case_advances_and_routes_by_test_type() -> None:
    events = _Events()
    ctx = SessionContext(
        queue=[_make_case(), _make_case(TestType.INBAND)],
        commands=object(),
        events=events,  # type: ignore[arg-type]
    )
    state = CheckNextCaseState()

    result = state.run(ctx)

    assert result is StateResult.OK
    assert ctx.current_index == 1
    assert events.tc_finished.values == [0]
    assert events.tc_started.values == [1]
    assert state.next_state(ctx, result) == "TestTypeChange"


def test_check_next_case_goes_to_test_end_at_queue_end() -> None:
    events = _Events()
    ctx = SessionContext(
        queue=[_make_case()],
        commands=object(),
        events=events,  # type: ignore[arg-type]
    )
    state = CheckNextCaseState()

    result = state.run(ctx)

    assert result is StateResult.OK
    assert state.next_state(ctx, result) == "TestEnd"
    assert events.tc_finished.values == [0]


def test_test_end_clears_queue_and_returns_to_idle() -> None:
    ctx = SessionContext(
        queue=[_make_case()],
        commands=object(),
        events=_Events(),  # type: ignore[arg-type]
        current_index=0,
        fundamental_frequency_mhz=3550.25,
    )
    state = TestEndState()

    result = state.run(ctx)

    assert result is StateResult.OK
    assert ctx.queue == []
    assert ctx.fundamental_frequency_mhz is None
    assert state.next_state(ctx, result) == "Idle"
