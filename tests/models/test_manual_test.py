from __future__ import annotations

import pytest

from app.models.enums import InputPath
from app.models.manual_test import (
    MANUAL_FREQUENCY_PRESETS,
    ManualMast,
    ManualPresetId,
    ManualSaSettings,
    get_manual_frequency_preset,
)


def test_manual_frequency_presets_define_expected_ranges() -> None:
    assert len(MANUAL_FREQUENCY_PRESETS) == 9
    assert get_manual_frequency_preset(1).start_frequency_mhz == 30.0
    assert get_manual_frequency_preset(3).stop_frequency_mhz == 12750.0
    assert get_manual_frequency_preset(7).rbw_mhz == 0.1
    assert get_manual_frequency_preset(8).stop_frequency_mhz == 4000.0
    assert get_manual_frequency_preset(9).start_frequency_mhz == 3000.0


def test_manual_frequency_preset_labels_use_display_units_without_ids() -> None:
    assert get_manual_frequency_preset(1).label == "30 MHz ~ 1 GHz"
    assert get_manual_frequency_preset(3).label == "1 GHz ~ 12.75 GHz"
    assert get_manual_frequency_preset(6).label == "6 GHz ~ 18 GHz"
    assert get_manual_frequency_preset(2).label == "1 GHz ~ 3 GHz"
    assert get_manual_frequency_preset(7).label == "1 GHz ~ 3 GHz"


def test_manual_mast_maps_to_existing_input_contract() -> None:
    assert ManualMast.BILOG_3M.input_path is InputPath.INPUT1
    assert ManualMast.HORN_3M.input_path is InputPath.INPUT2
    assert ManualMast.MAST_1M.input_path is InputPath.INPUT3


def _settings(**overrides: object) -> ManualSaSettings:
    values = {
        "start_frequency_mhz": 1000.0,
        "stop_frequency_mhz": 12750.0,
        "rbw_mhz": 1.0,
        "vbw_mhz": 3.0,
        "sweep_point": 30001,
        "sweep_time_sec": 0.1,
        "saturation_time_sec": 5.0,
        "atten_level_db": 0.0,
        "detector_mode": "RMS",
        "limit_dbm": -30.0,
    }
    values.update(overrides)
    return ManualSaSettings(**values)


def test_manual_sa_settings_accept_valid_input() -> None:
    assert _settings().sweep_point == 30001


@pytest.mark.parametrize(
    "overrides",
    [
        {"start_frequency_mhz": -1.0},
        {"start_frequency_mhz": 1000.0, "stop_frequency_mhz": 1000.0},
        {"rbw_mhz": 0.0},
        {"vbw_mhz": -1.0},
        {"sweep_point": 1.5},
        {"sweep_time_sec": 0.0},
        {"saturation_time_sec": -1.0},
        {"detector_mode": "invalid"},
    ],
)
def test_manual_sa_settings_reject_obvious_input_errors(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        _settings(**overrides)


def test_unknown_manual_preset_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unknown manual preset"):
        get_manual_frequency_preset(ManualPresetId.PRESET_9.value + 1)
