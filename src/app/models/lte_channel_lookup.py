"""LTE ARFCN 및 주파수 lookup."""
from __future__ import annotations

import math
from dataclasses import dataclass

from app.models.enums import LTEBand, TestChannel


@dataclass(frozen=True)
class LTEChannelProfile:
    """LTE Band/BW/채널 위치의 ARFCN과 주파수."""

    arfcn: int
    frequency_mhz: float


ChannelValues = tuple[
    tuple[int, float],
    tuple[int, float],
    tuple[int, float],
]


# 값 순서는 low, mid, high다.
_CHANNEL_VALUES_BY_BANDWIDTH: dict[tuple[LTEBand, float], ChannelValues] = {
    (LTEBand.B1, 5.0): ((18025, 1922.5), (18300, 1950.0), (18575, 1977.5)),
    (LTEBand.B1, 10.0): ((18050, 1925.0), (18300, 1950.0), (18550, 1975.0)),
    (LTEBand.B1, 15.0): ((18075, 1927.5), (18300, 1950.0), (18525, 1972.5)),
    (LTEBand.B1, 20.0): ((18100, 1930.0), (18300, 1950.0), (18500, 1970.0)),
    (LTEBand.B3, 1.4): ((19207, 1710.7), (19575, 1747.5), (19943, 1784.3)),
    (LTEBand.B3, 3.0): ((19215, 1711.5), (19575, 1747.5), (19935, 1783.5)),
    (LTEBand.B3, 5.0): ((19225, 1712.5), (19575, 1747.5), (19925, 1782.5)),
    (LTEBand.B3, 10.0): ((19250, 1715.0), (19575, 1747.5), (19900, 1780.0)),
    (LTEBand.B3, 15.0): ((19275, 1717.5), (19575, 1747.5), (19875, 1777.5)),
    (LTEBand.B3, 20.0): ((19300, 1720.0), (19575, 1747.5), (19850, 1775.0)),
    (LTEBand.B5, 1.4): ((20407, 824.7), (20525, 836.5), (20643, 848.3)),
    (LTEBand.B5, 3.0): ((20415, 825.5), (20525, 836.5), (20635, 847.5)),
    (LTEBand.B5, 5.0): ((20425, 826.5), (20525, 836.5), (20625, 846.5)),
    (LTEBand.B5, 10.0): ((20450, 829.0), (20525, 836.5), (20600, 844.0)),
    (LTEBand.B7, 5.0): ((20775, 2502.5), (21100, 2535.0), (21425, 2567.5)),
    (LTEBand.B7, 10.0): ((20800, 2505.0), (21100, 2535.0), (21400, 2565.0)),
    (LTEBand.B7, 15.0): ((20825, 2507.5), (21100, 2535.0), (21375, 2562.5)),
    (LTEBand.B7, 20.0): ((20850, 2510.0), (21100, 2535.0), (21350, 2560.0)),
    (LTEBand.B8, 1.4): ((21457, 880.7), (21625, 897.5), (21793, 914.3)),
    (LTEBand.B8, 3.0): ((21465, 881.5), (21625, 897.5), (21785, 913.5)),
    (LTEBand.B8, 5.0): ((21475, 882.5), (21625, 897.5), (21775, 912.5)),
    (LTEBand.B8, 10.0): ((21500, 885.0), (21625, 897.5), (21750, 910.0)),
    (LTEBand.B20, 5.0): ((24175, 834.5), (24300, 847.0), (24425, 859.5)),
    (LTEBand.B20, 10.0): ((24200, 837.0), (24300, 847.0), (24400, 857.0)),
    (LTEBand.B20, 15.0): ((24225, 839.5), (24300, 847.0), (24375, 854.5)),
    (LTEBand.B20, 20.0): ((24250, 842.0), (24300, 847.0), (24350, 852.0)),
    (LTEBand.B28, 3.0): ((27225, 704.5), (27375, 719.5), (27645, 746.5)),
    (LTEBand.B28, 5.0): ((27235, 705.5), (27385, 720.5), (27635, 745.5)),
    (LTEBand.B28, 10.0): ((27260, 708.0), (27410, 723.0), (27610, 743.0)),
    (LTEBand.B28, 15.0): ((27285, 710.5), (27435, 725.5), (27585, 740.5)),
    (LTEBand.B28, 20.0): ((27310, 713.0), (27460, 728.0), (27560, 738.0)),
    (LTEBand.B34, 5.0): ((36225, 2012.5), (36275, 2017.5), (36325, 2022.5)),
    (LTEBand.B34, 10.0): ((36250, 2015.0), (36275, 2017.5), (36300, 2020.0)),
    (LTEBand.B34, 15.0): ((36275, 2017.5), (36275, 2017.5), (36275, 2017.5)),
    (LTEBand.B38, 5.0): ((37775, 2572.5), (38000, 2595.0), (38225, 2617.5)),
    (LTEBand.B38, 10.0): ((37800, 2575.0), (38000, 2595.0), (38200, 2615.0)),
    (LTEBand.B38, 15.0): ((37825, 2577.5), (38000, 2595.0), (38175, 2612.5)),
    (LTEBand.B38, 20.0): ((37850, 2580.0), (38000, 2595.0), (38150, 2610.0)),
    (LTEBand.B40, 5.0): ((38675, 2302.5), (39150, 2350.0), (39625, 2397.5)),
    (LTEBand.B40, 10.0): ((38700, 2305.0), (39150, 2350.0), (39600, 2395.0)),
    (LTEBand.B40, 15.0): ((38725, 2307.5), (39150, 2350.0), (39575, 2392.5)),
    (LTEBand.B40, 20.0): ((38750, 2310.0), (39150, 2350.0), (39550, 2390.0)),
    (LTEBand.B41, 5.0): ((39675, 2498.5), (40620, 2593.0), (41565, 2687.5)),
    (LTEBand.B41, 10.0): ((39700, 2501.0), (40620, 2593.0), (41540, 2685.0)),
    (LTEBand.B41, 15.0): ((39725, 2503.5), (40620, 2593.0), (41515, 2682.5)),
    (LTEBand.B41, 20.0): ((39750, 2506.0), (40620, 2593.0), (41490, 2680.0)),
}

_CHANNEL_ORDER = (TestChannel.LOW, TestChannel.MID, TestChannel.HIGH)

_CHANNEL_LOOKUP: dict[tuple[LTEBand, float, TestChannel], LTEChannelProfile] = {
    (band, bandwidth, channel): LTEChannelProfile(
        arfcn=values[index][0],
        frequency_mhz=values[index][1],
    )
    for (band, bandwidth), values in _CHANNEL_VALUES_BY_BANDWIDTH.items()
    for index, channel in enumerate(_CHANNEL_ORDER)
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


def _get_profile(
    band: LTEBand | str,
    bandwidth: float,
    test_channel: TestChannel,
) -> LTEChannelProfile:
    band_key = _coerce_lte_band(band)
    normalized_bandwidth = _normalize_bandwidth_value(bandwidth)
    try:
        return _CHANNEL_LOOKUP[(band_key, normalized_bandwidth, test_channel)]
    except KeyError as exc:
        channel_value = getattr(test_channel, "value", test_channel)
        raise ValueError(
            "No LTE channel lookup for "
            f"band={band_key.value!r}, "
            f"bandwidth={format(normalized_bandwidth, '.15g')!r}, "
            f"test_channel={channel_value!r}"
        ) from exc


def resolve_arfcn(
    band: LTEBand | str,
    bandwidth: float,
    test_channel: TestChannel,
) -> int:
    """LTE Call에 사용하는 ARFCN을 반환한다."""

    return _get_profile(band, bandwidth, test_channel).arfcn


def resolve_lte_frequency_mhz(
    band: LTEBand | str,
    bandwidth: float,
    test_channel: TestChannel,
) -> float:
    """LTE 측정에 사용하는 중심 주파수를 반환한다."""

    return _get_profile(band, bandwidth, test_channel).frequency_mhz
