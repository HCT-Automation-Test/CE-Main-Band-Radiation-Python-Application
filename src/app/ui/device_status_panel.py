"""장비 상태 표시 패널."""
from __future__ import annotations

from PySide6.QtWidgets import QWidget


class DeviceStatusPanel(QWidget):
    """MT8000A/FSV40/Switch Box/CO3000 연결 상태 표시."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # TODO(spec): 장비별 인디케이터 위젯 배치
