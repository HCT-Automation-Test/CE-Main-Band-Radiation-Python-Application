from __future__ import annotations

import pytest

from app.models.enums import (
    DUTAntPosition,
    FilterMode,
    FilterPath,
    InputPath,
    Modulation,
    NRBand,
    RBAllocation,
    TestChannel as ChannelEnum,
)
from app.models.switch_box import (
    display_filter_path,
    display_input_path,
    parse_input_path,
    resolve_filter_path,
)


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


def test_switch_box_display_input_path_labels() -> None:
    assert display_input_path(InputPath.INPUT1) == "3m"
    assert display_input_path(InputPath.INPUT2) == "Bilog"
    assert display_input_path(InputPath.INPUT3) == "1m"


def test_switch_box_display_filter_path_labels() -> None:
    assert display_filter_path(FilterPath.PORT_14) == "Port 14"
    assert display_filter_path(FilterPath.HPF_1G) == "1G HPF"
    assert display_filter_path(FilterPath.HPF_3G) == "3G HPF"
    assert display_filter_path(FilterPath.HPF_6G) == "6G HPF"
    assert display_filter_path(FilterPath.THRU) == "THRU"


def test_filter_mode_rejects_unsupported_brf_band() -> None:
    with pytest.raises(ValueError, match="Unsupported BRF band"):
        resolve_filter_path(FilterMode.BRF, "n2")


def test_modulation_enum_uses_canonical_labels() -> None:
    assert Modulation.QPSK.value == "QPSK"
    assert Modulation.PI_OVER_2_BPSK.value == "pi/2 BPSK"
    assert len(Modulation) == 2


def test_rb_allocation_enum_uses_canonical_labels() -> None:
    assert RBAllocation.INNER_FULL.value == "Inner_Full"
    assert RBAllocation.INNER_1RB_LEFT.value == "Inner_1RB_Left"
    assert RBAllocation.INNER_1RB_RIGHT.value == "Inner_1RB_Right"
    assert len(RBAllocation) == 3


def test_test_channel_enum_uses_canonical_labels() -> None:
    assert ChannelEnum.LOW.value == "low"
    assert ChannelEnum.MID.value == "mid"
    assert ChannelEnum.HIGH.value == "high"
    assert len(ChannelEnum) == 3


def test_dut_ant_position_enum_uses_canonical_labels() -> None:
    assert DUTAntPosition.UPPER.value == "Upper"
    assert DUTAntPosition.LOWER.value == "Lower"
    assert len(DUTAntPosition) == 2


def test_nr_band_enum_uses_canonical_labels() -> None:
    assert NRBand.N1.value == "n1"
    assert NRBand.N78.value == "n78"
    assert NRBand.N79.value == "n79"
