"""SA 스크린샷 뷰어."""
from __future__ import annotations

from PySide6.QtWidgets import QWidget


class ScreenshotViewer(QWidget):
    """screenshot_saved 시그널 구독 → 즉시 갱신."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # TODO(spec): QLabel/QGraphicsView 배치
