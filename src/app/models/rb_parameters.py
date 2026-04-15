"""RB allocation별 RB size/offset lookup."""
from __future__ import annotations

from app.models.band_group import find_band_group
from app.models.enums import RBAllocation

_RB_PARAMETERS_BY_KEY: dict[tuple[str, int, RBAllocation], tuple[int, int]] = {
    ("3MHz", 15, RBAllocation.INNER_FULL): (6, 4),
    ("3MHz", 15, RBAllocation.INNER_1RB_LEFT): (1, 1),
    ("3MHz", 15, RBAllocation.INNER_1RB_RIGHT): (1, 13),
    ("5MHz", 15, RBAllocation.INNER_FULL): (12, 6),
    ("5MHz", 15, RBAllocation.INNER_1RB_LEFT): (1, 1),
    ("5MHz", 15, RBAllocation.INNER_1RB_RIGHT): (1, 23),
    ("5MHz", 30, RBAllocation.INNER_FULL): (5, 1),
    ("5MHz", 30, RBAllocation.INNER_1RB_LEFT): (1, 1),
    ("5MHz", 30, RBAllocation.INNER_1RB_RIGHT): (1, 9),
    ("10MHz", 15, RBAllocation.INNER_FULL): (25, 12),
    ("10MHz", 15, RBAllocation.INNER_1RB_LEFT): (1, 1),
    ("10MHz", 15, RBAllocation.INNER_1RB_RIGHT): (1, 50),
    ("10MHz", 30, RBAllocation.INNER_FULL): (12, 6),
    ("10MHz", 30, RBAllocation.INNER_1RB_LEFT): (1, 1),
    ("10MHz", 30, RBAllocation.INNER_1RB_RIGHT): (1, 22),
    ("15MHz", 15, RBAllocation.INNER_FULL): (38, 18),
    ("15MHz", 15, RBAllocation.INNER_1RB_LEFT): (1, 1),
    ("15MHz", 15, RBAllocation.INNER_1RB_RIGHT): (1, 77),
    ("15MHz", 30, RBAllocation.INNER_FULL): (18, 9),
    ("15MHz", 30, RBAllocation.INNER_1RB_LEFT): (1, 1),
    ("15MHz", 30, RBAllocation.INNER_1RB_RIGHT): (1, 36),
    ("20MHz", 15, RBAllocation.INNER_FULL): (50, 25),
    ("20MHz", 15, RBAllocation.INNER_1RB_LEFT): (1, 1),
    ("20MHz", 15, RBAllocation.INNER_1RB_RIGHT): (1, 104),
    ("20MHz", 30, RBAllocation.INNER_FULL): (25, 12),
    ("20MHz", 30, RBAllocation.INNER_1RB_LEFT): (1, 1),
    ("20MHz", 30, RBAllocation.INNER_1RB_RIGHT): (1, 49),
    ("25MHz", 15, RBAllocation.INNER_FULL): (64, 32),
    ("25MHz", 15, RBAllocation.INNER_1RB_LEFT): (1, 1),
    ("25MHz", 15, RBAllocation.INNER_1RB_RIGHT): (1, 131),
    ("25MHz", 30, RBAllocation.INNER_FULL): (32, 16),
    ("25MHz", 30, RBAllocation.INNER_1RB_LEFT): (1, 1),
    ("25MHz", 30, RBAllocation.INNER_1RB_RIGHT): (1, 63),
    ("30MHz", 15, RBAllocation.INNER_FULL): (80, 40),
    ("30MHz", 15, RBAllocation.INNER_1RB_LEFT): (1, 1),
    ("30MHz", 15, RBAllocation.INNER_1RB_RIGHT): (1, 158),
    ("30MHz", 30, RBAllocation.INNER_FULL): (36, 18),
    ("30MHz", 30, RBAllocation.INNER_1RB_LEFT): (1, 1),
    ("30MHz", 30, RBAllocation.INNER_1RB_RIGHT): (1, 76),
    ("35MHz", 15, RBAllocation.INNER_FULL): (90, 45),
    ("35MHz", 15, RBAllocation.INNER_1RB_LEFT): (1, 1),
    ("35MHz", 15, RBAllocation.INNER_1RB_RIGHT): (1, 186),
    ("35MHz", 30, RBAllocation.INNER_FULL): (45, 22),
    ("35MHz", 30, RBAllocation.INNER_1RB_LEFT): (1, 1),
    ("35MHz", 30, RBAllocation.INNER_1RB_RIGHT): (1, 90),
    ("40MHz", 15, RBAllocation.INNER_FULL): (108, 54),
    ("40MHz", 15, RBAllocation.INNER_1RB_LEFT): (1, 1),
    ("40MHz", 15, RBAllocation.INNER_1RB_RIGHT): (1, 214),
    ("40MHz", 30, RBAllocation.INNER_FULL): (50, 25),
    ("40MHz", 30, RBAllocation.INNER_1RB_LEFT): (1, 1),
    ("40MHz", 30, RBAllocation.INNER_1RB_RIGHT): (1, 104),
    ("45MHz", 15, RBAllocation.INNER_FULL): (120, 60),
    ("45MHz", 15, RBAllocation.INNER_1RB_LEFT): (1, 1),
    ("45MHz", 15, RBAllocation.INNER_1RB_RIGHT): (1, 240),
    ("45MHz", 30, RBAllocation.INNER_FULL): (54, 27),
    ("45MHz", 30, RBAllocation.INNER_1RB_LEFT): (1, 1),
    ("45MHz", 30, RBAllocation.INNER_1RB_RIGHT): (1, 117),
    ("50MHz", 15, RBAllocation.INNER_FULL): (135, 67),
    ("50MHz", 15, RBAllocation.INNER_1RB_LEFT): (1, 1),
    ("50MHz", 15, RBAllocation.INNER_1RB_RIGHT): (1, 268),
    ("50MHz", 30, RBAllocation.INNER_FULL): (64, 32),
    ("50MHz", 30, RBAllocation.INNER_1RB_LEFT): (1, 1),
    ("50MHz", 30, RBAllocation.INNER_1RB_RIGHT): (1, 131),
    ("60MHz", 30, RBAllocation.INNER_FULL): (81, 40),
    ("60MHz", 30, RBAllocation.INNER_1RB_LEFT): (1, 1),
    ("60MHz", 30, RBAllocation.INNER_1RB_RIGHT): (1, 160),
    ("70MHz", 30, RBAllocation.INNER_FULL): (90, 45),
    ("70MHz", 30, RBAllocation.INNER_1RB_LEFT): (1, 1),
    ("70MHz", 30, RBAllocation.INNER_1RB_RIGHT): (1, 187),
    ("80MHz", 30, RBAllocation.INNER_FULL): (108, 54),
    ("80MHz", 30, RBAllocation.INNER_1RB_LEFT): (1, 1),
    ("80MHz", 30, RBAllocation.INNER_1RB_RIGHT): (1, 215),
    ("90MHz", 30, RBAllocation.INNER_FULL): (120, 60),
    ("90MHz", 30, RBAllocation.INNER_1RB_LEFT): (1, 1),
    ("90MHz", 30, RBAllocation.INNER_1RB_RIGHT): (1, 243),
    ("100MHz", 30, RBAllocation.INNER_FULL): (135, 67),
    ("100MHz", 30, RBAllocation.INNER_1RB_LEFT): (1, 1),
    ("100MHz", 30, RBAllocation.INNER_1RB_RIGHT): (1, 271),
}


def _normalize_bandwidth_label(bandwidth: str) -> str:
    normalized = bandwidth.strip().replace(" ", "")
    if normalized.lower().endswith("mhz"):
        return f"{normalized[:-3]}MHz"
    return normalized


def resolve_rb_parameters(
    band: str,
    bandwidth: str,
    rb_allocation: RBAllocation,
) -> tuple[int, int]:
    """RB allocation 표에서 RB size/offset을 계산한다.

    OFDM는 현재 스펙 범위 밖이므로 DFT-s 조합만 지원한다.
    """

    scs_khz = find_band_group(band).scs_khz
    normalized_bandwidth = _normalize_bandwidth_label(bandwidth)
    key = (normalized_bandwidth, scs_khz, rb_allocation)
    try:
        return _RB_PARAMETERS_BY_KEY[key]
    except KeyError as exc:
        raise ValueError(
            "Unsupported RB allocation mapping for "
            f"band={band!r}, "
            f"bandwidth={normalized_bandwidth!r}, "
            f"scs_khz={scs_khz}, "
            f"rb_allocation={rb_allocation.value!r}"
        ) from exc
