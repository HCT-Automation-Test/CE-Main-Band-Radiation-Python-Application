"""MainWindow — 앱 메인 윈도우."""
from __future__ import annotations

import logging
import sys
import ctypes

from PySide6.QtCore import QEvent, QSize, Qt
from PySide6.QtGui import QCloseEvent, QShowEvent
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

# 먼저 `uv run pyside6-uic resources/main_window.ui -o src/app/ui/generated/main_window_ui.py`
# 실행해야 아래 임포트가 성공한다.
from app.core.runner import INSTRUMENT_CONNECTION_BLOCK_MESSAGE, Runner
from app.models.test_case import TestCase
from app.ui.generated.main_window_ui import Ui_MainWindow
from app.ui.instrument_check_panel import InstrumentCheckPanel
from app.ui.manual_test_panel import ManualTestPanel
from app.ui.rf_filter_box_panel import RFFilterBoxPanel
from app.ui.test_manager_panel import TestManagerPanel
from app.ui.test_plot_screenshot_panel import TestPlotScreenshotPanel

logger = logging.getLogger(__name__)

_DEFAULT_WINDOW_SIZE = QSize(1600, 900)
_UNBOUNDED_WINDOW_SIZE = QSize(16777215, 16777215)
_GWL_STYLE = -16
_WS_THICKFRAME = 0x00040000
_WS_MAXIMIZEBOX = 0x00010000
_SWP_NOSIZE = 0x0001
_SWP_NOMOVE = 0x0002
_SWP_NOZORDER = 0x0004
_SWP_FRAMECHANGED = 0x0020


class MainWindow(QMainWindow):
    """최상위 메인 윈도우. 생성된 Ui_MainWindow를 컴포지션으로 보유."""

    def __init__(self, parent: QMainWindow | None = None) -> None:
        super().__init__(parent)
        self._ui = Ui_MainWindow()
        self._ui.setupUi(self)
        self._runner = Runner(self)
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
        self._lock_default_window_size()
        self._setup_main_layout()
        self._connect_signals()

    def _connect_signals(self) -> None:
        """시그널/슬롯 연결 허브. TODO(spec): 도크/패널 결선."""
        self._navigation_button_group.idClicked.connect(
            self.on_navigation_button_clicked,
        )
        self._test_manager_panel.start_requested.connect(
            self.on_start_requested,
        )
        self._runner.measurement_active_changed.connect(
            self.on_measurement_active_changed,
        )
        self._runner.events.current_case_changed.connect(
            self.on_current_case_changed,
        )
        self._runner.instrument_connection_service.connection_started.connect(
            self._test_manager_panel.set_connection_connecting,
        )
        self._runner.instrument_connection_service.connection_finished.connect(
            self._test_manager_panel.set_connection_state,
        )
        self._runner.instrument_connection_service.error_occurred.connect(
            self._test_manager_panel.set_connection_failed,
        )
        self.on_measurement_active_changed(self._runner.is_measurement_active)
        self._test_manager_panel.set_connection_state(self._runner.equipment_state)

    def _setup_main_layout(self) -> None:
        """좌측 서브 윈도우 선택 버튼과 우측 화면 스택을 구성한다."""

        self._ui.titleLabel.hide()
        self._ui.centralLayout.setContentsMargins(10, 10, 10, 10)
        self._ui.centralLayout.setSpacing(0)

        main_container = QWidget(self)
        main_container.setObjectName("mainContent")
        main_layout = QHBoxLayout(main_container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(14)

        navigation_panel = QWidget(main_container)
        navigation_panel.setObjectName("navigationPanel")
        navigation_panel.setFixedWidth(148)
        navigation_layout = QVBoxLayout(navigation_panel)
        navigation_layout.setContentsMargins(0, 0, 0, 0)
        navigation_layout.setSpacing(20)

        self._navigation_button_group = QButtonGroup(self)
        self._navigation_button_group.setExclusive(True)
        self._page_stack = QStackedWidget(main_container)
        self._page_stack.setObjectName("subWindowStack")
        self._page_stack.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self._instrument_check_panel = InstrumentCheckPanel(
            self._page_stack,
            service=self._runner.instrument_connection_service,
        )
        self._test_manager_panel = TestManagerPanel(self._page_stack)

        self._add_navigation_page(
            navigation_layout,
            index=0,
            button_text="Instrument\nCheck",
            object_name="instrumentCheck",
            page_widget=self._instrument_check_panel,
        )
        self._add_navigation_page(
            navigation_layout,
            index=1,
            button_text="Manual\nTest",
            object_name="manualTest",
            page_widget=ManualTestPanel(self._page_stack),
        )
        self._add_navigation_page(
            navigation_layout,
            index=2,
            button_text="RF Filter\nBox",
            object_name="rfFilterBox",
            page_widget=RFFilterBoxPanel(self._page_stack),
        )
        self._add_navigation_page(
            navigation_layout,
            index=3,
            button_text="Test\nManager",
            object_name="testManager",
            page_widget=self._test_manager_panel,
        )
        self._add_navigation_page(
            navigation_layout,
            index=4,
            button_text="Test Plot\nScreenshot",
            object_name="testPlotScreenshot",
            page_widget=TestPlotScreenshotPanel(self._page_stack),
        )

        navigation_layout.addStretch(1)

        content_area = QWidget(main_container)
        content_area.setObjectName("subWindowContentArea")
        self._content_layout = QVBoxLayout(content_area)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(10)
        self._content_layout.addWidget(self._page_stack, 1)

        main_layout.addWidget(navigation_panel)
        main_layout.addWidget(content_area, 1)

        self._ui.centralLayout.addWidget(main_container, 1)
        self._navigation_button_group.button(0).setChecked(True)

        self.setStyleSheet(
            """
            QWidget#navigationPanel QPushButton[navigationButton="true"] {
                background: #f8f8f8;
                border: 1px solid #3f73a8;
                color: #111111;
                font-size: 23px;
                padding: 4px 6px;
                text-align: center;
            }

            QWidget#navigationPanel QPushButton[navigationButton="true"]:checked {
                background: #eaf3ff;
                border: 2px solid #2f69a6;
            }

            QWidget#navigationPanel QPushButton[navigationButton="true"]:hover {
                background: #f1f7ff;
            }
            """
        )

    def _add_navigation_page(
        self,
        navigation_layout: QVBoxLayout,
        *,
        index: int,
        button_text: str,
        object_name: str,
        page_widget: QWidget,
    ) -> None:
        """내비게이션 버튼과 연결된 스택 페이지를 추가한다."""

        button = QPushButton(button_text, self)
        button.setObjectName(f"{object_name}NavigationButton")
        button.setProperty("navigationButton", True)
        button.setCheckable(True)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFixedHeight(70)
        button.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self._navigation_button_group.addButton(button, index)
        navigation_layout.addWidget(button)

        page = self._create_page(page_widget)
        page.setObjectName(f"{object_name}Page")
        self._page_stack.addWidget(page)

    def _create_page(self, content_widget: QWidget) -> QWidget:
        """서브 윈도우 페이지 공통 외곽을 만든다."""

        page = QWidget(self._page_stack)
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)

        content_widget.setParent(page)
        content_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        page_layout.addWidget(content_widget, 1)
        return page

    def on_navigation_button_clicked(self, index: int) -> None:
        """내비게이션 버튼 클릭 시 우측 서브 윈도우를 전환한다."""

        self._page_stack.setCurrentIndex(index)

    def on_start_requested(self) -> None:
        """Test Manager의 시작 요청을 Runner에 전달한다."""

        settings = self._test_manager_panel.build_test_run_settings()
        if settings is None:
            return
        self._runner.start(
            list(self._test_manager_panel.test_cases),
            settings=settings,
        )

    def on_measurement_active_changed(self, active: bool) -> None:
        """측정 실행 중에는 Instrument Check 재연결을 막는다."""

        self._instrument_check_panel.set_connection_block_reason(
            INSTRUMENT_CONNECTION_BLOCK_MESSAGE if active else None
        )

    def on_current_case_changed(self, case: TestCase) -> None:
        """현재 실행 중인 TestCase 요약 정보를 갱신한다."""

        self._test_manager_panel.set_current_case(case)

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        """창 표시 후 네이티브 resize 테두리 정책을 다시 적용한다."""

        super().showEvent(event)
        if self.isMaximized() or self.isFullScreen():
            self._unlock_window_size()
            return
        self._lock_default_window_size()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """윈도우 종료 전에 worker를 가진 하위 패널을 정리한다."""

        self._shutdown_child_panels()
        self._runner.shutdown()
        super().closeEvent(event)

    def event(self, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Destroy:
            self._shutdown_child_panels()
            self._runner.shutdown()
        return super().event(event)

    def _shutdown_child_panels(self) -> None:
        seen: set[int] = set()
        for widget in self.findChildren(QWidget):
            identifier = id(widget)
            if identifier in seen:
                continue
            seen.add(identifier)

            shutdown = getattr(widget, "shutdown", None)
            if callable(shutdown):
                shutdown()
                continue

            dispose = getattr(widget, "dispose", None)
            if callable(dispose):
                dispose()

    def showMaximized(self) -> None:  # noqa: N802
        """최대화 진입 전 크기 제한을 해제한다."""

        self._unlock_window_size()
        super().showMaximized()

    def showFullScreen(self) -> None:  # noqa: N802
        """전체화면 진입 전 크기 제한을 해제한다."""

        self._unlock_window_size()
        super().showFullScreen()

    def showNormal(self) -> None:  # noqa: N802
        """일반 창으로 돌아올 때 기본 크기로 다시 고정한다."""

        super().showNormal()
        self._lock_default_window_size()

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802
        """타이틀바 상태 전환 시 크기 제한을 갱신한다."""

        super().changeEvent(event)
        if event.type() != QEvent.Type.WindowStateChange:
            return
        if self.isMaximized() or self.isFullScreen():
            self._unlock_window_size()
            return
        self._lock_default_window_size()

    def _lock_default_window_size(self) -> None:
        """일반 상태에서 창 크기를 기본 크기로 고정한다."""

        self.resize(_DEFAULT_WINDOW_SIZE)
        self.setMinimumSize(_DEFAULT_WINDOW_SIZE)
        self.setMaximumSize(_UNBOUNDED_WINDOW_SIZE)
        self._set_windows_resize_frame_enabled(False)

    def _unlock_window_size(self) -> None:
        """최대화/전체화면 전환을 위해 크기 제한을 해제한다."""

        self.setMinimumSize(0, 0)
        self.setMaximumSize(_UNBOUNDED_WINDOW_SIZE)
        self._set_windows_resize_frame_enabled(True)

    def _set_windows_resize_frame_enabled(self, enabled: bool) -> None:
        """Windows에서 드래그 resize 테두리만 켜고 끈다."""

        if sys.platform != "win32":
            return

        hwnd = int(self.winId())
        style = ctypes.windll.user32.GetWindowLongPtrW(hwnd, _GWL_STYLE)
        if enabled:
            style |= _WS_THICKFRAME | _WS_MAXIMIZEBOX
        else:
            style = (style & ~_WS_THICKFRAME) | _WS_MAXIMIZEBOX

        ctypes.windll.user32.SetWindowLongPtrW(hwnd, _GWL_STYLE, style)
        ctypes.windll.user32.SetWindowPos(
            hwnd,
            0,
            0,
            0,
            0,
            0,
            _SWP_NOMOVE | _SWP_NOSIZE | _SWP_NOZORDER | _SWP_FRAMECHANGED,
        )
