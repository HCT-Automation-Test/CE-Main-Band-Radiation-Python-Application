"""LTE Band별 지원 bandwidth lookup."""
from __future__ import annotations

import math

from app.models.enums import LTEBand

_SUPPORTED_BANDWIDTHS_BY_BAND: dict[LTEBand, tuple[float, ...]] = {
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


def _coerce_lte_band(band: LTEBand | str) -> LTEBand:
    if isinstance(band, LTEBand):
        return band

    normalized = str(band).strip()
    for member in LTEBand:
        if member.value.lower() == normalized.lower():
            return member
    raise ValueError(f"Unknown LTE band: {band!r}")


def _normalize_bandwidth_value(bandwidth: float) -> float:
    if isinstance(bandwidth, bool) or not isinstance(bandwidth, int | float):
        raise ValueError(f"Invalid bandwidth: {bandwidth!r}")

    normalized = float(bandwidth)
    if not math.isfinite(normalized):
        raise ValueError(f"Invalid bandwidth: {bandwidth!r}")
    return float(format(normalized, ".15g"))


def _format_bandwidth_value(bandwidth: float) -> str:
    return format(_normalize_bandwidth_value(bandwidth), ".15g")


def get_lte_supported_bandwidths(band: LTEBand | str) -> tuple[float, ...]:
    """LTE band별 지원 bandwidth 목록을 반환한다."""

    band_key = _coerce_lte_band(band)
    return _SUPPORTED_BANDWIDTHS_BY_BAND[band_key]


def validate_lte_supported_bandwidth(
    band: LTEBand | str,
    bandwidth: float,
) -> None:
    """LTE band/bandwidth 조합이 최종 표에 없으면 예외를 발생시킨다."""

    band_key = _coerce_lte_band(band)
    normalized_bandwidth = _normalize_bandwidth_value(bandwidth)
    supported_bandwidths = get_lte_supported_bandwidths(band_key)
    if normalized_bandwidth in supported_bandwidths:
        return

    formatted_supported = ", ".join(
        _format_bandwidth_value(value) for value in supported_bandwidths
    )
    raise ValueError(
        f"Unsupported LTE bandwidth '{_format_bandwidth_value(normalized_bandwidth)}' "
        f"for band '{band_key.value}'. "
        f"Supported bandwidths: {formatted_supported}"
    )
