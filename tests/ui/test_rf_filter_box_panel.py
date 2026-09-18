from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QLabel, QPushButton, QScrollArea, QWidget

from app.models.enums import FilterPath, InputPath
from app.net.mock_lv_server import MockLvServer
from app.net.tcp_client import TcpClient
from app.net import commands
from app.ui.rf_filter_box_panel import RFFilterBoxPanel, RFSwitchBoxService


class _Service(QObject):
    operation_started = Signal()
    switch_box_set = Signal(object, object)
    switch_filter_set = Signal(object)
    operation_failed = Signal(str)
    operation_finished = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.set_calls: list[tuple[InputPath, FilterPath]] = []
        self.thru_calls = 0
        self.fail_next = False

    def set_switch_box(self, input_path: InputPath, filter_path: FilterPath) -> None:
        self.set_calls.append((input_path, filter_path))
        self.operation_started.emit()
        if self.fail_next:
            self.fail_next = False
            self.operation_failed.emit("set failed")
            return
        self.switch_box_set.emit(input_path, filter_path)
        self.operation_finished.emit("set ok")

    def set_thru(self) -> None:
        self.thru_calls += 1
        self.operation_started.emit()
        if self.fail_next:
            self.fail_next = False
            self.operation_failed.emit("thru failed")
            return
        self.switch_filter_set.emit(FilterPath.THRU)
        self.operation_finished.emit("thru ok")

    def shutdown(self) -> None:
        return


class _Commands:
    def __init__(
        self,
        *,
        switch_box_result: bool = True,
        filter_result: bool = True,
        exception: Exception | None = None,
    ) -> None:
        self.switch_box_result = switch_box_result
        self.filter_result = filter_result
        self.exception = exception
        self.switch_box_calls: list[tuple[Any, InputPath, FilterPath]] = []
        self.filter_calls: list[tuple[Any, FilterPath]] = []

    def set_switch_box(
        self,
        client: Any,
        *,
        input_path: InputPath,
        filter_path: FilterPath,
    ) -> bool:
        self.switch_box_calls.append((client, input_path, filter_path))
        if self.exception is not None:
            raise self.exception
        return self.switch_box_result

    def set_switch_filter(self, client: Any, *, filter_path: FilterPath) -> bool:
        self.filter_calls.append((client, filter_path))
        if self.exception is not None:
            raise self.exception
        return self.filter_result


def _connected_panel(qtbot) -> tuple[RFFilterBoxPanel, _Service]:
    service = _Service()
    panel = RFFilterBoxPanel(service=service)
    qtbot.addWidget(panel)
    panel.set_connection_state({"Switch Box": True})
    return panel, service


def test_rf_filter_box_panel_exposes_expected_buttons(qtbot) -> None:
    panel, _service = _connected_panel(qtbot)

    assert panel.findChild(QPushButton, "inputButton1").text() == "Bilog"
    assert panel.findChild(QPushButton, "inputButton2").text() == "3M HORN"
    assert panel.findChild(QPushButton, "inputButton3").text() == "1M HORN"
    assert panel.findChild(QPushButton, "filterButton01").text() == "Thru"
    assert panel.findChild(QPushButton, "filterButton02").text() == "Direct-amp"
    assert panel.findChild(QPushButton, "filterButton03").text() == "1 GHz HPF"
    assert panel.findChild(QPushButton, "filterButton06").text() == "6 GHz HPF"
    assert panel.findChild(QPushButton, "filterButton20").text() == "BAND 78"
    assert panel.findChild(QPushButton, "filterButton23").text() == "DCS1800"
    assert panel.findChild(QPushButton, "filterButton24").text() == "Port 18"


def test_rf_filter_box_canvas_follows_visible_panel_size(qtbot) -> None:
    panel, _service = _connected_panel(qtbot)
    panel.resize(1500, 820)
    panel.show()
    qtbot.wait(0)

    scroll_area = panel.findChild(QScrollArea, "rfSwitchScrollArea")
    canvas = panel.findChild(QWidget, "rfSwitchBoxCanvas")

    assert scroll_area is not None
    assert canvas is not None
    assert scroll_area.widgetResizable()
    assert canvas.width() == scroll_area.viewport().width()
    assert canvas.height() == scroll_area.viewport().height()
    assert canvas.width() > 1098
    assert canvas.height() > 747


def test_panel_controls_scale_with_large_window(qtbot) -> None:
    panel, _service = _connected_panel(qtbot)
    panel.resize(1200, 820)
    panel.show()
    qtbot.wait(0)

    set_button = panel.findChild(QPushButton, "setSwitchBoxButton")
    thru_button = panel.findChild(QPushButton, "thruSwitchBoxButton")
    input_button = panel.findChild(QPushButton, "inputButton1")
    assert set_button is not None
    assert thru_button is not None
    assert input_button is not None

    base_set_height = set_button.height()
    base_thru_height = thru_button.height()
    base_input_height = input_button.height()
    base_input_font = input_button.font().pointSize()

    panel.resize(1920, 1230)
    qtbot.wait(0)

    assert set_button.height() > base_set_height
    assert thru_button.height() > base_thru_height
    assert input_button.height() > base_input_height
    assert input_button.font().pointSize() > base_input_font

def test_select_buttons_do_not_send_until_set(qtbot) -> None:
    panel, service = _connected_panel(qtbot)

    panel.findChild(QPushButton, "inputButton3").click()
    panel.findChild(QPushButton, "filterButton06").click()

    assert service.set_calls == []
    assert panel.findChild(QPushButton, "setSwitchBoxButton").isEnabled()


def test_set_applies_selected_path_and_updates_current_state(qtbot) -> None:
    panel, service = _connected_panel(qtbot)

    panel.findChild(QPushButton, "inputButton3").click()
    panel.findChild(QPushButton, "filterButton06").click()
    panel.findChild(QPushButton, "setSwitchBoxButton").click()

    assert service.set_calls == [(InputPath.INPUT3, FilterPath.HPF_6G)]
    assert panel.findChild(QLabel, "currentInputLabel").text() == "Input: 1M HORN"
    assert panel.findChild(QLabel, "currentFilterLabel").text() == "Filter: 6 GHz HPF"
    assert panel.findChild(QPushButton, "inputButton3").isChecked()
    assert panel.findChild(QPushButton, "filterButton06").isChecked()


def test_thru_button_applies_filter_only(qtbot) -> None:
    panel, service = _connected_panel(qtbot)
    panel.set_switch_box_info(
        {"input_path": InputPath.INPUT2, "filter_path": FilterPath.HPF_3G}
    )

    panel.findChild(QPushButton, "thruSwitchBoxButton").click()

    assert service.thru_calls == 1
    assert service.set_calls == []
    assert panel.findChild(QLabel, "currentInputLabel").text() == "Input: 3M HORN"
    assert panel.findChild(QLabel, "currentFilterLabel").text() == "Filter: Thru"


def test_failed_operation_keeps_current_state(qtbot) -> None:
    panel, service = _connected_panel(qtbot)
    panel.set_switch_box_info(
        {"input_path": InputPath.INPUT1, "filter_path": FilterPath.THRU}
    )
    service.fail_next = True

    panel.findChild(QPushButton, "inputButton3").click()
    panel.findChild(QPushButton, "filterButton06").click()
    panel.findChild(QPushButton, "setSwitchBoxButton").click()

    assert panel.findChild(QLabel, "currentInputLabel").text() == "Input: Bilog"
    assert panel.findChild(QLabel, "currentFilterLabel").text() == "Filter: Thru"
    assert "failed" in panel.findChild(QLabel, "operationStatusLabel").text()


def test_clear_switch_box_info_resets_current_and_selected_path(qtbot) -> None:
    panel, _service = _connected_panel(qtbot)
    panel.set_switch_box_info(
        {"input_path": InputPath.INPUT1, "filter_path": FilterPath.THRU}
    )

    panel.clear_switch_box_info()

    assert panel.findChild(QLabel, "currentInputLabel").text() == "Input: Unknown"
    assert panel.findChild(QLabel, "currentFilterLabel").text() == "Filter: Unknown"
    assert not panel.findChild(QPushButton, "inputButton1").isChecked()
    assert not panel.findChild(QPushButton, "filterButton01").isChecked()
    assert not panel.findChild(QPushButton, "setSwitchBoxButton").isEnabled()


def test_panel_disables_controls_when_locked_or_disconnected(qtbot) -> None:
    panel, _service = _connected_panel(qtbot)

    panel.set_operation_locked(True)
    assert not panel.findChild(QPushButton, "inputButton1").isEnabled()
    assert not panel.findChild(QPushButton, "thruSwitchBoxButton").isEnabled()

    panel.set_operation_locked(False)
    panel.set_connection_state({"Switch Box": False})

    assert not panel.findChild(QPushButton, "inputButton1").isEnabled()
    assert not panel.findChild(QPushButton, "thruSwitchBoxButton").isEnabled()


def test_rf_switch_box_service_runs_set_synchronously(qtbot) -> None:
    command_facade = _Commands()
    client = object()
    service = RFSwitchBoxService(client=client, commands=command_facade)
    started: list[bool] = []
    finished: list[str] = []
    set_paths: list[tuple[InputPath, FilterPath]] = []

    service.operation_started.connect(lambda: started.append(service.is_running))
    service.switch_box_set.connect(lambda input_path, filter_path: set_paths.append((input_path, filter_path)))
    service.operation_finished.connect(finished.append)

    service.set_switch_box(InputPath.INPUT3, FilterPath.HPF_6G)

    assert started == [True]
    assert command_facade.switch_box_calls == [(client, InputPath.INPUT3, FilterPath.HPF_6G)]
    assert set_paths == [(InputPath.INPUT3, FilterPath.HPF_6G)]
    assert finished == ["Switch Box 경로 설정 완료"]
    assert not service.is_running


def test_rf_switch_box_service_runs_thru_synchronously(qtbot) -> None:
    command_facade = _Commands()
    client = object()
    service = RFSwitchBoxService(client=client, commands=command_facade)
    filters: list[FilterPath] = []
    finished: list[str] = []

    service.switch_filter_set.connect(filters.append)
    service.operation_finished.connect(finished.append)

    service.set_thru()

    assert command_facade.filter_calls == [(client, FilterPath.THRU)]
    assert filters == [FilterPath.THRU]
    assert finished == ["Switch Box THRU 설정 완료"]
    assert not service.is_running


def test_rf_switch_box_service_reports_failure_and_releases_running_flag(qtbot) -> None:
    command_facade = _Commands(exception=RuntimeError("instrument timeout"))
    service = RFSwitchBoxService(client=object(), commands=command_facade)
    failed: list[str] = []

    service.operation_failed.connect(failed.append)

    service.set_switch_box(InputPath.INPUT3, FilterPath.HPF_6G)

    assert failed == ["instrument timeout"]
    assert not service.is_running


def test_rf_switch_box_service_guard_rejects_before_command(qtbot) -> None:
    command_facade = _Commands()
    service = RFSwitchBoxService(
        client=object(),
        commands=command_facade,
        operation_guard=lambda: "다른 장비 작업이 진행 중입니다.",
    )
    failures: list[str] = []
    service.operation_failed.connect(failures.append)

    service.set_thru()

    assert command_facade.filter_calls == []
    assert failures == ["다른 장비 작업이 진행 중입니다."]
    assert not service.is_running


def test_rf_switch_box_service_repeated_operations_with_tcp_client(qtbot, tmp_path) -> None:
    server = MockLvServer(port=0, temp_dir=tmp_path)
    server.start()
    client = TcpClient()
    service = RFSwitchBoxService(client=client, commands=commands)
    finished: list[str] = []
    failed: list[str] = []
    service.operation_finished.connect(finished.append)
    service.operation_failed.connect(failed.append)

    try:
        with qtbot.waitSignal(client.connected_changed, timeout=1000):
            client.connect_to(server.host, server.port, timeout=1.0)

        for index in range(10):
            if index % 2:
                service.set_thru()
            else:
                service.set_switch_box(InputPath.INPUT3, FilterPath.HPF_6G)
            qtbot.waitUntil(lambda: not service.is_running, timeout=1000)

        assert len(finished) == 10
        assert failed == []
    finally:
        service.shutdown()
        client.disconnect_from_host()
        server.stop()
