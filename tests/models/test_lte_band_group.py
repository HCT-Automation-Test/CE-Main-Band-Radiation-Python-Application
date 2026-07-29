from __future__ import annotations

import pytest

from app.models.enums import DuplexMode, LTEBand, TestType as MeasurementTestType
from app.models.lte_band_group import (
    LTE_BAND_GROUPS,
    find_lte_band_group,
    resolve_lte_range_id,
)
from app.models.test_range import RangeId


def test_lte_band_groups_cover_all_supported_bands_once() -> None:
    bands = [band for group in LTE_BAND_GROUPS for band in group.bands]

    assert len(LTE_BAND_GROUPS) == 3
    assert len(bands) == 11
    assert len(set(bands)) == 11
    assert set(bands) == set(LTEBand)


@pytest.mark.parametrize(
    (
        "band",
        "duplex",
        "ranges",
        "factor_keyword",
        "recall",
        "scs_khz",
        "speed",
    ),
    [
        (
            LTEBand.B5,
            DuplexMode.FDD,
            (RangeId.RANGE_1, RangeId.RANGE_3),
            "1G HPF",
            "LTE_FDD.PRM",
            15,
            5,
        ),
        (
            LTEBand.B1,
            DuplexMode.FDD,
            (RangeId.RANGE_1, RangeId.RANGE_2, RangeId.RANGE_4),
            "3G HPF",
            "LTE_FDD.PRM",
            15,
            5,
        ),
        (
            LTEBand.B34,
            DuplexMode.TDD,
            (RangeId.RANGE_1, RangeId.RANGE_2, RangeId.RANGE_4),
            "3G HPF",
            "LTE_TDD.PRM",
            15,
            3,
        ),
    ],
)
def test_find_lte_band_group_returns_final_profile(
    band: LTEBand,
    duplex: DuplexMode,
    ranges: tuple[RangeId, ...],
    factor_keyword: str,
    recall: str,
    scs_khz: int,
    speed: int,
) -> None:
    profile = find_lte_band_group(band)

    assert profile.duplex is duplex
    assert profile.test_ranges == ranges
    assert profile.factor_keyword == factor_keyword
    assert profile.mt8000_recall == recall
    assert profile.scs_khz == scs_khz
    assert profile.turntable_speed == speed


@pytest.mark.parametrize("band", [LTEBand.B5, LTEBand.B8, LTEBand.B20, LTEBand.B28])
def test_lte_lb_range_mapping_and_bilog_rejection(band: LTEBand) -> None:
    assert resolve_lte_range_id(band, MeasurementTestType.INBAND) is RangeId.RANGE_1
    assert resolve_lte_range_id(band, MeasurementTestType.HARMONIC) is RangeId.RANGE_3
    with pytest.raises(ValueError, match="Bilog not supported"):
        resolve_lte_range_id(band, MeasurementTestType.BILOG)


@pytest.mark.parametrize(
    "band",
    [
        LTEBand.B1,
        LTEBand.B3,
        LTEBand.B7,
        LTEBand.B34,
        LTEBand.B38,
        LTEBand.B40,
        LTEBand.B41,
    ],
)
def test_lte_non_lb_range_mapping(band: LTEBand) -> None:
    assert resolve_lte_range_id(band, MeasurementTestType.BILOG) is RangeId.RANGE_1
    assert resolve_lte_range_id(band, MeasurementTestType.INBAND) is RangeId.RANGE_2
    assert resolve_lte_range_id(band, MeasurementTestType.HARMONIC) is RangeId.RANGE_4


def test_lte_band_group_lookup_accepts_case_insensitive_label() -> None:
    assert find_lte_band_group("b41").duplex is DuplexMode.TDD
