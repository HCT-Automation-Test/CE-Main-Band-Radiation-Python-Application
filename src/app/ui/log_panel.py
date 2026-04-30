"""앱 로그 출력 패널."""
from __future__ import annotations

import logging
import weakref
from typing import Any

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtWidgets import QPlainTextEdit, QVBoxLayout, QWidget

_DEFAULT_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


class _LogSignalEmitter(QObject):
    """logging handler에서 UI thread로 메시지를 전달한다."""

    message_logged = Signal(str)


class _PlainTextEditLogHandler(logging.Handler):
    """logging record를 Qt signal로 넘기는 handler."""

    def __init__(self, emitter: _LogSignalEmitter) -> None:
        super().__init__()
        self._emitter_ref = weakref.ref(emitter)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            emitter = self._emitter_ref()
            if emitter is None:
                return
            emitter.message_logged.emit(self.format(record))
        except Exception:
            self.handleError(record)


def _detach_panel_handler(panel_ref: weakref.ReferenceType["LogPanel"]) -> None:
    panel = panel_ref()
    if panel is not None:
        panel.detach_logging()


class LogPanel(QWidget):
    """logging → QPlainTextEdit 미러."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        logger: logging.Logger | None = None,
        max_blocks: int = 1000,
    ) -> None:
        super().__init__(parent)
        self._logger = logger or logging.getLogger()
        self._handler: logging.Handler | None = None
        self._emitter = _LogSignalEmitter(self)
        self._setup_layout(max_blocks)
        self._attach_logging()
        self.destroyed.connect(
            lambda _obj=None, panel_ref=weakref.ref(self): _detach_panel_handler(
                panel_ref,
            ),
        )

    @property
    def text_edit(self) -> QPlainTextEdit:
        """테스트와 상위 UI에서 로그 위젯을 확인하기 위한 접근자."""

        return self._log_text_edit

    def _setup_layout(self, max_blocks: int) -> None:
        """로그 출력 영역을 패널 전체에 배치한다."""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._log_text_edit = QPlainTextEdit(self)
        self._log_text_edit.setObjectName("logTextEdit")
        self._log_text_edit.setReadOnly(True)
        self._log_text_edit.setMaximumBlockCount(max_blocks)

        layout.addWidget(self._log_text_edit, 1)
        self.setStyleSheet(
            """
            QPlainTextEdit#logTextEdit {
                border: 1px solid #3f73a8;
                background: #ffffff;
                color: #111111;
                font-family: Consolas, "Courier New", monospace;
                font-size: 12px;
            }
            """
        )

    def _attach_logging(self) -> None:
        """logger에 UI 미러 handler를 부착한다."""

        handler = _PlainTextEditLogHandler(self._emitter)
        handler.setFormatter(logging.Formatter(_DEFAULT_LOG_FORMAT))
        self._emitter.message_logged.connect(self.append_message)
        self._logger.addHandler(handler)
        self._handler = handler

    def detach_logging(self) -> None:
        """logger에서 UI 미러 handler를 제거한다."""

        if self._handler is None:
            return
        self._logger.removeHandler(self._handler)
        self._handler = None

    @Slot(str)
    def append_message(self, message: str) -> None:
        """로그 메시지를 출력 영역에 추가한다."""

        self._log_text_edit.appendPlainText(message)

    def clear(self) -> None:
        """현재 표시 중인 로그를 비운다."""

        self._log_text_edit.clear()

    def closeEvent(self, event: Any) -> None:  # noqa: N802
        """패널이 닫힐 때 logging handler를 정리한다."""

        self.detach_logging()
        super().closeEvent(event)
