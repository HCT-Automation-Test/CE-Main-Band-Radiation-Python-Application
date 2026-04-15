from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.range_preset_store import load
from app.models.enums import FilterMode, FilterPath, InputPath
from app.models.switch_box import resolve_filter_path


def test_load_range_presets(tmp_path: Path) -> None:
    preset_path = tmp_path / "presets.json"
    preset_path.write_text(
        json.dumps(
            {
                "_comment": "metadata should be ignored",
                "default": {
                    "start_freq": 100.0,
                    "stop_freq": 200.0,
                    "rbw": 1.0,
                    "vbw": 3.0,
                    "limit": -20.5,
                    "sweep_point": 401,
                    "input_path": "Input1",
                    "filter_mode": "BRF",
                },
            }
        ),
        encoding="utf-8",
    )

    presets = load(preset_path)

    assert set(presets) == {"default"}

    preset = presets["default"]
    assert preset.start_freq == 100.0
    assert preset.stop_freq == 200.0
    assert preset.rbw == 1.0
    assert preset.vbw == 3.0
    assert preset.limit == -20.5
    assert preset.sweep_point == 401
    assert preset.input_path is InputPath.INPUT1
    assert preset.filter_mode is FilterMode.BRF
    assert resolve_filter_path(preset.filter_mode, "n78") is FilterPath.PORT_14


def test_load_range_presets_rejects_legacy_keys(tmp_path: Path) -> None:
    preset_path = tmp_path / "presets.json"
    preset_path.write_text(
        json.dumps(
            {
                "legacy": {
                    "start_freq_hz": 100.0,
                    "stop_freq": 200.0,
                    "rbw": 1.0,
                    "vbw": 3.0,
                    "limit": -20.5,
                    "sweep_point": 401,
                    "input_path": "Input1",
                    "filter_mode": "BRF",
                }
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Unexpected fields"):
        load(preset_path)


def test_load_range_presets_rejects_invalid_filter_mode_label(tmp_path: Path) -> None:
    preset_path = tmp_path / "presets.json"
    preset_path.write_text(
        json.dumps(
            {
                "invalid": {
                    "start_freq": 100.0,
                    "stop_freq": 200.0,
                    "rbw": 1.0,
                    "vbw": 3.0,
                    "limit": -20.5,
                    "sweep_point": 401,
                    "input_path": "Input1",
                    "filter_mode": "port 1",
                }
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Unknown filter mode label"):
        load(preset_path)
