from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from openpyxl import Workbook, load_workbook

from app.models.enums import (
    AntennaPol,
    DUTAntPosition,
    DUTAxis,
    Modulation,
    NRBand,
    RBAllocation,
    TestChannel as ChannelEnum,
    TestType as MeasurementTestType,
)
from app.models.measurement_result import (
    BilogResult,
    FundamentalResult,
    HarmonicResult,
    InbandResult,
)
from app.models.test_case import TestCase
from app.report.excel_writer import ExcelReportWriter
from app.report import template_map


def _make_case(
    *,
    band: NRBand = NRBand.N78,
    bandwidth: float = 100.0,
    test_type: MeasurementTestType = MeasurementTestType.HARMONIC,
    antenna_pol: AntennaPol = AntennaPol.V,
    dut_axis: DUTAxis = DUTAxis.X,
    dut_ant_position: DUTAntPosition = DUTAntPosition.UPPER,
) -> TestCase:
    return TestCase(
        band=band,
        bandwidth=bandwidth,
        test_type=test_type,
        modulation=Modulation.QPSK,
        rb_allocation=RBAllocation.INNER_FULL,
        test_channel=ChannelEnum.MID,
        antenna_pol=antenna_pol,
        dut_axis=dut_axis,
        dut_ant_position=dut_ant_position,
    )


def _make_workbook(path: Path, *bands: NRBand) -> Path:
    workbook = Workbook()
    default = workbook.active
    workbook.remove(default)
    for band in bands:
        workbook.create_sheet(f"Sub6 {band.value}")
    workbook.save(path)
    return path


def _cell(path: Path, sheet: str, cell: str) -> object:
    workbook = load_workbook(path)
    return workbook[sheet][cell].value


def test_write_fundamental_saves_default_cells_to_template_file(tmp_path: Path) -> None:
    path = _make_workbook(tmp_path / "report.xlsx", NRBand.N78)
    writer = ExcelReportWriter(path)
    case = _make_case()

    assert writer.write_fundamental(
        case,
        FundamentalResult(fundamental_frequency_mhz=3550.25),
    )

    sheet = "Sub6 n78"
    workbook = load_workbook(path)
    worksheet = workbook[sheet]
    assert worksheet["C49"].value == "mid"
    assert worksheet["D49"].value == 100
    assert worksheet["E49"].value == case.rb_size
    assert worksheet["F49"].value == case.rb_offset
    assert worksheet["G49"].value == "QPSK"
    assert worksheet["I49"].value == "Upper"
    assert worksheet["J49"].value == 3550.25
    assert worksheet["A66"].value == 7100.5
    assert worksheet["A68"].value == 10650.75
    assert worksheet["A70"].value == 14201
    assert worksheet["A72"].value == 17751.25


def test_read_fundamental_frequency_returns_none_for_empty_cell(
    tmp_path: Path,
) -> None:
    path = _make_workbook(tmp_path / "report.xlsx", NRBand.N78)
    writer = ExcelReportWriter(path)

    assert writer.read_fundamental_frequency(_make_case()) is None


def test_read_fundamental_frequency_reads_default_layout_cell(
    tmp_path: Path,
) -> None:
    path = _make_workbook(tmp_path / "report.xlsx", NRBand.N78)
    writer = ExcelReportWriter(path)
    writer.workbook["Sub6 n78"]["J49"] = 3550.25

    assert writer.read_fundamental_frequency(_make_case()) == 3550.25


def test_read_fundamental_frequency_reads_lb_layout_cell(tmp_path: Path) -> None:
    path = _make_workbook(tmp_path / "report.xlsx", NRBand.N5)
    writer = ExcelReportWriter(path)
    writer.workbook["Sub6 n5"]["J44"] = 836

    assert (
        writer.read_fundamental_frequency(_make_case(band=NRBand.N5, bandwidth=20.0))
        == 836.0
    )


@pytest.mark.parametrize("value", [True, "3550.25", "=SUM(1, 2)"])
def test_read_fundamental_frequency_rejects_invalid_cell_values(
    tmp_path: Path,
    value: object,
) -> None:
    path = _make_workbook(tmp_path / "report.xlsx", NRBand.N78)
    writer = ExcelReportWriter(path)
    writer.workbook["Sub6 n78"]["J49"] = value

    with pytest.raises(ValueError, match="Invalid fundamental frequency value"):
        writer.read_fundamental_frequency(_make_case())


def test_write_harmonic_saves_default_axis_and_pol_cells(tmp_path: Path) -> None:
    path = _make_workbook(tmp_path / "report.xlsx", NRBand.N78)
    writer = ExcelReportWriter(path)
    case = _make_case(antenna_pol=AntennaPol.H, dut_axis=DUTAxis.Y)

    assert writer.write_harmonic(
        case,
        HarmonicResult(
            harmonic_2nd_peak_level_dbm=-41.0,
            harmonic_3rd_peak_level_dbm=-39.5,
            harmonic_4th_peak_level_dbm=-38.0,
            harmonic_5th_peak_level_dbm=-37.5,
        ),
    )

    sheet = "Sub6 n78"
    assert _cell(path, sheet, "C67") == -41.0
    assert _cell(path, sheet, "C69") == -39.5
    assert _cell(path, sheet, "C71") == -38.0
    assert _cell(path, sheet, "C73") == -37.5


def test_write_fundamental_uses_common_harmonic_frequency_cells_for_pol(
    tmp_path: Path,
) -> None:
    path = _make_workbook(tmp_path / "report.xlsx", NRBand.N78)
    writer = ExcelReportWriter(path)
    case = _make_case(antenna_pol=AntennaPol.H)

    writer.write_fundamental(
        case,
        FundamentalResult(fundamental_frequency_mhz=3550.25),
    )

    workbook = load_workbook(path)
    worksheet = workbook["Sub6 n78"]
    assert worksheet["A66"].value == 7100.5
    assert worksheet["A67"].value is None
    assert worksheet["A68"].value == 10650.75
    assert worksheet["A69"].value is None


def test_write_harmonic_writes_dash_for_missing_levels(tmp_path: Path) -> None:
    path = _make_workbook(tmp_path / "report.xlsx", NRBand.N78)
    writer = ExcelReportWriter(path)
    case = _make_case(antenna_pol=AntennaPol.H, dut_axis=DUTAxis.Y)

    assert writer.write_harmonic(
        case,
        HarmonicResult(
            harmonic_2nd_peak_level_dbm=None,
            harmonic_3rd_peak_level_dbm=-39.5,
            harmonic_4th_peak_level_dbm=None,
            harmonic_5th_peak_level_dbm=-37.5,
        ),
    )

    sheet = "Sub6 n78"
    assert _cell(path, sheet, "C67") == "-"
    assert _cell(path, sheet, "C69") == -39.5
    assert _cell(path, sheet, "C71") == "-"
    assert _cell(path, sheet, "C73") == -37.5


def test_write_fundamental_and_harmonic_use_lb_layout(tmp_path: Path) -> None:
    path = _make_workbook(tmp_path / "report.xlsx", NRBand.N5)
    writer = ExcelReportWriter(path)
    case = _make_case(
        band=NRBand.N5,
        bandwidth=20.0,
        dut_ant_position=DUTAntPosition.LOWER,
    )

    writer.write_fundamental(case, FundamentalResult(fundamental_frequency_mhz=836.5))
    writer.write_harmonic(
        case,
        HarmonicResult(
            harmonic_2nd_peak_level_dbm=-42.0,
            harmonic_3rd_peak_level_dbm=-41.0,
            harmonic_4th_peak_level_dbm=-40.0,
            harmonic_5th_peak_level_dbm=-39.0,
        ),
    )

    workbook = load_workbook(path)
    worksheet = workbook["Sub6 n5"]
    assert worksheet["C44"].value == "mid"
    assert worksheet["D44"].value == 20
    assert worksheet["I44"].value == "Lower"
    assert worksheet["J44"].value == 836.5
    assert worksheet["A56"].value == 1673
    assert worksheet["A58"].value == 2509.5
    assert worksheet["B56"].value == -42.0
    assert worksheet["B62"].value == -39.0


def test_write_inband_and_bilog_default_cells(tmp_path: Path) -> None:
    path = _make_workbook(tmp_path / "report.xlsx", NRBand.N78)
    writer = ExcelReportWriter(path)

    inband_case = _make_case(
        test_type=MeasurementTestType.INBAND,
        antenna_pol=AntennaPol.H,
        dut_axis=DUTAxis.Z,
    )
    bilog_case = _make_case(
        test_type=MeasurementTestType.BILOG,
        antenna_pol=AntennaPol.V,
        dut_axis=DUTAxis.X,
    )

    writer.write_inband(inband_case, InbandResult(inband_peak_level_dbm=-45.5))
    writer.write_bilog(bilog_case, BilogResult(bilog_peak_level_dbm=-38.25))

    sheet = "Sub6 n78"
    assert _cell(path, sheet, "D62") == -45.5
    assert _cell(path, sheet, "B56") == -38.25


def test_write_inband_uses_lb_layout(tmp_path: Path) -> None:
    path = _make_workbook(tmp_path / "report.xlsx", NRBand.N5)
    writer = ExcelReportWriter(path)
    case = _make_case(
        band=NRBand.N5,
        bandwidth=20.0,
        test_type=MeasurementTestType.INBAND,
        antenna_pol=AntennaPol.H,
        dut_axis=DUTAxis.Z,
    )

    writer.write_inband(case, InbandResult(inband_peak_level_dbm=-47.0))

    assert _cell(path, "Sub6 n5", "D52") == -47.0


def test_band_info_is_written_once_per_band(tmp_path: Path) -> None:
    path = _make_workbook(tmp_path / "report.xlsx", NRBand.N78)
    writer = ExcelReportWriter(path)
    first_case = _make_case(test_type=MeasurementTestType.INBAND)
    second_case = _make_case(
        bandwidth=90.0,
        test_type=MeasurementTestType.INBAND,
        antenna_pol=AntennaPol.H,
    )

    writer.write_inband(first_case, InbandResult(inband_peak_level_dbm=-45.0))
    writer.write_inband(second_case, InbandResult(inband_peak_level_dbm=-44.0))

    assert _cell(path, "Sub6 n78", "D49") == 100


def test_write_fails_when_sheet_is_missing(tmp_path: Path) -> None:
    path = _make_workbook(tmp_path / "report.xlsx", NRBand.N77)
    writer = ExcelReportWriter(path)

    with pytest.raises(ValueError, match="Workbook has no sheet"):
        writer.write_inband(
            _make_case(test_type=MeasurementTestType.INBAND),
            InbandResult(inband_peak_level_dbm=-45.0),
        )


def test_write_fails_for_invalid_cell_coordinate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = _make_workbook(tmp_path / "report.xlsx", NRBand.N78)
    writer = ExcelReportWriter(path)
    layout = template_map.LAYOUTS["default"]
    monkeypatch.setitem(
        template_map.LAYOUTS,
        "default",
        replace(layout, fundamental_frequency_cell="A1:B2"),
    )

    with pytest.raises(ValueError, match="Invalid single cell coordinate"):
        writer.write_fundamental(
            _make_case(),
            FundamentalResult(fundamental_frequency_mhz=3550.25),
        )


def test_write_inband_fails_when_required_result_value_is_missing(tmp_path: Path) -> None:
    path = _make_workbook(tmp_path / "report.xlsx", NRBand.N78)
    writer = ExcelReportWriter(path)

    with pytest.raises(ValueError, match="inband_peak_level_dbm"):
        writer.write_inband(
            _make_case(test_type=MeasurementTestType.INBAND),
            InbandResult(inband_peak_level_dbm=None),
        )


def test_write_falls_back_to_open_excel_workbook_when_file_is_locked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = _make_workbook(tmp_path / "report.xlsx", NRBand.N78)
    writer = ExcelReportWriter(path)
    fallback_cells: list[tuple[str, str, object]] = []

    def raise_permission_error(_: Path) -> None:
        raise PermissionError("locked")

    def save_open_workbook() -> None:
        fallback_cells.extend(writer._pending_cells)
        writer._pending_cells.clear()

    monkeypatch.setattr(writer.workbook, "save", raise_permission_error)
    monkeypatch.setattr(writer, "_save_open_workbook_with_excel", save_open_workbook)

    assert writer.write_inband(
        _make_case(
            test_type=MeasurementTestType.INBAND,
            antenna_pol=AntennaPol.H,
            dut_axis=DUTAxis.Z,
        ),
        InbandResult(inband_peak_level_dbm=-45.5),
    )

    assert ("Sub6 n78", "D62", -45.5) in fallback_cells
    assert writer._pending_cells == []
