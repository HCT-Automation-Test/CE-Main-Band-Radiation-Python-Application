"""NR Test Case 선택 팝업."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.models.band_group import BAND_GROUPS, resolve_range_id
from app.models.enums import (
    AntennaPol,
    DUTAntPosition,
    DUTAxis,
    Modulation,
    NRBand,
    RBAllocation,
    TestChannel,
    TestType,
)
from app.models.nr_channel_lookup import resolve_call_channel
from app.models.supported_bandwidths import get_supported_bandwidths
from app.models.test_case import TestCase

_GROUP_TITLES: dict[str, str] = {
    "lb": "LB",
    "mhb_fdd": "MHB_FDD",
    "mhb_tdd": "MHB_TDD",
    "uhb_tdd": "UHB_TDD",
}

_PARAMETER_HEADERS: tuple[str, ...] = (
    "Band",
    "Case",
    "BW",
    "Modulation",
    "RB Allocation",
    "CH",
    "EUT ANT",
    "Axis",
    "Pol",
)


@dataclass(frozen=True)
class NRCaseParameters:
    """NR Select 표에서 band별로 입력하는 TestCase 파라미터."""

    test_type: TestType
    bandwidth: float
    modulation: Modulation
    rb_allocation: RBAllocation
    test_channel: TestChannel
    dut_ant_position: DUTAntPosition
    dut_axis: DUTAxis
    antenna_pol: AntennaPol


def _band_from_number(band_number: int) -> NRBand:
    return NRBand(f"n{band_number}")


def _band_label(band: NRBand) -> str:
    return f"B{band.value[1:]}"


def _format_bandwidth(bandwidth: object) -> str:
    return format(float(bandwidth), ".15g")


def _field_object_suffix(field_name: str) -> str:
    return "".join(part.capitalize() for part in field_name.split("_"))


def _supported_test_types(band: NRBand) -> tuple[TestType, ...]:
    supported: list[TestType] = []
    for test_type in TestType:
        try:
            resolve_range_id(band, test_type)
        except ValueError:
            continue
        supported.append(test_type)
    return tuple(supported)


def _default_parameters_for_band(band: NRBand) -> NRCaseParameters:
    return NRCaseParameters(
        test_type=_supported_test_types(band)[0],
        bandwidth=get_supported_bandwidths(band)[0],
        modulation=Modulation.QPSK,
        rb_allocation=RBAllocation.INNER_FULL,
        test_channel=TestChannel.MID,
        dut_ant_position=DUTAntPosition.UPPER,
        dut_axis=DUTAxis.X,
        antenna_pol=AntennaPol.H,
    )


def _create_default_parameters() -> dict[NRBand, NRCaseParameters]:
    return {
        _band_from_number(band_number): _default_parameters_for_band(
            _band_from_number(band_number),
        )
        for group in BAND_GROUPS
        for band_number in group.bands
    }


class NRParameterDialog(QDialog):
    """Band별 TestCase 파라미터를 입력하는 보조 팝업."""

    def __init__(
        self,
        parameters_by_band: Mapping[NRBand, NRCaseParameters],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("nrParameterDialog")
        self.setWindowTitle("NR Table")
        self._parameters_by_band = dict(parameters_by_band)
        self._combo_by_cell: dict[tuple[NRBand, str], QComboBox] = {}
        self._setup_layout()
        self._apply_styles()

    def parameters_by_band(self) -> dict[NRBand, NRCaseParameters]:
        """표에 입력된 band별 파라미터를 반환한다."""

        parameters: dict[NRBand, NRCaseParameters] = {}
        for band in self._parameters_by_band:
            parameters[band] = NRCaseParameters(
                test_type=self._current_data(band, "test_type"),
                bandwidth=self._current_data(band, "bandwidth"),
                modulation=self._current_data(band, "modulation"),
                rb_allocation=self._current_data(band, "rb_allocation"),
                test_channel=self._current_data(band, "test_channel"),
                dut_ant_position=self._current_data(band, "dut_ant_position"),
                dut_axis=self._current_data(band, "dut_axis"),
                antenna_pol=self._current_data(band, "antenna_pol"),
            )
        return parameters

    def _setup_layout(self) -> None:
        """파라미터 입력용 표와 확인/취소 버튼을 배치한다."""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        self._table = QTableWidget(len(self._parameters_by_band), len(_PARAMETER_HEADERS), self)
        self._table.setObjectName("nrParameterTable")
        self._table.setHorizontalHeaderLabels(_PARAMETER_HEADERS)
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        for row, (band, parameters) in enumerate(self._parameters_by_band.items()):
            self._setup_band_row(row, band, parameters)

        header = self._table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        self._table.resizeColumnsToContents()
        layout.addWidget(self._table)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        button_box.setObjectName("nrParameterButtonBox")
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        self.resize(900, 520)

    def _setup_band_row(
        self,
        row: int,
        band: NRBand,
        parameters: NRCaseParameters,
    ) -> None:
        """한 band에 해당하는 파라미터 입력 행을 구성한다."""

        band_item = QTableWidgetItem(_band_label(band))
        band_item.setData(Qt.ItemDataRole.UserRole, band)
        band_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self._table.setItem(row, 0, band_item)
        self._set_combo(row, 1, band, "test_type", _supported_test_types(band), parameters.test_type)
        self._set_combo(
            row,
            2,
            band,
            "bandwidth",
            get_supported_bandwidths(band),
            parameters.bandwidth,
            text_formatter=_format_bandwidth,
        )
        self._set_combo(row, 3, band, "modulation", tuple(Modulation), parameters.modulation)
        self._set_combo(
            row,
            4,
            band,
            "rb_allocation",
            tuple(RBAllocation),
            parameters.rb_allocation,
        )
        self._set_combo(row, 5, band, "test_channel", tuple(TestChannel), parameters.test_channel)
        self._set_combo(
            row,
            6,
            band,
            "dut_ant_position",
            tuple(DUTAntPosition),
            parameters.dut_ant_position,
        )
        self._set_combo(row, 7, band, "dut_axis", tuple(DUTAxis), parameters.dut_axis)
        self._set_combo(row, 8, band, "antenna_pol", tuple(AntennaPol), parameters.antenna_pol)

    def _set_combo(
        self,
        row: int,
        column: int,
        band: NRBand,
        field_name: str,
        values: tuple[object, ...],
        current_value: object,
        *,
        text_formatter: Callable[[object], str] | None = None,
    ) -> None:
        """표 셀에 enum/숫자 선택 콤보를 넣는다."""

        combo = QComboBox(self._table)
        combo.setObjectName(f"nrParam{_field_object_suffix(field_name)}_{band.value}")
        for value in values:
            if text_formatter is None:
                text = getattr(value, "value", str(value))
            else:
                text = text_formatter(value)
            combo.addItem(str(text), value)
        combo.setCurrentIndex(max(combo.findData(current_value), 0))
        self._table.setCellWidget(row, column, combo)
        self._combo_by_cell[(band, field_name)] = combo

    def _current_data(self, band: NRBand, field_name: str) -> object:
        return self._combo_by_cell[(band, field_name)].currentData()

    def _apply_styles(self) -> None:
        """NR Table 팝업 전용 스타일을 적용한다."""

        self.setStyleSheet(
            """
            QTableWidget#nrParameterTable {
                border: 1px solid #2f5aa8;
                gridline-color: #d6e0ef;
                background: #ffffff;
                color: #111111;
                alternate-background-color: #f4f8fe;
            }

            QTableWidget#nrParameterTable QHeaderView::section {
                background: #edf3fa;
                color: #111111;
                border: 0;
                border-right: 1px solid #ffffff;
                border-bottom: 1px solid #d2ddea;
                padding: 4px 6px;
            }

            QComboBox {
                background: #ffffff;
                color: #111111;
                border: 1px solid #9eb4d0;
                padding: 2px 6px;
            }

            QDialogButtonBox QPushButton {
                background: #fbfbfb;
                color: #111111;
                border: 1px solid #2f5aa8;
                padding: 5px 12px;
            }
            """
        )


class NRSelectDialog(QDialog):
    """Test Manager에서 사용할 NR Test Case 선택 팝업."""

    test_cases_created = Signal(list)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("nrSelectDialog")
        self.setWindowTitle("NR Select")
        self._band_checks: dict[NRBand, QCheckBox] = {}
        self._parameters_by_band = _create_default_parameters()
        self._setup_layout()
        self._apply_styles()

    @property
    def parameters_by_band(self) -> dict[NRBand, NRCaseParameters]:
        """현재 저장된 band별 TestCase 파라미터를 반환한다."""

        return dict(self._parameters_by_band)

    def selected_bands(self) -> list[NRBand]:
        """선택된 band 목록을 화면 순서대로 반환한다."""

        return [
            band
            for band in self._parameters_by_band
            if self._band_checks[band].isChecked()
        ]

    def _setup_layout(self) -> None:
        """초안 기준 NR Select 레이아웃을 구성한다."""

        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(18, 18, 18, 18)
        root_layout.setSpacing(16)

        band_layout = QVBoxLayout()
        band_layout.setContentsMargins(0, 0, 0, 0)
        band_layout.setSpacing(6)

        title = QLabel("BAND", self)
        title.setObjectName("nrBandTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFixedSize(86, 46)
        band_layout.addWidget(title, alignment=Qt.AlignmentFlag.AlignLeft)

        group_layout = QHBoxLayout()
        group_layout.setContentsMargins(0, 0, 0, 0)
        group_layout.setSpacing(14)
        for group in BAND_GROUPS:
            group_layout.addWidget(self._create_band_group(group.key, group.bands))
        band_layout.addLayout(group_layout, 1)

        action_layout = QVBoxLayout()
        action_layout.setContentsMargins(0, 52, 0, 0)
        action_layout.setSpacing(0)

        self._table_button = QPushButton("Table", self)
        self._table_button.setObjectName("nrTableButton")
        self._table_button.setMinimumSize(210, 108)
        self._table_button.clicked.connect(self.on_table_clicked)

        self._add_button = QPushButton("Add", self)
        self._add_button.setObjectName("nrAddButton")
        self._add_button.setMinimumSize(210, 48)
        self._add_button.clicked.connect(self.on_add_clicked)

        action_layout.addWidget(self._table_button)
        action_layout.addStretch(1)
        action_layout.addWidget(self._add_button)

        root_layout.addLayout(band_layout, 1)
        root_layout.addLayout(action_layout)
        self.setMinimumSize(860, 350)

    def _create_band_group(self, group_key: str, band_numbers: tuple[int, ...]) -> QFrame:
        """Band 그룹별 체크박스 영역을 만든다."""

        group = QFrame(self)
        group.setObjectName(f"nrBandGroup_{group_key}")
        group.setProperty("nrBandGroup", True)
        group.setMinimumWidth(144)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(12, 12, 12, 8)
        layout.setSpacing(4)

        group_title = QLabel(_GROUP_TITLES[group_key], group)
        group_title.setObjectName(f"nrBandGroupTitle_{group_key}")
        group_title.setProperty("nrBandGroupTitle", True)
        layout.addWidget(group_title)

        for band_number in band_numbers:
            band = _band_from_number(band_number)
            layout.addWidget(self._create_band_check_row(group, band))

        layout.addStretch(1)
        toggle_button = QPushButton("ALL/RESET", group)
        toggle_button.setObjectName(f"nrBandToggle_{group_key}")
        toggle_button.clicked.connect(lambda checked=False, key=group_key: self.on_group_toggle_clicked(key))
        layout.addWidget(toggle_button)
        return group

    def _create_band_check_row(self, parent: QWidget, band: NRBand) -> QWidget:
        """Band 라벨 오른쪽에 체크박스를 둔 행을 만든다."""

        row = QWidget(parent)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        label = QLabel(_band_label(band), row)
        label.setObjectName(f"nrBandLabel_{band.value}")
        checkbox = QCheckBox(row)
        checkbox.setObjectName(f"nrBandCheck_{band.value}")
        checkbox.setCursor(Qt.CursorShape.PointingHandCursor)
        checkbox.setFixedSize(22, 22)
        self._band_checks[band] = checkbox

        layout.addWidget(label)
        layout.addStretch(1)
        layout.addWidget(checkbox)
        return row

    def on_group_toggle_clicked(self, group_key: str) -> None:
        """해당 그룹의 모든 Band를 선택하거나 해제한다."""

        group = next(item for item in BAND_GROUPS if item.key == group_key)
        bands = [_band_from_number(band_number) for band_number in group.bands]
        should_check = not all(self._band_checks[band].isChecked() for band in bands)
        for band in bands:
            self._band_checks[band].setChecked(should_check)

    def on_table_clicked(self) -> None:
        """Band별 파라미터 입력 팝업을 연다."""

        dialog = NRParameterDialog(self._parameters_by_band, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._parameters_by_band = dialog.parameters_by_band()

    def on_add_clicked(self) -> None:
        """선택한 Band와 Table 파라미터로 TestCase를 생성한다."""

        selected_bands = self.selected_bands()
        if not selected_bands:
            QMessageBox.warning(self, "NR Select", "선택된 Band가 없습니다.")
            return

        try:
            cases = [self._build_test_case(band) for band in selected_bands]
        except ValueError as exc:
            QMessageBox.warning(self, "NR Select", str(exc))
            return

        self.test_cases_created.emit(cases)
        self.accept()

    def _build_test_case(self, band: NRBand) -> TestCase:
        """저장된 Table 파라미터로 단일 TestCase를 생성한다."""

        parameters = self._parameters_by_band[band]
        case = TestCase(
            band=band,
            bandwidth=parameters.bandwidth,
            test_type=parameters.test_type,
            modulation=parameters.modulation,
            rb_allocation=parameters.rb_allocation,
            test_channel=parameters.test_channel,
            antenna_pol=parameters.antenna_pol,
            dut_axis=parameters.dut_axis,
            dut_ant_position=parameters.dut_ant_position,
        )
        resolve_call_channel(case.band, case.bandwidth, case.test_channel)
        return case

    def _apply_styles(self) -> None:
        """NR Select 전용 기본 스타일을 적용한다."""

        self.setStyleSheet(
            """
            QLabel#nrBandTitle,
            QFrame[nrBandGroup="true"],
            QPushButton {
                border: 1px solid #2f5aa8;
            }

            QDialog#nrSelectDialog,
            QFrame[nrBandGroup="true"],
            QWidget {
                background: #ffffff;
                color: #111111;
            }

            QLabel {
                color: #111111;
            }

            QLabel#nrBandTitle {
                font-size: 20px;
                background: #ffffff;
                color: #111111;
            }

            QFrame[nrBandGroup="true"] {
                background: #ffffff;
            }

            QLabel[nrBandGroupTitle="true"] {
                font-size: 18px;
                color: #111111;
            }

            QPushButton {
                background: #fbfbfb;
                color: #111111;
                font-size: 18px;
                padding: 5px 10px;
            }

            QPushButton:hover {
                background: #f1f7ff;
            }

            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 1px solid #2f5aa8;
                background: #ffffff;
            }

            QCheckBox::indicator:checked {
                background: #5a9bd5;
            }
            """
        )
