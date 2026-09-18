"""Manual Test 장비 제어 및 Screenshot 패널."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QDoubleValidator, QIntValidator, QPixmap, QResizeEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.core.manual_test_service import ManualTestCapabilities, ManualTestService
from app.models.enums import AntennaPol
from app.models.manual_test import (
    MANUAL_DETECTOR_MODES,
    MANUAL_FREQUENCY_PRESETS,
    ManualMast,
    ManualPresetId,
    ManualSaSettings,
    get_manual_frequency_preset,
)

_DEFAULT_PRESET = ManualPresetId.PRESET_3
_MAX_NEXT_PEAK_SEARCH_LEVEL_DB = 80.0


class ManualTestPanel(QWidget):
    """Manual Test 전체 제어를 한 화면에 제공한다."""

    get_tdf_list_requested = Signal()
    tdf_all_off_requested = Signal()
    set_tdf_requested = Signal(str)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        service: ManualTestService | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("manualTestPanel")
        self._service = service
        self._capabilities = (
            service.capabilities if service is not None else ManualTestCapabilities()
        )
        self._service_running = service.is_running if service is not None else False
        self._external_operation_locked = False
        self._tdf_operation_locked = False
        self._active_tdf_file_name: str | None = None
        self._source_pixmap: QPixmap | None = None
        self._build_ui()
        self._connect_controls()
        self._connect_service()
        self._apply_preset(_DEFAULT_PRESET)
        self._update_control_state()
        self._apply_styles()

    @property
    def service(self) -> ManualTestService | None:
        return self._service

    def _build_ui(self) -> None:
        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(10, 10, 10, 10)
        root_layout.setSpacing(12)

        left_panel = QWidget(self)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)
        left_layout.addWidget(self._create_screenshot_group(), 1)
        left_layout.addWidget(self._create_capture_group())

        right_panel = QWidget(self)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)
        right_layout.addWidget(self._create_sa_group(), 1)
        right_layout.addWidget(self._create_marker_group())
        self._status_label = QLabel("Manual Test 대기 중", right_panel)
        self._status_label.setObjectName("manualStatusLabel")
        self._status_label.setWordWrap(True)
        right_layout.addWidget(self._status_label)

        root_layout.addWidget(left_panel, 1)
        root_layout.addWidget(right_panel, 1)

    def _create_screenshot_group(self) -> QGroupBox:
        group = QGroupBox("SA Screenshot", self)
        group.setObjectName("manualScreenshotGroup")
        layout = QHBoxLayout(group)
        layout.setContentsMargins(8, 16, 8, 8)
        layout.setSpacing(8)

        frame = QFrame(group)
        frame.setObjectName("manualScreenshotFrame")
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(6, 6, 6, 6)
        self._screenshot_label = QLabel("Screenshot 대기 중", frame)
        self._screenshot_label.setObjectName("manualScreenshotImageLabel")
        self._screenshot_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._screenshot_label.setMinimumSize(420, 320)
        self._screenshot_label.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Ignored,
        )
        frame_layout.addWidget(self._screenshot_label, 1)

        self._screenshot_list = QListWidget(group)
        self._screenshot_list.setObjectName("manualScreenshotListWidget")
        self._screenshot_list.setMinimumWidth(180)
        self._screenshot_list.setMaximumWidth(250)
        self._screenshot_list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection,
        )
        layout.addWidget(frame, 1)
        layout.addWidget(self._screenshot_list)
        return group

    def _create_capture_group(self) -> QGroupBox:
        group = QGroupBox("Screenshot Capture", self)
        layout = QGridLayout(group)
        layout.setHorizontalSpacing(8)
        layout.setVerticalSpacing(6)

        self._capture_directory_edit = QLineEdit(group)
        self._capture_directory_edit.setObjectName("captureDirectoryEdit")
        browse_button = QPushButton("…", group)
        browse_button.setObjectName("captureDirectoryButton")
        browse_button.setFixedWidth(36)
        browse_button.clicked.connect(self._on_browse_directory)

        self._capture_name_edit = QLineEdit(group)
        self._capture_name_edit.setObjectName("captureFileNameEdit")
        self._capture_name_edit.setPlaceholderText("확장자 제외")
        self._capture_button = QPushButton("Capture", group)
        self._capture_button.setObjectName("singleCaptureButton")

        self._capture_interval_spin = QDoubleSpinBox(group)
        self._capture_interval_spin.setObjectName("captureIntervalSpinBox")
        self._capture_interval_spin.setRange(0.0, 86400.0)
        self._capture_interval_spin.setDecimals(1)
        self._capture_interval_spin.setValue(1.0)
        self._capture_interval_spin.setSuffix(" s")
        self._capture_shots_spin = QSpinBox(group)
        self._capture_shots_spin.setObjectName("captureShotsSpinBox")
        self._capture_shots_spin.setRange(1, 999)
        self._capture_shots_spin.setValue(1)
        self._n_capture_button = QPushButton("N-Capture", group)
        self._n_capture_button.setObjectName("nCaptureButton")

        layout.addWidget(QLabel("저장 폴더", group), 0, 0)
        layout.addWidget(self._capture_directory_edit, 0, 1, 1, 3)
        layout.addWidget(browse_button, 0, 4)
        layout.addWidget(QLabel("Screenshot File Name", group), 1, 0)
        layout.addWidget(self._capture_name_edit, 1, 1, 1, 3)
        layout.addWidget(self._capture_button, 1, 4)
        layout.addWidget(QLabel("Interval", group), 2, 0)
        layout.addWidget(self._capture_interval_spin, 2, 1)
        layout.addWidget(QLabel("N Shots", group), 2, 2)
        layout.addWidget(self._capture_shots_spin, 2, 3)
        layout.addWidget(self._n_capture_button, 2, 4)
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(3, 1)
        return group

    def _create_sa_group(self) -> QGroupBox:
        group = QGroupBox("SA Setting Panel", self)
        group.setObjectName("manualSaSettingGroup")
        layout = QHBoxLayout(group)
        layout.setContentsMargins(10, 16, 10, 8)
        layout.setSpacing(10)

        settings = QWidget(group)
        form = QGridLayout(settings)
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(5)
        self._preset_combo = QComboBox(settings)
        self._preset_combo.setObjectName("manualPresetComboBox")
        for preset in MANUAL_FREQUENCY_PRESETS:
            self._preset_combo.addItem(preset.label, preset.id)
        self._custom_check = QCheckBox("Custom On", settings)
        self._custom_check.setObjectName("manualCustomCheckBox")

        self._start_frequency_edit = self._number_edit("manualStartFrequencyEdit", settings)
        self._stop_frequency_edit = self._number_edit("manualStopFrequencyEdit", settings)
        self._rbw_edit = self._number_edit("manualRbwEdit", settings)
        self._vbw_edit = self._number_edit("manualVbwEdit", settings)
        self._sweep_point_edit = QLineEdit(settings)
        self._sweep_point_edit.setObjectName("manualSweepPointEdit")
        self._sweep_point_edit.setValidator(QIntValidator(1, 2_147_483_647, settings))
        self._sweep_point_edit.setText("30001")
        self._sweep_time_edit = self._number_edit("manualSweepTimeEdit", settings, "0.1")
        self._saturation_time_edit = self._number_edit(
            "manualSaturationTimeEdit", settings, "5"
        )
        self._atten_level_edit = self._number_edit("manualAttenLevelEdit", settings, "0")
        self._detector_combo = QComboBox(settings)
        self._detector_combo.setObjectName("manualDetectorModeComboBox")
        self._detector_combo.addItems(MANUAL_DETECTOR_MODES)
        self._detector_combo.setCurrentText("RMS")
        self._limit_edit = self._number_edit("manualLimitEdit", settings, "-30")

        form.addWidget(QLabel("Frequency Range", settings), 0, 0)
        form.addWidget(self._preset_combo, 0, 1, 1, 3)
        form.addWidget(self._custom_check, 1, 0, 1, 2)
        row_fields = (
            ("Start Freq (MHz)", self._start_frequency_edit, "Sweep Point", self._sweep_point_edit),
            ("Stop Freq (MHz)", self._stop_frequency_edit, "Sweep Time (s)", self._sweep_time_edit),
            ("RBW (MHz)", self._rbw_edit, "Saturation (s)", self._saturation_time_edit),
            ("VBW (MHz)", self._vbw_edit, "Atten Level (dB)", self._atten_level_edit),
            ("Detector Mode", self._detector_combo, "Line Limit (dBm)", self._limit_edit),
        )
        for row, (left_label, left_widget, right_label, right_widget) in enumerate(
            row_fields, start=2
        ):
            form.addWidget(QLabel(left_label, settings), row, 0)
            form.addWidget(left_widget, row, 1)
            form.addWidget(QLabel(right_label, settings), row, 2)
            form.addWidget(right_widget, row, 3)

        controls = QWidget(group)
        control_layout = QGridLayout(controls)
        control_layout.setContentsMargins(0, 0, 0, 0)
        control_layout.setSpacing(6)
        self._preset_button = self._button("Preset", "manualPresetButton", controls)
        self._set_button = self._button("Set", "manualSetButton", controls)
        self._trace_clear_button = self._button("Trace Clear", "manualTraceClearButton", controls)
        self._semi_auto_button = self._button("Semi Auto", "manualSemiAutoButton", controls)
        self._stop_button = self._button("Stop", "manualStopButton", controls)
        control_layout.addWidget(self._preset_button, 0, 0)
        control_layout.addWidget(self._semi_auto_button, 0, 1)
        control_layout.addWidget(self._stop_button, 0, 2, 2, 1)
        control_layout.addWidget(self._set_button, 1, 0)
        control_layout.addWidget(self._trace_clear_button, 1, 1)

        self._turntable_speed_spin = QSpinBox(controls)
        self._turntable_speed_spin.setObjectName("manualTurntableSpeedSpinBox")
        self._turntable_speed_spin.setRange(1, 10)
        self._turntable_speed_spin.setValue(6)
        self._turntable_zero_button = self._button("0°", "manualTurntableZeroButton", controls)
        self._turntable_360_button = self._button("360°", "manualTurntable360Button", controls)
        self._mast_combo = QComboBox(controls)
        self._mast_combo.setObjectName("manualMastComboBox")
        for mast in ManualMast:
            self._mast_combo.addItem(mast.value, mast)
        self._vertical_button = self._button("V", "manualVerticalButton", controls)
        self._horizontal_button = self._button("H", "manualHorizontalButton", controls)
        control_layout.addWidget(QLabel("Turn Table Speed", controls), 2, 0, 1, 2)
        control_layout.addWidget(self._turntable_speed_spin, 2, 2)
        control_layout.addWidget(self._turntable_zero_button, 3, 0)
        control_layout.addWidget(self._turntable_360_button, 3, 1)
        control_layout.addWidget(QLabel("Mast Type", controls), 4, 0)
        control_layout.addWidget(self._mast_combo, 4, 1, 1, 2)
        control_layout.addWidget(self._vertical_button, 5, 1)
        control_layout.addWidget(self._horizontal_button, 5, 2)
        control_layout.setRowStretch(6, 1)

        tdf_group = QGroupBox("FSV Factor List", group)
        tdf_layout = QVBoxLayout(tdf_group)
        tdf_layout.setContentsMargins(6, 14, 6, 6)
        self._tdf_list = QListWidget(tdf_group)
        self._tdf_list.setObjectName("manualTdfListWidget")
        tdf_buttons = QHBoxLayout()
        self._tdf_select_button = self._button("Select", "manualSetTdfButton", tdf_group)
        self._tdf_all_off_button = self._button("All Off", "manualTdfAllOffButton", tdf_group)
        self._tdf_update_button = self._button("List Update", "manualGetTdfListButton", tdf_group)
        tdf_buttons.addWidget(self._tdf_select_button)
        tdf_buttons.addWidget(self._tdf_all_off_button)
        tdf_buttons.addWidget(self._tdf_update_button)
        tdf_layout.addWidget(self._tdf_list, 1)
        tdf_layout.addLayout(tdf_buttons)
        layout.addWidget(settings, 5)
        layout.addWidget(controls, 3)
        layout.addWidget(tdf_group, 3)
        return group

    def _create_marker_group(self) -> QGroupBox:
        group = QGroupBox("Marker Setting Panel", self)
        layout = QGridLayout(group)
        self._marker_combo = QComboBox(group)
        self._marker_combo.setObjectName("manualTargetMarkerComboBox")
        for index in range(1, 11):
            self._marker_combo.addItem(f"Marker {index}", index)
        self._excursion_edit = self._number_edit(
            "manualNextPeakSearchLevelEdit", group, "6"
        )
        self._excursion_edit.setValidator(
            QDoubleValidator(0.0, _MAX_NEXT_PEAK_SEARCH_LEVEL_DB, 3, group)
        )
        self._marker_peak_button = self._button("Peak", "manualMarkerPeakButton", group)
        self._marker_next_button = self._button("Next Peak", "manualMarkerNextButton", group)
        self._marker_off_button = self._button("OFF", "manualMarkerOffButton", group)
        self._marker_all_off_button = self._button("ALL Marker OFF", "manualMarkerAllOffButton", group)
        self._marker_auto_max_button = self._button("Auto Max Peak", "manualMarkerAutoMaxButton", group)
        self._marker_center_button = self._button("Mkr→Center", "manualMarkerCenterButton", group)
        layout.addWidget(QLabel("Target Marker", group), 0, 0)
        layout.addWidget(self._marker_combo, 0, 1, 1, 5)
        layout.addWidget(QLabel("Next Peak Search Level", group), 1, 0)
        layout.addWidget(self._excursion_edit, 1, 1, 1, 5)
        for column, button in enumerate(
            (
                self._marker_peak_button,
                self._marker_next_button,
                self._marker_off_button,
                self._marker_all_off_button,
                self._marker_auto_max_button,
                self._marker_center_button,
            )
        ):
            layout.addWidget(button, 2, column)
        return group

    def _connect_controls(self) -> None:
        self._preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        self._custom_check.toggled.connect(self._on_custom_toggled)
        self._preset_button.clicked.connect(self._on_preset_clicked)
        self._set_button.clicked.connect(self._on_set_clicked)
        self._trace_clear_button.clicked.connect(self._on_trace_clear_clicked)
        self._semi_auto_button.clicked.connect(self._on_semi_auto_clicked)
        self._stop_button.clicked.connect(self._on_stop_clicked)
        self._turntable_zero_button.clicked.connect(lambda _checked=False: self._move_turntable(0.0))
        self._turntable_360_button.clicked.connect(lambda _checked=False: self._move_turntable(360.0))
        self._mast_combo.currentIndexChanged.connect(self._update_control_state)
        self._vertical_button.clicked.connect(lambda _checked=False: self._set_polarization(AntennaPol.V))
        self._horizontal_button.clicked.connect(lambda _checked=False: self._set_polarization(AntennaPol.H))
        self._marker_peak_button.clicked.connect(lambda _checked=False: self._run_marker("peak"))
        self._marker_next_button.clicked.connect(lambda _checked=False: self._run_marker("next"))
        self._marker_off_button.clicked.connect(lambda _checked=False: self._run_marker("off"))
        self._marker_all_off_button.clicked.connect(self._on_marker_all_off_clicked)
        self._marker_auto_max_button.clicked.connect(lambda _checked=False: self._run_marker("auto"))
        self._marker_center_button.clicked.connect(lambda _checked=False: self._run_marker("center"))
        self._capture_button.clicked.connect(self._on_capture_clicked)
        self._n_capture_button.clicked.connect(self._on_n_capture_clicked)
        self._screenshot_list.currentItemChanged.connect(self._on_screenshot_selected)
        self._tdf_list.currentItemChanged.connect(self._update_control_state)
        self._tdf_update_button.clicked.connect(self.get_tdf_list_requested.emit)
        self._tdf_all_off_button.clicked.connect(self.tdf_all_off_requested.emit)
        self._tdf_select_button.clicked.connect(self._on_tdf_select_clicked)

    def _connect_service(self) -> None:
        if self._service is None:
            return
        self._service.capabilities_changed.connect(self.set_capabilities)
        self._service.applied_settings_changed.connect(self._on_applied_settings_changed)
        self._service.running_changed.connect(self._on_running_changed)
        self._service.operation_started.connect(self._on_operation_started)
        self._service.step_changed.connect(self._status_label.setText)
        self._service.operation_finished.connect(self._on_operation_finished)
        self._service.operation_cancelled.connect(self._on_operation_cancelled)
        self._service.operation_failed.connect(self._on_operation_failed)
        self._service.screenshot_saved.connect(self.add_screenshot)
        self._service.turntable_info_changed.connect(self._on_turntable_info_changed)

    @Slot(object)
    def set_capabilities(self, capabilities: ManualTestCapabilities) -> None:
        self._capabilities = capabilities
        self._update_control_state()

    def set_tdf_operation_locked(self, locked: bool) -> None:
        self._tdf_operation_locked = bool(locked)
        self._update_control_state()

    def set_operation_locked(self, locked: bool) -> None:
        """다른 전역 장비 operation 동안 Manual command 버튼을 잠근다."""

        self._external_operation_locked = bool(locked)
        self._update_control_state()

    def set_tdf_file_list(self, file_names: list[str]) -> None:
        self._tdf_list.clear()
        for file_name in file_names:
            item = QListWidgetItem(str(file_name))
            item.setData(Qt.ItemDataRole.UserRole, str(file_name))
            self._tdf_list.addItem(item)
        self._refresh_tdf_highlight()

    def set_active_tdf_file_name(self, file_name: str) -> None:
        self._active_tdf_file_name = str(file_name)
        self._refresh_tdf_highlight()

    def clear_active_tdf_file_name(self) -> None:
        self._active_tdf_file_name = None
        self._refresh_tdf_highlight()

    @Slot(str)
    def add_screenshot(self, path: str) -> None:
        screenshot_path = Path(path)
        item = QListWidgetItem(screenshot_path.name)
        item.setToolTip(str(screenshot_path))
        item.setData(Qt.ItemDataRole.UserRole, str(screenshot_path))
        self._screenshot_list.insertItem(0, item)
        self._screenshot_list.setCurrentItem(item)

    def _update_control_state(self, *_args: object) -> None:
        idle = not self._service_running and not self._external_operation_locked
        fsv = self._capabilities.fsv40 and idle
        for button in (self._preset_button, self._set_button, self._trace_clear_button):
            button.setEnabled(fsv)
        for button in (
            self._marker_peak_button,
            self._marker_next_button,
            self._marker_off_button,
            self._marker_all_off_button,
            self._marker_auto_max_button,
            self._marker_center_button,
        ):
            button.setEnabled(self._capabilities.marker and idle)
        self._capture_button.setEnabled(self._capabilities.capture and idle)
        self._n_capture_button.setEnabled(self._capabilities.capture and idle)
        self._turntable_zero_button.setEnabled(self._capabilities.turntable and idle)
        self._turntable_360_button.setEnabled(self._capabilities.turntable and idle)
        selected_mast = self._selected_mast()
        mast_ready = (
            self._capabilities.mast_1m
            if selected_mast is ManualMast.MAST_1M
            else self._capabilities.mast_3m
        )
        self._vertical_button.setEnabled(mast_ready and idle)
        self._horizontal_button.setEnabled(mast_ready and idle)
        semi_ready = (
            self._capabilities.semi_auto
            and self._service is not None
            and self._service.applied_saturation_time_sec is not None
        )
        self._semi_auto_button.setEnabled(semi_ready and idle)
        self._stop_button.setEnabled(self._service_running)
        tdf_ready = self._capabilities.fsv40 and idle and not self._tdf_operation_locked
        self._tdf_update_button.setEnabled(tdf_ready)
        self._tdf_all_off_button.setEnabled(tdf_ready)
        self._tdf_select_button.setEnabled(tdf_ready and self._tdf_list.currentItem() is not None)

    @Slot(bool)
    def _on_running_changed(self, active: bool) -> None:
        self._service_running = active
        self._update_control_state()

    @Slot(object)
    def _on_applied_settings_changed(self, _value: object) -> None:
        self._update_control_state()

    @Slot(str)
    def _on_operation_started(self, name: str) -> None:
        self._status_label.setText(f"{name} 시작")

    @Slot(str)
    def _on_operation_finished(self, name: str) -> None:
        self._status_label.setText(f"{name} 완료")
        self._update_control_state()

    @Slot(str)
    def _on_operation_cancelled(self, name: str) -> None:
        self._status_label.setText(f"{name} 중단")

    @Slot(str, str)
    def _on_operation_failed(self, name: str, message: str) -> None:
        self._status_label.setText(f"{name} 실패: {message}")
        self._show_warning(name, message)

    @Slot(object)
    def _on_turntable_info_changed(self, info: dict[str, object]) -> None:
        current = info.get("current_angle")
        target = info.get("target_angle")
        self._status_label.setText(
            f"Turntable {target}° 이동 중" if current is None else f"Turntable {current}°"
        )

    def _on_set_clicked(self) -> None:
        if self._service is None:
            return
        try:
            self._service.apply_sa_settings(self._build_sa_settings())
        except ValueError as exc:
            self._show_warning("FSV40 Set", str(exc))

    def _on_preset_clicked(self) -> None:
        if self._service is not None:
            self._service.preset_sa()

    def _on_trace_clear_clicked(self) -> None:
        if self._service is not None:
            self._service.clear_trace()

    def _on_semi_auto_clicked(self) -> None:
        if self._service is not None:
            self._service.run_semi_auto(speed=self._turntable_speed_spin.value())

    def _on_stop_clicked(self) -> None:
        if self._service is not None:
            self._service.request_stop()
            self._status_label.setText("중단 요청 중")

    def _move_turntable(self, angle: float) -> None:
        if self._service is not None:
            self._service.move_turntable(angle=angle, speed=self._turntable_speed_spin.value())

    def _set_polarization(self, polarization: AntennaPol) -> None:
        if self._service is not None:
            self._service.set_mast_polarization(mast=self._selected_mast(), polarization=polarization)

    def _run_marker(self, action: str) -> None:
        if self._service is None:
            return
        try:
            marker_index = int(self._marker_combo.currentData())
            excursion = 0.0
            if action not in {"auto", "center"}:
                excursion = self._parse_float(
                    self._excursion_edit,
                    "Next Peak Search Level",
                )
                if not 0 <= excursion <= _MAX_NEXT_PEAK_SEARCH_LEVEL_DB:
                    raise ValueError(
                        "Next Peak Search Level은 "
                        f"0~{_MAX_NEXT_PEAK_SEARCH_LEVEL_DB:g} 범위여야 합니다."
                    )
            method = {
                "peak": self._service.marker_peak,
                "next": self._service.marker_next,
                "off": self._service.marker_off,
                "auto": self._service.marker_auto_max,
                "center": self._service.marker_set_center,
            }[action]
            method(marker_index, excursion)
        except ValueError as exc:
            self._show_warning("Marker", str(exc))

    def _on_marker_all_off_clicked(self) -> None:
        if self._service is not None:
            self._service.marker_all_off()

    def _on_capture_clicked(self) -> None:
        if self._service is None:
            return
        try:
            self._service.capture_single(
                directory=self._capture_directory(),
                base_name=self._capture_name_edit.text(),
            )
        except (ValueError, FileExistsError) as exc:
            self._show_warning("Single Capture", str(exc))

    def _on_n_capture_clicked(self) -> None:
        if self._service is None:
            return
        try:
            self._service.capture_many(
                directory=self._capture_directory(),
                base_name=self._capture_name_edit.text(),
                interval_sec=self._capture_interval_spin.value(),
                shot_count=self._capture_shots_spin.value(),
            )
        except (ValueError, FileExistsError) as exc:
            self._show_warning("N-Capture", str(exc))

    def _on_browse_directory(self) -> None:
        initial = self._capture_directory_edit.text().strip() or str(Path.cwd())
        selected = QFileDialog.getExistingDirectory(self, "Screenshot 저장 폴더", initial)
        if selected:
            self._capture_directory_edit.setText(selected)

    def _capture_directory(self) -> Path:
        value = self._capture_directory_edit.text().strip()
        if not value:
            raise ValueError("Screenshot 저장 폴더를 선택하세요.")
        return Path(value)

    def _on_tdf_select_clicked(self) -> None:
        item = self._tdf_list.currentItem()
        if item is not None:
            self.set_tdf_requested.emit(str(item.data(Qt.ItemDataRole.UserRole)))

    def _on_preset_changed(self) -> None:
        if not self._custom_check.isChecked():
            self._apply_preset(ManualPresetId(self._preset_combo.currentData()))

    def _on_custom_toggled(self, custom: bool) -> None:
        for edit in (
            self._start_frequency_edit,
            self._stop_frequency_edit,
            self._rbw_edit,
            self._vbw_edit,
        ):
            edit.setReadOnly(not custom)
        if not custom:
            self._set_preset_values(ManualPresetId(self._preset_combo.currentData()))

    def _apply_preset(self, preset_id: ManualPresetId) -> None:
        self._preset_combo.setCurrentIndex(int(preset_id) - 1)
        self._set_preset_values(preset_id)
        self._on_custom_toggled(self._custom_check.isChecked())

    def _set_preset_values(self, preset_id: ManualPresetId) -> None:
        preset = get_manual_frequency_preset(preset_id)
        self._start_frequency_edit.setText(f"{preset.start_frequency_mhz:g}")
        self._stop_frequency_edit.setText(f"{preset.stop_frequency_mhz:g}")
        self._rbw_edit.setText(f"{preset.rbw_mhz:g}")
        self._vbw_edit.setText(f"{preset.vbw_mhz:g}")

    def _build_sa_settings(self) -> ManualSaSettings:
        try:
            sweep_point = int(self._sweep_point_edit.text().strip())
        except ValueError as exc:
            raise ValueError("Sweep Point는 정수여야 합니다.") from exc
        return ManualSaSettings(
            start_frequency_mhz=self._parse_float(self._start_frequency_edit, "Start Frequency"),
            stop_frequency_mhz=self._parse_float(self._stop_frequency_edit, "Stop Frequency"),
            rbw_mhz=self._parse_float(self._rbw_edit, "RBW"),
            vbw_mhz=self._parse_float(self._vbw_edit, "VBW"),
            sweep_point=sweep_point,
            sweep_time_sec=self._parse_float(self._sweep_time_edit, "Sweep Time"),
            saturation_time_sec=self._parse_float(self._saturation_time_edit, "Saturation Time"),
            atten_level_db=self._parse_float(self._atten_level_edit, "Atten Level"),
            detector_mode=self._detector_combo.currentText(),
            limit_dbm=self._parse_float(self._limit_edit, "Line Limit"),
        )

    @staticmethod
    def _parse_float(edit: QLineEdit, field_name: str) -> float:
        try:
            return float(edit.text().strip())
        except ValueError as exc:
            raise ValueError(f"{field_name}은 숫자여야 합니다.") from exc

    def _selected_mast(self) -> ManualMast:
        value = self._mast_combo.currentData()
        return value if isinstance(value, ManualMast) else ManualMast(value)

    def _on_screenshot_selected(
        self,
        current: QListWidgetItem | None,
        _previous: QListWidgetItem | None,
    ) -> None:
        if current is None:
            return
        path = Path(str(current.data(Qt.ItemDataRole.UserRole)))
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            self._source_pixmap = None
            self._screenshot_label.setText(f"Screenshot을 불러올 수 없습니다.\n{path}")
            return
        self._source_pixmap = pixmap
        self._update_screenshot_pixmap()

    def _update_screenshot_pixmap(self) -> None:
        if self._source_pixmap is None:
            return
        self._screenshot_label.setText("")
        self._screenshot_label.setPixmap(
            self._source_pixmap.scaled(
                self._screenshot_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def _refresh_tdf_highlight(self) -> None:
        for index in range(self._tdf_list.count()):
            item = self._tdf_list.item(index)
            font = item.font()
            font.setBold(item.data(Qt.ItemDataRole.UserRole) == self._active_tdf_file_name)
            item.setFont(font)
        self._update_control_state()

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._update_screenshot_pixmap()

    @staticmethod
    def _number_edit(object_name: str, parent: QWidget, text: str = "") -> QLineEdit:
        edit = QLineEdit(parent)
        edit.setObjectName(object_name)
        edit.setValidator(QDoubleValidator(-1.0e12, 1.0e12, 6, parent))
        edit.setText(text)
        return edit

    @staticmethod
    def _button(text: str, object_name: str, parent: QWidget) -> QPushButton:
        button = QPushButton(text, parent)
        button.setObjectName(object_name)
        button.setMinimumHeight(32)
        return button

    def _show_warning(self, title: str, message: str) -> None:
        QMessageBox.warning(self, title, message)

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QWidget#manualTestPanel { background: #f4f6f8; }
            QGroupBox {
                background: #ffffff;
                border: 1px solid #3f73a8;
                border-radius: 3px;
                margin-top: 9px;
                font-weight: 600;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 8px; padding: 0 3px; }
            QFrame#manualScreenshotFrame { border: 1px solid #9aa7b4; background: #ffffff; }
            QLabel#manualScreenshotImageLabel { color: #66717d; border: 0; }
            QLabel#manualStatusLabel { background: #eaf2fa; padding: 6px; border: 1px solid #aac2d9; }
            QPushButton { min-width: 68px; padding: 4px 7px; }
            """
        )
