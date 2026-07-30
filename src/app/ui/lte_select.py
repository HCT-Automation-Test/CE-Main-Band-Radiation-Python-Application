"""LTE Test Case 선택과 파라미터 입력을 제공하는 통합 팝업."""
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

from app.models.enums import (
    AntennaPol,
    DUTAntPosition,
    DUTAxis,
    Generation,
    LTEBand,
    LTERBAllocation,
    Modulation,
    TestChannel,
    TestType,
)
from app.models.lte_band_group import LTE_BAND_GROUPS
from app.models.lte_supported_bandwidths import get_lte_supported_bandwidths
from app.models.test_case import TestCase

_GROUP_TITLES: dict[str, str] = {
    "lb": "LB",
    "mhb_fdd": "MHB_FDD",
    "mhb_tdd": "MHB_TDD",
}

_TABLE_HEADERS: tuple[str, ...] = (
    "",
    "",
    "LTE Band",
    "BW",
    "RB Allocation",
    "Channel",
    "EUT ANT",
    "ARFCN",
    "Frequency",
    "RB Size",
    "RB Offset",
    "Test 대역",
    "Position",
)

_GROUP_COLUMN = 0
_BAND_SELECT_COLUMN = 1
_BAND_COLUMN = 2
_BANDWIDTH_COLUMN = 3
_RB_ALLOCATION_COLUMN = 4
_CHANNEL_COLUMN = 5
_EUT_ANT_COLUMN = 6
_ARFCN_COLUMN = 7
_FREQUENCY_COLUMN = 8
_RB_SIZE_COLUMN = 9
_RB_OFFSET_COLUMN = 10
_TEST_RANGE_COLUMN = 11
_POSITION_COLUMN = 12
_MIN_ROW_HEIGHT = 30
_POSITION_OPTION_MIN_WIDTH = 86
_COLUMN_WIDTHS: tuple[int, ...] = (
    96,
    40,
    68,
    60,
    104,
    72,
    78,
    76,
    84,
    66,
    74,
    105,
    210,
)
_DUT_ANT_POSITION_OPTIONS: tuple[DUTAntPosition, ...] = (
    DUTAntPosition.LOWER,
    DUTAntPosition.UPPER,
)


@dataclass(frozen=True)
class LTETestRangeOption:
    """그룹별 Test 대역 선택 항목."""

    label: str
    test_type: TestType


@dataclass(frozen=True)
class LTEPositionOption:
    """Axis 또는 Pol 단일/순차 선택 항목."""

    label: str
    values: tuple[DUTAxis, ...] | tuple[AntennaPol, ...]


@dataclass(frozen=True)
class LTECaseParameters:
    """LTE Band별 사용자 선택 파라미터."""

    bandwidth: float
    rb_allocation: LTERBAllocation
    test_channel: TestChannel
    dut_ant_position: DUTAntPosition


@dataclass(frozen=True)
class LTEGroupSettings:
    """LTE Band Group별 Test 대역과 Position 설정."""

    selected_test_types: tuple[TestType, ...]
    axis_sequence: tuple[DUTAxis, ...]
    antenna_pol_sequence: tuple[AntennaPol, ...]


def _format_number(value: float | int) -> str:
    return format(float(value), ".15g")


def _field_object_suffix(field_name: str) -> str:
    return "".join(part.capitalize() for part in field_name.split("_"))


def _option_object_suffix(label: str) -> str:
    return (
        label.replace("->", "_to_")
        .replace("-", "_")
        .replace("/", "_")
        .replace(" ", "")
    )


def _group_key_for_band(band: LTEBand) -> str:
    for group in LTE_BAND_GROUPS:
        if band in group.bands:
            return group.key
    raise ValueError(f"Unknown LTE band: {band.value}")


def _test_range_options_for_group(
    group_key: str,
) -> tuple[LTETestRangeOption, ...]:
    if group_key == "lb":
        return (
            LTETestRangeOption("30M-1G", TestType.INBAND),
            LTETestRangeOption("1-12.75G", TestType.HARMONIC),
        )
    return (
        LTETestRangeOption("30M-1G", TestType.BILOG),
        LTETestRangeOption("1-3G", TestType.INBAND),
        LTETestRangeOption("3-12.75G", TestType.HARMONIC),
    )


def _axis_options() -> tuple[LTEPositionOption, ...]:
    return (
        LTEPositionOption("X", (DUTAxis.X,)),
        LTEPositionOption("Y", (DUTAxis.Y,)),
        LTEPositionOption("Z", (DUTAxis.Z,)),
        LTEPositionOption("X->Y->Z", (DUTAxis.X, DUTAxis.Y, DUTAxis.Z)),
        LTEPositionOption("Z->Y->X", (DUTAxis.Z, DUTAxis.Y, DUTAxis.X)),
    )


def _pol_options() -> tuple[LTEPositionOption, ...]:
    return (
        LTEPositionOption("H", (AntennaPol.H,)),
        LTEPositionOption("V", (AntennaPol.V,)),
        LTEPositionOption("H->V", (AntennaPol.H, AntennaPol.V)),
        LTEPositionOption("V->H", (AntennaPol.V, AntennaPol.H)),
    )


def _default_parameters_for_band(band: LTEBand) -> LTECaseParameters:
    return LTECaseParameters(
        bandwidth=get_lte_supported_bandwidths(band)[0],
        rb_allocation=LTERBAllocation.LOW,
        test_channel=TestChannel.MID,
        dut_ant_position=DUTAntPosition.LOWER,
    )


def _create_default_parameters() -> dict[LTEBand, LTECaseParameters]:
    return {
        band: _default_parameters_for_band(band)
        for group in LTE_BAND_GROUPS
        for band in group.bands
    }


def _create_default_group_settings() -> dict[str, LTEGroupSettings]:
    return {
        group.key: LTEGroupSettings(
            selected_test_types=tuple(
                option.test_type
                for option in _test_range_options_for_group(group.key)
            ),
            axis_sequence=(),
            antenna_pol_sequence=(),
        )
        for group in LTE_BAND_GROUPS
    }


class _BandSelectionHeader(QHeaderView):
    """Band 선택 열에 전체 선택 체크박스를 배치하는 헤더."""

    def __init__(self, parent: QTableWidget) -> None:
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.checkbox = QCheckBox(self.viewport())
        self.checkbox.setObjectName("lteBandMasterCheck")
        self.checkbox.setToolTip("전체 LTE Band 선택/해제")
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


class LTESelectDialog(QDialog):
    """LTE Band 선택과 파라미터 입력을 한 화면에서 처리한다."""

    test_cases_created = Signal(list)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        parameters_by_band: Mapping[LTEBand, LTECaseParameters] | None = None,
        group_settings: Mapping[str, LTEGroupSettings] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("lteSelectDialog")
        self.setWindowTitle("LTE Test Case")
        self._parameters_by_band = _create_default_parameters()
        self._parameters_by_band.update(parameters_by_band or {})
        self._group_settings = _create_default_group_settings()
        self._group_settings.update(group_settings or {})
        self._band_checks: dict[LTEBand, QCheckBox] = {}
        self._group_checks: dict[str, QCheckBox] = {}
        self._combo_by_cell: dict[tuple[LTEBand, str], QComboBox] = {}
        self._preview_items: dict[tuple[LTEBand, int], QTableWidgetItem] = {}
        self._test_range_checks: dict[tuple[str, TestType], QCheckBox] = {}
        self._axis_button_groups: dict[str, QButtonGroup] = {}
        self._pol_button_groups: dict[str, QButtonGroup] = {}
        self._setup_layout()
        self._apply_styles()
        self._fit_table_size()
        self.resize(self.sizeHint())
        self._sync_aggregate_checks()

    @property
    def parameters_by_band(self) -> dict[LTEBand, LTECaseParameters]:
        """현재 화면의 Band별 파라미터를 반환한다."""

        return {
            band: LTECaseParameters(
                bandwidth=self._current_data(band, "bandwidth"),
                rb_allocation=self._current_data(band, "rb_allocation"),
                test_channel=self._current_data(band, "test_channel"),
                dut_ant_position=self._current_data(band, "dut_ant_position"),
            )
            for band in self._parameters_by_band
        }

    @property
    def group_settings(self) -> dict[str, LTEGroupSettings]:
        """현재 화면의 그룹별 Test 대역과 Position 설정을 반환한다."""

        return {
            group.key: LTEGroupSettings(
                selected_test_types=self._selected_test_types(group.key),
                axis_sequence=self._selected_axis_sequence(group.key),
                antenna_pol_sequence=self._selected_pol_sequence(group.key),
            )
            for group in LTE_BAND_GROUPS
        }

    def selected_bands(self) -> list[LTEBand]:
        """선택된 Band를 표의 표시 순서로 반환한다."""

        return [
            band
            for group in LTE_BAND_GROUPS
            for band in group.bands
            if self._band_checks[band].isChecked()
        ]

    def _setup_layout(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        self._table = QTableWidget(
            len(self._parameters_by_band),
            len(_TABLE_HEADERS),
            self,
        )
        self._table.setObjectName("lteParameterTable")
        header = _BandSelectionHeader(self._table)
        self._table.setHorizontalHeader(header)
        self._master_check = header.checkbox
        self._table.setHorizontalHeaderLabels(_TABLE_HEADERS)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(False)
        self._table.setShowGrid(True)

        row = 0
        for group in LTE_BAND_GROUPS:
            row = self._setup_group_rows(row, group.key, group.bands)

        self._apply_table_geometry()
        self._normalize_group_row_heights()
        self._fit_table_size()
        self._master_check.clicked.connect(self.on_master_check_clicked)
        layout.addWidget(self._table)

        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        cancel_button = QPushButton("Cancel", self)
        cancel_button.setObjectName("lteCancelButton")
        cancel_button.clicked.connect(self.reject)
        add_button = QPushButton("Add", self)
        add_button.setObjectName("lteAddButton")
        add_button.clicked.connect(self.on_add_clicked)
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(add_button)
        layout.addLayout(button_layout)
        self.resize(self.sizeHint())

    def _setup_group_rows(
        self,
        start_row: int,
        group_key: str,
        bands: tuple[LTEBand, ...],
    ) -> int:
        row_count = len(bands)
        self._set_spanned_widget(
            start_row,
            _GROUP_COLUMN,
            row_count,
            self._create_group_widget(group_key),
        )
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
        for offset, band in enumerate(bands):
            self._setup_band_row(
                start_row + offset,
                band,
                self._parameters_by_band[band],
            )
        return start_row + row_count

    def _set_spanned_widget(
        self,
        row: int,
        column: int,
        row_count: int,
        widget: QWidget,
    ) -> None:
        self._table.setCellWidget(row, column, widget)
        self._table.setSpan(row, column, row_count, 1)

    def _create_group_widget(self, group_key: str) -> QWidget:
        widget = QWidget(self._table)
        widget.setObjectName(f"lteBandGroup_{group_key}")
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(5)
        label = QLabel(_GROUP_TITLES[group_key], widget)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        checkbox = QCheckBox(widget)
        checkbox.setObjectName(f"lteBandGroupCheck_{group_key}")
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

    def _setup_band_row(
        self,
        row: int,
        band: LTEBand,
        parameters: LTECaseParameters,
    ) -> None:
        band_check = QCheckBox(self._table)
        band_check.setObjectName(f"lteBandCheck_{band.value}")
        band_check.setCursor(Qt.CursorShape.PointingHandCursor)
        band_check.stateChanged.connect(self._sync_aggregate_checks)
        check_panel = QWidget(self._table)
        check_layout = QHBoxLayout(check_panel)
        check_layout.setContentsMargins(0, 0, 0, 0)
        check_layout.addStretch(1)
        check_layout.addWidget(band_check)
        check_layout.addStretch(1)
        self._table.setCellWidget(row, _BAND_SELECT_COLUMN, check_panel)
        self._band_checks[band] = band_check

        self._table.setItem(
            row,
            _BAND_COLUMN,
            self._create_center_item(band.value),
        )
        self._set_combo(
            row,
            _BANDWIDTH_COLUMN,
            band,
            "bandwidth",
            get_lte_supported_bandwidths(band),
            parameters.bandwidth,
            text_formatter=lambda value: _format_number(float(value)),
        )
        self._set_combo(
            row,
            _RB_ALLOCATION_COLUMN,
            band,
            "rb_allocation",
            tuple(LTERBAllocation),
            parameters.rb_allocation,
        )
        self._set_combo(
            row,
            _CHANNEL_COLUMN,
            band,
            "test_channel",
            tuple(TestChannel),
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
            _ARFCN_COLUMN,
            _FREQUENCY_COLUMN,
            _RB_SIZE_COLUMN,
            _RB_OFFSET_COLUMN,
        ):
            item = self._create_center_item("")
            self._table.setItem(row, column, item)
            self._preview_items[(band, column)] = item
        self._connect_row_updates(band)
        self._refresh_row_preview(band)

    def _set_combo(
        self,
        row: int,
        column: int,
        band: LTEBand,
        field_name: str,
        values: tuple[object, ...],
        current_value: object,
        *,
        text_formatter: Callable[[object], str] | None = None,
    ) -> None:
        combo = QComboBox(self._table)
        combo.setObjectName(
            f"lteParam{_field_object_suffix(field_name)}_{band.value}",
        )
        for value in values:
            text = (
                str(text_formatter(value))
                if text_formatter is not None
                else str(getattr(value, "value", value))
            )
            combo.addItem(text, value)
        index = combo.findData(current_value)
        combo.setCurrentIndex(index if index >= 0 else 0)
        self._table.setCellWidget(row, column, combo)
        self._combo_by_cell[(band, field_name)] = combo

    def _connect_row_updates(self, band: LTEBand) -> None:
        for field_name in ("bandwidth", "rb_allocation", "test_channel"):
            self._combo_by_cell[(band, field_name)].currentIndexChanged.connect(
                lambda index, selected_band=band: self._refresh_row_preview(
                    selected_band,
                ),
            )

    def _refresh_row_preview(self, band: LTEBand) -> None:
        try:
            preview_case = TestCase(
                generation=Generation.LTE,
                band=band,
                bandwidth=self._current_data(band, "bandwidth"),
                test_type=_test_range_options_for_group(
                    _group_key_for_band(band),
                )[0].test_type,
                modulation=Modulation.QPSK,
                rb_allocation=self._current_data(band, "rb_allocation"),
                test_channel=self._current_data(band, "test_channel"),
                antenna_pol=AntennaPol.H,
                dut_axis=DUTAxis.X,
                dut_ant_position=self._current_data(
                    band,
                    "dut_ant_position",
                ),
            )
            values = {
                _ARFCN_COLUMN: str(preview_case.channel_number),
                _FREQUENCY_COLUMN: _format_number(preview_case.frequency_mhz),
                _RB_SIZE_COLUMN: str(preview_case.rb_size),
                _RB_OFFSET_COLUMN: str(preview_case.rb_offset),
            }
        except ValueError:
            values = {
                _ARFCN_COLUMN: "",
                _FREQUENCY_COLUMN: "",
                _RB_SIZE_COLUMN: "",
                _RB_OFFSET_COLUMN: "",
            }
        for column, value in values.items():
            self._preview_items[(band, column)].setText(value)

    def _create_test_range_widget(self, group_key: str) -> QWidget:
        widget = QWidget(self._table)
        widget.setObjectName(f"lteTestRangePanel_{group_key}")
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(3)
        selected_types = set(
            self._group_settings[group_key].selected_test_types,
        )
        for option in _test_range_options_for_group(group_key):
            checkbox = QCheckBox(option.label, widget)
            checkbox.setObjectName(
                f"lteRangeCheck_{group_key}_{option.test_type.value}",
            )
            checkbox.setChecked(option.test_type in selected_types)
            self._test_range_checks[(group_key, option.test_type)] = checkbox
            layout.addWidget(checkbox)
        layout.addStretch(1)
        return widget

    def _create_position_widget(self, group_key: str) -> QWidget:
        widget = QWidget(self._table)
        widget.setObjectName(f"ltePositionPanel_{group_key}")
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(10)

        axis_layout = QVBoxLayout()
        axis_layout.setSpacing(3)
        axis_layout.addWidget(self._create_position_label("Axis", widget))
        axis_group = self._create_position_group(
            group_key,
            "Axis",
            _axis_options(),
            self._group_settings[group_key].axis_sequence,
            widget,
            axis_layout,
        )
        axis_layout.addStretch(1)

        pol_layout = QVBoxLayout()
        pol_layout.setSpacing(3)
        pol_layout.addWidget(self._create_position_label("Pol", widget))
        pol_group = self._create_position_group(
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

    def _create_position_label(self, text: str, parent: QWidget) -> QLabel:
        label = QLabel(text, parent)
        label.setProperty("ltePositionSection", True)
        return label

    def _create_position_group(
        self,
        group_key: str,
        kind: str,
        options: tuple[LTEPositionOption, ...],
        selected_values: tuple[object, ...],
        parent: QWidget,
        layout: QVBoxLayout,
    ) -> QButtonGroup:
        group = QButtonGroup(parent)
        group.setExclusive(True)
        for index, option in enumerate(options):
            checkbox = QCheckBox(option.label, parent)
            checkbox.setObjectName(
                f"lte{kind}Check_{group_key}_{_option_object_suffix(option.label)}",
            )
            checkbox.setProperty("positionValues", option.values)
            checkbox.setChecked(tuple(option.values) == tuple(selected_values))
            checkbox.setMinimumWidth(_POSITION_OPTION_MIN_WIDTH)
            group.addButton(checkbox, index)
            layout.addWidget(checkbox)
        return group

    def on_master_check_clicked(self, checked: bool) -> None:
        """전체 Band의 체크 상태를 변경한다."""

        for checkbox in self._band_checks.values():
            checkbox.setChecked(checked)
        self._sync_aggregate_checks()

    def on_group_check_clicked(self, group_key: str, checked: bool) -> None:
        """선택한 그룹 Band의 체크 상태를 변경한다."""

        group = next(
            candidate for candidate in LTE_BAND_GROUPS
            if candidate.key == group_key
        )
        for band in group.bands:
            self._band_checks[band].setChecked(checked)
        self._sync_aggregate_checks()

    def _sync_aggregate_checks(self, state: int = 0) -> None:
        del state
        for group in LTE_BAND_GROUPS:
            selected_count = sum(
                self._band_checks[band].isChecked()
                for band in group.bands
            )
            self._set_aggregate_check_state(
                self._group_checks[group.key],
                selected_count,
                len(group.bands),
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
        """현재 선택으로 LTE TestCase를 생성한다."""

        selected_bands = self.selected_bands()
        if not selected_bands:
            QMessageBox.warning(self, "LTE Select", "선택된 Band가 없습니다.")
            return
        try:
            cases = self._build_test_cases(selected_bands)
        except ValueError as exc:
            QMessageBox.warning(self, "LTE Select", str(exc))
            return
        self.test_cases_created.emit(cases)
        self.accept()

    def _build_test_cases(self, bands: list[LTEBand]) -> list[TestCase]:
        self._validate_group_settings_for_bands(bands)
        settings_by_group = self.group_settings
        parameters_by_band = self.parameters_by_band
        cases: list[TestCase] = []
        for band in bands:
            settings = settings_by_group[_group_key_for_band(band)]
            parameters = parameters_by_band[band]
            for test_type in settings.selected_test_types:
                for axis in settings.axis_sequence:
                    for pol in settings.antenna_pol_sequence:
                        cases.append(
                            TestCase(
                                generation=Generation.LTE,
                                band=band,
                                bandwidth=parameters.bandwidth,
                                test_type=test_type,
                                modulation=Modulation.QPSK,
                                rb_allocation=parameters.rb_allocation,
                                test_channel=parameters.test_channel,
                                antenna_pol=pol,
                                dut_axis=axis,
                                dut_ant_position=parameters.dut_ant_position,
                            ),
                        )
        return cases

    def _validate_group_settings_for_bands(
        self,
        bands: list[LTEBand],
    ) -> None:
        settings_by_group = self.group_settings
        selected_group_keys = {
            _group_key_for_band(band)
            for band in bands
        }
        for group in LTE_BAND_GROUPS:
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

    def _selected_test_types(self, group_key: str) -> tuple[TestType, ...]:
        return tuple(
            option.test_type
            for option in _test_range_options_for_group(group_key)
            if self._test_range_checks[
                (group_key, option.test_type)
            ].isChecked()
        )

    def _selected_axis_sequence(self, group_key: str) -> tuple[DUTAxis, ...]:
        button = self._axis_button_groups[group_key].checkedButton()
        if button is None:
            return ()
        return tuple(button.property("positionValues"))

    def _selected_pol_sequence(
        self,
        group_key: str,
    ) -> tuple[AntennaPol, ...]:
        button = self._pol_button_groups[group_key].checkedButton()
        if button is None:
            return ()
        return tuple(button.property("positionValues"))

    def _current_data(self, band: LTEBand, field_name: str) -> object:
        return self._combo_by_cell[(band, field_name)].currentData()

    def _create_center_item(self, text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return item

    def _apply_table_geometry(self) -> None:
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(36)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)
        for column, width in enumerate(_COLUMN_WIDTHS):
            self._table.setColumnWidth(column, width)

    def _normalize_group_row_heights(self) -> None:
        start_row = 0
        for group in LTE_BAND_GROUPS:
            row_count = len(group.bands)
            widgets = (
                self._table.cellWidget(start_row, _TEST_RANGE_COLUMN),
                self._table.cellWidget(start_row, _POSITION_COLUMN),
            )
            span_height = max(
                widget.sizeHint().height() if widget is not None else 0
                for widget in widgets
            )
            row_height = max(
                _MIN_ROW_HEIGHT,
                (span_height + row_count - 1) // row_count,
            )
            for row in range(start_row, start_row + row_count):
                self._table.setRowHeight(row, row_height)
            start_row += row_count

    def _fit_table_size(self) -> None:
        table_width = sum(_COLUMN_WIDTHS) + 4
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
        self._table.setFixedSize(table_width, table_height)

    def _apply_styles(self) -> None:
        """기존 NR Table과 동일한 기본 색상과 컨트롤 스타일을 적용한다."""

        self.setStyleSheet(
            """
            QTableWidget#lteParameterTable {
                border: 1px solid #2f5aa8;
                gridline-color: #111111;
                background: #ffffff;
                color: #111111;
            }

            QTableWidget#lteParameterTable QHeaderView::section {
                background: #f5f5f5;
                color: #111111;
                border: 0;
                border-right: 1px solid #111111;
                border-bottom: 1px solid #111111;
                padding: 4px 6px;
            }

            QTableWidget#lteParameterTable QWidget {
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

            QCheckBox::indicator:indeterminate {
                background: #9eb4d0;
            }

            QLabel[ltePositionSection="true"] {
                font-weight: 600;
            }

            QPushButton {
                background: #fbfbfb;
                color: #111111;
                border: 1px solid #2f5aa8;
                padding: 5px 12px;
            }
            """
        )
