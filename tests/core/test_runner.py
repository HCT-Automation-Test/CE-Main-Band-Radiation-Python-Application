from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

from app.core.fsm.context import SessionContext
from app.core.runner import Runner
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


class _ReportWriter:
    pass


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


def test_connect_equipment_sets_session_init_request(
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

    runner.connect_equipment()
    qtbot.waitUntil(lambda: bool(engines) and engines[0].started.is_set())

    assert runner.context is not None
    assert runner.context.equipment_connect_requested.is_set()

    runner.stop()
    qtbot.waitUntil(lambda: not runner.is_running)


def test_start_populates_context_and_sets_start_request(
    qtbot: Any, tmp_path: Path
) -> None:
    engines: list[_FakeEngine] = []
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
        assert template_path == tmp_path / "template.xlsx"
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
        temp_dir=tmp_path / "temp",
    )
    runner.initialize()
    qtbot.waitUntil(lambda: bool(engines) and engines[0].started.is_set())
    engines[0].current_state_name = "Idle"

    case = _make_case()
    runner.start(
        [case],
        model_name=" SM-000 ",
        template_path=tmp_path / "template.xlsx",
        screenshot_root_dir=tmp_path / "screenshots",
    )

    ctx = runner.context
    assert ctx is not None
    assert ctx.queue == [case]
    assert ctx.model_name == "SM-000"
    assert ctx.template_path == tmp_path / "template.xlsx"
    assert ctx.screenshot_root_dir == tmp_path / "screenshots"
    assert ctx.report_writer is report_writers[0]
    assert ctx.test_start_requested.is_set()

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
    runner.initialize()
    qtbot.waitUntil(lambda: bool(engines) and engines[0].started.is_set())

    ctx = runner.context
    assert ctx is not None
    original_case = _make_case()
    ctx.queue = [original_case]
    engines[0].current_state_name = "MeasureFundamental"

    runner.start(
        [_make_case(antenna_pol=AntennaPol.V)],
        model_name="SM-000",
        template_path=tmp_path / "template.xlsx",
        screenshot_root_dir=tmp_path / "screenshots",
    )

    assert messages == ["시험 시작 실패: Runner is not idle"]
    assert ctx.queue == [original_case]
    assert not ctx.test_start_requested.is_set()
    assert report_writers == []

    runner.stop()
    qtbot.waitUntil(lambda: not runner.is_running)


def test_start_before_initialize_emits_error(tmp_path: Path) -> None:
    messages: list[str] = []
    runner = Runner(client=object(), commands=object(), temp_dir=tmp_path / "temp")
    runner.events.error.connect(messages.append)

    runner.start(
        [_make_case()],
        model_name="SM-000",
        template_path=tmp_path / "template.xlsx",
        screenshot_root_dir=tmp_path / "screenshots",
    )

    assert messages == ["시험 시작 실패: Runner is not initialized"]
