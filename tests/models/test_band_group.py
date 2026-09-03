from __future__ import annotations

import pytest

from app.models.band_group import BAND_GROUPS, find_band_group, resolve_range_id
from app.models.enums import NRBand, TestType as BandTestType
from app.models.test_range import RangeId


def test_resolve_range_id_harmonic_all_groups() -> None:
    assert resolve_range_id("n5", BandTestType.HARMONIC) is RangeId.RANGE_3
    assert resolve_range_id("n1", BandTestType.HARMONIC) is RangeId.RANGE_4
    assert resolve_range_id("n38", BandTestType.HARMONIC) is RangeId.RANGE_4
    assert resolve_range_id("n78", BandTestType.HARMONIC) is RangeId.RANGE_6


def test_resolve_range_id_inband_all_groups() -> None:
    assert resolve_range_id("n20", BandTestType.INBAND) is RangeId.RANGE_1
    assert resolve_range_id("n3", BandTestType.INBAND) is RangeId.RANGE_2
    assert resolve_range_id("n41", BandTestType.INBAND) is RangeId.RANGE_2
    assert resolve_range_id("n77", BandTestType.INBAND) is RangeId.RANGE_5


def test_resolve_range_id_bilog_unsupported_on_first_group() -> None:
    with pytest.raises(ValueError, match="Bilog not supported"):
        resolve_range_id("n5", BandTestType.BILOG)


def test_resolve_range_id_bilog_supported_on_other_groups() -> None:
    assert resolve_range_id("n1", BandTestType.BILOG) is RangeId.RANGE_1
    assert resolve_range_id("n40", BandTestType.BILOG) is RangeId.RANGE_1
    assert resolve_range_id("n79", BandTestType.BILOG) is RangeId.RANGE_1


def test_resolve_range_id_accepts_numeric_string() -> None:
    assert resolve_range_id("78", BandTestType.HARMONIC) is RangeId.RANGE_6


def test_resolve_range_id_accepts_band_enum() -> None:
    assert resolve_range_id(NRBand.N78, BandTestType.HARMONIC) is RangeId.RANGE_6


def test_resolve_range_id_unknown_band() -> None:
    with pytest.raises(ValueError):
        resolve_range_id("n99", BandTestType.HARMONIC)


def test_find_band_group_returns_expected_profile() -> None:
    group = find_band_group(NRBand.N78)
    assert group.sa_recall == "6G HPF"
    assert group.mt8000_sa_recall == "5GNR_SA_TDD"
    assert group.mt8000_nsa_recall == "5GNR_NSA_TDD"
    assert group.scs_khz == 30
    assert group.turntable_speed == 3
    assert group.test_ranges == (RangeId.RANGE_1, RangeId.RANGE_5, RangeId.RANGE_6)


def test_band_groups_cover_four_profiles() -> None:
    assert len(BAND_GROUPS) == 4
    all_bands = {b for g in BAND_GROUPS for b in g.bands}
    assert {1, 3, 5, 7, 8, 20, 26, 28, 38, 40, 41, 71, 77, 78, 79} <= all_bands
