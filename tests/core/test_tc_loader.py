from __future__ import annotations

import pytest

from app.core.tc_loader import resolve_test_range
from app.models.enums import (
    AntennaPol,
    DUTAxis,
    Modulation,
    RBAllocation,
    TestType as MeasurementTestType,
)
from app.models.test_case import TestCase
from app.models.test_range import RangeId


def _build_case(
    *,
    band: str,
    test_range: RangeId | int | str = RangeId.RANGE_1,
) -> TestCase:
    return TestCase(
        band=band,
        bandwidth="100MHz",
        modulation=Modulation.QPSK,
        rb_allocation=RBAllocation.INNER_FULL,
        test_channel="mid",
        test_range=test_range,
        antenna_pol=AntennaPol.H,
        dut_axis=DUTAxis.X,
    )


def test_resolve_test_range_sets_range_from_band_and_test_type() -> None:
    case = _build_case(band="n78", test_range=RangeId.RANGE_1)

    resolved = resolve_test_range(case, MeasurementTestType.HARMONIC)

    assert resolved is not case
    assert case.test_range is RangeId.RANGE_1
    assert resolved.test_range is RangeId.RANGE_6
    assert resolved.band == "n78"
    assert resolved.test_channel == "mid"


def test_resolve_test_range_raises_for_unsupported_mapping() -> None:
    case = _build_case(band="n5")

    with pytest.raises(ValueError, match="Bilog not supported"):
        resolve_test_range(case, MeasurementTestType.BILOG)
