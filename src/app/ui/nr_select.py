"""NR Test Case 선택 팝업."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
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

from app.models.band_group import BAND_GROUPS, find_band_group
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
from app.models.nr_channel_lookup import (
    resolve_call_channel,
    resolve_target_frequency_mhz,
)
from app.models.supported_bandwidths import get_supported_bandwidths
from app.models.test_case import TestCase

_GROUP_TITLES: dict[str, str] = {
    "lb": "LB",
    "mhb_fdd": "MHB_FDD",
    "mhb_tdd": "MHB_TDD",
    "uhb_tdd": "UHB_TDD",
}

_PARAMETER_HEADERS: tuple[str, ...] = (
    "",
    "NR Band",
    "SCS",
    "BW",
    "MOD",
    "RB Allocation",
    "Channel",
    "EUT ANT",
    "NARFCN",
    "Frequency",
    "RB Size",
    "RB Offset",
    "Test 대역",
    "Position",
)

_GROUP_COLUMN = 0
_BAND_COLUMN = 1
_SCS_COLUMN = 2
_BANDWIDTH_COLUMN = 3
_MODULATION_COLUMN = 4
_RB_ALLOCATION_COLUMN = 5
_CHANNEL_COLUMN = 6
_EUT_ANT_COLUMN = 7
_NARFCN_COLUMN = 8
_FREQUENCY_COLUMN = 9
_RB_SIZE_COLUMN = 10
_RB_OFFSET_COLUMN = 11
_TEST_RANGE_COLUMN = 12
_POSITION_COLUMN = 13
_MIN_PARAMETER_ROW_HEIGHT = 30
_POSITION_OPTION_MIN_WIDTH = 86
_PARAMETER_COLUMN_WIDTHS: tuple[int, ...] = (
    76,
    66,
    46,
    66,
    90,
    120,
    74,
    76,
    80,
    82,
    66,
    74,
    105,
    210,
)
_RB_ALLOCATION_OPTIONS: tuple[RBAllocation, ...] = (
    RBAllocation.INNER_1RB_LEFT,
    RBAllocation.INNER_1RB_RIGHT,
    RBAllocation.INNER_FULL,
)
_DUT_ANT_POSITION_OPTIONS: tuple[DUTAntPosition, ...] = (
    DUTAntPosition.LOWER,
    DUTAntPosition.UPPER,
)


@dataclass(frozen=True)
class NRTestRangeOption:
    """Table의 Test 대역 체크 항목."""

    label: str
    test_type: TestType


@dataclass(frozen=True)
class NRPositionOption:
    """Table의 Position 체크 항목."""

    label: str
    values: tuple[DUTAxis, ...] | tuple[AntennaPol, ...]


@dataclass(frozen=True)
class NRCaseParameters:
    """NR Select 표에서 band별로 입력하는 TestCase 파라미터."""

    bandwidth: float
    modulation: Modulation
    rb_allocation: RBAllocation
    test_channel: TestChannel
    dut_ant_position: DUTAntPosition


@dataclass(frozen=True)
class NRGroupSettings:
    """NR Select 표에서 group별로 입력하는 대역/Position 설정."""

    selected_test_types: tuple[TestType, ...]
    axis_sequence: tuple[DUTAxis, ...]
    antenna_pol_sequence: tuple[AntennaPol, ...]


def _band_from_number(band_number: int) -> NRBand:
    return NRBand(f"n{band_number}")


def _band_label(band: NRBand) -> str:
    return band.value.upper()


def _format_number(value: float | int) -> str:
    return format(float(value), ".15g")


def _format_bandwidth(bandwidth: object) -> str:
    return _format_number(float(bandwidth))


def _field_object_suffix(field_name: str) -> str:
    return "".join(part.capitalize() for part in field_name.split("_"))


def _option_object_suffix(label: str) -> str:
    return (
        label.replace("->", "_to_")
        .replace("-", "_")
        .replace("/", "_")
        .replace(" ", "")
    )


def _group_key_for_band(band: NRBand) -> str:
    band_number = int(band.value[1:])
    for group in BAND_GROUPS:
        if band_number in group.bands:
            return group.key
    raise ValueError(f"Unknown band: {band.value}")


def _test_range_options_for_group(group_key: str) -> tuple[NRTestRangeOption, ...]:
    if group_key == "lb":
        return (
            NRTestRangeOption("30M-1G", TestType.INBAND),
            NRTestRangeOption("1-12.75G", TestType.HARMONIC),
        )
    if group_key in {"mhb_fdd", "mhb_tdd"}:
        return (
            NRTestRangeOption("30M-1G", TestType.BILOG),
            NRTestRangeOption("1-3G", TestType.INBAND),
            NRTestRangeOption("3-12.75G", TestType.HARMONIC),
        )
    return (
        NRTestRangeOption("30M-1G", TestType.BILOG),
        NRTestRangeOption("1-6G", TestType.INBAND),
        NRTestRangeOption("6-18G", TestType.HARMONIC),
    )


def _axis_options() -> tuple[NRPositionOption, ...]:
    return (
        NRPositionOption("X", (DUTAxis.X,)),
        NRPositionOption("Y", (DUTAxis.Y,)),
        NRPositionOption("Z", (DUTAxis.Z,)),
        NRPositionOption("X->Y->Z", (DUTAxis.X, DUTAxis.Y, DUTAxis.Z)),
        NRPositionOption("Z->Y->X", (DUTAxis.Z, DUTAxis.Y, DUTAxis.X)),
    )


def _pol_options() -> tuple[NRPositionOption, ...]:
    return (
        NRPositionOption("H", (AntennaPol.H,)),
        NRPositionOption("V", (AntennaPol.V,)),
        NRPositionOption("H->V", (AntennaPol.H, AntennaPol.V)),
        NRPositionOption("V->H", (AntennaPol.V, AntennaPol.H)),
    )


def _available_channels(band: NRBand, bandwidth: float) -> tuple[TestChannel, ...]:
    channels: list[TestChannel] = []
    for channel in TestChannel:
        try:
            resolve_call_channel(band, bandwidth, channel)
        except ValueError:
            continue
        channels.append(channel)
    return tuple(channels)


def _default_parameters_for_band(band: NRBand) -> NRCaseParameters:
    bandwidth = get_supported_bandwidths(band)[0]
    channels = _available_channels(band, bandwidth)
    return NRCaseParameters(
        bandwidth=bandwidth,
        modulation=Modulation.QPSK,
        rb_allocation=RBAllocation.INNER_1RB_LEFT,
        test_channel=TestChannel.MID if TestChannel.MID in channels else channels[0],
        dut_ant_position=DUTAntPosition.LOWER,
    )


def _create_default_parameters() -> dict[NRBand, NRCaseParameters]:
    return {
        _band_from_number(band_number): _default_parameters_for_band(
            _band_from_number(band_number),
        )
        for group in BAND_GROUPS
        for band_number in group.bands
    }


def _create_default_group_settings() -> dict[str, NRGroupSettings]:
    return {
        group.key: NRGroupSettings(
            selected_test_types=tuple(
                option.test_type for option in _test_range_options_for_group(group.key)
            ),
            axis_sequence=(),
            antenna_pol_sequence=(),
        )
        for group in BAND_GROUPS
    }


class NRParameterDialog(QDialog):
    """Band별 TestCase 파라미터를 입력하는 보조 팝업."""

    def __init__(
        self,
        parameters_by_band: Mapping[NRBand, NRCaseParameters],
        group_settings: Mapping[str, NRGroupSettings] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("nrParameterDialog")
        self.setWindowTitle("NR Table")
        self._parameters_by_band = dict(parameters_by_band)
        self._group_settings = dict(group_settings or _create_default_group_settings())
        self._combo_by_cell: dict[tuple[NRBand, str], QComboBox] = {}
        self._preview_items: dict[tuple[NRBand, int], QTableWidgetItem] = {}
        self._test_range_checks: dict[tuple[str, TestType], QCheckBox] = {}
        self._axis_button_groups: dict[str, QButtonGroup] = {}
        self._pol_button_groups: dict[str, QButtonGroup] = {}
        self._setup_layout()
        self._apply_styles()

    def parameters_by_band(self) -> dict[NRBand, NRCaseParameters]:
        """표에 입력된 band별 파라미터를 반환한다."""

        parameters: dict[NRBand, NRCaseParameters] = {}
        for band in self._parameters_by_band:
            parameters[band] = NRCaseParameters(
                bandwidth=self._current_data(band, "bandwidth"),
                modulation=self._current_data(band, "modulation"),
                rb_allocation=self._current_data(band, "rb_allocation"),
                test_channel=self._current_data(band, "test_channel"),
                dut_ant_position=self._current_data(band, "dut_ant_position"),
            )
        return parameters

    def group_settings(self) -> dict[str, NRGroupSettings]:
        """표에 입력된 group별 Test 대역/Position 설정을 반환한다."""

        settings: dict[str, NRGroupSettings] = {}
        for group in BAND_GROUPS:
            settings[group.key] = NRGroupSettings(
                selected_test_types=self._selected_test_types(group.key),
                axis_sequence=self._selected_axis_sequence(group.key),
                antenna_pol_sequence=self._selected_pol_sequence(group.key),
            )
        return settings

    def _setup_layout(self) -> None:
        """첨부 Table 형태의 설정/미리보기 표를 배치한다."""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        self._table = QTableWidget(len(self._parameters_by_band), len(_PARAMETER_HEADERS), self)
        self._table.setObjectName("nrParameterTable")
        self._table.setHorizontalHeaderLabels(_PARAMETER_HEADERS)
        self._table.verticalHeader().setVisible(False)
        self._table.setAlternatingRowColors(False)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setShowGrid(True)

        row = 0
        for group in BAND_GROUPS:
            row = self._setup_group_rows(row, group.key, group.bands)

        self._apply_parameter_table_geometry()
        self._normalize_group_row_heights()
        self._fit_parameter_table_width()
        self._fit_parameter_table_height()
        layout.addWidget(self._table)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        button_box.setObjectName("nrParameterButtonBox")
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        self.resize(self.sizeHint())

    def _apply_parameter_table_geometry(self) -> None:
        """Table 컬럼 폭을 고정해 첨부표처럼 조밀하게 보이도록 맞춘다."""

        header = self._table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(40)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        for column, width in enumerate(_PARAMETER_COLUMN_WIDTHS):
            self._table.setColumnWidth(column, width)

    def _fit_parameter_table_width(self) -> None:
        """Table viewport가 컬럼 폭 합계만큼만 보이도록 폭을 맞춘다."""

        columns_width = sum(
            self._table.columnWidth(column)
            for column in range(self._table.columnCount())
        )
        table_width = columns_width + 2
        self._table.setFixedWidth(table_width)

    def _normalize_group_row_heights(self) -> None:
        """span 위젯 높이가 첫 Band 행에만 몰리지 않도록 그룹 행 높이를 맞춘다."""

        start_row = 0
        for group in BAND_GROUPS:
            row_count = len(group.bands)
            test_range_widget = self._table.cellWidget(start_row, _TEST_RANGE_COLUMN)
            position_widget = self._table.cellWidget(start_row, _POSITION_COLUMN)
            span_height = max(
                test_range_widget.sizeHint().height() if test_range_widget else 0,
                position_widget.sizeHint().height() if position_widget else 0,
            )
            row_height = max(
                _MIN_PARAMETER_ROW_HEIGHT,
                (span_height + row_count - 1) // row_count,
            )
            for row in range(start_row, start_row + row_count):
                self._table.setRowHeight(row, row_height)
            start_row += row_count

    def _fit_parameter_table_height(self) -> None:
        """Table viewport가 행 높이만큼만 보이도록 높이를 맞춘다."""

        rows_height = sum(
            self._table.rowHeight(row)
            for row in range(self._table.rowCount())
        )
        table_height = (
            self._table.horizontalHeader().sizeHint().height()
            + rows_height
            + (self._table.frameWidth() * 2)
            + 7
        )
        self._table.setFixedHeight(table_height)

    def _setup_group_rows(
        self,
        start_row: int,
        group_key: str,
        band_numbers: tuple[int, ...],
    ) -> int:
        """그룹 병합 셀과 해당 Band 행들을 구성한다."""

        row_count = len(band_numbers)
        group_title = _GROUP_TITLES[group_key]
        self._set_spanned_item(start_row, _GROUP_COLUMN, row_count, group_title)
        self._set_spanned_widget(
            start_row,
            _TEST_RANGE_COLUMN,
            row_count,
            self._create_test_range_widget(group_key),
        )
        self._set_spanned_widget(
            start_row,
            _POSITION_COLUMN,
            row_count,
            self._create_position_widget(group_key),
        )

        for offset, band_number in enumerate(band_numbers):
            band = _band_from_number(band_number)
            row = start_row + offset
            parameters = self._parameters_by_band[band]
            self._setup_band_row(row, band, parameters)
        return start_row + row_count

    def _set_spanned_item(
        self,
        row: int,
        column: int,
        row_count: int,
        text: str,
    ) -> None:
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self._table.setItem(row, column, item)
        self._table.setSpan(row, column, row_count, 1)

    def _set_spanned_widget(
        self,
        row: int,
        column: int,
        row_count: int,
        widget: QWidget,
    ) -> None:
        self._table.setCellWidget(row, column, widget)
        self._table.setSpan(row, column, row_count, 1)

    def _setup_band_row(
        self,
        row: int,
        band: NRBand,
        parameters: NRCaseParameters,
    ) -> None:
        """한 band에 해당하는 입력/미리보기 행을 구성한다."""

        band_item = self._create_center_item(_band_label(band))
        band_item.setData(Qt.ItemDataRole.UserRole, band)
        self._table.setItem(row, _BAND_COLUMN, band_item)
        self._table.setItem(
            row,
            _SCS_COLUMN,
            self._create_center_item(str(find_band_group(band).scs_khz)),
        )
        self._set_combo(
            row,
            _BANDWIDTH_COLUMN,
            band,
            "bandwidth",
            get_supported_bandwidths(band),
            parameters.bandwidth,
            text_formatter=_format_bandwidth,
        )
        self._set_combo(
            row,
            _MODULATION_COLUMN,
            band,
            "modulation",
            tuple(Modulation),
            parameters.modulation,
        )
        self._set_combo(
            row,
            _RB_ALLOCATION_COLUMN,
            band,
            "rb_allocation",
            _RB_ALLOCATION_OPTIONS,
            parameters.rb_allocation,
        )
        self._set_combo(
            row,
            _CHANNEL_COLUMN,
            band,
            "test_channel",
            _available_channels(band, parameters.bandwidth),
            parameters.test_channel,
        )
        self._set_combo(
            row,
            _EUT_ANT_COLUMN,
            band,
            "dut_ant_position",
            _DUT_ANT_POSITION_OPTIONS,
            parameters.dut_ant_position,
        )
        for column in (
            _NARFCN_COLUMN,
            _FREQUENCY_COLUMN,
            _RB_SIZE_COLUMN,
            _RB_OFFSET_COLUMN,
        ):
            item = self._create_center_item("")
            self._table.setItem(row, column, item)
            self._preview_items[(band, column)] = item
        self._connect_row_updates(band)
        self._refresh_row_preview(band)

    def _create_center_item(self, text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item

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
        self._fill_combo(combo, values, current_value, text_formatter=text_formatter)
        self._table.setCellWidget(row, column, combo)
        self._combo_by_cell[(band, field_name)] = combo

    def _fill_combo(
        self,
        combo: QComboBox,
        values: tuple[object, ...],
        current_value: object | None,
        *,
        text_formatter: Callable[[object], str] | None = None,
    ) -> None:
        with QSignalBlocker(combo):
            combo.clear()
            for value in values:
                if text_formatter is None:
                    text = getattr(value, "value", str(value))
                else:
                    text = text_formatter(value)
                combo.addItem(str(text), value)
            index = combo.findData(current_value)
            combo.setCurrentIndex(index if index >= 0 else 0)

    def _connect_row_updates(self, band: NRBand) -> None:
        self._combo_by_cell[(band, "bandwidth")].currentIndexChanged.connect(
            lambda index, selected_band=band: self._on_bandwidth_changed(selected_band),
        )
        for field_name in ("modulation", "rb_allocation", "test_channel"):
            self._combo_by_cell[(band, field_name)].currentIndexChanged.connect(
                lambda index, selected_band=band: self._refresh_row_preview(selected_band),
            )

    def _on_bandwidth_changed(self, band: NRBand) -> None:
        """BW 변경 시 Channel 후보와 미리보기 값을 갱신한다."""

        bandwidth = self._current_data(band, "bandwidth")
        channel_combo = self._combo_by_cell[(band, "test_channel")]
        current_channel = channel_combo.currentData()
        self._fill_combo(
            channel_combo,
            _available_channels(band, bandwidth),
            current_channel,
        )
        self._refresh_row_preview(band)

    def _refresh_row_preview(self, band: NRBand) -> None:
        """Band 행의 자동 계산 컬럼을 갱신한다."""

        bandwidth = self._current_data(band, "bandwidth")
        rb_allocation = self._current_data(band, "rb_allocation")
        channel = self._current_data(band, "test_channel")
        try:
            narfcn = resolve_call_channel(band, bandwidth, channel)
            frequency = resolve_target_frequency_mhz(band, bandwidth, channel)
            preview_case = TestCase(
                band=band,
                bandwidth=bandwidth,
                test_type=_test_range_options_for_group(_group_key_for_band(band))[0].test_type,
                modulation=self._current_data(band, "modulation"),
                rb_allocation=rb_allocation,
                test_channel=channel,
                antenna_pol=AntennaPol.H,
                dut_axis=DUTAxis.X,
                dut_ant_position=self._current_data(band, "dut_ant_position"),
            )
            values = {
                _NARFCN_COLUMN: str(narfcn),
                _FREQUENCY_COLUMN: _format_number(frequency),
                _RB_SIZE_COLUMN: str(preview_case.rb_size),
                _RB_OFFSET_COLUMN: str(preview_case.rb_offset),
            }
        except ValueError:
            values = {
                _NARFCN_COLUMN: "",
                _FREQUENCY_COLUMN: "",
                _RB_SIZE_COLUMN: "",
                _RB_OFFSET_COLUMN: "",
            }
        for column, value in values.items():
            self._preview_items[(band, column)].setText(value)

    def _create_test_range_widget(self, group_key: str) -> QWidget:
        widget = QWidget(self._table)
        widget.setObjectName(f"nrTestRangePanel_{group_key}")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(3)
        selected_types = set(self._group_settings[group_key].selected_test_types)

        for option in _test_range_options_for_group(group_key):
            checkbox = QCheckBox(option.label, widget)
            checkbox.setObjectName(f"nrRangeCheck_{group_key}_{option.test_type.value}")
            checkbox.setChecked(option.test_type in selected_types)
            self._test_range_checks[(group_key, option.test_type)] = checkbox
            layout.addWidget(checkbox)
        layout.addStretch(1)
        return widget

    def _create_position_widget(self, group_key: str) -> QWidget:
        widget = QWidget(self._table)
        widget.setObjectName(f"nrPositionPanel_{group_key}")
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(10)

        axis_layout = QVBoxLayout()
        axis_layout.setContentsMargins(0, 0, 0, 0)
        axis_layout.setSpacing(3)
        axis_layout.addWidget(self._create_position_section_label("Axis", widget))
        axis_group = self._create_exclusive_position_group(
            group_key,
            "Axis",
            _axis_options(),
            self._group_settings[group_key].axis_sequence,
            widget,
            axis_layout,
        )
        axis_layout.addStretch(1)

        pol_layout = QVBoxLayout()
        pol_layout.setContentsMargins(0, 0, 0, 0)
        pol_layout.setSpacing(3)
        pol_layout.addWidget(self._create_position_section_label("Pol", widget))
        pol_group = self._create_exclusive_position_group(
            group_key,
            "Pol",
            _pol_options(),
            self._group_settings[group_key].antenna_pol_sequence,
            widget,
            pol_layout,
        )
        pol_layout.addStretch(1)

        layout.addLayout(axis_layout, 1)
        layout.addLayout(pol_layout, 1)
        self._axis_button_groups[group_key] = axis_group
        self._pol_button_groups[group_key] = pol_group
        return widget

    def _create_position_section_label(self, text: str, parent: QWidget) -> QLabel:
        label = QLabel(text, parent)
        label.setProperty("nrPositionSection", True)
        return label

    def _create_exclusive_position_group(
        self,
        group_key: str,
        kind: str,
        options: tuple[NRPositionOption, ...],
        selected_values: tuple[object, ...],
        parent: QWidget,
        layout: QVBoxLayout,
    ) -> QButtonGroup:
        button_group = QButtonGroup(parent)
        button_group.setExclusive(True)
        selected_tuple = tuple(selected_values)
        for index, option in enumerate(options):
            checkbox = QCheckBox(option.label, parent)
            checkbox.setObjectName(
                f"nr{kind}Check_{group_key}_{_option_object_suffix(option.label)}",
            )
            checkbox.setProperty("positionValues", option.values)
            checkbox.setChecked(tuple(option.values) == selected_tuple)
            checkbox.setMinimumWidth(_POSITION_OPTION_MIN_WIDTH)
            button_group.addButton(checkbox, index)
            layout.addWidget(checkbox)
        return button_group

    def _selected_test_types(self, group_key: str) -> tuple[TestType, ...]:
        selected: list[TestType] = []
        for option in _test_range_options_for_group(group_key):
            checkbox = self._test_range_checks[(group_key, option.test_type)]
            if checkbox.isChecked():
                selected.append(option.test_type)
        return tuple(selected)

    def _selected_axis_sequence(self, group_key: str) -> tuple[DUTAxis, ...]:
        button = self._axis_button_groups[group_key].checkedButton()
        if button is None:
            return ()
        return tuple(button.property("positionValues"))

    def _selected_pol_sequence(self, group_key: str) -> tuple[AntennaPol, ...]:
        button = self._pol_button_groups[group_key].checkedButton()
        if button is None:
            return ()
        return tuple(button.property("positionValues"))

    def _current_data(self, band: NRBand, field_name: str) -> object:
        return self._combo_by_cell[(band, field_name)].currentData()

    def _apply_styles(self) -> None:
        """NR Table 팝업 전용 스타일을 적용한다."""

        self.setStyleSheet(
            """
            QTableWidget#nrParameterTable {
                border: 1px solid #2f5aa8;
                gridline-color: #111111;
                background: #ffffff;
                color: #111111;
                alternate-background-color: #ffffff;
            }

            QTableWidget#nrParameterTable::item {
                color: #111111;
            }

            QTableWidget#nrParameterTable QHeaderView::section {
                background: #f5f5f5;
                color: #111111;
                border: 0;
                border-right: 1px solid #111111;
                border-bottom: 1px solid #111111;
                padding: 4px 6px;
            }

            QTableWidget#nrParameterTable QWidget {
                background: #ffffff;
                color: #111111;
            }

            QComboBox {
                background: #ffffff;
                color: #111111;
                border: 1px solid #9eb4d0;
                padding: 2px 6px;
            }

            QCheckBox {
                color: #111111;
                spacing: 5px;
            }

            QCheckBox::indicator {
                width: 14px;
                height: 14px;
                border: 1px solid #2f5aa8;
                background: #ffffff;
            }

            QCheckBox::indicator:checked {
                background: #5a9bd5;
            }

            QLabel[nrPositionSection="true"] {
                font-weight: 600;
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

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        parameters_by_band: Mapping[NRBand, NRCaseParameters] | None = None,
        group_settings: Mapping[str, NRGroupSettings] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("nrSelectDialog")
        self.setWindowTitle("NR Select")
        self._band_checks: dict[NRBand, QCheckBox] = {}
        self._parameters_by_band = dict(parameters_by_band or _create_default_parameters())
        self._group_settings = dict(group_settings or _create_default_group_settings())
        self._setup_layout()
        self._apply_styles()

    @property
    def parameters_by_band(self) -> dict[NRBand, NRCaseParameters]:
        """현재 저장된 band별 TestCase 파라미터를 반환한다."""

        return dict(self._parameters_by_band)

    @property
    def group_settings(self) -> dict[str, NRGroupSettings]:
        """현재 저장된 group별 Test 대역/Position 설정을 반환한다."""

        return dict(self._group_settings)

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
        toggle_button.clicked.connect(
            lambda checked=False, key=group_key: self.on_group_toggle_clicked(key),
        )
        layout.addWidget(toggle_button)
        return group

    def _create_band_check_row(self, parent: QWidget, band: NRBand) -> QWidget:
        """Band 라벨 오른쪽에 체크박스를 둔 행을 만든다."""

        row = QWidget(parent)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        label = QLabel(f"B{band.value[1:]}", row)
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

        dialog = NRParameterDialog(
            self._parameters_by_band,
            self._group_settings,
            self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._parameters_by_band = dialog.parameters_by_band()
            self._group_settings = dialog.group_settings()

    def on_add_clicked(self) -> None:
        """선택한 Band와 Table 파라미터로 TestCase를 생성한다."""

        selected_bands = self.selected_bands()
        if not selected_bands:
            QMessageBox.warning(self, "NR Select", "선택된 Band가 없습니다.")
            return

        try:
            cases = self._build_test_cases(selected_bands)
        except ValueError as exc:
            QMessageBox.warning(self, "NR Select", str(exc))
            return

        self.test_cases_created.emit(cases)
        self.accept()

    def _build_test_cases(self, bands: list[NRBand]) -> list[TestCase]:
        """선택 Band/Test 대역/Position 조합을 TestCase 목록으로 펼친다."""

        self._validate_group_settings_for_bands(bands)
        cases: list[TestCase] = []
        for band in bands:
            group_key = _group_key_for_band(band)
            group_settings = self._group_settings[group_key]
            band_parameters = self._parameters_by_band[band]
            for test_type in group_settings.selected_test_types:
                for dut_axis in group_settings.axis_sequence:
                    for antenna_pol in group_settings.antenna_pol_sequence:
                        case = TestCase(
                            band=band,
                            bandwidth=band_parameters.bandwidth,
                            test_type=test_type,
                            modulation=band_parameters.modulation,
                            rb_allocation=band_parameters.rb_allocation,
                            test_channel=band_parameters.test_channel,
                            antenna_pol=antenna_pol,
                            dut_axis=dut_axis,
                            dut_ant_position=band_parameters.dut_ant_position,
                        )
                        resolve_call_channel(case.band, case.bandwidth, case.test_channel)
                        cases.append(case)
        return cases

    def _validate_group_settings_for_bands(self, bands: list[NRBand]) -> None:
        selected_group_keys = {_group_key_for_band(band) for band in bands}
        for group_key in selected_group_keys:
            settings = self._group_settings[group_key]
            group_title = _GROUP_TITLES[group_key]
            if not settings.selected_test_types:
                raise ValueError(f"{group_title} Test 대역을 선택하세요.")
            if not settings.axis_sequence:
                raise ValueError(f"{group_title} Axis Position을 선택하세요.")
            if not settings.antenna_pol_sequence:
                raise ValueError(f"{group_title} Pol Position을 선택하세요.")

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
