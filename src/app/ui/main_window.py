"""MainWindow — 앱 메인 윈도우."""
from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

# 먼저 `uv run pyside6-uic resources/main_window.ui -o src/app/ui/generated/main_window_ui.py`
# 실행해야 아래 임포트가 성공한다.
from app.ui.generated.main_window_ui import Ui_MainWindow
from app.ui.instrument_check_panel import InstrumentCheckPanel
from app.ui.manual_test_panel import ManualTestPanel
from app.ui.rf_filter_box_panel import RFFilterBoxPanel
from app.ui.test_manager_panel import TestManagerPanel
from app.ui.test_plot_screenshot_panel import TestPlotScreenshotPanel

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """최상위 메인 윈도우. 생성된 Ui_MainWindow를 컴포지션으로 보유."""

    def __init__(self, parent: QMainWindow | None = None) -> None:
        super().__init__(parent)
        self._ui = Ui_MainWindow()
        self._ui.setupUi(self)
        self.resize(1280, 800)
        self.setMinimumSize(1100, 700)
        self._setup_main_layout()
        self._connect_signals()

    def _connect_signals(self) -> None:
        """시그널/슬롯 연결 허브. TODO(spec): 도크/패널 결선."""
        self._navigation_button_group.idClicked.connect(
            self.on_navigation_button_clicked,
        )

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

        self._add_navigation_page(
            navigation_layout,
            index=0,
            button_text="Instrument\nCheck",
            object_name="instrumentCheck",
            page_title="Instrument Check",
            page_widget=InstrumentCheckPanel(self._page_stack),
        )
        self._add_navigation_page(
            navigation_layout,
            index=1,
            button_text="Manual\nTest",
            object_name="manualTest",
            page_title="Manual Test",
            page_widget=ManualTestPanel(self._page_stack),
        )
        self._add_navigation_page(
            navigation_layout,
            index=2,
            button_text="RF Filter\nBox",
            object_name="rfFilterBox",
            page_title="RF Filter Box",
            page_widget=RFFilterBoxPanel(self._page_stack),
        )
        self._add_navigation_page(
            navigation_layout,
            index=3,
            button_text="Test\nManager",
            object_name="testManager",
            page_title="Test Manager",
            page_widget=TestManagerPanel(self._page_stack),
        )
        self._add_navigation_page(
            navigation_layout,
            index=4,
            button_text="Test Plot\nScreenshot",
            object_name="testPlotScreenshot",
            page_title="Test Plot Screenshot",
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

            QLabel#subWindowTitleLabel {
                color: #222222;
                font-size: 20px;
                font-weight: 600;
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
        page_title: str,
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

        page = self._create_page(page_title, page_widget)
        page.setObjectName(f"{object_name}Page")
        self._page_stack.addWidget(page)

    def _create_page(self, title: str, content_widget: QWidget) -> QWidget:
        """서브 윈도우 페이지 공통 외곽을 만든다."""

        page = QWidget(self._page_stack)
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(18, 14, 18, 18)
        page_layout.setSpacing(12)

        title_label = QLabel(title, page)
        title_label.setObjectName("subWindowTitleLabel")
        title_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        )
        page_layout.addWidget(title_label)

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
