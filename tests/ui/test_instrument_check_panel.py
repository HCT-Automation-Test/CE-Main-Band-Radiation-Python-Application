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

from app.core.instrument_connection import CONNECTION_IN_PROGRESS_MESSAGE
from app.ui.instrument_check_panel import InstrumentCheckPanel
from app.ui.log_panel import LogPanel


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
    assert any(
        label.text() == "CO3000(T.T, 3m/Bilog Mast)"
        for label in panel.findChildren(QLabel)
    )
    assert any(
        label.text() == "3D Controller(1m Mast)"
        for label in panel.findChildren(QLabel)
    )
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


def test_instrument_check_panel_block_reason_disables_connect(
    qtbot,
    monkeypatch,
) -> None:
    service = _Service()
    panel = InstrumentCheckPanel(service=service)
    qtbot.addWidget(panel)
    panel.show()
    qtbot.waitUntil(lambda: service.refresh_calls == 1, timeout=1000)
    _fill_valid_connection_fields(panel)
    warnings = []
    monkeypatch.setattr(panel, "_show_warning", warnings.append)

    panel.set_connection_block_reason("blocked")

    button = panel.findChild(QPushButton, "connectInstrumentButton")
    assert button is not None
    assert not button.isEnabled()

    panel.on_connect_clicked()

    assert service.connect_configs == []
    assert warnings == ["blocked"]

    panel.set_connection_block_reason(None)

    assert button.isEnabled()


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


def test_instrument_check_panel_preserves_state_for_blocked_service_error(
    qtbot,
    monkeypatch,
) -> None:
    service = _Service()
    panel = InstrumentCheckPanel(service=service)
    qtbot.addWidget(panel)
    panel.show()
    qtbot.waitUntil(lambda: service.refresh_calls == 1, timeout=1000)
    _fill_valid_connection_fields(panel)
    warnings: list[str] = []
    monkeypatch.setattr(panel, "_show_warning", warnings.append)
    ready_states = {
        "FSV40": True,
        "MT8000A": True,
        "CO3000": True,
        "Switch Box": True,
        "3D Controller": True,
    }

    with qtbot.waitSignal(panel.connection_succeeded, timeout=1000):
        panel.findChild(QPushButton, "connectInstrumentButton").click()
        service.connection_finished.emit(ready_states)

    panel.set_connection_block_reason("blocked")

    with qtbot.waitSignal(panel.connection_failed, timeout=1000) as blocker:
        service.error_occurred.emit("blocked")

    assert blocker.args == ["blocked"]
    assert warnings == ["blocked"]
    assert panel.equipment_state == ready_states
    assert panel.is_fully_connected
    for object_name in (
        "mt8000aStatusLabel",
        "fsv40StatusLabel",
        "co3000StatusLabel",
        "controller_3dStatusLabel",
        "switch_boxStatusLabel",
    ):
        assert panel.findChild(QLabel, object_name).text() == "Connected"


def test_instrument_check_panel_preserves_state_when_retry_is_still_in_progress(
    qtbot,
    monkeypatch,
) -> None:
    service = _Service()
    panel = InstrumentCheckPanel(service=service)
    qtbot.addWidget(panel)
    panel.show()
    qtbot.waitUntil(lambda: service.refresh_calls == 1, timeout=1000)
    _fill_valid_connection_fields(panel)
    warnings: list[str] = []
    monkeypatch.setattr(panel, "_show_warning", warnings.append)
    ready_states = {
        "FSV40": True,
        "MT8000A": True,
        "CO3000": True,
        "Switch Box": True,
        "3D Controller": True,
    }

    with qtbot.waitSignal(panel.connection_succeeded, timeout=1000):
        panel.findChild(QPushButton, "connectInstrumentButton").click()
        service.connection_finished.emit(ready_states)

    with qtbot.waitSignal(panel.connection_failed, timeout=1000) as blocker:
        panel.findChild(QPushButton, "connectInstrumentButton").click()
        service.error_occurred.emit(CONNECTION_IN_PROGRESS_MESSAGE)

    assert blocker.args == [CONNECTION_IN_PROGRESS_MESSAGE]
    assert warnings == [CONNECTION_IN_PROGRESS_MESSAGE]
    assert panel.equipment_state == ready_states
    assert panel.is_fully_connected
    for object_name in (
        "mt8000aStatusLabel",
        "fsv40StatusLabel",
        "co3000StatusLabel",
        "controller_3dStatusLabel",
        "switch_boxStatusLabel",
    ):
        assert panel.findChild(QLabel, object_name).text() == "Connected"


def test_instrument_check_panel_clears_state_for_real_service_error(
    qtbot,
    monkeypatch,
) -> None:
    service = _Service()
    panel = InstrumentCheckPanel(service=service)
    qtbot.addWidget(panel)
    panel.show()
    qtbot.waitUntil(lambda: service.refresh_calls == 1, timeout=1000)
    _fill_valid_connection_fields(panel)
    monkeypatch.setattr(panel, "_show_warning", lambda message: None)

    with qtbot.waitSignal(panel.connection_succeeded, timeout=1000):
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

    with qtbot.waitSignal(panel.connection_failed, timeout=1000) as blocker:
        panel.findChild(QPushButton, "connectInstrumentButton").click()
        service.connection_started.emit()
        service.error_occurred.emit("boom")

    assert blocker.args == ["boom"]
    assert panel.equipment_state == {}
    assert not panel.is_fully_connected


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

    assert blocker.args == ["장비 연결 실패: disconnected equipment: Switch Box"]


def test_instrument_check_panel_emits_failure_for_missing_equipment(
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
        service.connection_finished.emit({"FSV40": True})

    assert not panel.is_fully_connected
    assert blocker.args == [
        "장비 연결 실패: missing equipment: "
        "MT8000A, CO3000, Switch Box, 3D Controller"
    ]
