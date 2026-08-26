from __future__ import annotations

from pathlib import Path

import pytest

from app.core.tc_loader import load_csv, save_csv
from app.models.enums import (
    AntennaPol,
    DUTAntPosition,
    DUTAxis,
    Generation,
    LTEBand,
    LTERBAllocation,
    Modulation,
    NRBand,
    RBAllocation,
    TestChannel as ChannelEnum,
    TestType as MeasurementTestType,
)
from app.models.test_case import CSV_FIELDNAMES, TestCase
from app.models.test_range import RangeId

_LEGACY_CSV_FIELDNAMES = tuple(
    field_name for field_name in CSV_FIELDNAMES if field_name != "anchor_band"
)


def _build_case(
    *,
    band: NRBand | str,
    test_type: MeasurementTestType = MeasurementTestType.HARMONIC,
) -> TestCase:
    return TestCase(
        band=band,
        bandwidth=100.0,
        test_type=test_type,
        modulation=Modulation.QPSK,
        rb_allocation=RBAllocation.INNER_FULL,
        test_channel=ChannelEnum.MID,
        antenna_pol=AntennaPol.H,
        dut_axis=DUTAxis.X,
        dut_ant_position=DUTAntPosition.UPPER,
    )


def test_test_case_derives_range_during_direct_creation() -> None:
    case = _build_case(band="n78")

    assert case.test_range is RangeId.RANGE_6
    assert case.band is NRBand.N78
    assert case.test_channel is ChannelEnum.MID


def test_load_csv_reads_sample_and_resolves_test_range() -> None:
    sample_path = (
        Path(__file__).resolve().parents[2] / "testcases" / "samples" / "harmonic_sample.csv"
    )

    cases = load_csv(sample_path)

    assert len(cases) == 1
    assert cases[0].band is NRBand.N78
    assert cases[0].bandwidth == 100.0
    assert cases[0].test_type is MeasurementTestType.HARMONIC
    assert cases[0].test_channel is ChannelEnum.MID
    assert cases[0].test_range is RangeId.RANGE_6
    assert cases[0].dut_ant_position is DUTAntPosition.UPPER


def test_save_csv_round_trips_external_fields(tmp_path: Path) -> None:
    path = tmp_path / "cases.csv"
    original_cases = [_build_case(band="n78")]

    save_csv(path, original_cases)
    reloaded_cases = load_csv(path)

    assert path.read_text(encoding="utf-8").splitlines()[0] == ",".join(CSV_FIELDNAMES)
    assert [case.to_csv_row() for case in reloaded_cases] == [
        case.to_csv_row() for case in original_cases
    ]
    assert reloaded_cases[0].test_range is RangeId.RANGE_6


def test_load_csv_rejects_missing_required_column(tmp_path: Path) -> None:
    path = tmp_path / "missing_test_type.csv"
    path.write_text(
        "generation,band,bandwidth,modulation,rb_allocation,test_channel,antenna_pol,"
        "dut_axis,dut_ant_position\n"
        "NR_SA,n78,100,QPSK,Inner_Full,mid,H,X,Upper\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="missing required columns"):
        load_csv(path)


def test_load_csv_rejects_unexpected_column(tmp_path: Path) -> None:
    path = tmp_path / "unexpected_column.csv"
    path.write_text(
        "generation,band,bandwidth,test_type,modulation,rb_allocation,test_channel,"
        "antenna_pol,dut_axis,dut_ant_position,test_range\n"
        "NR_SA,n78,100,harmonic,QPSK,Inner_Full,mid,H,X,Upper,range_6\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unexpected columns"):
        load_csv(path)


def test_load_csv_rejects_out_of_order_header(tmp_path: Path) -> None:
    path = tmp_path / "wrong_order.csv"
    path.write_text(
        "band,generation,test_type,bandwidth,modulation,rb_allocation,test_channel,"
        "antenna_pol,dut_axis,dut_ant_position\n"
        "n78,NR_SA,harmonic,100,QPSK,Inner_Full,mid,H,X,Upper\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="CSV header mismatch"):
        load_csv(path)


def test_load_csv_reports_row_and_field_context_for_invalid_rows(tmp_path: Path) -> None:
    path = tmp_path / "invalid_row.csv"
    path.write_text(
        ",".join(CSV_FIELDNAMES) + "\n"
        "NR_SA,n78,,100,unknown,QPSK,Inner_Full,mid,H,X,Upper\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"row 2: Invalid test_type"):
        load_csv(path)


def test_load_csv_rejects_bandwidth_unit_suffix(tmp_path: Path) -> None:
    path = tmp_path / "legacy_bandwidth.csv"
    path.write_text(
        ",".join(CSV_FIELDNAMES) + "\n"
        "NR_SA,n78,,100MHz,harmonic,QPSK,Inner_Full,mid,H,X,Upper\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"row 2: Invalid bandwidth"):
        load_csv(path)


def test_load_csv_rejects_unsupported_bandwidth_for_band(tmp_path: Path) -> None:
    path = tmp_path / "unsupported_bandwidth.csv"
    path.write_text(
        ",".join(CSV_FIELDNAMES) + "\n"
        "NR_SA,n71,,30,harmonic,QPSK,Inner_Full,mid,H,X,Upper\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match=r"row 2: Unsupported bandwidth '30' for band 'n71'",
    ):
        load_csv(path)


def test_load_csv_accepts_legacy_nr_sa_and_lte_rows(tmp_path: Path) -> None:
    path = tmp_path / "legacy_cases.csv"
    path.write_text(
        ",".join(_LEGACY_CSV_FIELDNAMES) + "\n"
        "NR_SA,n78,100,harmonic,QPSK,Inner_Full,mid,H,X,Upper\n"
        "LTE,B1,5,harmonic,QPSK,mid,mid,H,X,Upper\n",
        encoding="utf-8",
    )

    cases = load_csv(path)

    assert [case.generation for case in cases] == [
        Generation.NR_SA,
        Generation.LTE,
    ]
    assert all(case.anchor_band is None for case in cases)


def test_load_csv_rejects_legacy_nr_nsa_without_anchor_migration(
    tmp_path: Path,
) -> None:
    path = tmp_path / "legacy_nsa.csv"
    path.write_text(
        ",".join(_LEGACY_CSV_FIELDNAMES) + "\n"
        "NR_NSA,n78,100,harmonic,QPSK,Inner_Full,mid,H,X,Upper\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match=r"row 2: legacy 10-column NR_NSA CSV requires anchor_band migration",
    ):
        load_csv(path)


@pytest.mark.parametrize(
    ("anchor_band", "expected_error"),
    [
        ("", "NR_NSA requires anchor_band"),
        ("B34", "Unsupported NSA anchor_band"),
    ],
)
def test_load_csv_rejects_invalid_nr_nsa_anchor_with_row_context(
    tmp_path: Path,
    anchor_band: str,
    expected_error: str,
) -> None:
    path = tmp_path / "invalid_nsa.csv"
    path.write_text(
        ",".join(CSV_FIELDNAMES) + "\n"
        f"NR_NSA,n78,{anchor_band},100,harmonic,QPSK,Inner_Full,mid,H,X,Upper\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=rf"row 2: {expected_error}"):
        load_csv(path)


@pytest.mark.parametrize("generation", ["NR_SA", "LTE"])
def test_load_csv_rejects_anchor_for_non_nsa_generation(
    tmp_path: Path,
    generation: str,
) -> None:
    path = tmp_path / "invalid_non_nsa_anchor.csv"
    band = "n78" if generation == "NR_SA" else "B1"
    bandwidth = "100" if generation == "NR_SA" else "5"
    rb_allocation = "Inner_Full" if generation == "NR_SA" else "mid"
    path.write_text(
        ",".join(CSV_FIELDNAMES) + "\n"
        f"{generation},{band},B1,{bandwidth},harmonic,QPSK,"
        f"{rb_allocation},mid,H,X,Upper\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=rf"row 2: {generation} must not define"):
        load_csv(path)


def test_save_csv_round_trips_sa_nsa_and_lte_with_current_schema(
    tmp_path: Path,
) -> None:
    path = tmp_path / "all_generations.csv"
    cases = [
        _build_case(band=NRBand.N78),
        TestCase(
            generation=Generation.NR_NSA,
            anchor_band=LTEBand.B5,
            band=NRBand.N78,
            bandwidth=100.0,
            test_type=MeasurementTestType.HARMONIC,
            modulation=Modulation.QPSK,
            rb_allocation=RBAllocation.INNER_FULL,
            test_channel=ChannelEnum.MID,
            antenna_pol=AntennaPol.H,
            dut_axis=DUTAxis.X,
            dut_ant_position=DUTAntPosition.UPPER,
        ),
        TestCase(
            generation=Generation.LTE,
            band=LTEBand.B1,
            bandwidth=5.0,
            test_type=MeasurementTestType.HARMONIC,
            modulation=Modulation.QPSK,
            rb_allocation=LTERBAllocation.MID,
            test_channel=ChannelEnum.MID,
            antenna_pol=AntennaPol.H,
            dut_axis=DUTAxis.X,
            dut_ant_position=DUTAntPosition.UPPER,
        ),
    ]

    save_csv(path, cases)
    loaded = load_csv(path)

    assert [case.to_csv_row() for case in loaded] == [
        case.to_csv_row() for case in cases
    ]
    assert loaded[1].anchor_band is LTEBand.B5


def test_save_csv_rejects_mutated_invalid_anchor_before_creating_file(
    tmp_path: Path,
) -> None:
    path = tmp_path / "invalid.csv"
    case = _build_case(band=NRBand.N78)
    case.anchor_band = LTEBand.B1

    with pytest.raises(ValueError, match="NR_SA must not define anchor_band"):
        save_csv(path, [case])

    assert not path.exists()
