from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QWidget,
)

from app.ui.log_panel import LogPanel
from app.ui.instrument_check_panel import InstrumentCheckPanel


class _Service(QObject):
    visa_resources_discovered = Signal(list)
    visa_discovery_failed = Signal(str)
    connection_started = Signal()
    connection_finished = Signal(dict)
    error_occurred = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.refresh_calls = 0
        self.connect_configs = []
        self.shutdown_calls = 0

    def refresh_visa_resources(self) -> None:
        self.refresh_calls += 1

    def connect_equipment(self, config) -> None:
        self.connect_configs.append(config)

    def shutdown(self) -> None:
        self.shutdown_calls += 1


def _fill_valid_connection_fields(panel: InstrumentCheckPanel) -> None:
    panel.set_resource_text("mt8000a", "TCPIP0::192.168.0.3::inst0::INSTR")
    panel.set_resource_text("fsv40", "TCPIP0::192.168.0.2::inst0::INSTR")
    panel.set_resource_text("co3000", "ASRL1::INSTR")
    panel.set_resource_text("controller_3d", "ASRL2::INSTR")
    panel.findChild(QLineEdit, "switchBoxIpEdit").setText("192.168.0.10")
    panel.findChild(QLineEdit, "switchBoxPortEdit").setText("5000")


def test_instrument_check_panel_exposes_expected_widgets(qtbot) -> None:
    service = _Service()
    panel = InstrumentCheckPanel(service=service)
    qtbot.addWidget(panel)
    panel.show()
    qtbot.waitUntil(lambda: service.refresh_calls == 1, timeout=1000)

    for object_name in (
        "mt8000aResourceCombo",
        "fsv40ResourceCombo",
        "co3000ResourceCombo",
        "controller3dResourceCombo",
    ):
        combo = panel.findChild(QComboBox, object_name)
        assert combo is not None
        assert combo.isEditable()

    assert panel.findChild(QLineEdit, "switchBoxIpEdit") is not None
    assert panel.findChild(QLineEdit, "switchBoxPortEdit") is not None
    assert panel.findChild(QPushButton, "refreshVisaButton") is None
    assert panel.findChild(QPushButton, "connectInstrumentButton") is not None
    assert panel.findChild(QWidget, "instrumentCheckContentPanel") is not None
    assert panel.findChild(LogPanel, "instrumentCheckLogPanel") is not None
    assert panel.findChild(QPlainTextEdit, "logTextEdit") is not None
    for object_name in (
        "mt8000aStatusLabel",
        "fsv40StatusLabel",
        "co3000StatusLabel",
        "controller_3dStatusLabel",
        "switch_boxStatusLabel",
    ):
        status = panel.findChild(QLabel, object_name)
        assert status is not None
        assert status.text() == "Not Connected"


def test_instrument_check_panel_auto_refresh_updates_all_visa_combos(qtbot) -> None:
    service = _Service()
    panel = InstrumentCheckPanel(service=service)
    qtbot.addWidget(panel)
    panel.show()
    qtbot.waitUntil(lambda: service.refresh_calls == 1, timeout=1000)

    service.visa_resources_discovered.emit(["ASRL1::INSTR", "ASRL2::INSTR"])

    assert service.refresh_calls == 1
    for object_name in (
        "mt8000aResourceCombo",
        "fsv40ResourceCombo",
        "co3000ResourceCombo",
        "controller3dResourceCombo",
    ):
        combo = panel.findChild(QComboBox, object_name)
        assert combo is not None
        assert [combo.itemText(index) for index in range(combo.count())] == [
            "ASRL1::INSTR",
            "ASRL2::INSTR",
        ]
        assert combo.currentIndex() == -1
        assert combo.currentText() == ""


def test_instrument_check_panel_preserves_manual_visa_text_on_refresh(qtbot) -> None:
    service = _Service()
    panel = InstrumentCheckPanel(service=service)
    qtbot.addWidget(panel)
    panel.show()
    qtbot.waitUntil(lambda: service.refresh_calls == 1, timeout=1000)
    panel.set_resource_text("mt8000a", "MANUAL::INSTR")

    service.visa_resources_discovered.emit(["ASRL1::INSTR", "ASRL2::INSTR"])

    combo = panel.findChild(QComboBox, "mt8000aResourceCombo")
    assert combo is not None
    assert combo.currentText() == "MANUAL::INSTR"
    assert combo.itemText(0) == "MANUAL::INSTR"
    assert [combo.itemText(index) for index in range(1, combo.count())] == [
        "ASRL1::INSTR",
        "ASRL2::INSTR",
    ]


def test_instrument_check_panel_periodically_refreshes_visa_resources(qtbot) -> None:
    service = _Service()
    panel = InstrumentCheckPanel(service=service)
    qtbot.addWidget(panel)
    panel.show()
    qtbot.waitUntil(lambda: service.refresh_calls == 1, timeout=1000)

    timer = panel.findChild(QTimer, "visaAutoRefreshTimer")
    assert timer is not None
    assert timer.isActive()
    assert timer.interval() == 5000

    timer.timeout.emit()

    assert service.refresh_calls == 2

    panel.hide()
    assert not timer.isActive()


def test_instrument_check_panel_shutdown_stops_timer_once(qtbot) -> None:
    service = _Service()
    panel = InstrumentCheckPanel(service=service)
    qtbot.addWidget(panel)
    panel.show()
    qtbot.waitUntil(lambda: service.refresh_calls == 1, timeout=1000)

    timer = panel.findChild(QTimer, "visaAutoRefreshTimer")
    assert timer is not None
    assert timer.isActive()

    panel.shutdown()
    timer.timeout.emit()
    panel.show()
    qtbot.wait(0)
    panel.shutdown()

    assert not timer.isActive()
    assert service.shutdown_calls == 0
    assert service.refresh_calls == 1


def test_instrument_check_panel_close_event_does_not_shutdown_injected_service(qtbot) -> None:
    service = _Service()
    panel = InstrumentCheckPanel(service=service)
    qtbot.addWidget(panel)
    panel.show()
    qtbot.waitUntil(lambda: service.refresh_calls == 1, timeout=1000)

    panel.close()

    assert service.shutdown_calls == 0


def test_instrument_check_panel_missing_fields_warns_without_connect(
    qtbot,
    monkeypatch,
) -> None:
    service = _Service()
    panel = InstrumentCheckPanel(service=service)
    qtbot.addWidget(panel)
    panel.show()
    qtbot.waitUntil(lambda: service.refresh_calls == 1, timeout=1000)
    warnings = []

    def fake_warning(message):
        warnings.append(message)

    monkeypatch.setattr(panel, "_show_warning", fake_warning)

    panel.findChild(QPushButton, "connectInstrumentButton").click()

    assert service.connect_configs == []
    assert warnings
    assert "MT8000A VISA Resource" in warnings[0]


def test_instrument_check_panel_rejects_invalid_switch_box_ip(
    qtbot,
    monkeypatch,
) -> None:
    service = _Service()
    panel = InstrumentCheckPanel(service=service)
    qtbot.addWidget(panel)
    panel.show()
    qtbot.waitUntil(lambda: service.refresh_calls == 1, timeout=1000)
    warnings = []

    monkeypatch.setattr(panel, "_show_warning", warnings.append)
    _fill_valid_connection_fields(panel)

    for ip_address in ("11.3.123", "999.1.1.1"):
        warnings.clear()
        panel.findChild(QLineEdit, "switchBoxIpEdit").setText(ip_address)

        panel.findChild(QPushButton, "connectInstrumentButton").click()

        assert service.connect_configs == []
        assert warnings
        assert "Switch Box IP" in warnings[0]


def test_instrument_check_panel_rejects_invalid_switch_box_port(
    qtbot,
    monkeypatch,
) -> None:
    service = _Service()
    panel = InstrumentCheckPanel(service=service)
    qtbot.addWidget(panel)
    panel.show()
    qtbot.waitUntil(lambda: service.refresh_calls == 1, timeout=1000)
    warnings = []

    monkeypatch.setattr(panel, "_show_warning", warnings.append)
    _fill_valid_connection_fields(panel)

    for port in ("0", "70000"):
        warnings.clear()
        panel.findChild(QLineEdit, "switchBoxPortEdit").setText(port)

        panel.findChild(QPushButton, "connectInstrumentButton").click()

        assert service.connect_configs == []
        assert warnings
        assert "Switch Box Port" in warnings[0]


def test_instrument_check_panel_connects_and_updates_statuses(qtbot) -> None:
    service = _Service()
    panel = InstrumentCheckPanel(service=service)
    qtbot.addWidget(panel)
    panel.show()
    qtbot.waitUntil(lambda: service.refresh_calls == 1, timeout=1000)
    _fill_valid_connection_fields(panel)

    panel.findChild(QPushButton, "connectInstrumentButton").click()
    service.connection_started.emit()
    service.connection_finished.emit(
        {
            "FSV40": True,
            "MT8000A": True,
            "CO3000": True,
            "Switch Box": False,
            "3D Controller": True,
        }
    )

    assert len(service.connect_configs) == 1
    assert service.connect_configs[0].switch_box_port == 5000
    assert panel.findChild(QLabel, "mt8000aStatusLabel").text() == "Connected"
    assert panel.findChild(QLabel, "fsv40StatusLabel").text() == "Connected"
    assert panel.findChild(QLabel, "co3000StatusLabel").text() == "Connected"
    assert panel.findChild(QLabel, "controller_3dStatusLabel").text() == "Connected"
    assert panel.findChild(QLabel, "switch_boxStatusLabel").text() == "Failed"
    assert not panel.is_fully_connected
    assert panel.equipment_state == {
        "FSV40": True,
        "MT8000A": True,
        "CO3000": True,
        "Switch Box": False,
        "3D Controller": True,
    }


def test_instrument_check_panel_emits_success_when_all_equipment_connected(
    qtbot,
) -> None:
    service = _Service()
    panel = InstrumentCheckPanel(service=service)
    qtbot.addWidget(panel)
    panel.show()
    qtbot.waitUntil(lambda: service.refresh_calls == 1, timeout=1000)
    _fill_valid_connection_fields(panel)

    with qtbot.waitSignal(panel.connection_succeeded, timeout=1000) as blocker:
        panel.findChild(QPushButton, "connectInstrumentButton").click()
        service.connection_finished.emit(
            {
                "FSV40": True,
                "MT8000A": True,
                "CO3000": True,
                "Switch Box": True,
                "3D Controller": True,
            }
        )

    config, states = blocker.args
    assert config is panel.last_connection_config
    assert states == panel.equipment_state
    assert panel.is_fully_connected


def test_instrument_check_panel_emits_failure_for_partial_connection(
    qtbot,
) -> None:
    service = _Service()
    panel = InstrumentCheckPanel(service=service)
    qtbot.addWidget(panel)
    panel.show()
    qtbot.waitUntil(lambda: service.refresh_calls == 1, timeout=1000)
    _fill_valid_connection_fields(panel)

    with qtbot.waitSignal(panel.connection_failed, timeout=1000) as blocker:
        panel.findChild(QPushButton, "connectInstrumentButton").click()
        service.connection_finished.emit(
            {
                "FSV40": True,
                "MT8000A": True,
                "CO3000": True,
                "Switch Box": False,
                "3D Controller": True,
            }
        )

    assert blocker.args == ["장비 연결 실패: Switch Box"]
