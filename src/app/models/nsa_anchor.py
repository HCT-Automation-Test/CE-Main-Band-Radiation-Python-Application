"""NR NSA LTE Anchor Band 정책."""
from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import Generation, LTEBand


SUPPORTED_NSA_ANCHOR_BANDS: tuple[LTEBand, ...] = (
    LTEBand.B1,
    LTEBand.B3,
    LTEBand.B7,
    LTEBand.B5,
    LTEBand.B8,
    LTEBand.B20,
    LTEBand.B28,
    LTEBand.B38,
    LTEBand.B40,
    LTEBand.B41,
)


@dataclass(frozen=True)
class NSAAnchorChannels:
    """고정 MID/5 MHz NSA Anchor의 UL/DL Channel."""

    dl_channel: int
    ul_channel: int


_NSA_ANCHOR_CHANNELS_BY_BAND: dict[LTEBand, NSAAnchorChannels] = {
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


def validate_supported_nsa_anchor_band(anchor_band: LTEBand) -> None:
    """지원하는 NSA Anchor Band인지 검증한다."""

    if anchor_band in SUPPORTED_NSA_ANCHOR_BANDS:
        return

    supported = ", ".join(band.value for band in SUPPORTED_NSA_ANCHOR_BANDS)
    raise ValueError(
        f"Unsupported NSA anchor_band: {anchor_band.value!r}. Supported: {supported}"
    )


def resolve_nsa_anchor_channels(anchor_band: LTEBand) -> NSAAnchorChannels:
    """지원 Anchor Band의 고정 MID/5 MHz UL/DL Channel을 반환한다."""

    validate_supported_nsa_anchor_band(anchor_band)
    return _NSA_ANCHOR_CHANNELS_BY_BAND[anchor_band]


def validate_anchor_band_for_generation(
    generation: Generation,
    anchor_band: LTEBand | None,
) -> None:
    """Generation별 Anchor Band 필수·금지 규칙을 검증한다."""

    if generation is Generation.NR_NSA:
        if anchor_band is None:
            raise ValueError("NR_NSA requires anchor_band")
        validate_supported_nsa_anchor_band(anchor_band)
        return

    if anchor_band is not None:
        raise ValueError(f"{generation.value} must not define anchor_band")
