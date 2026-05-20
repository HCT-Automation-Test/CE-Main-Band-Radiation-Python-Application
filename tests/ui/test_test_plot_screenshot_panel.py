"""Test Plot Screenshot 패널 테스트."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QLabel, QStackedWidget

from app.ui.log_panel import LogPanel
from app.ui.main_window import MainWindow
from app.ui.test_plot_screenshot_panel import TestPlotScreenshotPanel


def _write_png(path: Path, color: QColor) -> None:
    image = QImage(80, 60, QImage.Format.Format_RGB32)
    image.fill(color)
    assert image.save(str(path))


def test_plot_screenshot_panel_shows_latest_saved_screenshot(qtbot, tmp_path) -> None:
    """저장 이벤트로 전달된 최신 스크린샷만 화면에 표시한다."""

    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    _write_png(first, QColor("#ff0000"))
    _write_png(second, QColor("#00ff00"))

    panel = TestPlotScreenshotPanel()
    qtbot.addWidget(panel)
    panel.resize(640, 480)
    panel.show()

    panel.on_screenshot_saved(str(first))
    panel.on_screenshot_saved(str(second))

    image_label = panel.findChild(QLabel, "screenshotImageLabel")
    path_label = panel.findChild(QLabel, "screenshotPathLabel")

    assert panel.latest_screenshot_path == second
    assert image_label is not None
    assert image_label.pixmap() is not None
    assert not image_label.pixmap().isNull()
    assert path_label is not None
    assert path_label.text() == str(second)


def test_plot_screenshot_panel_contains_right_log_panel(qtbot) -> None:
    """다른 서브 패널처럼 우측 로그 패널을 가진다."""

    panel = TestPlotScreenshotPanel()
    qtbot.addWidget(panel)

    assert panel.findChild(QLabel, "screenshotImageLabel") is not None
    assert panel.findChild(QLabel, "screenshotPathLabel") is not None
    assert panel.findChild(LogPanel, "testPlotScreenshotLogPanel") is not None


def test_main_window_wires_screenshot_saved_to_plot_panel(qtbot, tmp_path) -> None:
    """Runner screenshot_saved 이벤트가 Test Plot Screenshot 패널을 갱신한다."""

    screenshot = tmp_path / "latest.png"
    _write_png(screenshot, QColor("#336699"))

    window = MainWindow()
    qtbot.addWidget(window)
    panel = window.findChild(TestPlotScreenshotPanel)

    assert panel is not None

    window._runner.events.screenshot_saved.emit(str(screenshot))

    assert panel.latest_screenshot_path == screenshot


def test_main_window_shows_screenshot_saved_while_plot_page_is_hidden(
    qtbot,
    tmp_path,
) -> None:
    """숨겨진 탭에서 받은 스크린샷도 탭 전환 후 이미지로 표시한다."""

    screenshot = tmp_path / "hidden-page.png"
    _write_png(screenshot, QColor("#8844cc"))

    window = MainWindow()
    qtbot.addWidget(window)
    window.resize(1000, 700)
    window.show()
    qtbot.wait(0)

    stack = window.findChild(QStackedWidget, "subWindowStack")
    panel = window.findChild(TestPlotScreenshotPanel)
    image_label = window.findChild(QLabel, "screenshotImageLabel")

    assert stack is not None
    assert panel is not None
    assert image_label is not None
    assert stack.currentIndex() != 4

    window._runner.events.screenshot_saved.emit(str(screenshot))
    stack.setCurrentIndex(4)
    qtbot.waitUntil(
        lambda: image_label.pixmap() is not None and not image_label.pixmap().isNull(),
        timeout=1000,
    )

    assert panel.latest_screenshot_path == screenshot
