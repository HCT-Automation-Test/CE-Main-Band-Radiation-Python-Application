"""결과 Excel 리포트 작성기."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from app.models.measurement_result import MeasurementResult


class ExcelReportWriter:
    """템플릿 복사 → mapping에 따라 셀 채움 → 스크린샷 첨부 → 저장."""

    def __init__(self, template_path: Path, mapping_path: Path) -> None:
        self.template_path = Path(template_path)
        self.mapping_path = Path(mapping_path)
        # TODO(spec): mapping 로드 시점(lazy vs eager) 결정

    def write(self, results: Iterable[MeasurementResult], output_path: Path) -> Path:
        """결과를 템플릿에 채워 새 xlsx로 저장하고 경로 반환."""
        # TODO(spec): openpyxl load_workbook → 셀 기록 → add_image → save
        raise NotImplementedError("spec TODO")
