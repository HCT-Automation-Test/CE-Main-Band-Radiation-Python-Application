"""FSM measurement states에서 호출하는 report writer."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from app.models.measurement_result import (
    BilogResult,
    FundamentalResult,
    HarmonicResult,
    InbandResult,
)
from app.models.test_case import TestCase
from app.report.excel_writer import ExcelReportWriter
from app.report.screenshot_store import (
    finalize_fundamental_screenshot,
    finalize_sa_screenshot,
)


class ReportWriter:
    """Excel write와 screenshot 저장을 함께 수행하는 report writer."""

    def __init__(
        self,
        excel_writer: ExcelReportWriter,
        screenshot_root_dir: Path,
        model_name: str,
        events: Any | None = None,
    ) -> None:
        self.excel_writer = excel_writer
        self.screenshot_root_dir = Path(screenshot_root_dir)
        self.model_name = model_name
        self.events = events

    def write_fundamental(
        self,
        test_case: TestCase,
        result: FundamentalResult,
    ) -> bool:
        """Fundamental 결과를 Excel에 쓰고 screenshot을 최종 저장한다."""

        if not self.excel_writer.write_fundamental(test_case, result):
            return False

        finalize_fundamental_screenshot(
            source_path=_require_screenshot_path(result.screenshot_path),
            root_dir=self.screenshot_root_dir,
            model_name=self.model_name,
            test_case=test_case,
            events=self.events,
        )
        return True

    def read_fundamental_frequency(self, test_case: TestCase) -> float | None:
        """Excel에 이미 기록된 Fundamental frequency를 읽는다."""

        return self.excel_writer.read_fundamental_frequency(test_case)

    def write_harmonic(
        self,
        test_case: TestCase,
        result: HarmonicResult,
    ) -> bool:
        """Harmonic 결과를 Excel에 쓰고 screenshot을 최종 저장한다."""

        if not self.excel_writer.write_harmonic(test_case, result):
            return False

        self._finalize_sa_screenshot(test_case, result.screenshot_path)
        return True

    def write_inband(
        self,
        test_case: TestCase,
        result: InbandResult,
    ) -> bool:
        """In-Band 결과를 Excel에 쓰고 screenshot을 최종 저장한다."""

        if not self.excel_writer.write_inband(test_case, result):
            return False

        self._finalize_sa_screenshot(test_case, result.screenshot_path)
        return True

    def write_bilog(
        self,
        test_case: TestCase,
        result: BilogResult,
    ) -> bool:
        """Bilog 결과를 Excel에 쓰고 screenshot을 최종 저장한다."""

        if not self.excel_writer.write_bilog(test_case, result):
            return False

        self._finalize_sa_screenshot(test_case, result.screenshot_path)
        return True

    def _finalize_sa_screenshot(
        self,
        test_case: TestCase,
        screenshot_path: Path | None,
    ) -> None:
        finalize_sa_screenshot(
            source_path=_require_screenshot_path(screenshot_path),
            root_dir=self.screenshot_root_dir,
            model_name=self.model_name,
            test_case=test_case,
            events=self.events,
        )


def _require_screenshot_path(screenshot_path: Path | None) -> Path:
    if screenshot_path is None:
        raise ValueError("screenshot_path is required")
    return screenshot_path
