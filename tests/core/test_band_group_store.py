from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.band_group_store import load
from app.models.enums import FilterMode


def _sample_group(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "bands": [1, 3, 7],
        "test_ranges": [1, 2, 4],
        "hpf_factor": "3G HPF",
        "sa_recall": "SA_FDD",
        "scs_khz": 15,
        "turntable_speed": 6,
    }
    base.update(overrides)
    return base


def test_load_parses_single_group(tmp_path: Path) -> None:
    path = tmp_path / "band_groups.json"
    path.write_text(json.dumps({"groups": [_sample_group()]}), encoding="utf-8")

    groups = load(path)

    assert len(groups) == 1
    group = groups[0]
    assert group.bands == (1, 3, 7)
    assert group.test_ranges == (1, 2, 4)
    assert group.hpf_factor is FilterMode.HPF_3G
    assert group.sa_recall == "SA_FDD"
    assert group.scs_khz == 15
    assert group.turntable_speed == 6


def test_load_rejects_unknown_filter_label(tmp_path: Path) -> None:
    path = tmp_path / "band_groups.json"
    path.write_text(
        json.dumps({"groups": [_sample_group(hpf_factor="9G HPF")]}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Unknown filter mode label"):
        load(path)


def test_load_rejects_missing_fields(tmp_path: Path) -> None:
    path = tmp_path / "band_groups.json"
    bad = _sample_group()
    del bad["scs_khz"]
    path.write_text(json.dumps({"groups": [bad]}), encoding="utf-8")

    with pytest.raises(ValueError, match="Missing fields"):
        load(path)


def test_load_default_shipping_file() -> None:
    path = Path(__file__).resolve().parents[2] / "testcases" / "band_groups" / "default.json"
    groups = load(path)
    assert len(groups) == 4
    assert groups[0].bands[0] == 5
    assert groups[-1].sa_recall == "SA_TDD"
