"""RB allocation별 RB size/offset lookup."""
from __future__ import annotations

import math

from app.models.band_group import find_band_group
from app.models.enums import RBAllocation

_RB_PARAMETERS_BY_KEY: dict[tuple[float, int, RBAllocation], tuple[int, int]] = {
    (3.0, 15, RBAllocation.INNER_FULL): (6, 4),
    (3.0, 15, RBAllocation.INNER_1RB_LEFT): (1, 1),
    (3.0, 15, RBAllocation.INNER_1RB_RIGHT): (1, 13),
    (5.0, 15, RBAllocation.INNER_FULL): (12, 6),
    (5.0, 15, RBAllocation.INNER_1RB_LEFT): (1, 1),
    (5.0, 15, RBAllocation.INNER_1RB_RIGHT): (1, 23),
    (5.0, 30, RBAllocation.INNER_FULL): (5, 1),
    (5.0, 30, RBAllocation.INNER_1RB_LEFT): (1, 1),
    (5.0, 30, RBAllocation.INNER_1RB_RIGHT): (1, 9),
    (10.0, 15, RBAllocation.INNER_FULL): (25, 12),
    (10.0, 15, RBAllocation.INNER_1RB_LEFT): (1, 1),
    (10.0, 15, RBAllocation.INNER_1RB_RIGHT): (1, 50),
    (10.0, 30, RBAllocation.INNER_FULL): (12, 6),
    (10.0, 30, RBAllocation.INNER_1RB_LEFT): (1, 1),
    (10.0, 30, RBAllocation.INNER_1RB_RIGHT): (1, 22),
    (15.0, 15, RBAllocation.INNER_FULL): (38, 18),
    (15.0, 15, RBAllocation.INNER_1RB_LEFT): (1, 1),
    (15.0, 15, RBAllocation.INNER_1RB_RIGHT): (1, 77),
    (15.0, 30, RBAllocation.INNER_FULL): (18, 9),
    (15.0, 30, RBAllocation.INNER_1RB_LEFT): (1, 1),
    (15.0, 30, RBAllocation.INNER_1RB_RIGHT): (1, 36),
    (20.0, 15, RBAllocation.INNER_FULL): (50, 25),
    (20.0, 15, RBAllocation.INNER_1RB_LEFT): (1, 1),
    (20.0, 15, RBAllocation.INNER_1RB_RIGHT): (1, 104),
    (20.0, 30, RBAllocation.INNER_FULL): (25, 12),
    (20.0, 30, RBAllocation.INNER_1RB_LEFT): (1, 1),
    (20.0, 30, RBAllocation.INNER_1RB_RIGHT): (1, 49),
    (25.0, 15, RBAllocation.INNER_FULL): (64, 32),
    (25.0, 15, RBAllocation.INNER_1RB_LEFT): (1, 1),
    (25.0, 15, RBAllocation.INNER_1RB_RIGHT): (1, 131),
    (25.0, 30, RBAllocation.INNER_FULL): (32, 16),
    (25.0, 30, RBAllocation.INNER_1RB_LEFT): (1, 1),
    (25.0, 30, RBAllocation.INNER_1RB_RIGHT): (1, 63),
    (30.0, 15, RBAllocation.INNER_FULL): (80, 40),
    (30.0, 15, RBAllocation.INNER_1RB_LEFT): (1, 1),
    (30.0, 15, RBAllocation.INNER_1RB_RIGHT): (1, 158),
    (30.0, 30, RBAllocation.INNER_FULL): (36, 18),
    (30.0, 30, RBAllocation.INNER_1RB_LEFT): (1, 1),
    (30.0, 30, RBAllocation.INNER_1RB_RIGHT): (1, 76),
    (35.0, 15, RBAllocation.INNER_FULL): (90, 45),
    (35.0, 15, RBAllocation.INNER_1RB_LEFT): (1, 1),
    (35.0, 15, RBAllocation.INNER_1RB_RIGHT): (1, 186),
    (35.0, 30, RBAllocation.INNER_FULL): (45, 22),
    (35.0, 30, RBAllocation.INNER_1RB_LEFT): (1, 1),
    (35.0, 30, RBAllocation.INNER_1RB_RIGHT): (1, 90),
    (40.0, 15, RBAllocation.INNER_FULL): (108, 54),
    (40.0, 15, RBAllocation.INNER_1RB_LEFT): (1, 1),
    (40.0, 15, RBAllocation.INNER_1RB_RIGHT): (1, 214),
    (40.0, 30, RBAllocation.INNER_FULL): (50, 25),
    (40.0, 30, RBAllocation.INNER_1RB_LEFT): (1, 1),
    (40.0, 30, RBAllocation.INNER_1RB_RIGHT): (1, 104),
    (45.0, 15, RBAllocation.INNER_FULL): (120, 60),
    (45.0, 15, RBAllocation.INNER_1RB_LEFT): (1, 1),
    (45.0, 15, RBAllocation.INNER_1RB_RIGHT): (1, 240),
    (45.0, 30, RBAllocation.INNER_FULL): (54, 27),
    (45.0, 30, RBAllocation.INNER_1RB_LEFT): (1, 1),
    (45.0, 30, RBAllocation.INNER_1RB_RIGHT): (1, 117),
    (50.0, 15, RBAllocation.INNER_FULL): (135, 67),
    (50.0, 15, RBAllocation.INNER_1RB_LEFT): (1, 1),
    (50.0, 15, RBAllocation.INNER_1RB_RIGHT): (1, 268),
    (50.0, 30, RBAllocation.INNER_FULL): (64, 32),
    (50.0, 30, RBAllocation.INNER_1RB_LEFT): (1, 1),
    (50.0, 30, RBAllocation.INNER_1RB_RIGHT): (1, 131),
    (60.0, 30, RBAllocation.INNER_FULL): (81, 40),
    (60.0, 30, RBAllocation.INNER_1RB_LEFT): (1, 1),
    (60.0, 30, RBAllocation.INNER_1RB_RIGHT): (1, 160),
    (70.0, 30, RBAllocation.INNER_FULL): (90, 45),
    (70.0, 30, RBAllocation.INNER_1RB_LEFT): (1, 1),
    (70.0, 30, RBAllocation.INNER_1RB_RIGHT): (1, 187),
    (80.0, 30, RBAllocation.INNER_FULL): (108, 54),
    (80.0, 30, RBAllocation.INNER_1RB_LEFT): (1, 1),
    (80.0, 30, RBAllocation.INNER_1RB_RIGHT): (1, 215),
    (90.0, 30, RBAllocation.INNER_FULL): (120, 60),
    (90.0, 30, RBAllocation.INNER_1RB_LEFT): (1, 1),
    (90.0, 30, RBAllocation.INNER_1RB_RIGHT): (1, 243),
    (100.0, 30, RBAllocation.INNER_FULL): (135, 67),
    (100.0, 30, RBAllocation.INNER_1RB_LEFT): (1, 1),
    (100.0, 30, RBAllocation.INNER_1RB_RIGHT): (1, 271),
}


def _normalize_bandwidth_key(bandwidth: float) -> float:
    if isinstance(bandwidth, bool) or not isinstance(bandwidth, int | float):
        raise ValueError(f"Invalid bandwidth: {bandwidth!r}")

    normalized = float(bandwidth)
    if not math.isfinite(normalized):
        raise ValueError(f"Invalid bandwidth: {bandwidth!r}")
    return float(format(normalized, ".15g"))


def _format_bandwidth_value(bandwidth: float) -> str:
    return format(_normalize_bandwidth_key(bandwidth), ".15g")


def resolve_rb_parameters(
    band: str,
    bandwidth: float,
    rb_allocation: RBAllocation,
) -> tuple[int, int]:
    """RB allocation 표에서 RB size/offset을 계산한다.

    OFDM는 현재 스펙 범위 밖이므로 DFT-s 조합만 지원한다.
    """

    scs_khz = find_band_group(band).scs_khz
    normalized_bandwidth = _normalize_bandwidth_key(bandwidth)
    key = (normalized_bandwidth, scs_khz, rb_allocation)
    try:
        return _RB_PARAMETERS_BY_KEY[key]
    except KeyError as exc:
        raise ValueError(
            "Unsupported RB allocation mapping for "
            f"band={band!r}, "
            f"bandwidth={_format_bandwidth_value(normalized_bandwidth)!r}, "
            f"scs_khz={scs_khz}, "
            f"rb_allocation={rb_allocation.value!r}"
        ) from exc
