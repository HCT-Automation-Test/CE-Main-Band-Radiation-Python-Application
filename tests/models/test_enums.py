from __future__ import annotations

import pytest

from app.models.enums import FilterMode, FilterPath, InputPath
from app.models.switch_box import parse_input_path, resolve_filter_path


def test_input_path_from_label() -> None:
    assert parse_input_path("Input3") is InputPath.INPUT3


def test_filter_mode_resolves_brf_band_to_port() -> None:
    assert resolve_filter_path(FilterMode.BRF, "n1") is FilterPath.PORT_1
    assert resolve_filter_path(FilterMode.BRF, "n78") is FilterPath.PORT_14
    assert resolve_filter_path(FilterMode.BRF, "79") is FilterPath.PORT_15


def test_filter_mode_resolves_direct_hpf_paths() -> None:
    assert resolve_filter_path(FilterMode.HPF_1G, "n78") is FilterPath.HPF_1G
    assert resolve_filter_path(FilterMode.HPF_3G, "n78") is FilterPath.HPF_3G
    assert resolve_filter_path(FilterMode.HPF_6G, "n78") is FilterPath.HPF_6G


def test_filter_mode_rejects_unsupported_brf_band() -> None:
    with pytest.raises(ValueError, match="Unsupported BRF band"):
        resolve_filter_path(FilterMode.BRF, "n2")
