from __future__ import annotations

import pytest

from app.models.enums import LTEBand, TestChannel as ChannelEnum
from app.models.lte_channel_lookup import resolve_arfcn, resolve_dl_channel
from app.models.nsa_anchor import (
    NSAAnchorChannels,
    SUPPORTED_NSA_ANCHOR_BANDS,
    resolve_nsa_anchor_channels,
)


EXPECTED_NSA_ANCHOR_CHANNELS = {
    LTEBand.B1: NSAAnchorChannels(dl_channel=300, ul_channel=18300),
    LTEBand.B3: NSAAnchorChannels(dl_channel=1575, ul_channel=19575),
    LTEBand.B7: NSAAnchorChannels(dl_channel=3100, ul_channel=21100),
    LTEBand.B5: NSAAnchorChannels(dl_channel=2525, ul_channel=20525),
    LTEBand.B8: NSAAnchorChannels(dl_channel=3625, ul_channel=21625),
    LTEBand.B20: NSAAnchorChannels(dl_channel=6300, ul_channel=24300),
    LTEBand.B28: NSAAnchorChannels(dl_channel=9385, ul_channel=27385),
    LTEBand.B38: NSAAnchorChannels(dl_channel=38000, ul_channel=38000),
    LTEBand.B40: NSAAnchorChannels(dl_channel=39150, ul_channel=39150),
    LTEBand.B41: NSAAnchorChannels(dl_channel=40620, ul_channel=40620),
}


def test_resolve_nsa_anchor_channels_returns_all_fixed_mid_5mhz_values() -> None:
    assert set(SUPPORTED_NSA_ANCHOR_BANDS) == set(EXPECTED_NSA_ANCHOR_CHANNELS)

    for band, expected in EXPECTED_NSA_ANCHOR_CHANNELS.items():
        assert resolve_nsa_anchor_channels(band) == expected


def test_nsa_anchor_channels_match_lte_mid_5mhz_lookup() -> None:
    for band in SUPPORTED_NSA_ANCHOR_BANDS:
        channels = resolve_nsa_anchor_channels(band)
        assert channels.dl_channel == resolve_dl_channel(band, 5.0, ChannelEnum.MID)
        assert channels.ul_channel == resolve_arfcn(band, 5.0, ChannelEnum.MID)


def test_b5_is_supported_and_b34_is_rejected() -> None:
    assert resolve_nsa_anchor_channels(LTEBand.B5) == NSAAnchorChannels(
        dl_channel=2525,
        ul_channel=20525,
    )

    with pytest.raises(ValueError, match="Unsupported NSA anchor_band: 'B34'"):
        resolve_nsa_anchor_channels(LTEBand.B34)
