"""MainWindow — 앱 메인 윈도우."""
from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QWidget,
)

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
        self._setup_session_inputs()
        self._connect_signals()

    @property
    def model_name(self) -> str:
        """UI에 입력된 모델명을 반환한다."""

        return self._model_name_edit.text().strip()

    @property
    def screenshot_root_dir(self) -> Path | None:
        """UI에서 선택한 스크린샷 루트 디렉터리를 반환한다."""

        value = self._screenshot_root_edit.text().strip()
        if not value:
            return None
        return Path(value)

    def _setup_session_inputs(self) -> None:
        """생성 UI 바깥에서 세션 메타데이터 입력 위젯을 추가한다."""

        container = QWidget(self)
        layout = QHBoxLayout(container)

        self._model_name_edit = QLineEdit(container)
        self._model_name_edit.setObjectName("modelNameEdit")

        self._screenshot_root_edit = QLineEdit(container)
        self._screenshot_root_edit.setObjectName("screenshotRootEdit")

        browse_button = QPushButton("...", container)
        browse_button.setObjectName("screenshotRootBrowseButton")
        browse_button.clicked.connect(self._on_browse_screenshot_root_clicked)

        layout.addWidget(QLabel("Model", container))
        layout.addWidget(self._model_name_edit)
        layout.addWidget(QLabel("Screenshot Root", container))
        layout.addWidget(self._screenshot_root_edit)
        layout.addWidget(browse_button)

        self._ui.centralLayout.addWidget(container)

    def _connect_signals(self) -> None:
        """시그널/슬롯 연결 허브. TODO(spec): 도크/패널 결선."""
        return None

    def _on_browse_screenshot_root_clicked(self) -> None:
        """스크린샷 루트 디렉터리를 선택한다."""

        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Screenshot Root",
            self._screenshot_root_edit.text(),
        )
        if directory:
            self._screenshot_root_edit.setText(directory)
