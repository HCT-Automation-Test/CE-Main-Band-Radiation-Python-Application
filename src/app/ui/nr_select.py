"""NR Test Case 선택 팝업."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
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
    Generation,
    LTEBand,
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
from app.models.nsa_anchor import SUPPORTED_NSA_ANCHOR_BANDS
from app.models.supported_bandwidths import get_supported_bandwidths
from app.models.test_case import TestCase

_GROUP_TITLES: dict[str, str] = {
    "lb": "LB",
    "mhb_fdd": "MHB_FDD",
    "mhb_tdd": "MHB_TDD",
    "uhb_tdd": "UHB_TDD",
}

_SA_PARAMETER_HEADERS: tuple[str, ...] = (
    "",
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

_NSA_PARAMETER_HEADERS: tuple[str, ...] = (
    *_SA_PARAMETER_HEADERS[:3],
    "LTE Anchor Band",
    *_SA_PARAMETER_HEADERS[3:],
)

_GROUP_COLUMN = 0
_BAND_SELECT_COLUMN = 1
_BAND_COLUMN = 2
_ANCHOR_COLUMN = 3
_SCS_COLUMN = 3
_BANDWIDTH_COLUMN = 4
_MODULATION_COLUMN = 5
_RB_ALLOCATION_COLUMN = 6
_CHANNEL_COLUMN = 7
_EUT_ANT_COLUMN = 8
_NARFCN_COLUMN = 9
_FREQUENCY_COLUMN = 10
_RB_SIZE_COLUMN = 11
_RB_OFFSET_COLUMN = 12
_TEST_RANGE_COLUMN = 13
_POSITION_COLUMN = 14
_MIN_PARAMETER_ROW_HEIGHT = 30
_POSITION_OPTION_MIN_WIDTH = 86
_SA_PARAMETER_COLUMN_WIDTHS: tuple[int, ...] = (
    76,
    40,
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
_NSA_PARAMETER_COLUMN_WIDTHS: tuple[int, ...] = (
    *_SA_PARAMETER_COLUMN_WIDTHS[:3],
    130,
    *_SA_PARAMETER_COLUMN_WIDTHS[3:],
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


@dataclass(frozen=True)
class NRSelectState:
    """Generation별 NR 통합 생성 화면 상태."""

    generation: Generation
    selected_bands: tuple[NRBand, ...]
    parameters_by_band: dict[NRBand, NRCaseParameters]
    group_settings: dict[str, NRGroupSettings]
    anchor_bands_by_band: dict[NRBand, LTEBand]


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


class _BandSelectionHeader(QHeaderView):
    """Band 선택 열에 전체 선택 체크박스를 배치하는 헤더."""

    def __init__(self, parent: QTableWidget) -> None:
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.checkbox = QCheckBox(self.viewport())
        self.checkbox.setObjectName("nrBandMasterCheck")
        self.checkbox.setToolTip("전체 NR Band 선택/해제")
        self.sectionResized.connect(self._update_checkbox_geometry)
        self.geometriesChanged.connect(self._update_checkbox_geometry)

    def _update_checkbox_geometry(self) -> None:
        section_x = self.sectionViewportPosition(_BAND_SELECT_COLUMN)
        section_width = self.sectionSize(_BAND_SELECT_COLUMN)
        size = self.checkbox.sizeHint()
        self.checkbox.setGeometry(
            section_x + max(0, (section_width - size.width()) // 2),
            max(0, (self.height() - size.height()) // 2),
            size.width(),
            size.height(),
        )

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        self._update_checkbox_geometry()


class NRSelectDialog(QDialog):
    """NR Band 선택과 파라미터 입력을 한 화면에서 처리한다."""

    test_cases_created = Signal(list)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        generation: Generation = Generation.NR_SA,
        state: NRSelectState | None = None,
    ) -> None:
        super().__init__(parent)
        if generation not in {Generation.NR_SA, Generation.NR_NSA}:
            raise ValueError(f"Unsupported NR generation: {generation.value}")
        if state is not None and state.generation is not generation:
            raise ValueError(
                "NRSelectState generation does not match dialog generation: "
                f"{state.generation.value} != {generation.value}"
            )

        self.setObjectName("nrSelectDialog")
        self.setWindowTitle(f"{'NR SA' if generation is Generation.NR_SA else 'NR NSA'} Test Case")
        self._generation = generation
        self._parameters_by_band = _create_default_parameters()
        self._group_settings = _create_default_group_settings()
        self._selected_bands: set[NRBand] = set()
        self._anchor_bands_by_band = {
            band: SUPPORTED_NSA_ANCHOR_BANDS[0]
            for band in self._parameters_by_band
        }
        if state is not None:
            self._parameters_by_band.update(state.parameters_by_band)
            self._group_settings.update(state.group_settings)
            self._selected_bands.update(state.selected_bands)
            self._anchor_bands_by_band.update(state.anchor_bands_by_band)

        self._band_checks: dict[NRBand, QCheckBox] = {}
        self._group_checks: dict[str, QCheckBox] = {}
        self._combo_by_cell: dict[tuple[NRBand, str], QComboBox] = {}
        self._anchor_combo_by_band: dict[NRBand, QComboBox] = {}
        self._preview_items: dict[tuple[NRBand, int], QTableWidgetItem] = {}
        self._test_range_checks: dict[tuple[str, TestType], QCheckBox] = {}
        self._axis_button_groups: dict[str, QButtonGroup] = {}
        self._pol_button_groups: dict[str, QButtonGroup] = {}
        self._column_offset = 1 if generation is Generation.NR_NSA else 0
        self._setup_layout()
        self._apply_styles()
        self._sync_aggregate_checks()

    @property
    def generation(self) -> Generation:
        """이 화면에 고정된 NR Generation을 반환한다."""

        return self._generation

    @property
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

    @property
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

    @property
    def anchor_bands_by_band(self) -> dict[NRBand, LTEBand]:
        """NSA 화면의 NR Band별 Anchor 선택값을 반환한다."""

        if self._generation is Generation.NR_SA:
            return {}
        return {
            band: combo.currentData()
            for band, combo in self._anchor_combo_by_band.items()
        }

    @property
    def state(self) -> NRSelectState:
        """현재 화면 값을 다음 진입에서 복원할 상태로 반환한다."""

        return NRSelectState(
            generation=self._generation,
            selected_bands=tuple(self.selected_bands()),
            parameters_by_band=self.parameters_by_band,
            group_settings=self.group_settings,
            anchor_bands_by_band=self.anchor_bands_by_band,
        )

    def selected_bands(self) -> list[NRBand]:
        """선택된 Band를 화면 표시 순서로 반환한다."""

        return [
            band
            for group in BAND_GROUPS
            for band in (_band_from_number(number) for number in group.bands)
            if self._band_checks[band].isChecked()
        ]

    def _setup_layout(self) -> None:
        """첨부 Table 형태의 설정/미리보기 표를 배치한다."""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        headers = (
            _NSA_PARAMETER_HEADERS
            if self._generation is Generation.NR_NSA
            else _SA_PARAMETER_HEADERS
        )
        self._table = QTableWidget(len(self._parameters_by_band), len(headers), self)
        self._table.setObjectName("nrParameterTable")
        header = _BandSelectionHeader(self._table)
        self._table.setHorizontalHeader(header)
        self._master_check = header.checkbox
        self._table.setHorizontalHeaderLabels(headers)
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
        self._master_check.clicked.connect(self.on_master_check_clicked)
        layout.addWidget(self._table)

        button_layout = QHBoxLayout()
        cancel_button = QPushButton("Cancel", self)
        cancel_button.setObjectName("nrCancelButton")
        cancel_button.setAutoDefault(False)
        cancel_button.clicked.connect(self.reject)
        add_button = QPushButton("Add", self)
        add_button.setObjectName("nrAddButton")
        add_button.setDefault(True)
        add_button.setAutoDefault(True)
        add_button.clicked.connect(self.on_add_clicked)
        button_layout.addWidget(cancel_button)
        button_layout.addStretch(1)
        button_layout.addWidget(add_button)
        layout.addLayout(button_layout)
        self.resize(self.sizeHint())

    def _apply_parameter_table_geometry(self) -> None:
        """Table 컬럼 폭을 고정해 첨부표처럼 조밀하게 보이도록 맞춘다."""

        header = self._table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(40)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        widths = (
            _NSA_PARAMETER_COLUMN_WIDTHS
            if self._generation is Generation.NR_NSA
            else _SA_PARAMETER_COLUMN_WIDTHS
        )
        for column, width in enumerate(widths):
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
            test_range_widget = self._table.cellWidget(
                start_row,
                self._parameter_column(_TEST_RANGE_COLUMN),
            )
            position_widget = self._table.cellWidget(
                start_row,
                self._parameter_column(_POSITION_COLUMN),
            )
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
        self._set_spanned_widget(
            start_row,
            _GROUP_COLUMN,
            row_count,
            self._create_group_widget(group_key),
        )
        self._set_spanned_widget(
            start_row,
            self._parameter_column(_TEST_RANGE_COLUMN),
            row_count,
            self._create_test_range_widget(group_key),
        )
        self._set_spanned_widget(
            start_row,
            self._parameter_column(_POSITION_COLUMN),
            row_count,
            self._create_position_widget(group_key),
        )

        for offset, band_number in enumerate(band_numbers):
            band = _band_from_number(band_number)
            row = start_row + offset
            parameters = self._parameters_by_band[band]
            self._setup_band_row(row, band, parameters)
        return start_row + row_count

    def _parameter_column(self, base_column: int) -> int:
        """NSA Anchor 열 추가 여부를 반영한 실제 컬럼 인덱스를 반환한다."""

        return base_column + self._column_offset

    def _create_group_widget(self, group_key: str) -> QWidget:
        widget = QWidget(self._table)
        widget.setObjectName(f"nrBandGroup_{group_key}")
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(5)
        label = QLabel(_GROUP_TITLES[group_key], widget)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        checkbox = QCheckBox(widget)
        checkbox.setObjectName(f"nrBandGroupCheck_{group_key}")
        checkbox.clicked.connect(
            lambda checked=False, key=group_key: self.on_group_check_clicked(
                key,
                checked,
            ),
        )
        self._group_checks[group_key] = checkbox
        layout.addStretch(1)
        layout.addWidget(label)
        layout.addWidget(checkbox)
        layout.addStretch(1)
        return widget

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

        band_check = QCheckBox(self._table)
        band_check.setObjectName(f"nrBandCheck_{band.value}")
        band_check.setCursor(Qt.CursorShape.PointingHandCursor)
        band_check.setChecked(band in self._selected_bands)
        band_check.stateChanged.connect(self._sync_aggregate_checks)
        check_panel = QWidget(self._table)
        check_layout = QHBoxLayout(check_panel)
        check_layout.setContentsMargins(0, 0, 0, 0)
        check_layout.addStretch(1)
        check_layout.addWidget(band_check)
        check_layout.addStretch(1)
        self._table.setCellWidget(row, _BAND_SELECT_COLUMN, check_panel)
        self._band_checks[band] = band_check

        band_item = self._create_center_item(_band_label(band))
        band_item.setData(Qt.ItemDataRole.UserRole, band)
        self._table.setItem(row, _BAND_COLUMN, band_item)
        if self._generation is Generation.NR_NSA:
            self._set_anchor_combo(row, band)
        self._table.setItem(
            row,
            self._parameter_column(_SCS_COLUMN),
            self._create_center_item(str(find_band_group(band).scs_khz)),
        )
        self._set_combo(
            row,
            self._parameter_column(_BANDWIDTH_COLUMN),
            band,
            "bandwidth",
            get_supported_bandwidths(band),
            parameters.bandwidth,
            text_formatter=_format_bandwidth,
        )
        self._set_combo(
            row,
            self._parameter_column(_MODULATION_COLUMN),
            band,
            "modulation",
            tuple(Modulation),
            parameters.modulation,
        )
        self._set_combo(
            row,
            self._parameter_column(_RB_ALLOCATION_COLUMN),
            band,
            "rb_allocation",
            _RB_ALLOCATION_OPTIONS,
            parameters.rb_allocation,
        )
        self._set_combo(
            row,
            self._parameter_column(_CHANNEL_COLUMN),
            band,
            "test_channel",
            _available_channels(band, parameters.bandwidth),
            parameters.test_channel,
        )
        self._set_combo(
            row,
            self._parameter_column(_EUT_ANT_COLUMN),
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
            column = self._parameter_column(column)
            item = self._create_center_item("")
            self._table.setItem(row, column, item)
            self._preview_items[(band, column)] = item
        self._connect_row_updates(band)
        self._refresh_row_preview(band)

    def _set_anchor_combo(self, row: int, band: NRBand) -> None:
        combo = QComboBox(self._table)
        combo.setObjectName(f"nrAnchorBand_{band.value}")
        for anchor_band in SUPPORTED_NSA_ANCHOR_BANDS:
            combo.addItem(anchor_band.value, anchor_band)
        current_anchor = self._anchor_bands_by_band[band]
        index = combo.findData(current_anchor)
        combo.setCurrentIndex(index if index >= 0 else 0)
        self._table.setCellWidget(row, _ANCHOR_COLUMN, combo)
        self._anchor_combo_by_band[band] = combo

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
                generation=self._generation,
                band=band,
                anchor_band=(
                    self._anchor_combo_by_band[band].currentData()
                    if self._generation is Generation.NR_NSA
                    else None
                ),
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
                self._parameter_column(_NARFCN_COLUMN): str(narfcn),
                self._parameter_column(_FREQUENCY_COLUMN): _format_number(frequency),
                self._parameter_column(_RB_SIZE_COLUMN): str(preview_case.rb_size),
                self._parameter_column(_RB_OFFSET_COLUMN): str(preview_case.rb_offset),
            }
        except ValueError:
            values = {
                self._parameter_column(_NARFCN_COLUMN): "",
                self._parameter_column(_FREQUENCY_COLUMN): "",
                self._parameter_column(_RB_SIZE_COLUMN): "",
                self._parameter_column(_RB_OFFSET_COLUMN): "",
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

    def on_master_check_clicked(self, checked: bool) -> None:
        """전체 NR Band 선택 상태를 변경한다."""

        for checkbox in self._band_checks.values():
            checkbox.setChecked(checked)
        self._sync_aggregate_checks()

    def on_group_check_clicked(self, group_key: str, checked: bool) -> None:
        """선택한 NR Band Group의 체크 상태를 변경한다."""

        group = next(candidate for candidate in BAND_GROUPS if candidate.key == group_key)
        for band_number in group.bands:
            self._band_checks[_band_from_number(band_number)].setChecked(checked)
        self._sync_aggregate_checks()

    def _sync_aggregate_checks(self, state: int = 0) -> None:
        del state
        for group in BAND_GROUPS:
            bands = [_band_from_number(number) for number in group.bands]
            selected_count = sum(self._band_checks[band].isChecked() for band in bands)
            self._set_aggregate_check_state(
                self._group_checks[group.key],
                selected_count,
                len(bands),
            )
        selected_count = sum(
            checkbox.isChecked()
            for checkbox in self._band_checks.values()
        )
        self._set_aggregate_check_state(
            self._master_check,
            selected_count,
            len(self._band_checks),
        )

    def _set_aggregate_check_state(
        self,
        checkbox: QCheckBox,
        selected_count: int,
        total_count: int,
    ) -> None:
        with QSignalBlocker(checkbox):
            is_partial = 0 < selected_count < total_count
            checkbox.setTristate(is_partial)
            if selected_count == 0:
                checkbox.setCheckState(Qt.CheckState.Unchecked)
            elif selected_count == total_count:
                checkbox.setCheckState(Qt.CheckState.Checked)
            else:
                checkbox.setCheckState(Qt.CheckState.PartiallyChecked)

    def on_add_clicked(self) -> None:
        """현재 화면 선택으로 NR TestCase를 생성한다."""

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
        self._validate_group_settings_for_bands(bands)
        parameters_by_band = self.parameters_by_band
        settings_by_group = self.group_settings
        anchors_by_band = self.anchor_bands_by_band
        cases: list[TestCase] = []
        for band in bands:
            settings = settings_by_group[_group_key_for_band(band)]
            parameters = parameters_by_band[band]
            for test_type in settings.selected_test_types:
                for axis in settings.axis_sequence:
                    for pol in settings.antenna_pol_sequence:
                        cases.append(
                            TestCase(
                                generation=self._generation,
                                band=band,
                                anchor_band=(
                                    anchors_by_band[band]
                                    if self._generation is Generation.NR_NSA
                                    else None
                                ),
                                bandwidth=parameters.bandwidth,
                                test_type=test_type,
                                modulation=parameters.modulation,
                                rb_allocation=parameters.rb_allocation,
                                test_channel=parameters.test_channel,
                                antenna_pol=pol,
                                dut_axis=axis,
                                dut_ant_position=parameters.dut_ant_position,
                            ),
                        )
        return cases

    def _validate_group_settings_for_bands(self, bands: list[NRBand]) -> None:
        settings_by_group = self.group_settings
        selected_group_keys = {_group_key_for_band(band) for band in bands}
        for group in BAND_GROUPS:
            if group.key not in selected_group_keys:
                continue
            settings = settings_by_group[group.key]
            group_title = _GROUP_TITLES[group.key]
            if not settings.selected_test_types:
                raise ValueError(f"{group_title} Test 대역을 선택하세요.")
            if not settings.axis_sequence:
                raise ValueError(f"{group_title} Axis Position을 선택하세요.")
            if not settings.antenna_pol_sequence:
                raise ValueError(f"{group_title} Pol Position을 선택하세요.")

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

            QPushButton#nrCancelButton,
            QPushButton#nrAddButton {
                background: #fbfbfb;
                color: #111111;
                border: 1px solid #2f5aa8;
                padding: 5px 12px;
            }
            """
        )
