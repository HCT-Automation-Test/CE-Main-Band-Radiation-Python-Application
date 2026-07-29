from __future__ import annotations

import pytest

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
from app.models.test_range import RangeId


def _make_lte_case(
    *,
    band: LTEBand | NRBand | str = LTEBand.B3,
    bandwidth: float = 1.4,
    test_type: MeasurementTestType = MeasurementTestType.HARMONIC,
    modulation: Modulation = Modulation.QPSK,
    rb_allocation: LTERBAllocation | RBAllocation | str = LTERBAllocation.MID,
) -> TestCase:
    return TestCase(
        generation=Generation.LTE,
        band=band,
        bandwidth=bandwidth,
        test_type=test_type,
        modulation=modulation,
        rb_allocation=rb_allocation,
        test_channel=ChannelEnum.MID,
        antenna_pol=AntennaPol.H,
        dut_axis=DUTAxis.X,
        dut_ant_position=DUTAntPosition.UPPER,
    )


@pytest.mark.parametrize(
    ("band", "bandwidth", "test_type", "expected_range", "expected_offset"),
    [
        (LTEBand.B5, 1.4, MeasurementTestType.INBAND, RangeId.RANGE_1, 3),
        (LTEBand.B20, 20.0, MeasurementTestType.HARMONIC, RangeId.RANGE_3, 49),
        (LTEBand.B1, 5.0, MeasurementTestType.BILOG, RangeId.RANGE_1, 12),
        (LTEBand.B3, 10.0, MeasurementTestType.INBAND, RangeId.RANGE_2, 24),
        (LTEBand.B34, 15.0, MeasurementTestType.HARMONIC, RangeId.RANGE_4, 36),
    ],
)
def test_lte_test_case_derives_final_values(
    band: LTEBand,
    bandwidth: float,
    test_type: MeasurementTestType,
    expected_range: RangeId,
    expected_offset: int,
) -> None:
    case = _make_lte_case(
        band=band,
        bandwidth=bandwidth,
        test_type=test_type,
    )

    assert case.generation is Generation.LTE
    assert case.band is band
    assert case.scs_khz == 15
    assert case.test_range is expected_range
    assert case.rb_size == 1
    assert case.rb_offset == expected_offset


def test_lte_test_case_rejects_lb_bilog() -> None:
    with pytest.raises(ValueError, match="Bilog not supported"):
        _make_lte_case(
            band=LTEBand.B28,
            bandwidth=20.0,
            test_type=MeasurementTestType.BILOG,
        )


def test_lte_test_case_exposes_band_and_channel_derived_values() -> None:
    tdd_case = _make_lte_case(band=LTEBand.B34, bandwidth=10.0)
    lb_case = _make_lte_case(
        band=LTEBand.B5,
        bandwidth=5.0,
        test_type=MeasurementTestType.INBAND,
    )

    assert tdd_case.factor_keyword == "3G HPF"
    assert tdd_case.mt8000_recall == "LTE_TDD"
    assert tdd_case.turntable_speed == 3
    assert tdd_case.channel_number == 36275
    assert tdd_case.frequency_mhz == 2017.5
    assert lb_case.factor_keyword == "1G HPF"
    assert lb_case.mt8000_recall == "LTE_FDD"
    assert lb_case.turntable_speed == 5


def test_lte_test_case_rejects_non_qpsk_modulation() -> None:
    with pytest.raises(ValueError, match="LTE modulation must be QPSK"):
        _make_lte_case(modulation=Modulation.PI_OVER_2_BPSK)


def test_lte_generation_rejects_nr_band() -> None:
    with pytest.raises(ValueError, match="Invalid band"):
        _make_lte_case(band=NRBand.N1)


def test_lte_generation_rejects_nr_rb_allocation() -> None:
    with pytest.raises(ValueError, match="Invalid rb_allocation"):
        _make_lte_case(rb_allocation=RBAllocation.INNER_FULL)


def test_nr_generation_rejects_lte_band() -> None:
    with pytest.raises(ValueError, match="Invalid band"):
        TestCase(
            generation=Generation.NR_SA,
            band=LTEBand.B1,
            bandwidth=5.0,
            test_type=MeasurementTestType.HARMONIC,
            modulation=Modulation.QPSK,
            rb_allocation=RBAllocation.INNER_FULL,
            test_channel=ChannelEnum.MID,
            antenna_pol=AntennaPol.H,
            dut_axis=DUTAxis.X,
            dut_ant_position=DUTAntPosition.UPPER,
        )


def test_nr_generation_rejects_lte_rb_allocation() -> None:
    with pytest.raises(ValueError, match="Invalid rb_allocation"):
        TestCase(
            generation=Generation.NR_SA,
            band=NRBand.N1,
            bandwidth=5.0,
            test_type=MeasurementTestType.HARMONIC,
            modulation=Modulation.QPSK,
            rb_allocation=LTERBAllocation.MID,
            test_channel=ChannelEnum.MID,
            antenna_pol=AntennaPol.H,
            dut_axis=DUTAxis.X,
            dut_ant_position=DUTAntPosition.UPPER,
        )


def test_lte_test_case_rejects_unsupported_bandwidth() -> None:
    with pytest.raises(ValueError, match="Unsupported LTE bandwidth"):
        _make_lte_case(band=LTEBand.B34, bandwidth=20.0)
