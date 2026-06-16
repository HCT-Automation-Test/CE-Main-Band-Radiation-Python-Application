from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.core.fsm.context import SessionContext
from app.core.fsm.engine import build_session_engine
from app.core.fsm.states.measurement import common as common_module
from app.core.fsm.states import nr_setup as nr_setup_module
from app.core.fsm.states import transition as transition_module
from app.models.enums import (
    AntennaPol,
    DUTAntPosition,
    DUTAxis,
    FilterPath,
    InputPath,
    Modulation,
    NRBand,
    RBAllocation,
    TestChannel as ChannelEnum,
    TestType as MeasurementTestType,
)
from app.models.measurement_result import (
    BilogResult,
    FundamentalResult,
    HarmonicMarker,
    HarmonicResult,
    InbandResult,
)
from app.models.test_case import TestCase
from app.models.test_run_settings import TestRunSettings


class _Signal:
    def __init__(self, on_emit: Any | None = None) -> None:
        self.values: list[Any] = []
        self._slots: list[Any] = []
        self._on_emit = on_emit

    def connect(self, slot: Any, *args: Any, **kwargs: Any) -> None:
        self._slots.append(slot)

    def disconnect(self, slot: Any) -> None:
        self._slots.remove(slot)

    def emit(self, value: Any = None) -> None:
        self.values.append(value)
        if self._on_emit is not None:
            self._on_emit(value)
        for slot in list(self._slots):
            slot(value)


class _Events:
    def __init__(self) -> None:
        self.tc_started = _Signal()
        self.tc_finished = _Signal()
        self.current_case_changed = _Signal()
        self.user_action_required = _Signal()
        self.spectrum_analyzer_info_changed = _Signal()
        self.switch_box_info_changed = _Signal()
        self.turntable_info_changed = _Signal()
        self.polarization_info_changed = _Signal()
        self.state_changed = _Signal()
        self.progress = _Signal()
        self.screenshot_saved = _Signal()
        self.session_finished = _Signal()
        self.error = _Signal()


class _FakeEvent:
    def __init__(
        self,
        command: str,
        params: dict[str, Any] | None = None,
        *,
        target: str = common_module._TARGET_TURNTABLE,
    ) -> None:
        self.target = target
        self.command = command
        self.params = params or {}


class _FakeClient:
    def __init__(self) -> None:
        self.event_received = _Signal()
        self._event_buffer: list[_FakeEvent] = []

    def buffer_event(self, event: _FakeEvent) -> None:
        self._event_buffer.append(event)

    def pop_events(self, predicate: Any) -> list[_FakeEvent]:
        matched: list[_FakeEvent] = []
        remaining: list[_FakeEvent] = []
        for event in self._event_buffer:
            if predicate(event):
                matched.append(event)
            else:
                remaining.append(event)
        self._event_buffer = remaining
        return matched


class _Commands:
    def __init__(self, *, setup_mt8000_results: list[bool] | None = None) -> None:
        self.setup_mt8000_results = list(setup_mt8000_results or [True])
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.temp_dir = Path("temp")

    def setup_sa_startup_levels(self, client: Any, **params: Any) -> bool:
        self.calls.append(("setup_sa_startup_levels", params))
        return True

    def preset_sa(self, client: Any) -> bool:
        self.calls.append(("preset_sa", {}))
        return True

    def setup_mt8000(self, client: Any, **params: Any) -> bool:
        self.calls.append(("setup_mt8000", params))
        if len(self.setup_mt8000_results) > 1:
            return self.setup_mt8000_results.pop(0)
        return self.setup_mt8000_results[0]

    def call_handover(self, client: Any, **params: Any) -> bool:
        self.calls.append(("call_handover", params))
        return True

    def check_call_status(self, client: Any) -> bool:
        self.calls.append(("check_call_status", {}))
        return True

    def get_turntable_angle(self, client: Any) -> float:
        self.calls.append(("get_turntable_angle", {}))
        return 0.0

    def set_antenna_pol(self, client: Any, **params: Any) -> bool:
        self.calls.append(("set_antenna_pol", params))
        return True

    def set_switch_box(
        self,
        client: Any,
        *,
        input_path: InputPath,
        filter_path: FilterPath,
    ) -> bool:
        self.calls.append(
            (
                "set_switch_box",
                {"input_path": input_path, "filter_path": filter_path},
            )
        )
        return True

    def set_tdf(self, client: Any, **params: Any) -> bool:
        self.calls.append(("set_tdf", params))
        return True

    def setup_sa(self, client: Any, *, test_range: Any) -> bool:
        self.calls.append(("setup_sa", {"test_range": test_range}))
        return True

    def rotate_turntable(self, client: _FakeClient, **params: Any) -> None:
        self.calls.append(("rotate_turntable", params))
        client.buffer_event(_FakeEvent(common_module._COMMAND_TURNTABLE_COMPLETE))

    def stop_turntable(self, client: Any) -> None:
        self.calls.append(("stop_turntable", {}))

    def measure_fundamental(self, client: Any, *, target_freq: float) -> float:
        self.calls.append(("measure_fundamental", {"target_freq": target_freq}))
        self.temp_dir.mkdir(exist_ok=True)
        (self.temp_dir / "fundamental.png").write_bytes(b"fundamental")
        return target_freq + 0.25

    def measure_harmonics(self, client: Any, *, fundamental: float) -> list[HarmonicMarker]:
        self.calls.append(("measure_harmonics", {"fundamental": fundamental}))
        self.temp_dir.mkdir(exist_ok=True)
        (self.temp_dir / "harmonic.png").write_bytes(b"harmonic")
        return [
            HarmonicMarker(order=2, amplitude_dbm=-28.0, peak_frequency_mhz=7100.5),
            HarmonicMarker(order=3, amplitude_dbm=-45.0, peak_frequency_mhz=10650.75),
            HarmonicMarker(order=4, amplitude_dbm=-46.0, peak_frequency_mhz=14201.0),
            HarmonicMarker(order=5, amplitude_dbm=-47.0, peak_frequency_mhz=17751.25),
        ]

    def setup_sa_precision(
        self,
        client: Any,
        *,
        peak_frequency: float,
        sweep_time: int,
    ) -> bool:
        self.calls.append(
            (
                "setup_sa_precision",
                {"peak_frequency": peak_frequency, "sweep_time": sweep_time},
            )
        )
        return True

    def measure_harmonic_precision(self, client: Any) -> float:
        self.calls.append(("measure_harmonic_precision", {}))
        self.temp_dir.mkdir(exist_ok=True)
        (self.temp_dir / "precision.png").write_bytes(b"precision")
        return -40.0

    def measure_inband(self, client: Any, *, limit: float) -> float:
        self.calls.append(("measure_inband", {"limit": limit}))
        self.temp_dir.mkdir(exist_ok=True)
        (self.temp_dir / "inband.png").write_bytes(b"inband")
        return limit + 1.0

    def measure_bilog(self, client: Any, *, limit: float) -> float:
        self.calls.append(("measure_bilog", {"limit": limit}))
        self.temp_dir.mkdir(exist_ok=True)
        (self.temp_dir / "inband.png").write_bytes(b"bilog")
        return limit + 1.0


class _ReportWriter:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []

    def read_fundamental_frequency(self, test_case: TestCase) -> float | None:
        self.calls.append(("read_fundamental_frequency", test_case))
        return None

    def write_fundamental(
        self,
        test_case: TestCase,
        result: FundamentalResult,
    ) -> bool:
        self.calls.append(("write_fundamental", result))
        return True

    def write_harmonic(
        self,
        test_case: TestCase,
        result: HarmonicResult,
    ) -> bool:
        self.calls.append(("write_harmonic", result))
        return True

    def write_inband(
        self,
        test_case: TestCase,
        result: InbandResult,
    ) -> bool:
        self.calls.append(("write_inband", result))
        return True

    def write_bilog(
        self,
        test_case: TestCase,
        result: BilogResult,
    ) -> bool:
        self.calls.append(("write_bilog", result))
        return True


def _make_case(
    test_type: MeasurementTestType = MeasurementTestType.HARMONIC,
    *,
    band: NRBand = NRBand.N78,
    bandwidth: float = 100.0,
    antenna_pol: AntennaPol = AntennaPol.H,
    dut_axis: DUTAxis = DUTAxis.X,
    test_channel: ChannelEnum = ChannelEnum.MID,
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


def _make_settings(tmp_path: Path) -> TestRunSettings:
    template_path = tmp_path / "template.xlsx"
    screenshot_root_dir = tmp_path / "screenshots"
    template_path.write_bytes(b"template")
    screenshot_root_dir.mkdir(exist_ok=True)
    return TestRunSettings(
        eut_name="SM-000",
        template_path=template_path,
        screenshot_root_dir=screenshot_root_dir,
        saturation_time_sec=0,
        connection_waiting_time_sec=1,
        atten_level_db=0,
        next_peak_search_level_db=0,
        active_tdf_file_name="NR_Radiated.tdf",
    )


def _make_ctx(
    tmp_path: Path,
    queue: list[TestCase],
    *,
    commands: _Commands | None = None,
    report_writer: _ReportWriter | None = None,
) -> tuple[SessionContext, _Events, _Commands, _ReportWriter]:
    events = _Events()
    command_facade = commands or _Commands()
    command_facade.temp_dir = tmp_path
    writer = report_writer or _ReportWriter()
    ctx = SessionContext(
        queue=list(queue),
        commands=command_facade,
        events=events,  # type: ignore[arg-type]
        client=_FakeClient(),
        report_writer=writer,  # type: ignore[arg-type]
        temp_dir=tmp_path,
        settings=_make_settings(tmp_path),
        model_name="SM-000",
        template_path=tmp_path / "template.xlsx",
        screenshot_root_dir=tmp_path / "screenshots",
        equipment_state={
            "FSV40": True,
            "MT8000A": True,
            "CO3000": True,
            "Switch Box": True,
            "3D Controller": True,
        },
    )

    def stop_on_session_finished(_: Any = None) -> None:
        ctx.stopped = True

    def complete_user_action(_: Any = None) -> None:
        ctx.user_action_completed.set()

    events.session_finished._on_emit = stop_on_session_finished
    events.user_action_required._on_emit = complete_user_action
    ctx.equipment_connect_requested.set()
    ctx.test_start_requested.set()
    return ctx, events, command_facade, writer


def _run_session(ctx: SessionContext) -> None:
    engine = build_session_engine(ctx)
    engine.run("SessionInit")


def _call_names(commands: _Commands) -> list[str]:
    return [name for name, _ in commands.calls]


def _writer_call_names(writer: _ReportWriter) -> list[str]:
    return [name for name, _ in writer.calls]


@pytest.fixture(autouse=True)
def _shrink_fsm_waits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(common_module, "_POLL_INTERVAL_SEC", 0.001)
    monkeypatch.setattr(common_module, "_SETTLING_SEC", 0.0)
    monkeypatch.setattr(common_module, "_ROTATION_TIMEOUT_SEC", 1.0)
    monkeypatch.setattr(common_module, "_PROGRESS_EMIT_INTERVAL_SEC", 0.0)
    monkeypatch.setattr(nr_setup_module, "_USER_ACTION_WAIT_INTERVAL_SEC", 0.001)
    monkeypatch.setattr(transition_module, "_USER_ACTION_WAIT_INTERVAL_SEC", 0.001)


def test_session_init_to_idle(tmp_path: Path) -> None:
    case = _make_case()
    ctx, events, _, _ = _make_ctx(tmp_path, [case])
    ctx.test_start_requested.clear()
    events.state_changed._on_emit = (
        lambda state_name: setattr(ctx, "stopped", True)
        if state_name == "Idle"
        else None
    )

    _run_session(ctx)

    assert events.state_changed.values == ["SessionInit", "Idle"]
    assert events.error.values == []


def test_harmonic_measurement_chain(tmp_path: Path) -> None:
    case = _make_case(MeasurementTestType.HARMONIC)
    ctx, events, commands, writer = _make_ctx(tmp_path, [case])

    _run_session(ctx)

    assert events.state_changed.values == [
        "SessionInit",
        "Idle",
        "InitialTurntableZero",
        "AntPolChange",
        "SetupSpectrumAnalyzerStartupLevel",
        "NRCallConnect",
        "MeasureFundamental",
        "SetSwitchBox",
        "SetupSpectrumAnalyzer",
        "RotateTurntable",
        "MeasureHarmonics",
        "MeasureHarmonicPrecision",
        "ResetSwitchBox",
        "CheckNextCase",
        "TestEnd",
    ]
    assert "measure_fundamental" in _call_names(commands)
    assert "measure_harmonics" in _call_names(commands)
    assert _writer_call_names(writer) == [
        "read_fundamental_frequency",
        "write_fundamental",
        "write_harmonic",
    ]
    assert events.error.values == []


@pytest.mark.parametrize(
    ("first_case", "second_case", "expected_transition"),
    [
        (
            _make_case(MeasurementTestType.HARMONIC, band=NRBand.N77),
            _make_case(MeasurementTestType.HARMONIC, band=NRBand.N78),
            "Handover",
        ),
        (
            _make_case(MeasurementTestType.BILOG, band=NRBand.N1, bandwidth=20.0),
            _make_case(MeasurementTestType.HARMONIC, band=NRBand.N78),
            "RecallChange",
        ),
        (
            _make_case(MeasurementTestType.HARMONIC, dut_axis=DUTAxis.X),
            _make_case(MeasurementTestType.HARMONIC, dut_axis=DUTAxis.Y),
            "DUTAxisChange",
        ),
        (
            _make_case(MeasurementTestType.HARMONIC, antenna_pol=AntennaPol.H),
            _make_case(MeasurementTestType.HARMONIC, antenna_pol=AntennaPol.V),
            "AntPolChange",
        ),
        (
            _make_case(MeasurementTestType.HARMONIC),
            _make_case(MeasurementTestType.INBAND),
            "TestTypeChange",
        ),
    ],
)
def test_check_next_case_transitions(
    tmp_path: Path,
    first_case: TestCase,
    second_case: TestCase,
    expected_transition: str,
) -> None:
    ctx, events, _, _ = _make_ctx(tmp_path, [first_case, second_case])

    _run_session(ctx)

    first_check_next_case = events.state_changed.values.index("CheckNextCase")
    assert events.state_changed.values[first_check_next_case + 1] == expected_transition
    assert events.error.values == []


def test_nr_call_disconnected_recovery(tmp_path: Path) -> None:
    case = _make_case(MeasurementTestType.HARMONIC)
    commands = _Commands(setup_mt8000_results=[False, True])
    ctx, events, _, _ = _make_ctx(tmp_path, [case], commands=commands)

    _run_session(ctx)

    assert events.state_changed.values[:8] == [
        "SessionInit",
        "Idle",
        "InitialTurntableZero",
        "AntPolChange",
        "SetupSpectrumAnalyzerStartupLevel",
        "NRCallConnect",
        "NRCallDisconnected",
        "NRCallConnect",
    ]
    assert _call_names(commands).count("setup_mt8000") == 2
    assert events.user_action_required.values == ["비행기 모드 On/Off 후 확인"]
