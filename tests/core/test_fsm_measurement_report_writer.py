from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.core.fsm.base import StateResult
from app.core.fsm.context import SessionContext
from app.core.fsm.states.measurement.bilog import MeasureBilogManualState, MeasureBilogState
from app.core.fsm.states.measurement.harmonic import (
    MeasureHarmonicPrecisionState,
    MeasureFundamentalState,
    MeasureHarmonicsManualState,
    MeasureHarmonicsState,
)
from app.core.fsm.states.measurement.inband import MeasureInBandManualState, MeasureInBandState
from app.models.enums import (
    AntennaPol,
    DUTAntPosition,
    DUTAxis,
    Generation,
    LTEBand,
    LTERBAllocation,
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
    HarmonicPrecisionCandidate,
    HarmonicResult,
    InbandResult,
)
from app.models.test_case import TestCase


class _SignalRecorder:
    def __init__(self) -> None:
        self.messages: list[Any] = []
        self.on_emit: Any | None = None

    def emit(self, message: Any = None) -> None:
        self.messages.append(message)
        if self.on_emit is not None:
            self.on_emit(message)


class _Events:
    def __init__(self) -> None:
        self.error = _SignalRecorder()
        self.screenshot_saved = _SignalRecorder()
        self.spectrum_analyzer_info_changed = _SignalRecorder()
        self.manual_marker_edit_required = _SignalRecorder()


_DEFAULT_HARMONIC_LEVELS = object()


class _Commands:
    def __init__(
        self,
        *,
        fundamental_frequency_mhz: float = 3549.99,
        harmonic_levels: object = _DEFAULT_HARMONIC_LEVELS,
        inband_amplitude: float = -39.5,
        bilog_amplitude: float = -45.5,
        fundamental_exception: Exception | None = None,
        harmonics_exception: Exception | None = None,
        inband_exception: Exception | None = None,
        bilog_exception: Exception | None = None,
        fundamental_screenshot_path: Path | None = None,
        harmonic_screenshot_path: Path | None = None,
        inband_screenshot_path: Path | None = None,
        bilog_screenshot_path: Path | None = None,
    ) -> None:
        self.fundamental_frequency_mhz = fundamental_frequency_mhz
        self.harmonic_levels = (
            _markers((-41.0, -39.5, -40.0, -37.0))
            if harmonic_levels is _DEFAULT_HARMONIC_LEVELS
            else harmonic_levels
        )
        self.inband_amplitude = inband_amplitude
        self.bilog_amplitude = bilog_amplitude
        self.fundamental_exception = fundamental_exception
        self.harmonics_exception = harmonics_exception
        self.inband_exception = inband_exception
        self.bilog_exception = bilog_exception
        self.fundamental_screenshot_path = fundamental_screenshot_path
        self.harmonic_screenshot_path = harmonic_screenshot_path
        self.inband_screenshot_path = inband_screenshot_path
        self.bilog_screenshot_path = bilog_screenshot_path
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.measure_fundamental_calls: list[tuple[Any, dict[str, Any]]] = []
        self.measure_harmonics_calls: list[tuple[Any, dict[str, Any]]] = []
        self.measure_harmonic_manual_calls: list[tuple[Any, dict[str, Any]]] = []
        self.measure_inband_calls: list[tuple[Any, dict[str, Any]]] = []
        self.measure_inband_manual_calls: list[tuple[Any, dict[str, Any]]] = []
        self.measure_bilog_calls: list[tuple[Any, dict[str, Any]]] = []
        self.measure_bilog_manual_calls: list[tuple[Any, dict[str, Any]]] = []
        self.setup_sa_precision_calls: list[tuple[Any, dict[str, Any]]] = []
        self.setup_sa_startup_levels_calls: list[tuple[Any, dict[str, Any]]] = []
        self.get_screenshot_calls: list[Any] = []
        self.measure_harmonic_precision_calls: list[Any] = []
        self.precision_amplitudes: list[float] = []

    def measure_fundamental(self, client: Any, *, target_freq: float) -> float:
        self.calls.append(("measure_fundamental", {"target_freq": target_freq}))
        self.measure_fundamental_calls.append(
            (client, {"target_freq": target_freq})
        )
        if self.fundamental_exception is not None:
            raise self.fundamental_exception
        if self.fundamental_screenshot_path is not None:
            self.fundamental_screenshot_path.write_bytes(b"fresh fundamental")
        return self.fundamental_frequency_mhz

    def measure_harmonics(self, client: Any, *, fundamental: float) -> object:
        self.measure_harmonics_calls.append(
            (client, {"fundamental": fundamental})
        )
        if self.harmonics_exception is not None:
            raise self.harmonics_exception
        if self.harmonic_screenshot_path is not None:
            self.harmonic_screenshot_path.write_bytes(b"fresh harmonic")
        return self.harmonic_levels

    def measure_harmonic_manual(self, client: Any, *, fundamental: float) -> object:
        self.measure_harmonic_manual_calls.append(
            (client, {"fundamental": fundamental})
        )
        if self.harmonics_exception is not None:
            raise self.harmonics_exception
        return self.harmonic_levels

    def measure_inband(self, client: Any, *, limit: float) -> float:
        self.measure_inband_calls.append((client, {"limit": limit}))
        if self.inband_exception is not None:
            raise self.inband_exception
        if self.inband_screenshot_path is not None:
            self.inband_screenshot_path.write_bytes(b"fresh inband")
        return self.inband_amplitude

    def measure_inband_manual(self, client: Any, *, limit: float) -> float:
        self.measure_inband_manual_calls.append((client, {"limit": limit}))
        if self.inband_exception is not None:
            raise self.inband_exception
        return self.inband_amplitude

    def measure_bilog(self, client: Any, *, limit: float) -> float:
        self.measure_bilog_calls.append((client, {"limit": limit}))
        if self.bilog_exception is not None:
            raise self.bilog_exception
        if self.bilog_screenshot_path is not None:
            self.bilog_screenshot_path.write_bytes(b"fresh bilog")
        return self.bilog_amplitude

    def measure_bilog_manual(self, client: Any, *, limit: float) -> float:
        self.measure_bilog_manual_calls.append((client, {"limit": limit}))
        if self.bilog_exception is not None:
            raise self.bilog_exception
        return self.bilog_amplitude

    def setup_sa_startup_levels(
        self,
        client: Any,
        *,
        atten_level_db: float,
        next_peak_search_level_db: float,
    ) -> bool:
        self.setup_sa_startup_levels_calls.append(
            (
                client,
                {
                    "atten_level_db": atten_level_db,
                    "next_peak_search_level_db": next_peak_search_level_db,
                },
            )
        )
        return True

    def get_screenshot(self, client: Any) -> bool:
        self.get_screenshot_calls.append(client)
        return True

    def setup_sa_precision(
        self,
        client: Any,
        *,
        peak_frequency: float,
        sweep_time: int,
    ) -> bool:
        self.setup_sa_precision_calls.append(
            (
                client,
                {
                    "peak_frequency": peak_frequency,
                    "sweep_time": sweep_time,
                },
            )
        )
        return True

    def measure_harmonic_precision(self, client: Any) -> float:
        self.measure_harmonic_precision_calls.append(client)
        if self.precision_amplitudes:
            amplitude = self.precision_amplitudes.pop(0)
        else:
            amplitude = -40.0
        return amplitude


class _ReportWriter:
    def __init__(
        self,
        *,
        return_value: bool = True,
        exception: Exception | None = None,
        cached_fundamental_frequency_mhz: float | None = None,
        read_exception: Exception | None = None,
    ) -> None:
        self.return_value = return_value
        self.exception = exception
        self.cached_fundamental_frequency_mhz = cached_fundamental_frequency_mhz
        self.read_exception = read_exception
        self.calls: list[tuple[str, TestCase, object]] = []
        self.read_fundamental_frequency_calls: list[TestCase] = []

    def read_fundamental_frequency(self, test_case: TestCase) -> float | None:
        self.read_fundamental_frequency_calls.append(test_case)
        if self.read_exception is not None:
            raise self.read_exception
        return self.cached_fundamental_frequency_mhz

    def write_fundamental(
        self,
        test_case: TestCase,
        result: FundamentalResult,
    ) -> bool:
        return self._record("fundamental", test_case, result)

    def write_harmonic(
        self,
        test_case: TestCase,
        result: HarmonicResult,
    ) -> bool:
        return self._record("harmonic", test_case, result)

    def write_inband(
        self,
        test_case: TestCase,
        result: InbandResult,
    ) -> bool:
        return self._record("inband", test_case, result)

    def write_bilog(
        self,
        test_case: TestCase,
        result: BilogResult,
    ) -> bool:
        return self._record("bilog", test_case, result)

    def _record(self, name: str, test_case: TestCase, result: object) -> bool:
        if self.exception is not None:
            raise self.exception
        self.calls.append((name, test_case, result))
        return self.return_value


def _markers(
    amplitudes: tuple[float, float, float, float],
    frequencies: tuple[float, float, float, float] = (
        7100.5,
        10650.75,
        14201.0,
        17751.25,
    ),
) -> list[HarmonicMarker]:
    return [
        HarmonicMarker(order=order, amplitude_dbm=amplitude, peak_frequency_mhz=frequency)
        for order, amplitude, frequency in zip(
            (2, 3, 4, 5),
            amplitudes,
            frequencies,
            strict=True,
        )
    ]


def _make_case(
    test_type: MeasurementTestType,
    *,
    band: NRBand = NRBand.N78,
    bandwidth: float = 100.0,
    test_channel: ChannelEnum = ChannelEnum.MID,
    antenna_pol: AntennaPol = AntennaPol.H,
    dut_axis: DUTAxis = DUTAxis.X,
    dut_ant_position: DUTAntPosition | str = DUTAntPosition.UPPER,
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
        dut_ant_position=dut_ant_position,
    )


def _make_lte_case(test_type: MeasurementTestType) -> TestCase:
    return TestCase(
        generation=Generation.LTE,
        band=LTEBand.B1,
        bandwidth=10.0,
        test_type=test_type,
        modulation=Modulation.QPSK,
        rb_allocation=LTERBAllocation.MID,
        test_channel=ChannelEnum.MID,
        antenna_pol=AntennaPol.H,
        dut_axis=DUTAxis.X,
        dut_ant_position=DUTAntPosition.LOWER,
    )


def _make_ctx(
    test_type: MeasurementTestType,
    *,
    case: TestCase | None = None,
    commands: Any | None = None,
    report_writer: Any | None = None,
    events: Any | None = None,
    temp_dir: Path | None = Path("tmp"),
    fundamental_frequency_mhz: float | None = None,
    model_name: str = "SM-000",
    screenshot_root_dir: Path | None = None,
) -> SessionContext:
    ctx = SessionContext(
        queue=[case or _make_case(test_type)],
        commands=commands or _Commands(),
        events=events,  # type: ignore[arg-type]
        report_writer=report_writer,
        temp_dir=temp_dir,
        fundamental_frequency_mhz=fundamental_frequency_mhz,
        model_name=model_name,
        screenshot_root_dir=screenshot_root_dir or temp_dir,
    )
    if test_type is MeasurementTestType.HARMONIC:
        ctx.equipment_state = {"FSV40": True}
    return ctx


def _prepare_harmonic_measurement(
    ctx: SessionContext,
    temp_dir: Path,
    *,
    screenshot_exists: bool = True,
) -> None:
    ctx.temp_dir = temp_dir
    ctx.fundamental_frequency_mhz = 3550.25
    if screenshot_exists:
        (temp_dir / "harmonic.png").write_bytes(b"png")


def test_measure_fundamental_uses_target_frequency_and_temp_dir(
    tmp_path: Path,
) -> None:
    report_writer = _ReportWriter()
    screenshot_path = tmp_path / "fundamental.png"
    screenshot_path.write_bytes(b"stale")
    commands = _Commands(
        fundamental_frequency_mhz=3550.25,
        fundamental_screenshot_path=screenshot_path,
    )
    events = _Events()
    ctx = _make_ctx(
        MeasurementTestType.HARMONIC,
        commands=commands,
        report_writer=report_writer,
        events=events,
        temp_dir=tmp_path,
    )

    result = MeasureFundamentalState().run(ctx)

    assert result is StateResult.OK
    assert commands.calls == [("measure_fundamental", {"target_freq": 3549.99})]
    assert commands.measure_fundamental_calls == [
        (None, {"target_freq": 3549.99})
    ]
    assert ctx.fundamental_frequency_mhz == 3550.25
    assert report_writer.calls[0][0] == "fundamental"
    assert report_writer.calls[0][1] == ctx.current_case
    measured = report_writer.calls[0][2]
    assert isinstance(measured, FundamentalResult)
    assert measured.fundamental_frequency_mhz == 3550.25
    assert measured.screenshot_path == tmp_path / "fundamental.png"
    assert screenshot_path.read_bytes() == b"fresh fundamental"
    assert events.spectrum_analyzer_info_changed.messages == [
        {
            "start_freq": 3449.99,
            "stop_freq": 3649.99,
            "trace_mode": "View",
            "rbw": 1.0,
            "vbw": 1.0,
            "sweep_point": 10001,
        }
    ]


def test_measure_fundamental_uses_lte_target_frequency(tmp_path: Path) -> None:
    screenshot_path = tmp_path / "fundamental.png"
    commands = _Commands(fundamental_screenshot_path=screenshot_path)
    ctx = _make_ctx(
        MeasurementTestType.HARMONIC,
        case=_make_lte_case(MeasurementTestType.HARMONIC),
        commands=commands,
        report_writer=_ReportWriter(),
        events=_Events(),
        temp_dir=tmp_path,
    )

    result = MeasureFundamentalState().run(ctx)

    assert result is StateResult.OK
    assert commands.measure_fundamental_calls == [
        (None, {"target_freq": 1950.0})
    ]


def test_measure_fundamental_reuses_excel_frequency_without_measurement(
    tmp_path: Path,
) -> None:
    report_writer = _ReportWriter(cached_fundamental_frequency_mhz=3550.25)
    screenshot_path = tmp_path / "fundamental.png"
    screenshot_path.write_bytes(b"stale")
    commands = _Commands(
        fundamental_frequency_mhz=3549.99,
        fundamental_screenshot_path=screenshot_path,
    )
    events = _Events()
    ctx = _make_ctx(
        MeasurementTestType.HARMONIC,
        commands=commands,
        report_writer=report_writer,
        events=events,
        temp_dir=tmp_path,
    )

    result = MeasureFundamentalState().run(ctx)

    assert result is StateResult.OK
    assert report_writer.read_fundamental_frequency_calls == [ctx.current_case]
    assert report_writer.calls == []
    assert commands.calls == []
    assert commands.measure_fundamental_calls == []
    assert ctx.fundamental_frequency_mhz == 3550.25
    assert screenshot_path.read_bytes() == b"stale"
    assert events.screenshot_saved.messages == []
    assert events.spectrum_analyzer_info_changed.messages == []


def test_measure_fundamental_skips_when_fsv40_is_not_connected() -> None:
    commands = _Commands()
    events = _Events()
    ctx = _make_ctx(
        MeasurementTestType.HARMONIC,
        commands=commands,
        events=events,
    )
    ctx.equipment_state = {"FSV40": False}
    state = MeasureFundamentalState()

    result = state.run(ctx)

    assert result is StateResult.OK
    assert state.next_state(ctx, result) == "SetSwitchBox"
    assert commands.calls == []
    assert commands.measure_fundamental_calls == []
    assert events.error.messages


def test_measure_harmonics_uses_fundamental_threshold_and_screenshot(
    tmp_path: Path,
) -> None:
    report_writer = _ReportWriter()
    screenshot_path = tmp_path / "harmonic.png"
    screenshot_path.write_bytes(b"stale")
    commands = _Commands(
        harmonic_levels=_markers((-41.0, -39.9, -40.0, -37.5)),
        harmonic_screenshot_path=screenshot_path,
    )
    ctx = _make_ctx(
        MeasurementTestType.HARMONIC,
        commands=commands,
        report_writer=report_writer,
        temp_dir=tmp_path,
    )
    _prepare_harmonic_measurement(ctx, tmp_path)

    result = MeasureHarmonicsState().run(ctx)

    assert result is StateResult.OK
    assert commands.measure_harmonics_calls == [
        (None, {"fundamental": 3550.25})
    ]
    assert report_writer.calls[0][0] == "harmonic"
    assert report_writer.calls[0][1] == ctx.current_case
    measured = report_writer.calls[0][2]
    assert isinstance(measured, HarmonicResult)
    assert measured.screenshot_path == tmp_path / "harmonic.png"
    assert measured.harmonic_2nd_peak_level_dbm is None
    assert measured.harmonic_3rd_peak_level_dbm == -39.9
    assert measured.harmonic_4th_peak_level_dbm is None
    assert measured.harmonic_5th_peak_level_dbm == -37.5
    assert screenshot_path.read_bytes() == b"fresh harmonic"


def test_measure_harmonics_skips_when_fsv40_is_not_connected(
    tmp_path: Path,
) -> None:
    commands = _Commands()
    events = _Events()
    ctx = _make_ctx(
        MeasurementTestType.HARMONIC,
        commands=commands,
        events=events,
        temp_dir=tmp_path,
        fundamental_frequency_mhz=3550.25,
    )
    ctx.equipment_state = {"FSV40": False}
    state = MeasureHarmonicsState()

    result = state.run(ctx)

    assert result is StateResult.OK
    assert state.next_state(ctx, result) == "ResetSwitchBox"
    assert commands.measure_harmonics_calls == []
    assert events.error.messages


@pytest.mark.parametrize(
    ("state", "test_type", "command_attr", "expected_message"),
    [
        (
            MeasureInBandState(),
            MeasurementTestType.INBAND,
            "measure_inband_calls",
            "In-Band 측정 스킵: FSV40이 연결되어 있지 않습니다.",
        ),
        (
            MeasureBilogState(),
            MeasurementTestType.BILOG,
            "measure_bilog_calls",
            "Bilog 측정 스킵: FSV40이 연결되어 있지 않습니다.",
        ),
    ],
)
def test_non_harmonic_measurement_states_skip_when_fsv40_is_not_connected(
    tmp_path: Path,
    state: Any,
    test_type: MeasurementTestType,
    command_attr: str,
    expected_message: str,
) -> None:
    commands = _Commands(
        inband_screenshot_path=tmp_path / "inband.png",
        bilog_screenshot_path=tmp_path / "inband.png",
    )
    report_writer = _ReportWriter()
    events = _Events()
    ctx = _make_ctx(
        test_type,
        commands=commands,
        report_writer=report_writer,
        events=events,
        temp_dir=tmp_path,
    )
    ctx.equipment_state = {"FSV40": False}

    result = state.run(ctx)

    assert result is StateResult.OK
    assert state.next_state(ctx, result) == "ResetSwitchBox"
    assert getattr(commands, command_attr) == []
    assert report_writer.calls == []
    assert not (tmp_path / "inband.png").exists()
    assert events.error.messages == [expected_message]


def test_measure_harmonics_writes_report_even_when_no_peak_exceeds_threshold(
    tmp_path: Path,
) -> None:
    report_writer = _ReportWriter()
    screenshot_path = tmp_path / "harmonic.png"
    commands = _Commands(
        harmonic_levels=_markers((-45.0, -40.0, -42.0, -50.0)),
        harmonic_screenshot_path=screenshot_path,
    )
    ctx = _make_ctx(
        MeasurementTestType.HARMONIC,
        commands=commands,
        report_writer=report_writer,
        temp_dir=tmp_path,
    )
    _prepare_harmonic_measurement(ctx, tmp_path)

    state = MeasureHarmonicsState()
    result = state.run(ctx)

    assert result is StateResult.OK
    assert state.next_state(ctx, result) == "ResetSwitchBox"
    measured = report_writer.calls[0][2]
    assert isinstance(measured, HarmonicResult)
    assert measured.harmonic_2nd_peak_level_dbm is None
    assert measured.harmonic_3rd_peak_level_dbm is None
    assert measured.harmonic_4th_peak_level_dbm is None
    assert measured.harmonic_5th_peak_level_dbm is None


def test_measure_harmonics_builds_precision_candidates_after_report(
    tmp_path: Path,
) -> None:
    report_writer = _ReportWriter()
    commands = _Commands(
        harmonic_levels=_markers(
            (-32.5, -40.0, 0.0, -33.0),
            (7088.35, 10632.525, 0.0, 14176.7),
        ),
        harmonic_screenshot_path=tmp_path / "harmonic.png",
    )
    ctx = _make_ctx(
        MeasurementTestType.HARMONIC,
        commands=commands,
        report_writer=report_writer,
        temp_dir=tmp_path,
    )
    _prepare_harmonic_measurement(ctx, tmp_path)

    state = MeasureHarmonicsState()
    result = state.run(ctx)

    assert result is StateResult.OK
    assert state.next_state(ctx, result) == "MeasureHarmonicPrecision"
    assert report_writer.calls[0][0] == "harmonic"
    assert [
        (candidate.order, candidate.amplitude_dbm, candidate.peak_frequency_mhz)
        for candidate in ctx.harmonic_precision_candidates
    ] == [
        (2, -32.5, 7088.35),
        (5, -33.0, 14176.7),
    ]


def test_measure_harmonic_precision_skips_without_candidates(tmp_path: Path) -> None:
    commands = _Commands()
    ctx = _make_ctx(
        MeasurementTestType.HARMONIC,
        commands=commands,
        temp_dir=tmp_path,
    )
    state = MeasureHarmonicPrecisionState()

    result = state.run(ctx)

    assert result is StateResult.OK
    assert state.next_state(ctx, result) == "ResetSwitchBox"
    assert commands.setup_sa_precision_calls == []
    assert commands.measure_harmonic_precision_calls == []


def test_measure_harmonic_precision_runs_100ms_only_and_saves_screenshot(
    tmp_path: Path,
) -> None:
    events = _Events()
    commands = _Commands()
    commands.precision_amplitudes = [-40.0]
    ctx = _make_ctx(
        MeasurementTestType.HARMONIC,
        commands=commands,
        events=events,
        temp_dir=tmp_path,
        screenshot_root_dir=tmp_path / "screenshots",
    )
    ctx.harmonic_precision_candidates = [
        HarmonicPrecisionCandidate(
            order=2,
            amplitude_dbm=-32.5,
            peak_frequency_mhz=7088.35,
        )
    ]

    def write_precision_png(_: Any) -> float:
        (tmp_path / "precision.png").write_bytes(b"precision")
        return -40.0

    commands.measure_harmonic_precision = write_precision_png  # type: ignore[method-assign]

    result = MeasureHarmonicPrecisionState().run(ctx)

    assert result is StateResult.OK
    assert commands.setup_sa_precision_calls == [
        (None, {"peak_frequency": 7088.35, "sweep_time": 100})
    ]
    assert len(events.screenshot_saved.messages) == 1
    assert events.screenshot_saved.messages[0].endswith(
        "SM-000_Traffic_5G_SA_n78_UPPER_7088.350MHz_XH_100ms.png"
    )


def test_measure_harmonic_precision_runs_500ms_when_100ms_is_near_limit(
    tmp_path: Path,
) -> None:
    events = _Events()
    commands = _Commands()
    ctx = _make_ctx(
        MeasurementTestType.HARMONIC,
        commands=commands,
        events=events,
        temp_dir=tmp_path,
        screenshot_root_dir=tmp_path / "screenshots",
    )
    ctx.harmonic_precision_candidates = [
        HarmonicPrecisionCandidate(
            order=5,
            amplitude_dbm=-31.0,
            peak_frequency_mhz=14176.7,
        )
    ]
    amplitudes = [-31.0, -34.0]

    def write_precision_png(_: Any) -> float:
        (tmp_path / "precision.png").write_bytes(b"precision")
        return amplitudes.pop(0)

    commands.measure_harmonic_precision = write_precision_png  # type: ignore[method-assign]

    result = MeasureHarmonicPrecisionState().run(ctx)

    assert result is StateResult.OK
    assert [call[1]["sweep_time"] for call in commands.setup_sa_precision_calls] == [
        100,
        500,
    ]
    assert len(events.screenshot_saved.messages) == 2
    assert events.screenshot_saved.messages[1].endswith(
        "SM-000_Traffic_5G_SA_n78_UPPER_14176.700MHz_XH_500ms.png"
    )


def test_measure_harmonic_precision_returns_fail_when_screenshot_is_missing(
    tmp_path: Path,
) -> None:
    events = _Events()
    commands = _Commands()
    commands.precision_amplitudes = [-40.0]
    ctx = _make_ctx(
        MeasurementTestType.HARMONIC,
        commands=commands,
        events=events,
        temp_dir=tmp_path,
    )
    ctx.harmonic_precision_candidates = [
        HarmonicPrecisionCandidate(
            order=2,
            amplitude_dbm=-32.5,
            peak_frequency_mhz=7088.35,
        )
    ]

    result = MeasureHarmonicPrecisionState().run(ctx)

    assert result is StateResult.FAIL
    assert events.error.messages[-1] == (
        f"Harmonic Precision 스크린샷 저장 실패: {tmp_path / 'precision.png'} does not exist"
    )


def test_measure_fundamental_returns_fail_without_temp_dir() -> None:
    events = _Events()
    commands = _Commands()
    ctx = _make_ctx(
        MeasurementTestType.HARMONIC,
        commands=commands,
        events=events,
        temp_dir=None,
    )
    state = MeasureFundamentalState()

    result = state.run(ctx)

    assert result is StateResult.FAIL
    assert state.next_state(ctx, result) is None
    assert ctx.fundamental_frequency_mhz is None
    assert commands.measure_fundamental_calls == []
    assert events.error.messages == [
        "Fundamental 스크린샷 경로 생성 실패: temp_dir is not set"
    ]


def test_measure_fundamental_returns_fail_when_lookup_raises() -> None:
    events = _Events()
    commands = _Commands()
    case = _make_case(
        MeasurementTestType.HARMONIC,
        band=NRBand.N28,
        bandwidth=25.0,
        test_channel=ChannelEnum.MID,
    )
    ctx = _make_ctx(
        MeasurementTestType.HARMONIC,
        case=case,
        commands=commands,
        events=events,
    )
    state = MeasureFundamentalState()

    result = state.run(ctx)

    assert result is StateResult.FAIL
    assert state.next_state(ctx, result) is None
    assert ctx.fundamental_frequency_mhz is None
    assert commands.measure_fundamental_calls == []
    assert events.error.messages == [
        (
            "Fundamental 측정 준비 실패: "
            "No NR channel lookup for band='n28', bandwidth='25', "
            "test_channel='mid'"
        )
    ]


def test_measure_fundamental_returns_fail_when_cached_frequency_is_invalid() -> None:
    events = _Events()
    commands = _Commands()
    report_writer = _ReportWriter(read_exception=ValueError("invalid cached value"))
    ctx = _make_ctx(
        MeasurementTestType.HARMONIC,
        commands=commands,
        report_writer=report_writer,
        events=events,
    )
    state = MeasureFundamentalState()

    result = state.run(ctx)

    assert result is StateResult.FAIL
    assert state.next_state(ctx, result) is None
    assert ctx.fundamental_frequency_mhz is None
    assert commands.measure_fundamental_calls == []
    assert report_writer.calls == []
    assert events.error.messages == [
        "Fundamental frequency 재사용 실패: invalid cached value"
    ]


def test_measure_fundamental_returns_fail_when_command_raises() -> None:
    events = _Events()
    commands = _Commands(
        fundamental_exception=RuntimeError("instrument timeout")
    )
    ctx = _make_ctx(
        MeasurementTestType.HARMONIC,
        commands=commands,
        events=events,
    )
    state = MeasureFundamentalState()

    result = state.run(ctx)

    assert result is StateResult.FAIL
    assert state.next_state(ctx, result) is None
    assert ctx.fundamental_frequency_mhz is None
    assert commands.measure_fundamental_calls == [
        (None, {"target_freq": 3549.99})
    ]
    assert events.error.messages == [
        "Fundamental 측정 실패: instrument timeout"
    ]


def test_measure_fundamental_does_not_emit_sa_info_when_command_raises() -> None:
    events = _Events()
    commands = _Commands(fundamental_exception=RuntimeError("instrument timeout"))
    ctx = _make_ctx(
        MeasurementTestType.HARMONIC,
        commands=commands,
        events=events,
    )

    result = MeasureFundamentalState().run(ctx)

    assert result is StateResult.FAIL
    assert events.spectrum_analyzer_info_changed.messages == []


def test_measure_fundamental_returns_fail_when_screenshot_is_missing(
    tmp_path: Path,
) -> None:
    events = _Events()
    report_writer = _ReportWriter()
    commands = _Commands(fundamental_frequency_mhz=3550.25)
    ctx = _make_ctx(
        MeasurementTestType.HARMONIC,
        commands=commands,
        report_writer=report_writer,
        events=events,
        temp_dir=tmp_path,
    )
    state = MeasureFundamentalState()

    result = state.run(ctx)

    assert result is StateResult.FAIL
    assert state.next_state(ctx, result) is None
    assert ctx.fundamental_frequency_mhz is None
    assert report_writer.calls == []
    assert commands.measure_fundamental_calls == [
        (None, {"target_freq": 3549.99})
    ]
    assert events.error.messages == [
        f"Fundamental 스크린샷 저장 실패: {tmp_path / 'fundamental.png'} does not exist"
    ]


def test_measure_fundamental_emits_sa_info_when_screenshot_is_missing(
    tmp_path: Path,
) -> None:
    events = _Events()
    commands = _Commands(fundamental_frequency_mhz=3550.25)
    ctx = _make_ctx(
        MeasurementTestType.HARMONIC,
        commands=commands,
        events=events,
        temp_dir=tmp_path,
    )

    result = MeasureFundamentalState().run(ctx)

    assert result is StateResult.FAIL
    assert events.spectrum_analyzer_info_changed.messages == [
        {
            "start_freq": 3449.99,
            "stop_freq": 3649.99,
            "trace_mode": "View",
            "rbw": 1.0,
            "vbw": 1.0,
            "sweep_point": 10001,
        }
    ]


def test_measure_harmonics_returns_fail_without_fundamental(
    tmp_path: Path,
) -> None:
    events = _Events()
    commands = _Commands()
    ctx = _make_ctx(
        MeasurementTestType.HARMONIC,
        commands=commands,
        events=events,
        temp_dir=tmp_path,
    )
    (tmp_path / "harmonic.png").write_bytes(b"png")
    state = MeasureHarmonicsState()

    result = state.run(ctx)

    assert result is StateResult.FAIL
    assert state.next_state(ctx, result) is None
    assert commands.measure_harmonics_calls == []
    assert events.error.messages == [
        "Harmonic 측정 실패: fundamental_frequency_mhz is not set"
    ]


def test_measure_harmonics_returns_fail_without_temp_dir() -> None:
    events = _Events()
    commands = _Commands()
    ctx = _make_ctx(
        MeasurementTestType.HARMONIC,
        commands=commands,
        events=events,
        temp_dir=None,
        fundamental_frequency_mhz=3550.25,
    )
    state = MeasureHarmonicsState()

    result = state.run(ctx)

    assert result is StateResult.FAIL
    assert state.next_state(ctx, result) is None
    assert commands.measure_harmonics_calls == []
    assert events.error.messages == [
        "Harmonic 스크린샷 경로 생성 실패: temp_dir is not set"
    ]


def test_measure_harmonics_returns_fail_when_command_raises(
    tmp_path: Path,
) -> None:
    events = _Events()
    commands = _Commands(
        harmonics_exception=RuntimeError("instrument timeout")
    )
    ctx = _make_ctx(
        MeasurementTestType.HARMONIC,
        commands=commands,
        events=events,
        temp_dir=tmp_path,
        fundamental_frequency_mhz=3550.25,
    )
    (tmp_path / "harmonic.png").write_bytes(b"png")
    state = MeasureHarmonicsState()

    result = state.run(ctx)

    assert result is StateResult.FAIL
    assert state.next_state(ctx, result) is None
    assert commands.measure_harmonics_calls == [
        (None, {"fundamental": 3550.25})
    ]
    assert events.error.messages == [
        "Harmonic 측정 실패: instrument timeout"
    ]


@pytest.mark.parametrize(
    ("harmonic_levels", "message"),
    [
        (
            (-41.0, -39.0, -38.0),
            "Harmonic 측정 실패: Harmonic 측정 응답 형식 오류: expected 4 harmonic markers, got 3",
        ),
        (
            ("bad", -39.0, -38.0, -37.0),
            "Harmonic 측정 실패: Harmonic 측정 응답 형식 오류: expected numeric amplitude/frequency",
        ),
        (
            None,
            "Harmonic 측정 실패: Harmonic 측정 응답 형식 오류: expected 4 harmonic markers",
        ),
    ],
)
def test_measure_harmonics_returns_fail_for_invalid_response(
    tmp_path: Path,
    harmonic_levels: object,
    message: str,
) -> None:
    events = _Events()
    commands = _Commands(harmonic_levels=harmonic_levels)
    ctx = _make_ctx(
        MeasurementTestType.HARMONIC,
        commands=commands,
        events=events,
        temp_dir=tmp_path,
        fundamental_frequency_mhz=3550.25,
    )
    (tmp_path / "harmonic.png").write_bytes(b"png")
    state = MeasureHarmonicsState()

    result = state.run(ctx)

    assert result is StateResult.FAIL
    assert state.next_state(ctx, result) is None
    assert commands.measure_harmonics_calls == [
        (None, {"fundamental": 3550.25})
    ]
    assert events.error.messages == [message]


def test_measure_harmonics_returns_fail_when_screenshot_is_missing(
    tmp_path: Path,
) -> None:
    events = _Events()
    report_writer = _ReportWriter()
    commands = _Commands()
    ctx = _make_ctx(
        MeasurementTestType.HARMONIC,
        commands=commands,
        report_writer=report_writer,
        events=events,
        temp_dir=tmp_path,
        fundamental_frequency_mhz=3550.25,
    )
    state = MeasureHarmonicsState()

    result = state.run(ctx)

    assert result is StateResult.FAIL
    assert state.next_state(ctx, result) is None
    assert report_writer.calls == []
    assert events.error.messages == [
        f"Harmonic 스크린샷 저장 실패: {tmp_path / 'harmonic.png'} does not exist"
    ]


def test_measurement_state_returns_fail_when_report_writer_returns_false(
    tmp_path: Path,
) -> None:
    report_writer = _ReportWriter(return_value=False)
    events = _Events()
    commands = _Commands(inband_screenshot_path=tmp_path / "inband.png")
    ctx = _make_ctx(
        MeasurementTestType.INBAND,
        commands=commands,
        report_writer=report_writer,
        events=events,
        temp_dir=tmp_path,
    )
    ctx.equipment_state = {"FSV40": True}
    state = MeasureInBandState()

    result = state.run(ctx)

    assert result is StateResult.FAIL
    assert state.next_state(ctx, result) is None
    assert len(report_writer.calls) == 1
    assert events.error.messages == [
        "In-Band 리포트 작성 실패: write_inband returned false"
    ]


def test_measurement_state_returns_fail_when_report_writer_raises(
    tmp_path: Path,
) -> None:
    report_writer = _ReportWriter(exception=RuntimeError("disk full"))
    events = _Events()
    commands = _Commands(bilog_screenshot_path=tmp_path / "inband.png")
    ctx = _make_ctx(
        MeasurementTestType.BILOG,
        commands=commands,
        report_writer=report_writer,
        events=events,
        temp_dir=tmp_path,
    )
    ctx.equipment_state = {"FSV40": True}
    state = MeasureBilogState()

    result = state.run(ctx)

    assert result is StateResult.FAIL
    assert state.next_state(ctx, result) is None
    assert report_writer.calls == []
    assert events.error.messages == ["리포트 작성 실패: disk full"]


@pytest.mark.parametrize(
    (
        "state",
        "test_type",
        "expected_name",
        "expected_result_type",
        "command_attr",
        "peak_attr",
        "expected_limit",
    ),
    [
        (
            MeasureInBandState(),
            MeasurementTestType.INBAND,
            "inband",
            InbandResult,
            "measure_inband_calls",
            "inband_peak_level_dbm",
            -40.0,
        ),
        (
            MeasureBilogState(),
            MeasurementTestType.BILOG,
            "bilog",
            BilogResult,
            "measure_bilog_calls",
            "bilog_peak_level_dbm",
            -46.0,
        ),
    ],
)
def test_non_harmonic_measurement_states_call_individual_report_writer_methods(
    tmp_path: Path,
    state: Any,
    test_type: MeasurementTestType,
    expected_name: str,
    expected_result_type: type,
    command_attr: str,
    peak_attr: str,
    expected_limit: float,
) -> None:
    report_writer = _ReportWriter()
    commands = _Commands(
        inband_screenshot_path=tmp_path / "inband.png",
        bilog_screenshot_path=tmp_path / "inband.png",
    )
    ctx = _make_ctx(
        test_type,
        commands=commands,
        report_writer=report_writer,
        temp_dir=tmp_path,
    )
    ctx.equipment_state = {"FSV40": True}

    result = state.run(ctx)

    assert result is StateResult.OK
    assert getattr(commands, command_attr) == [(None, {"limit": expected_limit})]
    assert report_writer.calls[0][0] == expected_name
    assert report_writer.calls[0][1] == ctx.current_case
    measured = report_writer.calls[0][2]
    assert isinstance(measured, expected_result_type)
    assert measured.screenshot_path == tmp_path / "inband.png"
    assert measured.screenshot_path.read_bytes() in {
        b"fresh inband",
        b"fresh bilog",
    }
    assert getattr(measured, peak_attr) is not None


@pytest.mark.parametrize(
    (
        "state",
        "test_type",
        "command_kwargs",
        "expected_result_type",
        "peak_attr",
    ),
    [
        (
            MeasureInBandState(),
            MeasurementTestType.INBAND,
            {"inband_amplitude": -40.0},
            InbandResult,
            "inband_peak_level_dbm",
        ),
        (
            MeasureBilogState(),
            MeasurementTestType.BILOG,
            {"bilog_amplitude": -47.0},
            BilogResult,
            "bilog_peak_level_dbm",
        ),
    ],
)
def test_non_harmonic_measurement_states_write_dash_value_below_threshold(
    tmp_path: Path,
    state: Any,
    test_type: MeasurementTestType,
    command_kwargs: dict[str, float],
    expected_result_type: type,
    peak_attr: str,
) -> None:
    commands = _Commands(
        **command_kwargs,
        inband_screenshot_path=tmp_path / "inband.png",
        bilog_screenshot_path=tmp_path / "inband.png",
    )
    report_writer = _ReportWriter()
    ctx = _make_ctx(
        test_type,
        commands=commands,
        report_writer=report_writer,
        temp_dir=tmp_path,
    )
    ctx.equipment_state = {"FSV40": True}

    result = state.run(ctx)

    assert result is StateResult.OK
    measured = report_writer.calls[0][2]
    assert isinstance(measured, expected_result_type)
    assert getattr(measured, peak_attr) is None


def test_measure_fundamental_returns_fail_without_report_writer(
    tmp_path: Path,
) -> None:
    commands = _Commands(
        fundamental_frequency_mhz=3550.25,
        fundamental_screenshot_path=tmp_path / "fundamental.png",
    )
    ctx = _make_ctx(
        MeasurementTestType.HARMONIC,
        commands=commands,
        temp_dir=tmp_path,
    )

    result = MeasureFundamentalState().run(ctx)

    assert result is StateResult.FAIL
    assert ctx.fundamental_frequency_mhz == 3550.25


def test_measure_harmonics_returns_fail_without_report_writer(
    tmp_path: Path,
) -> None:
    commands = _Commands(harmonic_screenshot_path=tmp_path / "harmonic.png")
    ctx = _make_ctx(
        MeasurementTestType.HARMONIC,
        commands=commands,
        temp_dir=tmp_path,
        fundamental_frequency_mhz=3550.25,
    )

    result = MeasureHarmonicsState().run(ctx)

    assert result is StateResult.FAIL
    assert commands.measure_harmonics_calls == [
        (None, {"fundamental": 3550.25})
    ]


@pytest.mark.parametrize(
    ("state", "test_type"),
    [
        (MeasureInBandState(), MeasurementTestType.INBAND),
        (MeasureBilogState(), MeasurementTestType.BILOG),
    ],
)
def test_non_harmonic_measurement_states_return_fail_without_report_writer(
    tmp_path: Path,
    state: Any,
    test_type: MeasurementTestType,
) -> None:
    commands = _Commands(
        inband_screenshot_path=tmp_path / "inband.png",
        bilog_screenshot_path=tmp_path / "inband.png",
    )
    ctx = _make_ctx(test_type, commands=commands, temp_dir=tmp_path)
    ctx.equipment_state = {"FSV40": True}

    result = state.run(ctx)

    assert result is StateResult.FAIL



def _enable_manual_marker(ctx: SessionContext, events: _Events) -> None:
    ctx.settings = SimpleNamespace(
        atten_level_db=1.5,
        next_peak_search_level_db=6.5,
    )
    events.manual_marker_edit_required.on_emit = (
        lambda _payload: ctx.user_action_completed.set()
    )


def test_measure_harmonics_manual_waits_restores_level_and_gets_screenshot(
    tmp_path: Path,
) -> None:
    report_writer = _ReportWriter()
    commands = _Commands(harmonic_levels=_markers((-28.0, -39.5, -40.0, -37.0)))
    events = _Events()
    ctx = _make_ctx(
        MeasurementTestType.HARMONIC,
        commands=commands,
        report_writer=report_writer,
        events=events,
        temp_dir=tmp_path,
        fundamental_frequency_mhz=3550.25,
    )
    _enable_manual_marker(ctx, events)
    (tmp_path / "screenshot.png").write_bytes(b"stale")
    events.manual_marker_edit_required.on_emit = lambda _payload: (
        (tmp_path / "screenshot.png").write_bytes(b"manual screenshot"),
        ctx.user_action_completed.set(),
    )

    result = MeasureHarmonicsManualState().run(ctx)

    assert result is StateResult.OK
    assert commands.measure_harmonic_manual_calls == [
        (None, {"fundamental": 3550.25})
    ]
    assert commands.setup_sa_startup_levels_calls == [
        (None, {"atten_level_db": 1.5, "next_peak_search_level_db": 6.5})
    ]
    assert commands.get_screenshot_calls == [None]
    assert events.manual_marker_edit_required.messages == [
        {
            "test_type": MeasurementTestType.HARMONIC,
            "next_peak_search_level_db": 6.5,
        }
    ]
    assert report_writer.calls[0][0] == "harmonic"
    measured = report_writer.calls[0][2]
    assert isinstance(measured, HarmonicResult)
    assert measured.screenshot_path == tmp_path / "screenshot.png"
    assert ctx.harmonic_precision_candidates
    assert MeasureHarmonicsManualState().next_state(ctx, result) == "MeasureHarmonicPrecision"


@pytest.mark.parametrize(
    ("state", "test_type", "writer_name", "manual_call_name"),
    [
        (
            MeasureInBandManualState(),
            MeasurementTestType.INBAND,
            "inband",
            "measure_inband_manual_calls",
        ),
        (
            MeasureBilogManualState(),
            MeasurementTestType.BILOG,
            "bilog",
            "measure_bilog_manual_calls",
        ),
    ],
)
def test_measure_inband_and_bilog_manual_use_screenshot_png(
    tmp_path: Path,
    state: Any,
    test_type: MeasurementTestType,
    writer_name: str,
    manual_call_name: str,
) -> None:
    report_writer = _ReportWriter()
    commands = _Commands()
    events = _Events()
    ctx = _make_ctx(
        test_type,
        commands=commands,
        report_writer=report_writer,
        events=events,
        temp_dir=tmp_path,
    )
    ctx.equipment_state = {"FSV40": True}
    _enable_manual_marker(ctx, events)
    events.manual_marker_edit_required.on_emit = lambda _payload: (
        (tmp_path / "screenshot.png").write_bytes(b"manual screenshot"),
        ctx.user_action_completed.set(),
    )

    result = state.run(ctx)

    assert result is StateResult.OK
    assert getattr(commands, manual_call_name)
    assert commands.setup_sa_startup_levels_calls == [
        (None, {"atten_level_db": 1.5, "next_peak_search_level_db": 6.5})
    ]
    assert commands.get_screenshot_calls == [None]
    assert report_writer.calls[0][0] == writer_name
    measured = report_writer.calls[0][2]
    assert measured.screenshot_path == tmp_path / "screenshot.png"


