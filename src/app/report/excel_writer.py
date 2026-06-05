"""결과 Excel 리포트 작성기."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet

from app.models.band_group import find_band_group
from app.models.measurement_result import (
    BilogResult,
    FundamentalResult,
    HarmonicResult,
    InbandResult,
    MeasurementResult,
)
from app.models.test_case import TestCase
from app.report.template_map import (
    BandInfoCells,
    ReportLayout,
    bilog_level_cell,
    harmonic_frequency_cell,
    harmonic_level_cell,
    inband_level_cell,
    layout_for_group_key,
    sheet_name_for_band,
    validate_single_cell,
)


class ExcelReportWriter:
    """Excel 템플릿 파일에 측정 결과를 즉시 기록한다."""

    def __init__(self, template_path: Path) -> None:
        self.template_path = Path(template_path)
        self.workbook = load_workbook(self.template_path)
        self._written_band_info: set[str] = set()
        self._pending_cells: list[tuple[str, str, Any]] = []

    def write_fundamental(
        self,
        test_case: TestCase,
        result: FundamentalResult,
    ) -> bool:
        """기본파 및 harmonic frequency를 작성한다."""

        frequency_mhz = _require_value(
            result.fundamental_frequency_mhz,
            "fundamental_frequency_mhz",
        )
        worksheet = self._worksheet_for_case(test_case)
        layout = self._layout_for_case(test_case)
        self._write_band_info_once(worksheet, layout.band_info_cells, test_case)

        frequency_cell = validate_single_cell(layout.fundamental_frequency_cell)
        self._set_cell(worksheet, frequency_cell, frequency_mhz)
        for order in (2, 3, 4, 5):
            self._set_cell(
                worksheet,
                harmonic_frequency_cell(layout, order),
                frequency_mhz * order,
            )

        self._save()
        return True

    def read_fundamental_frequency(self, test_case: TestCase) -> float | None:
        """현재 Band sheet에 기록된 fundamental frequency를 읽는다."""

        worksheet = self._worksheet_for_case(test_case)
        layout = self._layout_for_case(test_case)
        frequency_cell = validate_single_cell(layout.fundamental_frequency_cell)
        value = worksheet[frequency_cell].value
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValueError(
                f"Invalid fundamental frequency value at "
                f"{worksheet.title}!{frequency_cell}: {value!r}"
            )
        return float(value)

    def write_harmonic(
        self,
        test_case: TestCase,
        result: HarmonicResult,
    ) -> bool:
        """Harmonic level 결과를 작성한다."""

        worksheet = self._worksheet_for_case(test_case)
        layout = self._layout_for_case(test_case)
        self._write_band_info_once(worksheet, layout.band_info_cells, test_case)

        levels_by_order = {
            2: _harmonic_level_value(result.harmonic_2nd_peak_level_dbm),
            3: _harmonic_level_value(result.harmonic_3rd_peak_level_dbm),
            4: _harmonic_level_value(result.harmonic_4th_peak_level_dbm),
            5: _harmonic_level_value(result.harmonic_5th_peak_level_dbm),
        }

        for order, level_dbm in levels_by_order.items():
            self._set_cell(
                worksheet,
                harmonic_level_cell(
                    layout,
                    order,
                    test_case.dut_axis,
                    test_case.antenna_pol,
                ),
                level_dbm,
            )

        self._save()
        return True

    def write_inband(
        self,
        test_case: TestCase,
        result: InbandResult,
    ) -> bool:
        """In-band peak level 결과를 작성한다."""

        level_dbm = _require_value(
            result.inband_peak_level_dbm,
            "inband_peak_level_dbm",
        )
        worksheet = self._worksheet_for_case(test_case)
        layout = self._layout_for_case(test_case)
        self._write_band_info_once(worksheet, layout.band_info_cells, test_case)
        self._set_cell(
            worksheet,
            inband_level_cell(layout, test_case.dut_axis, test_case.antenna_pol),
            level_dbm,
        )
        self._save()
        return True

    def write_bilog(
        self,
        test_case: TestCase,
        result: BilogResult,
    ) -> bool:
        """Bilog peak level 결과를 작성한다."""

        level_dbm = _require_value(
            result.bilog_peak_level_dbm,
            "bilog_peak_level_dbm",
        )
        worksheet = self._worksheet_for_case(test_case)
        layout = self._layout_for_case(test_case)
        self._write_band_info_once(worksheet, layout.band_info_cells, test_case)
        self._set_cell(
            worksheet,
            bilog_level_cell(layout, test_case.dut_axis, test_case.antenna_pol),
            level_dbm,
        )
        self._save()
        return True

    def write(
        self,
        results: list[MeasurementResult],
        output_path: Path,
    ) -> Path:
        """이전 batch API는 더 이상 지원하지 않는다."""

        raise NotImplementedError(
            "Use write_fundamental/write_harmonic/write_inband/write_bilog"
        )

    def _worksheet_for_case(self, test_case: TestCase) -> Worksheet:
        sheet_name = sheet_name_for_band(test_case.band)
        if sheet_name not in self.workbook.sheetnames:
            raise ValueError(
                f"Workbook has no sheet for band {test_case.band.value}: {sheet_name}"
            )
        return self.workbook[sheet_name]

    def _layout_for_case(self, test_case: TestCase) -> ReportLayout:
        group = find_band_group(test_case.band)
        return layout_for_group_key(group.key)

    def _write_band_info_once(
        self,
        worksheet: Worksheet,
        cells: BandInfoCells,
        test_case: TestCase,
    ) -> None:
        if worksheet.title in self._written_band_info:
            return

        self._set_cell(
            worksheet,
            validate_single_cell(cells.channel),
            test_case.test_channel.value,
        )
        self._set_cell(
            worksheet,
            validate_single_cell(cells.bandwidth),
            test_case.bandwidth,
        )
        self._set_cell(worksheet, validate_single_cell(cells.rb_size), test_case.rb_size)
        self._set_cell(
            worksheet,
            validate_single_cell(cells.rb_offset),
            test_case.rb_offset,
        )
        self._set_cell(
            worksheet,
            validate_single_cell(cells.modulation),
            test_case.modulation.value,
        )
        self._set_cell(
            worksheet,
            validate_single_cell(cells.dut_ant_position),
            test_case.dut_ant_position.value,
        )
        self._written_band_info.add(worksheet.title)

    def _set_cell(self, worksheet: Worksheet, cell: str, value: Any) -> None:
        worksheet[cell] = value
        self._pending_cells.append((worksheet.title, cell, value))

    def _save(self) -> None:
        try:
            self.workbook.save(self.template_path)
        except PermissionError:
            self._save_open_workbook_with_excel()
        else:
            self._pending_cells.clear()

    def _save_open_workbook_with_excel(self) -> None:
        if not self._pending_cells:
            return

        try:
            import win32com.client
        except ImportError as exc:
            raise PermissionError(
                f"Excel report file is open and cannot be saved: {self.template_path}"
            ) from exc

        try:
            excel = win32com.client.GetActiveObject("Excel.Application")
        except Exception as exc:
            raise PermissionError(
                f"Excel report file is locked and Excel is not available: "
                f"{self.template_path}"
            ) from exc
        workbook = _find_open_excel_workbook(excel, self.template_path)
        if workbook is None:
            raise PermissionError(
                f"Excel report file is locked but no open Excel workbook was found: "
                f"{self.template_path}"
            )

        try:
            for sheet_name, cell, value in self._pending_cells:
                workbook.Worksheets(sheet_name).Range(cell).Value = value
            workbook.Save()
        except Exception as exc:
            raise PermissionError(
                f"Excel report file is open but could not be updated through Excel: "
                f"{self.template_path}"
            ) from exc
        self._pending_cells.clear()


def _find_open_excel_workbook(excel: Any, template_path: Path) -> Any | None:
    target = _normalized_path(template_path)
    for workbook in excel.Workbooks:
        if _normalized_path(Path(workbook.FullName)) == target:
            return workbook
    return None


def _normalized_path(path: Path) -> str:
    return str(path.resolve()).casefold()


def _require_value(value: float | None, field_name: str) -> float:
    if value is None:
        raise ValueError(f"Missing required report value: {field_name}")
    return value


def _harmonic_level_value(value: float | None) -> float | str:
    if value is None:
        return "-"
    return value
