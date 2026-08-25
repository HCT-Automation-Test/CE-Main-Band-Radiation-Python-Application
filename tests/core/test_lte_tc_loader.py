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
    TestChannel as ChannelEnum,
    TestType as MeasurementTestType,
)
from app.models.lte_channel_lookup import (
    resolve_arfcn,
    resolve_lte_frequency_mhz,
)
from app.models.test_case import CSV_FIELDNAMES, TestCase


def _make_lte_case() -> TestCase:
    return TestCase(
        generation=Generation.LTE,
        band=LTEBand.B3,
        bandwidth=1.4,
        test_type=MeasurementTestType.HARMONIC,
        modulation=Modulation.QPSK,
        rb_allocation=LTERBAllocation.HIGH,
        test_channel=ChannelEnum.LOW,
        antenna_pol=AntennaPol.V,
        dut_axis=DUTAxis.Y,
        dut_ant_position=DUTAntPosition.LOWER,
    )


def test_lte_csv_round_trips_canonical_values_without_channel_number(
    tmp_path: Path,
) -> None:
    path = tmp_path / "lte.csv"
    original = _make_lte_case()

    save_csv(path, [original])
    loaded = load_csv(path)

    header = path.read_text(encoding="utf-8").splitlines()[0].split(",")
    assert header == list(CSV_FIELDNAMES)
    assert "ARFCN" not in header
    assert loaded[0].to_csv_row() == original.to_csv_row()
    assert loaded[0].to_csv_row()["generation"] == "LTE"
    assert loaded[0].to_csv_row()["band"] == "B3"
    assert loaded[0].to_csv_row()["bandwidth"] == "1.4"
    assert loaded[0].to_csv_row()["rb_allocation"] == "high"


def test_lte_csv_recomputes_arfcn_and_frequency_after_load(tmp_path: Path) -> None:
    path = tmp_path / "lte.csv"
    save_csv(path, [_make_lte_case()])

    case = load_csv(path)[0]

    assert resolve_arfcn(case.band, case.bandwidth, case.test_channel) == 19207
    assert (
        resolve_lte_frequency_mhz(case.band, case.bandwidth, case.test_channel)
        == 1710.7
    )


def test_lte_csv_reports_row_for_unsupported_bandwidth(tmp_path: Path) -> None:
    path = tmp_path / "invalid_lte.csv"
    path.write_text(
        ",".join(CSV_FIELDNAMES) + "\n"
        "LTE,B34,,20,harmonic,QPSK,mid,mid,H,X,Upper\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match=r"row 2: Unsupported LTE bandwidth '20'.*'B34'",
    ):
        load_csv(path)
