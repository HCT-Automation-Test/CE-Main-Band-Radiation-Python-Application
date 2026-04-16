from __future__ import annotations

import pytest

from app.models.supported_bandwidths import (
    get_supported_bandwidths,
    validate_supported_bandwidth,
)


@pytest.mark.parametrize(
    ("band", "bandwidth"),
    [
        ("n1", 45.0),
        ("n5", 20.0),
        ("n28", 30.0),
        ("n38", 25.0),
        ("n40", 90.0),
        ("n78", 100.0),
    ],
)
def test_validate_supported_bandwidth_accepts_representative_combinations(
    band: str,
    bandwidth: float,
) -> None:
    validate_supported_bandwidth(band, bandwidth)


@pytest.mark.parametrize(
    ("band", "bandwidth"),
    [
        ("n20", 25.0),
        ("n38", 50.0),
        ("n40", 35.0),
        ("n71", 30.0),
        ("n79", 5.0),
    ],
)
def test_validate_supported_bandwidth_rejects_unsupported_combinations(
    band: str,
    bandwidth: float,
) -> None:
    with pytest.raises(
        ValueError,
        match=rf"Unsupported bandwidth '{int(bandwidth)}' for band '{band}'",
    ):
        validate_supported_bandwidth(band, bandwidth)


def test_get_supported_bandwidths_normalizes_band_label() -> None:
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
