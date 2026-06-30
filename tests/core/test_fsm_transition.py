from __future__ import annotations

import threading
import time
from typing import Any

import pytest

from app.core.fsm.base import StateResult
from app.core.fsm.context import SessionContext
from app.core.fsm.states.transition import (
    AntPolChangeState,
    DUTAxisChangeState,
    HandoverState,
    RecallChangeState,
    TestTypeChangeState,
)
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
        self.user_action_required = _SignalRecorder()


class _Commands:
    def __init__(
        self,
        *,
        configured: bool = True,
        exception: Exception | None = None,
        handover_configured: bool = True,
        handover_exception: Exception | None = None,
        call_connected: bool = True,
        call_status_exception: Exception | None = None,
    ) -> None:
        self.configured = configured
        self.exception = exception
        self.calls: list[tuple[Any, dict[str, Any]]] = []
        self.handover_configured = handover_configured
        self.handover_exception = handover_exception
        self.handover_calls: list[tuple[Any, dict[str, Any]]] = []
        self.call_connected = call_connected
        self.call_status_exception = call_status_exception
        self.call_status_calls: list[Any] = []

    def set_antenna_pol(self, client: Any, **params: Any) -> bool:
        self.calls.append((client, params))
        if self.exception is not None:
            raise self.exception
        return self.configured

    def call_handover(self, client: Any, **params: Any) -> bool:
        self.handover_calls.append((client, params))
        if self.handover_exception is not None:
            raise self.handover_exception
        return self.handover_configured

    def check_call_status(self, client: Any) -> bool:
        self.call_status_calls.append(client)
        if self.call_status_exception is not None:
            raise self.call_status_exception
        return self.call_connected


def _make_case(
    *,
    band: NRBand = NRBand.N78,
    bandwidth: float = 100.0,
    test_type: NRTestType = NRTestType.HARMONIC,
    test_channel: NRTestChannel = NRTestChannel.MID,
    antenna_pol: AntennaPol = AntennaPol.H,
    dut_axis: DUTAxis = DUTAxis.X,
) -> TestCase:
    return TestCase(
        band=band,
        bandwidth=bandwidth,
        test_type=test_type,
        modulation=Modulation.QPSK,
        rb_allocation=RBAllocation.INNER_FULL,
        test_channel=test_channel,
        antenna_pol=antenna_pol,
        dut_axis=dut_axis,
        dut_ant_position=DUTAntPosition.UPPER,
    )


def _make_ctx(
    case: TestCase,
    *,
    commands: _Commands | None = None,
    queue: list[TestCase] | None = None,
    current_index: int = 0,
) -> tuple[SessionContext, _Commands, _Events, object]:
    client = object()
    events = _Events()
    command_facade = commands if commands is not None else _Commands()
    ctx = SessionContext(
        queue=queue if queue is not None else [case],
        commands=command_facade,
        events=events,  # type: ignore[arg-type]
        client=client,
        current_index=current_index,
    )
    ctx.equipment_state = {
        "CO3000": True,
        "3D Controller": True,
        "MT8000A": True,
    }
    return ctx, command_facade, events, client


def _make_axis_change_ctx() -> tuple[SessionContext, _Events]:
    events = _Events()
    ctx = SessionContext(
        queue=[
            _make_case(dut_axis=DUTAxis.X),
            _make_case(dut_axis=DUTAxis.Y),
        ],
        commands=_Commands(),
        events=events,  # type: ignore[arg-type]
        current_index=1,
    )
    return ctx, events


@pytest.mark.parametrize(
    ("test_type", "expected"),
    [
        (NRTestType.HARMONIC, "MeasureFundamental"),
        (NRTestType.INBAND, "SetSwitchBox"),
        (NRTestType.BILOG, "SetSwitchBox"),
    ],
)
def test_ant_pol_change_uses_test_type_measurement_route(
    test_type: NRTestType,
    expected: str,
) -> None:
    prev_case = _make_case(test_type=test_type, antenna_pol=AntennaPol.V)
    current_case = _make_case(test_type=test_type, antenna_pol=AntennaPol.H)
    ctx, _, _, _ = _make_ctx(
        current_case,
        queue=[prev_case, current_case],
        current_index=1,
    )
    state = AntPolChangeState()

    assert state.next_state(ctx, StateResult.OK) == expected
    assert state.next_state(ctx, StateResult.FAIL) is None


def test_handover_continues_to_pending_transition_before_measurement() -> None:
    prev_case = _make_case(band=NRBand.N77)
    current_case = _make_case(band=NRBand.N78)
    ctx, _, _, _ = _make_ctx(
        current_case,
        queue=[prev_case, current_case],
        current_index=1,
    )
    ctx.pending_transition_states = ["AntPolChange", "TestTypeChange"]

    assert HandoverState().next_state(ctx, StateResult.OK) == "AntPolChange"
    assert ctx.pending_transition_states == ["TestTypeChange"]


def test_ant_pol_change_continues_to_pending_transition_before_measurement() -> None:
    prev_case = _make_case(antenna_pol=AntennaPol.V)
    current_case = _make_case(antenna_pol=AntennaPol.H)
    ctx, _, _, _ = _make_ctx(
        current_case,
        queue=[prev_case, current_case],
        current_index=1,
    )
    ctx.pending_transition_states = ["TestTypeChange"]

    assert AntPolChangeState().next_state(ctx, StateResult.OK) == "TestTypeChange"
    assert ctx.pending_transition_states == []


def test_test_type_change_continues_to_measurement_after_pending_transitions() -> None:
    ctx, _, _, _ = _make_ctx(_make_case(test_type=NRTestType.INBAND))
    ctx.pending_transition_states = []

    assert TestTypeChangeState().next_state(ctx, StateResult.OK) == "SetSwitchBox"


def test_ant_pol_change_restarted_case_routes_to_initial_setup() -> None:
    prev_case = _make_case(antenna_pol=AntennaPol.V)
    current_case = _make_case(antenna_pol=AntennaPol.H)
    ctx, _, _, _ = _make_ctx(
        current_case,
        queue=[prev_case, current_case],
        current_index=1,
    )
    ctx.start_index = 1
    state = AntPolChangeState()

    assert state.next_state(ctx, StateResult.OK) == "SetupSpectrumAnalyzerStartupLevel"


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
            {"polarization_3m": "H"},
        ),
        (
            _make_case(
                band=NRBand.N1,
                bandwidth=20.0,
                test_type=NRTestType.HARMONIC,
                antenna_pol=AntennaPol.V,
            ),
            {"polarization_3m": "V"},
        ),
        (
            _make_case(
                band=NRBand.N1,
                bandwidth=20.0,
                test_type=NRTestType.BILOG,
                antenna_pol=AntennaPol.H,
            ),
            {"polarization_bilog": "H"},
        ),
        (
            _make_case(
                band=NRBand.N1,
                bandwidth=20.0,
                test_type=NRTestType.BILOG,
                antenna_pol=AntennaPol.V,
            ),
            {"polarization_bilog": "V"},
        ),
        (
            _make_case(test_type=NRTestType.HARMONIC, antenna_pol=AntennaPol.V),
            {"polarization_1m": "0°"},
        ),
        (
            _make_case(test_type=NRTestType.HARMONIC, antenna_pol=AntennaPol.H),
            {"polarization_1m": "90°"},
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


def test_ant_pol_change_skips_input3_when_3d_controller_is_not_connected() -> None:
    case = _make_case(
        band=NRBand.N78,
        bandwidth=100.0,
        test_type=NRTestType.HARMONIC,
    )
    ctx, commands, events, _ = _make_ctx(case)
    ctx.equipment_state = {"3D Controller": False}
    state = AntPolChangeState()

    result = state.run(ctx)

    assert result is StateResult.OK
    assert state.next_state(ctx, result) == "SetupSpectrumAnalyzerStartupLevel"
    assert commands.calls == []
    assert events.polarization_info_changed.messages == []
    assert events.error.messages


def test_ant_pol_change_skips_other_inputs_when_co3000_is_not_connected() -> None:
    case = _make_case(
        band=NRBand.N1,
        bandwidth=20.0,
        test_type=NRTestType.HARMONIC,
    )
    ctx, commands, events, _ = _make_ctx(case)
    ctx.equipment_state = {"CO3000": False}
    state = AntPolChangeState()

    result = state.run(ctx)

    assert result is StateResult.OK
    assert state.next_state(ctx, result) == "SetupSpectrumAnalyzerStartupLevel"
    assert commands.calls == []
    assert events.polarization_info_changed.messages == []
    assert events.error.messages


def test_ant_pol_change_does_not_emit_display_info_on_false_result() -> None:
    command_facade = _Commands(configured=False)
    case = _make_case(
        band=NRBand.N1,
        bandwidth=20.0,
        test_type=NRTestType.HARMONIC,
    )
    ctx, _, events, _ = _make_ctx(case, commands=command_facade)
    state = AntPolChangeState()

    result = state.run(ctx)

    assert result is StateResult.FAIL
    assert state.next_state(ctx, result) is None
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
    state = AntPolChangeState()

    result = state.run(ctx)

    assert result is StateResult.FAIL
    assert state.next_state(ctx, result) is None
    assert events.polarization_info_changed.messages == []
    assert events.error.messages == ["Antenna Pol 설정 실패: instrument timeout"]


def test_dut_axis_change_emits_user_action_and_waits_for_completion() -> None:
    ctx, events = _make_axis_change_ctx()
    state = DUTAxisChangeState()

    def complete_action() -> None:
        time.sleep(0.02)
        ctx.user_action_completed.set()

    threading.Thread(target=complete_action, daemon=True).start()

    result = state.run(ctx)

    assert result is StateResult.OK
    assert events.user_action_required.messages == ["DUT Axis 변경: X -> Y"]
    assert state.next_state(ctx, result) == "NRCallConnect"


def test_dut_axis_change_returns_fail_when_stopped_while_waiting() -> None:
    ctx, events = _make_axis_change_ctx()
    state = DUTAxisChangeState()

    def request_stop() -> None:
        time.sleep(0.02)
        ctx.stopped = True
        ctx.user_action_completed.set()

    threading.Thread(target=request_stop, daemon=True).start()

    result = state.run(ctx)

    assert result is StateResult.FAIL
    assert events.user_action_required.messages == ["DUT Axis 변경: X -> Y"]
    assert state.next_state(ctx, result) is None


def test_handover_calls_command_with_current_case_params() -> None:
    prev_case = _make_case(
        band=NRBand.N28,
        bandwidth=20.0,
    )
    current_case = _make_case(
        band=NRBand.N78,
        bandwidth=100.0,
        test_channel=NRTestChannel.HIGH,
    )
    ctx, commands, events, client = _make_ctx(
        current_case,
        queue=[prev_case, current_case],
        current_index=1,
    )
    state = HandoverState()

    result = state.run(ctx)

    assert result is StateResult.OK
    assert state.next_state(ctx, result) == "MeasureFundamental"
    assert commands.handover_calls == [
        (
            client,
            {
                "mid_channel": 145600,
                "band": 78,
                "bw": 100,
                "modulation": Modulation.QPSK,
                "rb_size": 135,
                "rb_offset": 67,
                "channel": 650000,
            },
        )
    ]
    assert events.error.messages == []


@pytest.mark.parametrize(
    ("test_type", "expected"),
    [
        (NRTestType.HARMONIC, "MeasureFundamental"),
        (NRTestType.INBAND, "SetSwitchBox"),
        (NRTestType.BILOG, "SetSwitchBox"),
    ],
)
def test_handover_routes_to_test_type_measurement_start(
    test_type: NRTestType,
    expected: str,
) -> None:
    prev_case = _make_case(band=NRBand.N77)
    current_case = _make_case(band=NRBand.N78, test_type=test_type)
    ctx, _, _, _ = _make_ctx(
        current_case,
        queue=[prev_case, current_case],
        current_index=1,
    )

    assert HandoverState().next_state(ctx, StateResult.OK) == expected


def test_handover_skips_when_mt8000a_is_not_connected() -> None:
    prev_case = _make_case(band=NRBand.N77)
    current_case = _make_case(band=NRBand.N78)
    ctx, commands, events, _ = _make_ctx(
        current_case,
        queue=[prev_case, current_case],
        current_index=1,
    )
    ctx.equipment_state = {"MT8000A": False}
    state = HandoverState()

    result = state.run(ctx)

    assert result is StateResult.FAIL
    assert state.next_state(ctx, result) == "NRCallDisconnected"
    assert commands.handover_calls == []
    assert events.error.messages


def test_handover_fails_when_previous_case_is_missing() -> None:
    ctx, commands, events, _ = _make_ctx(_make_case())
    state = HandoverState()

    result = state.run(ctx)

    assert result is StateResult.FAIL
    assert state.next_state(ctx, result) == "NRCallDisconnected"
    assert commands.handover_calls == []
    assert events.error.messages == [
        "NR Handover 실패: previous test case is not set"
    ]


def test_handover_goes_to_nr_call_disconnected_on_false_result() -> None:
    command_facade = _Commands(handover_configured=False)
    prev_case = _make_case(band=NRBand.N77)
    current_case = _make_case(band=NRBand.N78)
    ctx, _, events, _ = _make_ctx(
        current_case,
        commands=command_facade,
        queue=[prev_case, current_case],
        current_index=1,
    )
    state = HandoverState()

    result = state.run(ctx)

    assert result is StateResult.FAIL
    assert state.next_state(ctx, result) == "NRCallDisconnected"
    assert events.error.messages == [
        "NR Handover 실패: call_handover returned false"
    ]


def test_handover_goes_to_nr_call_disconnected_on_exception() -> None:
    command_facade = _Commands(handover_exception=RuntimeError("instrument timeout"))
    prev_case = _make_case(band=NRBand.N77)
    current_case = _make_case(band=NRBand.N78)
    ctx, _, events, _ = _make_ctx(
        current_case,
        commands=command_facade,
        queue=[prev_case, current_case],
        current_index=1,
    )
    state = HandoverState()

    result = state.run(ctx)

    assert result is StateResult.FAIL
    assert state.next_state(ctx, result) == "NRCallDisconnected"
    assert events.error.messages == ["NR Handover 실패: instrument timeout"]


def test_handover_goes_to_nr_call_disconnected_on_channel_lookup_error() -> None:
    prev_case = _make_case(band=NRBand.N28, bandwidth=25.0)
    current_case = _make_case(band=NRBand.N78)
    ctx, commands, events, _ = _make_ctx(
        current_case,
        queue=[prev_case, current_case],
        current_index=1,
    )
    state = HandoverState()

    result = state.run(ctx)

    assert result is StateResult.FAIL
    assert state.next_state(ctx, result) == "NRCallDisconnected"
    assert commands.handover_calls == []
    assert events.error.messages == [
        "NR Handover 실패: No NR channel lookup for "
        "band='n28', bandwidth='25', test_channel='mid'"
    ]


def test_recall_change_emits_user_action_and_waits_for_completion() -> None:
    prev_case = _make_case(band=NRBand.N7, bandwidth=20.0)
    current_case = _make_case(band=NRBand.N38, bandwidth=20.0)
    ctx, _, events, _ = _make_ctx(
        current_case,
        queue=[prev_case, current_case],
        current_index=1,
    )
    state = RecallChangeState()

    def complete_action() -> None:
        time.sleep(0.02)
        ctx.user_action_completed.set()

    threading.Thread(target=complete_action, daemon=True).start()

    result = state.run(ctx)

    assert result is StateResult.OK
    assert events.user_action_required.messages == [
        "MT8000A Recall 변경: SA_FDD -> SA_TDD"
    ]
    assert state.next_state(ctx, result) == "NRCallConnect"


def test_recall_change_returns_fail_when_stopped_while_waiting() -> None:
    prev_case = _make_case(band=NRBand.N7, bandwidth=20.0)
    current_case = _make_case(band=NRBand.N38, bandwidth=20.0)
    ctx, _, events, _ = _make_ctx(
        current_case,
        queue=[prev_case, current_case],
        current_index=1,
    )
    state = RecallChangeState()

    def request_stop() -> None:
        time.sleep(0.02)
        ctx.stopped = True
        ctx.user_action_completed.set()

    threading.Thread(target=request_stop, daemon=True).start()

    result = state.run(ctx)

    assert result is StateResult.FAIL
    assert events.user_action_required.messages == [
        "MT8000A Recall 변경: SA_FDD -> SA_TDD"
    ]
    assert state.next_state(ctx, result) is None


@pytest.mark.parametrize(
    ("test_type", "expected"),
    [
        (NRTestType.HARMONIC, "MeasureFundamental"),
        (NRTestType.INBAND, "SetSwitchBox"),
        (NRTestType.BILOG, "SetSwitchBox"),
    ],
)
def test_test_type_change_checks_call_status_and_routes_to_test_type_measurement(
    test_type: NRTestType,
    expected: str,
) -> None:
    ctx, commands, events, client = _make_ctx(_make_case(test_type=test_type))
    state = TestTypeChangeState()

    result = state.run(ctx)

    assert result is StateResult.OK
    assert commands.call_status_calls == [client]
    assert state.next_state(ctx, result) == expected
    assert events.error.messages == []


def test_test_type_change_skips_when_mt8000a_is_not_connected() -> None:
    ctx, commands, events, _ = _make_ctx(_make_case())
    ctx.equipment_state = {"MT8000A": False}
    state = TestTypeChangeState()

    result = state.run(ctx)

    assert result is StateResult.FAIL
    assert state.next_state(ctx, result) == "NRCallDisconnected"
    assert commands.call_status_calls == []
    assert events.error.messages


def test_test_type_change_goes_to_nr_call_disconnected_on_false_result() -> None:
    command_facade = _Commands(call_connected=False)
    ctx, commands, events, client = _make_ctx(
        _make_case(),
        commands=command_facade,
    )
    state = TestTypeChangeState()

    result = state.run(ctx)

    assert result is StateResult.FAIL
    assert commands.call_status_calls == [client]
    assert state.next_state(ctx, result) == "NRCallDisconnected"
    assert events.error.messages == [
        "NR Call 끊김 감지: check_call_status returned disconnected"
    ]


def test_test_type_change_goes_to_nr_call_disconnected_on_exception() -> None:
    command_facade = _Commands(
        call_status_exception=RuntimeError("instrument timeout")
    )
    ctx, commands, events, client = _make_ctx(
        _make_case(),
        commands=command_facade,
    )
    state = TestTypeChangeState()

    result = state.run(ctx)

    assert result is StateResult.FAIL
    assert commands.call_status_calls == [client]
    assert state.next_state(ctx, result) == "NRCallDisconnected"
    assert events.error.messages == [
        "NR Call 상태 확인 실패: instrument timeout"
    ]
