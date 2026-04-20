from __future__ import annotations

import pytest

from app.models.enums import NRBand, TestChannel as ChannelEnum
from app.models.nr_channel_lookup import (
    resolve_call_channel,
    resolve_target_frequency_mhz,
)


@pytest.mark.parametrize(
    ("band", "bandwidth", "test_channel", "expected_channel", "expected_frequency"),
    [
        (NRBand.N1, 5.0, ChannelEnum.LOW, 384500, 1922.5),
        ("n3", 50.0, ChannelEnum.HIGH, 352000, 1760.0),
        ("n5", 20.0, ChannelEnum.MID, 167300, 836.5),
        ("n7", 35.0, ChannelEnum.HIGH, 510500, 2552.5),
        ("n8", 10.0, ChannelEnum.MID, 179500, 897.5),
        ("n20", 20.0, ChannelEnum.LOW, 168400, 842.0),
        ("n26", 15.0, ChannelEnum.HIGH, 168300, 841.5),
        ("n28", 20.0, ChannelEnum.MID, 145600, 728.0),
        ("n38", 40.0, ChannelEnum.HIGH, 520000, 2600.0),
        ("n40", 100.0, ChannelEnum.LOW, 470000, 2350.0),
        ("n41", 10.0, ChannelEnum.HIGH, 537000, 2685.0),
        ("n71", 5.0, ChannelEnum.MID, 136100, 680.5),
        ("n77", 70.0, ChannelEnum.HIGH, 677666, 4164.99),
        ("n78", 100.0, ChannelEnum.MID, 636666, 3549.99),
        ("n79", 80.0, ChannelEnum.LOW, 696000, 4440.0),
    ],
)
def test_lookup_resolves_representative_channel_profiles(
    band: NRBand | str,
    bandwidth: float,
    test_channel: ChannelEnum,
    expected_channel: int,
    expected_frequency: float,
) -> None:
    assert resolve_call_channel(band, bandwidth, test_channel) == expected_channel
    assert (
        resolve_target_frequency_mhz(band, bandwidth, test_channel)
        == expected_frequency
    )


def test_lookup_accepts_numeric_band_label() -> None:
    assert resolve_call_channel("78", 100.0, ChannelEnum.HIGH) == 650000


@pytest.mark.parametrize("bandwidth", [25.0, 30.0])
def test_lookup_rejects_missing_n28_mid_channel(bandwidth: float) -> None:
    with pytest.raises(
        ValueError,
        match=(
            rf"band='n28'.*bandwidth='{int(bandwidth)}'.*test_channel='mid'"
        ),
    ):
        resolve_call_channel("n28", bandwidth, ChannelEnum.MID)


def test_lookup_rejects_missing_bandwidth_definition() -> None:
    with pytest.raises(
        ValueError,
        match=r"band='n71'.*bandwidth='30'.*test_channel='mid'",
    ):
        resolve_target_frequency_mhz("n71", 30.0, ChannelEnum.MID)
