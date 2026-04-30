"""RF Filter Box 서브 패널."""
from __future__ import annotations

from PySide6.QtWidgets import QWidget


class RFFilterBoxPanel(QWidget):
    """추후 개발될 RF Filter Box 화면."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # TODO(spec): RF Filter Box 경로 선택 UI 배치
