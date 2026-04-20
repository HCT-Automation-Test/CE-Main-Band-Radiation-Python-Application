from __future__ import annotations

from app.core.tc_validator import validate
from app.models.enums import (
    AntennaPol,
    DUTAxis,
    Modulation,
    NRBand,
    RBAllocation,
    TestChannel as ChannelEnum,
    TestType as MeasurementTestType,
)
from app.models.test_case import TestCase


def _build_case(*, band: NRBand | str = NRBand.N78, bandwidth: float = 100.0) -> TestCase:
    return TestCase(
        band=band,
        bandwidth=bandwidth,
        test_type=MeasurementTestType.HARMONIC,
        modulation=Modulation.QPSK,
        rb_allocation=RBAllocation.INNER_FULL,
        test_channel=ChannelEnum.MID,
        antenna_pol=AntennaPol.H,
        dut_axis=DUTAxis.X,
    )


def test_validate_returns_empty_list_for_supported_bandwidth() -> None:
    case = _build_case()

    assert validate(case) == []


def test_validate_returns_friendly_error_for_unsupported_bandwidth() -> None:
    case = _build_case()
    case.bandwidth = 5.0

    assert validate(case) == [
        "Unsupported bandwidth '5' for band 'n78'. "
        "Supported bandwidths: 10, 15, 20, 25, 30, 40, 50, 60, 70, 80, 90, 100"
    ]
