"""Test Case 편집 패널."""
from __future__ import annotations

from PySide6.QtWidgets import QWidget


class TestCaseEditor(QWidget):
    """CSV TC 로드/편집/저장 UI."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # TODO(spec): QTableView + QAbstractTableModel 연결, Range 확장 버튼
