"""Band 그룹 상수 및 lookup 헬퍼."""
from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import TestType
from app.models.switch_box import parse_band_number


@dataclass(frozen=True)
class BandGroupProfile:
    """여러 Test Case가 공통으로 사용하는 Band 그룹 설정.

    `test_ranges`는 그룹에서 사용하는 전역 Range 인덱스(1~6) 목록이다.
    `sa_recall`은 Spectrum Analyzer(FSV40)에 로드할 preset/recall 이름이고,
    `mt8000_recall`은 MT8000A recall 이름이다.
    Switch Box filter 선택은 band group이 아니라 range preset에서 관리한다.
    Band 그룹 정의는 별도 JSON이 아니라 이 모듈의 상수로 유지한다.
    """

    bands: tuple[int, ...]
    test_ranges: tuple[int, ...]
    sa_recall: str
    mt8000_recall: str
    scs_khz: int
    turntable_speed: int


BAND_GROUPS: tuple[BandGroupProfile, ...] = (
    BandGroupProfile(
        bands=(5, 8, 20, 26, 28, 71),
        test_ranges=(1, 3),
        sa_recall="1G HPF",
        mt8000_recall="SA_FDD",
        scs_khz=15,
        turntable_speed=6,
    ),
    BandGroupProfile(
        bands=(1, 3, 7),
        test_ranges=(1, 2, 4),
        sa_recall="3G HPF",
        mt8000_recall="SA_FDD",
        scs_khz=15,
        turntable_speed=6,
    ),
    BandGroupProfile(
        bands=(38, 40, 41),
        test_ranges=(1, 2, 4),
        sa_recall="3G HPF",
        mt8000_recall="SA_TDD",
        scs_khz=30,
        turntable_speed=4,
    ),
    BandGroupProfile(
        bands=(77, 78, 79),
        test_ranges=(1, 5, 6),
        sa_recall="6G HPF",
        mt8000_recall="SA_TDD",
        scs_khz=30,
        turntable_speed=4,
    ),
)


RANGE_BY_BAND_TEST: dict[tuple[int, TestType], int] = {
    **{(b, TestType.INBAND): 1 for b in (5, 8, 20, 26, 28, 71)},
    **{(b, TestType.HARMONIC): 3 for b in (5, 8, 20, 26, 28, 71)},
    **{(b, TestType.BILOG): 1 for b in (1, 3, 7)},
    **{(b, TestType.INBAND): 2 for b in (1, 3, 7)},
    **{(b, TestType.HARMONIC): 4 for b in (1, 3, 7)},
    **{(b, TestType.BILOG): 1 for b in (38, 40, 41)},
    **{(b, TestType.INBAND): 2 for b in (38, 40, 41)},
    **{(b, TestType.HARMONIC): 4 for b in (38, 40, 41)},
    **{(b, TestType.BILOG): 1 for b in (77, 78, 79)},
    **{(b, TestType.INBAND): 5 for b in (77, 78, 79)},
    **{(b, TestType.HARMONIC): 6 for b in (77, 78, 79)},
}


def find_band_group(band: str) -> BandGroupProfile:
    """입력한 band가 속한 BandGroupProfile을 반환한다."""

    band_number = parse_band_number(band)
    for group in BAND_GROUPS:
        if band_number in group.bands:
            return group
    raise ValueError(f"Unknown band: {band!r}")


def resolve_range_id(band: str, test_type: TestType) -> int:
    """Band/TestType 조합에 해당하는 전역 Range id(1~6)를 반환한다."""

    band_number = parse_band_number(band)
    try:
        return RANGE_BY_BAND_TEST[(band_number, test_type)]
    except KeyError as exc:
        if test_type is TestType.BILOG and band_number in {5, 8, 20, 26, 28, 71}:
            raise ValueError(f"Bilog not supported for band {band!r}") from exc
        raise ValueError(
            f"No range mapping for band {band!r} and test type {test_type.value}"
        ) from exc
