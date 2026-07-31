from __future__ import annotations

import pytest
from openpyxl.utils.cell import coordinate_to_tuple

from app.models.band_group import BAND_GROUPS
from app.models.enums import AntennaPol, DUTAxis, Generation, LTEBand, NRBand
from app.models.lte_band_group import find_lte_band_group
from app.report.template_map import (
    ALLOWED_BAND_GROUP_KEYS,
    LAYOUTS,
    LB_LAYOUT_KEY,
    bilog_level_cell,
    LTE_DEFAULT_LAYOUT_KEY,
    LTE_LB_LAYOUT_KEY,
    harmonic_frequency_cell,
    harmonic_level_cell,
    inband_level_cell,
    layout_for_group_key_and_generation,
    sheet_name_for_band,
)


def test_every_nr_band_has_sub6_sheet_name() -> None:
    for band in NRBand:
        assert sheet_name_for_band(band) == f"Sub6 {band.value}"


def test_band_group_keys_are_allowed() -> None:
    assert {group.key for group in BAND_GROUPS} == ALLOWED_BAND_GROUP_KEYS


@pytest.mark.parametrize(
    "layout_key",
    ["default", "lb", LTE_DEFAULT_LAYOUT_KEY, LTE_LB_LAYOUT_KEY],
)
def test_layout_cells_are_valid_single_cells(layout_key: str) -> None:
    layout = LAYOUTS[layout_key]
    cells = [
        layout.band_info_cells.channel,
        layout.band_info_cells.bandwidth,
        layout.band_info_cells.rb_size,
        layout.band_info_cells.rb_offset,
        layout.band_info_cells.modulation,
        layout.band_info_cells.dut_ant_position,
        layout.fundamental_frequency_cell,
        inband_level_cell(layout, DUTAxis.X, AntennaPol.V),
    ]

    for order in (2, 3, 4, 5):
        cells.append(harmonic_level_cell(layout, order, DUTAxis.X, AntennaPol.V))
        cells.append(harmonic_frequency_cell(layout, order))

    if layout.bilog_base_row is not None:
        cells.append(bilog_level_cell(layout, DUTAxis.X, AntennaPol.V))

    for cell in cells:
        coordinate_to_tuple(cell)
        assert ":" not in cell


def test_lb_layout_is_independent_from_default_layout() -> None:
    default = LAYOUTS["default"]
    lb = LAYOUTS[LB_LAYOUT_KEY]

    assert default is not lb
    assert default.band_info_cells.channel == "C49"
    assert lb.band_info_cells.channel == "C44"
    assert default.band_info_cells.dut_ant_position == "I49"
    assert lb.band_info_cells.dut_ant_position == "I44"
    assert default.harmonic_base_row == 66
    assert lb.harmonic_base_row == 56


def test_nsa_default_layout_offsets_rows_only() -> None:
    layout = layout_for_group_key_and_generation("uhb_tdd", Generation.NR_NSA)

    assert layout.key == "default_nsa"
    assert layout.band_info_cells.channel == "C7"
    assert layout.fundamental_frequency_cell == "J7"
    assert layout.bilog_base_row == 14
    assert layout.inband_base_row == 19
    assert layout.harmonic_base_row == 24
    assert bilog_level_cell(layout, DUTAxis.X, AntennaPol.V) == "B14"
    assert inband_level_cell(layout, DUTAxis.Z, AntennaPol.H) == "D20"
    assert harmonic_frequency_cell(layout, 2) == "A24"


def test_nsa_lb_layout_offsets_rows_only_and_keeps_bilog_unsupported() -> None:
    layout = layout_for_group_key_and_generation("lb", Generation.NR_NSA)

    assert layout.key == "lb_nsa"
    assert layout.band_info_cells.channel == "C7"
    assert layout.fundamental_frequency_cell == "J7"
    assert layout.bilog_base_row is None
    assert layout.inband_base_row == 14
    assert layout.harmonic_base_row == 19
    assert inband_level_cell(layout, DUTAxis.Z, AntennaPol.H) == "D15"
    assert harmonic_frequency_cell(layout, 2) == "A19"

    with pytest.raises(ValueError, match="Bilog layout is not supported"):
        bilog_level_cell(layout, DUTAxis.X, AntennaPol.V)


def test_every_lte_band_has_lte_band_sheet_name() -> None:
    for band in LTEBand:
        assert sheet_name_for_band(band) == f"LTE_BAND {band.value.removeprefix('B')}"


def test_lte_b34_uses_mhb_layout() -> None:
    group = find_lte_band_group(LTEBand.B34)
    layout = layout_for_group_key_and_generation(group.key, Generation.LTE)

    assert layout.key == LTE_DEFAULT_LAYOUT_KEY
    assert layout.band_info_cells.channel == "B7"
    assert layout.band_info_cells.bandwidth == "C7"
    assert layout.band_info_cells.rb_size == "D7"
    assert layout.band_info_cells.rb_offset == "E7"
    assert layout.band_info_cells.modulation == "F7"
    assert layout.band_info_cells.dut_ant_position == "H7"
    assert layout.fundamental_frequency_cell == "I7"
    assert bilog_level_cell(layout, DUTAxis.X, AntennaPol.V) == "B14"
    assert inband_level_cell(layout, DUTAxis.Z, AntennaPol.H) == "D20"
    assert harmonic_frequency_cell(layout, 2) == "A24"
    assert harmonic_level_cell(layout, 5, DUTAxis.Z, AntennaPol.H) == "D31"


def test_lte_lb_layout_uses_shifted_rows_and_keeps_bilog_unsupported() -> None:
    group = find_lte_band_group(LTEBand.B5)
    layout = layout_for_group_key_and_generation(group.key, Generation.LTE)

    assert layout.key == LTE_LB_LAYOUT_KEY
    assert layout.band_info_cells.channel == "B7"
    assert layout.band_info_cells.bandwidth == "C7"
    assert layout.band_info_cells.rb_size == "D7"
    assert layout.band_info_cells.rb_offset == "E7"
    assert layout.band_info_cells.modulation == "F7"
    assert layout.band_info_cells.dut_ant_position == "H7"
    assert layout.fundamental_frequency_cell == "I7"
    assert layout.bilog_base_row is None
    assert inband_level_cell(layout, DUTAxis.Z, AntennaPol.H) == "D15"
    assert harmonic_frequency_cell(layout, 2) == "A19"
    assert harmonic_level_cell(layout, 5, DUTAxis.Z, AntennaPol.H) == "D26"

    with pytest.raises(ValueError, match="Bilog layout is not supported"):
        bilog_level_cell(layout, DUTAxis.X, AntennaPol.V)
