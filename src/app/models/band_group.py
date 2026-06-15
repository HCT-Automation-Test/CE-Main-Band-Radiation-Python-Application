"""Band 그룹 상수 및 lookup 헬퍼."""
from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import TestType
from app.models.switch_box import parse_band_number
from app.models.test_range import RangeId


@dataclass(frozen=True)
class BandGroupProfile:
    """여러 Test Case가 공통으로 사용하는 Band 그룹 설정.

    `test_ranges`는 그룹에서 사용하는 전역 Range 상수 목록이다.
    `sa_recall`은 Spectrum Analyzer(FSV40)에 로드할 preset/recall 이름이고,
    `mt8000_recall`은 MT8000A recall 이름이다.
    Switch Box filter 선택은 band group이 아니라 Range 정의에서 관리한다.
    Band 그룹 정의는 별도 JSON이 아니라 이 모듈의 상수로 유지한다.
    """

    key: str
    bands: tuple[int, ...]
    test_ranges: tuple[RangeId, ...]
    sa_recall: str
    mt8000_recall: str
    scs_khz: int
    turntable_speed: int


BAND_GROUPS: tuple[BandGroupProfile, ...] = (
    BandGroupProfile(
        key="lb",
        bands=(5, 8, 20, 26, 28, 71),
        test_ranges=(RangeId.RANGE_1, RangeId.RANGE_3),
        sa_recall="1G HPF",
        mt8000_recall="SA_FDD",
        scs_khz=15,
        turntable_speed=5,
    ),
    BandGroupProfile(
        key="mhb_fdd",
        bands=(1, 3, 7),
        test_ranges=(RangeId.RANGE_1, RangeId.RANGE_2, RangeId.RANGE_4),
        sa_recall="3G HPF",
        mt8000_recall="SA_FDD",
        scs_khz=15,
        turntable_speed=5,
    ),
    BandGroupProfile(
        key="mhb_tdd",
        bands=(38, 40, 41),
        test_ranges=(RangeId.RANGE_1, RangeId.RANGE_2, RangeId.RANGE_4),
        sa_recall="3G HPF",
        mt8000_recall="SA_TDD",
        scs_khz=30,
        turntable_speed=3,
    ),
    BandGroupProfile(
        key="uhb_tdd",
        bands=(77, 78, 79),
        test_ranges=(RangeId.RANGE_1, RangeId.RANGE_5, RangeId.RANGE_6),
        sa_recall="6G HPF",
        mt8000_recall="SA_TDD",
        scs_khz=30,
        turntable_speed=3,
    ),
)


RANGE_BY_BAND_TEST: dict[tuple[int, TestType], RangeId] = {
    **{(b, TestType.INBAND): RangeId.RANGE_1 for b in (5, 8, 20, 26, 28, 71)},
    **{(b, TestType.HARMONIC): RangeId.RANGE_3 for b in (5, 8, 20, 26, 28, 71)},
    **{(b, TestType.BILOG): RangeId.RANGE_1 for b in (1, 3, 7)},
    **{(b, TestType.INBAND): RangeId.RANGE_2 for b in (1, 3, 7)},
    **{(b, TestType.HARMONIC): RangeId.RANGE_4 for b in (1, 3, 7)},
    **{(b, TestType.BILOG): RangeId.RANGE_1 for b in (38, 40, 41)},
    **{(b, TestType.INBAND): RangeId.RANGE_2 for b in (38, 40, 41)},
    **{(b, TestType.HARMONIC): RangeId.RANGE_4 for b in (38, 40, 41)},
    **{(b, TestType.BILOG): RangeId.RANGE_1 for b in (77, 78, 79)},
    **{(b, TestType.INBAND): RangeId.RANGE_5 for b in (77, 78, 79)},
    **{(b, TestType.HARMONIC): RangeId.RANGE_6 for b in (77, 78, 79)},
}


def find_band_group(band: str) -> BandGroupProfile:
    """입력한 band가 속한 BandGroupProfile을 반환한다."""

    band_number = parse_band_number(band)
    for group in BAND_GROUPS:
        if band_number in group.bands:
            return group
    raise ValueError(f"Unknown band: {band!r}")


def resolve_range_id(band: str, test_type: TestType) -> RangeId:
    """Band/TestType 조합에 해당하는 RangeId를 반환한다."""

    band_number = parse_band_number(band)
    try:
        return RANGE_BY_BAND_TEST[(band_number, test_type)]
    except KeyError as exc:
        if test_type is TestType.BILOG and band_number in {5, 8, 20, 26, 28, 71}:
            raise ValueError(f"Bilog not supported for band {band!r}") from exc
        raise ValueError(
            f"No range mapping for band {band!r} and test type {test_type.value}"
        ) from exc
