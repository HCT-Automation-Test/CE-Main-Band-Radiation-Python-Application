"""Test Manager 서브 패널."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
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
    QVBoxLayout,
    QWidget,
)


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


class TestManagerPanel(QWidget):
    """테스트 케이스 생성, 실행, 로그 출력의 중심 패널."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._setup_layout()
        self._apply_styles()

    def _setup_layout(self) -> None:
        """초안 기준 Test Manager 레이아웃을 구성한다."""

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(8)

        self._test_case_table = self._create_test_case_table()
        root_layout.addWidget(self._test_case_table, 1)

        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(10)
        root_layout.addLayout(bottom_layout)

        bottom_layout.addWidget(self._create_left_panel(), 3)
        bottom_layout.addWidget(self._create_center_panel(), 3)
        bottom_layout.addWidget(self._create_technology_panel())

    def _create_test_case_table(self) -> QTableWidget:
        """확장 실행용 Test Case 표를 만든다."""

        table = QTableWidget(0, len(_TABLE_HEADERS), self)
        table.setObjectName("testCaseTable")
        table.setHorizontalHeaderLabels(_TABLE_HEADERS)
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
        self._excel_template_browse_button = QPushButton("...", panel)
        self._excel_template_browse_button.setObjectName("excelTemplateBrowseButton")

        self._screenshot_root_edit = QLineEdit(panel)
        self._screenshot_root_edit.setObjectName("screenshotRootEdit")
        self._screenshot_root_browse_button = QPushButton("...", panel)
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
        layout.setSpacing(6)

        action_layout = QHBoxLayout()
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(6)
        for text, object_name in (
            ("Start", "startButton"),
            ("Pause", "pauseButton"),
            ("Delete", "deleteButton"),
            ("Clear", "clearButton"),
            ("Load Item", "loadItemButton"),
            ("Save Item", "saveItemButton"),
        ):
            button = QPushButton(text, panel)
            button.setObjectName(object_name)
            action_layout.addWidget(button)
        layout.addLayout(action_layout)

        layout.addWidget(self._create_info_group(), 1)
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
        panel.setFixedWidth(154)
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
            button.setMinimumHeight(48)
            layout.addWidget(button)

        layout.addStretch(1)
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
                min-height: 28px;
                padding: 3px 8px;
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
