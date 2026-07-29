"""TestCase dataclass and CSV conversion behavior."""
from __future__ import annotations

import pytest

from app.models.enums import (
    AntennaPol,
    DUTAntPosition,
    DUTAxis,
    FilterMode,
    Generation,
    InputPath,
    Modulation,
    NRBand,
    RBAllocation,
    TestChannel as ChannelEnum,
    TestType as MeasurementTestType,
)
from app.models.supported_bandwidths import get_supported_bandwidths
from app.models.test_case import CSV_FIELDNAMES, TestCase
from app.models.test_range import RangeId


def _build_case(
    *,
    bandwidth: float = 100.0,
    band: NRBand | str = NRBand.N78,
    test_type: MeasurementTestType = MeasurementTestType.HARMONIC,
    rb_allocation: RBAllocation = RBAllocation.INNER_FULL,
    test_channel: ChannelEnum | str = ChannelEnum.MID,
) -> TestCase:
    return TestCase(
        band=band,
        bandwidth=bandwidth,
        test_type=test_type,
        modulation=Modulation.QPSK,
        rb_allocation=rb_allocation,
        test_channel=test_channel,
        antenna_pol=AntennaPol.H,
        dut_axis=DUTAxis.X,
        dut_ant_position=DUTAntPosition.UPPER,
    )


def test_test_case_instantiation() -> None:
    case = _build_case()

    assert case.band is NRBand.N78
    assert case.bandwidth == 100.0
    assert case.generation is Generation.NR_SA
    assert case.scs_khz == 30
    assert case.factor_keyword == "6G HPF"
    assert case.mt8000_recall == "SA_TDD"
    assert case.turntable_speed == 3
    assert case.channel_number == 636666
    assert case.frequency_mhz == 3549.99
    assert case.test_type is MeasurementTestType.HARMONIC
    assert case.modulation is Modulation.QPSK
    assert case.rb_allocation is RBAllocation.INNER_FULL
    assert case.test_channel is ChannelEnum.MID
    assert case.test_range is RangeId.RANGE_6
    assert case.range_name == "range_6"
    assert case.antenna_pol is AntennaPol.H
    assert case.dut_axis is DUTAxis.X
    assert case.dut_ant_position is DUTAntPosition.UPPER


def test_test_case_coerces_test_channel_on_direct_instantiation() -> None:
    case = _build_case(test_channel="MID")

    assert case.test_channel is ChannelEnum.MID


def test_test_case_coerces_band_on_direct_instantiation() -> None:
    case = _build_case(band="N78")

    assert case.band is NRBand.N78


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


def test_test_case_rejects_legacy_bandwidth_units_at_instantiation() -> None:
    with pytest.raises(ValueError, match="Invalid bandwidth"):
        _build_case(bandwidth="100MHz")  # type: ignore[arg-type]


def test_test_case_rejects_unknown_test_channel_at_instantiation() -> None:
    with pytest.raises(ValueError, match="Invalid test_channel"):
        _build_case(test_channel="center")


def test_test_case_rejects_unknown_band_at_instantiation() -> None:
    with pytest.raises(ValueError, match="Invalid band"):
        _build_case(band="n99")


def test_test_case_rejects_unknown_dut_ant_position_at_instantiation() -> None:
    with pytest.raises(ValueError, match="Invalid dut_ant_position"):
        TestCase(
            band=NRBand.N78,
            bandwidth=100.0,
            test_type=MeasurementTestType.HARMONIC,
            modulation=Modulation.QPSK,
            rb_allocation=RBAllocation.INNER_FULL,
            test_channel=ChannelEnum.MID,
            antenna_pol=AntennaPol.H,
            dut_axis=DUTAxis.X,
            dut_ant_position="Middle",
        )


def test_test_case_rejects_unsupported_band_and_test_type_at_instantiation() -> None:
    with pytest.raises(ValueError, match="Bilog not supported"):
        _build_case(band="n5", test_type=MeasurementTestType.BILOG)


def test_test_case_rejects_unsupported_bandwidth_at_instantiation() -> None:
    with pytest.raises(
        ValueError,
        match=r"Unsupported bandwidth '60' for band 'n1'",
    ):
        _build_case(band="n1", bandwidth=60.0)


def test_test_case_exposes_supported_bandwidth_lookup_for_valid_band() -> None:
    assert get_supported_bandwidths("N78") == (
        10.0,
        15.0,
        20.0,
        25.0,
        30.0,
        40.0,
        50.0,
        60.0,
        70.0,
        80.0,
        90.0,
        100.0,
    )


def test_test_case_from_csv_row_resolves_range_from_band_and_test_type() -> None:
    case = TestCase.from_csv_row(
        {
            "generation": "NR_SA",
            "band": "n78",
            "bandwidth": "100",
            "test_type": "harmonic",
            "modulation": "QPSK",
            "rb_allocation": "Inner_Full",
            "test_channel": "mid",
            "antenna_pol": "H",
            "dut_axis": "X",
            "dut_ant_position": "Lower",
        }
    )

    assert case.test_type is MeasurementTestType.HARMONIC
    assert case.band is NRBand.N78
    assert case.bandwidth == 100.0
    assert case.test_channel is ChannelEnum.MID
    assert case.test_range is RangeId.RANGE_6
    assert case.rb_size == 135
    assert case.rb_offset == 67
    assert case.dut_ant_position is DUTAntPosition.LOWER


def test_test_case_from_csv_row_parses_decimal_bandwidth() -> None:
    case = TestCase.from_csv_row(
        {
            "generation": "NR_SA",
            "band": "n78",
            "bandwidth": "100.0",
            "test_type": "harmonic",
            "modulation": "QPSK",
            "rb_allocation": "Inner_Full",
            "test_channel": "mid",
            "antenna_pol": "H",
            "dut_axis": "X",
            "dut_ant_position": "Upper",
        }
    )

    assert case.bandwidth == 100.0


def test_test_case_from_csv_row_parses_band_case_insensitively() -> None:
    case = TestCase.from_csv_row(
        {
            "generation": "NR_SA",
            "band": "N78",
            "bandwidth": "100",
            "test_type": "harmonic",
            "modulation": "QPSK",
            "rb_allocation": "Inner_Full",
            "test_channel": "mid",
            "antenna_pol": "H",
            "dut_axis": "X",
            "dut_ant_position": "Upper",
        }
    )

    assert case.band is NRBand.N78


def test_test_case_from_csv_row_parses_test_channel_case_insensitively() -> None:
    case = TestCase.from_csv_row(
        {
            "generation": "NR_SA",
            "band": "n78",
            "bandwidth": "100",
            "test_type": "harmonic",
            "modulation": "QPSK",
            "rb_allocation": "Inner_Full",
            "test_channel": "MID",
            "antenna_pol": "H",
            "dut_axis": "X",
            "dut_ant_position": "Upper",
        }
    )

    assert case.test_channel is ChannelEnum.MID


@pytest.mark.parametrize(
    ("band", "bandwidth", "test_type", "expected_range"),
    [
        ("n5", "20", "harmonic", RangeId.RANGE_3),
        ("n78", "100", "harmonic", RangeId.RANGE_6),
    ],
)
def test_test_case_from_csv_row_uses_representative_range_mappings(
    band: str,
    bandwidth: str,
    test_type: str,
    expected_range: RangeId,
) -> None:
    case = TestCase.from_csv_row(
        {
            "generation": "NR_SA",
            "band": band,
            "bandwidth": bandwidth,
            "test_type": test_type,
            "modulation": "QPSK",
            "rb_allocation": "Inner_Full",
            "test_channel": "mid",
            "antenna_pol": "H",
            "dut_axis": "X",
            "dut_ant_position": "Upper",
        }
    )

    assert case.test_range is expected_range


def test_test_case_from_csv_row_parses_nr_nsa_generation() -> None:
    case = TestCase.from_csv_row(
        {
            "generation": "NR_NSA",
            "band": "n78",
            "bandwidth": "100",
            "test_type": "harmonic",
            "modulation": "QPSK",
            "rb_allocation": "Inner_Full",
            "test_channel": "mid",
            "antenna_pol": "H",
            "dut_axis": "X",
            "dut_ant_position": "Upper",
        }
    )

    assert case.generation is Generation.NR_NSA


def test_test_case_from_csv_row_rejects_unknown_generation() -> None:
    with pytest.raises(ValueError, match="Invalid generation"):
        TestCase.from_csv_row(
            {
                "generation": "UNKNOWN",
                "band": "n78",
                "bandwidth": "100",
                "test_type": "harmonic",
                "modulation": "QPSK",
                "rb_allocation": "Inner_Full",
                "test_channel": "mid",
                "antenna_pol": "H",
                "dut_axis": "X",
                "dut_ant_position": "Upper",
            }
        )
def test_test_case_to_csv_row_uses_external_csv_schema_only() -> None:
    row = _build_case().to_csv_row()

    assert list(row) == list(CSV_FIELDNAMES)
    assert row["generation"] == "NR_SA"
    assert row["band"] == "n78"
    assert row["bandwidth"] == "100"
    assert row["test_type"] == "harmonic"
    assert row["test_channel"] == "mid"
    assert row["dut_ant_position"] == "Upper"
    assert "test_range" not in row


def test_test_case_from_csv_row_rejects_missing_test_type() -> None:
    with pytest.raises(ValueError, match="Missing required field: test_type"):
        TestCase.from_csv_row(
            {
                "generation": "NR_SA",
                "band": "n78",
                "bandwidth": "100",
                "modulation": "QPSK",
                "rb_allocation": "Inner_Full",
                "test_channel": "mid",
                "antenna_pol": "H",
                "dut_axis": "X",
                "dut_ant_position": "Upper",
            }
        )


def test_test_case_from_csv_row_rejects_unknown_test_type() -> None:
    with pytest.raises(ValueError, match="Invalid test_type"):
        TestCase.from_csv_row(
            {
                "generation": "NR_SA",
                "band": "n78",
                "bandwidth": "100",
                "test_type": "unknown",
                "modulation": "QPSK",
                "rb_allocation": "Inner_Full",
                "test_channel": "mid",
                "antenna_pol": "H",
                "dut_axis": "X",
                "dut_ant_position": "Upper",
            }
        )


def test_test_case_from_csv_row_rejects_unknown_test_channel() -> None:
    with pytest.raises(ValueError, match="Invalid test_channel"):
        TestCase.from_csv_row(
            {
                "generation": "NR_SA",
                "band": "n78",
                "bandwidth": "100",
                "test_type": "harmonic",
                "modulation": "QPSK",
                "rb_allocation": "Inner_Full",
                "test_channel": "center",
                "antenna_pol": "H",
                "dut_axis": "X",
            }
        )


def test_test_case_from_csv_row_rejects_unknown_dut_ant_position() -> None:
    with pytest.raises(ValueError, match="Invalid dut_ant_position"):
        TestCase.from_csv_row(
            {
                "generation": "NR_SA",
                "band": "n78",
                "bandwidth": "100",
                "test_type": "harmonic",
                "modulation": "QPSK",
                "rb_allocation": "Inner_Full",
                "test_channel": "mid",
                "antenna_pol": "H",
                "dut_axis": "X",
                "dut_ant_position": "Middle",
            }
        )


def test_test_case_from_csv_row_rejects_unknown_band() -> None:
    with pytest.raises(ValueError, match="Invalid band"):
        TestCase.from_csv_row(
            {
                "generation": "NR_SA",
                "band": "n99",
                "bandwidth": "100",
                "test_type": "harmonic",
                "modulation": "QPSK",
                "rb_allocation": "Inner_Full",
                "test_channel": "mid",
                "antenna_pol": "H",
                "dut_axis": "X",
                "dut_ant_position": "Upper",
            }
        )


def test_test_case_from_csv_row_rejects_unsupported_band_and_test_type() -> None:
    with pytest.raises(ValueError, match="Bilog not supported"):
        TestCase.from_csv_row(
            {
                "generation": "NR_SA",
                "band": "n5",
                "bandwidth": "100",
                "test_type": "bilog",
                "modulation": "QPSK",
                "rb_allocation": "Inner_Full",
                "test_channel": "mid",
                "antenna_pol": "H",
                "dut_axis": "X",
                "dut_ant_position": "Upper",
            }
        )


@pytest.mark.parametrize("bandwidth", ["100MHz", "100 MHz"])
def test_test_case_from_csv_row_rejects_bandwidth_with_unit_suffix(
    bandwidth: str,
) -> None:
    with pytest.raises(ValueError, match="Invalid bandwidth"):
        TestCase.from_csv_row(
            {
                "generation": "NR_SA",
                "band": "n78",
                "bandwidth": bandwidth,
                "test_type": "harmonic",
                "modulation": "QPSK",
                "rb_allocation": "Inner_Full",
                "test_channel": "mid",
                "antenna_pol": "H",
                "dut_axis": "X",
            }
        )
