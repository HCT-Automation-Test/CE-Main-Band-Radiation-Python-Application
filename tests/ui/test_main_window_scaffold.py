"""MainWindow 서브 패널 스캐폴드 테스트."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QGroupBox,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QWidget,
)

from app.ui.instrument_check_panel import InstrumentCheckPanel
from app.ui.main_window import MainWindow
from app.ui.manual_test_panel import ManualTestPanel
from app.ui.nr_select import NRSelectDialog
from app.ui.rf_filter_box_panel import RFFilterBoxPanel
from app.ui.test_manager_panel import TestManagerPanel as ManagerPanel
from app.ui.test_plot_screenshot_panel import (
    TestPlotScreenshotPanel as PlotScreenshotPanel,
)


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


def test_nr_select_dialog_can_be_created(qtbot) -> None:
    """NR 선택 팝업 스캐폴드를 독립적으로 생성할 수 있다."""

    dialog = NRSelectDialog()
    qtbot.addWidget(dialog)

    assert dialog.windowTitle() == "NR Select"
