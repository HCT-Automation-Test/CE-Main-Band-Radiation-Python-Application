"""MainWindow 서브 패널 스캐폴드 테스트."""
from __future__ import annotations

import logging

from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QWidget,
)

from app.ui.instrument_check_panel import InstrumentCheckPanel
from app.ui.log_panel import LogPanel
from app.ui.main_window import MainWindow
from app.ui.manual_test_panel import ManualTestPanel
from app.ui.nr_select import NRSelectDialog
from app.ui.rf_filter_box_panel import RFFilterBoxPanel
from app.ui.test_manager_panel import TestManagerPanel as ManagerPanel
from app.ui.test_plot_screenshot_panel import (
    TestPlotScreenshotPanel as PlotScreenshotPanel,
)

DEFAULT_WINDOW_SIZE = QSize(1600, 900)
UNBOUNDED_WINDOW_SIZE = QSize(16777215, 16777215)


def test_main_window_has_five_navigation_buttons_and_pages(qtbot) -> None:
    """메인 윈도우가 5개 서브 패널 전환 구조를 가진다."""

    window = MainWindow()
    qtbot.addWidget(window)

    buttons = [
        button
        for button in window.findChildren(QPushButton)
        if button.property("navigationButton") is True
    ]
    button_names = {button.objectName() for button in buttons}

    assert len(buttons) == 5
    assert button_names == {
        "instrumentCheckNavigationButton",
        "manualTestNavigationButton",
        "rfFilterBoxNavigationButton",
        "testManagerNavigationButton",
        "testPlotScreenshotNavigationButton",
    }

    stack = window.findChild(QStackedWidget, "subWindowStack")

    assert stack is not None
    assert stack.count() == 5


def test_main_window_pages_use_expected_panel_classes(qtbot) -> None:
    """각 전환 페이지가 역할에 맞는 패널 클래스를 포함한다."""

    window = MainWindow()
    qtbot.addWidget(window)

    stack = window.findChild(QStackedWidget, "subWindowStack")
    assert stack is not None

    expected_panels = [
        InstrumentCheckPanel,
        ManualTestPanel,
        RFFilterBoxPanel,
        ManagerPanel,
        PlotScreenshotPanel,
    ]

    for index, panel_class in enumerate(expected_panels):
        page = stack.widget(index)
        assert page.findChild(panel_class) is not None


def test_main_window_page_content_aligns_with_navigation_panel(qtbot) -> None:
    """좌측 버튼 영역과 우측 서브패널 content 영역의 위치/크기를 맞춘다."""

    window = MainWindow()
    qtbot.addWidget(window)
    window.resize(1280, 800)
    window.show()
    qtbot.wait(0)

    navigation_panel = window.findChild(QWidget, "navigationPanel")
    stack = window.findChild(QStackedWidget, "subWindowStack")

    assert navigation_panel is not None
    assert stack is not None
    assert window.findChild(QWidget, "subWindowTitleLabel") is None

    navigation_origin = navigation_panel.mapTo(window, QPoint(0, 0))
    stack_origin = stack.mapTo(window, QPoint(0, 0))

    assert stack_origin.y() == navigation_origin.y()
    assert stack.height() == navigation_panel.height()

    expected_panels = [
        InstrumentCheckPanel,
        ManualTestPanel,
        RFFilterBoxPanel,
        ManagerPanel,
        PlotScreenshotPanel,
    ]

    for index, panel_class in enumerate(expected_panels):
        stack.setCurrentIndex(index)
        qtbot.wait(0)

        page = stack.widget(index)
        panel = page.findChild(panel_class)
        assert panel is not None

        panel_origin = panel.mapTo(window, QPoint(0, 0))
        assert panel_origin.x() == stack_origin.x()
        assert panel_origin.y() == navigation_origin.y()
        assert panel.width() == stack.width()
        assert panel.height() == navigation_panel.height()


def test_main_window_uses_fixed_default_size_in_normal_state(qtbot) -> None:
    """일반 창 상태에서는 기본 크기보다 작아지지 않게 한다."""

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.wait(0)

    assert window.size() == DEFAULT_WINDOW_SIZE
    assert window.minimumSize() == DEFAULT_WINDOW_SIZE
    assert window.maximumSize() == UNBOUNDED_WINDOW_SIZE

    window.resize(1180, 740)
    qtbot.wait(0)

    assert window.size() == DEFAULT_WINDOW_SIZE


def test_main_window_allows_maximized_state(qtbot) -> None:
    """최대화 상태는 기본 크기 복귀 예외로 허용한다."""

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.wait(0)

    window.showMaximized()
    qtbot.waitUntil(window.isMaximized, timeout=1000)
    assert window.windowState() & Qt.WindowState.WindowMaximized
    assert window.maximumSize() == UNBOUNDED_WINDOW_SIZE

    window.showNormal()
    qtbot.waitUntil(lambda: not window.isMaximized(), timeout=1000)
    qtbot.waitUntil(
        lambda: window.size() == DEFAULT_WINDOW_SIZE,
        timeout=1000,
    )
    assert window.minimumSize() == DEFAULT_WINDOW_SIZE
    assert window.maximumSize() == UNBOUNDED_WINDOW_SIZE


def test_main_window_allows_fullscreen_state(qtbot) -> None:
    """전체화면 상태는 기본 크기 복귀 예외로 허용한다."""

    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    qtbot.wait(0)

    window.showFullScreen()
    qtbot.waitUntil(window.isFullScreen, timeout=1000)
    assert window.windowState() & Qt.WindowState.WindowFullScreen
    assert window.maximumSize() == UNBOUNDED_WINDOW_SIZE

    window.showNormal()
    qtbot.waitUntil(lambda: not window.isFullScreen(), timeout=1000)
    qtbot.waitUntil(
        lambda: window.size() == DEFAULT_WINDOW_SIZE,
        timeout=1000,
    )
    assert window.minimumSize() == DEFAULT_WINDOW_SIZE
    assert window.maximumSize() == UNBOUNDED_WINDOW_SIZE


def test_main_window_session_inputs_are_moved_to_test_manager(qtbot) -> None:
    """메인 윈도우 전역 세션 입력 바를 더 이상 만들지 않는다."""

    window = MainWindow()
    qtbot.addWidget(window)

    assert window.findChild(QWidget, "sessionInputBar") is None
    assert window.findChild(QLineEdit, "modelNameEdit") is None
    assert not hasattr(window, "_model_name_edit")
    assert not hasattr(window, "_screenshot_root_edit")

    manager = window.findChild(ManagerPanel)
    assert manager is not None
    assert manager.findChild(QLineEdit, "eutNameEdit") is not None
    assert manager.findChild(QLineEdit, "screenshotRootEdit") is not None


def test_test_manager_panel_has_extended_test_case_table(qtbot) -> None:
    """Test Manager 표가 실행용 확장 컬럼을 가진다."""

    panel = ManagerPanel()
    qtbot.addWidget(panel)

    table = panel.findChild(QTableWidget, "testCaseTable")

    assert table is not None
    assert table.columnCount() == 17
    assert [
        table.horizontalHeaderItem(index).text()
        for index in range(table.columnCount())
    ] == [
        "Generation",
        "Band",
        "EUT ANT",
        "SCS",
        "BW",
        "Modulation",
        "RB Allocation",
        "RB Size",
        "RB Offset",
        "CH",
        "ARFCN",
        "CH_No.",
        "Case",
        "Start Freq",
        "Stop Freq",
        "Axis",
        "Pol",
    ]
    assert not table.horizontalHeader().stretchLastSection()


def test_test_manager_panel_test_case_table_fits_default_window(qtbot) -> None:
    """기본 창 크기에서 TestCase 표가 가로로 잘리지 않는다."""

    window = MainWindow()
    qtbot.addWidget(window)
    stack = window.findChild(QStackedWidget, "subWindowStack")
    assert stack is not None
    stack.setCurrentIndex(3)

    window.show()
    qtbot.wait(0)

    table = window.findChild(QTableWidget, "testCaseTable")

    assert window.size() == DEFAULT_WINDOW_SIZE
    assert table is not None
    assert table.horizontalScrollBar().maximum() == 0


def test_test_manager_panel_test_case_table_distributes_extra_width(qtbot) -> None:
    """넓은 화면에서 마지막 열만 과하게 늘어나지 않게 폭을 배분한다."""

    panel = ManagerPanel()
    qtbot.addWidget(panel)
    panel.resize(1700, 760)
    panel.show()
    qtbot.wait(0)

    table = panel.findChild(QTableWidget, "testCaseTable")
    assert table is not None

    generation_width = table.columnWidth(0)
    modulation_width = table.columnWidth(5)
    rb_allocation_width = table.columnWidth(6)
    arfc_width = table.columnWidth(10)
    pol_width = table.columnWidth(16)

    assert table.horizontalScrollBar().maximum() == 0
    assert pol_width < modulation_width
    assert pol_width < rb_allocation_width
    assert pol_width < arfc_width
    assert modulation_width > generation_width


def test_test_manager_panel_exposes_planned_layout_widgets(qtbot) -> None:
    """Test Manager 레이아웃의 주요 위젯 objectName을 제공한다."""

    panel = ManagerPanel()
    qtbot.addWidget(panel)

    for object_name in (
        "eutNameEdit",
        "excelTemplatePathEdit",
        "screenshotRootEdit",
    ):
        assert panel.findChild(QLineEdit, object_name) is not None

    for object_name in (
        "excelTemplateBrowseButton",
        "screenshotRootBrowseButton",
        "startButton",
        "pauseButton",
        "deleteButton",
        "clearButton",
        "loadItemButton",
        "saveItemButton",
    ):
        assert panel.findChild(QPushButton, object_name) is not None

    for object_name in (
        "connectionGroupBox",
        "turnTableGroupBox",
        "polarizationGroupBox",
        "infoGroupBox",
    ):
        assert panel.findChild(QGroupBox, object_name) is not None

    assert panel.findChild(QWidget, "technologyButtonPanel") is not None


def test_log_panel_mirrors_logging_messages(qtbot) -> None:
    """LogPanel이 logging 메시지를 QPlainTextEdit에 표시한다."""

    logger = logging.getLogger("tests.ui.log_panel")
    original_level = logger.level
    original_propagate = logger.propagate
    original_handlers = list(logger.handlers)
    for handler in original_handlers:
        logger.removeHandler(handler)

    logger.setLevel(logging.INFO)
    logger.propagate = False
    panel = LogPanel(logger=logger)
    qtbot.addWidget(panel)

    try:
        logger.info("hello ui log")

        qtbot.waitUntil(
            lambda: "hello ui log" in panel.text_edit.toPlainText(),
            timeout=1000,
        )

        log_edit = panel.findChild(QPlainTextEdit, "logTextEdit")
        assert log_edit is not None
        assert log_edit.isReadOnly()
    finally:
        panel.detach_logging()
        logger.setLevel(original_level)
        logger.propagate = original_propagate
        for handler in list(logger.handlers):
            logger.removeHandler(handler)
        for handler in original_handlers:
            logger.addHandler(handler)


def test_test_manager_panel_has_right_log_panel(qtbot) -> None:
    """Test Manager 오른쪽 전체 높이에 로그 패널을 배치한다."""

    panel = ManagerPanel()
    qtbot.addWidget(panel)
    panel.resize(1100, 700)
    panel.show()
    qtbot.wait(0)

    content_panel = panel.findChild(QWidget, "testManagerContentPanel")
    log_panel = panel.findChild(LogPanel, "testManagerLogPanel")
    log_edit = panel.findChild(QPlainTextEdit, "logTextEdit")

    assert content_panel is not None
    assert log_panel is not None
    assert log_edit is not None
    assert log_panel.x() > content_panel.x()
    assert log_panel.y() == 0
    assert log_panel.width() == 280
    assert log_panel.height() == panel.height()
    assert log_edit.y() == 0
    assert log_edit.height() == log_panel.height()
    assert log_edit.isReadOnly()


def test_test_manager_panel_buttons_have_visible_text(qtbot) -> None:
    """Test Manager 주요 버튼이 화면에 표시할 문구를 가진다."""

    panel = ManagerPanel()
    qtbot.addWidget(panel)

    expected_button_texts = {
        "excelTemplateBrowseButton": "찾기",
        "screenshotRootBrowseButton": "찾기",
        "startButton": "시작",
        "pauseButton": "일시정지",
        "deleteButton": "삭제",
        "clearButton": "초기화",
        "loadItemButton": "불러오기",
        "saveItemButton": "저장",
        "nrButton": "NR",
        "lteButton": "LTE",
        "wcdmaButton": "WCDMA",
        "gsmButton": "GSM",
        "caseConfirmButton": "Case 확인(1~6)",
    }

    for object_name, expected_text in expected_button_texts.items():
        button = panel.findChild(QPushButton, object_name)

        assert button is not None
        assert button.text().strip()
        assert button.text() == expected_text


def test_test_manager_panel_technology_buttons_match_info_group_height(
    qtbot,
) -> None:
    """우측 RAT/Case 버튼 영역을 Info 박스 높이에 맞춘다."""

    panel = ManagerPanel()
    qtbot.addWidget(panel)
    panel.resize(1100, 700)
    panel.show()
    qtbot.wait(0)

    action_button = panel.findChild(QPushButton, "startButton")
    save_button = panel.findChild(QPushButton, "saveItemButton")
    info_group = panel.findChild(QGroupBox, "infoGroupBox")
    technology_panel = panel.findChild(QWidget, "technologyButtonPanel")

    assert action_button is not None
    assert save_button is not None
    assert info_group is not None
    assert technology_panel is not None
    assert action_button.height() == 38
    assert technology_panel.y() == info_group.y()
    assert technology_panel.height() == info_group.height()
    assert technology_panel.y() - (save_button.y() + save_button.height()) == 12

    button_heights = []
    for object_name in (
        "nrButton",
        "lteButton",
        "wcdmaButton",
        "gsmButton",
        "caseConfirmButton",
    ):
        button = panel.findChild(QPushButton, object_name)

        assert button is not None
        assert button.width() == 120
        assert button.height() >= action_button.height()
        assert button.minimumWidth() == 120
        assert button.maximumWidth() == 120
        assert button.minimumHeight() == 38
        button_heights.append(button.height())

    assert sum(button_heights) + (8 * 4) == technology_panel.height()


def test_test_manager_panel_excel_browse_button_sets_selected_path(
    qtbot,
    monkeypatch,
    tmp_path,
) -> None:
    """Excel 양식 찾기 버튼이 선택한 파일 경로를 입력칸에 반영한다."""

    panel = ManagerPanel()
    qtbot.addWidget(panel)
    selected_path = tmp_path / "report_template.xlsx"

    def fake_get_open_file_name(
        parent,
        caption,
        directory,
        selected_filter,
    ) -> tuple[str, str]:
        assert parent is panel
        assert caption == "Excel 양식 선택"
        assert selected_filter == "Excel Files (*.xlsx *.xlsm);;All Files (*)"
        return str(selected_path), "Excel Files (*.xlsx *.xlsm)"

    monkeypatch.setattr(QFileDialog, "getOpenFileName", fake_get_open_file_name)

    panel.findChild(QPushButton, "excelTemplateBrowseButton").click()

    edit = panel.findChild(QLineEdit, "excelTemplatePathEdit")
    assert edit is not None
    assert edit.text() == str(selected_path)
    assert panel.excel_template_path == selected_path


def test_test_manager_panel_screenshot_browse_button_sets_selected_directory(
    qtbot,
    monkeypatch,
    tmp_path,
) -> None:
    """스크린샷 저장 경로 찾기 버튼이 선택한 폴더를 입력칸에 반영한다."""

    panel = ManagerPanel()
    qtbot.addWidget(panel)
    selected_dir = tmp_path / "screenshots"

    def fake_get_existing_directory(parent, caption, directory) -> str:
        assert parent is panel
        assert caption == "스크린샷 저장 경로 선택"
        return str(selected_dir)

    monkeypatch.setattr(
        QFileDialog,
        "getExistingDirectory",
        fake_get_existing_directory,
    )

    panel.findChild(QPushButton, "screenshotRootBrowseButton").click()

    edit = panel.findChild(QLineEdit, "screenshotRootEdit")
    assert edit is not None
    assert edit.text() == str(selected_dir)
    assert panel.screenshot_root_dir == selected_dir


def test_test_manager_panel_only_eut_name_is_user_editable(qtbot) -> None:
    """EUT Name 외 입력 필드는 직접 편집하지 못하게 제한한다."""

    panel = ManagerPanel()
    qtbot.addWidget(panel)

    for edit in panel.findChildren(QLineEdit):
        if edit.objectName() == "eutNameEdit":
            assert not edit.isReadOnly()
        else:
            assert edit.isReadOnly(), edit.objectName()


def test_nr_select_dialog_can_be_created(qtbot) -> None:
    """NR 선택 팝업 스캐폴드를 독립적으로 생성할 수 있다."""

    dialog = NRSelectDialog()
    qtbot.addWidget(dialog)

    assert dialog.windowTitle() == "NR Select"
