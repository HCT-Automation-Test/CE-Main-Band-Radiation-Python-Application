"""Excel 템플릿 셀 매핑 상수."""
from __future__ import annotations

from dataclasses import dataclass, replace

from openpyxl.utils.cell import coordinate_to_tuple, get_column_letter

from app.models.enums import AntennaPol, DUTAxis, Generation, LTEBand, NRBand

DEFAULT_LAYOUT_KEY = "default"
LB_LAYOUT_KEY = "lb"
LTE_DEFAULT_LAYOUT_KEY = "lte_default"
LTE_LB_LAYOUT_KEY = "lte_lb"
NSA_LB_ROW_OFFSET = -37
NSA_DEFAULT_ROW_OFFSET = -42
ALLOWED_BAND_GROUP_KEYS: frozenset[str] = frozenset(
    {LB_LAYOUT_KEY, "mhb_fdd", "mhb_tdd", "uhb_tdd"}
)

AXIS_COLUMNS: dict[DUTAxis, str] = {
    DUTAxis.X: "B",
    DUTAxis.Y: "C",
    DUTAxis.Z: "D",
}

POL_ROW_OFFSETS: dict[AntennaPol, int] = {
    AntennaPol.V: 0,
    AntennaPol.H: 1,
}

HARMONIC_ROW_OFFSETS: dict[int, int] = {
    2: 0,
    3: 2,
    4: 4,
    5: 6,
}

SHEET_BY_BAND: dict[NRBand | LTEBand, str] = {
    **{band: f"Sub6 {band.value}" for band in NRBand},
    **{band: f"LTE_BAND {band.value.removeprefix('B')}" for band in LTEBand},
}


@dataclass(frozen=True)
class BandInfoCells:
    """Band 공통 시험 정보 셀."""

    band: str
    anchor_band: str | None
    channel: str
    bandwidth: str
    rb_size: str
    rb_offset: str
    modulation: str
    scs: str
    dut_ant_position: str


@dataclass(frozen=True)
class ReportLayout:
    """Band group별 Excel layout."""

    key: str
    band_info_cells: BandInfoCells
    fundamental_frequency_cell: str
    harmonic_base_row: int
    inband_base_row: int
    bilog_base_row: int | None


LAYOUTS: dict[str, ReportLayout] = {
    DEFAULT_LAYOUT_KEY: ReportLayout(
        key=DEFAULT_LAYOUT_KEY,
        band_info_cells=BandInfoCells(
            band="A49",
            anchor_band="B49",
            channel="C49",
            bandwidth="D49",
            rb_size="E49",
            rb_offset="F49",
            modulation="G49",
            scs="H49",
            dut_ant_position="I49",
        ),
        fundamental_frequency_cell="J49",
        harmonic_base_row=66,
        inband_base_row=61,
        bilog_base_row=56,
    ),
    LB_LAYOUT_KEY: ReportLayout(
        key=LB_LAYOUT_KEY,
        band_info_cells=BandInfoCells(
            band="A44",
            anchor_band="B44",
            channel="C44",
            bandwidth="D44",
            rb_size="E44",
            rb_offset="F44",
            modulation="G44",
            scs="H44",
            dut_ant_position="I44",
        ),
        fundamental_frequency_cell="J44",
        harmonic_base_row=56,
        inband_base_row=51,
        bilog_base_row=None,
    ),
    LTE_DEFAULT_LAYOUT_KEY: ReportLayout(
        key=LTE_DEFAULT_LAYOUT_KEY,
        band_info_cells=BandInfoCells(
            band="A7",
            anchor_band=None,
            channel="B7",
            bandwidth="C7",
            rb_size="D7",
            rb_offset="E7",
            modulation="F7",
            scs="G7",
            dut_ant_position="H7",
        ),
        fundamental_frequency_cell="I7",
        harmonic_base_row=24,
        inband_base_row=19,
        bilog_base_row=14,
    ),
    LTE_LB_LAYOUT_KEY: ReportLayout(
        key=LTE_LB_LAYOUT_KEY,
        band_info_cells=BandInfoCells(
            band="A7",
            anchor_band=None,
            channel="B7",
            bandwidth="C7",
            rb_size="D7",
            rb_offset="E7",
            modulation="F7",
            scs="G7",
            dut_ant_position="H7",
        ),
        fundamental_frequency_cell="I7",
        harmonic_base_row=19,
        inband_base_row=14,
        bilog_base_row=None,
    ),
}


def sheet_name_for_band(band: NRBand | LTEBand) -> str:
    """Band에 대응하는 Excel 시트명을 반환한다."""

    try:
        return SHEET_BY_BAND[band]
    except KeyError as exc:
        raise ValueError(f"No sheet mapping for band: {band!r}") from exc


def layout_key_for_group(group_key: str) -> str:
    """Band group key를 Excel layout key로 변환한다."""

    if group_key == LB_LAYOUT_KEY:
        return LB_LAYOUT_KEY
    return DEFAULT_LAYOUT_KEY


def layout_for_group_key(group_key: str) -> ReportLayout:
    """Band group key에 대응하는 layout을 반환한다."""

    return layout_for_group_key_and_generation(group_key, Generation.NR_SA)


def layout_for_group_key_and_generation(
    group_key: str,
    generation: Generation,
) -> ReportLayout:
    """Band group/generation에 대응하는 layout을 반환한다."""

    if group_key not in ALLOWED_BAND_GROUP_KEYS:
        raise ValueError(f"Unknown band group key: {group_key!r}")
    if generation is Generation.LTE:
        layout_key = (
            LTE_LB_LAYOUT_KEY if group_key == LB_LAYOUT_KEY else LTE_DEFAULT_LAYOUT_KEY
        )
        return LAYOUTS[layout_key]

    layout_key = layout_key_for_group(group_key)
    try:
        layout = LAYOUTS[layout_key]
    except KeyError as exc:
        raise ValueError(f"No report layout for band group: {group_key!r}") from exc
    if generation is Generation.NR_NSA:
        return offset_layout_rows(
            layout,
            NSA_LB_ROW_OFFSET if layout.key == LB_LAYOUT_KEY else NSA_DEFAULT_ROW_OFFSET,
            f"{layout.key}_nsa",
        )
    return layout


def offset_layout_rows(
    layout: ReportLayout,
    row_offset: int,
    key: str,
) -> ReportLayout:
    """Layout의 행 위치만 row_offset만큼 이동한다."""

    return replace(
        layout,
        key=key,
        band_info_cells=BandInfoCells(
            band=offset_cell_row(layout.band_info_cells.band, row_offset),
            anchor_band=_offset_optional_cell_row(
                layout.band_info_cells.anchor_band,
                row_offset,
            ),
            channel=offset_cell_row(layout.band_info_cells.channel, row_offset),
            bandwidth=offset_cell_row(layout.band_info_cells.bandwidth, row_offset),
            rb_size=offset_cell_row(layout.band_info_cells.rb_size, row_offset),
            rb_offset=offset_cell_row(layout.band_info_cells.rb_offset, row_offset),
            modulation=offset_cell_row(layout.band_info_cells.modulation, row_offset),
            scs=offset_cell_row(layout.band_info_cells.scs, row_offset),
            dut_ant_position=offset_cell_row(
                layout.band_info_cells.dut_ant_position,
                row_offset,
            ),
        ),
        fundamental_frequency_cell=offset_cell_row(
            layout.fundamental_frequency_cell,
            row_offset,
        ),
        harmonic_base_row=layout.harmonic_base_row + row_offset,
        inband_base_row=layout.inband_base_row + row_offset,
        bilog_base_row=_offset_optional_row(layout.bilog_base_row, row_offset),
    )


def offset_cell_row(cell: str, row_offset: int) -> str:
    """셀 좌표의 행 위치만 row_offset만큼 이동한다."""

    row, column = coordinate_to_tuple(validate_single_cell(cell))
    return validate_single_cell(f"{get_column_letter(column)}{row + row_offset}")


def _offset_optional_row(row: int | None, row_offset: int) -> int | None:
    if row is None:
        return None
    return row + row_offset


def _offset_optional_cell_row(cell: str | None, row_offset: int) -> str | None:
    if cell is None:
        return None
    return offset_cell_row(cell, row_offset)


def axis_pol_cell(base_row: int, axis: DUTAxis, antenna_pol: AntennaPol) -> str:
    """Axis/Pol 규칙으로 셀 좌표를 만든다."""

    column = AXIS_COLUMNS[axis]
    row = base_row + POL_ROW_OFFSETS[antenna_pol]
    return validate_single_cell(f"{column}{row}")


def harmonic_level_cell(
    layout: ReportLayout,
    order: int,
    axis: DUTAxis,
    antenna_pol: AntennaPol,
) -> str:
    """Harmonic level 셀 좌표를 반환한다."""

    base_row = layout.harmonic_base_row + HARMONIC_ROW_OFFSETS[order]
    return axis_pol_cell(base_row, axis, antenna_pol)


def harmonic_frequency_cell(
    layout: ReportLayout,
    order: int,
) -> str:
    """Harmonic frequency 셀 좌표를 반환한다."""

    row = layout.harmonic_base_row + HARMONIC_ROW_OFFSETS[order]
    return validate_single_cell(f"A{row}")


def inband_level_cell(
    layout: ReportLayout,
    axis: DUTAxis,
    antenna_pol: AntennaPol,
) -> str:
    """In-band peak level 셀 좌표를 반환한다."""

    return axis_pol_cell(layout.inband_base_row, axis, antenna_pol)


def bilog_level_cell(
    layout: ReportLayout,
    axis: DUTAxis,
    antenna_pol: AntennaPol,
) -> str:
    """Bilog peak level 셀 좌표를 반환한다."""

    if layout.bilog_base_row is None:
        raise ValueError(f"Bilog layout is not supported for layout: {layout.key}")
    return axis_pol_cell(layout.bilog_base_row, axis, antenna_pol)


def validate_single_cell(cell: str) -> str:
    """openpyxl 단일 셀 좌표인지 검증한다."""

    if ":" in cell:
        raise ValueError(f"Invalid single cell coordinate: {cell!r}")
    try:
        coordinate_to_tuple(cell)
    except Exception as exc:
        raise ValueError(f"Invalid single cell coordinate: {cell!r}") from exc
    return cell
