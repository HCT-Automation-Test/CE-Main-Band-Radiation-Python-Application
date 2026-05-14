from __future__ import annotations

import pytest

from app.models.enums import FilterMode, FilterPath, InputPath
from app.models.switch_box import resolve_filter_path
from app.models.test_range import RangeId, get_test_range


def test_range_id_coerce_accepts_supported_labels() -> None:
    assert RangeId.coerce(1) is RangeId.RANGE_1
    assert RangeId.coerce("range_2") is RangeId.RANGE_2
    assert RangeId.coerce("Range 6") is RangeId.RANGE_6


def test_range_id_coerce_rejects_unknown_values() -> None:
    with pytest.raises(ValueError, match="Unknown range"):
        RangeId.coerce("range_9")


def test_get_test_range_uses_fixed_spec_values() -> None:
    range_2 = get_test_range(RangeId.RANGE_2)
    range_4 = get_test_range(RangeId.RANGE_4)
    range_5 = get_test_range(RangeId.RANGE_5)

    assert range_2.start_freq == 1000.0
    assert range_2.stop_freq == 3000.0
    assert range_2.input_path is InputPath.INPUT1
    assert range_2.filter_mode is FilterMode.BRF
    assert range_4.start_freq == 3000.0
    assert range_4.stop_freq == 12750.0
    assert range_4.input_path is InputPath.INPUT1
    assert range_4.filter_mode is FilterMode.HPF_3G
    assert range_5.start_freq == 1000.0
    assert range_5.stop_freq == 6000.0
    assert range_5.input_path is InputPath.INPUT3
    assert range_5.filter_mode is FilterMode.BRF


def test_get_test_range_covers_low_band_settings() -> None:
    range_1 = get_test_range(RangeId.RANGE_1)

    assert range_1.start_freq == 30.0
    assert range_1.stop_freq == 1000.0
    assert range_1.rbw == 0.1
    assert range_1.vbw == 0.3
    assert range_1.limit == -36.0
    assert range_1.sweep_point == 10001
    assert range_1.input_path is InputPath.INPUT2
    assert range_1.filter_mode is FilterMode.BRF
    assert resolve_filter_path(range_1.filter_mode, "n78") is FilterPath.PORT_14


def test_get_test_range_keeps_group_specific_paths() -> None:
    range_3 = get_test_range(RangeId.RANGE_3)
    range_6 = get_test_range(RangeId.RANGE_6)

    assert range_3.input_path is InputPath.INPUT1
    assert range_3.filter_mode is FilterMode.HPF_1G
    assert range_6.input_path is InputPath.INPUT3
    assert range_6.filter_mode is FilterMode.HPF_6G
