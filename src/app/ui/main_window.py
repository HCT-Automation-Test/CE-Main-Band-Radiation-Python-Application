"""MainWindow — 앱 메인 윈도우."""
from __future__ import annotations

import logging

from PySide6.QtWidgets import QMainWindow

# 먼저 `uv run pyside6-uic resources/main_window.ui -o src/app/ui/generated/main_window_ui.py`
# 실행해야 아래 임포트가 성공한다.
from app.ui.generated.main_window_ui import Ui_MainWindow

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """최상위 메인 윈도우. 생성된 Ui_MainWindow를 컴포지션으로 보유."""

    def __init__(self, parent: QMainWindow | None = None) -> None:
        super().__init__(parent)
        self._ui = Ui_MainWindow()
        self._ui.setupUi(self)
        self._connect_signals()

    def _connect_signals(self) -> None:
        """시그널/슬롯 연결 허브. TODO(spec): 도크/패널 결선."""
        return None
