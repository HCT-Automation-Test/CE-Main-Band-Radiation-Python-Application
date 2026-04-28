"""결과 Excel 리포트 작성기."""
from __future__ import annotations

from pathlib import Path

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
        worksheet[frequency_cell] = frequency_mhz
        for order in (2, 3, 4, 5):
            worksheet[
                harmonic_frequency_cell(layout, order, test_case.antenna_pol)
            ] = frequency_mhz * order

        self._save()
        return True

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
            2: _require_value(
                result.harmonic_2nd_peak_level_dbm,
                "harmonic_2nd_peak_level_dbm",
            ),
            3: _require_value(
                result.harmonic_3rd_peak_level_dbm,
                "harmonic_3rd_peak_level_dbm",
            ),
            4: _require_value(
                result.harmonic_4th_peak_level_dbm,
                "harmonic_4th_peak_level_dbm",
            ),
            5: _require_value(
                result.harmonic_5th_peak_level_dbm,
                "harmonic_5th_peak_level_dbm",
            ),
        }

        for order, level_dbm in levels_by_order.items():
            worksheet[
                harmonic_level_cell(
                    layout,
                    order,
                    test_case.dut_axis,
                    test_case.antenna_pol,
                )
            ] = level_dbm

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
        worksheet[
            inband_level_cell(layout, test_case.dut_axis, test_case.antenna_pol)
        ] = level_dbm
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
        worksheet[
            bilog_level_cell(layout, test_case.dut_axis, test_case.antenna_pol)
        ] = level_dbm
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

        worksheet[validate_single_cell(cells.channel)] = test_case.test_channel.value
        worksheet[validate_single_cell(cells.bandwidth)] = test_case.bandwidth
        worksheet[validate_single_cell(cells.rb_size)] = test_case.rb_size
        worksheet[validate_single_cell(cells.rb_offset)] = test_case.rb_offset
        worksheet[validate_single_cell(cells.modulation)] = test_case.modulation.value
        worksheet[validate_single_cell(cells.dut_ant_position)] = (
            test_case.dut_ant_position.value
        )
        self._written_band_info.add(worksheet.title)

    def _save(self) -> None:
        self.workbook.save(self.template_path)


def _require_value(value: float | None, field_name: str) -> float:
    if value is None:
        raise ValueError(f"Missing required report value: {field_name}")
    return value
