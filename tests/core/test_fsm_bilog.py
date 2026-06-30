from __future__ import annotations

from pathlib import Path

from app.models.enums import InputPath, NRBand, TestType as MeasurementTestType

from tests.core.test_fsm_harmonic import (
    _call_names,
    _make_case,
    _make_ctx,
    _run_session,
    _writer_call_names,
)


def test_bilog_measurement_chain(tmp_path: Path) -> None:
    case = _make_case(MeasurementTestType.BILOG)
    ctx, events, commands, writer = _make_ctx(tmp_path, [case])

    _run_session(ctx)

    assert events.state_changed.values == [
        "SessionInit",
        "Idle",
        "InitialTurntableZero",
        "AntPolChange",
        "SetupSpectrumAnalyzerStartupLevel",
        "NRCallConnect",
        "SetSwitchBox",
        "SetupSpectrumAnalyzer",
        "RotateTurntable",
        "MeasureBilog",
        "ResetSwitchBox",
        "CheckNextCase",
        "TestEnd",
    ]
    assert "measure_bilog" in _call_names(commands)
    assert _writer_call_names(writer) == ["write_bilog"]
    assert events.error.values == []


def test_bilog_test_type_change_from_inband(tmp_path: Path) -> None:
    inband_case = _make_case(
        MeasurementTestType.INBAND,
        band=NRBand.N1,
        bandwidth=20.0,
    )
    bilog_case = _make_case(
        MeasurementTestType.BILOG,
        band=NRBand.N1,
        bandwidth=20.0,
    )
    ctx, events, commands, writer = _make_ctx(tmp_path, [inband_case, bilog_case])

    _run_session(ctx)

    first_check_next_case = events.state_changed.values.index("CheckNextCase")
    assert events.state_changed.values[first_check_next_case + 1 : first_check_next_case + 6] == [
        "AntPolChange",
        "TestTypeChange",
        "SetSwitchBox",
        "SetupSpectrumAnalyzer",
        "RotateTurntable",
    ]
    ant_pol_calls = [
        params
        for name, params in commands.calls
        if name == "set_antenna_pol"
    ]
    assert ant_pol_calls == [
        {"pol": inband_case.antenna_pol, "input_path": InputPath.INPUT2},
        {"pol": bilog_case.antenna_pol, "input_path": InputPath.INPUT1},
    ]
    assert "measure_inband" in _call_names(commands)
    assert "measure_bilog" in _call_names(commands)
    assert _writer_call_names(writer) == ["write_inband", "write_bilog"]
    assert events.error.values == []
