"""NR call channel 및 harmonic target frequency lookup."""
from __future__ import annotations

import math
from dataclasses import dataclass

from app.models.enums import NRBand, TestChannel
from app.models.switch_box import parse_band_number

BandLookupTable = dict[float, dict[TestChannel, "NRChannelProfile"]]


@dataclass(frozen=True)
class NRChannelProfile:
    """Band/bandwidth/test_channel 조합의 channel/frequency 묶음."""

    call_channel: int
    target_frequency_mhz: float


def _normalize_bandwidth_value(bandwidth: float) -> float:
    if isinstance(bandwidth, bool) or not isinstance(bandwidth, int | float):
        raise ValueError(f"Invalid bandwidth: {bandwidth!r}")

    normalized = float(bandwidth)
    if not math.isfinite(normalized):
        raise ValueError(f"Invalid bandwidth: {bandwidth!r}")
    return float(format(normalized, ".15g"))


def _format_bandwidth_value(bandwidth: float) -> str:
    return format(_normalize_bandwidth_value(bandwidth), ".15g")


def _raise_missing_lookup(
    band_number: int,
    bandwidth: float,
    test_channel: TestChannel,
) -> None:
    raise ValueError(
        "No NR channel lookup for "
        f"band='n{band_number}', "
        f"bandwidth='{_format_bandwidth_value(bandwidth)}', "
        f"test_channel='{test_channel.value}'"
    )


def _resolve_band_key(band: str | NRBand) -> tuple[int, NRBand | None]:
    band_number = parse_band_number(band)
    try:
        return band_number, NRBand(f"n{band_number}")
    except ValueError:
        return band_number, None


def _get_profile(
    band: str | NRBand,
    bandwidth: float,
    test_channel: TestChannel,
) -> NRChannelProfile:
    band_number, band_key = _resolve_band_key(band)
    normalized_bandwidth = _normalize_bandwidth_value(bandwidth)

    if band_key is None:
        _raise_missing_lookup(band_number, normalized_bandwidth, test_channel)

    band_lookup = _CHANNEL_LOOKUP_BY_BAND.get(band_key)
    if band_lookup is None:
        _raise_missing_lookup(band_number, normalized_bandwidth, test_channel)

    profiles = band_lookup.get(normalized_bandwidth)
    if profiles is None:
        _raise_missing_lookup(band_number, normalized_bandwidth, test_channel)

    profile = profiles.get(test_channel)
    if profile is None:
        _raise_missing_lookup(band_number, normalized_bandwidth, test_channel)
    return profile


def resolve_call_channel(
    band: str | NRBand,
    bandwidth: float,
    test_channel: TestChannel,
) -> int:
    """실제 NR call setup에 사용하는 channel 번호를 반환한다."""

    return _get_profile(band, bandwidth, test_channel).call_channel


def resolve_target_frequency_mhz(
    band: str | NRBand,
    bandwidth: float,
    test_channel: TestChannel,
) -> float:
    """Harmonic fundamental 탐색에 사용하는 target frequency를 반환한다."""

    return _get_profile(band, bandwidth, test_channel).target_frequency_mhz


def _profile(call_channel: int, target_frequency_mhz: float) -> NRChannelProfile:
    return NRChannelProfile(
        call_channel=call_channel,
        target_frequency_mhz=target_frequency_mhz,
    )


def _profiles(
    *,
    low: tuple[int, float],
    mid: tuple[int, float] | None = None,
    high: tuple[int, float],
) -> dict[TestChannel, NRChannelProfile]:
    profiles = {
        TestChannel.LOW: _profile(*low),
        TestChannel.HIGH: _profile(*high),
    }
    if mid is not None:
        profiles[TestChannel.MID] = _profile(*mid)
    return profiles


# lookup 데이터는 아래에 모아둔다.
_CHANNEL_LOOKUP_BY_BAND: dict[NRBand, BandLookupTable] = {
    NRBand.N1: {
        5.0: _profiles(
            low=(384500, 1922.5),
            mid=(390000, 1950.0),
            high=(395500, 1977.5),
        ),
        10.0: _profiles(
            low=(385000, 1925.0),
            mid=(390000, 1950.0),
            high=(395000, 1975.0),
        ),
        15.0: _profiles(
            low=(385500, 1927.5),
            mid=(390000, 1950.0),
            high=(394500, 1972.5),
        ),
        20.0: _profiles(
            low=(386000, 1930.0),
            mid=(390000, 1950.0),
            high=(394000, 1970.0),
        ),
        25.0: _profiles(
            low=(386500, 1932.5),
            mid=(390000, 1950.0),
            high=(393500, 1967.5),
        ),
        30.0: _profiles(
            low=(387000, 1935.0),
            mid=(390000, 1950.0),
            high=(393000, 1965.0),
        ),
        40.0: _profiles(
            low=(388000, 1940.0),
            mid=(390000, 1950.0),
            high=(392000, 1960.0),
        ),
        45.0: _profiles(
            low=(388500, 1942.5),
            mid=(390000, 1950.0),
            high=(391500, 1957.5),
        ),
        50.0: _profiles(
            low=(389000, 1945.0),
            mid=(390000, 1950.0),
            high=(391000, 1955.0),
        ),
    },
    NRBand.N3: {
        5.0: _profiles(
            low=(342500, 1712.5),
            mid=(349500, 1747.5),
            high=(356500, 1782.5),
        ),
        10.0: _profiles(
            low=(343000, 1715.0),
            mid=(349500, 1747.5),
            high=(356000, 1780.0),
        ),
        15.0: _profiles(
            low=(343500, 1717.5),
            mid=(349500, 1747.5),
            high=(355500, 1777.5),
        ),
        20.0: _profiles(
            low=(344000, 1720.0),
            mid=(349500, 1747.5),
            high=(355000, 1775.0),
        ),
        25.0: _profiles(
            low=(344500, 1722.5),
            mid=(349500, 1747.5),
            high=(354500, 1772.5),
        ),
        30.0: _profiles(
            low=(345000, 1725.0),
            mid=(349500, 1747.5),
            high=(354000, 1770.0),
        ),
        35.0: _profiles(
            low=(345500, 1727.5),
            mid=(349500, 1747.5),
            high=(353500, 1767.5),
        ),
        40.0: _profiles(
            low=(346000, 1730.0),
            mid=(349500, 1747.5),
            high=(353000, 1765.0),
        ),
        45.0: _profiles(
            low=(346500, 1732.5),
            mid=(349500, 1747.5),
            high=(352500, 1762.5),
        ),
        50.0: _profiles(
            low=(347000, 1735.0),
            mid=(349500, 1747.5),
            high=(352000, 1760.0),
        ),
    },
    NRBand.N5: {
        5.0: _profiles(
            low=(165300, 826.5),
            mid=(167300, 836.5),
            high=(169300, 846.5),
        ),
        10.0: _profiles(
            low=(165800, 829.0),
            mid=(167300, 836.5),
            high=(168800, 844.0),
        ),
        15.0: _profiles(
            low=(166300, 831.5),
            mid=(167300, 836.5),
            high=(168300, 841.5),
        ),
        20.0: _profiles(
            low=(166800, 834.0),
            mid=(167300, 836.5),
            high=(167800, 839.0),
        ),
    },
    NRBand.N7: {
        5.0: _profiles(
            low=(500500, 2502.5),
            mid=(507000, 2535.0),
            high=(513500, 2567.5),
        ),
        10.0: _profiles(
            low=(501000, 2505.0),
            mid=(507000, 2535.0),
            high=(513000, 2565.0),
        ),
        15.0: _profiles(
            low=(501500, 2507.5),
            mid=(507000, 2535.0),
            high=(512500, 2562.5),
        ),
        20.0: _profiles(
            low=(502000, 2510.0),
            mid=(507000, 2535.0),
            high=(512000, 2560.0),
        ),
        25.0: _profiles(
            low=(502500, 2512.5),
            mid=(507000, 2535.0),
            high=(511500, 2557.5),
        ),
        30.0: _profiles(
            low=(503000, 2515.0),
            mid=(507000, 2535.0),
            high=(511000, 2555.0),
        ),
        35.0: _profiles(
            low=(503500, 2517.5),
            mid=(507000, 2535.0),
            high=(510500, 2552.5),
        ),
        40.0: _profiles(
            low=(504000, 2520.0),
            mid=(507000, 2535.0),
            high=(510000, 2550.0),
        ),
        50.0: _profiles(
            low=(505000, 2525.0),
            mid=(507000, 2535.0),
            high=(509000, 2545.0),
        ),
    },
    NRBand.N8: {
        5.0: _profiles(
            low=(176500, 882.5),
            mid=(179500, 897.5),
            high=(182500, 912.5),
        ),
        10.0: _profiles(
            low=(177000, 885.0),
            mid=(179500, 897.5),
            high=(182000, 910.0),
        ),
        15.0: _profiles(
            low=(177500, 887.5),
            mid=(179500, 897.5),
            high=(181500, 907.5),
        ),
        20.0: _profiles(
            low=(178000, 890.0),
            mid=(179500, 897.5),
            high=(181000, 905.0),
        ),
    },
    NRBand.N20: {
        5.0: _profiles(
            low=(166900, 834.5),
            mid=(169400, 847.0),
            high=(171900, 859.5),
        ),
        10.0: _profiles(
            low=(167400, 837.0),
            mid=(169400, 847.0),
            high=(171400, 857.0),
        ),
        15.0: _profiles(
            low=(167900, 839.5),
            mid=(169400, 847.0),
            high=(170900, 854.5),
        ),
        20.0: _profiles(
            low=(168400, 842.0),
            mid=(169400, 847.0),
            high=(170400, 852.0),
        ),
    },
    NRBand.N26: {
        5.0: _profiles(
            low=(163300, 816.5),
            mid=(166300, 831.5),
            high=(169300, 846.5),
        ),
        10.0: _profiles(
            low=(163800, 819.0),
            mid=(166300, 831.5),
            high=(168800, 844.0),
        ),
        15.0: _profiles(
            low=(164300, 821.5),
            mid=(166300, 831.5),
            high=(168300, 841.5),
        ),
        20.0: _profiles(
            low=(164800, 824.0),
            mid=(166300, 831.5),
            high=(167800, 839.0),
        ),
    },
    NRBand.N28: {
        5.0: _profiles(
            low=(141100, 705.5),
            mid=(145100, 725.5),
            high=(149100, 745.5),
        ),
        10.0: _profiles(
            low=(141600, 708.0),
            mid=(145100, 725.5),
            high=(148600, 743.0),
        ),
        15.0: _profiles(
            low=(142100, 710.5),
            mid=(145100, 725.5),
            high=(148100, 740.5),
        ),
        20.0: _profiles(
            low=(142600, 713.0),
            mid=(145600, 728.0),
            high=(147600, 738.0),
        ),
        25.0: _profiles(
            low=(143100, 715.5),
            high=(147100, 735.5),
        ),
        30.0: _profiles(
            low=(143600, 718.0),
            high=(146600, 733.0),
        ),
    },
    NRBand.N38: {
        10.0: _profiles(
            low=(515000, 2575.0),
            mid=(519000, 2595.0),
            high=(523000, 2615.0),
        ),
        15.0: _profiles(
            low=(515500, 2577.5),
            mid=(519000, 2595.0),
            high=(522500, 2612.5),
        ),
        20.0: _profiles(
            low=(516000, 2580.0),
            mid=(519000, 2595.0),
            high=(522000, 2610.0),
        ),
        25.0: _profiles(
            low=(516500, 2582.5),
            mid=(519000, 2595.0),
            high=(521500, 2607.5),
        ),
        30.0: _profiles(
            low=(517000, 2585.0),
            mid=(519000, 2595.0),
            high=(521000, 2605.0),
        ),
        40.0: _profiles(
            low=(518000, 2590.0),
            mid=(519000, 2595.0),
            high=(520000, 2600.0),
        ),
    },
    NRBand.N40: {
        10.0: _profiles(
            low=(461000, 2305.0),
            mid=(470000, 2350.0),
            high=(479000, 2395.0),
        ),
        15.0: _profiles(
            low=(461500, 2307.5),
            mid=(470000, 2350.0),
            high=(478500, 2392.5),
        ),
        20.0: _profiles(
            low=(462000, 2310.0),
            mid=(470000, 2350.0),
            high=(478000, 2390.0),
        ),
        25.0: _profiles(
            low=(462500, 2312.5),
            mid=(470000, 2350.0),
            high=(477500, 2387.5),
        ),
        30.0: _profiles(
            low=(463000, 2315.0),
            mid=(470000, 2350.0),
            high=(477000, 2385.0),
        ),
        40.0: _profiles(
            low=(464000, 2320.0),
            mid=(470000, 2350.0),
            high=(476000, 2380.0),
        ),
        50.0: _profiles(
            low=(465000, 2325.0),
            mid=(470000, 2350.0),
            high=(475000, 2375.0),
        ),
        60.0: _profiles(
            low=(466000, 2330.0),
            mid=(470000, 2350.0),
            high=(474000, 2370.0),
        ),
        70.0: _profiles(
            low=(467000, 2335.0),
            mid=(470000, 2350.0),
            high=(473000, 2365.0),
        ),
        80.0: _profiles(
            low=(468000, 2340.0),
            mid=(470000, 2350.0),
            high=(472000, 2360.0),
        ),
        90.0: _profiles(
            low=(469000, 2345.0),
            mid=(470000, 2350.0),
            high=(471000, 2355.0),
        ),
        100.0: _profiles(
            low=(470000, 2350.0),
            mid=(470000, 2350.0),
            high=(470000, 2350.0),
        ),
    },
    NRBand.N41: {
        10.0: _profiles(
            low=(500202, 2501.01),
            mid=(518598, 2592.99),
            high=(537000, 2685.0),
        ),
        15.0: _profiles(
            low=(500700, 2503.5),
            mid=(518598, 2592.99),
            high=(536496, 2682.48),
        ),
        20.0: _profiles(
            low=(501204, 2506.02),
            mid=(518598, 2592.99),
            high=(535998, 2679.99),
        ),
        25.0: _profiles(
            low=(501702, 2508.51),
            mid=(518598, 2592.99),
            high=(535500, 2677.5),
        ),
        30.0: _profiles(
            low=(502200, 2511.0),
            mid=(518598, 2592.99),
            high=(534996, 2674.98),
        ),
        40.0: _profiles(
            low=(503202, 2516.01),
            mid=(518598, 2592.99),
            high=(534000, 2670.0),
        ),
        50.0: _profiles(
            low=(504204, 2521.02),
            mid=(518598, 2592.99),
            high=(532998, 2664.99),
        ),
        60.0: _profiles(
            low=(505200, 2526.0),
            mid=(518598, 2592.99),
            high=(531996, 2659.98),
        ),
        70.0: _profiles(
            low=(506202, 2531.01),
            mid=(518598, 2592.99),
            high=(531000, 2655.0),
        ),
        80.0: _profiles(
            low=(507204, 2536.02),
            mid=(518598, 2592.99),
            high=(529998, 2649.99),
        ),
        90.0: _profiles(
            low=(508200, 2541.0),
            mid=(518598, 2592.99),
            high=(528996, 2644.98),
        ),
        100.0: _profiles(
            low=(509202, 2546.01),
            mid=(518598, 2592.99),
            high=(528000, 2640.0),
        ),
    },
    NRBand.N71: {
        5.0: _profiles(
            low=(133100, 665.5),
            mid=(136100, 680.5),
            high=(139100, 695.5),
        ),
        10.0: _profiles(
            low=(133600, 668.0),
            mid=(136100, 680.5),
            high=(138600, 693.0),
        ),
        15.0: _profiles(
            low=(134100, 670.5),
            mid=(136100, 680.5),
            high=(138100, 690.5),
        ),
        20.0: _profiles(
            low=(134600, 673.0),
            mid=(136100, 680.5),
            high=(137600, 688.0),
        ),
    },
    NRBand.N77: {
        10.0: _profiles(
            low=(620334, 3305.01),
            mid=(650000, 3750.0),
            high=(679666, 4194.99),
        ),
        15.0: _profiles(
            low=(620500, 3307.5),
            mid=(650000, 3750.0),
            high=(679500, 4192.5),
        ),
        20.0: _profiles(
            low=(620668, 3310.02),
            mid=(650000, 3750.0),
            high=(679332, 4189.98),
        ),
        25.0: _profiles(
            low=(620834, 3312.51),
            mid=(650000, 3750.0),
            high=(679166, 4187.49),
        ),
        30.0: _profiles(
            low=(621000, 3315.0),
            mid=(650000, 3750.0),
            high=(679000, 4185.0),
        ),
        40.0: _profiles(
            low=(621334, 3320.01),
            mid=(650000, 3750.0),
            high=(678666, 4179.99),
        ),
        50.0: _profiles(
            low=(621668, 3325.02),
            mid=(650000, 3750.0),
            high=(678332, 4174.98),
        ),
        60.0: _profiles(
            low=(622000, 3330.0),
            mid=(650000, 3750.0),
            high=(678000, 4170.0),
        ),
        70.0: _profiles(
            low=(622334, 3335.01),
            mid=(650000, 3750.0),
            high=(677666, 4164.99),
        ),
        80.0: _profiles(
            low=(622668, 3340.02),
            mid=(650000, 3750.0),
            high=(677332, 4159.98),
        ),
        90.0: _profiles(
            low=(623000, 3345.0),
            mid=(650000, 3750.0),
            high=(677000, 4155.0),
        ),
        100.0: _profiles(
            low=(623334, 3350.01),
            mid=(650000, 3750.0),
            high=(676666, 4149.99),
        ),
    },
    NRBand.N78: {
        10.0: _profiles(
            low=(620334, 3305.01),
            mid=(636666, 3549.99),
            high=(653000, 3795.0),
        ),
        15.0: _profiles(
            low=(620500, 3307.5),
            mid=(636666, 3549.99),
            high=(652832, 3792.48),
        ),
        20.0: _profiles(
            low=(620668, 3310.02),
            mid=(636666, 3549.99),
            high=(652666, 3789.99),
        ),
        25.0: _profiles(
            low=(620834, 3312.51),
            mid=(636666, 3549.99),
            high=(652500, 3787.5),
        ),
        30.0: _profiles(
            low=(621000, 3315.0),
            mid=(636666, 3549.99),
            high=(652332, 3784.98),
        ),
        40.0: _profiles(
            low=(621334, 3320.01),
            mid=(636666, 3549.99),
            high=(652000, 3780.0),
        ),
        50.0: _profiles(
            low=(621668, 3325.02),
            mid=(636666, 3549.99),
            high=(651666, 3774.99),
        ),
        60.0: _profiles(
            low=(622000, 3330.0),
            mid=(636666, 3549.99),
            high=(651332, 3769.98),
        ),
        70.0: _profiles(
            low=(622334, 3335.01),
            mid=(636666, 3549.99),
            high=(651000, 3765.0),
        ),
        80.0: _profiles(
            low=(622668, 3340.02),
            mid=(636666, 3549.99),
            high=(650666, 3759.99),
        ),
        90.0: _profiles(
            low=(623000, 3345.0),
            mid=(636666, 3549.99),
            high=(650332, 3754.98),
        ),
        100.0: _profiles(
            low=(623334, 3350.01),
            mid=(636666, 3549.99),
            high=(650000, 3750.0),
        ),
    },
    NRBand.N79: {
        10.0: _profiles(
            low=(693722, 4405.83),
            mid=(713328, 4699.92),
            high=(733000, 4995.0),
        ),
        20.0: _profiles(
            low=(694000, 4410.0),
            mid=(713334, 4700.01),
            high=(732666, 4989.99),
        ),
        40.0: _profiles(
            low=(694668, 4420.02),
            mid=(713334, 4700.01),
            high=(732000, 4980.0),
        ),
        50.0: _profiles(
            low=(695000, 4425.0),
            mid=(713334, 4700.01),
            high=(731666, 4974.99),
        ),
        60.0: _profiles(
            low=(695334, 4430.01),
            mid=(713334, 4700.01),
            high=(731332, 4969.98),
        ),
        80.0: _profiles(
            low=(696000, 4440.0),
            mid=(713334, 4700.01),
            high=(730666, 4959.99),
        ),
        100.0: _profiles(
            low=(696668, 4450.02),
            mid=(713334, 4700.01),
            high=(730000, 4950.0),
        ),
    },
}
