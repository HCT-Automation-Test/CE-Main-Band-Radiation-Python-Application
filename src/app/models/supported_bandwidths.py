"""NR Band별 지원 bandwidth lookup."""
from __future__ import annotations

import math

from app.models.switch_box import parse_band_number

_SUPPORTED_BANDWIDTHS_BY_BAND: dict[int, tuple[float, ...]] = {
    1: (5.0, 10.0, 15.0, 20.0, 25.0, 30.0, 40.0, 45.0, 50.0),
    3: (5.0, 10.0, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0, 45.0, 50.0),
    5: (5.0, 10.0, 15.0, 20.0),
    7: (5.0, 10.0, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0, 50.0),
    8: (5.0, 10.0, 15.0, 20.0),
    20: (5.0, 10.0, 15.0, 20.0),
    26: (5.0, 10.0, 15.0, 20.0),
    28: (5.0, 10.0, 15.0, 20.0, 25.0, 30.0),
    38: (10.0, 15.0, 20.0, 25.0, 30.0, 40.0),
    40: (10.0, 15.0, 20.0, 25.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0),
    41: (10.0, 15.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0),
    71: (5.0, 10.0, 15.0, 20.0),
    77: (10.0, 15.0, 20.0, 25.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0),
    78: (10.0, 15.0, 20.0, 25.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0),
    79: (10.0, 20.0, 40.0, 50.0, 60.0, 80.0, 100.0),
}


def _normalize_bandwidth_value(bandwidth: float) -> float:
    if isinstance(bandwidth, bool) or not isinstance(bandwidth, int | float):
        raise ValueError(f"Invalid bandwidth: {bandwidth!r}")

    normalized = float(bandwidth)
    if not math.isfinite(normalized):
        raise ValueError(f"Invalid bandwidth: {bandwidth!r}")
    return float(format(normalized, ".15g"))


def _format_bandwidth_value(bandwidth: float) -> str:
    return format(_normalize_bandwidth_value(bandwidth), ".15g")


def _format_supported_bandwidths(bandwidths: tuple[float, ...]) -> str:
    return ", ".join(_format_bandwidth_value(bandwidth) for bandwidth in bandwidths)


def get_supported_bandwidths(band: str) -> tuple[float, ...]:
    """band별 지원 bandwidth 목록을 반환한다."""

    band_number = parse_band_number(band)
    try:
        return _SUPPORTED_BANDWIDTHS_BY_BAND[band_number]
    except KeyError as exc:
        raise ValueError(f"No supported bandwidth definition for band 'n{band_number}'") from exc


def validate_supported_bandwidth(band: str, bandwidth: float) -> None:
    """band/bandwidth 조합이 표에 없으면 예외를 발생시킨다."""

    band_number = parse_band_number(band)
    supported_bandwidths = get_supported_bandwidths(band)
    normalized_bandwidth = _normalize_bandwidth_value(bandwidth)
    if normalized_bandwidth in supported_bandwidths:
        return

    raise ValueError(
        f"Unsupported bandwidth '{_format_bandwidth_value(normalized_bandwidth)}' "
        f"for band 'n{band_number}'. "
        f"Supported bandwidths: {_format_supported_bandwidths(supported_bandwidths)}"
    )
