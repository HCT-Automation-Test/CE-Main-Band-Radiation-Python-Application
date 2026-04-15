"""TestCase dataclass 기본 인스턴스화 확인."""
from __future__ import annotations

import pytest

from app.models.enums import AntennaPol, DUTAxis, FilterMode, InputPath, Modulation, RBAllocation
from app.models.test_case import TestCase
from app.models.test_range import RangeId


def _build_case(
    *,
    bandwidth: str = "100MHz",
    band: str = "n78",
    rb_allocation: RBAllocation = RBAllocation.INNER_FULL,
    test_range: RangeId | int | str = RangeId.RANGE_6,
) -> TestCase:
    return TestCase(
        band=band,
        bandwidth=bandwidth,
        modulation=Modulation.QPSK,
        rb_allocation=rb_allocation,
        test_channel="mid",
        test_range=test_range,
        antenna_pol=AntennaPol.H,
        dut_axis=DUTAxis.X,
    )


def test_test_case_instantiation() -> None:
    case = _build_case()

    assert case.band == "n78"
    assert case.scs_khz == 30
    assert case.modulation is Modulation.QPSK
    assert case.rb_allocation is RBAllocation.INNER_FULL
    assert case.test_range is RangeId.RANGE_6
    assert case.range_name == "range_6"
    assert case.antenna_pol is AntennaPol.H
    assert case.dut_axis is DUTAxis.X


def test_test_case_resolves_typed_range_definition() -> None:
    case = _build_case()

    assert case.range_definition.input_path is InputPath.INPUT3
    assert case.range_definition.filter_mode is FilterMode.HPF_6G


def test_test_case_resolves_inner_full_rb_parameters() -> None:
    case = _build_case()

    assert case.rb_size == 135
    assert case.rb_offset == 67


def test_test_case_resolves_edge_rb_allocations() -> None:
    left_case = _build_case(rb_allocation=RBAllocation.INNER_1RB_LEFT)
    right_case = _build_case(rb_allocation=RBAllocation.INNER_1RB_RIGHT)

    assert left_case.rb_size == 1
    assert left_case.rb_offset == 1
    assert right_case.rb_size == 1
    assert right_case.rb_offset == 271


def test_test_case_normalizes_bandwidth_before_lookup() -> None:
    case = _build_case(bandwidth="100 MHz")

    assert case.rb_size == 135
    assert case.rb_offset == 67


def test_test_case_normalizes_string_range_value() -> None:
    case = _build_case(test_range="Range 5")

    assert case.test_range is RangeId.RANGE_5
    assert case.range_name == "range_5"


def test_test_case_rejects_unsupported_bandwidth_scs_combination() -> None:
    case = _build_case(band="n1", bandwidth="60MHz")

    with pytest.raises(ValueError, match="Unsupported RB allocation mapping"):
        _ = case.rb_parameters
