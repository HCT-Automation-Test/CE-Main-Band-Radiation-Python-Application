from __future__ import annotations

from pathlib import Path

import pytest

from app.core.tc_loader import load_csv, save_csv
from app.models.enums import (
    AntennaPol,
    DUTAxis,
    Modulation,
    RBAllocation,
    TestType as MeasurementTestType,
)
from app.models.test_case import CSV_FIELDNAMES, TestCase
from app.models.test_range import RangeId


def _build_case(
    *,
    band: str,
    test_type: MeasurementTestType = MeasurementTestType.HARMONIC,
) -> TestCase:
    return TestCase(
        band=band,
        bandwidth=100.0,
        test_type=test_type,
        modulation=Modulation.QPSK,
        rb_allocation=RBAllocation.INNER_FULL,
        test_channel="mid",
        antenna_pol=AntennaPol.H,
        dut_axis=DUTAxis.X,
    )


def test_test_case_derives_range_during_direct_creation() -> None:
    case = _build_case(band="n78")

    assert case.test_range is RangeId.RANGE_6
    assert case.band == "n78"
    assert case.test_channel == "mid"


def test_load_csv_reads_sample_and_resolves_test_range() -> None:
    sample_path = (
        Path(__file__).resolve().parents[2] / "testcases" / "samples" / "harmonic_sample.csv"
    )

    cases = load_csv(sample_path)

    assert len(cases) == 1
    assert cases[0].band == "n78"
    assert cases[0].bandwidth == 100.0
    assert cases[0].test_type is MeasurementTestType.HARMONIC
    assert cases[0].test_range is RangeId.RANGE_6


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
        "band,bandwidth,modulation,rb_allocation,test_channel,antenna_pol,dut_axis\n"
        "n78,100,QPSK,Inner_Full,mid,H,X\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="missing required columns"):
        load_csv(path)


def test_load_csv_rejects_unexpected_column(tmp_path: Path) -> None:
    path = tmp_path / "unexpected_column.csv"
    path.write_text(
        "band,bandwidth,test_type,modulation,rb_allocation,test_channel,"
        "antenna_pol,dut_axis,test_range\n"
        "n78,100,harmonic,QPSK,Inner_Full,mid,H,X,range_6\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unexpected columns"):
        load_csv(path)


def test_load_csv_rejects_out_of_order_header(tmp_path: Path) -> None:
    path = tmp_path / "wrong_order.csv"
    path.write_text(
        "band,test_type,bandwidth,modulation,rb_allocation,test_channel,antenna_pol,dut_axis\n"
        "n78,harmonic,100,QPSK,Inner_Full,mid,H,X\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="CSV header mismatch"):
        load_csv(path)


def test_load_csv_reports_row_and_field_context_for_invalid_rows(tmp_path: Path) -> None:
    path = tmp_path / "invalid_row.csv"
    path.write_text(
        ",".join(CSV_FIELDNAMES) + "\n"
        "n78,100,unknown,QPSK,Inner_Full,mid,H,X\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"row 2: Invalid test_type"):
        load_csv(path)


def test_load_csv_rejects_legacy_bandwidth_unit_suffix(tmp_path: Path) -> None:
    path = tmp_path / "legacy_bandwidth.csv"
    path.write_text(
        ",".join(CSV_FIELDNAMES) + "\n"
        "n78,100MHz,harmonic,QPSK,Inner_Full,mid,H,X\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"row 2: Invalid bandwidth"):
        load_csv(path)


def test_load_csv_rejects_unsupported_bandwidth_for_band(tmp_path: Path) -> None:
    path = tmp_path / "unsupported_bandwidth.csv"
    path.write_text(
        ",".join(CSV_FIELDNAMES) + "\n"
        "n71,30,harmonic,QPSK,Inner_Full,mid,H,X\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match=r"row 2: Unsupported bandwidth '30' for band 'n71'",
    ):
        load_csv(path)
