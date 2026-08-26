from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

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
    Generation,
    InputPath,
    LTEBand,
    Modulation,
    NRBand,
    RBAllocation,
    TestChannel,
    TestType,
)
from app.models.test_case import TestCase
from app.models.test_run_settings import TestRunSettings


class _SignalRecorder:
    def __init__(self) -> None:
        self.values: list[Any] = []

    def emit(self, value: Any = None) -> None:
        self.values.append(value)


class _Events:
    def __init__(self) -> None:
        self.error = _SignalRecorder()
        self.tc_started = _SignalRecorder()
        self.tc_finished = _SignalRecorder()
        self.current_case_changed = _SignalRecorder()
        self.session_finished = _SignalRecorder()


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


def _ready_states() -> dict[str, bool]:
    return {
        "FSV40": True,
        "MT8000A": True,
        "CO3000": True,
        "Switch Box": True,
        "3D Controller": True,
    }


def _make_case(
    test_type: TestType = TestType.HARMONIC,
    *,
    band: NRBand = NRBand.N78,
    bandwidth: float = 100.0,
    modulation: Modulation = Modulation.QPSK,
    rb_allocation: RBAllocation = RBAllocation.INNER_FULL,
    test_channel: TestChannel = TestChannel.MID,
    antenna_pol: AntennaPol = AntennaPol.H,
    dut_axis: DUTAxis = DUTAxis.X,
    generation: Generation = Generation.NR_SA,
) -> TestCase:
    return TestCase(
        generation=generation,
        anchor_band=LTEBand.B1 if generation is Generation.NR_NSA else None,
        band=band,
        bandwidth=bandwidth,
        test_type=test_type,
        modulation=modulation,
        rb_allocation=rb_allocation,
        test_channel=test_channel,
        antenna_pol=antenna_pol,
        dut_axis=dut_axis,
        dut_ant_position="Upper",
    )


def _make_settings(tmp_path: Path) -> TestRunSettings:
    template_path = tmp_path / "template.xlsx"
    screenshot_root_dir = tmp_path / "screenshots"
    template_path.write_bytes(b"template")
    screenshot_root_dir.mkdir(exist_ok=True)
    return TestRunSettings(
        eut_name="SM-000",
        template_path=template_path,
        screenshot_root_dir=screenshot_root_dir,
        saturation_time_sec=5,
        connection_waiting_time_sec=5,
        atten_level_db=0,
        next_peak_search_level_db=6,
    )


def test_session_init_accepts_ready_equipment_state_without_connecting() -> None:
    events = _Events()
    client = _Client()
    commands = _Commands(response=_ready_states())
    ctx = SessionContext(
        queue=[],
        commands=commands,
        events=events,  # type: ignore[arg-type]
        client=client,
        tcp_host="127.0.0.1",
        tcp_port=5025,
    )
    ctx.equipment_state = _ready_states()
    ctx.equipment_connect_requested.set()

    result = SessionInitState().run(ctx)

    assert result is StateResult.OK
    assert client.connect_calls == []
    assert commands.connect_calls == []
    assert ctx.equipment_state == _ready_states()


def test_session_init_retries_when_equipment_state_is_empty() -> None:
    events = _Events()
    ctx = SessionContext(
        queue=[],
        commands=_Commands(response=True),
        events=events,  # type: ignore[arg-type]
        client=_Client(),
    )
    ctx.equipment_connect_requested.set()

    result = SessionInitState().run(ctx)

    assert result is StateResult.RETRY
    assert events.error.values[0].endswith("equipment_state is empty")


def test_session_init_retries_when_client_is_missing() -> None:
    events = _Events()
    ctx = SessionContext(
        queue=[],
        commands=_Commands(response=True),
        events=events,  # type: ignore[arg-type]
        client=None,
    )
    ctx.equipment_state = _ready_states()
    ctx.equipment_connect_requested.set()

    result = SessionInitState().run(ctx)

    assert result is StateResult.RETRY
    assert events.error.values[0].endswith("TCP client is not set")


def test_session_init_retries_when_any_equipment_status_is_false() -> None:
    events = _Events()
    states = _ready_states()
    states["FSV40"] = False
    commands = _Commands(response=states)
    ctx = SessionContext(
        queue=[],
        commands=commands,
        events=events,  # type: ignore[arg-type]
        client=_Client(),
    )
    ctx.equipment_state = states
    ctx.equipment_connect_requested.set()

    result = SessionInitState().run(ctx)

    assert result is StateResult.RETRY
    assert ctx.equipment_state == states
    assert commands.connect_calls == []
    assert events.error.values[0].endswith("disconnected equipment: FSV40")


def test_session_init_accepts_partial_success_equipment_state() -> None:
    events = _Events()
    commands = _Commands(response={"FSV40": True})
    ctx = SessionContext(
        queue=[],
        commands=commands,
        events=events,  # type: ignore[arg-type]
        client=_Client(),
    )
    ctx.equipment_state = {"FSV40": True}
    ctx.equipment_connect_requested.set()

    result = SessionInitState().run(ctx)

    assert result is StateResult.OK
    assert commands.connect_calls == []
    assert events.error.values == []


def test_session_init_retries_when_equipment_state_has_only_unknown_keys() -> None:
    events = _Events()
    ctx = SessionContext(
        queue=[],
        commands=_Commands(response=True),
        events=events,  # type: ignore[arg-type]
        client=_Client(),
    )
    ctx.equipment_state = {"Extra Device": True}
    ctx.equipment_connect_requested.set()

    result = SessionInitState().run(ctx)

    assert result is StateResult.RETRY
    assert events.error.values[0].endswith("equipment_state is not ready")


def test_idle_waits_for_start_request_and_validates_context(tmp_path: Path) -> None:
    events = _Events()
    settings = _make_settings(tmp_path)
    case = _make_case()
    ctx = SessionContext(
        queue=[case],
        commands=object(),
        events=events,  # type: ignore[arg-type]
        report_writer=object(),  # type: ignore[arg-type]
        temp_dir=tmp_path,
        settings=settings,
        model_name=settings.eut_name,
        template_path=settings.template_path,
        screenshot_root_dir=settings.screenshot_root_dir,
    )
    ctx.last_applied_factor_keyword = "6G HPF"
    ctx.test_start_requested.set()

    result = IdleState().run(ctx)

    assert result is StateResult.OK
    assert events.current_case_changed.values == [case]
    assert events.tc_started.values == [0]
    assert ctx.last_applied_factor_keyword is None
    assert IdleState().next_state(ctx, result) == "InitialTurntableZero"


def test_idle_starts_from_context_start_index(tmp_path: Path) -> None:
    events = _Events()
    settings = _make_settings(tmp_path)
    first_case = _make_case()
    second_case = _make_case(antenna_pol=AntennaPol.V)
    ctx = SessionContext(
        queue=[first_case, second_case],
        commands=object(),
        events=events,  # type: ignore[arg-type]
        report_writer=object(),  # type: ignore[arg-type]
        temp_dir=tmp_path,
        settings=settings,
        model_name=settings.eut_name,
        template_path=settings.template_path,
        screenshot_root_dir=settings.screenshot_root_dir,
        start_index=1,
        last_applied_factor_keyword="6G HPF",
    )
    ctx.test_start_requested.set()

    result = IdleState().run(ctx)

    assert result is StateResult.OK
    assert ctx.current_index == 1
    assert events.current_case_changed.values == [second_case]
    assert events.tc_started.values == [1]
    assert ctx.last_applied_factor_keyword is None


def test_idle_retries_without_report_writer(tmp_path: Path) -> None:
    events = _Events()
    settings = _make_settings(tmp_path)
    ctx = SessionContext(
        queue=[_make_case()],
        commands=object(),
        events=events,  # type: ignore[arg-type]
        temp_dir=tmp_path,
        settings=settings,
        model_name=settings.eut_name,
        template_path=settings.template_path,
        screenshot_root_dir=settings.screenshot_root_dir,
    )
    ctx.test_start_requested.set()

    result = IdleState().run(ctx)

    assert result is StateResult.RETRY
    assert events.error.values[0].endswith("report_writer is not set")


def test_idle_retries_without_settings(tmp_path: Path) -> None:
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

    assert result is StateResult.RETRY
    assert events.error.values[0].endswith("settings is required")


def test_idle_stop_wakeup_returns_fail_without_empty_queue_error() -> None:
    events = _Events()
    ctx = SessionContext(
        queue=[],
        commands=object(),
        events=events,  # type: ignore[arg-type]
    )
    ctx.stopped = True
    ctx.test_start_requested.set()

    result = IdleState().run(ctx)

    assert result is StateResult.FAIL
    assert events.error.values == []


def test_check_next_case_advances_and_routes_by_test_type() -> None:
    events = _Events()
    next_case = _make_case(TestType.INBAND)
    ctx = SessionContext(
        queue=[_make_case(), next_case],
        commands=object(),
        events=events,  # type: ignore[arg-type]
    )
    state = CheckNextCaseState()

    result = state.run(ctx)

    assert result is StateResult.OK
    assert ctx.current_index == 1
    assert events.tc_finished.values == [0]
    assert events.current_case_changed.values == [next_case]
    assert events.tc_started.values == [1]
    assert state.next_state(ctx, result) == "TestTypeChange"


def test_check_next_case_routes_co3000_to_mast3_as_ant_pol_change() -> None:
    events = _Events()
    prev_case = _make_case(TestType.BILOG, band=NRBand.N78)
    next_case = _make_case(TestType.HARMONIC, band=NRBand.N78)
    ctx = SessionContext(
        queue=[prev_case, next_case],
        commands=object(),
        events=events,  # type: ignore[arg-type]
    )
    state = CheckNextCaseState()

    result = state.run(ctx)

    assert prev_case.range_definition.input_path is InputPath.INPUT1
    assert next_case.range_definition.input_path is InputPath.INPUT3
    assert result is StateResult.OK
    assert state.next_state(ctx, result) == "AntPolChange"


def test_check_next_case_routes_mast3_to_co3000_as_ant_pol_change() -> None:
    events = _Events()
    prev_case = _make_case(TestType.HARMONIC, band=NRBand.N78)
    next_case = _make_case(TestType.BILOG, band=NRBand.N78)
    ctx = SessionContext(
        queue=[prev_case, next_case],
        commands=object(),
        events=events,  # type: ignore[arg-type]
    )
    state = CheckNextCaseState()

    result = state.run(ctx)

    assert prev_case.range_definition.input_path is InputPath.INPUT3
    assert next_case.range_definition.input_path is InputPath.INPUT1
    assert result is StateResult.OK
    assert state.next_state(ctx, result) == "AntPolChange"


def test_check_next_case_queues_handover_ant_pol_and_test_type_changes() -> None:
    events = _Events()
    prev_case = _make_case(TestType.BILOG, band=NRBand.N77)
    next_case = _make_case(TestType.HARMONIC, band=NRBand.N78)
    ctx = SessionContext(
        queue=[prev_case, next_case],
        commands=object(),
        events=events,  # type: ignore[arg-type]
    )
    state = CheckNextCaseState()

    result = state.run(ctx)

    assert prev_case.range_definition.input_path is InputPath.INPUT1
    assert next_case.range_definition.input_path is InputPath.INPUT3
    assert result is StateResult.OK
    assert state.next_state(ctx, result) == "Handover"
    assert ctx.pending_transition_states == ["AntPolChange", "TestTypeChange"]


def test_check_next_case_queues_recall_ant_pol_and_test_type_changes() -> None:
    events = _Events()
    prev_case = _make_case(TestType.BILOG, band=NRBand.N1, bandwidth=20.0)
    next_case = _make_case(TestType.HARMONIC, band=NRBand.N78)
    ctx = SessionContext(
        queue=[prev_case, next_case],
        commands=object(),
        events=events,  # type: ignore[arg-type]
    )
    state = CheckNextCaseState()

    result = state.run(ctx)

    assert prev_case.range_definition.input_path is InputPath.INPUT1
    assert next_case.range_definition.input_path is InputPath.INPUT3
    assert result is StateResult.OK
    assert state.next_state(ctx, result) == "RecallChange"
    assert ctx.pending_transition_states == ["AntPolChange", "TestTypeChange"]


def test_check_next_case_treats_co3000_mast_change_as_ant_pol_change() -> None:
    events = _Events()
    prev_case = _make_case(TestType.HARMONIC, band=NRBand.N1, bandwidth=20.0)
    next_case = _make_case(TestType.BILOG, band=NRBand.N1, bandwidth=20.0)
    ctx = SessionContext(
        queue=[prev_case, next_case],
        commands=object(),
        events=events,  # type: ignore[arg-type]
    )
    state = CheckNextCaseState()

    result = state.run(ctx)

    assert prev_case.range_definition.input_path is InputPath.INPUT2
    assert next_case.range_definition.input_path is InputPath.INPUT1
    assert result is StateResult.OK
    assert state.next_state(ctx, result) == "AntPolChange"


def test_check_next_case_routes_band_change_to_handover_when_recall_is_same() -> None:
    events = _Events()
    next_case = _make_case(band=NRBand.N78)
    ctx = SessionContext(
        queue=[_make_case(band=NRBand.N77), next_case],
        commands=object(),
        events=events,  # type: ignore[arg-type]
    )
    state = CheckNextCaseState()

    result = state.run(ctx)

    assert result is StateResult.OK
    assert state.next_state(ctx, result) == "Handover"


@pytest.mark.parametrize(
    "case_changes",
    [
        {"bandwidth": 90.0},
        {"test_channel": TestChannel.HIGH},
        {"rb_allocation": RBAllocation.INNER_1RB_LEFT},
        {"modulation": Modulation.PI_OVER_2_BPSK},
    ],
    ids=["bandwidth", "channel", "rb", "modulation"],
)
def test_check_next_case_routes_same_band_call_config_change_to_handover(
    case_changes: dict[str, Any],
) -> None:
    events = _Events()
    ctx = SessionContext(
        queue=[_make_case(), _make_case(**case_changes)],
        commands=object(),
        events=events,  # type: ignore[arg-type]
    )
    state = CheckNextCaseState()

    result = state.run(ctx)

    assert result is StateResult.OK
    assert state.next_state(ctx, result) == "Handover"


def test_check_next_case_routes_same_band_nr_nsa_config_change_via_anchor() -> None:
    events = _Events()
    ctx = SessionContext(
        queue=[
            _make_case(generation=Generation.NR_NSA),
            _make_case(generation=Generation.NR_NSA, bandwidth=90.0),
        ],
        commands=object(),
        events=events,  # type: ignore[arg-type]
    )
    state = CheckNextCaseState()

    result = state.run(ctx)

    assert result is StateResult.OK
    assert state.next_state(ctx, result) == "LTECallAnchorBeforeHandover"


def test_check_next_case_skips_handover_when_call_config_is_unchanged() -> None:
    events = _Events()
    ctx = SessionContext(
        queue=[_make_case(), _make_case()],
        commands=object(),
        events=events,  # type: ignore[arg-type]
    )
    state = CheckNextCaseState()

    result = state.run(ctx)

    assert result is StateResult.OK
    assert state.next_state(ctx, result) == "ApplyTdf"


def test_check_next_case_routes_band_change_to_recall_change_when_recall_differs() -> None:
    events = _Events()
    next_case = _make_case(
        band=NRBand.N38,
        bandwidth=20.0,
        test_channel=TestChannel.HIGH,
        rb_allocation=RBAllocation.INNER_1RB_LEFT,
    )
    ctx = SessionContext(
        queue=[
            _make_case(band=NRBand.N7, bandwidth=20.0),
            next_case,
        ],
        commands=object(),
        events=events,  # type: ignore[arg-type]
    )
    state = CheckNextCaseState()

    result = state.run(ctx)

    assert result is StateResult.OK
    assert state.next_state(ctx, result) == "RecallChange"



def test_check_next_case_goes_to_test_end_at_stop_index() -> None:
    events = _Events()
    ctx = SessionContext(
        queue=[_make_case(), _make_case(antenna_pol=AntennaPol.V)],
        commands=object(),
        events=events,  # type: ignore[arg-type]
        stop_index=0,
    )
    state = CheckNextCaseState()

    result = state.run(ctx)

    assert result is StateResult.OK
    assert ctx.current_index == 0
    assert state.next_state(ctx, result) == "TestEnd"
    assert events.tc_finished.values == [0]
    assert events.current_case_changed.values == []
    assert events.tc_started.values == []


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
    events = _Events()
    ctx = SessionContext(
        queue=[_make_case()],
        commands=object(),
        events=events,  # type: ignore[arg-type]
        current_index=0,
        fundamental_frequency_mhz=3550.25,
        last_applied_factor_keyword="6G HPF",
    )
    state = TestEndState()

    result = state.run(ctx)

    assert result is StateResult.OK
    assert events.session_finished.values == [None]
    assert ctx.queue == []
    assert ctx.fundamental_frequency_mhz is None
    assert ctx.last_applied_factor_keyword is None
    assert state.next_state(ctx, result) == "Idle"
