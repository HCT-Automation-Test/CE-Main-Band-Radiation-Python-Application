"""NR Select 팝업 동작 테스트."""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QWidget,
)

from app.core.tc_loader import load_csv, save_csv
from app.models.enums import (
    AntennaPol,
    DUTAntPosition,
    DUTAxis,
    Generation,
    LTEBand,
    Modulation,
    NRBand,
    RBAllocation,
    TestChannel as NRTestChannel,
    TestType as NRTestType,
)
from app.models.test_case import TestCase
from app.models.nsa_anchor import SUPPORTED_NSA_ANCHOR_BANDS
from app.ui.nr_select import (
    NRGroupSettings,
    NRSelectDialog,
    NRSelectState,
)
from app.ui.test_manager_panel import TestManagerPanel as ManagerPanel


def _make_case(*, test_type: NRTestType = NRTestType.HARMONIC) -> TestCase:
    return TestCase(
        band=NRBand.N78,
        bandwidth=100.0,
        test_type=test_type,
        modulation=Modulation.QPSK,
        rb_allocation=RBAllocation.INNER_FULL,
        test_channel=NRTestChannel.MID,
        antenna_pol=AntennaPol.H,
        dut_axis=DUTAxis.X,
        dut_ant_position=DUTAntPosition.UPPER,
    )


def _make_dialog_with_position() -> NRSelectDialog:
    dialog = NRSelectDialog()
    dialog.findChild(QCheckBox, "nrAxisCheck_lb_X_to_Y_to_Z").click()
    dialog.findChild(QCheckBox, "nrPolCheck_lb_V_to_H").click()
    return dialog


def test_nr_select_dialog_renders_band_groups_and_actions(qtbot) -> None:
    """SA 통합 화면이 Band 선택과 Parameter Table을 함께 제공한다."""

    dialog = NRSelectDialog()
    qtbot.addWidget(dialog)

    for object_name in (
        "nrBandGroup_lb",
        "nrBandGroup_mhb_fdd",
        "nrBandGroup_mhb_tdd",
        "nrBandGroup_uhb_tdd",
    ):
        assert dialog.findChild(QWidget, object_name) is not None

    for band in ("n5", "n8", "n20", "n26", "n28", "n71", "n1", "n79"):
        checkbox = dialog.findChild(QCheckBox, f"nrBandCheck_{band}")
        assert checkbox is not None
        assert not checkbox.isChecked()

    table = dialog.findChild(QTableWidget, "nrParameterTable")
    assert table is not None
    assert table.rowCount() == 15
    assert table.columnCount() == 15
    assert dialog.findChild(QPushButton, "nrTableButton") is None
    assert dialog.findChild(QPushButton, "nrCancelButton").text() == "Cancel"
    assert dialog.findChild(QPushButton, "nrAddButton").text() == "Add"


def test_nr_select_group_checkbox_toggles_group_bands(qtbot) -> None:
    """그룹 체크박스가 해당 그룹의 Band 선택을 토글한다."""

    dialog = NRSelectDialog()
    qtbot.addWidget(dialog)

    group_check = dialog.findChild(QCheckBox, "nrBandGroupCheck_lb")
    assert group_check is not None
    lb_checks = [
        dialog.findChild(QCheckBox, f"nrBandCheck_{band}")
        for band in ("n5", "n8", "n20", "n26", "n28", "n71")
    ]

    group_check.click()
    assert all(checkbox.isChecked() for checkbox in lb_checks)

    group_check.click()
    assert not any(checkbox.isChecked() for checkbox in lb_checks)


def test_nr_sa_dialog_exposes_integrated_table_shape(qtbot) -> None:
    """SA 화면은 Anchor 열 없이 전체 Band 통합 표를 제공한다."""

    dialog = NRSelectDialog(generation=Generation.NR_SA)
    qtbot.addWidget(dialog)

    table = dialog.findChild(QTableWidget, "nrParameterTable")

    assert table is not None
    assert table.rowCount() == 15
    assert table.columnCount() == 15
    assert [table.horizontalHeaderItem(index).text() for index in range(15)] == [
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
    ]
    assert table.cellWidget(0, 0).objectName() == "nrBandGroup_lb"
    assert table.item(0, 2).text() == "N5"
    assert table.rowSpan(0, 0) == 6
    assert table.rowSpan(0, 13) == 6
    assert table.rowSpan(0, 14) == 6
    assert table.cellWidget(6, 0).objectName() == "nrBandGroup_mhb_fdd"
    assert table.cellWidget(12, 0).objectName() == "nrBandGroup_uhb_tdd"


def test_nr_nsa_dialog_exposes_anchor_column_with_exact_allowlist(qtbot) -> None:
    """NSA 화면만 NR Band 바로 옆에 9개 Anchor 선택 열을 제공한다."""

    dialog = NRSelectDialog(generation=Generation.NR_NSA)
    qtbot.addWidget(dialog)

    table = dialog.findChild(QTableWidget, "nrParameterTable")
    anchor_combo = dialog.findChild(QComboBox, "nrAnchorBand_n5")

    assert table is not None
    assert table.columnCount() == 16
    assert table.horizontalHeaderItem(2).text() == "NR Band"
    assert table.horizontalHeaderItem(3).text() == "LTE Anchor Band"
    assert anchor_combo is not None
    assert [anchor_combo.itemData(index) for index in range(anchor_combo.count())] == list(
        SUPPORTED_NSA_ANCHOR_BANDS
    )
    assert anchor_combo.currentData() is LTEBand.B1
    assert dialog.findChild(QPushButton, "nrGenerationButton_NR_NSA") is None


def test_nr_nsa_dialog_builds_every_nr_anchor_combination(qtbot) -> None:
    """지원 NR Band와 9개 Anchor의 모든 조합을 별도 제한 없이 생성한다."""

    dialog = NRSelectDialog(generation=Generation.NR_NSA)
    qtbot.addWidget(dialog)
    for group_key in ("lb", "mhb_fdd", "mhb_tdd", "uhb_tdd"):
        dialog.findChild(QCheckBox, f"nrAxisCheck_{group_key}_X").click()
        dialog.findChild(QCheckBox, f"nrPolCheck_{group_key}_H").click()

    generated: set[tuple[NRBand, LTEBand]] = set()
    for band in NRBand:
        anchor_combo = dialog.findChild(QComboBox, f"nrAnchorBand_{band.value}")
        assert anchor_combo is not None
        for anchor_band in SUPPORTED_NSA_ANCHOR_BANDS:
            anchor_combo.setCurrentIndex(anchor_combo.findData(anchor_band))
            cases = dialog._build_test_cases([band])
            assert len(cases) == 1
            case = cases[0]
            assert case.generation is Generation.NR_NSA
            assert case.anchor_band is anchor_band
            generated.add((case.band, case.anchor_band))

    assert len(generated) == len(NRBand) * len(SUPPORTED_NSA_ANCHOR_BANDS)


def test_nr_nsa_dialog_rebuilds_same_band_with_changed_anchor(qtbot) -> None:
    """같은 NR Band도 Anchor를 바꿔 다시 Add할 수 있다."""

    dialog = NRSelectDialog(generation=Generation.NR_NSA)
    qtbot.addWidget(dialog)
    dialog.findChild(QCheckBox, "nrAxisCheck_lb_X").click()
    dialog.findChild(QCheckBox, "nrPolCheck_lb_H").click()
    anchor_combo = dialog.findChild(QComboBox, "nrAnchorBand_n5")

    anchor_combo.setCurrentIndex(anchor_combo.findData(LTEBand.B1))
    b1_cases = dialog._build_test_cases([NRBand.N5])
    anchor_combo.setCurrentIndex(anchor_combo.findData(LTEBand.B3))
    b3_cases = dialog._build_test_cases([NRBand.N5])

    assert {case.band for case in (*b1_cases, *b3_cases)} == {NRBand.N5}
    assert {case.anchor_band for case in b1_cases} == {LTEBand.B1}
    assert {case.anchor_band for case in b3_cases} == {LTEBand.B3}


def test_nr_select_state_restores_nsa_selection_and_anchor(qtbot) -> None:
    """NSA 화면 상태가 선택 Band, 파라미터, 그룹 설정, Anchor를 복원한다."""

    first_dialog = NRSelectDialog(generation=Generation.NR_NSA)
    qtbot.addWidget(first_dialog)
    first_dialog.findChild(QCheckBox, "nrBandCheck_n5").setChecked(True)
    anchor_combo = first_dialog.findChild(QComboBox, "nrAnchorBand_n5")
    anchor_combo.setCurrentIndex(anchor_combo.findData(LTEBand.B41))
    first_dialog.findChild(QComboBox, "nrParamModulation_n5").setCurrentText(
        "pi/2 BPSK",
    )
    first_dialog.findChild(QCheckBox, "nrRangeCheck_lb_inband").setChecked(False)
    first_dialog.findChild(QCheckBox, "nrAxisCheck_lb_Z").click()
    first_dialog.findChild(QCheckBox, "nrPolCheck_lb_V").click()

    restored_dialog = NRSelectDialog(
        generation=Generation.NR_NSA,
        state=first_dialog.state,
    )
    qtbot.addWidget(restored_dialog)

    assert restored_dialog.state.generation is Generation.NR_NSA
    assert restored_dialog.selected_bands() == [NRBand.N5]
    assert restored_dialog.findChild(QComboBox, "nrAnchorBand_n5").currentData() is LTEBand.B41
    assert (
        restored_dialog.parameters_by_band[NRBand.N5].modulation
        is Modulation.PI_OVER_2_BPSK
    )
    assert restored_dialog.group_settings["lb"] == NRGroupSettings(
        selected_test_types=(NRTestType.HARMONIC,),
        axis_sequence=(DUTAxis.Z,),
        antenna_pol_sequence=(AntennaPol.V,),
    )


def test_nr_parameter_dialog_distributes_spanned_widget_height_by_group(
    qtbot,
) -> None:
    """span 위젯 높이가 각 그룹 첫 Band 행에만 몰리지 않는다."""

    parameter_dialog = NRSelectDialog()
    qtbot.addWidget(parameter_dialog)

    table = parameter_dialog.findChild(QTableWidget, "nrParameterTable")

    assert table is not None
    assert table.rowHeight(0) == table.rowHeight(1)
    assert table.rowHeight(6) == table.rowHeight(7)
    assert table.rowHeight(9) == table.rowHeight(10)
    assert table.rowHeight(12) == table.rowHeight(13)


def test_nr_parameter_dialog_uses_compact_column_widths(qtbot) -> None:
    """Table 컬럼 폭을 첨부표처럼 조밀한 기본값으로 맞춘다."""

    parameter_dialog = NRSelectDialog()
    qtbot.addWidget(parameter_dialog)

    table = parameter_dialog.findChild(QTableWidget, "nrParameterTable")

    assert table is not None
    assert parameter_dialog.width() < 1360
    assert parameter_dialog.height() < 780
    assert table.columnWidth(0) == 76
    assert table.columnWidth(6) == 120
    assert table.columnWidth(13) == 105
    assert table.columnWidth(14) == 210

    axis_sequence = parameter_dialog.findChild(QCheckBox, "nrAxisCheck_lb_X_to_Y_to_Z")
    pol_sequence = parameter_dialog.findChild(QCheckBox, "nrPolCheck_lb_V_to_H")
    assert axis_sequence is not None
    assert pol_sequence is not None
    assert axis_sequence.minimumWidth() == 86
    assert pol_sequence.minimumWidth() == 86

    parameter_dialog.show()
    qtbot.wait(0)

    assert table.horizontalScrollBar().maximum() == 0
    assert table.verticalScrollBar().maximum() == 0
    visible_columns_width = sum(
        table.columnWidth(column)
        for column in range(table.columnCount())
    )
    assert abs(table.viewport().width() - visible_columns_width) <= 2
    visible_rows_height = sum(
        table.rowHeight(row)
        for row in range(table.rowCount())
    )
    assert abs(table.viewport().height() - visible_rows_height) <= 2


def test_nr_parameter_dialog_defaults_ranges_checked_and_positions_unchecked(
    qtbot,
) -> None:
    """Test 대역은 전체 체크, Position은 미체크로 시작한다."""

    parameter_dialog = NRSelectDialog()
    qtbot.addWidget(parameter_dialog)

    for object_name in (
        "nrRangeCheck_lb_inband",
        "nrRangeCheck_lb_harmonic",
        "nrRangeCheck_mhb_fdd_bilog",
        "nrRangeCheck_mhb_fdd_inband",
        "nrRangeCheck_mhb_fdd_harmonic",
        "nrRangeCheck_uhb_tdd_bilog",
        "nrRangeCheck_uhb_tdd_inband",
        "nrRangeCheck_uhb_tdd_harmonic",
    ):
        checkbox = parameter_dialog.findChild(QCheckBox, object_name)
        assert checkbox is not None
        assert checkbox.isChecked()

    for object_name in (
        "nrAxisCheck_lb_X",
        "nrAxisCheck_lb_X_to_Y_to_Z",
        "nrPolCheck_lb_H",
        "nrPolCheck_lb_V_to_H",
    ):
        checkbox = parameter_dialog.findChild(QCheckBox, object_name)
        assert checkbox is not None
        assert not checkbox.isChecked()


def test_nr_parameter_dialog_keeps_position_choices_exclusive(qtbot) -> None:
    """Axis/Pol Position은 그룹 안에서 각각 1개만 선택한다."""

    parameter_dialog = NRSelectDialog()
    qtbot.addWidget(parameter_dialog)

    axis_x = parameter_dialog.findChild(QCheckBox, "nrAxisCheck_lb_X")
    axis_y = parameter_dialog.findChild(QCheckBox, "nrAxisCheck_lb_Y")
    pol_h = parameter_dialog.findChild(QCheckBox, "nrPolCheck_lb_H")
    pol_v = parameter_dialog.findChild(QCheckBox, "nrPolCheck_lb_V")
    assert axis_x is not None
    assert axis_y is not None
    assert pol_h is not None
    assert pol_v is not None

    axis_x.click()
    axis_y.click()
    pol_h.click()
    pol_v.click()

    assert not axis_x.isChecked()
    assert axis_y.isChecked()
    assert not pol_h.isChecked()
    assert pol_v.isChecked()


def test_nr_parameter_dialog_updates_preview_when_bandwidth_changes(qtbot) -> None:
    """BW 변경 시 NARFCN/Frequency/RB 미리보기를 갱신한다."""

    parameter_dialog = NRSelectDialog()
    qtbot.addWidget(parameter_dialog)

    table = parameter_dialog.findChild(QTableWidget, "nrParameterTable")
    bandwidth_combo = parameter_dialog.findChild(QComboBox, "nrParamBandwidth_n78")
    channel_combo = parameter_dialog.findChild(QComboBox, "nrParamTestChannel_n78")
    assert table is not None
    assert bandwidth_combo is not None
    assert channel_combo is not None

    bandwidth_combo.setCurrentText("100")
    channel_combo.setCurrentText("mid")

    assert table.item(13, 9).text() == "636666"
    assert table.item(13, 10).text() == "3549.99"
    assert table.item(13, 11).text() == "1"
    assert table.item(13, 12).text() == "1"


def test_nr_parameter_dialog_collects_changed_band_parameters(qtbot) -> None:
    """Table 팝업에서 변경한 band별 주요 조건을 수집한다."""

    parameter_dialog = NRSelectDialog()
    qtbot.addWidget(parameter_dialog)

    bandwidth_combo = parameter_dialog.findChild(QComboBox, "nrParamBandwidth_n78")
    eut_ant_combo = parameter_dialog.findChild(QComboBox, "nrParamDutAntPosition_n78")
    assert bandwidth_combo is not None
    assert eut_ant_combo is not None

    bandwidth_combo.setCurrentText("100")
    eut_ant_combo.setCurrentText("Lower")

    parameters = parameter_dialog.parameters_by_band[NRBand.N78]

    assert parameters.bandwidth == 100.0
    assert parameters.dut_ant_position is DUTAntPosition.LOWER


def test_nr_parameter_dialog_uses_requested_rb_and_eut_ant_defaults(qtbot) -> None:
    """NR Table은 요청된 RB Allocation/EUT ANT 기본값과 표시 순서를 사용한다."""

    parameter_dialog = NRSelectDialog()
    qtbot.addWidget(parameter_dialog)

    rb_combo = parameter_dialog.findChild(QComboBox, "nrParamRbAllocation_n78")
    eut_ant_combo = parameter_dialog.findChild(QComboBox, "nrParamDutAntPosition_n78")
    assert rb_combo is not None
    assert eut_ant_combo is not None

    assert rb_combo.currentData() is RBAllocation.INNER_1RB_LEFT
    assert [rb_combo.itemData(index) for index in range(rb_combo.count())] == [
        RBAllocation.INNER_1RB_LEFT,
        RBAllocation.INNER_1RB_RIGHT,
        RBAllocation.INNER_FULL,
    ]
    assert eut_ant_combo.currentData() is DUTAntPosition.LOWER
    assert [eut_ant_combo.itemData(index) for index in range(eut_ant_combo.count())] == [
        DUTAntPosition.LOWER,
        DUTAntPosition.UPPER,
    ]


def test_nr_parameter_dialog_collects_group_settings(qtbot) -> None:
    """Table 팝업에서 선택한 Test 대역과 Position 설정을 수집한다."""

    parameter_dialog = NRSelectDialog()
    qtbot.addWidget(parameter_dialog)

    parameter_dialog.findChild(QCheckBox, "nrRangeCheck_lb_inband").setChecked(False)
    parameter_dialog.findChild(QCheckBox, "nrAxisCheck_lb_X_to_Y_to_Z").click()
    parameter_dialog.findChild(QCheckBox, "nrPolCheck_lb_V_to_H").click()

    settings = parameter_dialog.group_settings["lb"]

    assert settings.selected_test_types == (NRTestType.HARMONIC,)
    assert settings.axis_sequence == (DUTAxis.X, DUTAxis.Y, DUTAxis.Z)
    assert settings.antenna_pol_sequence == (AntennaPol.V, AntennaPol.H)


def test_nr_parameter_dialog_uses_correct_reverse_axis_sequence(qtbot) -> None:
    """Axis 역방향 선택지는 Z->Y->X 순서로 수집된다."""

    parameter_dialog = NRSelectDialog()
    qtbot.addWidget(parameter_dialog)

    axis_sequence = parameter_dialog.findChild(QCheckBox, "nrAxisCheck_lb_Z_to_Y_to_X")
    typo_axis_sequence = parameter_dialog.findChild(
        QCheckBox,
        "nrAxisCheck_lb_Z_to_Y_to_Z",
    )
    assert axis_sequence is not None
    assert axis_sequence.text() == "Z->Y->X"
    assert typo_axis_sequence is None

    axis_sequence.click()

    settings = parameter_dialog.group_settings["lb"]

    assert settings.axis_sequence == (DUTAxis.Z, DUTAxis.Y, DUTAxis.X)


def test_nr_select_add_expands_ranges_axis_and_pol_sequences(qtbot) -> None:
    """Add 버튼이 Test 대역, Axis, Pol 시퀀스 조합을 모두 펼친다."""

    dialog = _make_dialog_with_position()
    qtbot.addWidget(dialog)

    checkbox = dialog.findChild(QCheckBox, "nrBandCheck_n5")
    add_button = dialog.findChild(QPushButton, "nrAddButton")
    assert checkbox is not None
    assert add_button is not None
    checkbox.setChecked(True)

    with qtbot.waitSignal(dialog.test_cases_created, timeout=1000) as signal:
        add_button.click()

    cases = signal.args[0]

    assert len(cases) == 12
    assert {case.generation for case in cases} == {Generation.NR_SA}
    assert {case.anchor_band for case in cases} == {None}
    assert {case.band for case in cases} == {NRBand.N5}
    assert {case.test_type for case in cases} == {
        NRTestType.INBAND,
        NRTestType.HARMONIC,
    }
    assert {case.dut_axis for case in cases} == {DUTAxis.X, DUTAxis.Y, DUTAxis.Z}
    assert {case.antenna_pol for case in cases} == {AntennaPol.H, AntennaPol.V}


def test_nr_select_add_warns_when_position_is_missing(
    qtbot,
    monkeypatch,
) -> None:
    """Position 미선택 상태에서는 Add가 생성하지 않고 경고한다."""

    dialog = NRSelectDialog()
    qtbot.addWidget(dialog)
    warnings: list[tuple[str, str]] = []

    def fake_warning(parent, title, message) -> None:
        assert parent is dialog
        warnings.append((title, message))

    monkeypatch.setattr(QMessageBox, "warning", fake_warning)
    dialog.findChild(QCheckBox, "nrBandCheck_n5").setChecked(True)
    dialog.findChild(QPushButton, "nrAddButton").click()

    assert warnings == [("NR Select", "LB Axis Position을 선택하세요.")]


def test_test_manager_panel_adds_nr_test_cases_to_table(qtbot) -> None:
    """Test Manager가 생성된 NR TestCase를 표에 추가한다."""

    panel = ManagerPanel()
    qtbot.addWidget(panel)
    case = _make_case()

    panel.add_test_cases([case])

    table = panel.findChild(QTableWidget, "testCaseTable")
    assert table is not None
    assert panel.test_cases == (case,)
    assert table.rowCount() == 1
    assert table.item(0, 0).text() == "1"
    assert table.item(0, 1).text() == "NR_SA"
    assert table.item(0, 2).text() == "n78"
    assert table.item(0, 5).text() == "100"
    assert table.item(0, 8).text() == "135"
    assert table.item(0, 9).text() == "67"
    assert table.item(0, 13).text() == "6"
    assert table.item(0, 14).text() == "6000"
    assert table.item(0, 15).text() == "18000"
    assert table.item(0, 0).foreground().color().name() == "#111111"
    assert table.palette().color(QPalette.ColorRole.Text).name() == "#111111"
    assert table.palette().color(QPalette.ColorRole.HighlightedText).name() == "#111111"


def test_test_manager_delete_button_removes_selected_single_case(qtbot) -> None:
    """삭제 버튼은 선택된 TestCase 하나만 제거한다."""

    panel = ManagerPanel()
    qtbot.addWidget(panel)
    harmonic_case = _make_case()
    inband_case = _make_case(test_type=NRTestType.INBAND)
    panel.add_test_cases([harmonic_case, inband_case])

    table = panel.findChild(QTableWidget, "testCaseTable")
    assert table is not None
    table.selectRow(0)

    panel.findChild(QPushButton, "deleteButton").click()

    assert panel.test_cases == (inband_case,)
    assert table.rowCount() == 1
    assert table.item(0, 13).text() == "5"


def test_test_manager_delete_button_ignores_missing_selection(qtbot) -> None:
    """선택 행이 없으면 삭제 버튼은 목록을 변경하지 않는다."""

    panel = ManagerPanel()
    qtbot.addWidget(panel)
    case = _make_case()
    panel.add_test_cases([case])

    table = panel.findChild(QTableWidget, "testCaseTable")
    assert table is not None
    table.clearSelection()
    table.setCurrentItem(None)

    panel.findChild(QPushButton, "deleteButton").click()

    assert panel.test_cases == (case,)
    assert table.rowCount() == 1


def test_test_manager_clear_button_removes_all_cases(qtbot) -> None:
    """초기화 버튼은 내부 목록과 표를 모두 비운다."""

    panel = ManagerPanel()
    qtbot.addWidget(panel)
    panel.add_test_cases([_make_case(), _make_case(test_type=NRTestType.INBAND)])

    panel.findChild(QPushButton, "clearButton").click()

    table = panel.findChild(QTableWidget, "testCaseTable")
    assert table is not None
    assert panel.test_cases == ()
    assert table.rowCount() == 0


def test_test_manager_load_button_appends_csv_cases(
    qtbot,
    monkeypatch,
    tmp_path,
) -> None:
    """CSV 불러오기는 기존 TestCase 뒤에 항목을 추가한다."""

    panel = ManagerPanel()
    qtbot.addWidget(panel)
    existing_case = _make_case()
    loaded_case = _make_case(test_type=NRTestType.INBAND)
    panel.add_test_cases([existing_case])
    csv_path = tmp_path / "cases.csv"
    save_csv(csv_path, [loaded_case])

    def fake_get_open_file_name(parent, caption, directory, selected_filter):
        assert parent is panel
        assert caption == "Test Case CSV 불러오기"
        assert selected_filter == "CSV Files (*.csv);;All Files (*)"
        return str(csv_path), "CSV Files (*.csv)"

    monkeypatch.setattr(QFileDialog, "getOpenFileName", fake_get_open_file_name)

    panel.findChild(QPushButton, "loadItemButton").click()

    table = panel.findChild(QTableWidget, "testCaseTable")
    assert table is not None
    assert panel.test_cases == (existing_case, loaded_case)
    assert table.rowCount() == 2
    assert table.item(1, 13).text() == "5"


def test_test_manager_load_button_rejects_non_csv_file(
    qtbot,
    monkeypatch,
    tmp_path,
) -> None:
    """CSV가 아닌 파일은 읽지 않고 경고만 표시한다."""

    panel = ManagerPanel()
    qtbot.addWidget(panel)
    selected_path = tmp_path / "cases.txt"
    warnings: list[tuple[str, str]] = []
    load_calls: list[object] = []

    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        lambda parent, caption, directory, selected_filter: (
            str(selected_path),
            "All Files (*)",
        ),
    )
    monkeypatch.setattr(
        "app.ui.test_manager_panel.load_csv",
        lambda path: load_calls.append(path),
    )
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda parent, title, message: warnings.append((title, message)),
    )

    panel.findChild(QPushButton, "loadItemButton").click()

    assert load_calls == []
    assert panel.test_cases == ()
    assert warnings == [("Test Manager", "CSV 파일만 불러올 수 있습니다.")]


def test_test_manager_load_button_keeps_cases_when_csv_is_invalid(
    qtbot,
    monkeypatch,
    tmp_path,
) -> None:
    """CSV 로드 실패 시 기존 목록은 유지된다."""

    panel = ManagerPanel()
    qtbot.addWidget(panel)
    existing_case = _make_case()
    panel.add_test_cases([existing_case])
    csv_path = tmp_path / "invalid.csv"
    csv_path.write_text("bad,header\nvalue\n", encoding="utf-8")
    warnings: list[tuple[str, str]] = []

    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        lambda parent, caption, directory, selected_filter: (
            str(csv_path),
            "CSV Files (*.csv)",
        ),
    )
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda parent, title, message: warnings.append((title, message)),
    )

    panel.findChild(QPushButton, "loadItemButton").click()

    table = panel.findChild(QTableWidget, "testCaseTable")
    assert table is not None
    assert panel.test_cases == (existing_case,)
    assert table.rowCount() == 1
    assert warnings
    assert warnings[0][0] == "Test Manager"
    assert "CSV 불러오기에 실패했습니다." in warnings[0][1]


def test_test_manager_save_button_writes_current_cases_with_csv_suffix(
    qtbot,
    monkeypatch,
    tmp_path,
) -> None:
    """저장 버튼은 현재 TestCase 목록을 CSV로 저장한다."""

    panel = ManagerPanel()
    qtbot.addWidget(panel)
    cases = [_make_case(), _make_case(test_type=NRTestType.INBAND)]
    panel.add_test_cases(cases)
    selected_path = tmp_path / "exported_cases"

    def fake_get_save_file_name(parent, caption, directory, selected_filter):
        assert parent is panel
        assert caption == "Test Case CSV 저장"
        assert selected_filter == "CSV Files (*.csv);;All Files (*)"
        return str(selected_path), "CSV Files (*.csv)"

    monkeypatch.setattr(QFileDialog, "getSaveFileName", fake_get_save_file_name)

    panel.findChild(QPushButton, "saveItemButton").click()

    saved_path = selected_path.with_suffix(".csv")
    assert saved_path.exists()
    assert [case.to_csv_row() for case in load_csv(saved_path)] == [
        case.to_csv_row() for case in cases
    ]


def test_test_manager_nr_button_opens_dialog_and_appends_cases(
    qtbot,
    monkeypatch,
) -> None:
    """NR 버튼이 선택 팝업의 생성 결과를 Test Manager 표에 연결한다."""

    case = _make_case()
    created: dict[str, object] = {}

    class FakeDialog(QObject):
        test_cases_created = Signal(list)

        def __init__(
            self,
            parent: QWidget | None = None,
            *,
            parameters_by_band=None,
            group_settings=None,
            generation=Generation.NR_SA,
        ) -> None:
            super().__init__(parent)
            created["parent"] = parent
            created["parameters_by_band"] = parameters_by_band
            created["group_settings"] = group_settings
            created["generation"] = generation

        @property
        def parameters_by_band(self) -> dict:
            return {}

        @property
        def group_settings(self) -> dict:
            return {}

        @property
        def generation(self) -> Generation:
            return Generation.NR_SA

        def exec(self) -> int:
            self.test_cases_created.emit([case])
            return 1

    monkeypatch.setattr("app.ui.test_manager_panel.NRSelectDialog", FakeDialog)

    panel = ManagerPanel()
    qtbot.addWidget(panel)

    panel.findChild(QPushButton, "nrButton").click()

    assert created["parent"] is panel
    assert created["parameters_by_band"] is None
    assert created["group_settings"] is None
    assert created["generation"] is Generation.NR_SA
    assert panel.test_cases == (case,)


def test_test_manager_reuses_nr_table_settings_during_program_lifetime(
    qtbot,
    monkeypatch,
) -> None:
    """Test Manager가 NR Table 설정을 다음 NR 팝업에 다시 전달한다."""

    saved_parameters = {
        NRBand.N78: NRCaseParameters(
            bandwidth=100.0,
            modulation=Modulation.QPSK,
            rb_allocation=RBAllocation.INNER_FULL,
            test_channel=NRTestChannel.MID,
            dut_ant_position=DUTAntPosition.UPPER,
        ),
    }
    saved_group_settings = {
        "lb": NRGroupSettings(
            selected_test_types=(NRTestType.HARMONIC,),
            axis_sequence=(DUTAxis.X,),
            antenna_pol_sequence=(AntennaPol.H,),
        ),
    }
    calls: list[tuple[object, object, Generation]] = []

    class FakeDialog(QObject):
        test_cases_created = Signal(list)

        def __init__(
            self,
            parent: QWidget | None = None,
            *,
            parameters_by_band=None,
            group_settings=None,
            generation=Generation.NR_SA,
        ) -> None:
            super().__init__(parent)
            calls.append((parameters_by_band, group_settings, generation))

        @property
        def parameters_by_band(self) -> dict:
            return saved_parameters

        @property
        def group_settings(self) -> dict:
            return saved_group_settings

        @property
        def generation(self) -> Generation:
            return Generation.NR_NSA

        def exec(self) -> int:
            return 0

    monkeypatch.setattr("app.ui.test_manager_panel.NRSelectDialog", FakeDialog)

    panel = ManagerPanel()
    qtbot.addWidget(panel)

    panel.findChild(QPushButton, "nrButton").click()
    panel.findChild(QPushButton, "nrButton").click()

    assert calls == [
        (None, None, Generation.NR_SA),
        (saved_parameters, saved_group_settings, Generation.NR_NSA),
    ]
