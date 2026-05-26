from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
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
    set_started = Signal()
    set_step_changed = Signal(str)
    set_finished = Signal()
    set_failed = Signal(str)
    equipment_disconnected = Signal(dict)

    def __init__(self) -> None:
        super().__init__()
        self.refresh_calls = 0
        self.connect_configs = []
        self.set_states = []
        self.shutdown_calls = 0

    def refresh_visa_resources(self) -> None:
        self.refresh_calls += 1

    def connect_equipment(self, config) -> None:
        self.connect_configs.append(config)

    def set_equipment(self, equipment_state) -> None:
        self.set_states.append(dict(equipment_state))

    def shutdown(self) -> None:
        self.shutdown_calls += 1


def _fill_valid_connection_fields(panel: InstrumentCheckPanel) -> None:
    panel.set_resource_text("mt8000a", "TCPIP0::192.168.0.3::inst0::INSTR")
    panel.set_resource_text("fsv40", "TCPIP0::192.168.0.2::inst0::INSTR")
    panel.set_resource_text("co3000", "ASRL1::INSTR")
    panel.set_resource_text("controller_3d", "ASRL2::INSTR")
    panel.findChild(QLineEdit, "switchBoxIpEdit").setText("192.168.0.10")
    panel.findChild(QLineEdit, "switchBoxPortEdit").setText("5000")


def _ready_equipment_state() -> dict[str, bool]:
    return {
        "FSV40": True,
        "MT8000A": True,
        "CO3000": True,
        "Switch Box": True,
        "3D Controller": True,
    }


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
    set_button = panel.findChild(QPushButton, "setInstrumentButton")
    assert set_button is not None
    assert set_button.text() == "Set"
    assert not set_button.isEnabled()
    set_status = panel.findChild(QLabel, "instrumentSetStatusLabel")
    assert set_status is not None
    assert set_status.text()
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
    assert "Connect" in warnings[0]


def test_instrument_check_panel_connects_with_partial_visa_selection(
    qtbot,
    monkeypatch,
) -> None:
    service = _Service()
    panel = InstrumentCheckPanel(service=service)
    qtbot.addWidget(panel)
    panel.show()
    qtbot.waitUntil(lambda: service.refresh_calls == 1, timeout=1000)
    monkeypatch.setattr(panel, "_show_warning", lambda message: None)

    panel.set_resource_text("fsv40", "TCPIP0::192.168.0.2::inst0::INSTR")
    panel.findChild(QPushButton, "connectInstrumentButton").click()

    assert len(service.connect_configs) == 1
    config = service.connect_configs[0]
    assert config.fsv40_visa_resource == "TCPIP0::192.168.0.2::inst0::INSTR"
    assert config.mt8000a_visa_resource == ""
    assert config.switch_box_ip_address == ""
    assert config.switch_box_port is None


def test_instrument_check_panel_rejects_half_filled_switch_box(
    qtbot,
    monkeypatch,
) -> None:
    service = _Service()
    panel = InstrumentCheckPanel(service=service)
    qtbot.addWidget(panel)
    panel.show()
    qtbot.waitUntil(lambda: service.refresh_calls == 1, timeout=1000)
    warnings: list[str] = []
    monkeypatch.setattr(panel, "_show_warning", warnings.append)

    panel.findChild(QLineEdit, "switchBoxIpEdit").setText("192.168.0.10")
    panel.findChild(QPushButton, "connectInstrumentButton").click()

    assert service.connect_configs == []
    assert warnings
    assert "Switch Box" in warnings[0]


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


def test_instrument_check_panel_enables_set_after_all_equipment_connected(
    qtbot,
) -> None:
    service = _Service()
    panel = InstrumentCheckPanel(service=service)
    qtbot.addWidget(panel)
    panel.show()
    qtbot.waitUntil(lambda: service.refresh_calls == 1, timeout=1000)

    set_button = panel.findChild(QPushButton, "setInstrumentButton")
    assert set_button is not None
    assert not set_button.isEnabled()

    service.connection_finished.emit(_ready_equipment_state())

    assert set_button.isEnabled()


def test_instrument_check_panel_keeps_set_disabled_for_partial_connection(
    qtbot,
) -> None:
    service = _Service()
    panel = InstrumentCheckPanel(service=service)
    qtbot.addWidget(panel)
    panel.show()
    qtbot.waitUntil(lambda: service.refresh_calls == 1, timeout=1000)

    service.connection_finished.emit(
        {
            "FSV40": True,
            "MT8000A": True,
            "CO3000": True,
            "Switch Box": False,
            "3D Controller": True,
        }
    )

    set_button = panel.findChild(QPushButton, "setInstrumentButton")
    assert set_button is not None
    assert not set_button.isEnabled()


def test_instrument_check_panel_set_click_calls_service_with_equipment_state(
    qtbot,
) -> None:
    service = _Service()
    panel = InstrumentCheckPanel(service=service)
    qtbot.addWidget(panel)
    panel.show()
    qtbot.waitUntil(lambda: service.refresh_calls == 1, timeout=1000)
    ready_states = _ready_equipment_state()
    service.connection_finished.emit(ready_states)

    panel.findChild(QPushButton, "setInstrumentButton").click()

    assert service.set_states == [ready_states]


def test_instrument_check_panel_rejects_set_when_not_connected(
    qtbot,
    monkeypatch,
) -> None:
    service = _Service()
    panel = InstrumentCheckPanel(service=service)
    qtbot.addWidget(panel)
    panel.show()
    qtbot.waitUntil(lambda: service.refresh_calls == 1, timeout=1000)
    warnings: list[str] = []
    monkeypatch.setattr(panel, "_show_warning", warnings.append)

    panel.on_set_clicked()

    assert service.set_states == []
    assert warnings
    assert "Instrument Check" in warnings[0]


def test_instrument_check_panel_set_started_disables_connect_and_set(qtbot) -> None:
    service = _Service()
    panel = InstrumentCheckPanel(service=service)
    qtbot.addWidget(panel)
    panel.show()
    qtbot.waitUntil(lambda: service.refresh_calls == 1, timeout=1000)
    service.connection_finished.emit(_ready_equipment_state())

    service.set_started.emit()

    connect_button = panel.findChild(QPushButton, "connectInstrumentButton")
    set_button = panel.findChild(QPushButton, "setInstrumentButton")
    assert connect_button is not None
    assert set_button is not None
    assert not connect_button.isEnabled()
    assert not set_button.isEnabled()
    assert set_button.text() == "Setting..."
    dialog = panel.findChild(QDialog, "instrumentSetProgressDialog")
    assert dialog is not None
    assert dialog.isVisible()
    assert not dialog.isModal()


def test_instrument_check_panel_set_step_updates_status_label(qtbot) -> None:
    service = _Service()
    panel = InstrumentCheckPanel(service=service)
    qtbot.addWidget(panel)
    panel.show()
    qtbot.waitUntil(lambda: service.refresh_calls == 1, timeout=1000)

    service.set_step_changed.emit("CO3000 step")

    label = panel.findChild(QLabel, "instrumentSetStatusLabel")
    assert label is not None
    assert label.text() == "CO3000 step"


def test_instrument_check_panel_set_step_updates_progress_dialog(qtbot) -> None:
    service = _Service()
    panel = InstrumentCheckPanel(service=service)
    qtbot.addWidget(panel)
    panel.show()
    qtbot.waitUntil(lambda: service.refresh_calls == 1, timeout=1000)

    service.set_started.emit()
    service.set_step_changed.emit("CO3000 step")

    dialog = panel.findChild(QDialog, "instrumentSetProgressDialog")
    assert dialog is not None
    step_label = dialog.findChild(QLabel, "instrumentSetProgressStepLabel")
    assert step_label is not None
    assert step_label.text() == "CO3000 step"


def test_instrument_check_panel_set_finished_shows_info_and_updates_buttons(
    qtbot,
    monkeypatch,
) -> None:
    service = _Service()
    panel = InstrumentCheckPanel(service=service)
    qtbot.addWidget(panel)
    panel.show()
    qtbot.waitUntil(lambda: service.refresh_calls == 1, timeout=1000)
    service.connection_finished.emit(_ready_equipment_state())
    infos: list[str] = []
    monkeypatch.setattr(panel, "_show_info", infos.append)

    service.set_started.emit()
    dialog = panel.findChild(QDialog, "instrumentSetProgressDialog")
    assert dialog is not None
    service.set_finished.emit()
    qtbot.wait(0)

    set_button = panel.findChild(QPushButton, "setInstrumentButton")
    label = panel.findChild(QLabel, "instrumentSetStatusLabel")
    assert set_button is not None
    assert label is not None
    assert set_button.isEnabled()
    assert set_button.text() == "Set"
    assert "Set" in label.text()
    assert not dialog.isVisible()
    assert panel.findChild(QDialog, "instrumentSetProgressDialog") is None
    assert infos


def test_instrument_check_panel_set_failed_preserves_equipment_state(
    qtbot,
    monkeypatch,
) -> None:
    service = _Service()
    panel = InstrumentCheckPanel(service=service)
    qtbot.addWidget(panel)
    panel.show()
    qtbot.waitUntil(lambda: service.refresh_calls == 1, timeout=1000)
    service.connection_finished.emit(_ready_equipment_state())
    warnings: list[str] = []
    monkeypatch.setattr(panel, "_show_warning", warnings.append)

    service.set_started.emit()
    dialog = panel.findChild(QDialog, "instrumentSetProgressDialog")
    assert dialog is not None
    service.set_failed.emit("timeout")
    qtbot.wait(0)

    assert panel.equipment_state == _ready_equipment_state()
    assert warnings[0].endswith("timeout")
    assert "Set" in panel.findChild(QLabel, "instrumentSetStatusLabel").text()
    assert panel.findChild(QPushButton, "setInstrumentButton").isEnabled()
    assert not dialog.isVisible()
    assert panel.findChild(QDialog, "instrumentSetProgressDialog") is None
    for object_name in (
        "mt8000aStatusLabel",
        "fsv40StatusLabel",
        "co3000StatusLabel",
        "controller_3dStatusLabel",
        "switch_boxStatusLabel",
    ):
        status = panel.findChild(QLabel, object_name)
        assert status is not None
        assert status.text() == "Connected"
        assert status.property("connectionStatus") == "connected"


def test_instrument_check_panel_set_failed_does_not_duplicate_failure_prefix(
    qtbot,
    monkeypatch,
) -> None:
    service = _Service()
    panel = InstrumentCheckPanel(service=service)
    qtbot.addWidget(panel)
    panel.show()
    qtbot.waitUntil(lambda: service.refresh_calls == 1, timeout=1000)
    service.connection_finished.emit(_ready_equipment_state())
    warnings: list[str] = []
    monkeypatch.setattr(panel, "_show_warning", warnings.append)

    service.set_started.emit()
    service.set_failed.emit(
        "장비 Set 실패: CO3000 / Set Reference failed: reference failed"
    )
    qtbot.wait(0)

    assert warnings == [
        "장비 Set 실패: CO3000 / Set Reference failed: reference failed"
    ]


def test_instrument_check_panel_equipment_disconnected_marks_not_connected(
    qtbot,
) -> None:
    service = _Service()
    panel = InstrumentCheckPanel(service=service)
    qtbot.addWidget(panel)
    panel.show()
    qtbot.waitUntil(lambda: service.refresh_calls == 1, timeout=1000)
    service.connection_finished.emit(_ready_equipment_state())

    service.equipment_disconnected.emit(
        {
            "FSV40": False,
            "MT8000A": False,
            "CO3000": False,
            "Switch Box": False,
            "3D Controller": False,
        }
    )

    assert panel.equipment_state == {}
    assert not panel.findChild(QPushButton, "setInstrumentButton").isEnabled()
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
        assert status.property("connectionStatus") == "not_connected"


def test_instrument_check_panel_set_stays_disabled_with_block_reason(
    qtbot,
    monkeypatch,
) -> None:
    service = _Service()
    panel = InstrumentCheckPanel(service=service)
    qtbot.addWidget(panel)
    panel.show()
    qtbot.waitUntil(lambda: service.refresh_calls == 1, timeout=1000)
    service.connection_finished.emit(_ready_equipment_state())
    monkeypatch.setattr(panel, "_show_info", lambda message: None)

    panel.set_connection_block_reason("blocked")
    service.set_started.emit()
    service.set_finished.emit()

    set_button = panel.findChild(QPushButton, "setInstrumentButton")
    assert set_button is not None
    assert not set_button.isEnabled()


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


def test_instrument_check_panel_emits_success_for_selected_partial_connection(
    qtbot,
) -> None:
    service = _Service()
    panel = InstrumentCheckPanel(service=service)
    qtbot.addWidget(panel)
    panel.show()
    qtbot.waitUntil(lambda: service.refresh_calls == 1, timeout=1000)
    panel.set_resource_text("fsv40", "TCPIP0::192.168.0.2::inst0::INSTR")

    with qtbot.waitSignal(panel.connection_succeeded, timeout=1000):
        panel.findChild(QPushButton, "connectInstrumentButton").click()
        service.connection_started.emit()
        service.connection_finished.emit({"FSV40": True})

    assert panel.findChild(QLabel, "fsv40StatusLabel").text() == "Connected"
    assert panel.findChild(QLabel, "mt8000aStatusLabel").text() == "Not Connected"
    assert panel.findChild(QLabel, "co3000StatusLabel").text() == "Not Connected"
    assert panel.findChild(QLabel, "controller_3dStatusLabel").text() == "Not Connected"
    assert panel.findChild(QLabel, "switch_boxStatusLabel").text() == "Not Connected"
    assert panel.equipment_state == {"FSV40": True}
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

    assert blocker.args[0].endswith("disconnected equipment: Switch Box")


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
        service.connection_finished.emit({"FSV40": False})

    assert not panel.is_fully_connected
    assert blocker.args[0].endswith("disconnected equipment: FSV40")
