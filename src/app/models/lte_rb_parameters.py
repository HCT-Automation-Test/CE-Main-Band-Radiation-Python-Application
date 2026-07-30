"""LTE RB allocation별 RB size/offset lookup."""
from __future__ import annotations

import math

from app.models.enums import LTERBAllocation

_LTE_RB_OFFSET_BY_KEY: dict[tuple[float, LTERBAllocation], int] = {
    (1.4, LTERBAllocation.LOW): 0,
    (1.4, LTERBAllocation.MID): 3,
    (1.4, LTERBAllocation.HIGH): 5,
    (3.0, LTERBAllocation.LOW): 0,
    (3.0, LTERBAllocation.MID): 7,
    (3.0, LTERBAllocation.HIGH): 14,
    (5.0, LTERBAllocation.LOW): 0,
    (5.0, LTERBAllocation.MID): 12,
    (5.0, LTERBAllocation.HIGH): 24,
    (10.0, LTERBAllocation.LOW): 0,
    (10.0, LTERBAllocation.MID): 24,
    (10.0, LTERBAllocation.HIGH): 49,
    (15.0, LTERBAllocation.LOW): 0,
    (15.0, LTERBAllocation.MID): 36,
    (15.0, LTERBAllocation.HIGH): 74,
    (20.0, LTERBAllocation.LOW): 0,
    (20.0, LTERBAllocation.MID): 49,
    (20.0, LTERBAllocation.HIGH): 99,
}


def _normalize_bandwidth_key(bandwidth: float) -> float:
    if isinstance(bandwidth, bool) or not isinstance(bandwidth, int | float):
        raise ValueError(f"Invalid bandwidth: {bandwidth!r}")

    normalized = float(bandwidth)
    if not math.isfinite(normalized):
        raise ValueError(f"Invalid bandwidth: {bandwidth!r}")
    return float(format(normalized, ".15g"))


def resolve_lte_rb_parameters(
    bandwidth: float,
    rb_allocation: LTERBAllocation,
) -> tuple[int, int]:
    """LTE RB Size 1과 선택 위치의 Offset을 반환한다."""

    normalized_bandwidth = _normalize_bandwidth_key(bandwidth)
    try:
        offset = _LTE_RB_OFFSET_BY_KEY[(normalized_bandwidth, rb_allocation)]
    except KeyError as exc:
        allocation_value = getattr(rb_allocation, "value", rb_allocation)
        raise ValueError(
            "Unsupported LTE RB allocation mapping for "
            f"bandwidth={format(normalized_bandwidth, '.15g')!r}, "
            f"rb_allocation={allocation_value!r}"
        ) from exc
    return 1, offset
