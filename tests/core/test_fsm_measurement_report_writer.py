from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.core.fsm.base import StateResult
from app.core.fsm.context import SessionContext
from app.core.fsm.states.measurement.bilog import MeasureBilogState
from app.core.fsm.states.measurement.harmonic import (
    MeasureFundamentalState,
    MeasureHarmonicsState,
)
from app.core.fsm.states.measurement.inband import MeasureInBandState
from app.models.enums import (
    AntennaPol,
    DUTAntPosition,
    DUTAxis,
    Modulation,
    NRBand,
    RBAllocation,
    TestChannel as ChannelEnum,
    TestType as MeasurementTestType,
)
from app.models.measurement_result import (
    BilogResult,
    FundamentalResult,
    HarmonicResult,
    InbandResult,
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
        self.screenshot_saved = _SignalRecorder()
        self.spectrum_analyzer_info_changed = _SignalRecorder()


class _Commands:
    def __init__(
        self,
        *,
        fundamental_frequency_mhz: float = 3549.99,
        harmonic_levels: object = (-41.0, -39.5, -40.0, -37.0),
        fundamental_exception: Exception | None = None,
        harmonics_exception: Exception | None = None,
        fundamental_screenshot_path: Path | None = None,
        harmonic_screenshot_path: Path | None = None,
    ) -> None:
        self.fundamental_frequency_mhz = fundamental_frequency_mhz
        self.harmonic_levels = harmonic_levels
        self.fundamental_exception = fundamental_exception
        self.harmonics_exception = harmonics_exception
        self.fundamental_screenshot_path = fundamental_screenshot_path
        self.harmonic_screenshot_path = harmonic_screenshot_path
        self.measure_fundamental_calls: list[tuple[Any, dict[str, Any]]] = []
        self.measure_harmonics_calls: list[tuple[Any, dict[str, Any]]] = []

    def measure_fundamental(self, client: Any, *, target_freq: float) -> float:
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
    return SessionContext(
        queue=[case or _make_case(test_type)],
        commands=commands or _Commands(),
        events=events,  # type: ignore[arg-type]
        report_writer=report_writer,
        temp_dir=temp_dir,
        fundamental_frequency_mhz=fundamental_frequency_mhz,
        model_name=model_name,
        screenshot_root_dir=screenshot_root_dir or temp_dir,
    )


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
    assert commands.measure_fundamental_calls == []
    assert ctx.fundamental_frequency_mhz == 3550.25
    assert screenshot_path.read_bytes() == b"stale"
    assert events.screenshot_saved.messages == []
    assert events.spectrum_analyzer_info_changed.messages == []


def test_measure_harmonics_uses_fundamental_threshold_and_screenshot(
    tmp_path: Path,
) -> None:
    report_writer = _ReportWriter()
    screenshot_path = tmp_path / "harmonic.png"
    screenshot_path.write_bytes(b"stale")
    commands = _Commands(
        harmonic_levels=(-41.0, -39.9, -40.0, -37.5),
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


def test_measure_harmonics_writes_report_even_when_no_peak_exceeds_threshold(
    tmp_path: Path,
) -> None:
    report_writer = _ReportWriter()
    screenshot_path = tmp_path / "harmonic.png"
    commands = _Commands(
        harmonic_levels=(-45.0, -40.0, -42.0, -50.0),
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
    measured = report_writer.calls[0][2]
    assert isinstance(measured, HarmonicResult)
    assert measured.harmonic_2nd_peak_level_dbm is None
    assert measured.harmonic_3rd_peak_level_dbm is None
    assert measured.harmonic_4th_peak_level_dbm is None
    assert measured.harmonic_5th_peak_level_dbm is None


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
            "Harmonic 측정 실패: Harmonic 측정 응답 형식 오류: expected 4 peak levels, got 3",
        ),
        (
            ("bad", -39.0, -38.0, -37.0),
            "Harmonic 측정 실패: Harmonic 측정 응답 형식 오류: expected 4 numeric peak levels",
        ),
        (
            None,
            "Harmonic 측정 실패: Harmonic 측정 응답 형식 오류: expected 4 numeric peak levels",
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
    (tmp_path / "inband.png").write_bytes(b"png")
    ctx = _make_ctx(
        MeasurementTestType.INBAND,
        report_writer=report_writer,
        events=events,
        temp_dir=tmp_path,
    )
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
    (tmp_path / "bilog.png").write_bytes(b"png")
    ctx = _make_ctx(
        MeasurementTestType.BILOG,
        report_writer=report_writer,
        events=events,
        temp_dir=tmp_path,
    )
    state = MeasureBilogState()

    result = state.run(ctx)

    assert result is StateResult.FAIL
    assert state.next_state(ctx, result) is None
    assert report_writer.calls == []
    assert events.error.messages == ["리포트 작성 실패: disk full"]


@pytest.mark.parametrize(
    ("state", "test_type", "expected_name", "expected_result_type"),
    [
        (
            MeasureInBandState(),
            MeasurementTestType.INBAND,
            "inband",
            InbandResult,
        ),
        (MeasureBilogState(), MeasurementTestType.BILOG, "bilog", BilogResult),
    ],
)
def test_non_harmonic_measurement_states_call_individual_report_writer_methods(
    tmp_path: Path,
    state: Any,
    test_type: MeasurementTestType,
    expected_name: str,
    expected_result_type: type,
) -> None:
    report_writer = _ReportWriter()
    screenshot_name = (
        "inband.png" if test_type is MeasurementTestType.INBAND else "bilog.png"
    )
    (tmp_path / screenshot_name).write_bytes(b"png")
    ctx = _make_ctx(test_type, report_writer=report_writer, temp_dir=tmp_path)

    result = state.run(ctx)

    assert result is StateResult.OK
    assert report_writer.calls[0][0] == expected_name
    assert report_writer.calls[0][1] == ctx.current_case
    measured = report_writer.calls[0][2]
    assert isinstance(measured, expected_result_type)
    assert measured.screenshot_path is not None
    assert measured.screenshot_path.is_file()


def test_measure_fundamental_returns_ok_without_report_writer(
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

    assert result is StateResult.OK
    assert ctx.fundamental_frequency_mhz == 3550.25


def test_measure_harmonics_returns_ok_without_report_writer(
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

    assert result is StateResult.OK
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
def test_non_harmonic_measurement_states_return_ok_without_report_writer(
    tmp_path: Path,
    state: Any,
    test_type: MeasurementTestType,
) -> None:
    screenshot_name = (
        "inband.png" if test_type is MeasurementTestType.INBAND else "bilog.png"
    )
    (tmp_path / screenshot_name).write_bytes(b"png")
    ctx = _make_ctx(test_type, temp_dir=tmp_path)

    result = state.run(ctx)

    assert result is StateResult.OK
