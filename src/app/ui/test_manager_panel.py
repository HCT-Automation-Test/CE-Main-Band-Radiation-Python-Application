"""Test Manager 서브 패널."""
from __future__ import annotations
from collections.abc import Iterable
import math
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QDoubleValidator,
    QIntValidator,
    QPalette,
    QResizeEvent,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.core.tc_loader import load_csv, save_csv
from app.models.band_group import find_band_group
from app.models.nr_channel_lookup import (
    resolve_call_channel,
    resolve_target_frequency_mhz,
)
from app.models.test_case import TestCase
from app.models.test_run_settings import TestRunSettings
from app.ui.log_panel import LogPanel
from app.ui.nr_select import NRSelectDialog

_TABLE_HEADERS: tuple[str, ...] = (
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
)

_CONNECTION_ITEMS: tuple[str, ...] = (
    "MT8000a",
    "FSV40",
    "3D Position\nController",
    "CO3000",
    "RF Filter Box",
)

_INFO_FIELDS: tuple[tuple[str, str], ...] = (
    ("Start Freq", "startFreqEdit"),
    ("Stop Freq", "stopFreqEdit"),
    ("Trace Mode", "traceModeEdit"),
    ("Mast", "mastEdit"),
    ("RBW", "rbwEdit"),
    ("VBW", "vbwEdit"),
    ("Sweep Point", "sweepPointEdit"),
    ("Filter", "filterEdit"),
    ("Saturation Time", "saturationTimeEdit"),
    ("Connection Waiting Time", "connectionWaitingTimeEdit"),
    ("Atten Level", "attenLevelEdit"),
    ("Next Peak Search Level", "nextPeakSearchLevelEdit"),
)

_RUN_SETTING_FIELD_DEFAULTS: dict[str, str] = {
    "saturationTimeEdit": "5",
    "connectionWaitingTimeEdit": "5",
    "attenLevelEdit": "0",
    "nextPeakSearchLevelEdit": "0",
}
_RUN_SETTING_FIELD_NAMES = frozenset(_RUN_SETTING_FIELD_DEFAULTS)
_CONNECTION_CANONICAL_KEYS: tuple[str, ...] = (
    "MT8000A",
    "FSV40",
    "3D Controller",
    "CO3000",
    "Switch Box",
)
_CONNECTION_ALIASES: dict[str, str] = {
    "MT8000a": "MT8000A",
    "3D Position Controller": "3D Controller",
    "RF Filter Box": "Switch Box",
}

_TECHNOLOGY_BUTTON_WIDTH = 120
_TECHNOLOGY_BUTTON_MIN_HEIGHT = 38
_ACTION_BODY_SPACING = 12
_LOG_PANEL_WIDTH = 280
_TABLE_TEXT_COLOR = QColor("#111111")
_TABLE_SELECTION_COLOR = QColor("#dcecff")
_TABLE_COLUMN_BASE_WIDTHS: tuple[int, ...] = (
    82,  # Generation
    50,  # Band
    70,  # EUT ANT
    42,  # SCS
    44,  # BW
    86,  # Modulation
    96,  # RB Allocation
    62,  # RB Size
    74,  # RB Offset
    38,  # CH
    70,  # ARFCN
    70,  # CH_No.
    58,  # Case
    78,  # Start Freq
    78,  # Stop Freq
    42,  # Axis
    42,  # Pol
)
_TABLE_COLUMN_STRETCH_WEIGHTS: tuple[int, ...] = (
    2,  # Generation
    0,  # Band
    2,  # EUT ANT
    0,  # SCS
    0,  # BW
    4,  # Modulation
    4,  # RB Allocation
    2,  # RB Size
    2,  # RB Offset
    0,  # CH
    4,  # ARFCN
    4,  # CH_No.
    2,  # Case
    4,  # Start Freq
    4,  # Stop Freq
    0,  # Axis
    0,  # Pol
)
_TABLE_COLUMN_BASE_TOTAL = sum(_TABLE_COLUMN_BASE_WIDTHS)
_TABLE_COLUMN_STRETCH_TOTAL = sum(_TABLE_COLUMN_STRETCH_WEIGHTS)


class TestManagerPanel(QWidget):
    """테스트 케이스 생성, 실행, 로그 출력의 중심 패널."""

    start_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._test_cases: list[TestCase] = []
        self._connection_indicators: dict[str, QFrame] = {}
        self._setup_layout()
        self._connect_signals()
        self._apply_styles()

    @property
    def eut_name(self) -> str:
        """UI에 입력된 EUT 이름을 반환한다."""

        return self._eut_name_edit.text().strip()

    @property
    def excel_template_path(self) -> Path | None:
        """UI에서 선택한 Excel 양식 경로를 반환한다."""

        value = self._excel_template_path_edit.text().strip()
        if not value:
            return None
        return Path(value)

    @property
    def screenshot_root_dir(self) -> Path | None:
        """UI에서 선택한 스크린샷 저장 루트 디렉터리를 반환한다."""

        value = self._screenshot_root_edit.text().strip()
        if not value:
            return None
        return Path(value)

    @property
    def test_cases(self) -> tuple[TestCase, ...]:
        """Test Manager 표에 추가된 TestCase 목록을 반환한다."""

        return tuple(self._test_cases)

    @property
    def saturation_time_sec(self) -> float | None:
        """Saturation Time 입력값을 초 단위 실수로 반환한다."""

        return self._optional_float_field("saturationTimeEdit")

    @property
    def connection_waiting_time_sec(self) -> int | None:
        """Connection Waiting Time 입력값을 초 단위 정수로 반환한다."""

        return self._optional_int_field("connectionWaitingTimeEdit")

    @property
    def atten_level_db(self) -> float | None:
        """Atten Level 입력값을 dB 단위 실수로 반환한다."""

        return self._optional_float_field("attenLevelEdit")

    @property
    def next_peak_search_level_db(self) -> float | None:
        """Next Peak Search Level 입력값을 dB 단위 실수로 반환한다."""

        return self._optional_float_field("nextPeakSearchLevelEdit")

    def set_current_case(self, case: TestCase) -> None:
        """현재 실행/표시 대상 TestCase 정보를 표시 필드에 반영한다."""

        test_range = case.range_definition
        self._set_line_edit_text("currentTestBandEdit", self._format_band_label(case))
        self._set_line_edit_text("currentTestFreqEdit", self._safe_target_frequency(case))
        self._set_line_edit_text("startFreqEdit", self._format_number(test_range.start_freq))
        self._set_line_edit_text("stopFreqEdit", self._format_number(test_range.stop_freq))
        self._set_line_edit_text("rbwEdit", self._format_number(test_range.rbw))
        self._set_line_edit_text("vbwEdit", self._format_number(test_range.vbw))
        self._set_line_edit_text("sweepPointEdit", str(test_range.sweep_point))
        self._set_line_edit_text("filterEdit", test_range.filter_mode.name)
        try:
            speed = find_band_group(case.band.value).turntable_speed
        except ValueError:
            self._set_line_edit_text("settingSpeedEdit", "")
        else:
            self._set_line_edit_text("settingSpeedEdit", str(speed))

    def set_connection_state(self, states: dict[str, bool]) -> None:
        """외부에서 확인한 장비 연결 상태를 indicator에 반영한다."""

        normalized_states = {
            self._canonical_connection_key(key): bool(value)
            for key, value in states.items()
            if self._canonical_connection_key(key) in self._connection_indicators
        }
        for key, indicator in self._connection_indicators.items():
            connected = normalized_states.get(key, False)
            indicator.setProperty("connected", connected)
            indicator.setProperty("disconnected", not connected)
            self._refresh_widget_style(indicator)

    def set_analyzer_info(self, info: object) -> None:
        """Spectrum Analyzer 관련 표시값을 외부 상태로 갱신한다."""

        self._set_info_text(
            info,
            "startFreqEdit",
            "start_freq",
            "start_frequency",
            "Start Frequency",
            "startFreq",
        )
        self._set_info_text(
            info,
            "stopFreqEdit",
            "stop_freq",
            "stop_frequency",
            "Stop Frequency",
            "stopFreq",
        )
        self._set_info_text(info, "traceModeEdit", "trace_mode", "Trace Mode", "traceMode")
        self._set_info_text(info, "mastEdit", "mast", "Mast")
        self._set_info_text(info, "rbwEdit", "rbw", "RBW")
        self._set_info_text(info, "vbwEdit", "vbw", "VBW")
        self._set_info_text(
            info,
            "sweepPointEdit",
            "sweep_point",
            "sweep_points",
            "Sweep Point",
            "sweepPoint",
        )

    def set_switch_box_info(self, info: object) -> None:
        """Switch Box 관련 표시값을 외부 상태로 갱신한다."""

        self._set_info_text(
            info,
            "filterEdit",
            "filter",
            "filter_path",
            "filter_mode",
            "Filter",
            "Filter Path",
        )

    def set_turntable_info(self, info: object) -> None:
        """Turn Table 관련 표시값을 외부 상태로 갱신한다."""

        self._set_info_text(
            info,
            "targetAngleEdit",
            "target_angle",
            "Target Angle",
            "targetAngle",
        )
        self._set_info_text(
            info,
            "currentAngleEdit",
            "current_angle",
            "Current Angle",
            "currentAngle",
        )
        self._set_info_text(
            info,
            "settingSpeedEdit",
            "setting_speed",
            "turntable_speed",
            "Turn Table Speed",
            "Setting Speed",
        )

    def set_polarization_info(self, info: object) -> None:
        """편파 관련 표시값을 외부 상태로 갱신한다."""

        self._set_info_text(info, "polarization3mEdit", "3m", "pol_3m", "polarization_3m")
        self._set_info_text(info, "polarization1mEdit", "1m", "pol_1m", "polarization_1m")
        self._set_info_text(
            info,
            "polarizationBilogEdit",
            "bilog",
            "Bilog",
            "polarization_bilog",
        )

    def build_test_run_settings(self) -> TestRunSettings | None:
        """Start 요청에 필요한 UI 입력값을 실행 설정으로 변환한다."""

        try:
            eut_name = self.eut_name
            if not eut_name:
                raise ValueError("EUT Name을 입력하세요.")
            template_path = self._required_file(
                self.excel_template_path,
                "Excel Template",
            )
            screenshot_root_dir = self._required_directory(
                self.screenshot_root_dir,
                "Screenshot Root",
            )
            saturation_time_sec = self._float_field(
                "saturationTimeEdit",
                "Saturation Time",
            )
            if saturation_time_sec < 0:
                raise ValueError("Saturation Time은 0 이상이어야 합니다.")
            connection_waiting_time_sec = self._int_field(
                "connectionWaitingTimeEdit",
                "Connection Waiting Time",
            )
            if connection_waiting_time_sec <= 0:
                raise ValueError("Connection Waiting Time은 0보다 커야 합니다.")
            atten_level_db = self._float_field("attenLevelEdit", "Atten Level")
            if atten_level_db < 0:
                raise ValueError("Atten Level은 0 이상이어야 합니다.")
            settings = TestRunSettings(
                eut_name=eut_name,
                template_path=template_path,
                screenshot_root_dir=screenshot_root_dir,
                saturation_time_sec=saturation_time_sec,
                connection_waiting_time_sec=connection_waiting_time_sec,
                atten_level_db=atten_level_db,
                next_peak_search_level_db=self._float_field(
                    "nextPeakSearchLevelEdit",
                    "Next Peak Search Level",
                ),
            )
        except ValueError as exc:
            self._show_warning(str(exc))
            return None
        return settings

    def _setup_layout(self) -> None:
        """초안 기준 Test Manager 레이아웃을 구성한다."""

        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(10)

        content_panel = QWidget(self)
        content_panel.setObjectName("testManagerContentPanel")
        content_layout = QVBoxLayout(content_panel)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(8)

        self._test_case_table = self._create_test_case_table()
        content_layout.addWidget(self._test_case_table, 1)

        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(10)
        content_layout.addLayout(bottom_layout)

        bottom_layout.addWidget(self._create_left_panel(), 3)
        bottom_layout.addWidget(self._create_center_panel(), 4)

        self._log_panel = LogPanel(self)
        self._log_panel.setObjectName("testManagerLogPanel")
        self._log_panel.setFixedWidth(_LOG_PANEL_WIDTH)

        root_layout.addWidget(content_panel, 1)
        root_layout.addWidget(self._log_panel)

    def _create_test_case_table(self) -> QTableWidget:
        """확장 실행용 Test Case 표를 만든다."""

        table = QTableWidget(0, len(_TABLE_HEADERS), self)
        table.setObjectName("testCaseTable")
        table.setHorizontalHeaderLabels(_TABLE_HEADERS)
        self._apply_test_case_table_palette(table)
        self._apply_test_case_header_colors(table)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setMinimumHeight(260)
        table.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        horizontal_header = table.horizontalHeader()
        horizontal_header.setStretchLastSection(False)
        horizontal_header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        horizontal_header.setMinimumSectionSize(32)
        horizontal_header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        table.verticalHeader().setVisible(False)
        self._apply_test_case_column_widths(table)
        return table

    def _apply_test_case_column_widths(self, table: QTableWidget | None = None) -> None:
        """남는 표 폭을 긴 정보 컬럼 위주로 가중 배분한다."""

        target_table = table
        if target_table is None:
            if not hasattr(self, "_test_case_table"):
                return
            target_table = self._test_case_table

        viewport_width = target_table.viewport().width()
        if viewport_width <= 0:
            viewport_width = target_table.width() - (target_table.frameWidth() * 2)
        available_width = max(viewport_width, _TABLE_COLUMN_BASE_TOTAL)
        extra_width = max(0, available_width - _TABLE_COLUMN_BASE_TOTAL)
        widths = list(_TABLE_COLUMN_BASE_WIDTHS)

        if extra_width and _TABLE_COLUMN_STRETCH_TOTAL:
            distributed = 0
            for column, weight in enumerate(_TABLE_COLUMN_STRETCH_WEIGHTS):
                extra_for_column = (extra_width * weight) // _TABLE_COLUMN_STRETCH_TOTAL
                widths[column] += extra_for_column
                distributed += extra_for_column

            weighted_columns = [
                column
                for column, weight in sorted(
                    enumerate(_TABLE_COLUMN_STRETCH_WEIGHTS),
                    key=lambda item: (-item[1], item[0]),
                )
                if weight > 0
            ]
            remaining = extra_width - distributed
            for index in range(remaining):
                widths[weighted_columns[index % len(weighted_columns)]] += 1

        for column, width in enumerate(widths):
            target_table.setColumnWidth(column, width)

    def _apply_test_case_table_palette(self, table: QTableWidget) -> None:
        """TestCase 표의 셀 텍스트를 테마와 무관하게 읽히도록 고정한다."""

        palette = table.palette()
        palette.setColor(QPalette.ColorRole.Text, _TABLE_TEXT_COLOR)
        palette.setColor(QPalette.ColorRole.WindowText, _TABLE_TEXT_COLOR)
        palette.setColor(QPalette.ColorRole.HighlightedText, _TABLE_TEXT_COLOR)
        palette.setColor(QPalette.ColorRole.Highlight, _TABLE_SELECTION_COLOR)
        table.setPalette(palette)

    def _apply_test_case_header_colors(self, table: QTableWidget) -> None:
        """TestCase 표 헤더 글자색을 셀과 맞춘다."""

        for column in range(table.columnCount()):
            header_item = table.horizontalHeaderItem(column)
            if header_item is not None:
                header_item.setForeground(QBrush(_TABLE_TEXT_COLOR))

    def _connect_signals(self) -> None:
        """경로 선택 버튼 시그널을 연결한다."""

        self._excel_template_browse_button.clicked.connect(
            self.on_excel_template_browse_clicked,
        )
        self._screenshot_root_browse_button.clicked.connect(
            self.on_screenshot_root_browse_clicked,
        )
        self._nr_button.clicked.connect(self.on_nr_button_clicked)
        self._delete_button.clicked.connect(self.on_delete_button_clicked)
        self._clear_button.clicked.connect(self.on_clear_button_clicked)
        self._load_item_button.clicked.connect(self.on_load_item_button_clicked)
        self._save_item_button.clicked.connect(self.on_save_item_button_clicked)
        self._start_button.clicked.connect(self.start_requested.emit)

    def _create_left_panel(self) -> QWidget:
        """EUT 입력과 좌측 하단 제어 영역을 만든다."""

        panel = QWidget(self)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        layout.addWidget(self._create_summary_inputs())

        controls_layout = QHBoxLayout()
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(8)
        controls_layout.addWidget(self._create_connection_group(), 1)
        controls_layout.addWidget(self._create_turn_table_group(), 1)
        controls_layout.addWidget(self._create_polarization_group(), 1)
        layout.addLayout(controls_layout)

        current_factor_layout = QHBoxLayout()
        current_factor_layout.setContentsMargins(0, 0, 0, 0)
        current_factor_layout.setSpacing(8)
        current_factor_label = QLabel("Current Factor", panel)
        self._current_factor_edit = QLineEdit(panel)
        self._current_factor_edit.setObjectName("currentFactorEdit")
        self._current_factor_edit.setReadOnly(True)
        current_factor_layout.addWidget(current_factor_label)
        current_factor_layout.addWidget(self._current_factor_edit, 1)
        layout.addLayout(current_factor_layout)

        layout.addWidget(self._create_path_inputs())
        return panel

    def _create_summary_inputs(self) -> QWidget:
        """표 바로 아래 요약 입력 행을 만든다."""

        panel = QWidget(self)
        layout = QGridLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(3)

        inputs = (
            ("EUT Name", "eutNameEdit"),
            ("Current Test Band", "currentTestBandEdit"),
            ("Current Test Freq", "currentTestFreqEdit"),
        )
        for column, (label_text, object_name) in enumerate(inputs):
            label = QLabel(label_text, panel)
            if object_name != "eutNameEdit":
                label.setProperty("summaryLabel", True)
            edit = QLineEdit(panel)
            edit.setObjectName(object_name)
            if object_name == "eutNameEdit":
                self._eut_name_edit = edit
            else:
                edit.setReadOnly(True)
            layout.addWidget(label, 0, column)
            layout.addWidget(edit, 1, column)
            layout.setColumnStretch(column, 1)

        return panel

    def _create_path_inputs(self) -> QWidget:
        """리포트 양식과 스크린샷 루트 입력 행을 만든다."""

        panel = QWidget(self)
        layout = QGridLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(6)
        layout.setVerticalSpacing(4)

        self._excel_template_path_edit = QLineEdit(panel)
        self._excel_template_path_edit.setObjectName("excelTemplatePathEdit")
        self._excel_template_path_edit.setReadOnly(True)
        self._excel_template_browse_button = QPushButton("찾기", panel)
        self._excel_template_browse_button.setObjectName("excelTemplateBrowseButton")

        self._screenshot_root_edit = QLineEdit(panel)
        self._screenshot_root_edit.setObjectName("screenshotRootEdit")
        self._screenshot_root_edit.setReadOnly(True)
        self._screenshot_root_browse_button = QPushButton("찾기", panel)
        self._screenshot_root_browse_button.setObjectName("screenshotRootBrowseButton")

        layout.addWidget(QLabel("Excel Template", panel), 0, 0)
        layout.addWidget(self._excel_template_path_edit, 0, 1)
        layout.addWidget(self._excel_template_browse_button, 0, 2)
        layout.addWidget(QLabel("Screenshot Root", panel), 1, 0)
        layout.addWidget(self._screenshot_root_edit, 1, 1)
        layout.addWidget(self._screenshot_root_browse_button, 1, 2)
        layout.setColumnStretch(1, 1)
        return panel

    def _create_connection_group(self) -> QGroupBox:
        """장비 연결 상태 표시 영역을 만든다."""

        group = QGroupBox("Connection", self)
        group.setObjectName("connectionGroupBox")
        layout = QGridLayout(group)
        layout.setContentsMargins(10, 16, 10, 8)
        layout.setHorizontalSpacing(8)
        layout.setVerticalSpacing(7)

        for row, label_text in enumerate(_CONNECTION_ITEMS):
            label = QLabel(label_text, group)
            status = QFrame(group)
            status.setObjectName(f"connectionStatus{row + 1}")
            status.setProperty("statusIndicator", True)
            status.setProperty("connected", False)
            status.setProperty("disconnected", True)
            status.setFixedSize(18, 18)
            self._connection_indicators[_CONNECTION_CANONICAL_KEYS[row]] = status
            layout.addWidget(label, row, 0)
            layout.addWidget(status, row, 1, alignment=Qt.AlignmentFlag.AlignRight)

        layout.setColumnStretch(0, 1)
        return group

    def _create_turn_table_group(self) -> QGroupBox:
        """턴테이블 입력 영역을 만든다."""

        group = QGroupBox("Turn Table", self)
        group.setObjectName("turnTableGroupBox")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(10, 16, 10, 8)
        layout.setSpacing(5)

        for label_text, object_name in (
            ("Target Angle", "targetAngleEdit"),
            ("Current Angle", "currentAngleEdit"),
            ("Setting Speed", "settingSpeedEdit"),
        ):
            layout.addWidget(self._create_labeled_edit(label_text, object_name, group))

        return group

    def _create_polarization_group(self) -> QGroupBox:
        """편파별 측정 입력 영역을 만든다."""

        group = QGroupBox("Polarization", self)
        group.setObjectName("polarizationGroupBox")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(10, 16, 10, 8)
        layout.setSpacing(5)

        for label_text, object_name in (
            ("3m", "polarization3mEdit"),
            ("1m", "polarization1mEdit"),
            ("Bilog", "polarizationBilogEdit"),
        ):
            layout.addWidget(self._create_labeled_edit(label_text, object_name, group))

        return group

    def _create_center_panel(self) -> QWidget:
        """실행 버튼과 Info 영역을 만든다."""

        panel = QWidget(self)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(_ACTION_BODY_SPACING)

        action_layout = QHBoxLayout()
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(6)
        for text, object_name in (
            ("시작", "startButton"),
            ("일시정지", "pauseButton"),
            ("삭제", "deleteButton"),
            ("초기화", "clearButton"),
            ("불러오기", "loadItemButton"),
            ("저장", "saveItemButton"),
        ):
            button = QPushButton(text, panel)
            button.setObjectName(object_name)
            if object_name == "startButton":
                self._start_button = button
            elif object_name == "deleteButton":
                self._delete_button = button
            elif object_name == "clearButton":
                self._clear_button = button
            elif object_name == "loadItemButton":
                self._load_item_button = button
            elif object_name == "saveItemButton":
                self._save_item_button = button
            action_layout.addWidget(button)
        layout.addLayout(action_layout)

        body_layout = QHBoxLayout()
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(10)
        body_layout.addWidget(self._create_info_group(), 1)
        body_layout.addWidget(self._create_technology_panel())
        layout.addLayout(body_layout, 1)
        return panel

    def _create_info_group(self) -> QGroupBox:
        """선택 Test Case의 측정 조건 표시 영역을 만든다."""

        group = QGroupBox("Info", self)
        group.setObjectName("infoGroupBox")
        layout = QGridLayout(group)
        layout.setContentsMargins(12, 18, 12, 10)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(6)

        for index, (label_text, object_name) in enumerate(_INFO_FIELDS):
            row = index % 4
            column = index // 4
            layout.addWidget(
                self._create_labeled_edit(label_text, object_name, group),
                row,
                column,
            )
            layout.setColumnStretch(column, 1)

        return group

    def _create_technology_panel(self) -> QWidget:
        """우측 RAT 선택 버튼 영역을 만든다."""

        panel = QWidget(self)
        panel.setObjectName("technologyButtonPanel")
        panel.setFixedWidth(_TECHNOLOGY_BUTTON_WIDTH)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        for text, object_name in (
            ("NR", "nrButton"),
            ("LTE", "lteButton"),
            ("WCDMA", "wcdmaButton"),
            ("GSM", "gsmButton"),
            ("Case 확인(1~6)", "caseConfirmButton"),
        ):
            button = QPushButton(text, panel)
            button.setObjectName(object_name)
            button.setFixedWidth(_TECHNOLOGY_BUTTON_WIDTH)
            button.setMinimumHeight(_TECHNOLOGY_BUTTON_MIN_HEIGHT)
            button.setSizePolicy(
                QSizePolicy.Policy.Fixed,
                QSizePolicy.Policy.Expanding,
            )
            if object_name == "nrButton":
                self._nr_button = button
            layout.addWidget(button)

        return panel

    def _create_labeled_edit(
        self,
        label_text: str,
        object_name: str,
        parent: QWidget,
    ) -> QWidget:
        """라벨과 입력칸을 세로로 묶은 필드를 만든다."""

        field = QWidget(parent)
        layout = QVBoxLayout(field)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        label = QLabel(label_text, field)
        edit = QLineEdit(field)
        edit.setObjectName(object_name)
        edit.setReadOnly(object_name not in _RUN_SETTING_FIELD_NAMES)
        self._apply_run_setting_validator(edit, object_name)
        default_value = _RUN_SETTING_FIELD_DEFAULTS.get(object_name)
        if default_value is not None:
            edit.setText(default_value)
        layout.addWidget(label)
        layout.addWidget(edit)
        return field

    def _apply_styles(self) -> None:
        """Test Manager 전용 기본 스타일을 적용한다."""

        self.setStyleSheet(
            """
            QTableWidget#testCaseTable {
                border: 1px solid #3f73a8;
                gridline-color: #d8e2ee;
                background: #ffffff;
                alternate-background-color: #f3f7fc;
            }

            QTableWidget#testCaseTable QHeaderView::section {
                background: #edf3fa;
                border: 0;
                border-right: 1px solid #ffffff;
                border-bottom: 1px solid #d2ddea;
                padding: 4px 6px;
            }

            QGroupBox {
                border: 1px solid #3f73a8;
                margin-top: 10px;
            }

            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 2px;
                font-size: 18px;
            }

            QLineEdit {
                border: 1px solid #3f73a8;
                min-height: 20px;
                padding: 1px 4px;
            }

            QPushButton {
                border: 1px solid #3f73a8;
                background: #f8f8f8;
                color: #111111;
                font-size: 14px;
                min-height: 28px;
                padding: 4px 10px;
            }

            QPushButton:hover {
                background: #f1f7ff;
            }

            QFrame[statusIndicator="true"] {
                border: 1px solid #3f73a8;
                border-radius: 9px;
            }

            QFrame[statusIndicator="true"][connected="true"] {
                background: #48a868;
            }

            QFrame[statusIndicator="true"][disconnected="true"] {
                background: #b8c2cc;
            }

            QLabel[summaryLabel="true"] {
                font-weight: 600;
            }
            """
        )

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        """패널 폭 변경 시 TestCase 표 컬럼 폭을 다시 배분한다."""

        super().resizeEvent(event)
        self._apply_test_case_column_widths()

    def on_excel_template_browse_clicked(self) -> None:
        """Excel 양식 파일을 선택해 입력칸에 반영한다."""

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Excel 양식 선택",
            self._excel_template_path_edit.text().strip(),
            "Excel Files (*.xlsx *.xlsm);;All Files (*)",
        )
        if file_path:
            self._excel_template_path_edit.setText(str(Path(file_path)))

    def on_screenshot_root_browse_clicked(self) -> None:
        """스크린샷 저장 루트 디렉터리를 선택해 입력칸에 반영한다."""

        directory = QFileDialog.getExistingDirectory(
            self,
            "스크린샷 저장 경로 선택",
            self._screenshot_root_edit.text().strip(),
        )
        if directory:
            self._screenshot_root_edit.setText(str(Path(directory)))

    def on_nr_button_clicked(self) -> None:
        """NR 버튼 클릭 시 TestCase 선택 팝업을 연다."""

        dialog = NRSelectDialog(self)
        dialog.test_cases_created.connect(self.add_test_cases)
        dialog.exec()

    def on_delete_button_clicked(self) -> None:
        """선택한 TestCase 하나를 삭제한다."""

        row = self._test_case_table.currentRow()
        if row < 0 or row >= len(self._test_cases):
            return

        self._test_cases.pop(row)
        self._test_case_table.removeRow(row)

    def on_clear_button_clicked(self) -> None:
        """모든 TestCase를 삭제한다."""

        if not self._test_cases and self._test_case_table.rowCount() == 0:
            return

        self._test_cases.clear()
        self._test_case_table.setRowCount(0)

    def on_load_item_button_clicked(self) -> None:
        """CSV 파일에서 TestCase를 읽어 기존 목록 뒤에 추가한다."""

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Test Case CSV 불러오기",
            "",
            "CSV Files (*.csv);;All Files (*)",
        )
        if not file_path:
            return

        path = Path(file_path)
        if path.suffix.lower() != ".csv":
            self._show_warning("CSV 파일만 불러올 수 있습니다.")
            return

        try:
            cases = load_csv(path)
        except (OSError, ValueError) as exc:
            self._show_warning(f"CSV 불러오기에 실패했습니다.\n{exc}")
            return

        self.add_test_cases(cases)

    def on_save_item_button_clicked(self) -> None:
        """현재 TestCase 목록을 CSV 파일로 저장한다."""

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Test Case CSV 저장",
            "",
            "CSV Files (*.csv);;All Files (*)",
        )
        if not file_path:
            return

        path = Path(file_path)
        if not path.suffix:
            path = path.with_suffix(".csv")

        try:
            save_csv(path, self._test_cases)
        except OSError as exc:
            self._show_warning(f"CSV 저장에 실패했습니다.\n{exc}")
            return

    def _required_file(self, value: Path | None, label: str) -> Path:
        if value is None:
            raise ValueError(f"{label}을 선택하세요.")
        if not value.is_file():
            raise ValueError(f"{label} 파일이 존재하지 않습니다.")
        return value

    def _required_directory(self, value: Path | None, label: str) -> Path:
        if value is None:
            raise ValueError(f"{label}를 선택하세요.")
        if not value.is_dir():
            raise ValueError(f"{label} 폴더가 존재하지 않습니다.")
        return value

    def _float_field(self, object_name: str, label: str) -> float:
        text = self._field_text(object_name)
        if not text:
            raise ValueError(f"{label}을 입력하세요.")
        try:
            return float(text)
        except ValueError as exc:
            raise ValueError(f"{label}은 숫자로 입력하세요.") from exc

    def _int_field(self, object_name: str, label: str) -> int:
        text = self._field_text(object_name)
        if not text:
            raise ValueError(f"{label}을 입력하세요.")
        try:
            return int(text)
        except ValueError as exc:
            raise ValueError(f"{label}은 정수로 입력하세요.") from exc

    def _optional_float_field(self, object_name: str) -> float | None:
        try:
            text = self._field_text(object_name)
        except ValueError:
            return None
        if not text:
            return None
        try:
            value = float(text)
        except ValueError:
            return None
        if not math.isfinite(value):
            return None
        return value

    def _optional_int_field(self, object_name: str) -> int | None:
        try:
            text = self._field_text(object_name)
        except ValueError:
            return None
        if not text:
            return None
        try:
            return int(text)
        except ValueError:
            return None

    def _field_text(self, object_name: str) -> str:
        edit = self.findChild(QLineEdit, object_name)
        if edit is None:
            raise ValueError(f"{object_name} 입력 필드를 찾을 수 없습니다.")
        return edit.text().strip()

    def _set_line_edit_text(self, object_name: str, value: Any) -> None:
        edit = self.findChild(QLineEdit, object_name)
        if edit is None:
            return
        edit.setText(self._display_text(value))

    def _set_info_text(self, info: object, object_name: str, *keys: str) -> None:
        self._set_line_edit_text(object_name, self._info_value(info, *keys))

    def _info_value(self, info: object, *keys: str) -> Any:
        if isinstance(info, dict):
            return self._value_from_mapping(info, *keys)

        for key in keys:
            if key.isidentifier() and hasattr(info, key):
                return getattr(info, key)

        attributes = getattr(info, "__dict__", None)
        if isinstance(attributes, dict):
            return self._value_from_mapping(attributes, *keys)
        return None

    def _value_from_mapping(self, values: dict[Any, Any], *keys: str) -> Any:
        for key in keys:
            if key in values:
                return values[key]

        normalized_values = {
            self._normalize_key(str(key)): value for key, value in values.items()
        }
        for key in keys:
            normalized_key = self._normalize_key(key)
            if normalized_key in normalized_values:
                return normalized_values[normalized_key]
        return None

    def _display_text(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, float):
            if not math.isfinite(value):
                return ""
            return self._format_number(value)
        return str(value)

    def _canonical_connection_key(self, key: str) -> str:
        key_text = str(key).replace("\n", " ").strip()
        if key_text in _CONNECTION_CANONICAL_KEYS:
            return key_text
        if key_text in _CONNECTION_ALIASES:
            return _CONNECTION_ALIASES[key_text]

        normalized_key = self._normalize_key(key_text)
        for canonical in _CONNECTION_CANONICAL_KEYS:
            if normalized_key == self._normalize_key(canonical):
                return canonical
        for alias, canonical in _CONNECTION_ALIASES.items():
            if normalized_key == self._normalize_key(alias):
                return canonical
        return key_text

    def _normalize_key(self, key: str) -> str:
        return "".join(character for character in key.lower() if character.isalnum())

    def _refresh_widget_style(self, widget: QWidget) -> None:
        style = widget.style()
        style.unpolish(widget)
        style.polish(widget)
        widget.update()

    def _apply_run_setting_validator(self, edit: QLineEdit, object_name: str) -> None:
        if object_name in {
            "saturationTimeEdit",
            "attenLevelEdit",
        }:
            edit.setValidator(QDoubleValidator(0.0, math.inf, 6, edit))
        elif object_name == "connectionWaitingTimeEdit":
            edit.setValidator(QIntValidator(1, 2147483647, edit))
        elif object_name == "nextPeakSearchLevelEdit":
            edit.setValidator(QDoubleValidator(-math.inf, math.inf, 6, edit))

    def _show_warning(self, message: str) -> None:
        """Test Manager 경고 메시지를 표시한다."""

        QMessageBox.warning(self, "Test Manager", message)

    def add_test_cases(self, cases: Iterable[TestCase]) -> None:
        """생성된 TestCase를 내부 목록과 표에 추가한다."""

        for case in cases:
            self._test_cases.append(case)
            self._append_test_case_row(case)

    def _append_test_case_row(self, case: TestCase) -> None:
        """TestCase 하나를 실행 표에 표시한다."""

        row = self._test_case_table.rowCount()
        self._test_case_table.insertRow(row)
        for column, value in enumerate(self._row_values_for_case(case)):
            item = QTableWidgetItem(value)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setForeground(QBrush(_TABLE_TEXT_COLOR))
            self._test_case_table.setItem(row, column, item)

    def _row_values_for_case(self, case: TestCase) -> tuple[str, ...]:
        """확장 TestCase 표 컬럼 순서에 맞춰 표시값을 만든다."""

        test_range = case.range_definition
        return (
            "NR",
            self._format_band_label(case),
            case.dut_ant_position.value,
            str(case.scs_khz),
            self._format_number(case.bandwidth),
            case.modulation.value,
            case.rb_allocation.value,
            str(case.rb_size),
            str(case.rb_offset),
            case.test_channel.value,
            self._safe_call_channel(case),
            # TODO(spec): CH_No. 컬럼 의미가 확정되면 표시값을 조정한다.
            self._safe_target_frequency(case),
            case.test_type.value,
            self._format_number(test_range.start_freq),
            self._format_number(test_range.stop_freq),
            case.dut_axis.value,
            case.antenna_pol.value,
        )

    def _format_band_label(self, case: TestCase) -> str:
        return f"B{case.band.value[1:]}"

    def _format_number(self, value: float) -> str:
        return format(float(value), ".15g")

    def _safe_call_channel(self, case: TestCase) -> str:
        try:
            return str(resolve_call_channel(case.band, case.bandwidth, case.test_channel))
        except ValueError:
            return ""

    def _safe_target_frequency(self, case: TestCase) -> str:
        try:
            return self._format_number(
                resolve_target_frequency_mhz(
                    case.band,
                    case.bandwidth,
                    case.test_channel,
                ),
            )
        except ValueError:
            return ""
