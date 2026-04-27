from __future__ import annotations

from pathlib import Path

from app.models.measurement_result import (
    BilogResult,
    FundamentalResult,
    HarmonicResult,
    InbandResult,
    MeasurementResult,
)


def test_fundamental_result_defaults_and_frequency_unit() -> None:
    result = FundamentalResult()

    assert result.screenshot_path is None
    assert result.fundamental_frequency_mhz is None


def test_harmonic_result_defaults_are_not_recordable() -> None:
    result = HarmonicResult()

    assert result.screenshot_path is None
    assert result.harmonic_2nd_peak_level_dbm is None
    assert result.harmonic_3rd_peak_level_dbm is None
    assert result.harmonic_4th_peak_level_dbm is None
    assert result.harmonic_5th_peak_level_dbm is None
    assert result.has_recordable_peak is False


def test_harmonic_result_is_recordable_when_any_peak_exists() -> None:
    result = HarmonicResult(harmonic_4th_peak_level_dbm=-36.5)

    assert result.has_recordable_peak is True


def test_inband_result_recordable_peak_policy() -> None:
    result = InbandResult()

    assert result.screenshot_path is None
    assert result.inband_peak_level_dbm is None
    assert result.has_recordable_peak is False

    result.inband_peak_level_dbm = -41.2

    assert result.has_recordable_peak is True


def test_bilog_result_recordable_peak_policy() -> None:
    result = BilogResult()

    assert result.screenshot_path is None
    assert result.bilog_peak_level_dbm is None
    assert result.has_recordable_peak is False

    result.bilog_peak_level_dbm = -29.8

    assert result.has_recordable_peak is True


def test_measurement_result_alias_accepts_state_results() -> None:
    results: list[MeasurementResult] = [
        FundamentalResult(
            screenshot_path=Path("tmp/fundamental.png"),
            fundamental_frequency_mhz=836.5,
        ),
        HarmonicResult(harmonic_2nd_peak_level_dbm=-43.0),
        InbandResult(inband_peak_level_dbm=-45.0),
        BilogResult(bilog_peak_level_dbm=-38.0),
    ]

    assert [type(result) for result in results] == [
        FundamentalResult,
        HarmonicResult,
        InbandResult,
        BilogResult,
    ]
