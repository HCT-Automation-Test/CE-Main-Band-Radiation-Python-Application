"""장비 Set 진행 상태를 표시하는 modeless dialog."""
from __future__ import annotations

import time

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QCloseEvent, QKeyEvent
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


def format_elapsed_time(seconds: int) -> str:
    """초 단위 경과 시간을 HH:MM:SS 형식으로 변환한다."""

    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


class InstrumentSetProgressDialog(QDialog):
    """취소할 수 없는 장비 Set 진행 상태를 표시한다."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        initial_step: str = "장비 Set 진행 중",
    ) -> None:
        super().__init__(parent)
        self.setObjectName("instrumentSetProgressDialog")
        self.setWindowTitle("장비 Set 진행 중")
        self.setModal(False)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        self._allow_close = False
        self._started_monotonic = 0.0
        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.setObjectName("instrumentSetProgressElapsedTimer")
        self._elapsed_timer.setInterval(1000)
        self._elapsed_timer.timeout.connect(self.update_elapsed)
        self._setup_layout(initial_step)
        self._apply_styles()

    def start(self) -> None:
        """경과 시간 타이머를 시작하고 dialog를 표시한다."""

        self._started_monotonic = time.monotonic()
        self._elapsed_label.setText(format_elapsed_time(0))
        self._elapsed_timer.start()
        self.show()
        self.raise_()
        self.activateWindow()

    def set_step(self, message: str) -> None:
        """현재 진행 단계를 갱신한다."""

        self._step_label.setText(message)

    def update_elapsed(self) -> None:
        """타이머 tick 시 경과 시간을 갱신한다."""

        elapsed = int(time.monotonic() - self._started_monotonic)
        self._elapsed_label.setText(format_elapsed_time(elapsed))

    def close_without_action(self) -> None:
        """Set 결과 처리 시 UI 정리 목적으로 dialog를 닫는다."""

        self._allow_close = True
        self._elapsed_timer.stop()
        self.hide()

    def reject(self) -> None:
        """ESC나 창 시스템 reject로 Set 진행창이 닫히지 않게 한다."""

        return

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """사용자 close 시도를 무시한다."""

        if self._allow_close:
            super().closeEvent(event)
            return
        event.ignore()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        """ESC 키로 닫히지 않게 한다."""

        if event.key() == Qt.Key.Key_Escape:
            event.ignore()
            return
        super().keyPressEvent(event)

    def _setup_layout(self, initial_step: str) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        title = QLabel("장비 Set 진행 중", self)
        title.setObjectName("instrumentSetProgressTitleLabel")
        title.setProperty("titleLabel", True)
        layout.addWidget(title)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)

        self._step_label = QLabel(initial_step, self)
        self._step_label.setObjectName("instrumentSetProgressStepLabel")
        self._step_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        self._step_label.setWordWrap(True)

        self._elapsed_label = QLabel(format_elapsed_time(0), self)
        self._elapsed_label.setObjectName("instrumentSetProgressElapsedLabel")

        form.addRow("현재 단계:", self._step_label)
        form.addRow("경과 시간:", self._elapsed_label)
        layout.addLayout(form)

        guide = QLabel("장비 Set 작업은 취소할 수 없습니다.", self)
        guide.setObjectName("instrumentSetProgressGuideLabel")
        guide.setWordWrap(True)
        layout.addWidget(guide)

        self.setMinimumWidth(360)

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QDialog#instrumentSetProgressDialog {
                background: #ffffff;
                color: #111111;
            }
            QLabel {
                color: #111111;
                background: transparent;
            }
            QLabel[titleLabel="true"] {
                font-size: 16px;
                font-weight: 700;
            }
            """
        )
