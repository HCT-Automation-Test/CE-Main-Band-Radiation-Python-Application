from __future__ import annotations

import pytest

from app.models.enums import LTEBand
from app.models.lte_supported_bandwidths import (
    get_lte_supported_bandwidths,
    validate_lte_supported_bandwidth,
)

EXPECTED_BANDWIDTHS = {
    LTEBand.B1: (5.0, 10.0, 15.0, 20.0),
    LTEBand.B3: (1.4, 3.0, 5.0, 10.0, 15.0, 20.0),
    LTEBand.B5: (1.4, 3.0, 5.0, 10.0),
    LTEBand.B7: (5.0, 10.0, 15.0, 20.0),
    LTEBand.B8: (1.4, 3.0, 5.0, 10.0),
    LTEBand.B20: (5.0, 10.0, 15.0, 20.0),
    LTEBand.B28: (3.0, 5.0, 10.0, 15.0, 20.0),
    LTEBand.B34: (5.0, 10.0, 15.0),
    LTEBand.B38: (5.0, 10.0, 15.0, 20.0),
    LTEBand.B40: (5.0, 10.0, 15.0, 20.0),
    LTEBand.B41: (5.0, 10.0, 15.0, 20.0),
}


def test_lte_bandwidth_table_matches_all_46_combinations() -> None:
    actual = {
        band: get_lte_supported_bandwidths(band)
        for band in LTEBand
    }

    assert actual == EXPECTED_BANDWIDTHS
    assert sum(len(values) for values in actual.values()) == 46


@pytest.mark.parametrize(
    ("band", "bandwidth"),
    [
        (band, bandwidth)
        for band, bandwidths in EXPECTED_BANDWIDTHS.items()
        for bandwidth in bandwidths
    ],
)
def test_validate_lte_supported_bandwidth_accepts_all_final_rows(
    band: LTEBand,
    bandwidth: float,
) -> None:
    validate_lte_supported_bandwidth(band, bandwidth)


def test_validate_lte_supported_bandwidth_rejects_unsupported_combination() -> None:
    with pytest.raises(ValueError, match="Unsupported LTE bandwidth '20'.*'B34'"):
        validate_lte_supported_bandwidth(LTEBand.B34, 20.0)
