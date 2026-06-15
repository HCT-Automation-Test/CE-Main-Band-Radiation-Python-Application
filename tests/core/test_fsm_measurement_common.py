from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.core.fsm.base import StateResult
from app.core.fsm.context import SessionContext
from app.core.fsm.states.measurement import common as common_module
from app.core.fsm.states.measurement.common import (
    ResetSwitchBoxState,
    SetSwitchBoxState,
    SetupSpectrumAnalyzerState,
    SetupSpectrumAnalyzerStartupLevelState,
)
from app.models.enums import (
    AntennaPol,
    DUTAxis,
    FilterPath,
    InputPath,
    Modulation,
    NRBand,
    RBAllocation,
    TestChannel as ChannelEnum,
    TestType as MeasurementTestType,
)
from app.models.test_case import TestCase
from app.models.test_range import TestRange
from app.models.test_run_settings import TestRunSettings


class _SignalRecorder:
    def __init__(self) -> None:
        self.messages: list[Any] = []

    def emit(self, message: Any) -> None:
        self.messages.append(message)


class _Events:
    def __init__(self) -> None:
        self.error = _SignalRecorder()
        self.spectrum_analyzer_info_changed = _SignalRecorder()
        self.switch_box_info_changed = _SignalRecorder()


class _Commands:
    def __init__(
        self,
        *,
        switch_box_configured: bool = True,
        switch_box_exception: Exception | None = None,
        sa_configured: bool = True,
        sa_exception: Exception | None = None,
        startup_level_configured: bool = True,
        startup_level_exception: Exception | None = None,
    ) -> None:
        self.switch_box_configured = switch_box_configured
        self.switch_box_exception = switch_box_exception
        self.sa_configured = sa_configured
        self.sa_exception = sa_exception
        self.startup_level_configured = startup_level_configured
        self.startup_level_exception = startup_level_exception
        self.switch_box_calls: list[tuple[Any, dict[str, Any]]] = []
        self.setup_sa_calls: list[tuple[Any, TestRange]] = []
        self.startup_level_calls: list[tuple[Any, dict[str, Any]]] = []

    def set_switch_box(self, client: Any, **params: Any) -> bool:
        self.switch_box_calls.append((client, params))
        if self.switch_box_exception is not None:
            raise self.switch_box_exception
        return self.switch_box_configured

    def setup_sa(self, client: Any, *, test_range: TestRange) -> bool:
        self.setup_sa_calls.append((client, test_range))
        if self.sa_exception is not None:
            raise self.sa_exception
        return self.sa_configured

    def setup_sa_startup_levels(self, client: Any, **params: Any) -> bool:
        self.startup_level_calls.append((client, params))
        if self.startup_level_exception is not None:
            raise self.startup_level_exception
        return self.startup_level_configured


def _make_case(test_type: MeasurementTestType) -> TestCase:
    return TestCase(
        band=NRBand.N78,
        bandwidth=100.0,
        test_type=test_type,
        modulation=Modulation.QPSK,
        rb_allocation=RBAllocation.INNER_FULL,
        test_channel=ChannelEnum.MID,
        antenna_pol=AntennaPol.H,
        dut_axis=DUTAxis.X,
        dut_ant_position="Upper",
    )


def _make_settings(
    tmp_path: Path,
    *,
    saturation_time_sec: float = 0.0,
    atten_level_db: float = 1.5,
    next_peak_search_level_db: float = -20.0,
) -> TestRunSettings:
    template_path = tmp_path / "template.xlsx"
    screenshot_root_dir = tmp_path / "screenshots"
    template_path.write_bytes(b"template")
    screenshot_root_dir.mkdir(exist_ok=True)
    return TestRunSettings(
        eut_name="SM-000",
        template_path=template_path,
        screenshot_root_dir=screenshot_root_dir,
        saturation_time_sec=saturation_time_sec,
        connection_waiting_time_sec=5,
        atten_level_db=atten_level_db,
        next_peak_search_level_db=next_peak_search_level_db,
    )


def _connect_equipment(ctx: SessionContext, *names: str) -> SessionContext:
    ctx.equipment_state = {name: True for name in names}
    return ctx


@pytest.fixture(autouse=True)
def _skip_default_saturation_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    """settings가 없는 기존 state 단위 테스트는 fallback 대기를 생략한다."""
    monkeypatch.setattr(common_module, "_SETTLING_SEC", 0.0)


def test_setup_spectrum_analyzer_startup_level_uses_settings(
    tmp_path: Path,
) -> None:
    commands = _Commands()
    client = object()
    ctx = _connect_equipment(SessionContext(
        queue=[_make_case(MeasurementTestType.HARMONIC)],
        commands=commands,
        events=_Events(),  # type: ignore[arg-type]
        client=client,
        settings=_make_settings(
            tmp_path,
            atten_level_db=2.5,
            next_peak_search_level_db=-18.5,
        ),
    ), "FSV40")

    result = SetupSpectrumAnalyzerStartupLevelState().run(ctx)

    assert result is StateResult.OK
    assert commands.startup_level_calls == [
        (
            client,
            {
                "atten_level_db": 2.5,
                "next_peak_search_level_db": -18.5,
            },
        )
    ]


def test_setup_spectrum_analyzer_startup_level_skips_when_fsv40_is_not_connected(
    tmp_path: Path,
) -> None:
    commands = _Commands()
    events = _Events()
    ctx = _connect_equipment(SessionContext(
        queue=[_make_case(MeasurementTestType.HARMONIC)],
        commands=commands,
        events=events,  # type: ignore[arg-type]
        settings=_make_settings(tmp_path),
    ), "FSV40")
    ctx.equipment_state = {"FSV40": False}
    state = SetupSpectrumAnalyzerStartupLevelState()

    result = state.run(ctx)

    assert result is StateResult.OK
    assert state.next_state(ctx, result) == "NRCallConnect"
    assert commands.startup_level_calls == []
    assert events.error.messages


def test_setup_spectrum_analyzer_startup_level_returns_fail_on_false_result(
    tmp_path: Path,
) -> None:
    commands = _Commands(startup_level_configured=False)
    events = _Events()
    ctx = _connect_equipment(SessionContext(
        queue=[_make_case(MeasurementTestType.HARMONIC)],
        commands=commands,
        events=events,  # type: ignore[arg-type]
        settings=_make_settings(tmp_path),
    ), "FSV40")
    state = SetupSpectrumAnalyzerStartupLevelState()

    result = state.run(ctx)

    assert result is StateResult.FAIL
    assert state.next_state(ctx, result) is None
    assert events.error.messages == [
        "Spectrum Analyzer Startup Level 설정 실패: "
        "setup_sa_startup_levels returned false"
    ]


def test_setup_spectrum_analyzer_startup_level_returns_fail_on_exception(
    tmp_path: Path,
) -> None:
    commands = _Commands(startup_level_exception=RuntimeError("instrument timeout"))
    events = _Events()
    ctx = _connect_equipment(SessionContext(
        queue=[_make_case(MeasurementTestType.HARMONIC)],
        commands=commands,
        events=events,  # type: ignore[arg-type]
        settings=_make_settings(tmp_path),
    ), "FSV40")
    state = SetupSpectrumAnalyzerStartupLevelState()

    result = state.run(ctx)

    assert result is StateResult.FAIL
    assert state.next_state(ctx, result) is None
    assert events.error.messages == [
        "Spectrum Analyzer Startup Level 설정 실패: instrument timeout"
    ]


def test_setup_spectrum_analyzer_startup_level_requires_settings() -> None:
    events = _Events()
    ctx = SessionContext(
        queue=[_make_case(MeasurementTestType.HARMONIC)],
        commands=_Commands(),
        events=events,  # type: ignore[arg-type]
    )

    result = SetupSpectrumAnalyzerStartupLevelState().run(ctx)

    assert result is StateResult.FAIL
    assert events.error.messages == [
        "Spectrum Analyzer Startup Level 설정 실패: settings is required"
    ]


def test_setup_spectrum_analyzer_startup_level_goes_to_nr_call_connect(
    tmp_path: Path,
) -> None:
    ctx = SessionContext(
        queue=[_make_case(MeasurementTestType.HARMONIC)],
        commands=_Commands(),
        events=_Events(),  # type: ignore[arg-type]
        settings=_make_settings(tmp_path),
    )
    state = SetupSpectrumAnalyzerStartupLevelState()

    result = state.run(ctx)

    assert state.next_state(ctx, result) == "NRCallConnect"


def test_set_switch_box_uses_hpf_filter_path_from_range_definition() -> None:
    commands = _Commands()
    client = object()
    events = _Events()
    ctx = _connect_equipment(SessionContext(
        queue=[_make_case(MeasurementTestType.HARMONIC)],
        commands=commands,
        events=events,  # type: ignore[arg-type]
        client=client,
    ), "Switch Box")

    result = SetSwitchBoxState().run(ctx)

    assert result is StateResult.OK
    assert commands.switch_box_calls == [
        (
            client,
            {
                "input_path": InputPath.INPUT3,
                "filter_path": FilterPath.HPF_6G,
            },
        )
    ]
    assert events.switch_box_info_changed.messages == [
        {"mast": "1m", "filter": "6G HPF"}
    ]


def test_set_switch_box_skips_when_switch_box_is_not_connected() -> None:
    commands = _Commands()
    events = _Events()
    ctx = SessionContext(
        queue=[_make_case(MeasurementTestType.HARMONIC)],
        commands=commands,
        events=events,  # type: ignore[arg-type]
    )
    ctx.equipment_state = {"Switch Box": False}
    state = SetSwitchBoxState()

    result = state.run(ctx)

    assert result is StateResult.OK
    assert state.next_state(ctx, result) == "SetupSpectrumAnalyzer"
    assert commands.switch_box_calls == []
    assert events.switch_box_info_changed.messages == []
    assert events.error.messages


def test_set_switch_box_skips_when_equipment_state_is_empty_after_disconnect() -> None:
    commands = _Commands()
    events = _Events()
    ctx = SessionContext(
        queue=[_make_case(MeasurementTestType.HARMONIC)],
        commands=commands,
        events=events,  # type: ignore[arg-type]
    )
    state = SetSwitchBoxState()

    result = state.run(ctx)

    assert result is StateResult.OK
    assert state.next_state(ctx, result) == "SetupSpectrumAnalyzer"
    assert commands.switch_box_calls == []
    assert events.error.messages


def test_reset_switch_box_does_not_emit_info_on_false_result() -> None:
    commands = _Commands(switch_box_configured=False)
    events = _Events()
    ctx = _connect_equipment(SessionContext(
        queue=[_make_case(MeasurementTestType.HARMONIC)],
        commands=commands,
        events=events,  # type: ignore[arg-type]
    ), "Switch Box")

    result = ResetSwitchBoxState().run(ctx)

    assert result is StateResult.FAIL
    assert events.switch_box_info_changed.messages == []


def test_reset_switch_box_does_not_emit_info_on_exception() -> None:
    commands = _Commands(switch_box_exception=RuntimeError("instrument timeout"))
    events = _Events()
    ctx = _connect_equipment(SessionContext(
        queue=[_make_case(MeasurementTestType.HARMONIC)],
        commands=commands,
        events=events,  # type: ignore[arg-type]
    ), "Switch Box")
    state = ResetSwitchBoxState()

    result = state.run(ctx)

    assert result is StateResult.FAIL
    assert state.next_state(ctx, result) is None
    assert events.switch_box_info_changed.messages == []
    assert events.error.messages == [
        "Switch Box 기본 경로 복원 실패: instrument timeout"
    ]


def test_set_switch_box_resolves_brf_filter_path_by_band() -> None:
    commands = _Commands()
    client = object()
    events = _Events()
    ctx = _connect_equipment(SessionContext(
        queue=[_make_case(MeasurementTestType.INBAND)],
        commands=commands,
        events=events,  # type: ignore[arg-type]
        client=client,
    ), "Switch Box")

    result = SetSwitchBoxState().run(ctx)

    assert result is StateResult.OK
    assert commands.switch_box_calls == [
        (
            client,
            {
                "input_path": InputPath.INPUT3,
                "filter_path": FilterPath.PORT_14,
            },
        )
    ]
    assert events.switch_box_info_changed.messages == [
        {"mast": "1m", "filter": "Port 14"}
    ]


def test_set_switch_box_returns_fail_and_stops_on_false_result() -> None:
    commands = _Commands(switch_box_configured=False)
    events = _Events()
    ctx = _connect_equipment(SessionContext(
        queue=[_make_case(MeasurementTestType.HARMONIC)],
        commands=commands,
        events=events,  # type: ignore[arg-type]
    ), "Switch Box")
    state = SetSwitchBoxState()

    result = state.run(ctx)

    assert result is StateResult.FAIL
    assert state.next_state(ctx, result) is None
    assert events.error.messages == [
        "Switch Box RF 경로 설정 실패: set_switch_box returned false"
    ]


def test_set_switch_box_does_not_emit_info_on_false_result() -> None:
    commands = _Commands(switch_box_configured=False)
    events = _Events()
    ctx = _connect_equipment(SessionContext(
        queue=[_make_case(MeasurementTestType.HARMONIC)],
        commands=commands,
        events=events,  # type: ignore[arg-type]
    ), "Switch Box")

    result = SetSwitchBoxState().run(ctx)

    assert result is StateResult.FAIL
    assert events.switch_box_info_changed.messages == []


def test_set_switch_box_does_not_emit_info_on_exception() -> None:
    commands = _Commands(switch_box_exception=RuntimeError("instrument timeout"))
    events = _Events()
    ctx = _connect_equipment(SessionContext(
        queue=[_make_case(MeasurementTestType.HARMONIC)],
        commands=commands,
        events=events,  # type: ignore[arg-type]
    ), "Switch Box")
    state = SetSwitchBoxState()

    result = state.run(ctx)

    assert result is StateResult.FAIL
    assert state.next_state(ctx, result) is None
    assert events.switch_box_info_changed.messages == []
    assert events.error.messages == [
        "Switch Box RF 경로 설정 실패: instrument timeout"
    ]


def test_setup_spectrum_analyzer_uses_current_case_test_range() -> None:
    commands = _Commands()
    client = object()
    case = _make_case(MeasurementTestType.HARMONIC)
    events = _Events()
    ctx = _connect_equipment(SessionContext(
        queue=[case],
        commands=commands,
        events=events,  # type: ignore[arg-type]
        client=client,
    ), "FSV40")

    result = SetupSpectrumAnalyzerState().run(ctx)

    assert result is StateResult.OK
    assert commands.setup_sa_calls == [(client, case.range_definition)]
    test_range = commands.setup_sa_calls[0][1]
    assert test_range.start_freq == 6000.0
    assert test_range.stop_freq == 18000.0
    assert test_range.rbw == 1.0
    assert test_range.vbw == 3.0
    assert test_range.limit == -30.0
    assert test_range.sweep_point == 30001
    assert events.spectrum_analyzer_info_changed.messages == [
        {
            "start_freq": 6000.0,
            "stop_freq": 18000.0,
            "trace_mode": "Max Hold",
            "rbw": 1.0,
            "vbw": 3.0,
            "sweep_point": 30001,
            "limit": -30.0,
        }
    ]


def test_setup_spectrum_analyzer_skips_when_fsv40_is_not_connected() -> None:
    commands = _Commands()
    events = _Events()
    ctx = _connect_equipment(SessionContext(
        queue=[_make_case(MeasurementTestType.HARMONIC)],
        commands=commands,
        events=events,  # type: ignore[arg-type]
    ), "Switch Box")
    ctx.equipment_state = {"FSV40": False}
    state = SetupSpectrumAnalyzerState()

    result = state.run(ctx)

    assert result is StateResult.OK
    assert state.next_state(ctx, result) == "RotateTurntable"
    assert commands.setup_sa_calls == []
    assert events.spectrum_analyzer_info_changed.messages == []
    assert events.error.messages


def test_setup_spectrum_analyzer_returns_fail_when_stopped_during_saturation(
    tmp_path: Path,
) -> None:
    commands = _Commands()
    client = object()
    case = _make_case(MeasurementTestType.HARMONIC)
    events = _Events()
    ctx = _connect_equipment(SessionContext(
        queue=[case],
        commands=commands,
        events=events,  # type: ignore[arg-type]
        client=client,
        settings=_make_settings(tmp_path, saturation_time_sec=1.0),
        stopped=True,
    ), "FSV40")
    state = SetupSpectrumAnalyzerState()

    result = state.run(ctx)

    assert result is StateResult.FAIL
    assert state.next_state(ctx, result) is None
    assert commands.setup_sa_calls == [(client, case.range_definition)]


def test_setup_spectrum_analyzer_returns_fail_when_current_case_stop_requested(
    tmp_path: Path,
) -> None:
    commands = _Commands()
    client = object()
    case = _make_case(MeasurementTestType.HARMONIC)
    events = _Events()
    ctx = _connect_equipment(SessionContext(
        queue=[case],
        commands=commands,
        events=events,  # type: ignore[arg-type]
        client=client,
        settings=_make_settings(tmp_path, saturation_time_sec=1.0),
        current_case_stop_requested=True,
    ), "FSV40")
    state = SetupSpectrumAnalyzerState()

    result = state.run(ctx)

    assert result is StateResult.FAIL
    assert state.next_state(ctx, result) is None
    assert commands.setup_sa_calls == [(client, case.range_definition)]


def test_setup_spectrum_analyzer_returns_fail_and_stops_on_false_result() -> None:
    commands = _Commands(sa_configured=False)
    events = _Events()
    ctx = _connect_equipment(SessionContext(
        queue=[_make_case(MeasurementTestType.HARMONIC)],
        commands=commands,
        events=events,  # type: ignore[arg-type]
    ), "FSV40")
    state = SetupSpectrumAnalyzerState()

    result = state.run(ctx)

    assert result is StateResult.FAIL
    assert state.next_state(ctx, result) is None
    assert events.error.messages == [
        "Spectrum Analyzer 설정 실패: setup_sa returned false"
    ]


def test_setup_spectrum_analyzer_does_not_emit_info_on_false_result() -> None:
    commands = _Commands(sa_configured=False)
    events = _Events()
    ctx = _connect_equipment(SessionContext(
        queue=[_make_case(MeasurementTestType.HARMONIC)],
        commands=commands,
        events=events,  # type: ignore[arg-type]
    ), "FSV40")

    result = SetupSpectrumAnalyzerState().run(ctx)

    assert result is StateResult.FAIL
    assert events.spectrum_analyzer_info_changed.messages == []


def test_setup_spectrum_analyzer_does_not_emit_info_on_exception() -> None:
    commands = _Commands(sa_exception=RuntimeError("instrument timeout"))
    events = _Events()
    ctx = _connect_equipment(SessionContext(
        queue=[_make_case(MeasurementTestType.HARMONIC)],
        commands=commands,
        events=events,  # type: ignore[arg-type]
    ), "FSV40")
    state = SetupSpectrumAnalyzerState()

    result = state.run(ctx)

    assert result is StateResult.FAIL
    assert state.next_state(ctx, result) is None
    assert events.spectrum_analyzer_info_changed.messages == []
    assert events.error.messages == [
        "Spectrum Analyzer 설정 실패: instrument timeout"
    ]


def test_reset_switch_box_uses_input1_and_thru() -> None:
    commands = _Commands()
    client = object()
    events = _Events()
    ctx = _connect_equipment(SessionContext(
        queue=[_make_case(MeasurementTestType.HARMONIC)],
        commands=commands,
        events=events,  # type: ignore[arg-type]
        client=client,
    ), "Switch Box")

    result = ResetSwitchBoxState().run(ctx)

    assert result is StateResult.OK
    assert commands.switch_box_calls == [
        (
            client,
            {
                "input_path": InputPath.INPUT1,
                "filter_path": FilterPath.THRU,
            },
        )
    ]
    assert events.switch_box_info_changed.messages == [
        {"mast": "Bilog", "filter": "THRU"}
    ]


def test_reset_switch_box_skips_when_switch_box_is_not_connected() -> None:
    commands = _Commands()
    events = _Events()
    ctx = _connect_equipment(SessionContext(
        queue=[_make_case(MeasurementTestType.HARMONIC)],
        commands=commands,
        events=events,  # type: ignore[arg-type]
    ), "Switch Box")
    ctx.equipment_state = {"Switch Box": False}
    state = ResetSwitchBoxState()

    result = state.run(ctx)

    assert result is StateResult.OK
    assert state.next_state(ctx, result) == "CheckNextCase"
    assert commands.switch_box_calls == []
    assert events.switch_box_info_changed.messages == []
    assert events.error.messages


def test_reset_switch_box_returns_fail_and_stops_on_false_result() -> None:
    commands = _Commands(switch_box_configured=False)
    events = _Events()
    ctx = _connect_equipment(SessionContext(
        queue=[_make_case(MeasurementTestType.HARMONIC)],
        commands=commands,
        events=events,  # type: ignore[arg-type]
    ), "Switch Box")
    state = ResetSwitchBoxState()

    result = state.run(ctx)

    assert result is StateResult.FAIL
    assert state.next_state(ctx, result) is None
    assert events.error.messages == [
        "Switch Box 기본 경로 복원 실패: set_switch_box returned false"
    ]
