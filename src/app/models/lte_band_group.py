"""LTE Band 그룹 상수 및 lookup 헬퍼."""
from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import DuplexMode, LTEBand, TestType
from app.models.test_range import RangeId


@dataclass(frozen=True)
class LTEBandGroupProfile:
    """LTE Band가 공통으로 사용하는 RF 설정."""

    key: str
    bands: tuple[LTEBand, ...]
    duplex: DuplexMode
    test_ranges: tuple[RangeId, ...]
    factor_keyword: str
    mt8000_recall: str
    scs_khz: int
    turntable_speed: int


LTE_BAND_GROUPS: tuple[LTEBandGroupProfile, ...] = (
    LTEBandGroupProfile(
        key="lb",
        bands=(LTEBand.B5, LTEBand.B8, LTEBand.B20, LTEBand.B28),
        duplex=DuplexMode.FDD,
        test_ranges=(RangeId.RANGE_1, RangeId.RANGE_3),
        factor_keyword="1G HPF",
        mt8000_recall="LTE_FDD.PRM",
        scs_khz=15,
        turntable_speed=5,
    ),
    LTEBandGroupProfile(
        key="mhb_fdd",
        bands=(LTEBand.B1, LTEBand.B3, LTEBand.B7),
        duplex=DuplexMode.FDD,
        test_ranges=(RangeId.RANGE_1, RangeId.RANGE_2, RangeId.RANGE_4),
        factor_keyword="3G HPF",
        mt8000_recall="LTE_FDD.PRM",
        scs_khz=15,
        turntable_speed=5,
    ),
    LTEBandGroupProfile(
        key="mhb_tdd",
        bands=(LTEBand.B34, LTEBand.B38, LTEBand.B40, LTEBand.B41),
        duplex=DuplexMode.TDD,
        test_ranges=(RangeId.RANGE_1, RangeId.RANGE_2, RangeId.RANGE_4),
        factor_keyword="3G HPF",
        mt8000_recall="LTE_TDD.PRM",
        scs_khz=15,
        turntable_speed=3,
    ),
)


_RANGE_BY_BAND_TEST: dict[tuple[LTEBand, TestType], RangeId] = {
    **{
        (band, TestType.INBAND): RangeId.RANGE_1
        for band in (LTEBand.B5, LTEBand.B8, LTEBand.B20, LTEBand.B28)
    },
    **{
        (band, TestType.HARMONIC): RangeId.RANGE_3
        for band in (LTEBand.B5, LTEBand.B8, LTEBand.B20, LTEBand.B28)
    },
    **{
        (band, TestType.BILOG): RangeId.RANGE_1
        for band in (
            LTEBand.B1,
            LTEBand.B3,
            LTEBand.B7,
            LTEBand.B34,
            LTEBand.B38,
            LTEBand.B40,
            LTEBand.B41,
        )
    },
    **{
        (band, TestType.INBAND): RangeId.RANGE_2
        for band in (
            LTEBand.B1,
            LTEBand.B3,
            LTEBand.B7,
            LTEBand.B34,
            LTEBand.B38,
            LTEBand.B40,
            LTEBand.B41,
        )
    },
    **{
        (band, TestType.HARMONIC): RangeId.RANGE_4
        for band in (
            LTEBand.B1,
            LTEBand.B3,
            LTEBand.B7,
            LTEBand.B34,
            LTEBand.B38,
            LTEBand.B40,
            LTEBand.B41,
        )
    },
}


def _coerce_lte_band(band: LTEBand | str) -> LTEBand:
    if isinstance(band, LTEBand):
        return band

    normalized = str(band).strip()
    for member in LTEBand:
        if member.value.lower() == normalized.lower():
            return member
    raise ValueError(f"Unknown LTE band: {band!r}")


def find_lte_band_group(band: LTEBand | str) -> LTEBandGroupProfile:
    """입력 LTE band가 속한 그룹 설정을 반환한다."""

    band_key = _coerce_lte_band(band)
    for group in LTE_BAND_GROUPS:
        if band_key in group.bands:
            return group
    raise ValueError(f"Unknown LTE band: {band!r}")


def resolve_lte_range_id(band: LTEBand | str, test_type: TestType) -> RangeId:
    """LTE Band/TestType 조합에 해당하는 RangeId를 반환한다."""

    band_key = _coerce_lte_band(band)
    try:
        return _RANGE_BY_BAND_TEST[(band_key, test_type)]
    except KeyError as exc:
        if test_type is TestType.BILOG and band_key in {
            LTEBand.B5,
            LTEBand.B8,
            LTEBand.B20,
            LTEBand.B28,
        }:
            raise ValueError(f"Bilog not supported for LTE band {band_key.value!r}") from exc
        raise ValueError(
            "No LTE range mapping for "
            f"band {band_key.value!r} and test type {test_type.value}"
        ) from exc
