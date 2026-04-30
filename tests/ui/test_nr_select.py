"""NR Select 팝업 동작 테스트."""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QCheckBox, QComboBox, QPushButton, QTableWidget, QWidget

from app.models.enums import (
    AntennaPol,
    DUTAntPosition,
    DUTAxis,
    Modulation,
    NRBand,
    RBAllocation,
    TestChannel as NRTestChannel,
    TestType as NRTestType,
)
from app.models.test_case import TestCase
from app.ui.nr_select import NRParameterDialog, NRSelectDialog
from app.ui.test_manager_panel import TestManagerPanel as ManagerPanel


def _make_case() -> TestCase:
    return TestCase(
        band=NRBand.N78,
        bandwidth=100.0,
        test_type=NRTestType.HARMONIC,
        modulation=Modulation.QPSK,
        rb_allocation=RBAllocation.INNER_FULL,
        test_channel=NRTestChannel.MID,
        antenna_pol=AntennaPol.H,
        dut_axis=DUTAxis.X,
        dut_ant_position=DUTAntPosition.UPPER,
    )


def test_nr_select_dialog_renders_band_groups_and_actions(qtbot) -> None:
    """초안의 Band 그룹, Table, Add 컨트롤을 생성한다."""

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

    assert dialog.findChild(QPushButton, "nrTableButton").text() == "Table"
    assert dialog.findChild(QPushButton, "nrAddButton").text() == "Add"


def test_nr_select_all_reset_toggles_group_checkboxes(qtbot) -> None:
    """ALL/RESET 버튼이 해당 그룹의 Band 체크 상태를 토글한다."""

    dialog = NRSelectDialog()
    qtbot.addWidget(dialog)

    toggle_button = dialog.findChild(QPushButton, "nrBandToggle_lb")
    assert toggle_button is not None
    lb_checks = [
        dialog.findChild(QCheckBox, f"nrBandCheck_{band}")
        for band in ("n5", "n8", "n20", "n26", "n28", "n71")
    ]

    toggle_button.click()
    assert all(checkbox.isChecked() for checkbox in lb_checks)

    toggle_button.click()
    assert not any(checkbox.isChecked() for checkbox in lb_checks)


def test_nr_parameter_dialog_exposes_band_parameter_table(qtbot) -> None:
    """Table 팝업이 전체 Band의 파라미터 입력 행을 제공한다."""

    select_dialog = NRSelectDialog()
    parameter_dialog = NRParameterDialog(select_dialog.parameters_by_band)
    qtbot.addWidget(parameter_dialog)

    table = parameter_dialog.findChild(QTableWidget, "nrParameterTable")
    assert table is not None
    assert table.rowCount() == 15
    assert table.columnCount() == 9
    assert table.item(0, 0).text() == "B5"

    bandwidth_combo = parameter_dialog.findChild(QComboBox, "nrParamBandwidth_n5")
    test_type_combo = parameter_dialog.findChild(QComboBox, "nrParamTestType_n5")

    assert bandwidth_combo is not None
    assert [
        bandwidth_combo.itemText(index)
        for index in range(bandwidth_combo.count())
    ] == ["5", "10", "15", "20"]
    assert test_type_combo is not None
    assert [
        test_type_combo.itemText(index)
        for index in range(test_type_combo.count())
    ] == ["harmonic", "inband"]


def test_nr_parameter_dialog_collects_changed_parameters(qtbot) -> None:
    """Table 팝업에서 변경한 값이 band별 파라미터로 수집된다."""

    select_dialog = NRSelectDialog()
    parameter_dialog = NRParameterDialog(select_dialog.parameters_by_band)
    qtbot.addWidget(parameter_dialog)

    bandwidth_combo = parameter_dialog.findChild(QComboBox, "nrParamBandwidth_n78")
    test_type_combo = parameter_dialog.findChild(QComboBox, "nrParamTestType_n78")
    assert bandwidth_combo is not None
    assert test_type_combo is not None

    bandwidth_combo.setCurrentText("100")
    test_type_combo.setCurrentText("inband")

    parameters = parameter_dialog.parameters_by_band()[NRBand.N78]

    assert parameters.bandwidth == 100.0
    assert parameters.test_type is NRTestType.INBAND


def test_nr_select_add_emits_selected_band_test_cases(qtbot) -> None:
    """Add 버튼이 선택 Band와 Table 파라미터로 TestCase를 만든다."""

    dialog = NRSelectDialog()
    qtbot.addWidget(dialog)

    checkbox = dialog.findChild(QCheckBox, "nrBandCheck_n5")
    add_button = dialog.findChild(QPushButton, "nrAddButton")
    assert checkbox is not None
    assert add_button is not None
    checkbox.setChecked(True)

    with qtbot.waitSignal(dialog.test_cases_created, timeout=1000) as signal:
        add_button.click()

    cases = signal.args[0]

    assert len(cases) == 1
    assert cases[0].band is NRBand.N5
    assert cases[0].bandwidth == 5.0
    assert cases[0].test_type is NRTestType.HARMONIC


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
    assert table.item(0, 0).text() == "NR"
    assert table.item(0, 1).text() == "B78"
    assert table.item(0, 4).text() == "100"
    assert table.item(0, 7).text() == "135"
    assert table.item(0, 8).text() == "67"
    assert table.item(0, 12).text() == "harmonic"
    assert table.item(0, 13).text() == "6000"
    assert table.item(0, 14).text() == "18000"


def test_test_manager_nr_button_opens_dialog_and_appends_cases(
    qtbot,
    monkeypatch,
) -> None:
    """NR 버튼이 선택 팝업의 생성 결과를 Test Manager 표에 연결한다."""

    case = _make_case()
    created: dict[str, object] = {}

    class FakeDialog(QObject):
        test_cases_created = Signal(list)

        def __init__(self, parent: QWidget | None = None) -> None:
            super().__init__(parent)
            created["parent"] = parent

        def exec(self) -> int:
            self.test_cases_created.emit([case])
            return 1

    monkeypatch.setattr("app.ui.test_manager_panel.NRSelectDialog", FakeDialog)

    panel = ManagerPanel()
    qtbot.addWidget(panel)

    panel.findChild(QPushButton, "nrButton").click()

    assert created["parent"] is panel
    assert panel.test_cases == (case,)
