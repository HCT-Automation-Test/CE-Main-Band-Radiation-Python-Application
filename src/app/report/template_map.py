"""Excel 템플릿 셀 매핑 상수."""
from __future__ import annotations

from dataclasses import dataclass

from openpyxl.utils.cell import coordinate_to_tuple

from app.models.enums import AntennaPol, DUTAxis, NRBand

DEFAULT_LAYOUT_KEY = "default"
LB_LAYOUT_KEY = "lb"
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

SHEET_BY_BAND: dict[NRBand, str] = {
    band: f"Sub6 {band.value}" for band in NRBand
}


@dataclass(frozen=True)
class BandInfoCells:
    """Band 공통 시험 정보 셀."""

    channel: str
    bandwidth: str
    rb_size: str
    rb_offset: str
    modulation: str


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
            channel="C49",
            bandwidth="D49",
            rb_size="E49",
            rb_offset="F49",
            modulation="G49",
        ),
        fundamental_frequency_cell="J49",
        harmonic_base_row=66,
        inband_base_row=61,
        bilog_base_row=56,
    ),
    LB_LAYOUT_KEY: ReportLayout(
        key=LB_LAYOUT_KEY,
        band_info_cells=BandInfoCells(
            channel="C44",
            bandwidth="D44",
            rb_size="E44",
            rb_offset="F44",
            modulation="G44",
        ),
        fundamental_frequency_cell="J44",
        harmonic_base_row=56,
        inband_base_row=51,
        bilog_base_row=None,
    ),
}


def sheet_name_for_band(band: NRBand) -> str:
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

    if group_key not in ALLOWED_BAND_GROUP_KEYS:
        raise ValueError(f"Unknown band group key: {group_key!r}")
    layout_key = layout_key_for_group(group_key)
    try:
        return LAYOUTS[layout_key]
    except KeyError as exc:
        raise ValueError(f"No report layout for band group: {group_key!r}") from exc


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
    antenna_pol: AntennaPol,
) -> str:
    """Harmonic frequency 셀 좌표를 반환한다."""

    row = layout.harmonic_base_row + HARMONIC_ROW_OFFSETS[order]
    row += POL_ROW_OFFSETS[antenna_pol]
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
