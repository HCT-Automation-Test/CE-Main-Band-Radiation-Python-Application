"""Test Manager 서브 패널."""
from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QPalette
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
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.models.nr_channel_lookup import (
    resolve_call_channel,
    resolve_target_frequency_mhz,
)
from app.models.test_case import TestCase
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
    ("Turn Table Speed", "turnTableSpeedEdit"),
    ("Atten Level", "attenLevelEdit"),
    ("Next Peak Search Level", "nextPeakSearchLevelEdit"),
)

_TECHNOLOGY_BUTTON_WIDTH = 120
_TECHNOLOGY_BUTTON_MIN_HEIGHT = 38
_ACTION_BODY_SPACING = 12
_LOG_PANEL_WIDTH = 280
_TABLE_TEXT_COLOR = QColor("#111111")
_TABLE_SELECTION_COLOR = QColor("#dcecff")


class TestManagerPanel(QWidget):
    """테스트 케이스 생성, 실행, 로그 출력의 중심 패널."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._test_cases: list[TestCase] = []
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
        horizontal_header.setStretchLastSection(True)
        horizontal_header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        table.verticalHeader().setVisible(False)
        return table

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
            status.setFixedSize(18, 18)
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
        edit.setReadOnly(True)
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
                background: #5a9bd5;
                border: 1px solid #3f73a8;
                border-radius: 9px;
            }

            QLabel[summaryLabel="true"] {
                font-weight: 600;
            }
            """
        )

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
