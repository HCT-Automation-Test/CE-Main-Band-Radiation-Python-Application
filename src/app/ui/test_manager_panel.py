"""Test Manager 서브 패널."""
from __future__ import annotations
from collections.abc import Iterable
import math
from pathlib import Path
from typing import Any, Literal

from PySide6.QtCore import QEvent, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtGui import (
    QBrush,
    QColor,
    QDoubleValidator,
    QIntValidator,
    QPalette,
    QPixmap,
    QResizeEvent,
    QShowEvent,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.config.file_dialog_directory_settings import runtime_base_directory
from app.core.tc_loader import load_csv, save_csv
from app.models.enums import Generation, LTEBand
from app.models.test_case import TestCase
from app.models.test_range import TestRange
from app.models.test_run_settings import (
    TestRunSettings,
    default_screenshot_root_dir,
)
from app.ui.log_panel import LogPanel
from app.ui.lte_select import LTECaseParameters, LTEGroupSettings, LTESelectDialog
from app.ui.nr_select import NRSelectDialog, NRSelectState

_TABLE_HEADERS: tuple[str, ...] = (
    "Index",
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

_MAX_NEXT_PEAK_SEARCH_LEVEL_DB = 80.0
_MAX_CUSTOM_TURNTABLE_SPEED = 10
_CSV_DIRECTORY_NAME = "CSV"

_RUN_SETTING_FIELD_DEFAULTS: dict[str, str] = {
    "saturationTimeEdit": "5",
    "connectionWaitingTimeEdit": "5",
    "attenLevelEdit": "0",
    "nextPeakSearchLevelEdit": "6",
    "customTurnTableSpeedEdit": "5",
}
_RUN_SETTING_FIELD_NAMES = frozenset(_RUN_SETTING_FIELD_DEFAULTS)
_RUN_SETTING_BUTTON_NAMES = (
    "singleStartButton",
    "startButton",
    "deleteButton",
    "clearButton",
    "loadItemButton",
    "saveItemButton",
    "nrSaButton",
    "nrNsaButton",
    "lteButton",
    "wcdmaButton",
    "gsmButton",
)
_CONNECTION_CANONICAL_KEYS: tuple[str, ...] = (
    "MT8000A",
    "FSV40",
    "3D Controller",
    "CO3000",
    "Switch Box",
)
_CONNECTION_ALIASES: dict[str, str] = {
    "MT8000a": "MT8000A",
    "MT8000": "MT8000A",
    "3D Position Controller": "3D Controller",
    "3D Position": "3D Controller",
    "Controller 3D": "3D Controller",
    "RF Filter Box": "Switch Box",
    "Filter Box": "Switch Box",
    "SwitchBox": "Switch Box",
}
_CONNECTION_STATUS_NOT_CONNECTED = "not_connected"
_CONNECTION_STATUS_CONNECTING = "connecting"
_CONNECTION_STATUS_CONNECTED = "connected"
_CONNECTION_STATUS_FAILED = "failed"
_SCREENSHOT_PREVIEW_SOURCE_WIDTH = 1600
_SCREENSHOT_PREVIEW_SOURCE_HEIGHT = 1200
_SCREENSHOT_PREVIEW_PADDED_HEIGHT = 1244
_SCREENSHOT_PREVIEW_ASPECT_RATIO = (
    _SCREENSHOT_PREVIEW_SOURCE_WIDTH / _SCREENSHOT_PREVIEW_SOURCE_HEIGHT
)
_SCREENSHOT_PREVIEW_PADDED_ASPECT_RATIO = (
    _SCREENSHOT_PREVIEW_SOURCE_WIDTH / _SCREENSHOT_PREVIEW_PADDED_HEIGHT
)

_TECHNOLOGY_BUTTON_WIDTH = 120
_TECHNOLOGY_BUTTON_MIN_HEIGHT = 38
_ACTION_BODY_SPACING = 12
_LOG_PANEL_WIDTH = 280
_TABLE_TEXT_COLOR = QColor("#111111")
_TABLE_SELECTION_COLOR = QColor("#dcecff")
_TEST_CASE_RUNNING_BACKGROUND = QColor("#fff3bf")
_TEST_CASE_COMPLETED_BACKGROUND = QColor("#ced4da")
_TestCaseProgress = Literal["pending", "running", "completed"]
_TABLE_COLUMN_BASE_WIDTHS: tuple[int, ...] = (
    44,  # Index
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
_TABLE_COLUMN_BASE_TOTAL = sum(_TABLE_COLUMN_BASE_WIDTHS)
def _default_csv_directory() -> Path:
    """배포 EXE 또는 개발 작업 디렉터리 기준 CSV 폴더를 반환한다."""

    return runtime_base_directory() / _CSV_DIRECTORY_NAME


class TestManagerPanel(QWidget):
    """테스트 케이스 생성, 실행, 로그 출력의 중심 패널."""

    start_requested = Signal()
    single_start_requested = Signal()
    stop_requested = Signal()
    get_tdf_list_requested = Signal()
    tdf_all_off_requested = Signal()
    set_tdf_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._active_tdf_file_name: str | None = None
        self._test_cases: list[TestCase] = []
        self._test_case_progress: list[_TestCaseProgress] = []
        self._completed_test_case_indexes: set[int] = set()
        self._connection_indicators: dict[str, QFrame] = {}
        self._nr_states: dict[Generation, NRSelectState | None] = {
            Generation.NR_SA: None,
            Generation.NR_NSA: None,
        }
        self._lte_parameters_by_band: dict[LTEBand, LTECaseParameters] | None = None
        self._lte_group_settings: dict[str, LTEGroupSettings] | None = None
        self._setup_layout()
        self._connect_signals()
        self._apply_styles()

    @property
    def eut_name(self) -> str:
        """UI에 입력된 EUT 이름을 반환한다."""

        return self._eut_name_edit.text()

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

    @property
    def custom_turntable_speed(self) -> int | None:
        """Custom Turn Table Speed 입력값을 정수로 반환한다."""

        return self._optional_int_field("customTurnTableSpeedEdit")

    @property
    def active_tdf_file_name(self) -> str | None:
        """마지막으로 활성화에 성공한 TDF 파일명을 반환한다."""

        return self._active_tdf_file_name

    @property
    def selected_tdf_file_name(self) -> str | None:
        """TDF List Box에서 선택된 파일명을 반환한다."""

        selected_items = self._tdf_list_widget.selectedItems()
        if not selected_items:
            return None
        return self._tdf_item_file_name(selected_items[0])

    def set_current_case(self, case: TestCase) -> None:
        """현재 실행/표시 대상 TestCase 정보를 표시 필드에 반영한다."""

        test_range = case.range_definition
        current_index = self._find_test_case_index(case)
        if current_index is not None:
            self._set_line_edit_text("indexEdit", current_index + 1)
        self._set_line_edit_text("currentTestBandEdit", self._format_band_label(case))
        self._set_line_edit_text("currentTestFreqEdit", self._format_test_range_label(test_range))
        self._set_line_edit_text("currentFactorEdit", self._format_current_factor(case))

    def set_connection_state(self, states: dict[str, bool]) -> None:
        """외부에서 확인한 장비 연결 상태를 indicator에 반영한다."""

        normalized_states = {
            self._canonical_connection_key(key): bool(value)
            for key, value in states.items()
            if self._canonical_connection_key(key) in self._connection_indicators
        }
        for key, indicator in self._connection_indicators.items():
            if key not in normalized_states:
                self._set_connection_indicator_status(
                    indicator,
                    (
                        _CONNECTION_STATUS_FAILED
                        if normalized_states
                        else _CONNECTION_STATUS_NOT_CONNECTED
                    ),
                )
                continue

            self._set_connection_indicator_status(
                indicator,
                (
                    _CONNECTION_STATUS_CONNECTED
                    if normalized_states[key]
                    else _CONNECTION_STATUS_FAILED
                ),
            )

    def set_connection_connecting(self) -> None:
        """Instrument Check 연결 진행 상태를 Connection indicator에 표시한다."""

        for indicator in self._connection_indicators.values():
            self._set_connection_indicator_status(
                indicator,
                _CONNECTION_STATUS_CONNECTING,
            )

    def set_connection_failed(self) -> None:
        """장비별 결과가 없는 연결 실패를 Connection indicator에 표시한다."""

        for indicator in self._connection_indicators.values():
            if indicator.property("connectionStatus") == _CONNECTION_STATUS_CONNECTING:
                self._set_connection_indicator_status(
                    indicator,
                    _CONNECTION_STATUS_FAILED,
                )

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

        self._set_info_text(info, "mastEdit", "mast", "Mast")
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

    def update_turntable_info(self, info: object) -> None:
        """Turn Table 부분 변경 이벤트에 포함된 표시값만 갱신한다."""

        self._update_info_text_if_present(
            info,
            "targetAngleEdit",
            "target_angle",
            "Target Angle",
            "targetAngle",
        )
        self._update_info_text_if_present(
            info,
            "currentAngleEdit",
            "current_angle",
            "Current Angle",
            "currentAngle",
        )
        self._update_info_text_if_present(
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
        self._set_info_text(
            info,
            "polarizationBilogEdit",
            "bilog",
            "Bilog",
            "polarization_bilog",
        )
        self._set_info_text(
            info,
            "polarization1mEdit",
            "1m",
            "pol_1m",
            "polarization_1m",
        )

    def update_polarization_info(self, info: object) -> None:
        """편파 부분 변경 이벤트에 포함된 표시값만 갱신한다."""

        self._update_info_text_if_present(
            info,
            "polarization3mEdit",
            "3m",
            "pol_3m",
            "polarization_3m",
        )
        self._update_info_text_if_present(
            info,
            "polarizationBilogEdit",
            "bilog",
            "Bilog",
            "polarization_bilog",
        )
        self._update_info_text_if_present(
            info,
            "polarization1mEdit",
            "1m",
            "pol_1m",
            "polarization_1m",
        )

    def set_run_settings_locked(self, locked: bool) -> None:
        """시험 실행 중 Start 설정 입력값을 고정한다."""

        self._eut_name_edit.setEnabled(not locked)
        self._index_edit.setEnabled(not locked)
        for object_name in _RUN_SETTING_FIELD_NAMES:
            edit = self.findChild(QLineEdit, object_name)
            if edit is not None:
                edit.setEnabled(not locked)
        self._custom_option_check_box.setEnabled(not locked)
        self._marker_check_box.setEnabled(not locked)
        for object_name in _RUN_SETTING_BUTTON_NAMES:
            button = self.findChild(QPushButton, object_name)
            if button is not None:
                button.setEnabled(not locked)

    def set_stop_enabled(self, enabled: bool) -> None:
        """현재 TC 중단 버튼 활성화 상태를 갱신한다."""

        self._stop_button.setEnabled(enabled)

    def reset_test_case_progress(self) -> None:
        """TestCase 표의 진행 상태 표시를 초기화한다."""

        self._completed_test_case_indexes.clear()
        self._test_case_progress = ["pending"] * len(self._test_cases)
        self._refresh_test_case_progress_marks()

    def clear_running_test_case(self) -> None:
        self._restore_running_test_case_progress()
        self._refresh_test_case_progress_marks()

    def mark_current_test_case(self, case: TestCase) -> None:
        """현재 진행 중인 TestCase 행을 표시한다."""

        current_index = self._find_test_case_index(case)
        self._restore_running_test_case_progress()
        if current_index is not None:
            self._test_case_progress[current_index] = "running"
            first_item = self._test_case_table.item(current_index, 0)
            if first_item is not None:
                self._test_case_table.selectRow(current_index)
                self._test_case_table.scrollToItem(
                    first_item,
                    QAbstractItemView.ScrollHint.PositionAtCenter,
                )
        self._refresh_test_case_progress_marks()

    def _restore_running_test_case_progress(self) -> None:
        for row, status in enumerate(self._test_case_progress):
            if status == "running":
                self._test_case_progress[row] = (
                    "completed"
                    if row in self._completed_test_case_indexes
                    else "pending"
                )

    def mark_test_case_completed(self, index: int) -> None:
        """완료 이벤트를 받은 TestCase 행을 완료 표시로 바꾼다."""

        if 0 <= index < len(self._test_case_progress):
            self._completed_test_case_indexes.add(index)
            self._test_case_progress[index] = "completed"
        self._refresh_test_case_progress_marks()

    def complete_current_test_case(self) -> None:
        """현재 진행 중인 TestCase 행을 완료 표시로 바꾼다."""

        for row, status in enumerate(self._test_case_progress):
            if status == "running":
                self._completed_test_case_indexes.add(row)
                self._test_case_progress[row] = "completed"
        self._refresh_test_case_progress_marks()

    def set_tdf_file_list(self, file_names: Iterable[str]) -> None:
        """TDF 파일 목록을 List Box에 반영한다."""

        selected_file_name = self.selected_tdf_file_name
        file_name_list = [str(file_name) for file_name in file_names]
        if self._active_tdf_file_name not in file_name_list:
            self._active_tdf_file_name = None

        self._tdf_list_widget.clear()
        for file_name in file_name_list:
            item = QListWidgetItem(file_name)
            item.setData(Qt.ItemDataRole.UserRole, file_name)
            self._tdf_list_widget.addItem(item)

        self._refresh_tdf_active_marks()
        if selected_file_name:
            matching_items = self._tdf_list_widget.findItems(
                selected_file_name,
                Qt.MatchFlag.MatchExactly,
            )
            if matching_items:
                self._tdf_list_widget.setCurrentItem(matching_items[0])

    def set_active_tdf_file_name(self, file_name: str) -> None:
        """마지막으로 활성화에 성공한 TDF 파일을 목록에 표시한다."""

        self._active_tdf_file_name = file_name
        self._refresh_tdf_active_marks()

    def clear_active_tdf_file_name(self) -> None:
        """TDF 활성 표시를 모두 해제한다."""

        self._active_tdf_file_name = None
        self._refresh_tdf_active_marks()

    def set_tdf_operation_locked(self, locked: bool) -> None:
        """TDF 작업 중 TDF 조작 위젯을 잠근다."""

        enabled = not locked
        self._tdf_list_widget.setEnabled(enabled)
        self._get_tdf_list_button.setEnabled(enabled)
        self._tdf_all_off_button.setEnabled(enabled)
        self._set_tdf_button.setEnabled(enabled)

    def build_start_index(self, case_count: int) -> int | None:
        """Index 입력값을 0-based TestCase index로 변환한다."""

        text = self._index_edit.text().strip()
        if not text:
            return 0
        try:
            index = int(text)
        except ValueError:
            self._show_warning("Index는 정수로 입력하세요.")
            return None
        if index < 1:
            self._show_warning("Index는 1 이상이어야 합니다.")
            return None
        if index > case_count:
            self._show_warning("Index가 Test Case 개수를 초과했습니다.")
            return None
        return index - 1

    def build_test_run_settings(self) -> TestRunSettings | None:
        """Start 요청에 필요한 UI 입력값을 실행 설정으로 변환한다."""

        try:
            eut_name = self.eut_name
            if not eut_name:
                raise ValueError("EUT Name을 입력하세요.")
            screenshot_root_dir = default_screenshot_root_dir()
            custom_option_enabled = self._custom_option_check_box.isChecked()
            manual_marker_enabled = False
            if custom_option_enabled:
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
                custom_turntable_speed = self._int_field(
                    "customTurnTableSpeedEdit",
                    "Turn Table Speed",
                )
                if not 1 <= custom_turntable_speed <= _MAX_CUSTOM_TURNTABLE_SPEED:
                    raise ValueError(
                        "Turn Table Speed는 1에서 "
                        f"{_MAX_CUSTOM_TURNTABLE_SPEED}사이의 정수여야 합니다."
                    )
                next_peak_search_level_db = self._float_field(
                    "nextPeakSearchLevelEdit",
                    "Next Peak Search Level",
                )
                if (
                    next_peak_search_level_db <= 0
                    or next_peak_search_level_db > _MAX_NEXT_PEAK_SEARCH_LEVEL_DB
                ):
                    raise ValueError(
                        "Next Peak Search Level은 0보다 크고 "
                        f"{_MAX_NEXT_PEAK_SEARCH_LEVEL_DB:g}이하의 실수여야 합니다."
                    )
                manual_marker_enabled = self._marker_check_box.isChecked()
            else:
                saturation_time_sec = 5
                connection_waiting_time_sec = 5
                atten_level_db = 0
                next_peak_search_level_db = 6
                custom_turntable_speed = None

            settings = TestRunSettings(
                eut_name=eut_name,
                screenshot_root_dir=screenshot_root_dir,
                saturation_time_sec=saturation_time_sec,
                connection_waiting_time_sec=connection_waiting_time_sec,
                atten_level_db=atten_level_db,
                next_peak_search_level_db=next_peak_search_level_db,
                custom_turntable_speed=custom_turntable_speed,
                manual_marker_enabled=manual_marker_enabled,
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
        content_layout.addWidget(self._create_operation_bar())

        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(10)
        bottom_layout.addWidget(self._create_screenshot_group(), 3)
        bottom_layout.addWidget(self._create_tdf_group(), 2)
        bottom_layout.addWidget(self._create_custom_option_panel())
        bottom_layout.addWidget(self._create_technology_panel())
        content_layout.addLayout(bottom_layout, 1)

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
        table.setMinimumHeight(410)
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
        table.viewport().installEventFilter(self)
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
        widths = [
            (available_width * base_width) // _TABLE_COLUMN_BASE_TOTAL
            for base_width in _TABLE_COLUMN_BASE_WIDTHS
        ]
        columns_by_base_width = [
            column
            for column, _base_width in sorted(
                enumerate(_TABLE_COLUMN_BASE_WIDTHS),
                key=lambda item: (-item[1], item[0]),
            )
        ]
        remaining = available_width - sum(widths)
        for index in range(remaining):
            widths[columns_by_base_width[index % len(columns_by_base_width)]] += 1

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

        self._nr_sa_button.clicked.connect(self.on_nr_sa_button_clicked)
        self._nr_nsa_button.clicked.connect(self.on_nr_nsa_button_clicked)
        self._lte_button.clicked.connect(self.on_lte_button_clicked)
        self._delete_button.clicked.connect(self.on_delete_button_clicked)
        self._clear_button.clicked.connect(self.on_clear_button_clicked)
        self._load_item_button.clicked.connect(self.on_load_item_button_clicked)
        self._save_item_button.clicked.connect(self.on_save_item_button_clicked)
        self._start_button.clicked.connect(self.start_requested.emit)
        self._single_start_button.clicked.connect(self.single_start_requested.emit)
        self._stop_button.clicked.connect(self.stop_requested.emit)
        self._get_tdf_list_button.clicked.connect(self.get_tdf_list_requested.emit)
        self._tdf_all_off_button.clicked.connect(self.tdf_all_off_requested.emit)
        self._set_tdf_button.clicked.connect(self.on_set_tdf_button_clicked)

    def _create_operation_bar(self) -> QWidget:
        """Test Case ?? ??/?? ?? ?? ???."""

        panel = QWidget(self)
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self._create_hidden_monitoring_fields(panel)

        input_panel = QWidget(panel)
        input_layout = QGridLayout(input_panel)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setHorizontalSpacing(8)
        input_layout.setVerticalSpacing(3)
        input_layout.addWidget(QLabel("EUT Name", input_panel), 0, 0)

        self._eut_name_edit = QLineEdit(input_panel)
        self._eut_name_edit.setObjectName("eutNameEdit")
        input_layout.addWidget(self._eut_name_edit, 1, 0)
        input_layout.setColumnStretch(0, 1)
        layout.addWidget(input_panel, 3)

        index_panel = QWidget(panel)
        index_layout = QVBoxLayout(index_panel)
        index_layout.setContentsMargins(0, 0, 0, 0)
        index_layout.setSpacing(3)
        index_layout.addWidget(QLabel("Index", index_panel))
        self._index_edit = QLineEdit(index_panel)
        self._index_edit.setObjectName("indexEdit")
        self._index_edit.setValidator(QIntValidator(1, 2147483647, self._index_edit))
        self._index_edit.setFixedWidth(46)
        index_layout.addWidget(self._index_edit)
        layout.addWidget(index_panel)

        for text, object_name in (
            ("\uB2E8\uC77C\uC2DC\uC791", "singleStartButton"),
            ("\uC2DC\uC791", "startButton"),
            ("\uC815\uC9C0", "stopButton"),
            ("\uC0AD\uC81C", "deleteButton"),
            ("\uCD08\uAE30\uD654", "clearButton"),
            ("\uBD88\uB7EC\uC624\uAE30", "loadItemButton"),
            ("\uC800\uC7A5", "saveItemButton"),
        ):
            button = QPushButton(text, panel)
            button.setObjectName(object_name)
            if object_name == "singleStartButton":
                self._single_start_button = button
            elif object_name == "startButton":
                self._start_button = button
            elif object_name == "stopButton":
                self._stop_button = button
                self._stop_button.setEnabled(False)
            elif object_name == "deleteButton":
                self._delete_button = button
            elif object_name == "clearButton":
                self._clear_button = button
            elif object_name == "loadItemButton":
                self._load_item_button = button
            elif object_name == "saveItemButton":
                self._save_item_button = button
            layout.addWidget(button)
        return panel

    def _create_hidden_monitoring_fields(self, parent: QWidget) -> None:
        """?? setter/tests ??? ???? ??? ?? ?? ????."""

        for object_name in (
            "currentTestBandEdit",
            "currentTestFreqEdit",
            "currentFactorEdit",
            "startFreqEdit",
            "stopFreqEdit",
            "traceModeEdit",
            "mastEdit",
            "rbwEdit",
            "vbwEdit",
            "sweepPointEdit",
            "filterEdit",
            "targetAngleEdit",
            "currentAngleEdit",
            "settingSpeedEdit",
            "polarization3mEdit",
            "polarizationBilogEdit",
            "polarization1mEdit",
        ):
            edit = QLineEdit(parent)
            edit.setObjectName(object_name)
            edit.setReadOnly(True)
            edit.hide()

    def _create_tdf_group(self) -> QGroupBox:
        """FSV Factor ??? ?? TDF ?? ??? ????."""

        group = QGroupBox("FSV Factor List", self)
        group.setObjectName("tdfGroupBox")
        group.setMinimumWidth(220)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(10, 16, 10, 8)
        layout.setSpacing(6)

        self._tdf_list_widget = QListWidget(group)
        self._tdf_list_widget.setObjectName("tdfListWidget")
        self._tdf_list_widget.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection,
        )
        self._tdf_list_widget.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers,
        )
        self._tdf_list_widget.setMinimumHeight(165)
        layout.addWidget(self._tdf_list_widget, 1)

        button_layout = QHBoxLayout()
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(6)
        for text, object_name in (
            ("Select", "setTdfButton"),
            ("All Off", "tdfAllOffButton"),
            ("List Update", "getTdfListButton"),
        ):
            button = QPushButton(text, group)
            button.setObjectName(object_name)
            if object_name == "getTdfListButton":
                self._get_tdf_list_button = button
            elif object_name == "tdfAllOffButton":
                self._tdf_all_off_button = button
            elif object_name == "setTdfButton":
                self._set_tdf_button = button
            button_layout.addWidget(button)
        layout.addLayout(button_layout)

        return group

    def _create_custom_option_panel(self) -> QWidget:
        """Custom Option ?? ??? ?? ??? ????."""

        panel = QWidget(self)
        panel.setObjectName("customOptionPanel")
        panel.setFixedWidth(220)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        title_label = QLabel("Custom Option", panel)
        layout.addWidget(title_label)
        self._custom_option_check_box = QCheckBox(
            "\uCCB4\uD06C \uBC15\uC2A4 \uD574\uC81C \uC2DC \uAE30\uBCF8 \uAC12 \uC0AC\uC6A9",
            panel,
        )
        self._custom_option_check_box.setObjectName("customOptionCheckBox")
        self._custom_option_check_box.setChecked(False)
        layout.addWidget(self._custom_option_check_box)
        layout.addWidget(self._create_custom_option_group(), 1)
        return panel

    def _create_custom_option_group(self) -> QGroupBox:
        """Custom Option ?? ??? ? ???? ?? ????."""

        group = QGroupBox("", self)
        group.setObjectName("infoGroupBox")
        layout = QGridLayout(group)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(4)

        fields = (
            ("Saturation\nTime(s)", "saturationTimeEdit", 0, 0),
            ("Connection\nWaiting Time(s)", "connectionWaitingTimeEdit", 0, 1),
            ("Atten Level", "attenLevelEdit", 2, 0),
            ("Turn Table\nSpeed", "customTurnTableSpeedEdit", 2, 1),
            ("Next Peak\nSearch Level", "nextPeakSearchLevelEdit", 4, 0),
        )
        for label_text, object_name, row, column in fields:
            label = QLabel(label_text, group)
            label.setWordWrap(True)
            label.setFixedWidth(78)
            edit = self._create_custom_option_edit(object_name, group)
            layout.addWidget(label, row, column)
            layout.addWidget(edit, row + 1, column)

        marker = QCheckBox("Marker", group)
        marker.setObjectName("markerCheckBox")
        self._marker_check_box = marker
        layout.addWidget(marker, 5, 1)
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)
        layout.setRowStretch(6, 1)

        return group

    def _create_custom_option_edit(
        self,
        object_name: str,
        parent: QWidget,
    ) -> QLineEdit:
        edit = QLineEdit(parent)
        edit.setObjectName(object_name)
        edit.setFixedWidth(78)
        edit.setReadOnly(object_name not in _RUN_SETTING_FIELD_NAMES)
        self._apply_run_setting_validator(edit, object_name)
        default_value = _RUN_SETTING_FIELD_DEFAULTS.get(object_name)
        if default_value is not None:
            edit.setText(default_value)
        return edit

    def _create_screenshot_group(self) -> QWidget:
        """?? ???? ?? ??? ???."""

        panel = QWidget(self)
        self._screenshot_group_panel = panel
        panel.installEventFilter(self)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(QLabel("Screenshot", panel))

        frame = QFrame(panel)
        self._manager_screenshot_frame = frame
        frame.installEventFilter(self)
        frame.setObjectName("managerScreenshotFrame")
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame_layout = QVBoxLayout(frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        self._screenshot_image_label = QLabel("", frame)
        self._screenshot_image_label.setObjectName("managerScreenshotImageLabel")
        self._screenshot_image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._screenshot_image_label.setMinimumSize(360, 220)
        self._screenshot_image_label.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Ignored,
        )
        self._screenshot_image_label.installEventFilter(self)
        frame_layout.addWidget(self._screenshot_image_label, 1)
        layout.addWidget(frame, 1)
        self._manager_screenshot_pixmap: QPixmap | None = None
        return panel

    def _create_technology_panel(self) -> QWidget:
        """우측 RAT 선택 버튼 영역을 만든다."""

        panel = QWidget(self)
        panel.setObjectName("technologyButtonPanel")
        panel.setFixedWidth(_TECHNOLOGY_BUTTON_WIDTH)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        for text, object_name in (
            ("NR SA", "nrSaButton"),
            ("NR NSA", "nrNsaButton"),
            ("LTE", "lteButton"),
            ("WCDMA", "wcdmaButton"),
            ("GSM", "gsmButton"),
        ):
            button = QPushButton(text, panel)
            button.setObjectName(object_name)
            button.setFixedWidth(_TECHNOLOGY_BUTTON_WIDTH)
            button.setMinimumHeight(_TECHNOLOGY_BUTTON_MIN_HEIGHT)
            button.setSizePolicy(
                QSizePolicy.Policy.Fixed,
                QSizePolicy.Policy.Expanding,
            )
            if object_name == "nrSaButton":
                self._nr_sa_button = button
            elif object_name == "nrNsaButton":
                self._nr_nsa_button = button
            elif object_name == "lteButton":
                self._lte_button = button
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

            QLineEdit:disabled {
                background: #e9ecef;
                border: 1px solid #8f9ca8;
                color: #555555;
            }

            QListWidget#tdfListWidget {
                border: 1px solid #3f73a8;
                background: #ffffff;
                color: #111111;
            }

            QFrame#managerScreenshotFrame {
                border: 1px solid #3f73a8;
                background: #ffffff;
            }

            QLabel#managerScreenshotImageLabel {
                border: 0;
                background: #ffffff;
                color: #666666;
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

            QPushButton:disabled {
                background: #e1e5ea;
                border: 1px dashed #8f9ca8;
                color: #555555;
            }

            QCheckBox:disabled {
                color: #555555;
            }

            QFrame[statusIndicator="true"] {
                border: 1px solid #3f73a8;
                border-radius: 9px;
            }

            QFrame[statusIndicator="true"][connectionStatus="connected"] {
                background: #48a868;
            }

            QFrame[statusIndicator="true"][connectionStatus="connecting"] {
                background: #f3c744;
            }

            QFrame[statusIndicator="true"][connectionStatus="failed"] {
                background: #d83a3a;
            }

            QFrame[statusIndicator="true"][connectionStatus="not_connected"] {
                background: #b8c2cc;
            }

            QLabel[summaryLabel="true"] {
                font-weight: 600;
            }
            """
        )

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if (
            hasattr(self, "_test_case_table")
            and watched is self._test_case_table.viewport()
            and event.type() == QEvent.Type.Resize
        ):
            self._apply_test_case_column_widths()
        if event.type() == QEvent.Type.Resize and (
            (
                hasattr(self, "_screenshot_group_panel")
                and watched is self._screenshot_group_panel
            )
            or (
                hasattr(self, "_manager_screenshot_frame")
                and watched is self._manager_screenshot_frame
            )
        ):
            self._refresh_manager_screenshot_preview()
        if (
            hasattr(self, "_screenshot_image_label")
            and watched is self._screenshot_image_label
            and event.type() == QEvent.Type.Resize
        ):
            self._update_manager_screenshot_pixmap()
        return super().eventFilter(watched, event)

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        """?? ?? ?? ? ???? ???? ??? ?? ???."""

        super().resizeEvent(event)
        self._apply_test_case_column_widths()
        self._refresh_manager_screenshot_preview()

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        """패널 표시 후 확정된 크기에 맞춰 스크린샷을 다시 맞춘다."""

        super().showEvent(event)
        self._refresh_manager_screenshot_preview()
        QTimer.singleShot(0, self._refresh_manager_screenshot_preview)

    def on_screenshot_saved(self, path: str) -> None:
        screenshot_path = Path(path)
        pixmap = QPixmap(str(screenshot_path))
        if pixmap.isNull():
            return
        self._manager_screenshot_pixmap = pixmap
        self._refresh_manager_screenshot_preview()
        QTimer.singleShot(0, self._refresh_manager_screenshot_preview)

    def _refresh_manager_screenshot_preview(self) -> None:
        self._apply_manager_screenshot_aspect_ratio()
        self._update_manager_screenshot_pixmap()

    def _apply_manager_screenshot_aspect_ratio(self) -> None:
        if not hasattr(self, "_manager_screenshot_frame"):
            return
        if not hasattr(self, "_screenshot_group_panel"):
            return
        if not hasattr(self, "_screenshot_image_label"):
            return

        frame_height = self._manager_screenshot_frame.height()
        if frame_height <= 0:
            return

        frame_layout = self._manager_screenshot_frame.layout()
        if frame_layout is None:
            return
        margins = frame_layout.contentsMargins()
        image_height = max(
            frame_height - margins.top() - margins.bottom(),
            self._screenshot_image_label.minimumHeight(),
        )
        target_frame_width = int(
            image_height * _SCREENSHOT_PREVIEW_ASPECT_RATIO,
        )
        target_frame_width += margins.left() + margins.right()
        min_frame_width = (
            self._screenshot_image_label.minimumWidth()
            + margins.left()
            + margins.right()
        )
        target_frame_width = max(target_frame_width, min_frame_width)

        if self._manager_screenshot_frame.maximumWidth() != target_frame_width:
            self._manager_screenshot_frame.setMaximumWidth(target_frame_width)
        if self._screenshot_group_panel.maximumWidth() != target_frame_width:
            self._screenshot_group_panel.setMaximumWidth(target_frame_width)

    def _manager_screenshot_display_pixmap(self) -> QPixmap:
        assert self._manager_screenshot_pixmap is not None
        pixmap = self._manager_screenshot_pixmap
        if pixmap.width() <= 0 or pixmap.height() <= 0:
            return pixmap

        current_aspect_ratio = pixmap.width() / pixmap.height()
        if abs(current_aspect_ratio - _SCREENSHOT_PREVIEW_PADDED_ASPECT_RATIO) > 0.02:
            return pixmap

        crop_height = int(
            pixmap.width()
            * _SCREENSHOT_PREVIEW_SOURCE_HEIGHT
            / _SCREENSHOT_PREVIEW_SOURCE_WIDTH,
        )
        if crop_height <= 0 or crop_height >= pixmap.height():
            return pixmap
        return pixmap.copy(0, 0, pixmap.width(), crop_height)

    def _update_manager_screenshot_pixmap(self) -> None:
        if not hasattr(self, "_screenshot_image_label"):
            return
        if self._manager_screenshot_pixmap is None:
            return
        target_size = self._screenshot_image_label.size()
        if target_size.width() <= 0 or target_size.height() <= 0:
            return
        display_pixmap = self._manager_screenshot_display_pixmap()
        scaled = display_pixmap.scaled(
            target_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._screenshot_image_label.setText("")
        self._screenshot_image_label.setPixmap(scaled)

    def on_nr_sa_button_clicked(self) -> None:
        """NR SA 통합 생성 팝업을 연다."""

        self._open_nr_dialog(Generation.NR_SA)

    def on_nr_nsa_button_clicked(self) -> None:
        """NR NSA 통합 생성 팝업을 연다."""

        self._open_nr_dialog(Generation.NR_NSA)

    def _open_nr_dialog(self, generation: Generation) -> None:
        """Generation별 독립 상태로 NR 통합 생성 팝업을 연다."""

        dialog = NRSelectDialog(
            self,
            generation=generation,
            state=self._nr_states[generation],
        )
        dialog.test_cases_created.connect(self.add_test_cases)
        dialog.exec()
        self._nr_states[generation] = dialog.state

    def on_lte_button_clicked(self) -> None:
        """LTE 버튼 클릭 시 통합 TestCase 생성 팝업을 연다."""

        dialog = LTESelectDialog(
            self,
            parameters_by_band=self._lte_parameters_by_band,
            group_settings=self._lte_group_settings,
        )
        dialog.test_cases_created.connect(self.add_test_cases)
        dialog.exec()
        self._lte_parameters_by_band = dialog.parameters_by_band
        self._lte_group_settings = dialog.group_settings

    def on_set_tdf_button_clicked(self) -> None:
        """선택된 TDF 파일 활성화를 요청한다."""

        tdf_file_name = self.selected_tdf_file_name
        if not tdf_file_name:
            self._show_warning("활성화할 TDF 파일을 선택하세요.")
            return
        self.set_tdf_requested.emit(tdf_file_name)

    def _refresh_tdf_active_marks(self) -> None:
        """현재 활성 TDF 항목의 배경색만 표시한다."""

        active_background = QBrush(QColor("#d8f3dc"))
        for row in range(self._tdf_list_widget.count()):
            item = self._tdf_list_widget.item(row)
            is_active = self._tdf_item_file_name(item) == self._active_tdf_file_name
            item.setBackground(active_background if is_active else QBrush())

    def _refresh_test_case_progress_marks(self) -> None:
        """TestCase 진행 상태에 따라 행 배경색을 갱신한다."""

        for row in range(self._test_case_table.rowCount()):
            status = (
                self._test_case_progress[row]
                if row < len(self._test_case_progress)
                else "pending"
            )
            self._set_test_case_row_background(row, self._background_for_progress(status))

    def _set_test_case_row_background(self, row: int, background: QBrush) -> None:
        for column in range(self._test_case_table.columnCount()):
            item = self._test_case_table.item(row, column)
            if item is not None:
                item.setBackground(background)

    def _refresh_test_case_indexes(self) -> None:
        for row in range(self._test_case_table.rowCount()):
            item = self._test_case_table.item(row, 0)
            if item is not None:
                item.setText(str(row + 1))

    def _background_for_progress(self, status: _TestCaseProgress) -> QBrush:
        if status == "running":
            return QBrush(_TEST_CASE_RUNNING_BACKGROUND)
        if status == "completed":
            return QBrush(_TEST_CASE_COMPLETED_BACKGROUND)
        return QBrush()

    def _find_test_case_index(self, case: TestCase) -> int | None:
        for index, candidate in enumerate(self._test_cases):
            if candidate is case:
                return index
        for index, candidate in enumerate(self._test_cases):
            if candidate == case:
                return index
        return None

    @staticmethod
    def _tdf_item_file_name(item: QListWidgetItem) -> str:
        file_name = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(file_name, str):
            return file_name
        return item.text()

    def on_delete_button_clicked(self) -> None:
        """선택한 TestCase 하나를 삭제한다."""

        row = self._test_case_table.currentRow()
        if row < 0 or row >= len(self._test_cases):
            return

        self._test_cases.pop(row)
        self._test_case_progress.pop(row)
        self._completed_test_case_indexes = {
            index if index < row else index - 1
            for index in self._completed_test_case_indexes
            if index != row
        }
        self._test_case_table.removeRow(row)
        self._refresh_test_case_indexes()
        self._refresh_test_case_progress_marks()

    def on_clear_button_clicked(self) -> None:
        """모든 TestCase를 삭제한다."""

        if not self._test_cases and self._test_case_table.rowCount() == 0:
            return

        self._test_cases.clear()
        self._test_case_progress.clear()
        self._completed_test_case_indexes.clear()
        self._test_case_table.setRowCount(0)
        self._index_edit.clear()

    def on_load_item_button_clicked(self) -> None:
        """CSV 파일에서 TestCase를 읽어 기존 목록 뒤에 추가한다."""

        csv_directory = self._prepare_csv_dialog_directory()
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Test Case CSV 불러오기",
            str(csv_directory),
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

        csv_directory = self._prepare_csv_dialog_directory()
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Test Case CSV 저장",
            str(csv_directory),
            "CSV Files (*.csv);;All Files (*)",
        )
        if not file_path:
            return

        path = Path(file_path)
        if not path.suffix:
            path = path.with_suffix(".csv")

        try:
            save_csv(path, self._test_cases)
        except (OSError, ValueError) as exc:
            self._show_warning(f"CSV 저장에 실패했습니다.\n{exc}")
            return

    def _prepare_csv_dialog_directory(self) -> Path:
        """실행 환경 기준 CSV 폴더를 만들고 대화상자 시작 경로를 반환한다."""

        directory = _default_csv_directory()
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self._show_warning(
                "CSV 폴더를 생성하지 못했습니다. "
                "상위 폴더에서 시작합니다.\n"
                f"{exc}"
            )
            return directory.parent
        return directory

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

    def _update_info_text_if_present(
        self,
        info: object,
        object_name: str,
        *keys: str,
    ) -> None:
        found, value = self._try_info_value(info, *keys)
        if found:
            self._set_line_edit_text(object_name, value)

    def _info_value(self, info: object, *keys: str) -> Any:
        found, value = self._try_info_value(info, *keys)
        if found:
            return value
        return None

    def _try_info_value(self, info: object, *keys: str) -> tuple[bool, Any]:
        if isinstance(info, dict):
            return self._try_value_from_mapping(info, *keys)

        for key in keys:
            if key.isidentifier() and hasattr(info, key):
                return True, getattr(info, key)

        attributes = getattr(info, "__dict__", None)
        if isinstance(attributes, dict):
            return self._try_value_from_mapping(attributes, *keys)
        return False, None

    def _value_from_mapping(self, values: dict[Any, Any], *keys: str) -> Any:
        found, value = self._try_value_from_mapping(values, *keys)
        if found:
            return value
        return None

    def _try_value_from_mapping(
        self,
        values: dict[Any, Any],
        *keys: str,
    ) -> tuple[bool, Any]:
        for key in keys:
            if key in values:
                return True, values[key]

        normalized_values = {
            self._normalize_key(str(key)): value for key, value in values.items()
        }
        for key in keys:
            normalized_key = self._normalize_key(key)
            if normalized_key in normalized_values:
                return True, normalized_values[normalized_key]
        return False, None

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

    def _set_connection_indicator_status(self, indicator: QFrame, status: str) -> None:
        connected = status == _CONNECTION_STATUS_CONNECTED
        indicator.setProperty("connectionStatus", status)
        indicator.setProperty("connected", connected)
        indicator.setProperty("disconnected", not connected)
        self._refresh_widget_style(indicator)

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
        elif object_name == "customTurnTableSpeedEdit":
            edit.setValidator(QIntValidator(1, _MAX_CUSTOM_TURNTABLE_SPEED, edit))
        elif object_name == "nextPeakSearchLevelEdit":
            edit.setValidator(
                QDoubleValidator(0.0, _MAX_NEXT_PEAK_SEARCH_LEVEL_DB, 6, edit)
            )

    def _show_warning(self, message: str) -> None:
        """Test Manager 경고 메시지를 표시한다."""

        QMessageBox.warning(self, "Test Manager", message)

    def add_test_cases(self, cases: Iterable[TestCase]) -> None:
        """생성된 TestCase를 내부 목록과 표에 추가한다."""

        for case in cases:
            self._test_cases.append(case)
            self._test_case_progress.append("pending")
            self._append_test_case_row(case)
        self._refresh_test_case_progress_marks()

    def _append_test_case_row(self, case: TestCase) -> None:
        """TestCase 하나를 실행 표에 표시한다."""

        row = self._test_case_table.rowCount()
        self._test_case_table.insertRow(row)
        for column, value in enumerate((str(row + 1), *self._row_values_for_case(case))):
            item = QTableWidgetItem(value)
            item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item.setForeground(QBrush(_TABLE_TEXT_COLOR))
            self._test_case_table.setItem(row, column, item)

    def _row_values_for_case(self, case: TestCase) -> tuple[str, ...]:
        """확장 TestCase 표 컬럼 순서에 맞춰 표시값을 만든다."""

        test_range = case.range_definition
        return (
            case.generation.value,
            self._format_band_label(case),
            case.dut_ant_position.value,
            str(case.scs_khz),
            self._format_number(case.bandwidth),
            case.modulation.value,
            case.rb_allocation.value,
            str(case.rb_size),
            str(case.rb_offset),
            case.test_channel.value,
            self._safe_channel_number(case),
            # TODO(spec): CH_No. 컬럼 의미가 확정되면 표시값을 조정한다.
            self._safe_frequency(case),
            str(case.test_range.value),
            self._format_number(test_range.start_freq),
            self._format_number(test_range.stop_freq),
            case.dut_axis.value,
            case.antenna_pol.value,
        )

    def _format_band_label(self, case: TestCase) -> str:
        if case.generation is Generation.NR_NSA:
            if case.anchor_band is None:
                raise ValueError("NR_NSA requires anchor_band")
            return f"{case.band.value}-{case.anchor_band.value}"
        return case.band.value

    def _format_number(self, value: float) -> str:
        return format(float(value), ".15g")

    def _format_test_range_label(self, test_range: TestRange) -> str:
        start_freq = test_range.start_freq
        stop_freq = test_range.stop_freq
        if start_freq >= 1000 and stop_freq >= 1000:
            return (
                f"{self._format_number(start_freq / 1000)}-"
                f"{self._format_number(stop_freq / 1000)}G"
            )
        if start_freq < 1000 and stop_freq < 1000:
            return (
                f"{self._format_number(start_freq)}-"
                f"{self._format_number(stop_freq)}M"
            )
        return (
            f"{self._format_range_frequency(start_freq)}-"
            f"{self._format_range_frequency(stop_freq)}"
        )

    def _format_range_frequency(self, frequency_mhz: float) -> str:
        if frequency_mhz >= 1000:
            return f"{self._format_number(frequency_mhz / 1000)}G"
        return f"{self._format_number(frequency_mhz)}M"

    def _format_current_factor(self, case: TestCase) -> str:
        values = (value if value else "-" for value in self._row_values_for_case(case))
        return " / ".join(values)

    def _safe_channel_number(self, case: TestCase) -> str:
        try:
            return str(case.channel_number)
        except ValueError:
            return ""

    def _safe_frequency(self, case: TestCase) -> str:
        try:
            return self._format_number(case.frequency_mhz)
        except ValueError:
            return ""
