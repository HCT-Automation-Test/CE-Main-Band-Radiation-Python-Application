"""앱 로그 출력 패널."""
from __future__ import annotations

from PySide6.QtWidgets import QWidget


class LogPanel(QWidget):
    """logging → QPlainTextEdit 미러."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # TODO(spec): logging handler 부착 및 QPlainTextEdit 배치
