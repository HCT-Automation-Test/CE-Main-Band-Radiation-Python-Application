"""Instrument Check 서브 패널."""
from __future__ import annotations

from ipaddress import IPv4Address
import logging
from typing import Any

from PySide6.QtCore import QEvent, QTimer, Qt, Signal
from PySide6.QtGui import QCloseEvent, QHideEvent, QIntValidator, QShowEvent
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.core.instrument_connection import (
    InstrumentConnectionService,
    build_equipment_connection_config,
    describe_equipment_not_ready,
    is_selected_equipment_ready,
    normalize_equipment_state,
    should_preserve_equipment_state_on_connection_error,
)
from app.net.commands import EquipmentConnectionConfig
from app.ui.instrument_set_progress_dialog import InstrumentSetProgressDialog
from app.ui.log_panel import LogPanel

_VISA_EQUIPMENT: tuple[tuple[str, str, str], ...] = (
    ("CO3000(T.T, 3m/Bilog Mast)", "co3000", "co3000ResourceCombo"),
    ("3D Controller(1m Mast)", "controller_3d", "controller3dResourceCombo"),
    ("FSV40 Spectrum", "fsv40", "fsv40ResourceCombo"),
    ("MT8000A", "mt8000a", "mt8000aResourceCombo"),
)
_STATUS_KEYS: tuple[tuple[str, str], ...] = (
    ("MT8000A", "mt8000a"),
    ("FSV40", "fsv40"),
    ("CO3000", "co3000"),
    ("3D Controller", "controller_3d"),
    ("Switch Box", "switch_box"),
)
_RESULT_KEY_TO_STATUS_KEY = {
    "MT8000A": "mt8000a",
    "FSV40": "fsv40",
    "CO3000": "co3000",
    "3D Controller": "controller_3d",
    "Switch Box": "switch_box",
}
_STATUS_TEXT = {
    "not_connected": "Not Connected",
    "connecting": "Connecting",
    "connected": "Connected",
    "failed": "Failed",
}
_LOG_PANEL_WIDTH = 290
_FORM_PANEL_WIDTH = 560
_EQUIPMENT_LABEL_WIDTH = 170
_RESOURCE_INPUT_WIDTH = 250
_STATUS_WIDTH = 90
_SWITCH_BOX_IP_INPUT_WIDTH = 150
_SWITCH_BOX_PORT_INPUT_WIDTH = 54
_VISA_INITIAL_REFRESH_DELAY_MSEC = 250
_VISA_REFRESH_INTERVAL_MSEC = 5000

logger = logging.getLogger(__name__)


class InstrumentCheckPanel(QWidget):
    """5개 장비의 연결 정보 입력과 연결 상태를 표시한다."""

    connection_succeeded = Signal(object, dict)
    connection_failed = Signal(str)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        service: InstrumentConnectionService | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("instrumentCheckPanel")
        self._owns_service = service is None
        self._service = service or InstrumentConnectionService(self)
        self._resource_combos: dict[str, QComboBox] = {}
        self._status_labels: dict[str, QLabel] = {}
        self._last_connection_config: EquipmentConnectionConfig | None = None
        self._equipment_state: dict[str, bool] = {}
        self._connection_block_reason: str | None = None
        self._connection_in_progress = False
        self._set_in_progress = False
        self._set_progress_dialog: InstrumentSetProgressDialog | None = None
        self._visa_discovery_started = False
        self._shutdown_started = False
        self._visa_initial_refresh_timer = QTimer(self)
        self._visa_initial_refresh_timer.setSingleShot(True)
        self._visa_initial_refresh_timer.setInterval(_VISA_INITIAL_REFRESH_DELAY_MSEC)
        self._visa_refresh_timer = QTimer(self)
        self._visa_refresh_timer.setObjectName("visaAutoRefreshTimer")
        self._visa_refresh_timer.setInterval(_VISA_REFRESH_INTERVAL_MSEC)
        self._setup_layout()
        self._connect_signals()
        self._apply_styles()

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        """화면이 처음 표시될 때 VISA Resource를 자동 탐색한다."""

        super().showEvent(event)
        if self._shutdown_started:
            return
        if self._visa_discovery_started:
            self._visa_refresh_timer.start()
            return
        self._visa_initial_refresh_timer.start()
        self._visa_refresh_timer.start()

    def hideEvent(self, event: QHideEvent) -> None:  # noqa: N802
        """화면이 숨겨진 동안에는 VISA 자동 탐색을 멈춘다."""

        self._visa_refresh_timer.stop()
        self._visa_initial_refresh_timer.stop()
        super().hideEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """패널이 닫히기 전에 worker thread를 명시적으로 정리한다."""

        self.shutdown()
        super().closeEvent(event)

    def event(self, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Destroy:
            self.shutdown()
        return super().event(event)

    def _setup_layout(self) -> None:
        """Instrument Check 화면을 구성한다."""

        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(10)

        content_panel = QWidget(self)
        content_panel.setObjectName("instrumentCheckContentPanel")
        content_layout = QVBoxLayout(content_panel)
        content_layout.setContentsMargins(14, 50, 14, 14)
        content_layout.setSpacing(10)

        title = QLabel("Instrument Check", self)
        title.setObjectName("instrumentCheckTitleLabel")
        title.setProperty("titleLabel", True)
        title.hide()

        panel = QFrame(self)
        panel.setObjectName("instrumentCheckForm")
        panel.setFrameShape(QFrame.Shape.StyledPanel)
        panel.setFixedWidth(_FORM_PANEL_WIDTH)
        panel.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        form_layout = QGridLayout(panel)
        form_layout.setContentsMargins(8, 6, 8, 6)
        form_layout.setHorizontalSpacing(6)
        form_layout.setVerticalSpacing(7)

        for row, (label_text, key, object_name) in enumerate(_VISA_EQUIPMENT):
            label = QLabel(label_text, panel)
            label.setFixedWidth(_EQUIPMENT_LABEL_WIDTH)
            combo = QComboBox(panel)
            combo.setObjectName(object_name)
            combo.setEditable(True)
            combo.setFixedWidth(_RESOURCE_INPUT_WIDTH)
            status = self._create_status_label(key, panel)
            self._resource_combos[key] = combo
            form_layout.addWidget(label, row, 0)
            form_layout.addWidget(combo, row, 1)
            form_layout.addWidget(status, row, 2)

        switch_row = len(_VISA_EQUIPMENT)
        switch_label = QLabel("RF FilterBox (HCT)", panel)
        switch_label.setFixedWidth(_EQUIPMENT_LABEL_WIDTH)
        switch_inputs = QWidget(panel)
        switch_inputs.setObjectName("switchBoxInputPanel")
        switch_inputs_layout = QHBoxLayout(switch_inputs)
        switch_inputs_layout.setContentsMargins(0, 0, 0, 0)
        switch_inputs_layout.setSpacing(5)
        ip_label = QLabel("IP", panel)
        ip_label.setFixedWidth(18)
        self._switch_box_ip_edit = QLineEdit(panel)
        self._switch_box_ip_edit.setObjectName("switchBoxIpEdit")
        self._switch_box_ip_edit.setPlaceholderText("192.168.0.220")
        self._switch_box_ip_edit.setFixedWidth(_SWITCH_BOX_IP_INPUT_WIDTH)
        port_label = QLabel("Port", panel)
        port_label.setFixedWidth(26)
        self._switch_box_port_edit = QLineEdit(panel)
        self._switch_box_port_edit.setObjectName("switchBoxPortEdit")
        self._switch_box_port_edit.setValidator(QIntValidator(1, 65535, self))
        self._switch_box_port_edit.setPlaceholderText("80")
        self._switch_box_port_edit.setFixedWidth(_SWITCH_BOX_PORT_INPUT_WIDTH)
        switch_inputs_layout.addWidget(ip_label)
        switch_inputs_layout.addWidget(self._switch_box_ip_edit)
        switch_inputs_layout.addWidget(port_label)
        switch_inputs_layout.addWidget(self._switch_box_port_edit)
        form_layout.addWidget(switch_label, switch_row, 0)
        form_layout.addWidget(switch_inputs, switch_row, 1)
        form_layout.addWidget(self._create_status_label("switch_box", panel), switch_row, 2)

        form_layout.setColumnStretch(0, 0)
        form_layout.setColumnStretch(1, 0)
        form_layout.setColumnStretch(2, 0)
        content_layout.addWidget(panel, alignment=Qt.AlignmentFlag.AlignLeft)

        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(_EQUIPMENT_LABEL_WIDTH + 78, 0, 0, 0)
        button_layout.setSpacing(8)
        self._connect_button = QPushButton("Connect", self)
        self._connect_button.setObjectName("connectInstrumentButton")
        self._set_button = QPushButton("Set", self)
        self._set_button.setObjectName("setInstrumentButton")
        self._set_button.setEnabled(False)
        button_layout.addWidget(self._connect_button)
        button_layout.addWidget(self._set_button)
        button_layout.addStretch(1)
        content_layout.addLayout(button_layout)

        self._set_status_label = QLabel("장비 Set 대기", self)
        self._set_status_label.setObjectName("instrumentSetStatusLabel")
        content_layout.addWidget(
            self._set_status_label,
            alignment=Qt.AlignmentFlag.AlignLeft,
        )

        hint = QLabel(
            "Connected 상태: Close Device\nDisconnected 상태: Open Device",
            self,
        )
        hint.setObjectName("instrumentCheckHintLabel")
        content_layout.addWidget(hint, alignment=Qt.AlignmentFlag.AlignLeft)
        content_layout.addStretch(1)

        self._log_panel = LogPanel(self, logger=logging.getLogger())
        self._log_panel.setObjectName("instrumentCheckLogPanel")
        self._log_panel.setFixedWidth(_LOG_PANEL_WIDTH)

        root_layout.addWidget(content_panel, 1)
        root_layout.addWidget(self._log_panel)

    def _create_status_label(self, key: str, parent: QWidget) -> QLabel:
        status = QLabel(_STATUS_TEXT["not_connected"], parent)
        status.setObjectName(f"{key}StatusLabel")
        status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status.setProperty("connectionStatus", "not_connected")
        status.setFixedWidth(_STATUS_WIDTH)
        self._status_labels[key] = status
        return status

    def _connect_signals(self) -> None:
        """버튼과 서비스 시그널을 연결한다."""

        self._connect_button.clicked.connect(self.on_connect_clicked)
        self._set_button.clicked.connect(self.on_set_clicked)
        self._visa_initial_refresh_timer.timeout.connect(self._refresh_visa_resources)
        self._visa_refresh_timer.timeout.connect(self._refresh_visa_resources)
        self._service.visa_resources_discovered.connect(
            self.on_visa_resources_discovered,
        )
        self._service.visa_discovery_failed.connect(
            self.on_visa_discovery_failed,
        )
        self._service.connection_started.connect(self.on_connection_started)
        self._service.connection_finished.connect(self.on_connection_finished)
        self._service.error_occurred.connect(self.on_service_error)
        self._service.set_started.connect(self.on_set_started)
        self._service.set_step_changed.connect(self.on_set_step_changed)
        self._service.set_finished.connect(self.on_set_finished)
        self._service.set_failed.connect(self.on_set_failed)
        self._service.equipment_disconnected.connect(
            self.on_equipment_disconnected,
        )

    def shutdown(self) -> None:
        """패널 제거 시 자동 탐색/연결 worker를 정리한다."""

        if self._shutdown_started:
            return
        self._shutdown_started = True
        self._visa_initial_refresh_timer.stop()
        self._visa_refresh_timer.stop()
        self._close_set_progress_dialog()
        self._update_action_buttons_enabled()
        if self._owns_service:
            shutdown = getattr(self._service, "shutdown", None)
            if shutdown is not None:
                shutdown()

    @property
    def last_connection_config(self) -> EquipmentConnectionConfig | None:
        """마지막 Connect 요청에 사용한 설정을 반환한다."""

        return self._last_connection_config

    @property
    def equipment_state(self) -> dict[str, bool]:
        """마지막 장비 연결 결과를 반환한다."""

        return dict(self._equipment_state)

    @property
    def is_fully_connected(self) -> bool:
        """모든 장비가 연결 완료 상태인지 반환한다."""

        return is_selected_equipment_ready(self._equipment_state)

    @property
    def is_connecting(self) -> bool:
        """장비 연결 요청이 진행 중인지 반환한다."""

        return self._connection_in_progress

    def set_connection_block_reason(self, reason: str | None) -> None:
        """상위 실행 상태에 따라 연결 버튼 차단 사유를 설정한다."""

        self._connection_block_reason = reason
        self._update_action_buttons_enabled()

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QWidget#instrumentCheckPanel,
            QWidget#instrumentCheckContentPanel {
                background: #e2e2e2;
                color: #111111;
            }
            QWidget#switchBoxInputPanel {
                background: #ffffff;
                color: #111111;
            }
            QLabel {
                color: #111111;
                background: transparent;
            }
            QLabel[titleLabel="true"] {
                font-size: 22px;
                font-weight: 700;
                color: #111111;
            }
            QFrame#instrumentCheckForm {
                border: 1px solid #9aa7b1;
                background: #ffffff;
            }
            QComboBox,
            QComboBox QLineEdit,
            QComboBox QAbstractItemView,
            QLineEdit {
                background: #ffffff;
                color: #111111;
                border: 1px solid #b8c2cc;
                selection-background-color: #5a9bd5;
                selection-color: #ffffff;
            }
            QComboBox:disabled,
            QLineEdit:disabled {
                background: #f1f3f5;
                color: #555555;
            }
            QLabel[connectionStatus="not_connected"] {
                background: #e21b1b;
                color: #ffffff;
                font-weight: 700;
                padding: 5px 8px;
            }
            QLabel[connectionStatus="connecting"] {
                background: #f3c744;
                color: #111111;
                font-weight: 700;
                padding: 5px 8px;
            }
            QLabel[connectionStatus="connected"] {
                background: #0f8f3a;
                color: #ffffff;
                font-weight: 700;
                padding: 5px 8px;
            }
            QLabel[connectionStatus="failed"] {
                background: #e21b1b;
                color: #ffffff;
                font-weight: 700;
                padding: 5px 8px;
            }
            QPushButton {
                background: #f8f8f8;
                color: #111111;
                border: 1px solid #9aa7b1;
                min-height: 30px;
                padding: 4px 14px;
            }
            QPushButton:hover {
                background: #eef5ff;
            }
            QPushButton:disabled {
                background: #e6e8eb;
                color: #666666;
            }
            """
        )

    def _refresh_visa_resources(self) -> None:
        """화면 초기화 시 VISA Resource 탐색을 요청한다."""

        if self._shutdown_started:
            return
        self._visa_discovery_started = True
        self._service.refresh_visa_resources()

    def on_connect_clicked(self) -> None:
        """입력값 검증 후 장비 연결을 요청한다."""

        if self._connection_block_reason:
            self.connection_failed.emit(self._connection_block_reason)
            self._show_warning(self._connection_block_reason)
            return

        config = self._build_config_or_warn()
        if config is None:
            return
        logger.info("Instrument 연결 요청")
        self._last_connection_config = config
        self._connection_in_progress = True
        self._update_action_buttons_enabled()
        self._service.connect_equipment(config)

    def on_set_clicked(self) -> None:
        """연결 완료 상태의 장비 Set 작업을 요청한다."""

        if self._connection_block_reason:
            self._show_warning(self._connection_block_reason)
            return

        if not self.is_fully_connected or not self._has_connected_set_target():
            self._show_warning("Instrument Check 연결을 먼저 완료하세요.")
            return

        logger.info("Instrument Set 요청")
        self._service.set_equipment(dict(self._equipment_state))

    def on_visa_resources_discovered(self, resources: list[str]) -> None:
        """탐색된 VISA Resource를 콤보박스에 반영한다."""

        for combo in self._resource_combos.values():
            current_text = combo.currentText().strip()
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(resources)
            if current_text:
                index = combo.findText(current_text)
                if index < 0:
                    combo.insertItem(0, current_text)
                    index = 0
                combo.setCurrentIndex(index)
            else:
                combo.setCurrentIndex(-1)
            combo.blockSignals(False)

    def on_visa_discovery_failed(self, message: str) -> None:
        """자동 VISA 탐색 실패는 로그/팝업 없이 입력 가능한 빈 상태로 둔다."""

        _ = message

    def on_connection_started(self) -> None:
        """연결 진행 상태를 표시한다."""

        logger.info("Instrument 연결 진행 중")
        self._equipment_state = {}
        self._connection_in_progress = True
        self._update_action_buttons_enabled()
        selected_keys = self._selected_status_keys_from_config(
            self._last_connection_config
        )
        for _, key in _STATUS_KEYS:
            self._set_status(
                key,
                "connecting" if key in selected_keys else "not_connected",
            )

    def on_connection_finished(self, states: dict[str, bool]) -> None:
        """장비별 연결 결과를 표시한다."""

        logger.info("Instrument 연결 결과: %s", states)
        self._connection_in_progress = False
        self._equipment_state = normalize_equipment_state(states)
        for target, key in _RESULT_KEY_TO_STATUS_KEY.items():
            if target in states:
                self._set_status(key, "connected" if states.get(target) else "failed")
            else:
                self._set_status(key, "not_connected")
        self._update_action_buttons_enabled()
        if self.is_fully_connected:
            self.connection_succeeded.emit(
                self._last_connection_config,
                dict(self._equipment_state),
            )
            return
        self.connection_failed.emit(
            "장비 연결 실패: "
            + describe_equipment_not_ready(self._equipment_state)
        )

    def on_service_error(self, message: str) -> None:
        """서비스 오류를 사용자에게 알린다."""

        logger.error("Instrument Check 오류: %s", message)
        preserve_state = should_preserve_equipment_state_on_connection_error(
            message,
            block_reason=self._connection_block_reason,
        )
        self._connection_in_progress = False
        if not preserve_state:
            self._equipment_state = {}
        if not preserve_state and any(
            label.property("connectionStatus") == "connecting"
            for label in self._status_labels.values()
        ):
            for _, key in _STATUS_KEYS:
                if (
                    self._status_labels[key].property("connectionStatus")
                    == "connecting"
                ):
                    self._set_status(key, "failed")
        self._update_action_buttons_enabled()
        self.connection_failed.emit(message)
        self._show_warning(message)

    def on_set_started(self) -> None:
        """장비 Set 진행 상태를 UI에 반영한다."""

        self._set_in_progress = True
        self._set_button.setText("Setting...")
        self._set_status_label.setText("장비 Set 진행 중")
        self._show_set_progress_dialog("장비 Set 진행 중")
        self._update_action_buttons_enabled()

    def on_set_step_changed(self, message: str) -> None:
        """장비 Set 단계 변경 메시지를 표시한다."""

        self._set_status_label.setText(message)
        if self._set_progress_dialog is not None:
            self._set_progress_dialog.set_step(message)
        logger.info("Instrument Set 단계: %s", message)

    def on_set_finished(self) -> None:
        """장비 Set 완료 상태를 UI에 반영한다."""

        self._set_in_progress = False
        self._set_button.setText("Set")
        self._set_status_label.setText("장비 Set 완료")
        self._close_set_progress_dialog()
        self._update_action_buttons_enabled()
        self._show_info("장비 Set이 완료되었습니다.")

    def on_set_failed(self, message: str) -> None:
        """장비 Set 실패 상태를 UI에 반영한다."""

        self._set_in_progress = False
        self._set_button.setText("Set")
        self._set_status_label.setText("장비 Set 실패")
        self._close_set_progress_dialog()
        self._update_action_buttons_enabled()
        warning_message = (
            message
            if message.startswith("장비 Set 실패:")
            else f"장비 Set 실패: {message}"
        )
        self._show_warning(warning_message)

    def on_equipment_disconnected(self, states: dict[str, bool]) -> None:
        """장비 상태가 불명확해진 실제 실패/timeout을 disconnected로 표시한다."""

        _ = states
        self.mark_all_equipment_disconnected()

    def mark_all_equipment_disconnected(self) -> None:
        """모든 장비 표시를 Not Connected 상태로 초기화한다."""

        self._equipment_state = {}
        for _, key in _STATUS_KEYS:
            self._set_status(key, "not_connected")
        self._update_action_buttons_enabled()

    def _build_config_or_warn(self) -> EquipmentConnectionConfig | None:
        switch_box_ip_text = self._switch_box_ip_edit.text().strip()
        switch_box_port_text = self._switch_box_port_edit.text().strip()
        if bool(switch_box_ip_text) != bool(switch_box_port_text):
            self._show_warning("Switch Box IP와 Port를 모두 입력하거나 모두 비워두세요.")
            return None

        switch_box_ip = ""
        switch_box_port: int | None = None
        if switch_box_ip_text and switch_box_port_text:
            switch_box_ip = self._validated_switch_box_ip_or_warn()
            if switch_box_ip is None:
                return None

            switch_box_port = self._validated_switch_box_port_or_warn()
            if switch_box_port is None:
                return None

        if not self._has_selected_equipment(switch_box_ip, switch_box_port):
            self._show_warning("Connect할 장비를 하나 이상 선택하세요.")
            return None

        try:
            return build_equipment_connection_config(
                mt8000a_visa_resource=self._combo_text("mt8000a"),
                fsv40_visa_resource=self._combo_text("fsv40"),
                co3000_visa_resource=self._combo_text("co3000"),
                controller_3d_visa_resource=self._combo_text("controller_3d"),
                switch_box_ip_address=switch_box_ip,
                switch_box_port=switch_box_port,
            )
        except ValueError:
            self._show_warning(
                "Switch Box Port는 1~65535 사이의 숫자로 입력하세요.",
            )
            return None

    def _has_selected_equipment(
        self,
        switch_box_ip: str,
        switch_box_port: int | None,
    ) -> bool:
        return any(
            self._combo_text(key)
            for key in ("mt8000a", "fsv40", "co3000", "controller_3d")
        ) or (bool(switch_box_ip) and switch_box_port is not None)

    def _selected_status_keys_from_config(
        self,
        config: EquipmentConnectionConfig | None,
    ) -> set[str]:
        if config is None:
            return {key for _, key in _STATUS_KEYS}
        selected: set[str] = set()
        if config.mt8000a_visa_resource.strip():
            selected.add("mt8000a")
        if config.fsv40_visa_resource.strip():
            selected.add("fsv40")
        if config.co3000_visa_resource.strip():
            selected.add("co3000")
        if config.controller_3d_visa_resource.strip():
            selected.add("controller_3d")
        if config.switch_box_ip_address.strip() and config.switch_box_port is not None:
            selected.add("switch_box")
        return selected

    def _has_connected_set_target(self) -> bool:
        return any(
            self._equipment_state.get(target)
            for target in ("FSV40", "CO3000", "3D Controller")
        )

    def _validated_switch_box_ip_or_warn(self) -> str | None:
        value = self._switch_box_ip_edit.text().strip()
        try:
            IPv4Address(value)
        except ValueError:
            self._show_warning("Switch Box IP는 IPv4 형식으로 입력하세요.")
            return None
        return value

    def _validated_switch_box_port_or_warn(self) -> int | None:
        value = self._switch_box_port_edit.text().strip()
        try:
            port = int(value)
        except ValueError:
            self._show_warning(
                "Switch Box Port는 1~65535 사이의 숫자로 입력하세요.",
            )
            return None

        if not 1 <= port <= 65535:
            self._show_warning(
                "Switch Box Port는 1~65535 사이의 숫자로 입력하세요.",
            )
            return None
        return port

    def _combo_text(self, key: str) -> str:
        return self._resource_combos[key].currentText().strip()

    def _set_status(self, key: str, status: str) -> None:
        label = self._status_labels[key]
        label.setText(_STATUS_TEXT[status])
        label.setProperty("connectionStatus", status)
        label.style().unpolish(label)
        label.style().polish(label)

    def _update_connect_button_enabled(self) -> None:
        enabled = (
            not self._shutdown_started
            and not self._connection_in_progress
            and not self._set_in_progress
            and self._connection_block_reason is None
        )
        self._connect_button.setEnabled(enabled)
        self._connect_button.setToolTip(self._connection_block_reason or "")

    def _update_set_button_enabled(self) -> None:
        enabled = (
            not self._shutdown_started
            and not self._connection_in_progress
            and not self._set_in_progress
            and self._connection_block_reason is None
            and self.is_fully_connected
            and self._has_connected_set_target()
        )
        self._set_button.setEnabled(enabled)
        self._set_button.setToolTip(self._connection_block_reason or "")

    def _update_action_buttons_enabled(self) -> None:
        self._update_connect_button_enabled()
        self._update_set_button_enabled()

    def _show_set_progress_dialog(self, initial_step: str) -> None:
        """장시간 장비 Set 진행 상태를 modeless dialog로 표시한다."""

        self._close_set_progress_dialog()
        dialog = InstrumentSetProgressDialog(self, initial_step=initial_step)
        self._set_progress_dialog = dialog
        dialog.start()

    def _close_set_progress_dialog(self) -> None:
        """Set 완료/실패 또는 패널 정리 시 진행 dialog를 닫는다."""

        dialog = self._set_progress_dialog
        if dialog is None:
            return
        self._set_progress_dialog = None
        dialog.close_without_action()
        dialog.setParent(None)
        dialog.deleteLater()

    def _show_info(self, message: str) -> None:
        """어두운 OS 테마에서도 읽히는 안내 팝업을 표시한다."""

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle("Instrument Check")
        box.setText(message)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.setStyleSheet(
            """
            QMessageBox {
                background: #202124;
                color: #ffffff;
            }
            QMessageBox QLabel {
                color: #ffffff;
                background: transparent;
            }
            QMessageBox QPushButton {
                background: #3b3f45;
                color: #ffffff;
                border: 1px solid #8a9199;
                padding: 5px 18px;
                min-width: 72px;
            }
            QMessageBox QPushButton:hover {
                background: #4b5159;
            }
            """
        )
        box.exec()

    def _show_warning(self, message: str) -> None:
        """어두운 OS 테마에서도 읽히는 경고 팝업을 표시한다."""

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Instrument Check")
        box.setText(message)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.setStyleSheet(
            """
            QMessageBox {
                background: #202124;
                color: #ffffff;
            }
            QMessageBox QLabel {
                color: #ffffff;
                background: transparent;
            }
            QMessageBox QPushButton {
                background: #3b3f45;
                color: #ffffff;
                border: 1px solid #8a9199;
                padding: 5px 18px;
                min-width: 72px;
            }
            QMessageBox QPushButton:hover {
                background: #4b5159;
            }
            """
        )
        box.exec()

    def set_resource_text(self, key: str, value: str) -> None:
        """테스트와 상위 UI에서 콤보박스 값을 설정할 때 사용한다."""

        combo = self._resource_combos[key]
        if combo.findText(value) < 0:
            combo.addItem(value)
        combo.setCurrentText(value)

    def service(self) -> Any:
        """테스트에서 주입된 서비스를 확인할 수 있게 한다."""

        return self._service
