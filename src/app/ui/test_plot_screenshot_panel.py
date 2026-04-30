"""Test Plot Screenshot 서브 패널."""
from __future__ import annotations

from PySide6.QtWidgets import QWidget


class TestPlotScreenshotPanel(QWidget):
    """SA 스크린샷 저장 이벤트를 표시할 화면."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # TODO(spec): QLabel/QGraphicsView 배치와 screenshot_saved 시그널 구독
