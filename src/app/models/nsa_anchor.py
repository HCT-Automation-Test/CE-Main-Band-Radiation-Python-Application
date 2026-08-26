"""NR NSA LTE Anchor Band 정책."""
from __future__ import annotations

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


def validate_supported_nsa_anchor_band(anchor_band: LTEBand) -> None:
    """지원하는 NSA Anchor Band인지 검증한다."""

    if anchor_band in SUPPORTED_NSA_ANCHOR_BANDS:
        return

    supported = ", ".join(band.value for band in SUPPORTED_NSA_ANCHOR_BANDS)
    raise ValueError(
        f"Unsupported NSA anchor_band: {anchor_band.value!r}. Supported: {supported}"
    )


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
