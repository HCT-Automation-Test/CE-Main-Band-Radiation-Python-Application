from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.core.fsm.base import StateResult
from app.core.fsm.context import SessionContext
from app.core.fsm.states.session import (
    CheckNextCaseState,
    IdleState,
    PrepareReportState,
    SessionInitState,
    TestEndState,
)
from app.core.run_preparer import (
    PreparedRun,
    RunPreparationError,
    RunPreparationRequest,
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
from app.report.rawdata_source import RawDataWorkbookKind
from app.report.rawdata_workbook import RawDataResultWorkbook


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
        self.start_rejected = _SignalRecorder()


class _RunPreparer:
    def __init__(
        self,
        *,
        result_path: Path,
        report_writer: object | None = None,
        error: RunPreparationError | None = None,
        stop_context: SessionContext | None = None,
    ) -> None:
        self.result_path = result_path
        self.report_writer = report_writer if report_writer is not None else object()
        self.error = error
        self.stop_context = stop_context
        self.calls: list[RunPreparationRequest] = []

    def prepare(
        self,
        request: RunPreparationRequest,
        *,
        events: object,
        should_stop: object | None = None,
    ) -> PreparedRun:
        _ = events, should_stop
        self.calls.append(request)
        if self.error is not None:
            raise self.error
        if self.stop_context is not None:
            self.stop_context.stopped = True
        return PreparedRun(
            result_workbook=RawDataResultWorkbook(
                kind=RawDataWorkbookKind.NR,
                path=self.result_path,
                created=True,
            ),
            report_writer=self.report_writer,  # type: ignore[arg-type]
        )


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
    anchor_band: LTEBand = LTEBand.B1,
) -> TestCase:
    return TestCase(
        generation=generation,
        anchor_band=anchor_band if generation is Generation.NR_NSA else None,
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
    screenshot_root_dir = tmp_path / "screenshots"
    screenshot_root_dir.mkdir(exist_ok=True)
    return TestRunSettings(
        eut_name="SM-000",
        screenshot_root_dir=screenshot_root_dir,
        saturation_time_sec=5,
        connection_waiting_time_sec=5,
        atten_level_db=0,
        next_peak_search_level_db=6,
    )


def _prepared_check_next_state(ctx: SessionContext) -> CheckNextCaseState:
    ctx.last_applied_recall_id = ctx.current_case.mt8000_recall
    return CheckNextCaseState()


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


def test_idle_accepts_pending_request_and_routes_to_prepare_report(
    tmp_path: Path,
) -> None:
    events = _Events()
    settings = _make_settings(tmp_path)
    case = _make_case()
    request = RunPreparationRequest(
        cases=(case,),
        settings=settings,
        start_index=0,
        stop_index=None,
    )
    ctx = SessionContext(
        queue=[],
        commands=object(),
        events=events,  # type: ignore[arg-type]
        temp_dir=tmp_path,
        run_preparer=_RunPreparer(result_path=tmp_path / "result.xlsx"),  # type: ignore[arg-type]
        pending_run_request=request,
    )
    ctx.test_start_requested.set()

    result = IdleState().run(ctx)

    assert result is StateResult.OK
    assert ctx.pending_run_request is request
    assert ctx.queue == []
    assert events.current_case_changed.values == []
    assert events.tc_started.values == []
    assert IdleState().next_state(ctx, result) == "PrepareReport"


def test_prepare_report_commits_context_from_requested_start_index(
    tmp_path: Path,
) -> None:
    events = _Events()
    settings = _make_settings(tmp_path)
    first_case = _make_case()
    second_case = _make_case(
        band=NRBand.N38,
        bandwidth=20.0,
        antenna_pol=AntennaPol.V,
    )
    request = RunPreparationRequest(
        cases=(first_case, second_case),
        settings=settings,
        start_index=1,
        stop_index=1,
    )
    writer = object()
    preparer = _RunPreparer(
        result_path=tmp_path / "result.xlsx",
        report_writer=writer,
    )
    ctx = SessionContext(
        queue=[],
        commands=object(),
        events=events,  # type: ignore[arg-type]
        temp_dir=tmp_path,
        run_preparer=preparer,  # type: ignore[arg-type]
        pending_run_request=request,
        last_applied_factor_keyword="6G HPF",
        last_applied_recall_id="STALE_RECALL",
    )

    state = PrepareReportState()
    result = state.run(ctx)

    assert result is StateResult.OK
    assert preparer.calls == [request]
    assert ctx.queue == [first_case, second_case]
    assert ctx.current_index == 1
    assert ctx.start_index == 1
    assert ctx.stop_index == 1
    assert ctx.report_writer is writer
    assert ctx.result_workbook_path == tmp_path / "result.xlsx"
    assert ctx.settings is settings
    assert ctx.model_name == "SM-000"
    assert ctx.screenshot_root_dir == settings.screenshot_root_dir
    assert ctx.pending_run_request is None
    assert events.current_case_changed.values == [second_case]
    assert events.tc_started.values == [1]
    assert ctx.last_applied_factor_keyword is None
    assert ctx.last_applied_recall_id == second_case.mt8000_recall
    assert state.next_state(ctx, result) == "InitialTurntableZero"


def test_idle_rejects_missing_pending_request(tmp_path: Path) -> None:
    events = _Events()
    ctx = SessionContext(
        queue=[],
        commands=object(),
        events=events,  # type: ignore[arg-type]
        temp_dir=tmp_path,
        run_preparer=_RunPreparer(result_path=tmp_path / "result.xlsx"),  # type: ignore[arg-type]
    )
    ctx.test_start_requested.set()

    result = IdleState().run(ctx)

    assert result is StateResult.RETRY
    assert events.error.values[0].endswith("pending run request is required")
    assert events.start_rejected.values == [None]


def test_prepare_report_failure_returns_to_idle_without_partial_context(
    tmp_path: Path,
) -> None:
    events = _Events()
    settings = _make_settings(tmp_path)
    case = _make_case()
    request = RunPreparationRequest(
        cases=(case,),
        settings=settings,
        start_index=0,
        stop_index=None,
    )
    preparer = _RunPreparer(
        result_path=tmp_path / "result.xlsx",
        error=RunPreparationError("Excel report 준비 실패: unavailable"),
    )
    ctx = SessionContext(
        queue=[],
        commands=object(),
        events=events,  # type: ignore[arg-type]
        temp_dir=tmp_path,
        run_preparer=preparer,  # type: ignore[arg-type]
        pending_run_request=request,
    )

    state = PrepareReportState()
    result = state.run(ctx)

    assert result is StateResult.FAIL
    assert state.next_state(ctx, result) == "Idle"
    assert ctx.queue == []
    assert ctx.report_writer is None
    assert ctx.result_workbook_path is None
    assert ctx.pending_run_request is None
    assert events.current_case_changed.values == []
    assert events.tc_started.values == []
    assert events.start_rejected.values == [None]
    assert events.error.values[0].endswith("Excel report 준비 실패: unavailable")


def test_prepare_report_observes_stop_after_blocking_preparation(
    tmp_path: Path,
) -> None:
    events = _Events()
    settings = _make_settings(tmp_path)
    request = RunPreparationRequest(
        cases=(_make_case(),),
        settings=settings,
        start_index=0,
        stop_index=None,
    )
    ctx = SessionContext(
        queue=[],
        commands=object(),
        events=events,  # type: ignore[arg-type]
        pending_run_request=request,
    )
    ctx.run_preparer = _RunPreparer(  # type: ignore[assignment]
        result_path=tmp_path / "result.xlsx",
        stop_context=ctx,
    )

    result = PrepareReportState().run(ctx)

    assert result is StateResult.FAIL
    assert ctx.stopped
    assert ctx.queue == []
    assert ctx.report_writer is None
    assert events.current_case_changed.values == []
    assert events.tc_started.values == []
    assert events.start_rejected.values == []


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
    state = _prepared_check_next_state(ctx)

    result = state.run(ctx)

    assert result is StateResult.OK
    assert ctx.current_index == 1
    assert events.tc_finished.values == [0]
    assert events.current_case_changed.values == [next_case]
    assert events.tc_started.values == [1]
    assert state.next_state(ctx, result) == "CallCheck"


def test_check_next_case_queues_call_check_after_ant_pol_change() -> None:
    events = _Events()
    ctx = SessionContext(
        queue=[
            _make_case(antenna_pol=AntennaPol.H),
            _make_case(antenna_pol=AntennaPol.V),
        ],
        commands=object(),
        events=events,  # type: ignore[arg-type]
    )
    state = _prepared_check_next_state(ctx)

    result = state.run(ctx)

    assert result is StateResult.OK
    assert state.next_state(ctx, result) == "AntPolChange"
    assert ctx.pending_transition_states == ["CallCheck"]


def test_check_next_case_queues_call_check_after_dut_axis_and_ant_pol() -> None:
    events = _Events()
    ctx = SessionContext(
        queue=[
            _make_case(dut_axis=DUTAxis.X, antenna_pol=AntennaPol.H),
            _make_case(dut_axis=DUTAxis.Y, antenna_pol=AntennaPol.V),
        ],
        commands=object(),
        events=events,  # type: ignore[arg-type]
    )
    state = _prepared_check_next_state(ctx)

    result = state.run(ctx)

    assert result is StateResult.OK
    assert state.next_state(ctx, result) == "DUTAxisChange"
    assert ctx.pending_transition_states == ["AntPolChange", "CallCheck"]


def test_check_next_case_routes_co3000_to_mast3_as_ant_pol_change() -> None:
    events = _Events()
    prev_case = _make_case(TestType.BILOG, band=NRBand.N78)
    next_case = _make_case(TestType.HARMONIC, band=NRBand.N78)
    ctx = SessionContext(
        queue=[prev_case, next_case],
        commands=object(),
        events=events,  # type: ignore[arg-type]
    )
    state = _prepared_check_next_state(ctx)

    result = state.run(ctx)

    assert prev_case.range_definition.input_path is InputPath.INPUT1
    assert next_case.range_definition.input_path is InputPath.INPUT3
    assert result is StateResult.OK
    assert state.next_state(ctx, result) == "AntPolChange"
    assert ctx.pending_transition_states == ["CallCheck"]


def test_check_next_case_routes_mast3_to_co3000_as_ant_pol_change() -> None:
    events = _Events()
    prev_case = _make_case(TestType.HARMONIC, band=NRBand.N78)
    next_case = _make_case(TestType.BILOG, band=NRBand.N78)
    ctx = SessionContext(
        queue=[prev_case, next_case],
        commands=object(),
        events=events,  # type: ignore[arg-type]
    )
    state = _prepared_check_next_state(ctx)

    result = state.run(ctx)

    assert prev_case.range_definition.input_path is InputPath.INPUT3
    assert next_case.range_definition.input_path is InputPath.INPUT1
    assert result is StateResult.OK
    assert state.next_state(ctx, result) == "AntPolChange"
    assert ctx.pending_transition_states == ["CallCheck"]


def test_check_next_case_queues_handover_ant_pol_and_single_call_check() -> None:
    events = _Events()
    prev_case = _make_case(TestType.BILOG, band=NRBand.N77)
    next_case = _make_case(TestType.HARMONIC, band=NRBand.N78)
    ctx = SessionContext(
        queue=[prev_case, next_case],
        commands=object(),
        events=events,  # type: ignore[arg-type]
    )
    state = _prepared_check_next_state(ctx)

    result = state.run(ctx)

    assert prev_case.range_definition.input_path is InputPath.INPUT1
    assert next_case.range_definition.input_path is InputPath.INPUT3
    assert result is StateResult.OK
    assert state.next_state(ctx, result) == "Handover"
    assert ctx.pending_transition_states == ["AntPolChange", "CallCheck"]


def test_check_next_case_queues_recall_ant_pol_and_single_call_check() -> None:
    events = _Events()
    prev_case = _make_case(TestType.BILOG, band=NRBand.N1, bandwidth=20.0)
    next_case = _make_case(
        TestType.HARMONIC,
        band=NRBand.N78,
        dut_axis=DUTAxis.Y,
    )
    ctx = SessionContext(
        queue=[prev_case, next_case],
        commands=object(),
        events=events,  # type: ignore[arg-type]
    )
    state = _prepared_check_next_state(ctx)

    result = state.run(ctx)

    assert prev_case.range_definition.input_path is InputPath.INPUT1
    assert next_case.range_definition.input_path is InputPath.INPUT3
    assert result is StateResult.OK
    assert state.next_state(ctx, result) == "RecallChange"
    assert ctx.pending_transition_states == [
        "NRCallConnect",
        "DUTAxisChange",
        "AntPolChange",
        "CallCheck",
    ]


def test_check_next_case_treats_co3000_mast_change_as_ant_pol_change() -> None:
    events = _Events()
    prev_case = _make_case(TestType.HARMONIC, band=NRBand.N1, bandwidth=20.0)
    next_case = _make_case(TestType.BILOG, band=NRBand.N1, bandwidth=20.0)
    ctx = SessionContext(
        queue=[prev_case, next_case],
        commands=object(),
        events=events,  # type: ignore[arg-type]
    )
    state = _prepared_check_next_state(ctx)

    result = state.run(ctx)

    assert prev_case.range_definition.input_path is InputPath.INPUT2
    assert next_case.range_definition.input_path is InputPath.INPUT1
    assert result is StateResult.OK
    assert state.next_state(ctx, result) == "AntPolChange"
    assert ctx.pending_transition_states == ["CallCheck"]


def test_check_next_case_routes_band_change_to_handover_when_recall_is_same() -> None:
    events = _Events()
    next_case = _make_case(band=NRBand.N78)
    ctx = SessionContext(
        queue=[_make_case(band=NRBand.N77), next_case],
        commands=object(),
        events=events,  # type: ignore[arg-type]
    )
    state = _prepared_check_next_state(ctx)

    result = state.run(ctx)

    assert result is StateResult.OK
    assert state.next_state(ctx, result) == "Handover"
    assert ctx.pending_transition_states == []


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
    state = _prepared_check_next_state(ctx)

    result = state.run(ctx)

    assert result is StateResult.OK
    assert state.next_state(ctx, result) == "Handover"


def test_check_next_case_routes_same_anchor_nr_nsa_config_change_to_handover() -> None:
    events = _Events()
    ctx = SessionContext(
        queue=[
            _make_case(generation=Generation.NR_NSA),
            _make_case(generation=Generation.NR_NSA, bandwidth=90.0),
        ],
        commands=object(),
        events=events,  # type: ignore[arg-type]
    )
    state = _prepared_check_next_state(ctx)

    result = state.run(ctx)

    assert result is StateResult.OK
    assert state.next_state(ctx, result) == "Handover"


@pytest.mark.parametrize(
    "current_changes",
    [
        {"anchor_band": LTEBand.B3},
        {"anchor_band": LTEBand.B3, "bandwidth": 90.0},
    ],
    ids=["anchor-only", "anchor-and-nr-config"],
)
def test_check_next_case_routes_nsa_anchor_change_to_nsa_handover(
    current_changes: dict[str, Any],
) -> None:
    events = _Events()
    ctx = SessionContext(
        queue=[
            _make_case(generation=Generation.NR_NSA, anchor_band=LTEBand.B1),
            _make_case(generation=Generation.NR_NSA, **current_changes),
        ],
        commands=object(),
        events=events,  # type: ignore[arg-type]
    )
    state = _prepared_check_next_state(ctx)

    result = state.run(ctx)

    assert result is StateResult.OK
    assert state.next_state(ctx, result) == "NSAHandover"


def test_check_next_case_keeps_recall_change_priority_over_anchor_change() -> None:
    events = _Events()
    ctx = SessionContext(
        queue=[
            _make_case(
                generation=Generation.NR_NSA,
                band=NRBand.N7,
                bandwidth=20.0,
                anchor_band=LTEBand.B1,
            ),
            _make_case(
                generation=Generation.NR_NSA,
                band=NRBand.N38,
                bandwidth=20.0,
                anchor_band=LTEBand.B3,
            ),
        ],
        commands=object(),
        events=events,  # type: ignore[arg-type]
    )
    state = _prepared_check_next_state(ctx)

    result = state.run(ctx)

    assert result is StateResult.OK
    assert state.next_state(ctx, result) == "RecallChange"
    assert ctx.pending_transition_states == ["NSAHandover"]


def test_check_next_case_skips_handover_when_call_config_is_unchanged() -> None:
    events = _Events()
    ctx = SessionContext(
        queue=[_make_case(), _make_case()],
        commands=object(),
        events=events,  # type: ignore[arg-type]
    )
    state = _prepared_check_next_state(ctx)

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
    state = _prepared_check_next_state(ctx)

    result = state.run(ctx)

    assert result is StateResult.OK
    assert state.next_state(ctx, result) == "RecallChange"
    assert ctx.pending_transition_states == ["NRCallConnect"]


def test_check_next_case_compares_target_recall_to_applied_id_not_previous_case() -> None:
    events = _Events()
    previous_case = _make_case(band=NRBand.N1, bandwidth=20.0)
    current_case = _make_case(band=NRBand.N78)
    ctx = SessionContext(
        queue=[previous_case, current_case],
        commands=object(),
        events=events,  # type: ignore[arg-type]
        last_applied_recall_id=current_case.mt8000_recall,
    )
    state = CheckNextCaseState()

    result = state.run(ctx)

    assert result is StateResult.OK
    assert previous_case.mt8000_recall != current_case.mt8000_recall
    assert state.next_state(ctx, result) == "Handover"
    assert ctx.pending_transition_states == ["AntPolChange", "CallCheck"]


def test_check_next_case_routes_nsa_recall_change_to_nsa_call() -> None:
    events = _Events()
    previous_case = _make_case(
        generation=Generation.NR_NSA,
        band=NRBand.N7,
        bandwidth=20.0,
        anchor_band=LTEBand.B1,
    )
    current_case = _make_case(
        generation=Generation.NR_NSA,
        band=NRBand.N38,
        bandwidth=20.0,
        anchor_band=LTEBand.B1,
    )
    ctx = SessionContext(
        queue=[previous_case, current_case],
        commands=object(),
        events=events,  # type: ignore[arg-type]
        last_applied_recall_id=previous_case.mt8000_recall,
    )
    state = CheckNextCaseState()

    result = state.run(ctx)

    assert result is StateResult.OK
    assert state.next_state(ctx, result) == "RecallChange"
    assert ctx.pending_transition_states == ["NSACallConnect"]



def test_check_next_case_goes_to_test_end_at_stop_index() -> None:
    events = _Events()
    ctx = SessionContext(
        queue=[_make_case(), _make_case(antenna_pol=AntennaPol.V)],
        commands=object(),
        events=events,  # type: ignore[arg-type]
        stop_index=0,
    )
    state = _prepared_check_next_state(ctx)

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
    state = _prepared_check_next_state(ctx)

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
        last_applied_recall_id="5GNR_SA_TDD",
    )
    state = TestEndState()

    result = state.run(ctx)

    assert result is StateResult.OK
    assert events.session_finished.values == [None]
    assert ctx.queue == []
    assert ctx.fundamental_frequency_mhz is None
    assert ctx.last_applied_factor_keyword is None
    assert ctx.last_applied_recall_id is None
    assert state.next_state(ctx, result) == "Idle"
