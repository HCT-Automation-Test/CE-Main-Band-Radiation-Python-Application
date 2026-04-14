"""TestCase dataclass 기본 인스턴스화 확인."""
from __future__ import annotations

from app.models.enums import AntennaPol, DUTAxis, Modulation
from app.models.test_case import TestCase


def test_test_case_instantiation() -> None:
    case = TestCase(
        band="n78",
        bandwidth="100MHz",
        modulation=Modulation.UNSPECIFIED,
        rb_size=273,
        rb_offset=0,
        test_channel="mid",
        range_name="example_range",
        antenna_pol=AntennaPol.H,
        dut_axis=DUTAxis.X,
    )
    assert case.band == "n78"
    assert case.antenna_pol is AntennaPol.H
    assert case.dut_axis is DUTAxis.X
