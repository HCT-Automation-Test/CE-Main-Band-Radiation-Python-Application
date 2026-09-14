"""LTE Call, Handover 및 공통 전환 FSM 테스트."""
from __future__ import annotations

import threading
import time
from types import SimpleNamespace
from typing import Any

import pytest

from app.core.fsm.base import StateResult
from app.core.fsm.call_routing import handover_entry_state_for_case
from app.core.fsm.context import SessionContext
from app.core.fsm.engine import build_session_engine
from app.core.fsm.states.lte_setup import (
    LTECallConnectState,
    LTECallDisconnectedState,
)
from app.core.fsm.states.measurement.common import (
    PrepareFundamentalSwitchBoxBeforeCallState,
    SetupSpectrumAnalyzerStartupLevelState,
)
from app.core.fsm.states.session import CheckNextCaseState
from app.core.fsm.states.transition import (
    LTEHandoverState,
    RecallChangeState,
    TestTypeChangeState,
)
from app.models.enums import (
    AntennaPol,
    DUTAntPosition,
    DUTAxis,
    Generation,
    LTEBand,
    LTERBAllocation,
    Modulation,
    TestChannel as ChannelEnum,
    TestType as MeasurementTestType,
)
from app.models.test_case import TestCase


class _SignalRecorder:
    def __init__(self) -> None:
        self.values: list[Any] = []

    def emit(self, value: Any = None) -> None:
        self.values.append(value)


class _Events:
    def __init__(self) -> None:
        self.error = _SignalRecorder()
        self.user_action_required = _SignalRecorder()
        self.tc_started = _SignalRecorder()
        self.tc_finished = _SignalRecorder()
        self.current_case_changed = _SignalRecorder()


class _Commands:
    def __init__(
        self,
        *,
        call_connected: bool = True,
        call_exception: Exception | None = None,
        handover_configured: bool = True,
        handover_exception: Exception | None = None,
        status_connected: bool = True,
        recall_connected: bool = True,
    ) -> None:
        self.call_connected = call_connected
        self.call_exception = call_exception
        self.handover_configured = handover_configured
        self.handover_exception = handover_exception
        self.status_connected = status_connected
        self.recall_connected = recall_connected
        self.call_calls: list[tuple[Any, dict[str, Any]]] = []
        self.handover_calls: list[tuple[Any, dict[str, Any]]] = []
        self.status_calls: list[Any] = []
        self.recall_calls: list[tuple[Any, dict[str, Any]]] = []
        self.command_sequence: list[str] = []

    def setup_lte_mt8000(self, client: Any, **params: Any) -> bool:
        self.call_calls.append((client, params))
        self.command_sequence.append("setup_lte_mt8000")
        if self.call_exception is not None:
            raise self.call_exception
        return self.call_connected

    def lte_call_handover(self, client: Any, **params: Any) -> bool:
        self.handover_calls.append((client, params))
        if self.handover_exception is not None:
            raise self.handover_exception
        return self.handover_configured

    def check_call_status(self, client: Any) -> bool:
        self.status_calls.append(client)
        self.command_sequence.append("check_call_status")
        return self.status_connected

    def recall_param(self, client: Any, **params: Any) -> bool:
        self.recall_calls.append((client, params))
        self.command_sequence.append("recall_param")
        return self.recall_connected


def _make_case(
    *,
    band: LTEBand = LTEBand.B1,
    bandwidth: float = 10.0,
    test_type: MeasurementTestType = MeasurementTestType.INBAND,
    rb_allocation: LTERBAllocation = LTERBAllocation.MID,
    test_channel: ChannelEnum = ChannelEnum.MID,
    antenna_pol: AntennaPol = AntennaPol.H,
    dut_axis: DUTAxis = DUTAxis.X,
) -> TestCase:
    return TestCase(
        generation=Generation.LTE,
        band=band,
        bandwidth=bandwidth,
        test_type=test_type,
        modulation=Modulation.QPSK,
        rb_allocation=rb_allocation,
        test_channel=test_channel,
        antenna_pol=antenna_pol,
        dut_axis=dut_axis,
        dut_ant_position=DUTAntPosition.LOWER,
    )


def _make_ctx(
    case: TestCase,
    *,
    commands: _Commands | None = None,
    queue: list[TestCase] | None = None,
    current_index: int = 0,
    waiting_time: int = 5,
) -> tuple[SessionContext, _Commands, _Events, object]:
    client = object()
    command_facade = commands or _Commands()
    events = _Events()
    case_queue = queue or [case]
    ctx = SessionContext(
        queue=case_queue,
        commands=command_facade,
        events=events,  # type: ignore[arg-type]
        client=client,
        current_index=current_index,
        settings=SimpleNamespace(connection_waiting_time_sec=waiting_time),
        equipment_state={"MT8000A": True},
        last_applied_recall_id=case_queue[0].mt8000_recall,
    )
    return ctx, command_facade, events, client


def _complete_user_action(ctx: SessionContext) -> threading.Thread:
    def complete() -> None:
        time.sleep(0.02)
        ctx.user_action_completed.set()

    thread = threading.Thread(target=complete, daemon=True)
    thread.start()
    return thread


def test_lte_call_routing_uses_lte_states_for_all_measurement_entries() -> None:
    direct_call_contexts = [
        _make_ctx(_make_case(test_type=test_type))[0]
        for test_type in (
            MeasurementTestType.INBAND,
            MeasurementTestType.BILOG,
        )
    ]
    harmonic_ctx, _, _, _ = _make_ctx(
        _make_case(test_type=MeasurementTestType.HARMONIC)
    )

    for ctx in direct_call_contexts:
        assert (
            SetupSpectrumAnalyzerStartupLevelState().next_state(
                ctx, StateResult.OK
            )
            == "LTECallConnect"
        )
    assert (
        PrepareFundamentalSwitchBoxBeforeCallState().next_state(
            harmonic_ctx, StateResult.OK
        )
        == "LTECallConnect"
    )
    assert (
        handover_entry_state_for_case(direct_call_contexts[0].current_case)
        == "LTEHandover"
    )


def test_lte_call_connect_passes_current_case_params_and_waiting_time() -> None:
    case = _make_case(
        band=LTEBand.B1,
        bandwidth=10.0,
        rb_allocation=LTERBAllocation.HIGH,
        test_channel=ChannelEnum.HIGH,
    )
    ctx, commands, events, client = _make_ctx(case, waiting_time=7)
    state = LTECallConnectState()

    result = state.run(ctx)

    assert result is StateResult.OK
    assert state.next_state(ctx, result) == "ApplyTdf"
    assert commands.call_calls == [
        (
            client,
            {
                "bw": 10.0,
                "ul_channel": 18550,
                "rb_offset": 49,
                "waiting_time": 7,
            },
        )
    ]
    assert events.error.values == []


def test_lte_call_connect_continues_pending_transition() -> None:
    ctx, _, _, _ = _make_ctx(_make_case())
    ctx.pending_transition_states = ["AntPolChange"]
    state = LTECallConnectState()

    result = state.run(ctx)

    assert result is StateResult.OK
    assert state.next_state(ctx, result) == "AntPolChange"
    assert ctx.pending_transition_states == []


def test_lte_call_connect_failure_routes_to_lte_recovery() -> None:
    commands = _Commands(call_connected=False)
    ctx, _, events, _ = _make_ctx(_make_case(), commands=commands)
    state = LTECallConnectState()

    result = state.run(ctx)

    assert result is StateResult.FAIL
    assert state.next_state(ctx, result) == "LTECallDisconnected"
    assert events.error.values == [
        "LTE Call 연결 실패: setup_lte_mt8000 returned false"
    ]


def test_lte_call_connect_exception_routes_to_lte_recovery() -> None:
    commands = _Commands(call_exception=RuntimeError("instrument timeout"))
    ctx, _, events, _ = _make_ctx(_make_case(), commands=commands)
    state = LTECallConnectState()

    result = state.run(ctx)

    assert result is StateResult.FAIL
    assert state.next_state(ctx, result) == "LTECallDisconnected"
    assert events.error.values == ["LTE Call 연결 실패: instrument timeout"]


def test_lte_call_connect_without_equipment_routes_to_lte_recovery() -> None:
    ctx, commands, events, _ = _make_ctx(_make_case())
    ctx.equipment_state = {"MT8000A": False}
    state = LTECallConnectState()

    result = state.run(ctx)

    assert result is StateResult.FAIL
    assert state.next_state(ctx, result) == "LTECallDisconnected"
    assert commands.call_calls == []
    assert events.error.values == [
        "LTE Call 연결 스킵: MT8000A가 연결되어 있지 않습니다."
    ]


def test_lte_call_disconnected_uses_nr_message_and_retries_lte_call() -> None:
    ctx, _, events, _ = _make_ctx(_make_case())
    state = LTECallDisconnectedState()
    thread = _complete_user_action(ctx)

    result = state.run(ctx)
    thread.join(timeout=1.0)

    assert result is StateResult.OK
    assert events.user_action_required.values == ["비행기 모드 On/Off 후 확인"]
    assert state.next_state(ctx, result) == "LTECallConnect"


def test_lte_handover_uses_current_dl_and_ul_channel_params() -> None:
    prev_case = _make_case(band=LTEBand.B1, bandwidth=10.0)
    current_case = _make_case(
        band=LTEBand.B3,
        bandwidth=10.0,
        rb_allocation=LTERBAllocation.HIGH,
        test_channel=ChannelEnum.HIGH,
    )
    ctx, commands, events, client = _make_ctx(
        current_case,
        queue=[prev_case, current_case],
        current_index=1,
        waiting_time=9,
    )
    state = LTEHandoverState()

    result = state.run(ctx)

    assert result is StateResult.OK
    assert state.next_state(ctx, result) == "ApplyTdf"
    assert commands.handover_calls == [
        (
            client,
            {
                "bw": 10.0,
                "dl_channel": 1900,
                "ul_channel": 19900,
                "rb_offset": 49,
                "waiting_time": 9,
            },
        )
    ]
    assert events.error.values == []


def test_lte_handover_failure_routes_to_lte_recovery() -> None:
    commands = _Commands(handover_configured=False)
    prev_case = _make_case(band=LTEBand.B1)
    current_case = _make_case(band=LTEBand.B3)
    ctx, _, events, _ = _make_ctx(
        current_case,
        commands=commands,
        queue=[prev_case, current_case],
        current_index=1,
    )
    state = LTEHandoverState()

    result = state.run(ctx)

    assert result is StateResult.FAIL
    assert state.next_state(ctx, result) == "LTECallDisconnected"
    assert events.error.values == [
        "LTE Handover 실패: lte_call_handover returned false"
    ]


def test_lte_band_change_routes_by_recall() -> None:
    same_recall = [_make_case(band=LTEBand.B1), _make_case(band=LTEBand.B3)]
    changed_recall = [_make_case(band=LTEBand.B7), _make_case(band=LTEBand.B38)]

    same_ctx, _, _, _ = _make_ctx(same_recall[0], queue=same_recall)
    same_state = CheckNextCaseState()
    same_result = same_state.run(same_ctx)

    changed_ctx, _, _, _ = _make_ctx(changed_recall[0], queue=changed_recall)
    changed_state = CheckNextCaseState()
    changed_result = changed_state.run(changed_ctx)

    assert same_state.next_state(same_ctx, same_result) == "LTEHandover"
    assert changed_state.next_state(changed_ctx, changed_result) == "RecallChange"
    assert changed_ctx.pending_transition_states == ["LTECallConnect"]


@pytest.mark.parametrize(
    "case_changes",
    [
        {"bandwidth": 5.0},
        {"test_channel": ChannelEnum.HIGH},
        {"rb_allocation": LTERBAllocation.HIGH},
    ],
    ids=["bandwidth", "channel", "rb"],
)
def test_lte_same_band_routes_call_config_change_to_handover(
    case_changes: dict[str, Any],
) -> None:
    cases = [_make_case(), _make_case(**case_changes)]
    ctx, _, _, _ = _make_ctx(cases[0], queue=cases)
    state = CheckNextCaseState()

    result = state.run(ctx)

    assert result is StateResult.OK
    assert state.next_state(ctx, result) == "LTEHandover"


def test_lte_same_call_config_does_not_handover() -> None:
    cases = [_make_case(), _make_case()]
    ctx, _, _, _ = _make_ctx(cases[0], queue=cases)
    state = CheckNextCaseState()

    result = state.run(ctx)

    assert result is StateResult.OK
    assert state.next_state(ctx, result) == "ApplyTdf"


def test_lte_combined_changes_preserve_nr_transition_order() -> None:
    cases = [
        _make_case(
            band=LTEBand.B1,
            test_type=MeasurementTestType.BILOG,
            antenna_pol=AntennaPol.H,
            dut_axis=DUTAxis.X,
        ),
        _make_case(
            band=LTEBand.B3,
            test_type=MeasurementTestType.HARMONIC,
            antenna_pol=AntennaPol.V,
            dut_axis=DUTAxis.Y,
        ),
    ]
    ctx, _, _, _ = _make_ctx(cases[0], queue=cases)
    state = CheckNextCaseState()

    result = state.run(ctx)

    assert state.next_state(ctx, result) == "LTEHandover"
    assert ctx.pending_transition_states == [
        "DUTAxisChange",
        "AntPolChange",
        "TestTypeChange",
    ]


def test_lte_recall_change_checks_call_then_runs_lte_call() -> None:
    cases = [_make_case(band=LTEBand.B7), _make_case(band=LTEBand.B38)]
    ctx, commands, events, client = _make_ctx(
        cases[1],
        queue=cases,
        current_index=1,
    )
    ctx.pending_transition_states = ["LTECallConnect"]
    state = RecallChangeState()

    result = state.run(ctx)

    assert result is StateResult.OK
    assert state.next_state(ctx, result) == "LTECallConnect"
    assert LTECallConnectState().run(ctx) is StateResult.OK
    assert commands.command_sequence == [
        "recall_param",
        "setup_lte_mt8000",
    ]
    assert commands.recall_calls == [
        (client, {"recall_name": cases[1].mt8000_recall})
    ]
    assert commands.status_calls == []
    assert ctx.last_applied_recall_id == cases[1].mt8000_recall
    assert events.user_action_required.values == []


def test_lte_recall_disconnected_updates_id_and_uses_single_recovery_call() -> None:
    cases = [_make_case(band=LTEBand.B7), _make_case(band=LTEBand.B38)]
    commands = _Commands(recall_connected=False)
    ctx, _, events, _ = _make_ctx(
        cases[1],
        commands=commands,
        queue=cases,
        current_index=1,
    )
    ctx.pending_transition_states = ["LTECallConnect", "AntPolChange"]
    state = RecallChangeState()

    result = state.run(ctx)

    assert result is StateResult.OK
    assert ctx.last_applied_recall_id == cases[1].mt8000_recall
    assert events.error.values == []
    assert state.next_state(ctx, result) == "LTECallDisconnected"
    assert ctx.pending_transition_states == ["AntPolChange"]
    assert (
        LTECallDisconnectedState().next_state(ctx, StateResult.OK)
        == "LTECallConnect"
    )
    assert LTECallConnectState().next_state(ctx, StateResult.OK) == "AntPolChange"
    assert ctx.pending_transition_states == []


def test_lte_test_type_failure_routes_to_lte_recovery_with_lte_message() -> None:
    commands = _Commands(status_connected=False)
    ctx, _, events, _ = _make_ctx(_make_case(), commands=commands)
    state = TestTypeChangeState()

    result = state.run(ctx)

    assert result is StateResult.FAIL
    assert state.next_state(ctx, result) == "LTECallDisconnected"
    assert events.error.values == [
        "LTE Call 끊김 감지: check_call_status returned disconnected"
    ]


def test_session_engine_registers_lte_states() -> None:
    ctx, _, _, _ = _make_ctx(_make_case())

    engine = build_session_engine(ctx)

    assert {"LTECallConnect", "LTECallDisconnected", "LTEHandover"} <= set(
        engine._states  # noqa: SLF001 - 등록 상태 검증 목적
    )
