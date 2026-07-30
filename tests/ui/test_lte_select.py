"""LTE 통합 Test Case 생성 화면 동작 테스트."""
from __future__ import annotations

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QMessageBox,
    QPushButton,
    QTableWidget,
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
    TestChannel as LTETestChannel,
    TestType as LTETestType,
)
from app.models.test_case import TestCase
from app.ui.lte_select import (
    LTECaseParameters,
    LTEGroupSettings,
    LTESelectDialog,
)
from app.ui.test_manager_panel import TestManagerPanel as ManagerPanel


def _make_lte_case() -> TestCase:
    return TestCase(
        generation=Generation.LTE,
        band=LTEBand.B5,
        bandwidth=5.0,
        test_type=LTETestType.INBAND,
        modulation=Modulation.QPSK,
        rb_allocation=LTERBAllocation.MID,
        test_channel=LTETestChannel.MID,
        antenna_pol=AntennaPol.H,
        dut_axis=DUTAxis.X,
        dut_ant_position=DUTAntPosition.LOWER,
    )


def test_lte_select_renders_integrated_table_without_scs_or_modulation(
    qtbot,
) -> None:
    """LTE 선택과 파라미터가 한 표에 있으며 고정값 열은 표시하지 않는다."""

    dialog = LTESelectDialog()
    qtbot.addWidget(dialog)
    table = dialog.findChild(QTableWidget, "lteParameterTable")

    assert table is not None
    assert table.rowCount() == 11
    assert table.columnCount() == 13
    assert [
        table.horizontalHeaderItem(index).text()
        for index in range(table.columnCount())
    ] == [
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
    ]
    assert "SCS" not in {
        table.horizontalHeaderItem(index).text()
        for index in range(table.columnCount())
    }
    assert "MOD" not in {
        table.horizontalHeaderItem(index).text()
        for index in range(table.columnCount())
    }
    assert not any(
        "Modulation" in combo.objectName()
        for combo in dialog.findChildren(QComboBox)
    )


def test_lte_select_uses_requested_group_and_band_order(qtbot) -> None:
    """LTE Band Group과 Band 행 순서를 확정 계약대로 표시한다."""

    dialog = LTESelectDialog()
    qtbot.addWidget(dialog)
    table = dialog.findChild(QTableWidget, "lteParameterTable")

    assert table is not None
    assert [
        table.item(row, 2).text()
        for row in range(table.rowCount())
    ] == [
        "B5",
        "B8",
        "B20",
        "B28",
        "B1",
        "B3",
        "B7",
        "B34",
        "B38",
        "B40",
        "B41",
    ]
    assert table.rowSpan(0, 0) == 4
    assert table.rowSpan(4, 0) == 3
    assert table.rowSpan(7, 0) == 4
    for object_name in (
        "lteBandGroup_lb",
        "lteBandGroup_mhb_fdd",
        "lteBandGroup_mhb_tdd",
    ):
        assert dialog.findChild(QWidget, object_name) is not None


def test_lte_select_master_checkbox_toggles_all_bands(qtbot) -> None:
    """헤더 체크박스가 전체 LTE Band를 선택하거나 해제한다."""

    dialog = LTESelectDialog()
    qtbot.addWidget(dialog)
    master = dialog.findChild(QCheckBox, "lteBandMasterCheck")
    band_checks = [
        dialog.findChild(QCheckBox, f"lteBandCheck_{band.value}")
        for band in LTEBand
    ]

    assert master is not None
    assert all(checkbox is not None for checkbox in band_checks)

    master.click()
    assert all(checkbox.isChecked() for checkbox in band_checks)
    assert master.checkState() is Qt.CheckState.Checked

    master.click()
    assert not any(checkbox.isChecked() for checkbox in band_checks)
    assert master.checkState() is Qt.CheckState.Unchecked


def test_lte_select_group_and_individual_checks_stay_consistent(qtbot) -> None:
    """개별 선택을 상위에 반영하고 부분 선택 그룹 클릭 시 전체 선택한다."""

    dialog = LTESelectDialog()
    qtbot.addWidget(dialog)
    master = dialog.findChild(QCheckBox, "lteBandMasterCheck")
    group_check = dialog.findChild(QCheckBox, "lteBandGroupCheck_lb")
    b5_check = dialog.findChild(QCheckBox, "lteBandCheck_B5")
    lb_checks = [
        dialog.findChild(QCheckBox, f"lteBandCheck_{band}")
        for band in ("B5", "B8", "B20", "B28")
    ]

    assert master is not None
    assert group_check is not None
    assert b5_check is not None
    b5_check.click()

    assert group_check.checkState() is Qt.CheckState.PartiallyChecked
    assert master.checkState() is Qt.CheckState.PartiallyChecked

    group_check.click()
    assert all(checkbox.isChecked() for checkbox in lb_checks)
    assert group_check.checkState() is Qt.CheckState.Checked
    assert master.checkState() is Qt.CheckState.PartiallyChecked

    group_check.click()
    assert not any(checkbox.isChecked() for checkbox in lb_checks)
    assert group_check.checkState() is Qt.CheckState.Unchecked
    assert master.checkState() is Qt.CheckState.Unchecked


def test_lte_select_updates_arfcn_frequency_and_rb_preview(qtbot) -> None:
    """BW, RB Allocation, Channel 변경 시 읽기 전용 파생값을 갱신한다."""

    dialog = LTESelectDialog()
    qtbot.addWidget(dialog)
    table = dialog.findChild(QTableWidget, "lteParameterTable")
    bandwidth = dialog.findChild(QComboBox, "lteParamBandwidth_B1")
    rb_allocation = dialog.findChild(QComboBox, "lteParamRbAllocation_B1")
    channel = dialog.findChild(QComboBox, "lteParamTestChannel_B1")

    assert table is not None
    assert bandwidth is not None
    assert rb_allocation is not None
    assert channel is not None

    bandwidth.setCurrentText("20")
    rb_allocation.setCurrentText("high")
    channel.setCurrentText("low")

    assert table.item(4, 7).text() == "18100"
    assert table.item(4, 8).text() == "1930"
    assert table.item(4, 9).text() == "1"
    assert table.item(4, 10).text() == "99"


def test_lte_select_limits_bandwidths_and_lb_test_ranges(qtbot) -> None:
    """Band별 지원 BW만 제공하고 LB에는 Bilog를 노출하지 않는다."""

    dialog = LTESelectDialog()
    qtbot.addWidget(dialog)
    b5_bandwidth = dialog.findChild(QComboBox, "lteParamBandwidth_B5")
    b34_bandwidth = dialog.findChild(QComboBox, "lteParamBandwidth_B34")

    assert b5_bandwidth is not None
    assert b34_bandwidth is not None
    assert [
        b5_bandwidth.itemData(index)
        for index in range(b5_bandwidth.count())
    ] == [1.4, 3.0, 5.0, 10.0]
    assert [
        b34_bandwidth.itemData(index)
        for index in range(b34_bandwidth.count())
    ] == [5.0, 10.0, 15.0]
    assert dialog.findChild(QCheckBox, "lteRangeCheck_lb_bilog") is None
    assert dialog.findChild(QCheckBox, "lteRangeCheck_lb_inband") is not None
    assert dialog.findChild(QCheckBox, "lteRangeCheck_lb_harmonic") is not None
    assert (
        dialog.findChild(QCheckBox, "lteRangeCheck_mhb_fdd_bilog")
        is not None
    )


def test_lte_select_add_expands_combinations_with_fixed_lte_values(
    qtbot,
) -> None:
    """Test 대역, Axis, Pol 조합을 펼치고 LTE 고정값을 모델에 적용한다."""

    dialog = LTESelectDialog()
    qtbot.addWidget(dialog)
    dialog.findChild(QCheckBox, "lteBandCheck_B5").setChecked(True)
    dialog.findChild(QCheckBox, "lteAxisCheck_lb_X_to_Y_to_Z").click()
    dialog.findChild(QCheckBox, "ltePolCheck_lb_H_to_V").click()

    with qtbot.waitSignal(dialog.test_cases_created, timeout=1000) as signal:
        dialog.findChild(QPushButton, "lteAddButton").click()

    cases = signal.args[0]
    assert len(cases) == 12
    assert {case.generation for case in cases} == {Generation.LTE}
    assert {case.band for case in cases} == {LTEBand.B5}
    assert {case.test_type for case in cases} == {
        LTETestType.INBAND,
        LTETestType.HARMONIC,
    }
    assert {case.dut_axis for case in cases} == {
        DUTAxis.X,
        DUTAxis.Y,
        DUTAxis.Z,
    }
    assert {case.antenna_pol for case in cases} == {
        AntennaPol.H,
        AntennaPol.V,
    }
    assert {case.modulation for case in cases} == {Modulation.QPSK}
    assert {case.scs_khz for case in cases} == {15}
    assert [
        (case.test_type, case.dut_axis, case.antenna_pol)
        for case in cases[:6]
    ] == [
        (LTETestType.INBAND, axis, pol)
        for axis in (DUTAxis.X, DUTAxis.Y, DUTAxis.Z)
        for pol in (AntennaPol.H, AntennaPol.V)
    ]


def test_lte_select_warns_when_selected_group_position_is_missing(
    qtbot,
    monkeypatch,
) -> None:
    """선택 그룹의 Position이 없으면 TestCase를 생성하지 않는다."""

    dialog = LTESelectDialog()
    qtbot.addWidget(dialog)
    warnings: list[tuple[str, str]] = []

    def fake_warning(parent, title, message) -> None:
        warnings.append((title, message))

    monkeypatch.setattr(QMessageBox, "warning", fake_warning)
    dialog.findChild(QCheckBox, "lteBandCheck_B5").setChecked(True)
    dialog.findChild(QPushButton, "lteAddButton").click()

    assert warnings == [("LTE Select", "LB Axis Position을 선택하세요.")]


def test_lte_select_restores_parameters_and_group_settings(qtbot) -> None:
    """직전 Band 파라미터와 그룹 선택 상태를 다음 화면에 복원한다."""

    parameters = {
        LTEBand.B5: LTECaseParameters(
            bandwidth=10.0,
            rb_allocation=LTERBAllocation.HIGH,
            test_channel=LTETestChannel.LOW,
            dut_ant_position=DUTAntPosition.UPPER,
        ),
    }
    settings = {
        "lb": LTEGroupSettings(
            selected_test_types=(LTETestType.HARMONIC,),
            axis_sequence=(DUTAxis.Z, DUTAxis.Y, DUTAxis.X),
            antenna_pol_sequence=(AntennaPol.V, AntennaPol.H),
        ),
    }
    dialog = LTESelectDialog(
        parameters_by_band=parameters,
        group_settings=settings,
    )
    qtbot.addWidget(dialog)

    assert (
        dialog.findChild(QComboBox, "lteParamBandwidth_B5").currentData()
        == 10.0
    )
    assert (
        dialog.findChild(QComboBox, "lteParamRbAllocation_B5").currentData()
        is LTERBAllocation.HIGH
    )
    assert not dialog.findChild(
        QCheckBox,
        "lteRangeCheck_lb_inband",
    ).isChecked()
    assert dialog.findChild(
        QCheckBox,
        "lteAxisCheck_lb_Z_to_Y_to_X",
    ).isChecked()
    assert dialog.findChild(
        QCheckBox,
        "ltePolCheck_lb_V_to_H",
    ).isChecked()
    assert not dialog.findChild(QCheckBox, "lteBandCheck_B5").isChecked()


def test_test_manager_lte_button_connects_dialog_and_restores_state(
    qtbot,
    monkeypatch,
) -> None:
    """LTE 버튼이 생성 결과를 추가하고 다음 팝업에 설정을 전달한다."""

    case = _make_lte_case()
    saved_parameters = {
        LTEBand.B5: LTECaseParameters(
            bandwidth=5.0,
            rb_allocation=LTERBAllocation.MID,
            test_channel=LTETestChannel.MID,
            dut_ant_position=DUTAntPosition.LOWER,
        ),
    }
    saved_settings = {
        "lb": LTEGroupSettings(
            selected_test_types=(LTETestType.INBAND,),
            axis_sequence=(DUTAxis.X,),
            antenna_pol_sequence=(AntennaPol.H,),
        ),
    }
    calls: list[tuple[object, object]] = []

    class FakeDialog(QObject):
        test_cases_created = Signal(list)

        def __init__(
            self,
            parent: QWidget | None = None,
            *,
            parameters_by_band=None,
            group_settings=None,
        ) -> None:
            super().__init__(parent)
            calls.append((parameters_by_band, group_settings))

        @property
        def parameters_by_band(self) -> dict:
            return saved_parameters

        @property
        def group_settings(self) -> dict:
            return saved_settings

        def exec(self) -> int:
            if len(calls) == 1:
                self.test_cases_created.emit([case])
            return 1

    monkeypatch.setattr("app.ui.test_manager_panel.LTESelectDialog", FakeDialog)
    panel = ManagerPanel()
    qtbot.addWidget(panel)
    lte_button = panel.findChild(QPushButton, "lteButton")

    assert lte_button is not None
    lte_button.click()
    lte_button.click()

    assert calls == [
        (None, None),
        (saved_parameters, saved_settings),
    ]
    assert panel.test_cases == (case,)


def test_test_manager_displays_lte_channel_and_frequency(qtbot) -> None:
    """공용 Queue 표가 LTE ARFCN과 Frequency를 모델 파생값으로 표시한다."""

    panel = ManagerPanel()
    qtbot.addWidget(panel)
    panel.add_test_cases([_make_lte_case()])
    table = panel.findChild(QTableWidget, "testCaseTable")

    assert table is not None
    assert table.item(0, 1).text() == "LTE"
    assert table.item(0, 2).text() == "B5"
    assert table.item(0, 4).text() == "15"
    assert table.item(0, 6).text() == "QPSK"
    assert table.item(0, 7).text() == "mid"
    assert table.item(0, 8).text() == "1"
    assert table.item(0, 9).text() == "12"
    assert table.item(0, 11).text() == "20525"
    assert table.item(0, 12).text() == "836.5"


def test_lte_select_uses_compact_table_size_without_scrollbars(qtbot) -> None:
    """기존 NR Table과 유사한 크기에서 전체 LTE 표를 표시한다."""

    dialog = LTESelectDialog()
    qtbot.addWidget(dialog)
    table = dialog.findChild(QTableWidget, "lteParameterTable")

    assert table is not None
    assert dialog.width() < 1360
    assert dialog.height() < 780
    dialog.show()
    qtbot.wait(0)

    assert table.horizontalScrollBar().maximum() == 0
    assert table.verticalScrollBar().maximum() == 0
