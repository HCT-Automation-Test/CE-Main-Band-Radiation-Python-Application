from __future__ import annotations

import pytest
from openpyxl.utils.cell import coordinate_to_tuple

from app.models.band_group import BAND_GROUPS
from app.models.enums import AntennaPol, DUTAxis, NRBand
from app.report.template_map import (
    ALLOWED_BAND_GROUP_KEYS,
    LAYOUTS,
    LB_LAYOUT_KEY,
    bilog_level_cell,
    harmonic_frequency_cell,
    harmonic_level_cell,
    inband_level_cell,
    sheet_name_for_band,
)


def test_every_nr_band_has_sub6_sheet_name() -> None:
    for band in NRBand:
        assert sheet_name_for_band(band) == f"Sub6 {band.value}"


def test_band_group_keys_are_allowed() -> None:
    assert {group.key for group in BAND_GROUPS} == ALLOWED_BAND_GROUP_KEYS


@pytest.mark.parametrize("layout_key", ["default", "lb"])
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
        cells.append(harmonic_frequency_cell(layout, order, AntennaPol.V))

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
