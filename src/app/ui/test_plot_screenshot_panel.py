"""Test Plot Screenshot 서브 패널."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from PySide6.QtCore import QTimer, Qt, Slot
from PySide6.QtGui import QPixmap, QResizeEvent, QShowEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.ui.log_panel import LogPanel

logger = logging.getLogger(__name__)

_LOG_PANEL_WIDTH = 280
_SUPPORTED_IMAGE_SUFFIXES = {".bmp", ".gif", ".jpg", ".jpeg", ".png"}


class TestPlotScreenshotPanel(QWidget):
    """가장 최근 저장된 SA 스크린샷을 표시하는 화면."""

    __test__ = False

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("testPlotScreenshotPanel")
        self._latest_screenshot_path: Path | None = None
        self._source_pixmap: QPixmap | None = None
        self._setup_layout()
        self._apply_styles()

    @property
    def latest_screenshot_path(self) -> Path | None:
        """현재 표시 중인 최신 스크린샷 경로를 반환한다."""

        return self._latest_screenshot_path

    def _setup_layout(self) -> None:
        """스크린샷 표시 영역과 우측 로그 패널을 배치한다."""

        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(10)

        content_panel = QWidget(self)
        content_panel.setObjectName("testPlotScreenshotContentPanel")
        content_layout = QVBoxLayout(content_panel)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(8)

        self._path_label = QLabel("저장된 스크린샷이 없습니다.", content_panel)
        self._path_label.setObjectName("screenshotPathLabel")
        self._path_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse,
        )
        self._path_label.setWordWrap(True)
        self._path_label.setMaximumHeight(52)
        content_layout.addWidget(self._path_label)

        viewer_frame = QFrame(content_panel)
        viewer_frame.setObjectName("screenshotViewerFrame")
        viewer_frame.setFrameShape(QFrame.Shape.StyledPanel)
        viewer_layout = QVBoxLayout(viewer_frame)
        viewer_layout.setContentsMargins(10, 10, 10, 10)
        viewer_layout.setSpacing(0)

        self._image_label = QLabel("스크린샷 대기 중", viewer_frame)
        self._image_label.setObjectName("screenshotImageLabel")
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Ignored,
        )
        self._image_label.setMinimumSize(320, 240)
        viewer_layout.addWidget(self._image_label, 1)
        content_layout.addWidget(viewer_frame, 1)

        self._log_panel = LogPanel(self)
        self._log_panel.setObjectName("testPlotScreenshotLogPanel")
        self._log_panel.setFixedWidth(_LOG_PANEL_WIDTH)

        root_layout.addWidget(content_panel, 1)
        root_layout.addWidget(self._log_panel)

    def _apply_styles(self) -> None:
        """패널 전용 표시 스타일을 적용한다."""

        self.setStyleSheet(
            """
            QWidget#testPlotScreenshotPanel,
            QWidget#testPlotScreenshotContentPanel {
                background: #ffffff;
            }

            QLabel#screenshotPathLabel {
                border: 1px solid #3f73a8;
                color: #111111;
                padding: 6px 8px;
                background: #f8fbff;
                font-size: 13px;
            }

            QFrame#screenshotViewerFrame {
                border: 1px solid #3f73a8;
                background: #f5f7fa;
            }

            QLabel#screenshotImageLabel {
                border: 0;
                background: #ffffff;
                color: #666666;
                font-size: 18px;
            }
            """
        )

    @Slot(str)
    def on_screenshot_saved(self, path: str) -> None:
        """저장 완료 이벤트로 전달된 최신 스크린샷을 화면에 표시한다."""

        screenshot_path = Path(path)
        if not self._is_supported_image_path(screenshot_path):
            self._show_message(f"지원하지 않는 스크린샷 파일입니다: {screenshot_path}")
            logger.warning("지원하지 않는 스크린샷 파일: %s", screenshot_path)
            return
        if not screenshot_path.is_file():
            self._show_message(f"스크린샷 파일을 찾을 수 없습니다: {screenshot_path}")
            logger.warning("스크린샷 파일 없음: %s", screenshot_path)
            return

        pixmap = QPixmap(str(screenshot_path))
        if pixmap.isNull():
            self._show_message(f"스크린샷을 불러올 수 없습니다: {screenshot_path}")
            logger.warning("스크린샷 로드 실패: %s", screenshot_path)
            return

        self._latest_screenshot_path = screenshot_path
        self._source_pixmap = pixmap
        self._path_label.setText(str(screenshot_path))
        self._update_scaled_pixmap()
        QTimer.singleShot(0, self._update_scaled_pixmap)
        logger.info("스크린샷 표시: %s", screenshot_path)

    def _is_supported_image_path(self, path: Path) -> bool:
        return path.suffix.lower() in _SUPPORTED_IMAGE_SUFFIXES

    def _show_message(self, message: str) -> None:
        self._source_pixmap = None
        self._latest_screenshot_path = None
        self._path_label.setText(message)
        self._image_label.setPixmap(QPixmap())
        self._image_label.setText(message)

    def _update_scaled_pixmap(self) -> None:
        if self._source_pixmap is None:
            return

        try:
            target_size = self._image_label.size()
        except RuntimeError:
            return
        if target_size.width() <= 0 or target_size.height() <= 0:
            return

        scaled = self._source_pixmap.scaled(
            target_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        try:
            self._image_label.setText("")
            self._image_label.setPixmap(scaled)
        except RuntimeError:
            return

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        """패널 크기 변경 시 표시 중인 이미지를 다시 맞춘다."""

        super().resizeEvent(event)
        self._update_scaled_pixmap()

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        """숨겨진 탭에서 받은 스크린샷을 표시 시점에 다시 맞춘다."""

        super().showEvent(event)
        self._update_scaled_pixmap()
        QTimer.singleShot(0, self._update_scaled_pixmap)

    def closeEvent(self, event: Any) -> None:  # noqa: N802
        """패널 종료 시 로그 핸들러를 정리한다."""

        self._log_panel.detach_logging()
        super().closeEvent(event)
