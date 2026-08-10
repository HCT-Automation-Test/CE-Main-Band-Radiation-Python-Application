"""LTE ARFCN 및 주파수 lookup."""
from __future__ import annotations

import math
from dataclasses import dataclass

from app.models.enums import LTEBand, TestChannel


@dataclass(frozen=True)
class LTEChannelProfile:
    """LTE Band/BW/채널 위치의 ARFCN과 주파수."""

    dl_channel: int
    dl_frequency_mhz: float
    ul_channel: int
    ul_frequency_mhz: float


ChannelValues = tuple[
    tuple[int, float, int, float],
    tuple[int, float, int, float],
    tuple[int, float, int, float],
]


# 값 순서는 low, mid, high다.
_CHANNEL_VALUES_BY_BANDWIDTH: dict[tuple[LTEBand, float], ChannelValues] = {
    (LTEBand.B1, 5.0): ((25, 2112.5, 18025, 1922.5), (300, 2140.0, 18300, 1950.0), (575, 2167.5, 18575, 1977.5)),
    (LTEBand.B1, 10.0): ((50, 2115.0, 18050, 1925.0), (300, 2140.0, 18300, 1950.0), (550, 2165.0, 18550, 1975.0)),
    (LTEBand.B1, 15.0): ((75, 2117.5, 18075, 1927.5), (300, 2140.0, 18300, 1950.0), (525, 2162.5, 18525, 1972.5)),
    (LTEBand.B1, 20.0): ((100, 2120.0, 18100, 1930.0), (300, 2140.0, 18300, 1950.0), (500, 2160.0, 18500, 1970.0)),
    (LTEBand.B3, 1.4): ((1207, 1805.7, 19207, 1710.7), (1575, 1842.5, 19575, 1747.5), (1943, 1879.3, 19943, 1784.3)),
    (LTEBand.B3, 3.0): ((1215, 1806.5, 19215, 1711.5), (1575, 1842.5, 19575, 1747.5), (1935, 1878.5, 19935, 1783.5)),
    (LTEBand.B3, 5.0): ((1225, 1807.5, 19225, 1712.5), (1575, 1842.5, 19575, 1747.5), (1925, 1877.5, 19925, 1782.5)),
    (LTEBand.B3, 10.0): ((1250, 1810.0, 19250, 1715.0), (1575, 1842.5, 19575, 1747.5), (1900, 1875.0, 19900, 1780.0)),
    (LTEBand.B3, 15.0): ((1275, 1812.5, 19275, 1717.5), (1575, 1842.5, 19575, 1747.5), (1875, 1872.5, 19875, 1777.5)),
    (LTEBand.B3, 20.0): ((1300, 1815.0, 19300, 1720.0), (1575, 1842.5, 19575, 1747.5), (1850, 1870.0, 19850, 1775.0)),
    (LTEBand.B5, 1.4): ((2407, 869.7, 20407, 824.7), (2525, 881.5, 20525, 836.5), (2643, 893.3, 20643, 848.3)),
    (LTEBand.B5, 3.0): ((2415, 870.5, 20415, 825.5), (2525, 881.5, 20525, 836.5), (2635, 892.5, 20635, 847.5)),
    (LTEBand.B5, 5.0): ((2425, 871.5, 20425, 826.5), (2525, 881.5, 20525, 836.5), (2625, 891.5, 20625, 846.5)),
    (LTEBand.B5, 10.0): ((2450, 874.0, 20450, 829.0), (2525, 881.5, 20525, 836.5), (2600, 889.0, 20600, 844.0)),
    (LTEBand.B7, 5.0): ((2775, 2622.5, 20775, 2502.5), (3100, 2655.0, 21100, 2535.0), (3425, 2687.5, 21425, 2567.5)),
    (LTEBand.B7, 10.0): ((2800, 2625.0, 20800, 2505.0), (3100, 2655.0, 21100, 2535.0), (3400, 2685.0, 21400, 2565.0)),
    (LTEBand.B7, 15.0): ((2825, 2627.5, 20825, 2507.5), (3100, 2655.0, 21100, 2535.0), (3375, 2682.5, 21375, 2562.5)),
    (LTEBand.B7, 20.0): ((2850, 2630.0, 20850, 2510.0), (3100, 2655.0, 21100, 2535.0), (3350, 2680.0, 21350, 2560.0)),
    (LTEBand.B8, 1.4): ((3457, 925.7, 21457, 880.7), (3625, 942.5, 21625, 897.5), (3793, 959.3, 21793, 914.3)),
    (LTEBand.B8, 3.0): ((3465, 926.5, 21465, 881.5), (3625, 942.5, 21625, 897.5), (3785, 958.5, 21785, 913.5)),
    (LTEBand.B8, 5.0): ((3475, 927.5, 21475, 882.5), (3625, 942.5, 21625, 897.5), (3775, 957.5, 21775, 912.5)),
    (LTEBand.B8, 10.0): ((3500, 930.0, 21500, 885.0), (3625, 942.5, 21625, 897.5), (3750, 955.0, 21750, 910.0)),
    (LTEBand.B20, 5.0): ((6175, 793.5, 24175, 834.5), (6300, 806.0, 24300, 847.0), (6425, 818.5, 24425, 859.5)),
    (LTEBand.B20, 10.0): ((6200, 796.0, 24200, 837.0), (6300, 806.0, 24300, 847.0), (6400, 816.0, 24400, 857.0)),
    (LTEBand.B20, 15.0): ((6225, 798.5, 24225, 839.5), (6300, 806.0, 24300, 847.0), (6375, 813.5, 24375, 854.5)),
    (LTEBand.B20, 20.0): ((6250, 801.0, 24250, 842.0), (6300, 806.0, 24300, 847.0), (6350, 811.0, 24350, 852.0)),
    (LTEBand.B28, 3.0): ((9225, 759.5, 27225, 704.5), (9375, 774.5, 27375, 719.5), (9645, 801.5, 27645, 746.5)),
    (LTEBand.B28, 5.0): ((9235, 760.5, 27235, 705.5), (9385, 775.5, 27385, 720.5), (9635, 800.5, 27635, 745.5)),
    (LTEBand.B28, 10.0): ((9260, 763.0, 27260, 708.0), (9410, 778.0, 27410, 723.0), (9610, 798.0, 27610, 743.0)),
    (LTEBand.B28, 15.0): ((9285, 765.5, 27285, 710.5), (9435, 780.5, 27435, 725.5), (9585, 795.5, 27585, 740.5)),
    (LTEBand.B28, 20.0): ((9310, 768.0, 27310, 713.0), (9460, 783.0, 27460, 728.0), (9560, 793.0, 27560, 738.0)),
    (LTEBand.B34, 5.0): ((36225, 2012.5, 36225, 2012.5), (36275, 2017.5, 36275, 2017.5), (36325, 2022.5, 36325, 2022.5)),
    (LTEBand.B34, 10.0): ((36250, 2015.0, 36250, 2015.0), (36275, 2017.5, 36275, 2017.5), (36300, 2020.0, 36300, 2020.0)),
    (LTEBand.B34, 15.0): ((36275, 2017.5, 36275, 2017.5), (36275, 2017.5, 36275, 2017.5), (36275, 2017.5, 36275, 2017.5)),
    (LTEBand.B38, 5.0): ((37775, 2572.5, 37775, 2572.5), (38000, 2595.0, 38000, 2595.0), (38225, 2617.5, 38225, 2617.5)),
    (LTEBand.B38, 10.0): ((37800, 2575.0, 37800, 2575.0), (38000, 2595.0, 38000, 2595.0), (38200, 2615.0, 38200, 2615.0)),
    (LTEBand.B38, 15.0): ((37825, 2577.5, 37825, 2577.5), (38000, 2595.0, 38000, 2595.0), (38175, 2612.5, 38175, 2612.5)),
    (LTEBand.B38, 20.0): ((37850, 2580.0, 37850, 2580.0), (38000, 2595.0, 38000, 2595.0), (38150, 2610.0, 38150, 2610.0)),
    (LTEBand.B40, 5.0): ((38675, 2302.5, 38675, 2302.5), (39150, 2350.0, 39150, 2350.0), (39625, 2397.5, 39625, 2397.5)),
    (LTEBand.B40, 10.0): ((38700, 2305.0, 38700, 2305.0), (39150, 2350.0, 39150, 2350.0), (39600, 2395.0, 39600, 2395.0)),
    (LTEBand.B40, 15.0): ((38725, 2307.5, 38725, 2307.5), (39150, 2350.0, 39150, 2350.0), (39575, 2392.5, 39575, 2392.5)),
    (LTEBand.B40, 20.0): ((38750, 2310.0, 38750, 2310.0), (39150, 2350.0, 39150, 2350.0), (39550, 2390.0, 39550, 2390.0)),
    (LTEBand.B41, 5.0): ((39675, 2498.5, 39675, 2498.5), (40620, 2593.0, 40620, 2593.0), (41565, 2687.5, 41565, 2687.5)),
    (LTEBand.B41, 10.0): ((39700, 2501.0, 39700, 2501.0), (40620, 2593.0, 40620, 2593.0), (41540, 2685.0, 41540, 2685.0)),
    (LTEBand.B41, 15.0): ((39725, 2503.5, 39725, 2503.5), (40620, 2593.0, 40620, 2593.0), (41515, 2682.5, 41515, 2682.5)),
    (LTEBand.B41, 20.0): ((39750, 2506.0, 39750, 2506.0), (40620, 2593.0, 40620, 2593.0), (41490, 2680.0, 41490, 2680.0)),
}

_CHANNEL_ORDER = (TestChannel.LOW, TestChannel.MID, TestChannel.HIGH)

_CHANNEL_LOOKUP: dict[tuple[LTEBand, float, TestChannel], LTEChannelProfile] = {
    (band, bandwidth, channel): LTEChannelProfile(
        dl_channel=values[index][0],
        dl_frequency_mhz=values[index][1],
        ul_channel=values[index][2],
        ul_frequency_mhz=values[index][3],
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

    return _get_profile(band, bandwidth, test_channel).ul_channel


def resolve_lte_frequency_mhz(
    band: LTEBand | str,
    bandwidth: float,
    test_channel: TestChannel,
) -> float:
    """LTE 측정에 사용하는 중심 주파수를 반환한다."""

    return _get_profile(band, bandwidth, test_channel).ul_frequency_mhz


def resolve_dl_channel(
    band: LTEBand | str,
    bandwidth: float,
    test_channel: TestChannel,
) -> int:
    """LTE Handover에 사용하는 DL Channel을 반환한다."""

    return _get_profile(band, bandwidth, test_channel).dl_channel


def resolve_dl_frequency_mhz(
    band: LTEBand | str,
    bandwidth: float,
    test_channel: TestChannel,
) -> float:
    """LTE Handover 목적지의 DL 주파수를 반환한다."""

    return _get_profile(band, bandwidth, test_channel).dl_frequency_mhz
