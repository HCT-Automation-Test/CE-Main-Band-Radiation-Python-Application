from __future__ import annotations

import pytest

from app.core.band_group import BAND_GROUPS, find_band_group, resolve_range_id
from app.models.enums import FilterMode, TestType


def test_resolve_range_id_harmonic_all_groups() -> None:
    assert resolve_range_id("n5", TestType.HARMONIC) == 3
    assert resolve_range_id("n1", TestType.HARMONIC) == 4
    assert resolve_range_id("n38", TestType.HARMONIC) == 4
    assert resolve_range_id("n78", TestType.HARMONIC) == 6


def test_resolve_range_id_inband_all_groups() -> None:
    assert resolve_range_id("n20", TestType.INBAND) == 1
    assert resolve_range_id("n3", TestType.INBAND) == 2
    assert resolve_range_id("n41", TestType.INBAND) == 2
    assert resolve_range_id("n77", TestType.INBAND) == 5


def test_resolve_range_id_bilog_unsupported_on_first_group() -> None:
    with pytest.raises(ValueError, match="Bilog not supported"):
        resolve_range_id("n5", TestType.BILOG)


def test_resolve_range_id_bilog_supported_on_other_groups() -> None:
    assert resolve_range_id("n1", TestType.BILOG) == 1
    assert resolve_range_id("n40", TestType.BILOG) == 1
    assert resolve_range_id("n79", TestType.BILOG) == 1


def test_resolve_range_id_accepts_numeric_string() -> None:
    assert resolve_range_id("78", TestType.HARMONIC) == 6


def test_resolve_range_id_unknown_band() -> None:
    with pytest.raises(ValueError):
        resolve_range_id("n99", TestType.HARMONIC)


def test_find_band_group_returns_expected_profile() -> None:
    group = find_band_group("n78")
    assert group.sa_recall == "SA_TDD"
    assert group.scs_khz == 30
    assert group.turntable_speed == 4
    assert group.hpf_factor is FilterMode.HPF_6G
    assert group.test_ranges == (1, 5, 6)


def test_band_groups_cover_four_profiles() -> None:
    assert len(BAND_GROUPS) == 4
    all_bands = {b for g in BAND_GROUPS for b in g.bands}
    assert {1, 3, 5, 7, 8, 20, 26, 28, 38, 40, 41, 71, 77, 78, 79} <= all_bands
