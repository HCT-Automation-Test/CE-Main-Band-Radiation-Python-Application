"""시퀀스 실행 모니터링 패널."""
from __future__ import annotations

from PySide6.QtWidgets import QWidget


class ExecutionPanel(QWidget):
    """현재 State/진행률/턴테이블/시작/중단 버튼."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # TODO(spec): Runner.events 신호 구독 및 위젯 배치
