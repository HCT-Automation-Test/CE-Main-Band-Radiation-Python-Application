"""애플리케이션 엔트리포인트.

`uv run python -m app`으로 실행된다. 로깅을 구성하고 `MainWindow`를 띄운다.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from app.logging_setup import setup_logging


logger = logging.getLogger(__name__)


def _resource_path(relative_path: str) -> Path:
    base_path = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    return base_path / relative_path


def main() -> int:
    setup_logging()
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(str(_resource_path("resources/icons/app_icon.ico"))))
    try:
        from app.ui.main_window import MainWindow
    except ImportError as exc:
        # Ui_* 모듈이 아직 없을 때 (pyside6-uic 미실행)
        logger.error(
            "UI 모듈 import 실패. 먼저 다음 명령으로 .ui를 컴파일하세요:\n"
            "  uv run pyside6-uic resources/main_window.ui "
            "-o src/app/ui/generated/main_window_ui.py\n원인: %s",
            exc,
        )
        return 2

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
