"""Runner/FSM에서 UI로 보낼 이벤트 시그널 정의."""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class RunnerEvents(QObject):
    """시퀀스 실행 중 발생하는 이벤트의 Qt 시그널 묶음."""

    tc_started = Signal(int)                # index
    tc_finished = Signal(int)               # index
    current_case_changed = Signal(object)   # TestCase
    spectrum_analyzer_info_changed = Signal(object)  # dict
    state_changed = Signal(str)             # state name
    progress = Signal(int)                  # percent
    screenshot_saved = Signal(str)          # path
    error = Signal(str)                     # message
    user_action_required = Signal(str)      # reason

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
