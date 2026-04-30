"""Test Manager 서브 패널."""
from __future__ import annotations

from PySide6.QtWidgets import QWidget


class TestManagerPanel(QWidget):
    """테스트 케이스 생성, 실행, 로그 출력의 중심 패널."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # TODO(spec): TC 편집, 실행 제어, 로그 출력, NR 선택 팝업 연결
