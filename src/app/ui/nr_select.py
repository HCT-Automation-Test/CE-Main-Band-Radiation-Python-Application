"""NR Test Case 선택 팝업."""
from __future__ import annotations

from PySide6.QtWidgets import QDialog, QWidget


class NRSelectDialog(QDialog):
    """Test Manager에서 사용할 NR Test Case 선택 팝업."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("NR Select")
        # TODO(spec): NR Test Case 선택 항목과 확인/취소 버튼 배치
