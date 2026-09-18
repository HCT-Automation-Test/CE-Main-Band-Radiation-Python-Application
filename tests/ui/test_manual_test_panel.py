from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QCheckBox, QComboBox, QLineEdit, QListWidget, QPushButton

from app.core.manual_test_service import ManualTestCapabilities, ManualTestService
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
