from __future__ import annotations

from pathlib import Path

from app.models.enums import TestType as MeasurementTestType

from tests.core.test_fsm_harmonic import (
    _call_names,
    _make_case,
    _make_ctx,
    _run_session,
    _writer_call_names,
)


def test_inband_measurement_chain(tmp_path: Path) -> None:
    case = _make_case(MeasurementTestType.INBAND)
    ctx, events, commands, writer = _make_ctx(tmp_path, [case])

    _run_session(ctx)

    assert events.state_changed.values == [
        "SessionInit",
        "Idle",
        "PrepareReport",
        "InitialTurntableZero",
        "AntPolChange",
        "SetupSpectrumAnalyzerStartupLevel",
        "NRCallConnect",
        "ApplyTdf",
        "SetSwitchBox",
        "SetupSpectrumAnalyzer",
        "RotateTurntable",
        "MeasureInBand",
        "ResetSwitchBox",
        "CheckNextCase",
        "TestEnd",
    ]
    assert "measure_inband" in _call_names(commands)
    assert _writer_call_names(writer) == ["write_inband"]
    assert events.error.values == []


def test_inband_test_type_change_from_harmonic(tmp_path: Path) -> None:
    harmonic_case = _make_case(MeasurementTestType.HARMONIC)
    inband_case = _make_case(MeasurementTestType.INBAND)
    ctx, events, commands, writer = _make_ctx(
        tmp_path,
        [harmonic_case, inband_case],
    )

    _run_session(ctx)

    first_check_next_case = events.state_changed.values.index("CheckNextCase")
    assert events.state_changed.values[first_check_next_case + 1 : first_check_next_case + 6] == [
        "TestTypeChange",
        "ApplyTdf",
        "SetSwitchBox",
        "SetupSpectrumAnalyzer",
        "RotateTurntable",
    ]
    assert "measure_harmonics" in _call_names(commands)
    assert "measure_inband" in _call_names(commands)
    assert _writer_call_names(writer) == [
        "read_fundamental_frequency",
        "write_fundamental",
        "write_harmonic",
        "write_inband",
    ]
    assert events.error.values == []
