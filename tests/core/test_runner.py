from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

import pytest
import shiboken6
from PySide6.QtCore import QCoreApplication, QEvent, QObject

import app.core.runner as runner_module

from app.core.fsm.base import State, StateResult
from app.core.fsm.context import SessionContext
from app.core.fsm.engine import FSMEngine
from app.core.fsm.states.session import IdleState, PrepareReportState
from app.core.runner import (
    INSTRUMENT_CONNECTION_BLOCK_MESSAGE,
    INSTRUMENT_SET_BLOCK_MESSAGE,
    Runner,
)
from app.core.instrument_connection import (
    build_equipment_connection_config,
    disconnected_equipment_state,
)
from app.models.enums import (
    AntennaPol,
    DUTAxis,
    Generation,
    LTEBand,
    LTERBAllocation,
    Modulation,
    NRBand,
    RBAllocation,
    TestChannel,
    TestType,
)
from app.models.test_case import TestCase
from app.models import test_run_settings
from app.models.test_run_settings import (
    TestRunSettings,
    default_screenshot_root_dir,
)
from app.report.rawdata_source import RawDataWorkbookKind
from app.report.rawdata_workbook import RawDataResultWorkbook


class _FakeEngine:
    def __init__(self, ctx: SessionContext) -> None:
        self.ctx = ctx
        self.initial_state: str | None = None
        self.current_state_name: str | None = None
        self.started = threading.Event()

    def run(self, initial_state: str = "SessionInit") -> None:
        self.initial_state = initial_state
        self.current_state_name = initial_state
        self.started.set()
        while not self.ctx.stopped:
            time.sleep(0.01)


class _ExitAfterStartEngine:
    def __init__(self, ctx: SessionContext) -> None:
        self.ctx = ctx
        self.initial_state: str | None = None
        self.current_state_name: str | None = None
        self.started = threading.Event()

    def run(self, initial_state: str = "SessionInit") -> None:
        self.initial_state = initial_state
        self.current_state_name = "Idle"
        self.started.set()
        while not self.ctx.test_start_requested.is_set() and not self.ctx.stopped:
            time.sleep(0.01)
        self.current_state_name = "MeasureFundamental"


class _BlockingEngine:
    def __init__(self, ctx: SessionContext, release: threading.Event) -> None:
        self.ctx = ctx
        self.release = release
        self.current_state_name: str | None = None
        self.started = threading.Event()

    def run(self, initial_state: str = "SessionInit") -> None:
        _ = initial_state
        self.current_state_name = "Idle"
        self.started.set()
        self.release.wait()


class _SessionInitPassState(State):
    name = "SessionInit"

    def run(self, ctx: SessionContext) -> StateResult:
        _ = ctx
        return StateResult.OK

    def next_state(
        self,
        ctx: SessionContext,
        result: StateResult,
    ) -> str | None:
        _ = ctx
        return "Idle" if result is StateResult.OK else None


class _HoldInitialTurntableZeroState(State):
    """준비 성공 이후 장비 상태로 진입하지 않게 멈추는 테스트 state."""

    name = "InitialTurntableZero"

    def run(self, ctx: SessionContext) -> StateResult:
        while not ctx.stopped:
            time.sleep(0.01)
        return StateResult.FAIL

    def next_state(
        self,
        ctx: SessionContext,
        result: StateResult,
    ) -> str | None:
        _ = ctx, result
        return None


def _build_preparation_test_engine(ctx: SessionContext) -> FSMEngine:
    engine = FSMEngine(ctx)
    engine.register(_SessionInitPassState())
    engine.register(IdleState())
    engine.register(PrepareReportState())
    engine.register(_HoldInitialTurntableZeroState())
    return engine


class _ReportWriter:
    def __init__(self, *, prepare_exception: Exception | None = None) -> None:
        self.prepare_exception = prepare_exception
        self.prepare_calls: list[TestCase] = []

    def prepare_for_run(self, first_case: TestCase) -> None:
        self.prepare_calls.append(first_case)
        if self.prepare_exception is not None:
            raise self.prepare_exception


class _Client:
    def __init__(self) -> None:
        self.connect_calls: list[tuple[str, int]] = []

    def connect_to(self, host: str, port: int) -> None:
        self.connect_calls.append((host, port))


class _ClosableClient:
    def __init__(self) -> None:
        self.close_calls = 0

    def close(self) -> None:
        self.close_calls += 1


class _ConnectionCommands:
    def __init__(self, states: dict[str, bool]) -> None:
        self.states = states
        self.calls: list[tuple[Any, Any]] = []

    def connect_equipment(self, client: Any, *, config: Any) -> dict[str, bool]:
        self.calls.append((client, config))
        return self.states


def _ready_states() -> dict[str, bool]:
    return {
        "MT8000A": True,
        "FSV40": True,
        "CO3000": True,
        "Switch Box": True,
        "3D Controller": True,
    }


def _connection_config():
    return build_equipment_connection_config(
        mt8000a_visa_resource="MT",
        fsv40_visa_resource="FS",
        co3000_visa_resource="CO",
        controller_3d_visa_resource="3D",
        switch_box_ip_address="192.168.0.10",
        switch_box_port=5000,
    )


def _make_settings(tmp_path: Path, *, eut_name: str = "SM-000") -> TestRunSettings:
    template_path = tmp_path / "template.xlsx"
    screenshot_root_dir = tmp_path / "screenshots"
    template_path.write_bytes(b"template")
    screenshot_root_dir.mkdir(exist_ok=True)
    return TestRunSettings(
        eut_name=eut_name,
        template_path=template_path,
        screenshot_root_dir=screenshot_root_dir,
        saturation_time_sec=5,
        connection_waiting_time_sec=5,
        atten_level_db=0,
        next_peak_search_level_db=6,
    )


def _make_case(*, antenna_pol: AntennaPol = AntennaPol.H) -> TestCase:
    return TestCase(
        band=NRBand.N78,
        bandwidth=100.0,
        test_type=TestType.HARMONIC,
        modulation=Modulation.QPSK,
        rb_allocation=RBAllocation.INNER_FULL,
        test_channel=TestChannel.MID,
        antenna_pol=antenna_pol,
        dut_axis=DUTAxis.X,
        dut_ant_position="Upper",
    )


def _make_lte_case() -> TestCase:
    return TestCase(
        generation=Generation.LTE,
        band=LTEBand.B1,
        bandwidth=5.0,
        test_type=TestType.HARMONIC,
        modulation=Modulation.QPSK,
        rb_allocation=LTERBAllocation.MID,
        test_channel=TestChannel.MID,
        antenna_pol=AntennaPol.H,
        dut_axis=DUTAxis.X,
        dut_ant_position="Upper",
    )


def _make_nsa_case() -> TestCase:
    return TestCase(
        generation=Generation.NR_NSA,
        anchor_band=LTEBand.B1,
        band=NRBand.N78,
        bandwidth=100.0,
        test_type=TestType.HARMONIC,
        modulation=Modulation.QPSK,
        rb_allocation=RBAllocation.INNER_FULL,
        test_channel=TestChannel.MID,
        antenna_pol=AntennaPol.H,
        dut_axis=DUTAxis.X,
        dut_ant_position="Upper",
    )


def test_initialize_starts_worker_at_session_init(qtbot: Any, tmp_path: Path) -> None:
    engines: list[_FakeEngine] = []

    def engine_factory(ctx: SessionContext) -> _FakeEngine:
        engine = _FakeEngine(ctx)
        engines.append(engine)
        return engine

    runner = Runner(
        client=object(),
        commands=object(),
        engine_factory=engine_factory,  # type: ignore[arg-type]
        temp_dir=tmp_path / "temp",
    )

    runner.initialize()
    qtbot.waitUntil(lambda: bool(engines) and engines[0].started.is_set())

    assert runner.is_running
    assert runner.context is engines[0].ctx
    assert engines[0].initial_state == "SessionInit"
    assert runner.context is not None
    assert runner.context.temp_dir == tmp_path / "temp"
    assert (tmp_path / "temp").is_dir()

    runner.stop()
    qtbot.waitUntil(lambda: not runner.is_running)


def test_mark_equipment_ready_initializes_and_sets_session_init_request(
    qtbot: Any, tmp_path: Path
) -> None:
    engines: list[_FakeEngine] = []

    def engine_factory(ctx: SessionContext) -> _FakeEngine:
        engine = _FakeEngine(ctx)
        engines.append(engine)
        return engine

    runner = Runner(
        client=object(),
        commands=object(),
        engine_factory=engine_factory,  # type: ignore[arg-type]
        temp_dir=tmp_path / "temp",
    )

    runner.mark_equipment_ready(_ready_states())
    qtbot.waitUntil(lambda: bool(engines) and engines[0].started.is_set())

    assert runner.context is not None
    assert runner.context.equipment_state == _ready_states()
    assert runner.context.equipment_connect_requested.is_set()
    assert runner.equipment_state == _ready_states()
    assert runner.is_equipment_ready

    runner.stop()
    qtbot.waitUntil(lambda: not runner.is_running)


def test_equipment_ready_accepts_selected_success_devices(tmp_path: Path) -> None:
    states_with_extra_failure = _ready_states() | {"Extra Device": False}
    runner = Runner(client=object(), commands=object(), temp_dir=tmp_path / "temp")

    runner._equipment_state = {"FSV40": True}

    assert runner.is_equipment_ready

    runner._equipment_state = states_with_extra_failure

    assert runner.is_equipment_ready
    assert runner.equipment_state == states_with_extra_failure


def test_mark_equipment_ready_partial_state_initializes_runner(
    qtbot: Any,
    tmp_path: Path,
) -> None:
    engines: list[_FakeEngine] = []

    def engine_factory(ctx: SessionContext) -> _FakeEngine:
        engine = _FakeEngine(ctx)
        engines.append(engine)
        return engine

    runner = Runner(
        client=object(),
        commands=object(),
        engine_factory=engine_factory,  # type: ignore[arg-type]
        temp_dir=tmp_path / "temp",
    )

    runner.mark_equipment_ready({"FSV40": True})
    qtbot.waitUntil(lambda: bool(engines) and engines[0].started.is_set())

    assert runner.context is not None
    assert runner.context.equipment_state == {"FSV40": True}
    assert runner.is_equipment_ready

    runner.stop()
    qtbot.waitUntil(lambda: not runner.is_running)


def test_mark_equipment_ready_rejects_selected_failure(tmp_path: Path) -> None:
    messages: list[str] = []
    runner = Runner(client=object(), commands=object(), temp_dir=tmp_path / "temp")
    runner.events.error.connect(messages.append)

    runner.mark_equipment_ready({"FSV40": False})

    assert messages
    assert messages[0].endswith("disconnected equipment: FSV40")
    assert not runner.is_running


def test_mark_equipment_ready_rejects_unknown_only_state(tmp_path: Path) -> None:
    messages: list[str] = []
    runner = Runner(client=object(), commands=object(), temp_dir=tmp_path / "temp")
    runner.events.error.connect(messages.append)

    runner.mark_equipment_ready({"Extra Device": True})

    assert messages
    assert messages[0].endswith("equipment_state is not ready")
    assert not runner.is_running


def test_mark_equipment_ready_allows_real_fsm_to_reach_idle(
    qtbot: Any, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    runner = Runner(
        client=object(),
        commands=object(),
        temp_dir=tmp_path / "temp",
    )

    runner.mark_equipment_ready(_ready_states())

    qtbot.waitUntil(
        lambda: (
            runner.context is not None
            and runner._worker is not None
            and runner._worker.engine is not None
            and runner._worker.engine.current_state_name == "Idle"
        ),
        timeout=1000,
    )

    runner.stop()
    qtbot.waitUntil(lambda: not runner.is_running)
    assert "Runner worker thread did not stop cleanly" not in caplog.text


def test_runner_does_not_auto_manage_lv_server_for_source_runtime(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delattr(runner_module.sys, "frozen", raising=False)

    runner = Runner(commands=object(), temp_dir=tmp_path / "temp")

    assert runner._lv_server_manager is None
    assert runner.instrument_connection_service._lv_server_manager is None


def test_runner_auto_manages_lv_server_for_frozen_owned_client(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(runner_module.sys, "frozen", True, raising=False)

    runner = Runner(
        commands=object(),
        temp_dir=tmp_path / "temp",
        tcp_host="127.0.0.10",
        tcp_port=5026,
    )

    assert runner._lv_server_manager is not None
    assert runner._lv_server_manager.host == "127.0.0.10"
    assert runner._lv_server_manager.port == 5026
    assert runner.instrument_connection_service._lv_server_manager is runner._lv_server_manager


def test_runner_uses_explicit_lv_server_manager_when_not_frozen(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delattr(runner_module.sys, "frozen", raising=False)
    lv_server_manager = object()

    runner = Runner(
        client=object(),
        commands=object(),
        temp_dir=tmp_path / "temp",
        lv_server_manager=lv_server_manager,
    )

    assert runner._lv_server_manager is lv_server_manager
    assert runner.instrument_connection_service._lv_server_manager is lv_server_manager

def test_runner_connection_service_uses_runner_client(
    qtbot: Any, tmp_path: Path
) -> None:
    client = _Client()
    commands = _ConnectionCommands(_ready_states())
    runner = Runner(
        client=client,
        commands=commands,
        temp_dir=tmp_path / "temp",
        tcp_host="127.0.0.10",
        tcp_port=5026,
    )

    with qtbot.waitSignal(
        runner.instrument_connection_service.connection_finished,
        timeout=1000,
    ):
        runner.instrument_connection_service.connect_equipment(_connection_config())
    qtbot.waitUntil(
        lambda: not runner.instrument_connection_service.is_connecting,
        timeout=1000,
    )

    assert commands.calls
    assert commands.calls[0][0] is client
    assert client.connect_calls == [("127.0.0.10", 5026)]

    runner.stop()
    qtbot.waitUntil(lambda: not runner.is_running)


def test_start_populates_context_and_sets_start_request(
    qtbot: Any, tmp_path: Path
) -> None:
    engines: list[FSMEngine] = []
    report_writers: list[_ReportWriter] = []
    resolver_thread_ids: list[int] = []
    result_path = (tmp_path / "resolved-result.xlsx").resolve()

    def engine_factory(ctx: SessionContext) -> FSMEngine:
        engine = _build_preparation_test_engine(ctx)
        engines.append(engine)
        return engine

    def result_resolver(**kwargs: Any) -> RawDataResultWorkbook:
        resolver_thread_ids.append(threading.get_ident())
        assert kwargs == {
            "screenshot_root_dir": tmp_path / "screenshots",
            "eut_name": "SM-000",
            "generation": Generation.NR_SA,
        }
        return RawDataResultWorkbook(
            kind=RawDataWorkbookKind.NR,
            path=result_path,
            created=True,
        )

    def report_writer_factory(
        workbook_path: Path,
        screenshot_root_dir: Path,
        model_name: str,
        events: Any,
    ) -> _ReportWriter:
        _ = events
        assert workbook_path == result_path
        assert screenshot_root_dir == tmp_path / "screenshots"
        assert model_name == "SM-000"
        writer = _ReportWriter()
        report_writers.append(writer)
        return writer

    runner = Runner(
        client=object(),
        commands=object(),
        engine_factory=engine_factory,  # type: ignore[arg-type]
        report_writer_factory=report_writer_factory,  # type: ignore[arg-type]
        rawdata_result_resolver=result_resolver,  # type: ignore[arg-type]
        temp_dir=tmp_path / "temp",
    )
    runner.mark_equipment_ready(_ready_states())
    qtbot.waitUntil(
        lambda: bool(engines) and engines[0].current_state_name == "Idle"
    )

    case = _make_case()
    settings = _make_settings(tmp_path)
    ui_thread_id = threading.get_ident()
    runner.start(
        [case],
        settings=settings,
    )

    ctx = runner.context
    assert ctx is not None
    qtbot.waitUntil(lambda: ctx.report_writer is not None)
    assert ctx.queue == [case]
    assert ctx.settings == settings
    assert ctx.model_name == "SM-000"
    assert ctx.result_workbook_path == result_path
    assert ctx.screenshot_root_dir == tmp_path / "screenshots"
    assert ctx.report_writer is report_writers[0]
    assert ctx.pending_run_request is None
    assert not ctx.test_start_requested.is_set()
    assert resolver_thread_ids and resolver_thread_ids[0] != ui_thread_id
    assert runner.is_measurement_active

    runner.events.state_changed.emit("Idle")
    assert runner.is_measurement_active

    runner.events.session_finished.emit()
    assert not runner.is_measurement_active

    runner.stop()
    qtbot.waitUntil(lambda: not runner.is_running)


@pytest.mark.parametrize(
    ("mixed_case_factory", "expected_generations"),
    [
        (_make_lte_case, "LTE, NR_SA"),
        (_make_nsa_case, "NR_NSA, NR_SA"),
    ],
)
def test_start_rejects_mixed_generation_queue_before_report_setup(
    qtbot: Any,
    tmp_path: Path,
    mixed_case_factory: Any,
    expected_generations: str,
) -> None:
    engines: list[_FakeEngine] = []
    report_writers: list[_ReportWriter] = []
    messages: list[str] = []

    def engine_factory(ctx: SessionContext) -> _FakeEngine:
        engine = _FakeEngine(ctx)
        engines.append(engine)
        return engine

    def report_writer_factory(*args: Any) -> _ReportWriter:
        writer = _ReportWriter()
        report_writers.append(writer)
        return writer

    runner = Runner(
        client=object(),
        commands=object(),
        engine_factory=engine_factory,  # type: ignore[arg-type]
        report_writer_factory=report_writer_factory,  # type: ignore[arg-type]
        temp_dir=tmp_path / "temp",
    )
    runner.events.error.connect(messages.append)
    runner.mark_equipment_ready(_ready_states())
    qtbot.waitUntil(lambda: bool(engines) and engines[0].started.is_set())
    engines[0].current_state_name = "Idle"

    runner.start(
        [_make_case(), mixed_case_factory()],
        settings=_make_settings(tmp_path),
    )

    ctx = runner.context
    assert ctx is not None
    assert messages == [
        "시험 시작 실패: Generation 혼합 Queue는 실행할 수 없습니다: "
        + expected_generations
    ]
    assert report_writers == []
    assert ctx.queue == []
    assert not ctx.test_start_requested.is_set()
    assert not runner.is_measurement_active

    runner.stop()
    qtbot.waitUntil(lambda: not runner.is_running)


def test_duplicate_start_does_not_replace_pending_request(
    qtbot: Any,
    tmp_path: Path,
) -> None:
    engines: list[_FakeEngine] = []
    messages: list[str] = []

    class _ReadyEngine(_FakeEngine):
        def run(self, initial_state: str = "SessionInit") -> None:
            self.initial_state = initial_state
            self.current_state_name = "Idle"
            self.started.set()
            while not self.ctx.stopped:
                time.sleep(0.01)

    def engine_factory(ctx: SessionContext) -> _ReadyEngine:
        engine = _ReadyEngine(ctx)
        engines.append(engine)
        return engine

    runner = Runner(
        client=object(),
        commands=object(),
        engine_factory=engine_factory,  # type: ignore[arg-type]
        temp_dir=tmp_path / "temp",
    )
    runner.events.error.connect(messages.append)
    runner.mark_equipment_ready(_ready_states())
    qtbot.waitUntil(lambda: bool(engines) and engines[0].started.is_set())

    first_case = _make_case()
    second_case = _make_case(antenna_pol=AntennaPol.V)
    settings = _make_settings(tmp_path)
    runner.start([first_case], settings=settings)
    runner.start([second_case], settings=settings)

    assert runner.context is not None
    assert runner.context.pending_run_request is not None
    assert runner.context.pending_run_request.cases == (first_case,)
    assert messages == ["시험 시작 실패: Runner is not idle"]

    runner.stop()
    qtbot.waitUntil(lambda: not runner.is_running)



def test_runner_emits_session_stopped_when_active_run_is_stopped(
    qtbot: Any,
    tmp_path: Path,
) -> None:
    engines: list[_FakeEngine] = []
    stopped: list[None] = []
    failed: list[None] = []

    def engine_factory(ctx: SessionContext) -> _FakeEngine:
        engine = _FakeEngine(ctx)
        engines.append(engine)
        return engine

    runner = Runner(
        client=object(),
        commands=object(),
        engine_factory=engine_factory,  # type: ignore[arg-type]
        report_writer_factory=lambda *args: _ReportWriter(),  # type: ignore[arg-type]
        temp_dir=tmp_path / "temp",
    )
    runner.events.session_stopped.connect(lambda: stopped.append(None))
    runner.events.session_failed.connect(lambda: failed.append(None))
    runner.mark_equipment_ready(_ready_states())
    qtbot.waitUntil(lambda: bool(engines) and engines[0].started.is_set())
    thread = runner._thread
    assert thread is not None
    thread_valid_at_stop: list[bool] = []
    runner.events.session_stopped.connect(
        lambda: thread_valid_at_stop.append(shiboken6.isValid(thread))
    )
    engines[0].current_state_name = "Idle"

    runner.start([_make_case()], settings=_make_settings(tmp_path))
    runner.stop()
    qtbot.waitUntil(lambda: stopped == [None])
    qtbot.waitUntil(lambda: not runner.is_running)

    assert stopped == [None]
    assert failed == []
    assert thread_valid_at_stop == [False]


def test_runner_emits_session_failed_when_active_run_exits_without_completion(
    qtbot: Any,
    tmp_path: Path,
) -> None:
    engines: list[_ExitAfterStartEngine] = []
    stopped: list[None] = []
    failed: list[None] = []

    def engine_factory(ctx: SessionContext) -> _ExitAfterStartEngine:
        engine = _ExitAfterStartEngine(ctx)
        engines.append(engine)
        return engine

    runner = Runner(
        client=object(),
        commands=object(),
        engine_factory=engine_factory,  # type: ignore[arg-type]
        report_writer_factory=lambda *args: _ReportWriter(),  # type: ignore[arg-type]
        temp_dir=tmp_path / "temp",
    )
    runner.events.session_stopped.connect(lambda: stopped.append(None))
    runner.events.session_failed.connect(lambda: failed.append(None))
    runner.mark_equipment_ready(_ready_states())
    qtbot.waitUntil(lambda: bool(engines) and engines[0].started.is_set())

    runner.start([_make_case()], settings=_make_settings(tmp_path))
    qtbot.waitUntil(lambda: failed == [None])
    qtbot.waitUntil(lambda: not runner.is_running)

    assert stopped == []
    assert failed == [None]


def test_runner_does_not_emit_stop_or_failure_after_normal_completion_cleanup(
    qtbot: Any,
    tmp_path: Path,
) -> None:
    engines: list[_FakeEngine] = []
    stopped: list[None] = []
    failed: list[None] = []

    def engine_factory(ctx: SessionContext) -> _FakeEngine:
        engine = _FakeEngine(ctx)
        engines.append(engine)
        return engine

    runner = Runner(
        client=object(),
        commands=object(),
        engine_factory=engine_factory,  # type: ignore[arg-type]
        report_writer_factory=lambda *args: _ReportWriter(),  # type: ignore[arg-type]
        temp_dir=tmp_path / "temp",
    )
    runner.events.session_stopped.connect(lambda: stopped.append(None))
    runner.events.session_failed.connect(lambda: failed.append(None))
    runner.mark_equipment_ready(_ready_states())
    qtbot.waitUntil(lambda: bool(engines) and engines[0].started.is_set())
    engines[0].current_state_name = "Idle"

    runner.start([_make_case()], settings=_make_settings(tmp_path))
    runner.events.session_finished.emit()
    runner.stop()
    qtbot.waitUntil(lambda: not runner.is_running)

    assert stopped == []
    assert failed == []


def test_start_prepares_report_writer_with_requested_start_case(
    qtbot: Any,
    tmp_path: Path,
) -> None:
    engines: list[FSMEngine] = []
    report_writers: list[_ReportWriter] = []

    def engine_factory(ctx: SessionContext) -> FSMEngine:
        engine = _build_preparation_test_engine(ctx)
        engines.append(engine)
        return engine

    def report_writer_factory(*_: Any) -> _ReportWriter:
        writer = _ReportWriter()
        report_writers.append(writer)
        return writer

    runner = Runner(
        client=object(),
        commands=object(),
        engine_factory=engine_factory,  # type: ignore[arg-type]
        report_writer_factory=report_writer_factory,  # type: ignore[arg-type]
        rawdata_result_resolver=lambda **kwargs: RawDataResultWorkbook(
            kind=RawDataWorkbookKind.NR,
            path=tmp_path / "result.xlsx",
            created=True,
        ),  # type: ignore[arg-type]
        temp_dir=tmp_path / "temp",
    )
    runner.mark_equipment_ready(_ready_states())
    qtbot.waitUntil(
        lambda: bool(engines) and engines[0].current_state_name == "Idle"
    )

    first_case = _make_case()
    second_case = _make_case(antenna_pol=AntennaPol.V)
    runner.start(
        [first_case, second_case],
        settings=_make_settings(tmp_path),
        start_index=1,
    )

    qtbot.waitUntil(
        lambda: bool(report_writers) and bool(report_writers[0].prepare_calls)
    )
    assert report_writers[0].prepare_calls == [second_case]

    runner.stop()
    qtbot.waitUntil(lambda: not runner.is_running)


def test_start_rejects_when_report_writer_prepare_fails(
    qtbot: Any,
    tmp_path: Path,
) -> None:
    engines: list[FSMEngine] = []
    messages: list[str] = []
    rejected: list[None] = []

    def engine_factory(ctx: SessionContext) -> FSMEngine:
        engine = _build_preparation_test_engine(ctx)
        engines.append(engine)
        return engine

    runner = Runner(
        client=object(),
        commands=object(),
        engine_factory=engine_factory,  # type: ignore[arg-type]
        report_writer_factory=lambda *args: _ReportWriter(
            prepare_exception=RuntimeError("excel unavailable")
        ),  # type: ignore[arg-type]
        rawdata_result_resolver=lambda **kwargs: RawDataResultWorkbook(
            kind=RawDataWorkbookKind.NR,
            path=tmp_path / "result.xlsx",
            created=True,
        ),  # type: ignore[arg-type]
        temp_dir=tmp_path / "temp",
    )
    runner.events.error.connect(messages.append)
    runner.events.start_rejected.connect(lambda: rejected.append(None))
    runner.mark_equipment_ready(_ready_states())
    qtbot.waitUntil(
        lambda: bool(engines) and engines[0].current_state_name == "Idle"
    )

    runner.start([_make_case()], settings=_make_settings(tmp_path))

    ctx = runner.context
    assert ctx is not None
    qtbot.waitUntil(lambda: rejected == [None] and not runner.is_measurement_active)
    assert not ctx.test_start_requested.is_set()
    assert not runner.is_measurement_active
    assert ctx.queue == []
    assert ctx.pending_run_request is None
    assert engines[0].current_state_name == "Idle"
    assert any("Excel report 준비 실패" in message for message in messages)

    runner.stop()
    qtbot.waitUntil(lambda: not runner.is_running)


def test_stop_during_result_resolution_skips_writer_and_measurement(
    qtbot: Any,
    tmp_path: Path,
) -> None:
    engines: list[FSMEngine] = []
    resolver_entered = threading.Event()
    resolver_release = threading.Event()
    writer_calls: list[tuple[Any, ...]] = []
    tc_started: list[int] = []
    stopped: list[None] = []

    def engine_factory(ctx: SessionContext) -> FSMEngine:
        engine = _build_preparation_test_engine(ctx)
        engines.append(engine)
        return engine

    def result_resolver(**kwargs: Any) -> RawDataResultWorkbook:
        _ = kwargs
        resolver_entered.set()
        assert resolver_release.wait(2)
        return RawDataResultWorkbook(
            kind=RawDataWorkbookKind.NR,
            path=tmp_path / "result.xlsx",
            created=True,
        )

    def writer_factory(*args: Any) -> _ReportWriter:
        writer_calls.append(args)
        return _ReportWriter()

    runner = Runner(
        client=object(),
        commands=object(),
        engine_factory=engine_factory,  # type: ignore[arg-type]
        report_writer_factory=writer_factory,  # type: ignore[arg-type]
        rawdata_result_resolver=result_resolver,  # type: ignore[arg-type]
        temp_dir=tmp_path / "temp",
    )
    runner.events.tc_started.connect(tc_started.append)
    runner.events.session_stopped.connect(lambda: stopped.append(None))
    runner.mark_equipment_ready(_ready_states())
    qtbot.waitUntil(
        lambda: bool(engines) and engines[0].current_state_name == "Idle"
    )

    runner.start([_make_case()], settings=_make_settings(tmp_path))
    assert resolver_entered.wait(1)

    started_at = time.monotonic()
    runner.stop()
    stop_elapsed = time.monotonic() - started_at
    resolver_release.set()
    qtbot.waitUntil(lambda: stopped == [None] and not runner.is_running)

    assert stop_elapsed < 0.2
    assert writer_calls == []
    assert tc_started == []
    assert runner.context is not None
    assert runner.context.queue == []
    assert runner.context.report_writer is None
    assert runner.context.pending_run_request is None


def test_start_uses_requested_start_and_stop_indexes(
    qtbot: Any,
    tmp_path: Path,
) -> None:
    engines: list[FSMEngine] = []

    def engine_factory(ctx: SessionContext) -> FSMEngine:
        engine = _build_preparation_test_engine(ctx)
        engines.append(engine)
        return engine

    runner = Runner(
        client=object(),
        commands=object(),
        engine_factory=engine_factory,  # type: ignore[arg-type]
        report_writer_factory=lambda *args: _ReportWriter(),  # type: ignore[arg-type]
        rawdata_result_resolver=lambda **kwargs: RawDataResultWorkbook(
            kind=RawDataWorkbookKind.NR,
            path=tmp_path / "result.xlsx",
            created=True,
        ),  # type: ignore[arg-type]
        temp_dir=tmp_path / "temp",
    )
    runner.mark_equipment_ready(_ready_states())
    qtbot.waitUntil(
        lambda: bool(engines) and engines[0].current_state_name == "Idle"
    )

    cases = [_make_case(), _make_case(antenna_pol=AntennaPol.V)]
    runner.start(
        cases,
        settings=_make_settings(tmp_path),
        start_index=1,
        stop_index=1,
    )

    ctx = runner.context
    assert ctx is not None
    qtbot.waitUntil(lambda: ctx.result_workbook_path is not None)
    assert ctx.start_index == 1
    assert ctx.current_index == 1
    assert ctx.stop_index == 1

    runner.stop()
    qtbot.waitUntil(lambda: not runner.is_running)


def test_start_after_stop_initializes_new_worker(
    qtbot: Any,
    tmp_path: Path,
) -> None:
    engines: list[_FakeEngine] = []

    class _ReadyEngine(_FakeEngine):
        def run(self, initial_state: str = "SessionInit") -> None:
            self.initial_state = initial_state
            self.current_state_name = "Idle"
            self.started.set()
            while not self.ctx.stopped:
                time.sleep(0.01)

    def engine_factory(ctx: SessionContext) -> _ReadyEngine:
        engine = _ReadyEngine(ctx)
        engines.append(engine)
        return engine

    runner = Runner(
        client=object(),
        commands=object(),
        engine_factory=engine_factory,  # type: ignore[arg-type]
        report_writer_factory=lambda *args: _ReportWriter(),  # type: ignore[arg-type]
        temp_dir=tmp_path / "temp",
    )
    runner.mark_equipment_ready(_ready_states())
    qtbot.waitUntil(lambda: len(engines) == 1 and engines[0].started.is_set())
    runner.stop()
    qtbot.waitUntil(lambda: not runner.is_running, timeout=1000)

    case = _make_case()
    runner.start([case], settings=_make_settings(tmp_path), start_index=0)

    qtbot.waitUntil(lambda: len(engines) == 2 and engines[1].started.is_set())
    assert runner.context is not None
    assert runner.context.queue == []
    assert runner.context.pending_run_request is not None
    assert runner.context.pending_run_request.cases == (case,)
    assert runner.context.pending_run_request.start_index == 0
    assert runner.context.test_start_requested.is_set()
    assert runner.is_measurement_active

    runner.events.state_changed.emit("Idle")
    assert runner.is_measurement_active

    runner.stop()
    qtbot.waitUntil(lambda: not runner.is_running)


def test_stop_cleanup_gap_rejects_restart_until_generation_is_finalized(
    qtbot: Any,
    tmp_path: Path,
) -> None:
    engines: list[_FakeEngine] = []
    messages: list[str] = []
    report_writers: list[_ReportWriter] = []

    def engine_factory(ctx: SessionContext) -> _FakeEngine:
        engine = _FakeEngine(ctx)
        engines.append(engine)
        return engine

    def report_writer_factory(*_: Any) -> _ReportWriter:
        writer = _ReportWriter()
        report_writers.append(writer)
        return writer

    runner = Runner(
        client=object(),
        commands=object(),
        engine_factory=engine_factory,  # type: ignore[arg-type]
        report_writer_factory=report_writer_factory,  # type: ignore[arg-type]
        temp_dir=tmp_path / "temp",
    )
    runner.events.error.connect(messages.append)
    runner.mark_equipment_ready(_ready_states())
    qtbot.waitUntil(lambda: len(engines) == 1 and engines[0].started.is_set())
    engines[0].current_state_name = "Idle"

    thread = runner._thread
    worker = runner._worker
    ctx = runner.context
    generation = runner._active_generation
    assert thread is not None
    assert generation is not None

    runner.stop()
    assert thread.wait(1000)
    assert runner.is_running
    assert ctx is not None and ctx.stopped

    runner.initialize()
    runner.start([_make_case()], settings=_make_settings(tmp_path))

    assert runner._thread is thread
    assert runner._worker is worker
    assert runner.context is ctx
    assert runner._active_generation == generation
    assert len(engines) == 1
    assert report_writers == []
    assert messages == ["시험 시작 실패: Runner is not idle"]
    assert ctx.stopped

    runner._finalize_thread(thread, generation)
    assert runner.is_running
    assert runner._thread is None
    assert runner._worker is None
    qtbot.waitUntil(lambda: not runner.is_running)


def test_stale_thread_completion_cannot_clear_new_generation(
    qtbot: Any,
    tmp_path: Path,
) -> None:
    engines: list[_FakeEngine] = []

    def engine_factory(ctx: SessionContext) -> _FakeEngine:
        engine = _FakeEngine(ctx)
        engines.append(engine)
        return engine

    runner = Runner(
        client=object(),
        commands=object(),
        engine_factory=engine_factory,  # type: ignore[arg-type]
        temp_dir=tmp_path / "temp",
    )
    runner.initialize()
    qtbot.waitUntil(lambda: len(engines) == 1 and engines[0].started.is_set())
    old_thread = runner._thread
    old_generation = runner._active_generation
    assert old_thread is not None
    assert old_generation is not None
    runner.stop()
    qtbot.waitUntil(lambda: not runner.is_running)

    runner.initialize()
    qtbot.waitUntil(lambda: len(engines) == 2 and engines[1].started.is_set())
    current_thread = runner._thread
    current_worker = runner._worker
    current_context = runner.context
    current_generation = runner._active_generation
    assert current_generation is not None
    assert current_generation > old_generation

    runner._finalize_thread(old_thread, old_generation)

    assert runner.is_running
    assert runner._thread is current_thread
    assert runner._worker is current_worker
    assert runner.context is current_context
    assert runner._active_generation == current_generation

    runner.stop()
    qtbot.waitUntil(lambda: not runner.is_running)


def test_runner_survives_fifty_stop_restart_generations(
    qtbot: Any,
    tmp_path: Path,
) -> None:
    engines: list[_FakeEngine] = []
    generations: list[int] = []

    def engine_factory(ctx: SessionContext) -> _FakeEngine:
        engine = _FakeEngine(ctx)
        engines.append(engine)
        return engine

    runner = Runner(
        client=object(),
        commands=object(),
        engine_factory=engine_factory,  # type: ignore[arg-type]
        temp_dir=tmp_path / "temp",
    )

    for index in range(50):
        runner.initialize()
        qtbot.waitUntil(
            lambda index=index: (
                len(engines) == index + 1 and engines[index].started.is_set()
            ),
            timeout=1000,
        )
        assert runner._active_generation is not None
        generations.append(runner._active_generation)
        runner.stop()
        qtbot.waitUntil(lambda: not runner.is_running, timeout=1000)

    assert generations == list(range(1, 51))
    assert runner._generation == 50


def test_shutdown_is_idempotent_and_prevents_restart(
    qtbot: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    engines: list[_FakeEngine] = []
    client = _ClosableClient()
    completed: list[None] = []

    def engine_factory(ctx: SessionContext) -> _FakeEngine:
        engine = _FakeEngine(ctx)
        engines.append(engine)
        return engine

    monkeypatch.setattr(runner_module, "TcpClient", lambda _parent=None: client)
    runner = Runner(
        commands=object(),
        engine_factory=engine_factory,  # type: ignore[arg-type]
        temp_dir=tmp_path / "temp",
    )
    runner.shutdown_finished.connect(lambda: completed.append(None))
    runner.initialize()
    qtbot.waitUntil(lambda: len(engines) == 1 and engines[0].started.is_set())

    assert not runner.shutdown()
    qtbot.waitUntil(lambda: completed == [None] and not runner.is_running)
    assert runner.shutdown()

    assert completed == [None]
    assert client.close_calls == 1
    assert not runner.is_running
    generation = runner._generation

    runner.initialize()

    assert not runner.is_running
    assert runner._generation == generation
    assert len(engines) == 1


def test_shutdown_timeout_keeps_entire_runner_alive_until_worker_finishes(
    qtbot: Any,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    release = threading.Event()
    engines: list[_BlockingEngine] = []
    completed: list[None] = []
    owner = QObject()
    client = _ClosableClient()

    def engine_factory(ctx: SessionContext) -> _BlockingEngine:
        engine = _BlockingEngine(ctx, release)
        engines.append(engine)
        return engine

    monkeypatch.setattr(runner_module, "_SHUTDOWN_WAIT_MS", 10)
    monkeypatch.setattr(runner_module, "TcpClient", lambda _parent=None: client)
    runner = Runner(
        owner,
        commands=object(),
        engine_factory=engine_factory,  # type: ignore[arg-type]
        temp_dir=tmp_path / "temp",
    )
    runner.shutdown_finished.connect(lambda: completed.append(None))
    runner.initialize()
    qtbot.waitUntil(lambda: len(engines) == 1 and engines[0].started.is_set())

    thread = runner._thread
    worker = runner._worker
    ctx = runner.context
    events = runner.events
    assert thread is not None
    assert worker is not None
    assert ctx is not None

    assert not runner.shutdown()
    assert not runner.shutdown()

    assert runner.parent() is None
    assert runner_module._SHUTDOWN_KEEPERS[id(runner)] is runner
    assert runner._thread is thread
    assert runner._worker is worker
    assert runner.context is ctx
    assert runner.events is events
    assert runner.client is client
    assert client.close_calls == 0
    assert runner.is_running
    assert completed == []

    owner.deleteLater()
    QCoreApplication.sendPostedEvents(owner, QEvent.Type.DeferredDelete)
    assert runner_module._SHUTDOWN_KEEPERS[id(runner)] is runner
    assert runner._thread is thread
    assert runner._worker is worker
    assert runner.context is ctx
    assert runner.events is events
    assert runner.client is client
    assert client.close_calls == 0

    release.set()
    qtbot.waitUntil(
        lambda: completed == [None] and not runner.is_running,
        timeout=1000,
    )

    assert id(runner) not in runner_module._SHUTDOWN_KEEPERS
    assert runner._thread is None
    assert runner._worker is None
    assert not shiboken6.isValid(thread)
    assert not shiboken6.isValid(worker)
    assert runner.context is ctx
    assert client.close_calls == 1
    assert runner.shutdown()


def test_start_ignores_previous_stop_state_and_uses_requested_index(
    qtbot: Any,
    tmp_path: Path,
) -> None:
    engines: list[_FakeEngine] = []

    def engine_factory(ctx: SessionContext) -> _FakeEngine:
        engine = _FakeEngine(ctx)
        engines.append(engine)
        return engine

    runner = Runner(
        client=object(),
        commands=object(),
        engine_factory=engine_factory,  # type: ignore[arg-type]
        report_writer_factory=lambda *args: _ReportWriter(),  # type: ignore[arg-type]
        temp_dir=tmp_path / "temp",
    )
    runner.mark_equipment_ready(_ready_states())
    qtbot.waitUntil(lambda: bool(engines) and engines[0].started.is_set())
    engines[0].current_state_name = "Idle"

    cases = [_make_case(), _make_case(antenna_pol=AntennaPol.V)]
    runner.start(
        cases,
        settings=_make_settings(tmp_path),
        start_index=1,
    )

    ctx = runner.context
    assert ctx is not None
    assert ctx.pending_run_request is not None
    assert ctx.pending_run_request.cases == tuple(cases)
    assert ctx.pending_run_request.start_index == 1
    assert ctx.queue == []

    runner.stop()
    qtbot.waitUntil(lambda: not runner.is_running)

def test_start_rejects_while_instrument_set_is_active(
    qtbot: Any, tmp_path: Path
) -> None:
    engines: list[_FakeEngine] = []
    messages: list[str] = []

    def engine_factory(ctx: SessionContext) -> _FakeEngine:
        engine = _FakeEngine(ctx)
        engines.append(engine)
        return engine

    runner = Runner(
        client=object(),
        commands=object(),
        engine_factory=engine_factory,  # type: ignore[arg-type]
        temp_dir=tmp_path / "temp",
    )
    runner.events.error.connect(messages.append)
    runner.mark_equipment_ready(_ready_states())
    qtbot.waitUntil(lambda: bool(engines) and engines[0].started.is_set())
    engines[0].current_state_name = "Idle"
    runner.instrument_connection_service._set_thread = object()  # type: ignore[assignment]

    runner.start(
        [_make_case()],
        settings=_make_settings(tmp_path),
    )

    assert messages == [f"시험 시작 실패: {INSTRUMENT_SET_BLOCK_MESSAGE}"]
    assert runner.context is not None
    assert not runner.context.test_start_requested.is_set()
    assert not runner.is_measurement_active

    runner.instrument_connection_service._set_thread = None
    runner.stop()
    qtbot.waitUntil(lambda: not runner.is_running)


def test_equipment_disconnected_clears_runner_equipment_state(
    qtbot: Any, tmp_path: Path
) -> None:
    engines: list[_FakeEngine] = []

    def engine_factory(ctx: SessionContext) -> _FakeEngine:
        engine = _FakeEngine(ctx)
        engines.append(engine)
        return engine

    runner = Runner(
        client=object(),
        commands=object(),
        engine_factory=engine_factory,  # type: ignore[arg-type]
        temp_dir=tmp_path / "temp",
    )
    runner.mark_equipment_ready(_ready_states())
    qtbot.waitUntil(lambda: bool(engines) and engines[0].started.is_set())

    runner.instrument_connection_service.equipment_disconnected.emit(
        disconnected_equipment_state()
    )

    assert runner.equipment_state == {}
    assert runner.context is not None
    assert runner.context.equipment_state == {}

    runner.stop()
    qtbot.waitUntil(lambda: not runner.is_running)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("eut_name", " "),
        ("eut_name", " SM-000"),
        ("eut_name", "SM-000 "),
        ("saturation_time_sec", -1),
        ("connection_waiting_time_sec", 0),
        ("connection_waiting_time_sec", 1.5),
        ("atten_level_db", -0.1),
        ("next_peak_search_level_db", 0),
        ("next_peak_search_level_db", -0.1),
        ("next_peak_search_level_db", 80.1),
        ("next_peak_search_level_db", float("inf")),
        ("custom_turntable_speed", 0),
        ("custom_turntable_speed", -1),
        ("custom_turntable_speed", 1.5),
        ("custom_turntable_speed", 11),
    ],
)
def test_test_run_settings_rejects_invalid_values(
    tmp_path: Path,
    field: str,
    value: Any,
) -> None:
    template_path = tmp_path / "template.xlsx"
    screenshot_root_dir = tmp_path / "screenshots"
    template_path.write_bytes(b"template")
    screenshot_root_dir.mkdir()
    kwargs = {
        "eut_name": "SM-000",
        "template_path": template_path,
        "screenshot_root_dir": screenshot_root_dir,
        "saturation_time_sec": 5,
        "connection_waiting_time_sec": 5,
        "atten_level_db": 0,
        "next_peak_search_level_db": 6,
    }
    kwargs[field] = value

    with pytest.raises(ValueError):
        TestRunSettings(**kwargs)


def test_default_screenshot_root_dir_uses_desktop_for_source_runtime(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delattr(test_run_settings.sys, "frozen", raising=False)
    monkeypatch.setattr(test_run_settings.Path, "home", lambda: tmp_path)

    assert default_screenshot_root_dir() == tmp_path / "Desktop" / "screenshots"


def test_default_screenshot_root_dir_uses_executable_dir_for_frozen_runtime(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    executable = tmp_path / "NRRadiated.exe"
    monkeypatch.setattr(test_run_settings.sys, "frozen", True, raising=False)
    monkeypatch.setattr(test_run_settings.sys, "executable", str(executable))

    assert default_screenshot_root_dir() == tmp_path.resolve() / "screenshots"


def test_test_run_settings_accepts_optional_custom_turntable_speed(
    tmp_path: Path,
) -> None:
    template_path = tmp_path / "template.xlsx"
    screenshot_root_dir = tmp_path / "screenshots"
    template_path.write_bytes(b"template")
    screenshot_root_dir.mkdir()

    default_settings = TestRunSettings(
        eut_name="SM-000",
        template_path=template_path,
        screenshot_root_dir=screenshot_root_dir,
        saturation_time_sec=5,
        connection_waiting_time_sec=5,
        atten_level_db=0,
        next_peak_search_level_db=6,
    )
    custom_settings = TestRunSettings(
        eut_name="SM-000",
        template_path=template_path,
        screenshot_root_dir=screenshot_root_dir,
        saturation_time_sec=5,
        connection_waiting_time_sec=5,
        atten_level_db=0,
        next_peak_search_level_db=6,
        custom_turntable_speed="8",
    )

    assert default_settings.custom_turntable_speed is None
    assert custom_settings.custom_turntable_speed == 8


def test_test_run_settings_rejects_missing_template_path(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="template_path"):
        TestRunSettings(
            eut_name="SM-000",
            template_path=tmp_path / "missing.xlsx",
            screenshot_root_dir=tmp_path / "screenshots",
            saturation_time_sec=5,
            connection_waiting_time_sec=5,
            atten_level_db=0,
            next_peak_search_level_db=6,
        )


def test_test_run_settings_allows_missing_screenshot_directory(tmp_path: Path) -> None:
    template_path = tmp_path / "template.xlsx"
    screenshot_root_dir = tmp_path / "missing-screenshots"
    template_path.write_bytes(b"template")

    settings = TestRunSettings(
        eut_name="SM-000",
        template_path=template_path,
        screenshot_root_dir=screenshot_root_dir,
        saturation_time_sec=5,
        connection_waiting_time_sec=5,
        atten_level_db=0,
        next_peak_search_level_db=6,
    )

    assert settings.screenshot_root_dir == screenshot_root_dir


def test_test_run_settings_rejects_screenshot_path_that_is_file(tmp_path: Path) -> None:
    template_path = tmp_path / "template.xlsx"
    screenshot_root_dir = tmp_path / "screenshot-file"
    template_path.write_bytes(b"template")
    screenshot_root_dir.write_bytes(b"not a directory")

    with pytest.raises(ValueError, match="screenshot_root_dir"):
        TestRunSettings(
            eut_name="SM-000",
            template_path=template_path,
            screenshot_root_dir=screenshot_root_dir,
            saturation_time_sec=5,
            connection_waiting_time_sec=5,
            atten_level_db=0,
            next_peak_search_level_db=6,
        )


def test_runner_connection_service_guard_blocks_when_measurement_active(
    qtbot: Any, tmp_path: Path
) -> None:
    engines: list[_FakeEngine] = []
    client = _Client()
    commands = _ConnectionCommands(_ready_states())

    def engine_factory(ctx: SessionContext) -> _FakeEngine:
        engine = _FakeEngine(ctx)
        engines.append(engine)
        return engine

    def report_writer_factory(
        template_path: Path,
        screenshot_root_dir: Path,
        model_name: str,
        events: Any,
    ) -> _ReportWriter:
        _ = template_path, screenshot_root_dir, model_name, events
        return _ReportWriter()

    runner = Runner(
        client=client,
        commands=commands,
        engine_factory=engine_factory,  # type: ignore[arg-type]
        report_writer_factory=report_writer_factory,  # type: ignore[arg-type]
        temp_dir=tmp_path / "temp",
    )
    runner.mark_equipment_ready(_ready_states())
    qtbot.waitUntil(lambda: bool(engines) and engines[0].started.is_set())
    engines[0].current_state_name = "Idle"
    runner.start(
        [_make_case()],
        settings=_make_settings(tmp_path),
    )

    with qtbot.waitSignal(
        runner.instrument_connection_service.error_occurred,
        timeout=1000,
    ) as blocker:
        runner.instrument_connection_service.connect_equipment(_connection_config())

    assert blocker.args == [INSTRUMENT_CONNECTION_BLOCK_MESSAGE]
    assert runner.equipment_state == _ready_states()
    assert commands.calls == []
    assert client.connect_calls == []

    runner.stop()
    qtbot.waitUntil(lambda: not runner.is_running)


def test_start_rejects_when_runner_is_not_idle(
    qtbot: Any, tmp_path: Path
) -> None:
    engines: list[_FakeEngine] = []
    messages: list[str] = []
    report_writers: list[_ReportWriter] = []

    def engine_factory(ctx: SessionContext) -> _FakeEngine:
        engine = _FakeEngine(ctx)
        engines.append(engine)
        return engine

    def report_writer_factory(
        template_path: Path,
        screenshot_root_dir: Path,
        model_name: str,
        events: Any,
    ) -> _ReportWriter:
        writer = _ReportWriter()
        report_writers.append(writer)
        return writer

    runner = Runner(
        client=object(),
        commands=object(),
        engine_factory=engine_factory,  # type: ignore[arg-type]
        report_writer_factory=report_writer_factory,  # type: ignore[arg-type]
        temp_dir=tmp_path / "temp",
    )
    runner.events.error.connect(messages.append)
    runner.mark_equipment_ready(_ready_states())
    qtbot.waitUntil(lambda: bool(engines) and engines[0].started.is_set())

    ctx = runner.context
    assert ctx is not None
    original_case = _make_case()
    ctx.queue = [original_case]
    engines[0].current_state_name = "MeasureFundamental"

    runner.start(
        [_make_case(antenna_pol=AntennaPol.V)],
        settings=_make_settings(tmp_path),
    )

    assert messages == ["시험 시작 실패: Runner is not idle"]
    assert ctx.queue == [original_case]
    assert not ctx.test_start_requested.is_set()
    assert report_writers == []

    runner.stop()
    qtbot.waitUntil(lambda: not runner.is_running)


def test_start_before_equipment_ready_emits_error(tmp_path: Path) -> None:
    messages: list[str] = []
    runner = Runner(client=object(), commands=object(), temp_dir=tmp_path / "temp")
    runner.events.error.connect(messages.append)

    runner.start(
        [_make_case()],
        settings=_make_settings(tmp_path),
    )

    assert messages
    assert "Instrument Check" in messages[0]
