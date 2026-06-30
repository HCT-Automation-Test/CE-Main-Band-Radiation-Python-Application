from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

import pytest

import app.core.runner as runner_module

from app.core.fsm.context import SessionContext
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
        active_tdf_file_name="NR_Radiated.tdf",
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
    runner.mark_equipment_ready(_ready_states())
    qtbot.waitUntil(lambda: bool(engines) and engines[0].started.is_set())
    engines[0].current_state_name = "Idle"

    case = _make_case()
    settings = _make_settings(tmp_path, eut_name=" SM-000 ")
    runner.start(
        [case],
        settings=settings,
    )

    ctx = runner.context
    assert ctx is not None
    assert ctx.queue == [case]
    assert ctx.settings == settings
    assert ctx.settings.active_tdf_file_name == "NR_Radiated.tdf"
    assert ctx.model_name == "SM-000"
    assert ctx.template_path == tmp_path / "template.xlsx"
    assert ctx.screenshot_root_dir == tmp_path / "screenshots"
    assert ctx.report_writer is report_writers[0]
    assert ctx.test_start_requested.is_set()
    assert runner.is_measurement_active

    runner.events.state_changed.emit("Idle")
    assert runner.is_measurement_active

    runner.events.session_finished.emit()
    assert not runner.is_measurement_active

    runner.stop()
    qtbot.waitUntil(lambda: not runner.is_running)



def test_start_prepares_report_writer_with_requested_start_case(
    qtbot: Any,
    tmp_path: Path,
) -> None:
    engines: list[_FakeEngine] = []
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
    runner.mark_equipment_ready(_ready_states())
    qtbot.waitUntil(lambda: bool(engines) and engines[0].started.is_set())
    engines[0].current_state_name = "Idle"

    first_case = _make_case()
    second_case = _make_case(antenna_pol=AntennaPol.V)
    runner.start(
        [first_case, second_case],
        settings=_make_settings(tmp_path),
        start_index=1,
    )

    assert report_writers[0].prepare_calls == [second_case]

    runner.stop()
    qtbot.waitUntil(lambda: not runner.is_running)


def test_start_rejects_when_report_writer_prepare_fails(
    qtbot: Any,
    tmp_path: Path,
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
        report_writer_factory=lambda *args: _ReportWriter(
            prepare_exception=RuntimeError("excel unavailable")
        ),  # type: ignore[arg-type]
        temp_dir=tmp_path / "temp",
    )
    runner.events.error.connect(messages.append)
    runner.mark_equipment_ready(_ready_states())
    qtbot.waitUntil(lambda: bool(engines) and engines[0].started.is_set())
    engines[0].current_state_name = "Idle"

    runner.start([_make_case()], settings=_make_settings(tmp_path))

    ctx = runner.context
    assert ctx is not None
    assert not ctx.test_start_requested.is_set()
    assert not runner.is_measurement_active
    assert ctx.queue == []
    assert any("Excel report 준비 실패" in message for message in messages)

    runner.stop()
    qtbot.waitUntil(lambda: not runner.is_running)


def test_start_uses_requested_start_and_stop_indexes(
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
        stop_index=1,
    )

    ctx = runner.context
    assert ctx is not None
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
    assert runner.context.queue == [case]
    assert runner.context.start_index == 0
    assert runner.context.test_start_requested.is_set()
    assert runner.is_measurement_active

    runner.events.state_changed.emit("Idle")
    assert runner.is_measurement_active

    runner.stop()
    qtbot.waitUntil(lambda: not runner.is_running)


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
    assert ctx.start_index == 1
    assert ctx.current_index == 1

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
        ("active_tdf_file_name", " "),
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
        "active_tdf_file_name": "NR_Radiated.tdf",
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
        active_tdf_file_name="NR_Radiated.tdf",
    )
    custom_settings = TestRunSettings(
        eut_name="SM-000",
        template_path=template_path,
        screenshot_root_dir=screenshot_root_dir,
        saturation_time_sec=5,
        connection_waiting_time_sec=5,
        atten_level_db=0,
        next_peak_search_level_db=6,
        active_tdf_file_name="NR_Radiated.tdf",
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
            active_tdf_file_name="NR_Radiated.tdf",
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
        active_tdf_file_name="NR_Radiated.tdf",
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
            active_tdf_file_name="NR_Radiated.tdf",
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
