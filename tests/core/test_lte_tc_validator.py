from __future__ import annotations

from app.core.tc_validator import validate, validate_queue
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
from app.models.test_case import TestCase


def _make_nr_case(generation: Generation = Generation.NR_SA) -> TestCase:
    return TestCase(
        generation=generation,
        band=NRBand.N1,
        bandwidth=5.0,
        test_type=MeasurementTestType.HARMONIC,
        modulation=Modulation.QPSK,
        rb_allocation=RBAllocation.INNER_FULL,
        test_channel=ChannelEnum.MID,
        antenna_pol=AntennaPol.H,
        dut_axis=DUTAxis.X,
        dut_ant_position=DUTAntPosition.UPPER,
    )


def _make_lte_case() -> TestCase:
    return TestCase(
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
    )


def test_validate_accepts_lte_supported_bandwidth() -> None:
    assert validate(_make_lte_case()) == []


def test_validate_queue_allows_nr_sa_and_nr_nsa() -> None:
    assert validate_queue(
        [_make_nr_case(Generation.NR_SA), _make_nr_case(Generation.NR_NSA)]
    ) == []


def test_validate_queue_allows_lte_only() -> None:
    assert validate_queue([_make_lte_case(), _make_lte_case()]) == []


def test_validate_queue_rejects_nr_lte_mix() -> None:
    assert validate_queue([_make_nr_case(), _make_lte_case()]) == [
        "NR/LTE 혼합 Queue는 실행할 수 없습니다"
    ]
