from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPalette
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QWidget,
)

from app.core.manual_test_service import ManualTestCapabilities, ManualTestService
from app.models.test_run_settings import default_screenshot_root_dir
from app.ui.log_panel import LogPanel
from app.ui.manual_test_panel import ManualTestPanel


def test_manual_panel_uses_expected_defaults(qtbot) -> None:
    panel = ManualTestPanel(service=ManualTestService())
    qtbot.addWidget(panel)

    assert panel.findChild(QComboBox, "manualPresetComboBox").currentIndex() == 2
    assert panel.findChild(QLineEdit, "manualStartFrequencyEdit").text() == "1000"
    assert panel.findChild(QLineEdit, "manualStopFrequencyEdit").text() == "12750"
    assert panel.findChild(QLineEdit, "manualSweepPointEdit").text() == "30001"
    assert panel.findChild(QLineEdit, "manualSaturationTimeEdit").text() == "5"
    assert panel.findChild(QComboBox, "manualDetectorModeComboBox").currentText() == "RMS"
    assert panel.findChild(QLineEdit, "captureDirectoryEdit").text() == str(
        default_screenshot_root_dir()
    )


def test_manual_panel_browse_uses_current_directory_and_applies_selection(
    qtbot,
    monkeypatch,
    tmp_path,
) -> None:
    panel = ManualTestPanel(service=ManualTestService())
    qtbot.addWidget(panel)
    directory_edit = panel.findChild(QLineEdit, "captureDirectoryEdit")
    current = tmp_path / "current"
    selected = tmp_path / "selected"
    directory_edit.setText(str(current))
    calls: list[tuple[str, str]] = []

    def select_directory(_parent, title: str, initial: str) -> str:
        calls.append((title, initial))
        return str(selected)

    monkeypatch.setattr(QFileDialog, "getExistingDirectory", select_directory)

    panel.findChild(QPushButton, "captureDirectoryButton").click()

    assert calls == [("Screenshot 저장 폴더", str(current))]
    assert directory_edit.text() == str(selected)


def test_manual_panel_uses_compact_setting_sections_with_readable_inputs(qtbot) -> None:
    panel = ManualTestPanel(service=ManualTestService())
    qtbot.addWidget(panel)

    for object_name in (
        "manualFrequencyGroup",
        "manualSweepTraceGroup",
        "manualOperationGroup",
        "manualTdfGroup",
    ):
        assert panel.findChild(QGroupBox, object_name) is not None

    for object_name in (
        "manualStartFrequencyEdit",
        "manualStopFrequencyEdit",
        "manualRbwEdit",
        "manualVbwEdit",
        "manualSweepPointEdit",
        "manualSweepTimeEdit",
        "manualSaturationTimeEdit",
        "manualAttenLevelEdit",
        "manualLimitEdit",
    ):
        assert panel.findChild(QLineEdit, object_name).minimumWidth() >= 88

    assert panel.findChild(QComboBox, "manualPresetComboBox").minimumWidth() >= 120
    assert panel.findChild(QComboBox, "manualDetectorModeComboBox").minimumWidth() >= 120


def test_manual_panel_formats_duplicate_ranges_and_applies_their_bandwidths(qtbot) -> None:
    panel = ManualTestPanel(service=ManualTestService())
    qtbot.addWidget(panel)
    preset = panel.findChild(QComboBox, "manualPresetComboBox")
    rbw = panel.findChild(QLineEdit, "manualRbwEdit")
    vbw = panel.findChild(QLineEdit, "manualVbwEdit")

    assert preset.itemText(1) == "1 GHz ~ 3 GHz"
    assert preset.itemText(6) == "1 GHz ~ 3 GHz"
    assert preset.itemData(1) != preset.itemData(6)

    preset.setCurrentIndex(1)
    assert (rbw.text(), vbw.text()) == ("1", "3")
    preset.setCurrentIndex(6)
    assert (rbw.text(), vbw.text()) == ("0.1", "0.3")


def test_manual_panel_places_operation_below_settings_and_keeps_log_on_right(qtbot) -> None:
    panel = ManualTestPanel(service=ManualTestService())
    qtbot.addWidget(panel)
    panel.resize(1578, 898)
    panel.show()
    qtbot.wait(1)

    stack = panel.findChild(QWidget, "manualSaControlStack")
    control_area = panel.findChild(QWidget, "manualControlArea")
    sa_settings = panel.findChild(QGroupBox, "manualSaSettingGroup")
    settings = panel.findChild(QWidget, "manualSettingsContainer")
    operation = panel.findChild(QGroupBox, "manualOperationGroup")
    tdf = panel.findChild(QGroupBox, "manualTdfGroup")
    screenshot = panel.findChild(QGroupBox, "manualScreenshotGroup")
    controls = panel.findChild(QWidget, "manualControlPanel")
    log_panel = panel.findChild(LogPanel, "manualTestLogPanel")

    assert sa_settings.isAncestorOf(settings)
    assert not sa_settings.isAncestorOf(operation)
    assert not sa_settings.isAncestorOf(tdf)
    assert stack.layout().indexOf(sa_settings) < stack.layout().indexOf(operation)
    assert operation.y() > sa_settings.y()
    assert control_area.isAncestorOf(operation)
    assert control_area.isAncestorOf(tdf)
    assert screenshot.width() > controls.width()
    assert log_panel.width() == 280
    assert log_panel.x() > controls.x()


def test_manual_panel_sizes_operation_buttons_independently(qtbot) -> None:
    panel = ManualTestPanel(service=ManualTestService())
    qtbot.addWidget(panel)
    panel.resize(1578, 898)
    panel.show()
    qtbot.wait(1)

    trace_clear = panel.findChild(QPushButton, "manualTraceClearButton")
    stop = panel.findChild(QPushButton, "manualStopButton")
    zero = panel.findChild(QPushButton, "manualTurntableZeroButton")
    full_turn = panel.findChild(QPushButton, "manualTurntable360Button")
    vertical = panel.findChild(QPushButton, "manualVerticalButton")
    horizontal = panel.findChild(QPushButton, "manualHorizontalButton")
    update = panel.findChild(QPushButton, "manualGetTdfListButton")
    all_off = panel.findChild(QPushButton, "manualTdfAllOffButton")

    assert trace_clear.width() > stop.width()
    assert trace_clear.width() >= trace_clear.sizeHint().width()
    assert stop.width() >= stop.sizeHint().width()
    assert zero.width() == full_turn.width() == vertical.width() == horizontal.width()
    assert update.text() == "Update"
    assert all_off.text() == "All Off"


def test_manual_panel_and_log_follow_dark_palette(qtbot, qapp) -> None:
    original_palette = QPalette(qapp.palette())
    dark_palette = QPalette(original_palette)
    dark_palette.setColor(QPalette.ColorRole.Window, QColor("#20242a"))
    dark_palette.setColor(QPalette.ColorRole.WindowText, QColor("#f0f2f4"))
    dark_palette.setColor(QPalette.ColorRole.Base, QColor("#171a1f"))
    dark_palette.setColor(QPalette.ColorRole.Text, QColor("#f0f2f4"))
    dark_palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#2b3038"))
    try:
        qapp.setPalette(dark_palette)
        panel = ManualTestPanel(service=ManualTestService())
        qtbot.addWidget(panel)
        panel.show()
        qtbot.wait(1)

        frequency = panel.findChild(QLineEdit, "manualStartFrequencyEdit")
        log_edit = panel.findChild(QPlainTextEdit, "logTextEdit")
        assert frequency.palette().color(QPalette.ColorRole.Base) == QColor("#171a1f")
        assert frequency.palette().color(QPalette.ColorRole.Text) == QColor("#f0f2f4")
        assert log_edit.palette().color(QPalette.ColorRole.Base) == QColor("#171a1f")
        assert log_edit.palette().color(QPalette.ColorRole.Text) == QColor("#f0f2f4")
    finally:
        qapp.setPalette(original_palette)


def test_manual_panel_places_marker_actions_in_three_by_two_grid(qtbot) -> None:
    panel = ManualTestPanel(service=ManualTestService())
    qtbot.addWidget(panel)
    layout = panel.findChild(QGridLayout, "manualMarkerButtonLayout")
    object_names = (
        "manualMarkerPeakButton",
        "manualMarkerNextButton",
        "manualMarkerOffButton",
        "manualMarkerAllOffButton",
        "manualMarkerAutoMaxButton",
        "manualMarkerCenterButton",
    )

    assert layout is not None
    for index, object_name in enumerate(object_names):
        button = panel.findChild(QPushButton, object_name)
        row, column, row_span, column_span = layout.getItemPosition(
            layout.indexOf(button)
        )
        assert (row, column, row_span, column_span) == (
            index // 3,
            index % 3,
            1,
            1,
        )
        assert button.minimumHeight() == 28

    assert panel.findChild(QWidget, "manualStatusLabel").height() == 26


def test_manual_panel_custom_toggle_controls_frequency_edits(qtbot) -> None:
    panel = ManualTestPanel(service=ManualTestService())
    qtbot.addWidget(panel)
    custom = panel.findChild(QCheckBox, "manualCustomCheckBox")
    start = panel.findChild(QLineEdit, "manualStartFrequencyEdit")

    assert start.isReadOnly()
    custom.setChecked(True)
    assert not start.isReadOnly()
    start.setText("2000")
    custom.setChecked(False)
    assert start.isReadOnly()
    assert start.text() == "1000"


def test_manual_panel_enables_controls_by_capability(qtbot) -> None:
    service = ManualTestService()
    panel = ManualTestPanel(service=service)
    qtbot.addWidget(panel)

    service.set_equipment_state(
        {"FSV40": True, "CO3000": True, "3D Controller": True}
    )

    fsv40_buttons = tuple(
        panel.findChild(QPushButton, object_name)
        for object_name in (
            "manualSetButton",
            "manualPresetButton",
            "manualTraceClearButton",
        )
    )
    assert all(button.isEnabled() for button in fsv40_buttons)
    assert panel.findChild(QPushButton, "manualMarkerPeakButton").isEnabled()
    assert panel.findChild(QPushButton, "singleCaptureButton").isEnabled()
    assert panel.findChild(QPushButton, "nCaptureButton").isEnabled()
    assert panel.findChild(QPushButton, "manualSemiAutoButton").isEnabled()
    assert panel.findChild(QLineEdit, "manualSaturationTimeEdit").isEnabled()
    assert panel.findChild(QPushButton, "manualTurntableZeroButton").isEnabled()
    assert not panel.findChild(QPushButton, "manualStopButton").isEnabled()
    assert panel.findChild(QPushButton, "manualVerticalButton").isEnabled()

    panel.set_capabilities(ManualTestCapabilities())
    assert all(not button.isEnabled() for button in fsv40_buttons)
    assert not panel.findChild(QPushButton, "manualMarkerPeakButton").isEnabled()
    assert not panel.findChild(QPushButton, "manualTurntableZeroButton").isEnabled()
    assert not panel.findChild(QPushButton, "manualStopButton").isEnabled()
    assert not panel.findChild(QPushButton, "manualVerticalButton").isEnabled()


def test_manual_panel_enables_only_the_selected_mast_capability(qtbot) -> None:
    service = ManualTestService()
    panel = ManualTestPanel(service=service)
    qtbot.addWidget(panel)
    mast_combo = panel.findChild(QComboBox, "manualMastComboBox")
    vertical = panel.findChild(QPushButton, "manualVerticalButton")
    horizontal = panel.findChild(QPushButton, "manualHorizontalButton")

    service.set_equipment_state({"3D Controller": True})
    assert not vertical.isEnabled()
    assert not horizontal.isEnabled()

    mast_combo.setCurrentIndex(mast_combo.findText("1m Mast"))
    assert vertical.isEnabled()
    assert horizontal.isEnabled()


def test_manual_panel_semi_auto_requires_fsv40_and_co3000(qtbot) -> None:
    service = ManualTestService()
    panel = ManualTestPanel(service=service)
    qtbot.addWidget(panel)
    semi_auto = panel.findChild(QPushButton, "manualSemiAutoButton")
    saturation = panel.findChild(QLineEdit, "manualSaturationTimeEdit")
    stop = panel.findChild(QPushButton, "manualStopButton")

    service.set_equipment_state({"FSV40": True})
    assert not semi_auto.isEnabled()
    assert not saturation.isEnabled()
    assert not stop.isEnabled()

    service.set_equipment_state({"CO3000": True})
    assert not semi_auto.isEnabled()
    assert not saturation.isEnabled()
    assert not stop.isEnabled()

    service.set_equipment_state({"FSV40": True, "CO3000": True})
    assert semi_auto.isEnabled()
    assert saturation.isEnabled()
    assert not stop.isEnabled()


def test_manual_panel_locks_all_fsv40_commands_during_operations(qtbot) -> None:
    service = ManualTestService()
    panel = ManualTestPanel(service=service)
    qtbot.addWidget(panel)
    service.set_equipment_state(
        {"FSV40": True, "CO3000": True, "3D Controller": True}
    )
    buttons = tuple(
        panel.findChild(QPushButton, object_name)
        for object_name in (
            "manualSetButton",
            "manualPresetButton",
            "manualTraceClearButton",
            "manualMarkerPeakButton",
            "manualMarkerNextButton",
            "manualMarkerOffButton",
            "manualMarkerAllOffButton",
            "manualMarkerAutoMaxButton",
            "manualMarkerCenterButton",
            "singleCaptureButton",
            "nCaptureButton",
            "manualSemiAutoButton",
            "manualTurntableZeroButton",
            "manualTurntable360Button",
            "manualVerticalButton",
            "manualHorizontalButton",
        )
    )
    stop = panel.findChild(QPushButton, "manualStopButton")

    assert all(button.isEnabled() for button in buttons)
    assert not stop.isEnabled()

    service.running_changed.emit(True)
    assert all(not button.isEnabled() for button in buttons)
    assert stop.isEnabled()

    panel.set_operation_locked(True)
    assert all(not button.isEnabled() for button in buttons)
    assert stop.isEnabled()

    panel.set_operation_locked(False)
    assert all(not button.isEnabled() for button in buttons)
    assert stop.isEnabled()

    service.running_changed.emit(False)
    assert all(button.isEnabled() for button in buttons)
    assert not stop.isEnabled()


def test_manual_panel_semi_auto_passes_current_speed_and_saturation(qtbot) -> None:
    calls: list[tuple[object, ...]] = []

    class Commands:
        def get_turntable_angle(self, _client):
            calls.append(("get_turntable_angle",))
            return 90.0

        def rotate_turntable(
            self,
            _client,
            *,
            angle: float,
            turntable_speed: int,
        ) -> None:
            calls.append(("rotate_turntable", angle, turntable_speed))

    class Client(QObject):
        event_received = Signal(object)

    service = ManualTestService(
        client=Client(),
        commands=Commands(),
    )
    panel = ManualTestPanel(service=service)
    qtbot.addWidget(panel)
    service.set_equipment_state({"FSV40": True, "CO3000": True})
    panel.findChild(QSpinBox, "manualTurntableSpeedSpinBox").setValue(4)
    panel.findChild(QLineEdit, "manualSaturationTimeEdit").setText("2.5")

    qtbot.mouseClick(
        panel.findChild(QPushButton, "manualSemiAutoButton"),
        Qt.MouseButton.LeftButton,
    )

    assert calls == [
        ("get_turntable_angle",),
        ("rotate_turntable", 0.0, 4),
    ]
    assert service.is_running


def test_manual_panel_single_capture_saves_to_session_list(qtbot, tmp_path) -> None:
    temp_dir = tmp_path / "temp"

    class Commands:
        def get_screenshot(self, _client) -> bool:
            temp_dir.mkdir(parents=True, exist_ok=True)
            (temp_dir / "screenshot.png").write_bytes(
                b"\x89PNG\r\n\x1a\nfixture"
            )
            return True

    service = ManualTestService(
        client=object(),
        commands=Commands(),
        temp_dir=temp_dir,
    )
    panel = ManualTestPanel(service=service)
    qtbot.addWidget(panel)
    service.set_equipment_state({"FSV40": True})
    panel.findChild(QLineEdit, "captureDirectoryEdit").setText(str(tmp_path))
    panel.findChild(QLineEdit, "captureFileNameEdit").setText("manual")

    qtbot.mouseClick(
        panel.findChild(QPushButton, "singleCaptureButton"),
        Qt.MouseButton.LeftButton,
    )

    screenshot_list = panel.findChild(QListWidget, "manualScreenshotListWidget")
    assert (tmp_path / "manual.png").is_file()
    assert screenshot_list.count() == 1
    assert screenshot_list.item(0).text() == "manual.png"


def test_manual_panel_shows_n_capture_completion_message(
    qtbot,
    monkeypatch,
) -> None:
    service = ManualTestService()
    panel = ManualTestPanel(service=service)
    qtbot.addWidget(panel)
    calls: list[tuple[object, ...]] = []
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda parent, title, message: calls.append((parent, title, message)),
    )

    service.operation_finished.emit("N-Capture")

    assert calls == [(panel, "N-Capture", "N-Capture가 완료되었습니다.")]


def test_manual_panel_does_not_show_completion_message_for_other_or_failed_operations(
    qtbot,
    monkeypatch,
) -> None:
    service = ManualTestService()
    panel = ManualTestPanel(service=service)
    qtbot.addWidget(panel)
    information_calls: list[tuple[object, ...]] = []
    warning_calls: list[tuple[object, ...]] = []
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda *args: information_calls.append(args),
    )
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args: warning_calls.append(args),
    )

    service.operation_finished.emit("Single Capture")
    service.operation_failed.emit("N-Capture", "capture failed")

    assert information_calls == []
    assert warning_calls == [(panel, "N-Capture", "capture failed")]


def test_manual_panel_passes_displayed_directory_to_both_capture_actions(
    qtbot,
    tmp_path,
) -> None:
    service = ManualTestService(client=object())
    calls: list[tuple[object, ...]] = []
    service.capture_single = lambda **params: calls.append(
        ("single", params["directory"], params["base_name"])
    )
    service.capture_many = lambda **params: calls.append(
        (
            "many",
            params["directory"],
            params["base_name"],
            params["interval_sec"],
            params["shot_count"],
        )
    )
    panel = ManualTestPanel(service=service)
    qtbot.addWidget(panel)
    service.set_equipment_state({"FSV40": True})
    panel.findChild(QLineEdit, "captureDirectoryEdit").setText(str(tmp_path))
    panel.findChild(QLineEdit, "captureFileNameEdit").setText("manual")

    panel.findChild(QPushButton, "singleCaptureButton").click()
    panel.findChild(QPushButton, "nCaptureButton").click()

    assert calls == [
        ("single", tmp_path, "manual"),
        ("many", tmp_path, "manual", 1.0, 1),
    ]


def test_manual_panel_marker_buttons_use_existing_command_mapping(qtbot) -> None:
    calls: list[tuple[object, ...]] = []

    class Commands:
        def marker_peak(self, _client, **params):
            calls.append(("marker_peak", params))
            return True

        def marker_next(self, _client, **params):
            calls.append(("marker_next", params))
            return True

        def marker_off(self, _client, **params):
            calls.append(("marker_off", params))
            return True

        def marker_all_off(self, _client):
            calls.append(("marker_all_off",))
            return True

        def marker_auto_max(self, _client, **params):
            calls.append(("marker_auto_max", params))
            return True

        def marker_set_center(self, _client, **params):
            calls.append(("marker_set_center", params))
            return True

    service = ManualTestService(client=object(), commands=Commands())
    panel = ManualTestPanel(service=service)
    qtbot.addWidget(panel)
    service.set_equipment_state({"FSV40": True})
    panel.findChild(QComboBox, "manualTargetMarkerComboBox").setCurrentIndex(1)
    panel.findChild(QLineEdit, "manualNextPeakSearchLevelEdit").setText("3.5")

    for object_name in (
        "manualMarkerPeakButton",
        "manualMarkerNextButton",
        "manualMarkerOffButton",
        "manualMarkerAllOffButton",
        "manualMarkerAutoMaxButton",
        "manualMarkerCenterButton",
    ):
        panel.findChild(QPushButton, object_name).click()

    assert calls == [
        ("marker_peak", {"marker_index": 2, "excursion": 3.5}),
        ("marker_next", {"marker_index": 2, "excursion": 3.5}),
        ("marker_off", {"marker_index": 2, "excursion": 3.5}),
        ("marker_all_off",),
        ("marker_auto_max", {"marker_index": 2, "excursion": 0.0}),
        ("marker_set_center", {"marker_index": 2, "excursion": 0.0}),
    ]


def test_manual_panel_emits_tdf_requests_and_marks_active_item(qtbot) -> None:
    panel = ManualTestPanel(service=ManualTestService())
    qtbot.addWidget(panel)
    panel.set_capabilities(ManualTestCapabilities(fsv40=True))
    panel.set_tdf_file_list(["a.tdf", "b.tdf"])
    panel.findChild(QListWidget, "manualTdfListWidget").setCurrentRow(1)
    selected: list[str] = []
    panel.set_tdf_requested.connect(selected.append)

    panel.findChild(QPushButton, "manualSetTdfButton").click()
    panel.set_active_tdf_file_name("b.tdf")

    assert selected == ["b.tdf"]
    assert panel.findChild(QListWidget, "manualTdfListWidget").item(1).font().bold()


def test_manual_panel_adds_new_screenshot_first_and_displays_it(
    qtbot,
    tmp_path: Path,
) -> None:
    panel = ManualTestPanel(service=ManualTestService())
    qtbot.addWidget(panel)
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    image = QImage(8, 8, QImage.Format.Format_RGB32)
    image.fill(0xFFFFFF)
    assert image.save(str(first))
    assert image.save(str(second))

    panel.add_screenshot(str(first))
    panel.add_screenshot(str(second))

    screenshot_list = panel.findChild(QListWidget, "manualScreenshotListWidget")
    assert screenshot_list.count() == 2
    assert screenshot_list.item(0).text() == "second.png"
    assert screenshot_list.currentRow() == 0
