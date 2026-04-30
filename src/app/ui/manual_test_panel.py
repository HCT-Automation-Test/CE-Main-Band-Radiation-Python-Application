"""Manual Test 서브 패널."""
from __future__ import annotations

from PySide6.QtWidgets import QWidget


class ManualTestPanel(QWidget):
    """추후 개발될 Manual Test 화면."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # TODO(spec): 수동 시험 제어 UI 배치
