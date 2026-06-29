"""MainWindow 서브 패널 스캐폴드 테스트."""
from __future__ import annotations

import logging
import threading
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtGui import QDoubleValidator, QIntValidator
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGroupBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QWidget,
)

from app.core.instrument_connection import (
    CONNECTION_IN_PROGRESS_MESSAGE,
    INSTRUMENT_SET_IN_PROGRESS_MESSAGE,
    build_equipment_connection_config,
    disconnected_equipment_state,
)
from app.core.runner import (
    INSTRUMENT_CONNECTION_BLOCK_MESSAGE,
    INSTRUMENT_SET_BLOCK_MESSAGE,
)
from app.models.enums import (
    AntennaPol,
    FilterPath,
    InputPath,
    DUTAntPosition,
    DUTAxis,
    Modulation,
    NRBand,
    RBAllocation,
    TestChannel as NRTestChannel,
    TestType as NRTestType,
)
from app.models.test_case import TestCase
from app.ui.instrument_check_panel import InstrumentCheckPanel
from app.ui.log_panel import LogPanel
from app.ui.main_window import MainWindow, RF_SWITCH_BOX_OPERATION_IN_PROGRESS_MESSAGE
from app.ui.manual_marker_dialog import ManualMarkerDialog
from app.ui.manual_test_panel import ManualTestPanel
from app.ui.nr_select import NRSelectDialog
from app.ui.rf_filter_box_panel import RFFilterBoxPanel
from app.ui.test_manager_panel import (
    _TABLE_COLUMN_BASE_WIDTHS,
    TestManagerPanel as ManagerPanel,
)
from app.ui.test_plot_screenshot_panel import (
    TestPlotScreenshotPanel as PlotScreenshotPanel,
)

DEFAULT_WINDOW_SIZE = QSize(1760, 940)
UNBOUNDED_WINDOW_SIZE = QSize(16777215, 16777215)


def _make_test_case() -> TestCase:
    return TestCase(
        band=NRBand.N78,
        bandwidth=100.0,
        test_type=NRTestType.HARMONIC,
        modulation=Modulation.QPSK,
        rb_allocation=RBAllocation.INNER_FULL,
        test_channel=NRTestChannel.MID,
        antenna_pol=AntennaPol.H,
        dut_axis=DUTAxis.X,
        dut_ant_position=DUTAntPosition.UPPER,
    )


def test_main_window_has_five_navigation_buttons_and_four_pages(qtbot) -> None:
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
    assert stack.count() == 4


def test_main_window_pages_use_expected_panel_classes(qtbot) -> None:
    """각 전환 페이지가 역할에 맞는 패널 클래스를 포함한다."""

    window = MainWindow()
    qtbot.addWidget(window)

    stack = window.findChild(QStackedWidget, "subWindowStack")
    assert stack is not None

    expected_panels = [
        InstrumentCheckPanel,
        ManualTestPanel,
        ManagerPanel,
        PlotScreenshotPanel,
    ]

    for index, panel_class in enumerate(expected_panels):
        page = stack.widget(index)
        assert page.findChild(panel_class) is not None


def test_main_window_rf_filter_box_button_opens_modeless_window(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    rf_window = window._rf_switch_box_window
    assert rf_window is not None
    assert rf_window.parent() is None
    assert not rf_window.isVisible()

    button = window.findChild(QPushButton, "rfFilterBoxNavigationButton")
    button.click()
    qtbot.wait(0)

    assert rf_window.isVisible()
    assert rf_window.findChild(RFFilterBoxPanel) is not None
    stack = window.findChild(QStackedWidget, "subWindowStack")
    assert stack is not None
    assert stack.count() == 4


def test_rf_switch_box_window_maximize_close_hides_and_reopen_keeps_state(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    rf_window = window._rf_switch_box_window
    button = window.findChild(QPushButton, "rfFilterBoxNavigationButton")
    assert rf_window is not None
    assert button is not None

    button.click()
    qtbot.waitUntil(rf_window.isVisible, timeout=1000)
    rf_window.showMaximized()
    qtbot.waitUntil(rf_window.isMaximized, timeout=1000)

    panel = rf_window.findChild(RFFilterBoxPanel)
    assert panel is not None
    panel.set_switch_box_info(
        {"input_path": InputPath.INPUT2, "filter_path": FilterPath.HPF_6G}
    )

    rf_window.close()
    qtbot.waitUntil(lambda: not rf_window.isVisible(), timeout=1000)
    assert window._rf_switch_box_window is rf_window

    button.click()
    qtbot.waitUntil(rf_window.isVisible, timeout=1000)

    assert rf_window.findChild(RFFilterBoxPanel) is panel
    assert panel.findChild(QLabel, "currentInputLabel").text() == "Input: 3M HORN"
    assert panel.findChild(QLabel, "currentFilterLabel").text() == "Filter: 6 GHz HPF"

def test_rf_switch_box_window_minimize_reopen_keeps_state(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    rf_window = window._rf_switch_box_window
    button = window.findChild(QPushButton, "rfFilterBoxNavigationButton")
    assert rf_window is not None
    assert button is not None

    button.click()
    qtbot.waitUntil(rf_window.isVisible, timeout=1000)
    panel = rf_window.findChild(RFFilterBoxPanel)
    assert panel is not None
    panel.set_switch_box_info(
        {"input_path": InputPath.INPUT2, "filter_path": FilterPath.HPF_6G}
    )

    rf_window.showMinimized()
    qtbot.waitUntil(rf_window.isMinimized, timeout=1000)

    button.click()
    qtbot.waitUntil(
        lambda: rf_window.isVisible() and not rf_window.isMinimized(),
        timeout=1000,
    )

    assert rf_window.findChild(RFFilterBoxPanel) is panel
    assert panel.findChild(QLabel, "currentInputLabel").text() == "Input: 3M HORN"
    assert panel.findChild(QLabel, "currentFilterLabel").text() == "Filter: 6 GHz HPF"


def test_main_window_user_action_popup_completes_runner_action(
    qtbot,
    monkeypatch,
) -> None:
    """수동 조작 요청 팝업의 완료 버튼이 Runner 완료 입력으로 이어진다."""

    window = MainWindow()
    qtbot.addWidget(window)
    completed: list[bool] = []

    def fake_user_action_completed() -> None:
        completed.append(True)

    monkeypatch.setattr(
        window._runner,
        "user_action_completed",
        fake_user_action_completed,
    )

    window._runner.events.user_action_required.emit("DUT Axis 변경: X -> Y")

    qtbot.waitUntil(
        lambda: (
            window.findChild(QDialog, "userActionRequiredDialog") is not None
            and window.findChild(QDialog, "userActionRequiredDialog").isVisible()
        ),
        timeout=1000,
    )
    dialog = window.findChild(QDialog, "userActionRequiredDialog")
    assert dialog is not None
    assert dialog.windowTitle() == "User Action Required"
    label = dialog.findChild(QLabel, "userActionRequiredLabel")
    complete_button = dialog.findChild(QPushButton, "userActionCompleteButton")
    stop_button = dialog.findChild(QPushButton, "userActionStopButton")

    assert label is not None
    assert label.text() == "DUT Axis 변경: X -> Y"
    assert complete_button is not None
    assert complete_button.text() == "완료"
    assert stop_button is not None
    assert stop_button.text() == "중단"

    complete_button.click()

    qtbot.waitUntil(lambda: completed == [True], timeout=1000)
    assert not dialog.isVisible()


def test_main_window_user_action_popup_stops_runner_action(
    qtbot,
    monkeypatch,
) -> None:
    """수동 조작 중단 버튼이 Runner 중단 입력으로 이어진다."""

    window = MainWindow()
    qtbot.addWidget(window)
    stopped: list[bool] = []

    def fake_stop() -> None:
        stopped.append(True)

    monkeypatch.setattr(window._runner, "stop", fake_stop)

    window._runner.events.user_action_required.emit("DUT Axis 변경: X -> Y")

    qtbot.waitUntil(
        lambda: (
            window.findChild(QDialog, "userActionRequiredDialog") is not None
            and window.findChild(QDialog, "userActionRequiredDialog").isVisible()
        ),
        timeout=1000,
    )
    dialog = window.findChild(QDialog, "userActionRequiredDialog")
    assert dialog is not None
    stop_button = dialog.findChild(QPushButton, "userActionStopButton")

    assert stop_button is not None
    assert stop_button.text() == "중단"

    stop_button.click()

    qtbot.waitUntil(lambda: stopped == [True], timeout=1000)
    assert not dialog.isVisible()


def test_main_window_user_action_popup_ignores_reject(qtbot) -> None:
    """수동 조작 팝업은 Esc/reject만으로 닫히지 않는다."""

    window = MainWindow()
    qtbot.addWidget(window)

    window._runner.events.user_action_required.emit("DUT Axis 변경: X -> Y")

    qtbot.waitUntil(
        lambda: (
            window.findChild(QDialog, "userActionRequiredDialog") is not None
            and window.findChild(QDialog, "userActionRequiredDialog").isVisible()
        ),
        timeout=1000,
    )
    dialog = window.findChild(QDialog, "userActionRequiredDialog")
    assert dialog is not None

    dialog.reject()
    qtbot.wait(50)

    assert dialog.isVisible()
    assert window.findChild(QDialog, "userActionRequiredDialog") is dialog


def test_main_window_session_finished_shows_completion_popup(
    qtbot,
    monkeypatch,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    infos: list[tuple[str, str]] = []

    monkeypatch.setattr(
        window,
        "_show_info",
        lambda title, message: infos.append((title, message)),
    )

    window._runner.events.session_finished.emit()

    assert infos == [("시험 완료", "모든 시험이 완료되었습니다.")]


def test_main_window_wires_runner_owned_instrument_service(qtbot) -> None:
    """Instrument Check가 Runner 소유 연결 서비스를 사용한다."""

    window = MainWindow()
    qtbot.addWidget(window)

    instrument_panel = window.findChild(InstrumentCheckPanel)

    assert instrument_panel is not None
    assert instrument_panel.service() is window._runner.instrument_connection_service


def test_main_window_start_button_is_blocked_until_equipment_ready(
    qtbot,
    monkeypatch,
    tmp_path,
) -> None:
    """장비 준비 전 시작 버튼은 Runner gate에서 차단된다."""

    window = MainWindow()
    qtbot.addWidget(window)
    messages: list[str] = []
    window._runner.events.error.connect(messages.append)
    template_path = tmp_path / "template.xlsx"
    screenshot_root = tmp_path / "default-screenshots"
    template_path.write_bytes(b"template")
    monkeypatch.setattr(
        "app.ui.test_manager_panel.default_screenshot_root_dir",
        lambda: screenshot_root,
    )
    window.findChild(QLineEdit, "eutNameEdit").setText("SM-000")
    window.findChild(QLineEdit, "excelTemplatePathEdit").setText(str(template_path))
    window._test_manager_panel.set_active_tdf_file_name("NR_Radiated.tdf")

    start_button = window.findChild(QPushButton, "startButton")
    assert start_button is not None

    start_button.click()

    assert messages == ["시험 시작 실패: Instrument Check 연결을 완료하세요"]


def test_main_window_stop_button_requests_runner_stop(qtbot, monkeypatch) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    stops: list[bool] = []
    monkeypatch.setattr(window._runner, "stop", lambda: stops.append(True))

    window._runner._set_measurement_active(True)

    stop_button = window.findChild(QPushButton, "stopButton")
    assert stop_button is not None
    assert stop_button.isEnabled()

    stop_button.click()

    assert stops == [True]

    window._runner._set_measurement_active(False)

    assert not stop_button.isEnabled()


def test_main_window_locks_tdf_controls_while_measurement_active(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    get_tdf_button = window.findChild(QPushButton, "getTdfListButton")
    tdf_all_off_button = window.findChild(QPushButton, "tdfAllOffButton")
    set_tdf_button = window.findChild(QPushButton, "setTdfButton")
    tdf_list = window.findChild(QListWidget, "tdfListWidget")

    assert get_tdf_button is not None
    assert tdf_all_off_button is not None
    assert set_tdf_button is not None
    assert tdf_list is not None
    assert get_tdf_button.isEnabled()
    assert tdf_all_off_button.isEnabled()
    assert set_tdf_button.isEnabled()
    assert tdf_list.isEnabled()

    window._runner._set_measurement_active(True)

    assert not get_tdf_button.isEnabled()
    assert not tdf_all_off_button.isEnabled()
    assert not set_tdf_button.isEnabled()
    assert not tdf_list.isEnabled()

    window._runner._set_measurement_active(False)

    assert get_tdf_button.isEnabled()
    assert tdf_all_off_button.isEnabled()
    assert set_tdf_button.isEnabled()
    assert tdf_list.isEnabled()


def test_main_window_keeps_tdf_controls_locked_when_tdf_finishes_during_measurement(
    qtbot,
    monkeypatch,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    monkeypatch.setattr(window, "_show_info", lambda title, message: None)

    get_tdf_button = window.findChild(QPushButton, "getTdfListButton")
    tdf_all_off_button = window.findChild(QPushButton, "tdfAllOffButton")
    set_tdf_button = window.findChild(QPushButton, "setTdfButton")
    tdf_list = window.findChild(QListWidget, "tdfListWidget")

    assert get_tdf_button is not None
    assert tdf_all_off_button is not None
    assert set_tdf_button is not None
    assert tdf_list is not None

    window.on_tdf_operation_started()
    window._runner._set_measurement_active(True)
    window.on_tdf_operation_finished("done")

    assert not get_tdf_button.isEnabled()
    assert not tdf_all_off_button.isEnabled()
    assert not set_tdf_button.isEnabled()
    assert not tdf_list.isEnabled()

    window._runner._set_measurement_active(False)

    assert get_tdf_button.isEnabled()
    assert tdf_all_off_button.isEnabled()
    assert set_tdf_button.isEnabled()
    assert tdf_list.isEnabled()


def test_main_window_keeps_tdf_controls_locked_when_tdf_fails_during_measurement(
    qtbot,
    monkeypatch,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    monkeypatch.setattr(window, "_show_warning", lambda title, message: None)

    get_tdf_button = window.findChild(QPushButton, "getTdfListButton")
    tdf_all_off_button = window.findChild(QPushButton, "tdfAllOffButton")
    set_tdf_button = window.findChild(QPushButton, "setTdfButton")
    tdf_list = window.findChild(QListWidget, "tdfListWidget")

    assert get_tdf_button is not None
    assert tdf_all_off_button is not None
    assert set_tdf_button is not None
    assert tdf_list is not None

    window.on_tdf_operation_started()
    window._runner._set_measurement_active(True)
    window.on_tdf_operation_failed("boom")

    assert not get_tdf_button.isEnabled()
    assert not tdf_all_off_button.isEnabled()
    assert not set_tdf_button.isEnabled()
    assert not tdf_list.isEnabled()

    window._runner._set_measurement_active(False)

    assert get_tdf_button.isEnabled()
    assert tdf_all_off_button.isEnabled()
    assert set_tdf_button.isEnabled()
    assert tdf_list.isEnabled()

def test_main_window_blocks_instrument_connect_while_measurement_active(
    qtbot,
    monkeypatch,
) -> None:
    """측정 중에는 버튼과 service guard가 모두 Instrument Check 연결을 막는다."""

    window = MainWindow()
    qtbot.addWidget(window)
    instrument_panel = window.findChild(InstrumentCheckPanel)
    connect_button = window.findChild(QPushButton, "connectInstrumentButton")
    assert instrument_panel is not None
    assert connect_button is not None
    monkeypatch.setattr(instrument_panel, "_show_warning", lambda message: None)

    window._runner._set_measurement_active(True)

    assert not connect_button.isEnabled()

    config = build_equipment_connection_config(
        mt8000a_visa_resource="MT",
        fsv40_visa_resource="FS",
        co3000_visa_resource="CO",
        controller_3d_visa_resource="3D",
        switch_box_ip_address="192.168.0.10",
        switch_box_port=5000,
    )
    with qtbot.waitSignal(
        window._runner.instrument_connection_service.error_occurred,
        timeout=1000,
    ) as blocker:
        window._runner.instrument_connection_service.connect_equipment(config)

    assert blocker.args == [INSTRUMENT_CONNECTION_BLOCK_MESSAGE]

    window._runner._set_measurement_active(False)

    assert connect_button.isEnabled()


def test_main_window_page_content_aligns_with_navigation_panel(qtbot) -> None:
    """좌측 버튼 영역과 우측 sub panel content 영역의 위치/크기를 맞춘다."""

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
    stack.setCurrentIndex(2)

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

    column_widths = [table.columnWidth(column) for column in range(table.columnCount())]
    total_width = sum(column_widths)
    viewport_width = table.viewport().width()

    assert table.horizontalScrollBar().maximum() == 0
    assert total_width == viewport_width

    for column in (0, 5, 6, 8, 16):
        expected_ratio = (
            _TABLE_COLUMN_BASE_WIDTHS[column] / sum(_TABLE_COLUMN_BASE_WIDTHS)
        )
        actual_ratio = column_widths[column] / total_width
        assert actual_ratio == pytest.approx(expected_ratio, abs=0.003)

    assert column_widths[16] < column_widths[5]
    assert column_widths[16] < column_widths[6]


def test_test_manager_panel_exposes_planned_layout_widgets(qtbot) -> None:
    """Test Manager 레이아웃의 주요 위젯 objectName을 제공한다."""

    panel = ManagerPanel()
    qtbot.addWidget(panel)

    for object_name in (
        "eutNameEdit",
        "excelTemplatePathEdit",
    ):
        assert panel.findChild(QLineEdit, object_name) is not None

    for object_name in (
        "excelTemplateBrowseButton",
        "startButton",
        "stopButton",
        "deleteButton",
        "clearButton",
        "loadItemButton",
        "saveItemButton",
        "getTdfListButton",
        "tdfAllOffButton",
        "setTdfButton",
    ):
        assert panel.findChild(QPushButton, object_name) is not None

    for object_name in (
        "connectionGroupBox",
        "turnTableGroupBox",
        "polarizationGroupBox",
        "tdfGroupBox",
        "infoGroupBox",
    ):
        assert panel.findChild(QGroupBox, object_name) is not None

    tdf_list = panel.findChild(QListWidget, "tdfListWidget")
    assert tdf_list is not None
    assert tdf_list.selectionMode() == QAbstractItemView.SelectionMode.SingleSelection
    assert panel.findChild(QWidget, "technologyButtonPanel") is not None


def test_test_manager_panel_places_tdf_between_polarization_and_info(qtbot) -> None:
    """TDF 영역을 Polarization과 Info 사이에 배치한다."""

    panel = ManagerPanel()
    qtbot.addWidget(panel)
    panel.resize(1500, 760)
    panel.show()
    qtbot.wait(0)

    polarization_group = panel.findChild(QGroupBox, "polarizationGroupBox")
    tdf_group = panel.findChild(QGroupBox, "tdfGroupBox")
    info_group = panel.findChild(QGroupBox, "infoGroupBox")

    assert polarization_group is not None
    assert tdf_group is not None
    assert info_group is not None
    polarization_x = polarization_group.mapTo(panel, QPoint(0, 0)).x()
    tdf_x = tdf_group.mapTo(panel, QPoint(0, 0)).x()
    info_x = info_group.mapTo(panel, QPoint(0, 0)).x()
    assert polarization_x < tdf_x < info_x


def test_test_manager_panel_set_tdf_requires_selection(qtbot, monkeypatch) -> None:
    panel = ManagerPanel()
    qtbot.addWidget(panel)
    warnings: list[str] = []
    emitted: list[str] = []
    monkeypatch.setattr(panel, "_show_warning", warnings.append)
    panel.set_tdf_requested.connect(emitted.append)

    panel.findChild(QPushButton, "setTdfButton").click()

    assert warnings == ["활성화할 TDF 파일을 선택하세요."]
    assert emitted == []


def test_test_manager_panel_marks_active_tdf_without_changing_text(qtbot) -> None:
    panel = ManagerPanel()
    qtbot.addWidget(panel)

    panel.set_tdf_file_list(["a.tdf", "b.tdf"])
    panel.set_active_tdf_file_name("b.tdf")

    tdf_list = panel.findChild(QListWidget, "tdfListWidget")
    assert tdf_list is not None
    assert [tdf_list.item(row).text() for row in range(tdf_list.count())] == [
        "a.tdf",
        "b.tdf",
    ]
    assert tdf_list.item(0).background().style() == Qt.BrushStyle.NoBrush
    assert tdf_list.item(1).background().style() != Qt.BrushStyle.NoBrush
    assert not tdf_list.item(0).font().bold()
    assert not tdf_list.item(1).font().bold()


def test_test_manager_panel_clears_active_tdf_mark(qtbot) -> None:
    panel = ManagerPanel()
    qtbot.addWidget(panel)

    panel.set_tdf_file_list(["a.tdf", "b.tdf"])
    panel.set_active_tdf_file_name("b.tdf")
    panel.clear_active_tdf_file_name()

    tdf_list = panel.findChild(QListWidget, "tdfListWidget")
    assert tdf_list is not None
    assert all(
        tdf_list.item(row).background().style() == Qt.BrushStyle.NoBrush
        for row in range(tdf_list.count())
    )


def test_test_manager_panel_preserves_active_tdf_mark_on_list_refresh(qtbot) -> None:
    panel = ManagerPanel()
    qtbot.addWidget(panel)

    panel.set_tdf_file_list(["a.tdf", "b.tdf"])
    panel.set_active_tdf_file_name("b.tdf")
    panel.set_tdf_file_list(["b.tdf", "c.tdf"])

    tdf_list = panel.findChild(QListWidget, "tdfListWidget")
    assert tdf_list is not None
    assert tdf_list.item(0).text() == "b.tdf"
    assert tdf_list.item(0).background().style() != Qt.BrushStyle.NoBrush


def test_test_manager_panel_drops_active_tdf_mark_when_missing_from_refresh(qtbot) -> None:
    panel = ManagerPanel()
    qtbot.addWidget(panel)

    panel.set_tdf_file_list(["a.tdf", "b.tdf"])
    panel.set_active_tdf_file_name("b.tdf")
    panel.set_tdf_file_list(["a.tdf", "c.tdf"])

    tdf_list = panel.findChild(QListWidget, "tdfListWidget")
    assert tdf_list is not None
    assert all(
        tdf_list.item(row).background().style() == Qt.BrushStyle.NoBrush
        for row in range(tdf_list.count())
    )


def test_test_manager_panel_marks_test_case_progress_rows(qtbot) -> None:
    panel = ManagerPanel()
    qtbot.addWidget(panel)
    first_case = _make_test_case()
    second_case = _make_test_case()
    panel.add_test_cases([first_case, second_case])

    table = panel.findChild(QTableWidget, "testCaseTable")
    assert table is not None
    assert all(
        table.item(row, 0).background().style() == Qt.BrushStyle.NoBrush
        for row in range(table.rowCount())
    )

    panel.mark_current_test_case(first_case)

    assert table.item(0, 0).background().style() != Qt.BrushStyle.NoBrush
    assert table.item(1, 0).background().style() == Qt.BrushStyle.NoBrush

    running_color = table.item(0, 0).background().color().name()
    panel.mark_current_test_case(second_case)

    assert table.item(0, 0).background().style() == Qt.BrushStyle.NoBrush
    assert table.item(1, 0).background().color().name() == running_color

    panel.mark_test_case_completed(1)

    assert table.item(1, 0).background().style() != Qt.BrushStyle.NoBrush
    assert table.item(1, 0).background().color().name() != running_color

    completed_color = table.item(1, 0).background().color().name()
    panel.mark_current_test_case(second_case)
    panel.mark_current_test_case(first_case)

    assert table.item(1, 0).background().color().name() == completed_color


def test_test_manager_panel_resets_test_case_progress_rows(qtbot) -> None:
    panel = ManagerPanel()
    qtbot.addWidget(panel)
    case = _make_test_case()
    panel.add_test_cases([case])
    panel.mark_current_test_case(case)

    panel.reset_test_case_progress()

    table = panel.findChild(QTableWidget, "testCaseTable")
    assert table is not None
    assert table.item(0, 0).background().style() == Qt.BrushStyle.NoBrush


def test_test_manager_panel_keeps_progress_state_in_sync_when_rows_change(qtbot) -> None:
    panel = ManagerPanel()
    qtbot.addWidget(panel)
    first_case = _make_test_case()
    second_case = _make_test_case()
    panel.add_test_cases([first_case, second_case])
    panel.mark_current_test_case(second_case)
    table = panel.findChild(QTableWidget, "testCaseTable")
    assert table is not None

    table.selectRow(0)
    panel.findChild(QPushButton, "deleteButton").click()

    assert table.rowCount() == 1
    assert table.item(0, 0).background().style() != Qt.BrushStyle.NoBrush

    panel.findChild(QPushButton, "clearButton").click()

    assert table.rowCount() == 0
    assert panel.test_cases == ()


def test_test_manager_panel_polarization_labels_match_physical_masts(qtbot) -> None:
    panel = ManagerPanel()
    qtbot.addWidget(panel)

    expected_labels = {
        "polarization3mEdit": "3m",
        "polarizationBilogEdit": "Bilog",
        "polarization1mEdit": "1m",
    }
    for object_name, expected_label in expected_labels.items():
        edit = panel.findChild(QLineEdit, object_name)
        assert edit is not None
        label = edit.parent().findChild(QLabel)
        assert label is not None
        assert label.text() == expected_label


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
        "startButton": "시작",
        "stopButton": "정지",
        "deleteButton": "삭제",
        "clearButton": "초기화",
        "loadItemButton": "불러오기",
        "saveItemButton": "저장",
        "getTdfListButton": "Get List",
        "tdfAllOffButton": "All Off",
        "setTdfButton": "Set TDF",
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


def test_case_confirm_button_opens_range_setting_dialog(qtbot) -> None:
    """Case 확인 버튼은 Range 1~6 세팅 값을 읽기 전용 팝업으로 표시한다."""

    panel = ManagerPanel()
    qtbot.addWidget(panel)

    button = panel.findChild(QPushButton, "caseConfirmButton")
    assert button is not None
    button.click()

    dialog = panel.findChild(QDialog, "rangeSettingDialog")
    table = panel.findChild(QTableWidget, "rangeSettingTable")

    assert dialog is not None
    assert table is not None
    assert dialog.isVisible()
    assert table.rowCount() == 6
    assert table.columnCount() == 11
    assert [table.horizontalHeaderItem(index).text() for index in range(11)] == [
        "Mode",
        "Range",
        "Start Freq",
        "Stop Freq",
        "RBW(MHz)",
        "VBW(MHz)",
        "Limit(dBm)",
        "Sweep point",
        "Mast",
        "Controller",
        "Filter",
    ]
    assert table.item(0, 0).text() == "Traffic"
    assert table.rowSpan(0, 0) == 6
    assert table.item(0, 1).text() == "1"
    assert table.item(0, 8).text() == "Mast2"
    assert table.item(1, 1).text() == "2"
    assert table.item(1, 8).text() == "Mast1"
    assert table.item(1, 9).text() == "CO3000"
    assert table.item(1, 10).text() == "BRF"
    assert table.item(5, 1).text() == "6"
    assert table.item(5, 8).text() == "Mast3"
    assert table.item(5, 9).text() == "TeraTerm"
    assert table.item(5, 10).text() == "6G HPF"

    dialog.close()


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



def test_test_manager_panel_run_setting_fields_are_user_editable(qtbot) -> None:
    """EUT Name과 실행 설정 입력 필드는 사용자가 직접 편집할 수 있다."""

    panel = ManagerPanel()
    qtbot.addWidget(panel)

    editable_names = {
        "eutNameEdit",
        "indexEdit",
        "saturationTimeEdit",
        "connectionWaitingTimeEdit",
        "attenLevelEdit",
        "nextPeakSearchLevelEdit",
        "customTurnTableSpeedEdit",
    }
    for edit in panel.findChildren(QLineEdit):
        if edit.objectName() in editable_names:
            assert not edit.isReadOnly()
        else:
            assert edit.isReadOnly(), edit.objectName()


def test_test_manager_panel_run_setting_defaults_and_label(qtbot) -> None:
    panel = ManagerPanel()
    qtbot.addWidget(panel)

    assert panel.findChild(QLineEdit, "saturationTimeEdit").text() == "5"
    assert panel.findChild(QLineEdit, "connectionWaitingTimeEdit").text() == "5"
    assert panel.findChild(QLineEdit, "attenLevelEdit").text() == "0"
    assert panel.findChild(QLineEdit, "nextPeakSearchLevelEdit").text() == "6"
    assert panel.findChild(QLineEdit, "customTurnTableSpeedEdit").text() == "5"
    assert not panel.findChild(QCheckBox, "customOptionCheckBox").isChecked()
    assert panel.findChild(QLineEdit, "turnTableSpeedEdit") is None
    assert any(
        label.text() == "Connection\nWaiting Time(s)"
        for label in panel.findChildren(QLabel)
    )


def test_test_manager_panel_run_setting_properties_and_validators(qtbot) -> None:
    """실행 설정 필드가 property와 숫자 validator를 제공한다."""

    panel = ManagerPanel()
    qtbot.addWidget(panel)

    panel.findChild(QLineEdit, "saturationTimeEdit").setText("6.5")
    panel.findChild(QLineEdit, "connectionWaitingTimeEdit").setText("7")
    panel.findChild(QLineEdit, "attenLevelEdit").setText("1.5")
    panel.findChild(QLineEdit, "nextPeakSearchLevelEdit").setText("60.5")
    panel.findChild(QLineEdit, "customTurnTableSpeedEdit").setText("8")
    panel.set_active_tdf_file_name("NR_Radiated.tdf")

    assert panel.saturation_time_sec == 6.5
    assert panel.connection_waiting_time_sec == 7
    assert panel.atten_level_db == 1.5
    assert panel.next_peak_search_level_db == 60.5
    assert panel.custom_turntable_speed == 8
    assert isinstance(
        panel.findChild(QLineEdit, "saturationTimeEdit").validator(),
        QDoubleValidator,
    )
    assert isinstance(
        panel.findChild(QLineEdit, "connectionWaitingTimeEdit").validator(),
        QIntValidator,
    )
    assert isinstance(
        panel.findChild(QLineEdit, "attenLevelEdit").validator(),
        QDoubleValidator,
    )
    next_peak_validator = panel.findChild(
        QLineEdit,
        "nextPeakSearchLevelEdit",
    ).validator()
    custom_speed_validator = panel.findChild(
        QLineEdit,
        "customTurnTableSpeedEdit",
    ).validator()
    assert isinstance(next_peak_validator, QDoubleValidator)
    assert next_peak_validator.bottom() == 0.0
    assert next_peak_validator.top() == 80.0
    assert isinstance(custom_speed_validator, QIntValidator)
    assert custom_speed_validator.bottom() == 1
    assert custom_speed_validator.top() == 10

    panel.findChild(QLineEdit, "saturationTimeEdit").setText("")
    panel.findChild(QLineEdit, "connectionWaitingTimeEdit").setText("1.5")
    panel.findChild(QLineEdit, "attenLevelEdit").setText("nan")
    panel.findChild(QLineEdit, "nextPeakSearchLevelEdit").setText("bad")
    panel.findChild(QLineEdit, "customTurnTableSpeedEdit").setText("1.5")

    assert panel.saturation_time_sec is None
    assert panel.connection_waiting_time_sec is None
    assert panel.atten_level_db is None
    assert panel.next_peak_search_level_db is None
    assert panel.custom_turntable_speed is None


def test_test_manager_panel_set_current_case_updates_display_fields(qtbot) -> None:
    """현재 TestCase setter가 모델에서 확정 가능한 표시값을 채운다."""

    panel = ManagerPanel()
    qtbot.addWidget(panel)
    case = _make_test_case()
    preserved_values = {
        "startFreqEdit": "keep start",
        "stopFreqEdit": "keep stop",
        "rbwEdit": "keep rbw",
        "vbwEdit": "keep vbw",
        "sweepPointEdit": "keep sweep",
        "filterEdit": "keep filter",
        "settingSpeedEdit": "keep speed",
        "traceModeEdit": "keep trace",
        "mastEdit": "keep mast",
    }
    for object_name, value in preserved_values.items():
        panel.findChild(QLineEdit, object_name).setText(value)

    panel.set_current_case(case)

    assert panel.findChild(QLineEdit, "currentTestBandEdit").text() == "n78"
    assert panel.findChild(QLineEdit, "currentTestFreqEdit").text() == "6-18G"
    assert panel.findChild(QLineEdit, "currentFactorEdit").text() == " / ".join(
        value if value else "-" for value in panel._row_values_for_case(case)
    )
    for object_name, value in preserved_values.items():
        assert panel.findChild(QLineEdit, object_name).text() == value


def test_main_window_updates_current_case_summary_from_runner_event(qtbot) -> None:
    """RunnerEvents가 현재 TestCase 변경을 알리면 요약 필드가 갱신된다."""

    window = MainWindow()
    qtbot.addWidget(window)
    case = _make_test_case()
    panel = window._test_manager_panel
    preserved_values = {
        "startFreqEdit": "keep start",
        "stopFreqEdit": "keep stop",
        "rbwEdit": "keep rbw",
        "vbwEdit": "keep vbw",
        "sweepPointEdit": "keep sweep",
        "filterEdit": "keep filter",
        "settingSpeedEdit": "keep speed",
        "mastEdit": "keep mast",
    }
    for object_name, value in preserved_values.items():
        panel.findChild(QLineEdit, object_name).setText(value)

    window._runner.events.current_case_changed.emit(case)

    assert panel.findChild(QLineEdit, "currentTestBandEdit").text() == "n78"
    assert panel.findChild(QLineEdit, "currentTestFreqEdit").text() == "6-18G"
    assert panel.findChild(QLineEdit, "currentFactorEdit").text() == " / ".join(
        value if value else "-" for value in panel._row_values_for_case(case)
    )
    for object_name, value in preserved_values.items():
        assert panel.findChild(QLineEdit, object_name).text() == value


def test_main_window_updates_test_case_progress_from_runner_events(
    qtbot,
    monkeypatch,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    monkeypatch.setattr(window, "_show_info", lambda title, message: None)
    first_case = _make_test_case()
    second_case = _make_test_case()
    panel = window._test_manager_panel
    panel.add_test_cases([first_case, second_case])
    table = panel.findChild(QTableWidget, "testCaseTable")
    assert table is not None

    window._runner.events.current_case_changed.emit(first_case)

    assert table.item(0, 0).background().style() != Qt.BrushStyle.NoBrush
    assert table.item(1, 0).background().style() == Qt.BrushStyle.NoBrush

    running_color = table.item(0, 0).background().color().name()
    window._runner.events.current_case_changed.emit(second_case)

    assert table.item(0, 0).background().style() == Qt.BrushStyle.NoBrush
    assert table.item(1, 0).background().color().name() == running_color

    window._runner.events.session_finished.emit()

    assert table.item(1, 0).background().color().name() == running_color

    window._runner.events.tc_finished.emit(1)

    assert table.item(1, 0).background().style() != Qt.BrushStyle.NoBrush
    assert table.item(1, 0).background().color().name() != running_color


def test_main_window_clears_running_progress_when_measurement_stops(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    case = _make_test_case()
    panel = window._test_manager_panel
    panel.add_test_cases([case])
    table = panel.findChild(QTableWidget, "testCaseTable")
    assert table is not None

    window._runner.events.current_case_changed.emit(case)

    assert table.item(0, 0).background().style() != Qt.BrushStyle.NoBrush

    window.on_measurement_active_changed(False)

    assert table.item(0, 0).background().style() == Qt.BrushStyle.NoBrush


def test_main_window_restores_completed_progress_when_measurement_stops(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    case = _make_test_case()
    panel = window._test_manager_panel
    panel.add_test_cases([case])
    table = panel.findChild(QTableWidget, "testCaseTable")
    assert table is not None
    panel.mark_test_case_completed(0)
    completed_color = table.item(0, 0).background().color().name()

    window._runner.events.current_case_changed.emit(case)

    assert table.item(0, 0).background().color().name() != completed_color

    window.on_measurement_active_changed(False)

    assert table.item(0, 0).background().color().name() == completed_color

def test_main_window_start_preserves_test_case_progress(
    qtbot,
    monkeypatch,
    tmp_path,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    panel = window._test_manager_panel
    case = _make_test_case()
    panel.add_test_cases([case])
    panel.mark_test_case_completed(0)
    table = panel.findChild(QTableWidget, "testCaseTable")
    assert table is not None
    completed_color = table.item(0, 0).background().color().name()
    panel.findChild(QLineEdit, "eutNameEdit").setText("DUT")
    template_path = tmp_path / "template.xlsx"
    template_path.write_bytes(b"template")
    panel.findChild(QLineEdit, "excelTemplatePathEdit").setText(str(template_path))
    panel.set_active_tdf_file_name("NR_Radiated.tdf")
    monkeypatch.setattr(window._runner, "start", lambda cases, **kwargs: None)

    window.on_start_requested()

    assert table.item(0, 0).background().color().name() == completed_color


def test_main_window_blocks_start_while_rf_switch_running(qtbot, monkeypatch) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    warnings: list[tuple[str, str]] = []
    starts: list[bool] = []
    monkeypatch.setattr(
        window,
        "_show_warning",
        lambda title, message: warnings.append((title, message)),
    )
    monkeypatch.setattr(
        window._test_manager_panel,
        "build_test_run_settings",
        lambda: pytest.fail("settings should not be built while RF command is running"),
    )
    monkeypatch.setattr(
        window._runner,
        "start",
        lambda cases, **kwargs: starts.append(True),
    )

    window._rf_switch_box_service._running = True
    try:
        window.on_start_requested()

        assert starts == []
        assert warnings == [
            ("RF Switch Box", RF_SWITCH_BOX_OPERATION_IN_PROGRESS_MESSAGE),
        ]
    finally:
        window._rf_switch_box_service._running = False


def test_main_window_blocks_start_without_active_tdf(
    qtbot,
    monkeypatch,
    tmp_path,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    panel = window._test_manager_panel
    panel.add_test_cases([_make_test_case()])
    panel.findChild(QLineEdit, "eutNameEdit").setText("DUT")
    template_path = tmp_path / "template.xlsx"
    template_path.write_bytes(b"template")
    panel.findChild(QLineEdit, "excelTemplatePathEdit").setText(str(template_path))
    warnings: list[str] = []
    starts: list[bool] = []
    monkeypatch.setattr(panel, "_show_warning", warnings.append)
    monkeypatch.setattr(
        window._runner,
        "start",
        lambda cases, **kwargs: starts.append(True),
    )

    window.on_start_requested()

    assert starts == []
    assert warnings == ["활성화된 TDF 파일이 없습니다."]


def test_main_window_start_preserves_completed_progress(
    qtbot,
    monkeypatch,
    tmp_path,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    panel = window._test_manager_panel
    first_case = _make_test_case()
    second_case = _make_test_case()
    panel.add_test_cases([first_case, second_case])
    panel.mark_test_case_completed(0)
    panel.mark_current_test_case(second_case)
    table = panel.findChild(QTableWidget, "testCaseTable")
    assert table is not None
    completed_color = table.item(0, 0).background().color().name()
    running_color = table.item(1, 0).background().color().name()
    panel.findChild(QLineEdit, "eutNameEdit").setText("DUT")
    template_path = tmp_path / "template.xlsx"
    template_path.write_bytes(b"template")
    panel.findChild(QLineEdit, "excelTemplatePathEdit").setText(str(template_path))
    panel.set_active_tdf_file_name("NR_Radiated.tdf")
    monkeypatch.setattr(window._runner, "start", lambda cases, **kwargs: None)

    window.on_start_requested()

    assert table.item(0, 0).background().color().name() == completed_color
    assert table.item(1, 0).background().color().name() == running_color

    window._runner.events.current_case_changed.emit(first_case)

    assert table.item(0, 0).background().color().name() == running_color
    assert table.item(1, 0).background().style() == Qt.BrushStyle.NoBrush


def test_main_window_stop_then_start_uses_edited_index(
    qtbot,
    monkeypatch,
    tmp_path,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    panel = window._test_manager_panel
    cases = [_make_test_case(), _make_test_case()]
    panel.add_test_cases(cases)
    panel.findChild(QLineEdit, "eutNameEdit").setText("DUT")
    template_path = tmp_path / "template.xlsx"
    template_path.write_bytes(b"template")
    panel.findChild(QLineEdit, "excelTemplatePathEdit").setText(str(template_path))
    panel.findChild(QLineEdit, "indexEdit").setText("1")
    panel.set_active_tdf_file_name("NR_Radiated.tdf")
    starts: list[dict[str, object]] = []
    monkeypatch.setattr(
        window._runner,
        "start",
        lambda cases, **kwargs: starts.append({"cases": cases, **kwargs}),
    )

    window.on_start_requested()

    assert starts
    assert starts[0]["cases"] == cases
    assert starts[0]["start_index"] == 0
    assert starts[0]["stop_index"] is None


def test_main_window_stop_then_single_start_uses_edited_index(
    qtbot,
    monkeypatch,
    tmp_path,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    panel = window._test_manager_panel
    cases = [_make_test_case(), _make_test_case()]
    panel.add_test_cases(cases)
    panel.findChild(QLineEdit, "eutNameEdit").setText("DUT")
    template_path = tmp_path / "template.xlsx"
    template_path.write_bytes(b"template")
    panel.findChild(QLineEdit, "excelTemplatePathEdit").setText(str(template_path))
    panel.findChild(QLineEdit, "indexEdit").setText("1")
    panel.set_active_tdf_file_name("NR_Radiated.tdf")
    starts: list[dict[str, object]] = []
    monkeypatch.setattr(
        window._runner,
        "start",
        lambda cases, **kwargs: starts.append({"cases": cases, **kwargs}),
    )

    panel.findChild(QPushButton, "singleStartButton").click()

    assert starts
    assert starts[0]["cases"] == cases
    assert starts[0]["start_index"] == 0
    assert starts[0]["stop_index"] == 0


def test_main_window_stop_then_start_blocks_out_of_range_index(
    qtbot,
    monkeypatch,
    tmp_path,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    panel = window._test_manager_panel
    panel.add_test_cases([_make_test_case()])
    panel.findChild(QLineEdit, "eutNameEdit").setText("DUT")
    template_path = tmp_path / "template.xlsx"
    template_path.write_bytes(b"template")
    panel.findChild(QLineEdit, "excelTemplatePathEdit").setText(str(template_path))
    panel.findChild(QLineEdit, "indexEdit").setText("2")
    panel.set_active_tdf_file_name("NR_Radiated.tdf")
    starts: list[bool] = []
    warnings: list[str] = []
    monkeypatch.setattr(panel, "_show_warning", warnings.append)
    monkeypatch.setattr(
        window._runner,
        "start",
        lambda cases, **kwargs: starts.append(True),
    )

    window.on_start_requested()

    assert starts == []
    assert warnings == ["Index가 Test Case 개수를 초과했습니다."]


def test_main_window_start_uses_blank_index_as_first_case(
    qtbot,
    monkeypatch,
    tmp_path,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    panel = window._test_manager_panel
    first_case = _make_test_case()
    second_case = _make_test_case()
    panel.add_test_cases([first_case, second_case])
    panel.findChild(QLineEdit, "eutNameEdit").setText("DUT")
    template_path = tmp_path / "template.xlsx"
    template_path.write_bytes(b"template")
    panel.findChild(QLineEdit, "excelTemplatePathEdit").setText(str(template_path))
    panel.findChild(QLineEdit, "indexEdit").clear()
    panel.set_active_tdf_file_name("NR_Radiated.tdf")
    starts: list[dict[str, object]] = []
    monkeypatch.setattr(
        window._runner,
        "start",
        lambda cases, **kwargs: starts.append({"cases": cases, **kwargs}),
    )

    window.on_start_requested()

    assert starts
    assert starts[0]["cases"] == [first_case, second_case]
    assert starts[0]["start_index"] == 0
    assert starts[0]["stop_index"] is None


def test_main_window_start_blocks_out_of_range_index(
    qtbot,
    monkeypatch,
    tmp_path,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    panel = window._test_manager_panel
    panel.add_test_cases([_make_test_case()])
    panel.findChild(QLineEdit, "eutNameEdit").setText("DUT")
    template_path = tmp_path / "template.xlsx"
    template_path.write_bytes(b"template")
    panel.findChild(QLineEdit, "excelTemplatePathEdit").setText(str(template_path))
    panel.findChild(QLineEdit, "indexEdit").setText("2")
    panel.set_active_tdf_file_name("NR_Radiated.tdf")
    starts: list[bool] = []
    warnings: list[str] = []
    monkeypatch.setattr(panel, "_show_warning", warnings.append)
    monkeypatch.setattr(
        window._runner,
        "start",
        lambda cases, **kwargs: starts.append(True),
    )

    window.on_start_requested()

    assert starts == []
    assert warnings == ["Index가 Test Case 개수를 초과했습니다."]


def test_main_window_single_start_runs_only_selected_index(
    qtbot,
    monkeypatch,
    tmp_path,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    panel = window._test_manager_panel
    cases = [_make_test_case(), _make_test_case()]
    panel.add_test_cases(cases)
    panel.findChild(QLineEdit, "eutNameEdit").setText("DUT")
    template_path = tmp_path / "template.xlsx"
    template_path.write_bytes(b"template")
    panel.findChild(QLineEdit, "excelTemplatePathEdit").setText(str(template_path))
    panel.findChild(QLineEdit, "indexEdit").setText("2")
    panel.set_active_tdf_file_name("NR_Radiated.tdf")
    starts: list[dict[str, object]] = []
    monkeypatch.setattr(
        window._runner,
        "start",
        lambda cases, **kwargs: starts.append({"cases": cases, **kwargs}),
    )

    panel.findChild(QPushButton, "singleStartButton").click()

    assert starts
    assert starts[0]["cases"] == cases
    assert starts[0]["start_index"] == 1
    assert starts[0]["stop_index"] == 1


def test_main_window_updates_analyzer_info_from_runner_event(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    panel = window._test_manager_panel

    window._runner.events.spectrum_analyzer_info_changed.emit(
        {
            "start_freq": 3449.99,
            "stop_freq": 3649.99,
            "trace_mode": "View",
            "rbw": 1.0,
            "vbw": 1.0,
            "sweep_point": 10001,
            "limit": -30,
        }
    )

    assert panel.findChild(QLineEdit, "startFreqEdit").text() == "3449.99"
    assert panel.findChild(QLineEdit, "stopFreqEdit").text() == "3649.99"
    assert panel.findChild(QLineEdit, "traceModeEdit").text() == "View"
    assert panel.findChild(QLineEdit, "rbwEdit").text() == "1"
    assert panel.findChild(QLineEdit, "vbwEdit").text() == "1"
    assert panel.findChild(QLineEdit, "sweepPointEdit").text() == "10001"


def test_main_window_updates_turntable_info_from_runner_event(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    panel = window._test_manager_panel

    window._runner.events.turntable_info_changed.emit(
        {
            "target_angle": 360.0,
            "current_angle": 123.4,
            "setting_speed": 4,
        }
    )

    assert panel.findChild(QLineEdit, "targetAngleEdit").text() == "360"
    assert panel.findChild(QLineEdit, "currentAngleEdit").text() == "123.4"
    assert panel.findChild(QLineEdit, "settingSpeedEdit").text() == "4"


def test_main_window_keeps_missing_turntable_fields_from_runner_event(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    panel = window._test_manager_panel

    panel.set_turntable_info(
        {
            "target_angle": 360,
            "current_angle": 0,
            "setting_speed": 4,
        }
    )

    window._runner.events.turntable_info_changed.emit({"current_angle": 180})

    assert panel.findChild(QLineEdit, "targetAngleEdit").text() == "360"
    assert panel.findChild(QLineEdit, "currentAngleEdit").text() == "180"
    assert panel.findChild(QLineEdit, "settingSpeedEdit").text() == "4"


def test_main_window_updates_switch_box_info_from_runner_event(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    panel = window._test_manager_panel

    window._runner.events.switch_box_info_changed.emit(
        {
            "mast": "Bilog",
            "filter": "Port 14",
        }
    )

    assert panel.findChild(QLineEdit, "mastEdit").text() == "Bilog"
    assert panel.findChild(QLineEdit, "filterEdit").text() == "Port 14"


def test_main_window_updates_polarization_info_from_runner_event(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    panel = window._test_manager_panel

    window._runner.events.polarization_info_changed.emit(
        {
            "polarization_3m": "H",
            "polarization_bilog": "V",
            "polarization_1m": "90°",
        }
    )

    assert panel.findChild(QLineEdit, "polarization3mEdit").text() == "H"
    assert panel.findChild(QLineEdit, "polarizationBilogEdit").text() == "V"
    assert panel.findChild(QLineEdit, "polarization1mEdit").text() == "90°"


def test_main_window_keeps_missing_polarization_fields_from_runner_event(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    panel = window._test_manager_panel

    panel.set_polarization_info(
        {
            "polarization_3m": "H",
            "polarization_bilog": "V",
            "polarization_1m": "90°",
        }
    )

    window._runner.events.polarization_info_changed.emit({"polarization_3m": "V"})

    assert panel.findChild(QLineEdit, "polarization3mEdit").text() == "V"
    assert panel.findChild(QLineEdit, "polarizationBilogEdit").text() == "V"
    assert panel.findChild(QLineEdit, "polarization1mEdit").text() == "90°"


def test_main_window_updates_co3000_polarization_pair_from_runner_event(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    panel = window._test_manager_panel

    panel.set_polarization_info(
        {
            "polarization_3m": "H",
            "polarization_bilog": "H",
            "polarization_1m": "0°",
        }
    )

    window._runner.events.polarization_info_changed.emit(
        {
            "polarization_3m": "V",
            "polarization_bilog": "V",
        }
    )

    assert panel.findChild(QLineEdit, "polarization3mEdit").text() == "V"
    assert panel.findChild(QLineEdit, "polarizationBilogEdit").text() == "V"
    assert panel.findChild(QLineEdit, "polarization1mEdit").text() == "0°"


def test_main_window_updates_1m_polarization_only_from_runner_event(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    panel = window._test_manager_panel

    panel.set_polarization_info(
        {
            "polarization_3m": "H",
            "polarization_bilog": "H",
            "polarization_1m": "0°",
        }
    )

    window._runner.events.polarization_info_changed.emit({"polarization_1m": "90°"})

    assert panel.findChild(QLineEdit, "polarization3mEdit").text() == "H"
    assert panel.findChild(QLineEdit, "polarizationBilogEdit").text() == "H"
    assert panel.findChild(QLineEdit, "polarization1mEdit").text() == "90°"


def test_main_window_keeps_switch_box_mast_after_analyzer_event(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    panel = window._test_manager_panel

    window._runner.events.switch_box_info_changed.emit(
        {
            "mast": "Bilog",
            "filter": "Port 14",
        }
    )
    window._runner.events.spectrum_analyzer_info_changed.emit(
        {
            "start_freq": 3449.99,
            "stop_freq": 3649.99,
            "trace_mode": "View",
            "rbw": 1.0,
            "vbw": 1.0,
            "sweep_point": 10001,
        }
    )

    assert panel.findChild(QLineEdit, "mastEdit").text() == "Bilog"
    assert panel.findChild(QLineEdit, "filterEdit").text() == "Port 14"
    assert panel.findChild(QLineEdit, "startFreqEdit").text() == "3449.99"
    assert panel.findChild(QLineEdit, "stopFreqEdit").text() == "3649.99"
    assert panel.findChild(QLineEdit, "traceModeEdit").text() == "View"
    assert panel.findChild(QLineEdit, "rbwEdit").text() == "1"
    assert panel.findChild(QLineEdit, "vbwEdit").text() == "1"
    assert panel.findChild(QLineEdit, "sweepPointEdit").text() == "10001"


def test_main_window_locks_start_settings_while_measurement_active(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    locked_edits = (
        "eutNameEdit",
        "indexEdit",
        "saturationTimeEdit",
        "connectionWaitingTimeEdit",
        "attenLevelEdit",
        "nextPeakSearchLevelEdit",
        "customTurnTableSpeedEdit",
    )
    path_edits = ("excelTemplatePathEdit",)
    browse_buttons = ("excelTemplateBrowseButton",)
    locked_buttons = (
        "singleStartButton",
        "startButton",
        "deleteButton",
        "clearButton",
        "loadItemButton",
        "saveItemButton",
        "nrButton",
        "lteButton",
        "wcdmaButton",
        "gsmButton",
    )
    unlocked_buttons = ("stopButton",)
    custom_option_check_box = window.findChild(QCheckBox, "customOptionCheckBox")
    marker_check_box = window.findChild(QCheckBox, "markerCheckBox")
    assert custom_option_check_box is not None
    assert marker_check_box is not None

    window._runner._set_measurement_active(True)

    for object_name in locked_edits:
        assert not window.findChild(QLineEdit, object_name).isEnabled()
    for object_name in path_edits:
        assert window.findChild(QLineEdit, object_name).isReadOnly()
    for object_name in browse_buttons:
        assert not window.findChild(QPushButton, object_name).isEnabled()
    for object_name in locked_buttons:
        assert not window.findChild(QPushButton, object_name).isEnabled()
    for object_name in unlocked_buttons:
        assert window.findChild(QPushButton, object_name).isEnabled()
    assert window.findChild(QPushButton, "caseConfirmButton").isEnabled()
    assert not custom_option_check_box.isEnabled()
    assert not marker_check_box.isEnabled()

    window._runner._set_measurement_active(False)

    for object_name in locked_edits:
        assert window.findChild(QLineEdit, object_name).isEnabled()
    for object_name in path_edits:
        assert window.findChild(QLineEdit, object_name).isReadOnly()
    for object_name in browse_buttons:
        assert window.findChild(QPushButton, object_name).isEnabled()
    for object_name in locked_buttons:
        assert window.findChild(QPushButton, object_name).isEnabled()
    assert not window.findChild(QPushButton, "stopButton").isEnabled()
    assert window.findChild(QPushButton, "caseConfirmButton").isEnabled()
    assert custom_option_check_box.isEnabled()
    assert marker_check_box.isEnabled()

    window._runner._set_measurement_active(True)

    for object_name in locked_buttons:
        assert not window.findChild(QPushButton, object_name).isEnabled()
    assert window.findChild(QPushButton, "caseConfirmButton").isEnabled()
    assert window.findChild(QPushButton, "stopButton").isEnabled()


def test_main_window_locks_instrument_operations_while_set_active(
    qtbot,
    monkeypatch,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    instrument_panel = window.findChild(InstrumentCheckPanel)
    connect_button = window.findChild(QPushButton, "connectInstrumentButton")
    service = window._runner.instrument_connection_service
    assert instrument_panel is not None
    assert connect_button is not None
    monkeypatch.setattr(instrument_panel, "_show_warning", lambda message: None)
    monkeypatch.setattr(instrument_panel, "_show_info", lambda message: None)
    failures: list[str] = []
    instrument_panel.connection_failed.connect(failures.append)

    service.set_started.emit()

    assert not connect_button.isEnabled()
    assert not window.findChild(QLineEdit, "eutNameEdit").isEnabled()

    instrument_panel.on_connect_clicked()

    assert failures == [INSTRUMENT_SET_BLOCK_MESSAGE]

    service.set_finished.emit()

    assert connect_button.isEnabled()
    assert window.findChild(QLineEdit, "eutNameEdit").isEnabled()


def test_main_window_blocks_instrument_connect_while_rf_switch_running(
    qtbot,
    monkeypatch,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    service = window._runner.instrument_connection_service
    instrument_panel = window.findChild(InstrumentCheckPanel)
    rf_panel = window._rf_filter_box_panel
    assert instrument_panel is not None
    assert rf_panel is not None
    monkeypatch.setattr(instrument_panel, "_show_warning", lambda message: None)
    rf_panel.set_connection_state({"Switch Box": True})
    assert rf_panel.findChild(QPushButton, "thruSwitchBoxButton").isEnabled()
    config = build_equipment_connection_config(
        mt8000a_visa_resource="MT",
        fsv40_visa_resource="FS",
        co3000_visa_resource="CO",
        controller_3d_visa_resource="3D",
        switch_box_ip_address="192.168.0.10",
        switch_box_port=5000,
    )
    connected_state = {
        "MT8000A": True,
        "FSV40": True,
        "3D Controller": True,
        "CO3000": True,
        "Switch Box": True,
    }
    window._runner._equipment_state = dict(connected_state)

    window._rf_switch_box_service._running = True
    try:
        with qtbot.waitSignal(service.error_occurred, timeout=1000) as blocker:
            service.connect_equipment(config)

        assert blocker.args == [RF_SWITCH_BOX_OPERATION_IN_PROGRESS_MESSAGE]
        assert window._runner.equipment_state == connected_state
        assert rf_panel.findChild(QPushButton, "thruSwitchBoxButton").isEnabled()
    finally:
        window._rf_switch_box_service._running = False


def test_main_window_blocks_tdf_when_fsv40_is_not_connected(
    qtbot,
    monkeypatch,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    warnings: list[tuple[str, str]] = []
    calls: list[bool] = []
    monkeypatch.setattr(window, "_show_warning", lambda title, message: warnings.append((title, message)))
    monkeypatch.setattr(window._tdf_service, "get_tdf_list", lambda: calls.append(True))

    window.on_get_tdf_list_requested()

    assert calls == []
    assert warnings == [("TDF", "FSV40 연결을 먼저 완료하세요.")]


def test_main_window_blocks_tdf_while_rf_switch_running(qtbot, monkeypatch) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    warnings: list[tuple[str, str]] = []
    calls: list[bool] = []
    window._runner._equipment_state = {"FSV40": True}
    monkeypatch.setattr(
        window,
        "_show_warning",
        lambda title, message: warnings.append((title, message)),
    )
    monkeypatch.setattr(window._tdf_service, "get_tdf_list", lambda: calls.append(True))

    window._rf_switch_box_service._running = True
    try:
        window.on_get_tdf_list_requested()

        assert calls == []
        assert warnings == [
            ("TDF", RF_SWITCH_BOX_OPERATION_IN_PROGRESS_MESSAGE),
        ]
    finally:
        window._rf_switch_box_service._running = False


def test_main_window_updates_tdf_list_from_service_signal(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    window._tdf_service.tdf_list_received.emit(["a.tdf", "b.tdf"])

    tdf_list = window.findChild(QListWidget, "tdfListWidget")
    assert tdf_list is not None
    assert [tdf_list.item(row).text() for row in range(tdf_list.count())] == [
        "a.tdf",
        "b.tdf",
    ]


def test_main_window_set_tdf_request_passes_selected_file(
    qtbot,
    monkeypatch,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    calls: list[str] = []
    window._runner._equipment_state = {"FSV40": True}
    monkeypatch.setattr(window._tdf_service, "set_tdf", calls.append)

    window.on_set_tdf_requested("a.tdf")

    assert calls == ["a.tdf"]


def test_main_window_locks_tdf_operations_immediately_after_request(
    qtbot,
    monkeypatch,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window._runner._equipment_state = {"FSV40": True}
    monkeypatch.setattr(window._tdf_service, "get_tdf_list", lambda: None)
    monkeypatch.setattr(window, "_show_info", lambda title, message: None)
    connect_button = window.findChild(QPushButton, "connectInstrumentButton")
    get_tdf_button = window.findChild(QPushButton, "getTdfListButton")

    assert connect_button is not None
    assert get_tdf_button is not None

    window.on_get_tdf_list_requested()

    assert not connect_button.isEnabled()
    assert not get_tdf_button.isEnabled()
    assert not window.findChild(QLineEdit, "eutNameEdit").isEnabled()
    assert window.findChild(QDialog, "tdfProgressDialog") is None

    window.on_tdf_operation_finished("done")

    assert connect_button.isEnabled()
    assert get_tdf_button.isEnabled()
    assert window.findChild(QLineEdit, "eutNameEdit").isEnabled()


def test_main_window_marks_tdf_active_after_set_success(
    qtbot,
    monkeypatch,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    monkeypatch.setattr(window, "_show_info", lambda title, message: None)
    monkeypatch.setattr(window._tdf_service, "set_tdf", lambda file_name: None)
    window._runner._equipment_state = {"FSV40": True}
    window._tdf_service.tdf_list_received.emit(["a.tdf", "b.tdf"])

    window.on_set_tdf_requested("b.tdf")
    window.on_tdf_operation_finished("done")

    tdf_list = window.findChild(QListWidget, "tdfListWidget")
    assert tdf_list is not None
    assert window._test_manager_panel.active_tdf_file_name == "b.tdf"
    assert tdf_list.item(0).background().style() == Qt.BrushStyle.NoBrush
    assert tdf_list.item(1).background().style() != Qt.BrushStyle.NoBrush


def test_main_window_clears_tdf_active_after_all_off_success(
    qtbot,
    monkeypatch,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    monkeypatch.setattr(window, "_show_info", lambda title, message: None)
    monkeypatch.setattr(window._tdf_service, "set_tdf", lambda file_name: None)
    monkeypatch.setattr(window._tdf_service, "tdf_all_off", lambda: None)
    window._runner._equipment_state = {"FSV40": True}
    window._tdf_service.tdf_list_received.emit(["a.tdf", "b.tdf"])

    window.on_set_tdf_requested("b.tdf")
    window.on_tdf_operation_finished("set done")
    window.on_tdf_all_off_requested()
    window.on_tdf_operation_finished("all off done")

    tdf_list = window.findChild(QListWidget, "tdfListWidget")
    assert tdf_list is not None
    assert all(
        tdf_list.item(row).background().style() == Qt.BrushStyle.NoBrush
        for row in range(tdf_list.count())
    )


def test_main_window_keeps_tdf_active_mark_after_failure(
    qtbot,
    monkeypatch,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    monkeypatch.setattr(window, "_show_info", lambda title, message: None)
    monkeypatch.setattr(window, "_show_warning", lambda title, message: None)
    monkeypatch.setattr(window._tdf_service, "set_tdf", lambda file_name: None)
    window._runner._equipment_state = {"FSV40": True}
    window._tdf_service.tdf_list_received.emit(["a.tdf", "b.tdf"])

    window.on_set_tdf_requested("b.tdf")
    window.on_tdf_operation_finished("set done")
    window.on_set_tdf_requested("a.tdf")
    window.on_tdf_operation_failed("boom")

    tdf_list = window.findChild(QListWidget, "tdfListWidget")
    assert tdf_list is not None
    assert tdf_list.item(0).background().style() == Qt.BrushStyle.NoBrush
    assert tdf_list.item(1).background().style() != Qt.BrushStyle.NoBrush


def test_main_window_locks_instrument_operations_while_tdf_active(
    qtbot,
    monkeypatch,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    monkeypatch.setattr(window, "_show_info", lambda title, message: None)
    connect_button = window.findChild(QPushButton, "connectInstrumentButton")
    get_tdf_button = window.findChild(QPushButton, "getTdfListButton")

    assert connect_button is not None
    assert get_tdf_button is not None

    window.on_tdf_operation_started()

    assert not connect_button.isEnabled()
    assert not get_tdf_button.isEnabled()
    assert not window.findChild(QLineEdit, "eutNameEdit").isEnabled()
    dialog = window.findChild(QDialog, "tdfProgressDialog")
    assert dialog is not None
    assert dialog.property("progressDialog") is True

    window.on_tdf_operation_finished("done")

    assert connect_button.isEnabled()
    assert get_tdf_button.isEnabled()
    assert window.findChild(QLineEdit, "eutNameEdit").isEnabled()
    assert window.findChild(QDialog, "tdfProgressDialog") is None


def test_main_window_tdf_failure_closes_progress_and_warns(
    qtbot,
    monkeypatch,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    warnings: list[tuple[str, str]] = []
    monkeypatch.setattr(window, "_show_warning", lambda title, message: warnings.append((title, message)))

    window.on_tdf_operation_started()
    window.on_tdf_operation_failed("boom")

    assert window.findChild(QDialog, "tdfProgressDialog") is None
    assert warnings == [("TDF", "TDF 작업 실패: boom")]


def test_main_window_keeps_measurement_lock_after_set_finishes(
    qtbot,
    monkeypatch,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    instrument_panel = window.findChild(InstrumentCheckPanel)
    connect_button = window.findChild(QPushButton, "connectInstrumentButton")
    service = window._runner.instrument_connection_service
    assert instrument_panel is not None
    assert connect_button is not None
    monkeypatch.setattr(instrument_panel, "_show_info", lambda message: None)

    window._runner._set_measurement_active(True)
    service.set_started.emit()
    service.set_finished.emit()

    assert not connect_button.isEnabled()
    assert not window.findChild(QLineEdit, "eutNameEdit").isEnabled()

    window._runner._set_measurement_active(False)

    assert connect_button.isEnabled()
    assert window.findChild(QLineEdit, "eutNameEdit").isEnabled()


def test_main_window_updates_test_manager_equipment_info_after_set_finishes(
    monkeypatch,
    qtbot,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    instrument_panel = window.findChild(InstrumentCheckPanel)
    service = window._runner.instrument_connection_service
    panel = window.findChild(ManagerPanel)
    assert instrument_panel is not None
    assert panel is not None
    monkeypatch.setattr(instrument_panel, "_show_info", lambda message: None)

    panel.set_analyzer_info({"start_freq": 30, "stop_freq": 1000})
    panel.set_switch_box_info({"mast": "Bilog", "filter": "6G HPF"})
    panel.set_turntable_info(
        {
            "target_angle": 360,
            "current_angle": 180,
            "setting_speed": 6,
        }
    )
    panel.set_polarization_info(
        {
            "polarization_3m": "H",
            "polarization_bilog": "H",
            "polarization_1m": "90°",
        }
    )

    service.set_finished.emit()

    assert panel.findChild(QLineEdit, "targetAngleEdit").text() == "0"
    assert panel.findChild(QLineEdit, "currentAngleEdit").text() == "0"
    assert panel.findChild(QLineEdit, "settingSpeedEdit").text() == "4"
    assert panel.findChild(QLineEdit, "polarization3mEdit").text() == "V"
    assert panel.findChild(QLineEdit, "polarizationBilogEdit").text() == "V"
    assert panel.findChild(QLineEdit, "polarization1mEdit").text() == "0°"
    assert panel.findChild(QLineEdit, "startFreqEdit").text() == "30"
    assert panel.findChild(QLineEdit, "stopFreqEdit").text() == "1000"
    assert panel.findChild(QLineEdit, "mastEdit").text() == "Bilog"
    assert panel.findChild(QLineEdit, "filterEdit").text() == "6G HPF"


def test_main_window_marks_equipment_disconnected_after_set_failure(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    instrument_panel = window.findChild(InstrumentCheckPanel)
    assert instrument_panel is not None
    states = disconnected_equipment_state()

    window._runner.instrument_connection_service.equipment_disconnected.emit(states)

    assert window._runner.equipment_state == {}
    assert instrument_panel.equipment_state == {}
    for object_name in (
        "mt8000aStatusLabel",
        "fsv40StatusLabel",
        "co3000StatusLabel",
        "controller_3dStatusLabel",
        "switch_boxStatusLabel",
    ):
        status = window.findChild(QLabel, object_name)
        assert status is not None
        assert status.text() == "Not Connected"
    for index in range(1, 6):
        indicator = window.findChild(QWidget, f"connectionStatus{index}")
        assert indicator is not None
        assert indicator.property("connectionStatus") == "failed"
        assert indicator.property("connected") is False


def test_main_window_mirrors_instrument_connection_state_to_test_manager(
    qtbot,
) -> None:
    """Instrument Check service 결과가 Test Manager Connection indicator에 반영된다."""

    window = MainWindow()
    qtbot.addWidget(window)
    service = window._runner.instrument_connection_service
    rf_panel = window._rf_filter_box_panel
    assert rf_panel is not None
    rf_panel.set_connection_state({"Switch Box": True})
    rf_panel.findChild(QPushButton, "inputButton3").click()
    rf_panel.findChild(QPushButton, "filterButton06").click()

    assert rf_panel.findChild(QPushButton, "setSwitchBoxButton").isEnabled()
    assert rf_panel.findChild(QPushButton, "thruSwitchBoxButton").isEnabled()

    service._connection_thread = object()
    try:
        service.connection_started.emit()

        for index in range(1, 6):
            indicator = window.findChild(QWidget, f"connectionStatus{index}")
            assert indicator is not None
            assert indicator.property("connectionStatus") == "connecting"
            assert indicator.property("connected") is False
        assert not rf_panel.findChild(QPushButton, "inputButton1").isEnabled()
        assert not rf_panel.findChild(QPushButton, "setSwitchBoxButton").isEnabled()
        assert not rf_panel.findChild(QPushButton, "thruSwitchBoxButton").isEnabled()

        service.connection_finished.emit(
            {
                "MT8000A": True,
                "FSV40": False,
                "3D Controller": True,
                "CO3000": True,
                "Switch Box": True,
            }
        )

        assert rf_panel.findChild(QPushButton, "inputButton1").isEnabled()
        assert rf_panel.findChild(QPushButton, "setSwitchBoxButton").isEnabled()
        assert rf_panel.findChild(QPushButton, "thruSwitchBoxButton").isEnabled()

        expected_statuses = [
            "connected",
            "failed",
            "connected",
            "connected",
            "connected",
        ]
        for index, expected_status in enumerate(expected_statuses, start=1):
            indicator = window.findChild(QWidget, f"connectionStatus{index}")
            assert indicator is not None
            assert indicator.property("connectionStatus") == expected_status
            assert indicator.property("connected") is (expected_status == "connected")
    finally:
        service._connection_thread = None


def test_main_window_applies_initial_switch_box_101_after_connection(
    qtbot,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    service = window._runner.instrument_connection_service

    service.connection_finished.emit(
        {
            "MT8000A": True,
            "FSV40": True,
            "3D Controller": True,
            "CO3000": True,
            "Switch Box": True,
        }
    )

    rf_panel = window._rf_filter_box_panel
    assert rf_panel.findChild(QLabel, "currentInputLabel").text() == "Input: Bilog"
    assert rf_panel.findChild(QLabel, "currentFilterLabel").text() == "Filter: Thru"
    assert rf_panel.findChild(QPushButton, "inputButton1").isChecked()
    assert rf_panel.findChild(QPushButton, "filterButton01").isChecked()
    assert window.findChild(QLineEdit, "mastEdit").text() == "Bilog"
    assert window.findChild(QLineEdit, "filterEdit").text() == "Thru"


@pytest.mark.parametrize(
    "states",
    [
        {
            "MT8000A": True,
            "FSV40": True,
            "3D Controller": True,
            "CO3000": True,
            "Switch Box": False,
        },
        {
            "MT8000A": True,
            "FSV40": True,
            "3D Controller": True,
            "CO3000": True,
        },
    ],
)
def test_main_window_does_not_apply_initial_switch_box_101_when_unavailable(
    qtbot,
    states,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    service = window._runner.instrument_connection_service

    service.connection_finished.emit(
        {
            "MT8000A": True,
            "FSV40": True,
            "3D Controller": True,
            "CO3000": True,
            "Switch Box": True,
        }
    )
    service.connection_finished.emit(states)

    rf_panel = window._rf_filter_box_panel
    assert rf_panel.findChild(QLabel, "currentInputLabel").text() == "Input: Unknown"
    assert rf_panel.findChild(QLabel, "currentFilterLabel").text() == "Filter: Unknown"
    assert not rf_panel.findChild(QPushButton, "inputButton1").isChecked()
    assert not rf_panel.findChild(QPushButton, "filterButton01").isChecked()
    assert window.findChild(QLineEdit, "mastEdit").text() == ""
    assert window.findChild(QLineEdit, "filterEdit").text() == ""


@pytest.mark.parametrize(
    "message",
    [
        CONNECTION_IN_PROGRESS_MESSAGE,
        INSTRUMENT_SET_IN_PROGRESS_MESSAGE,
    ],
)
def test_main_window_preserves_switch_box_path_on_guard_connection_error(
    qtbot,
    monkeypatch,
    message,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    instrument_panel = window.findChild(InstrumentCheckPanel)
    assert instrument_panel is not None
    monkeypatch.setattr(instrument_panel, "_show_warning", lambda message: None)
    service = window._runner.instrument_connection_service

    service.connection_finished.emit(
        {
            "MT8000A": True,
            "FSV40": True,
            "3D Controller": True,
            "CO3000": True,
            "Switch Box": True,
        }
    )

    service.error_occurred.emit(message)

    rf_panel = window._rf_filter_box_panel
    assert rf_panel.findChild(QLabel, "currentInputLabel").text() == "Input: Bilog"
    assert rf_panel.findChild(QLabel, "currentFilterLabel").text() == "Filter: Thru"
    assert rf_panel.findChild(QPushButton, "inputButton1").isChecked()
    assert rf_panel.findChild(QPushButton, "filterButton01").isChecked()
    assert window.findChild(QLineEdit, "mastEdit").text() == "Bilog"
    assert window.findChild(QLineEdit, "filterEdit").text() == "Thru"


def test_main_window_marks_connecting_indicators_failed_on_connection_error(
    qtbot,
    monkeypatch,
) -> None:
    """장비별 결과가 없는 연결 오류는 진행 중 indicator만 실패 상태로 바꾼다."""

    window = MainWindow()
    qtbot.addWidget(window)
    instrument_panel = window.findChild(InstrumentCheckPanel)
    assert instrument_panel is not None
    monkeypatch.setattr(instrument_panel, "_show_warning", lambda message: None)
    service = window._runner.instrument_connection_service

    service.connection_started.emit()
    rf_panel = window._rf_filter_box_panel
    rf_panel.set_connection_state({"Switch Box": True})
    assert rf_panel.findChild(QPushButton, "thruSwitchBoxButton").isEnabled()

    service.connection_started.emit()
    service.error_occurred.emit("boom")

    for index in range(1, 6):
        indicator = window.findChild(QWidget, f"connectionStatus{index}")
        assert indicator is not None
        assert indicator.property("connectionStatus") == "failed"
        assert indicator.property("connected") is False
    assert not rf_panel.findChild(QPushButton, "inputButton1").isEnabled()
    assert not rf_panel.findChild(QPushButton, "thruSwitchBoxButton").isEnabled()
    assert (
        rf_panel.findChild(QLabel, "operationStatusLabel").text()
        == "Switch Box not connected"
    )


def test_test_manager_panel_set_connection_state_supports_aliases(qtbot) -> None:
    """장비 연결 setter가 canonical key와 UI alias를 처리한다."""

    panel = ManagerPanel()
    qtbot.addWidget(panel)

    panel.set_connection_state(
        {
            "MT8000A": True,
            "FSV40": False,
            "3D Position Controller": True,
            "CO3000": True,
            "RF Filter Box": True,
            "Unknown": True,
        }
    )

    expected = [True, False, True, True, True]
    for index, connected in enumerate(expected, start=1):
        indicator = panel.findChild(QWidget, f"connectionStatus{index}")
        assert indicator is not None
        assert indicator.property("connected") is connected
        assert indicator.property("disconnected") is (not connected)


def test_test_manager_panel_info_setters_update_display_fields(qtbot) -> None:
    """Info setter가 dict/object 입력을 표시 필드에 반영한다."""

    panel = ManagerPanel()
    qtbot.addWidget(panel)
    panel.findChild(QLineEdit, "saturationTimeEdit").setText("9")
    panel.findChild(QLineEdit, "connectionWaitingTimeEdit").setText("10")
    panel.findChild(QLineEdit, "attenLevelEdit").setText("11")
    panel.findChild(QLineEdit, "nextPeakSearchLevelEdit").setText("12")

    panel.set_analyzer_info(
        {
            "Start Frequency": 30.0,
            "stop_freq": 1000.0,
            "trace_mode": "Max Hold",
            "mast": "3m",
            "RBW": 0.1,
            "VBW": 0.3,
            "sweep_point": 10001,
            "atten_level": 99,
        }
    )
    panel.set_switch_box_info({"mast": "Bilog", "filter": "6G HPF"})
    panel.set_turntable_info(
        {
            "Target Angle": 360,
            "current_angle": 180,
            "turntable_speed": 4,
        }
    )
    panel.set_polarization_info(
        SimpleNamespace(
            polarization_3m="H",
            polarization_bilog="V",
            polarization_1m="90°",
        )
    )

    assert panel.findChild(QLineEdit, "startFreqEdit").text() == "30"
    assert panel.findChild(QLineEdit, "stopFreqEdit").text() == "1000"
    assert panel.findChild(QLineEdit, "traceModeEdit").text() == "Max Hold"
    assert panel.findChild(QLineEdit, "mastEdit").text() == "Bilog"
    assert panel.findChild(QLineEdit, "rbwEdit").text() == "0.1"
    assert panel.findChild(QLineEdit, "vbwEdit").text() == "0.3"
    assert panel.findChild(QLineEdit, "sweepPointEdit").text() == "10001"
    assert panel.findChild(QLineEdit, "filterEdit").text() == "6G HPF"
    assert panel.findChild(QLineEdit, "targetAngleEdit").text() == "360"
    assert panel.findChild(QLineEdit, "currentAngleEdit").text() == "180"
    assert panel.findChild(QLineEdit, "settingSpeedEdit").text() == "4"
    assert panel.findChild(QLineEdit, "polarization3mEdit").text() == "H"
    assert panel.findChild(QLineEdit, "polarizationBilogEdit").text() == "V"
    assert panel.findChild(QLineEdit, "polarization1mEdit").text() == "90°"
    assert panel.findChild(QLineEdit, "saturationTimeEdit").text() == "9"
    assert panel.findChild(QLineEdit, "connectionWaitingTimeEdit").text() == "10"
    assert panel.findChild(QLineEdit, "attenLevelEdit").text() == "11"
    assert panel.findChild(QLineEdit, "nextPeakSearchLevelEdit").text() == "12"

    panel.set_turntable_info({})

    assert panel.findChild(QLineEdit, "targetAngleEdit").text() == ""
    assert panel.findChild(QLineEdit, "currentAngleEdit").text() == ""
    assert panel.findChild(QLineEdit, "settingSpeedEdit").text() == ""


def test_test_manager_panel_builds_test_run_settings(qtbot, monkeypatch, tmp_path) -> None:
    panel = ManagerPanel()
    qtbot.addWidget(panel)
    template_path = tmp_path / "template.xlsx"
    screenshot_root = tmp_path / "default-screenshots"
    template_path.write_bytes(b"template")
    monkeypatch.setattr(
        "app.ui.test_manager_panel.default_screenshot_root_dir",
        lambda: screenshot_root,
    )

    panel.findChild(QLineEdit, "eutNameEdit").setText(" SM-000 ")
    panel.findChild(QLineEdit, "excelTemplatePathEdit").setText(str(template_path))
    panel.findChild(QLineEdit, "saturationTimeEdit").setText("6.5")
    panel.findChild(QLineEdit, "connectionWaitingTimeEdit").setText("7")
    panel.findChild(QLineEdit, "attenLevelEdit").setText("1.5")
    panel.findChild(QLineEdit, "nextPeakSearchLevelEdit").setText("60.5")
    panel.findChild(QLineEdit, "customTurnTableSpeedEdit").setText("8")
    panel.findChild(QCheckBox, "customOptionCheckBox").setChecked(True)
    panel.set_active_tdf_file_name("NR_Radiated.tdf")

    settings = panel.build_test_run_settings()

    assert settings is not None
    assert settings.eut_name == "SM-000"
    assert settings.template_path == template_path
    assert settings.screenshot_root_dir == screenshot_root
    assert settings.saturation_time_sec == 6.5
    assert settings.connection_waiting_time_sec == 7
    assert settings.atten_level_db == 1.5
    assert settings.next_peak_search_level_db == 60.5
    assert settings.custom_turntable_speed == 8
    assert settings.manual_marker_enabled is False
    assert settings.active_tdf_file_name == "NR_Radiated.tdf"


def test_test_manager_panel_builds_default_settings_when_custom_option_unchecked(
    qtbot,
    monkeypatch,
    tmp_path,
) -> None:
    panel = ManagerPanel()
    qtbot.addWidget(panel)
    template_path = tmp_path / "template.xlsx"
    screenshot_root = tmp_path / "default-screenshots"
    template_path.write_bytes(b"template")
    monkeypatch.setattr(
        "app.ui.test_manager_panel.default_screenshot_root_dir",
        lambda: screenshot_root,
    )

    panel.findChild(QLineEdit, "eutNameEdit").setText("SM-000")
    panel.findChild(QLineEdit, "excelTemplatePathEdit").setText(str(template_path))
    panel.findChild(QLineEdit, "saturationTimeEdit").setText("6.5")
    panel.findChild(QLineEdit, "connectionWaitingTimeEdit").setText("7")
    panel.findChild(QLineEdit, "attenLevelEdit").setText("1.5")
    panel.findChild(QLineEdit, "nextPeakSearchLevelEdit").setText("60.5")
    panel.findChild(QLineEdit, "customTurnTableSpeedEdit").setText("8")
    panel.findChild(QCheckBox, "customOptionCheckBox").setChecked(False)
    panel.set_active_tdf_file_name("NR_Radiated.tdf")

    settings = panel.build_test_run_settings()

    assert settings is not None
    assert settings.saturation_time_sec == 5
    assert settings.connection_waiting_time_sec == 5
    assert settings.atten_level_db == 0
    assert settings.next_peak_search_level_db == 6
    assert settings.custom_turntable_speed is None


def test_nr_select_dialog_can_be_created(qtbot) -> None:
    """NR 선택 팝업 스캐폴드를 독립적으로 생성할 수 있다."""

    dialog = NRSelectDialog()
    qtbot.addWidget(dialog)

    assert dialog.windowTitle() == "NR Select"


def test_test_manager_panel_enables_manual_marker_when_custom_marker_checked(
    qtbot,
    monkeypatch,
    tmp_path,
) -> None:
    panel = ManagerPanel()
    qtbot.addWidget(panel)
    template_path = tmp_path / "template.xlsx"
    screenshot_root = tmp_path / "default-screenshots"
    template_path.write_bytes(b"template")
    monkeypatch.setattr(
        "app.ui.test_manager_panel.default_screenshot_root_dir",
        lambda: screenshot_root,
    )

    panel.findChild(QLineEdit, "eutNameEdit").setText("SM-000")
    panel.findChild(QLineEdit, "excelTemplatePathEdit").setText(str(template_path))
    panel.findChild(QCheckBox, "customOptionCheckBox").setChecked(True)
    panel.findChild(QCheckBox, "markerCheckBox").setChecked(True)
    panel.set_active_tdf_file_name("NR_Radiated.tdf")

    settings = panel.build_test_run_settings()

    assert settings is not None
    assert settings.manual_marker_enabled is True


def test_manual_marker_dialog_emits_marker_commands(qtbot) -> None:
    dialog = ManualMarkerDialog(next_peak_search_level_db=6.5)
    qtbot.addWidget(dialog)
    received: list[tuple[int, float]] = []
    all_off: list[bool] = []
    completed: list[bool] = []

    dialog.peak_requested.connect(
        lambda index, excursion: received.append((index, excursion))
    )
    dialog.all_marker_off_requested.connect(lambda: all_off.append(True))
    dialog.completed.connect(lambda: completed.append(True))
    dialog.show()

    combo = dialog.findChild(QComboBox, "targetMarkerComboBox")
    edit = dialog.findChild(QLineEdit, "nextPeakSearchLevelEdit")
    combo.setCurrentIndex(1)
    edit.setText("7.5")

    qtbot.mouseClick(
        dialog.findChild(QPushButton, "markerPeakButton"),
        Qt.MouseButton.LeftButton,
    )
    qtbot.mouseClick(
        dialog.findChild(QPushButton, "markerAllOffButton"),
        Qt.MouseButton.LeftButton,
    )
    qtbot.mouseClick(
        dialog.findChild(QPushButton, "manualMarkerCompleteButton"),
        Qt.MouseButton.LeftButton,
    )

    assert received == [(2, 7.5)]
    assert all_off == [True]
    assert completed == [True]


def test_main_window_shows_manual_marker_dialog_and_complete_resumes(
    qtbot,
    monkeypatch,
) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    completed: list[bool] = []
    monkeypatch.setattr(
        window._runner,
        "user_action_completed",
        lambda: completed.append(True),
    )

    window._runner.events.manual_marker_edit_required.emit(
        {"next_peak_search_level_db": 6.5}
    )

    dialog = window.findChild(QDialog, "manualMarkerDialog")
    assert dialog is not None
    assert dialog.findChild(QComboBox, "targetMarkerComboBox").count() == 10
    assert dialog.findChild(QLineEdit, "nextPeakSearchLevelEdit").text() == "6.5"

    qtbot.mouseClick(
        dialog.findChild(QPushButton, "manualMarkerCompleteButton"),
        Qt.MouseButton.LeftButton,
    )

    assert completed == [True]
