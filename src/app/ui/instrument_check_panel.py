"""Instrument Check 서브 패널."""
from __future__ import annotations

from PySide6.QtWidgets import QWidget


class InstrumentCheckPanel(QWidget):
    """MT8000A/FSV40/Switch Box/CO3000 연결 상태 표시."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # TODO(spec): 장비별 상태 표시와 연결 점검 UI 배치
