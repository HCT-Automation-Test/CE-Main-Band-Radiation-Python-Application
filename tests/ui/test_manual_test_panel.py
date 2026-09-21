from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtGui import QColor, QImage, QPalette
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QWidget,
)

from app.core.manual_test_service import ManualTestCapabilities, ManualTestService
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


def test_manual_panel_only_uses_search_level_for_marker_next(
    qtbot,
    monkeypatch,
) -> None:
    service = ManualTestService()
    panel = ManualTestPanel(service=service)
    qtbot.addWidget(panel)
    calls: list[tuple[object, ...]] = []
    monkeypatch.setattr(
        service,
        "marker_peak",
        lambda marker, excursion: calls.append(("peak", marker, excursion)) or True,
    )
    monkeypatch.setattr(
        service,
        "marker_next",
        lambda marker, excursion: calls.append(("next", marker, excursion)) or True,
    )
    monkeypatch.setattr(
        service,
        "marker_off",
        lambda marker, excursion: calls.append(("off", marker, excursion)) or True,
    )
    monkeypatch.setattr(
        service,
        "marker_auto_max",
        lambda marker: calls.append(("auto", marker)) or True,
    )
    monkeypatch.setattr(
        service,
        "marker_set_center",
        lambda marker: calls.append(("center", marker)) or True,
    )
    service.set_equipment_state({"FSV40": True})
    panel.findChild(QLineEdit, "manualNextPeakSearchLevelEdit").setText("7.5")

    for object_name in (
        "manualMarkerPeakButton",
        "manualMarkerNextButton",
        "manualMarkerOffButton",
        "manualMarkerAutoMaxButton",
        "manualMarkerCenterButton",
    ):
        panel.findChild(QPushButton, object_name).click()

    assert calls == [
        ("peak", 1, 0.0),
        ("next", 1, 7.5),
        ("off", 1, 0.0),
        ("auto", 1),
        ("center", 1),
    ]


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


def test_manual_panel_semi_auto_uses_current_saturation_without_set(
    qtbot,
    monkeypatch,
) -> None:
    service = ManualTestService()
    panel = ManualTestPanel(service=service)
    qtbot.addWidget(panel)
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        service,
        "run_semi_auto",
        lambda **kwargs: calls.append(kwargs) or True,
    )
    service.set_equipment_state({"FSV40": True, "CO3000": True})
    panel.findChild(QLineEdit, "manualSaturationTimeEdit").setText("7.5")

    semi_auto = panel.findChild(QPushButton, "manualSemiAutoButton")
    assert semi_auto.isEnabled()
    semi_auto.click()

    assert calls == [{"speed": 6, "saturation_time_sec": 7.5}]


@pytest.mark.parametrize("value", ["", "bad", "-1", "nan"])
def test_manual_panel_rejects_invalid_semi_auto_saturation(
    qtbot,
    monkeypatch,
    value: str,
) -> None:
    service = ManualTestService()
    panel = ManualTestPanel(service=service)
    qtbot.addWidget(panel)
    warnings: list[tuple[str, str]] = []
    monkeypatch.setattr(
        panel,
        "_show_warning",
        lambda title, message: warnings.append((title, message)),
    )
    service.set_equipment_state({"FSV40": True, "CO3000": True})
    panel.findChild(QLineEdit, "manualSaturationTimeEdit").setText(value)

    panel.findChild(QPushButton, "manualSemiAutoButton").click()

    assert warnings and warnings[0][0] == "Semi Auto"
    assert not service.is_running


@pytest.mark.parametrize(
    ("object_name", "value"),
    [
        ("manualStartFrequencyEdit", ""),
        ("manualStartFrequencyEdit", "not-a-number"),
        ("manualStartFrequencyEdit", "-1"),
        ("manualStartFrequencyEdit", "12750"),
        ("manualRbwEdit", "0"),
        ("manualVbwEdit", "0"),
        ("manualSaturationTimeEdit", "-1"),
    ],
)
def test_manual_panel_rejects_invalid_sa_input_before_set(
    qtbot,
    monkeypatch,
    object_name: str,
    value: str,
) -> None:
    service = ManualTestService()
    panel = ManualTestPanel(service=service)
    qtbot.addWidget(panel)
    calls: list[object] = []
    warnings: list[tuple[str, str]] = []
    monkeypatch.setattr(
        service,
        "apply_sa_settings",
        lambda settings: calls.append(settings) or True,
    )
    monkeypatch.setattr(
        panel,
        "_show_warning",
        lambda title, message: warnings.append((title, message)),
    )
    service.set_equipment_state({"FSV40": True})
    panel.findChild(QLineEdit, object_name).setText(value)

    panel.findChild(QPushButton, "manualSetButton").click()

    assert calls == []
    assert warnings and warnings[0][0] == "FSV40 Set"


def test_manual_panel_enables_controls_by_capability(qtbot) -> None:
    service = ManualTestService()
    panel = ManualTestPanel(service=service)
    qtbot.addWidget(panel)

    service.set_equipment_state({"FSV40": True})

    assert panel.findChild(QPushButton, "manualSetButton").isEnabled()
    assert panel.findChild(QPushButton, "manualMarkerPeakButton").isEnabled()
    assert panel.findChild(QPushButton, "singleCaptureButton").isEnabled()
    assert not panel.findChild(QPushButton, "manualTurntableZeroButton").isEnabled()

    panel.set_capabilities(
        ManualTestCapabilities(turntable=True, mast_3m=True),
    )
    assert panel.findChild(QPushButton, "manualTurntableZeroButton").isEnabled()
    assert panel.findChild(QPushButton, "manualVerticalButton").isEnabled()
    assert not panel.findChild(QPushButton, "manualSetButton").isEnabled()


def test_manual_panel_mast_buttons_follow_selected_controller(qtbot) -> None:
    service = ManualTestService()
    panel = ManualTestPanel(service=service)
    qtbot.addWidget(panel)
    mast = panel.findChild(QComboBox, "manualMastComboBox")
    vertical = panel.findChild(QPushButton, "manualVerticalButton")
    turntable = panel.findChild(QPushButton, "manualTurntableZeroButton")

    service.set_equipment_state({"CO3000": True})
    for index in (0, 1):
        mast.setCurrentIndex(index)
        assert vertical.isEnabled()
    mast.setCurrentIndex(2)
    assert not vertical.isEnabled()
    assert turntable.isEnabled()

    service.set_equipment_state({"3D Controller": True})
    assert vertical.isEnabled()
    assert not turntable.isEnabled()
    mast.setCurrentIndex(0)
    assert not vertical.isEnabled()


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
