"""Band 그룹 프로파일 데이터 모델."""
from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import FilterMode, TestType
from app.models.switch_box import parse_band_number


@dataclass(frozen=True)
class BandGroupProfile:
    """CE NR Radiated 측정에서 같은 공통 설정을 공유하는 Band 묶음.

    test_ranges는 이 그룹이 사용하는 전역 Range 인덱스(1~6)의 부분집합이다.
    hpf_factor는 Switch Box의 HPF 경로, sa_recall은 FSV40에 로드할 프리셋 이름.
    """

    bands: tuple[int, ...]
    test_ranges: tuple[int, ...]
    hpf_factor: FilterMode
    sa_recall: str
    scs_khz: int
    turntable_speed: int


BAND_GROUPS: tuple[BandGroupProfile, ...] = (
    BandGroupProfile(
        bands=(5, 8, 20, 26, 28, 71),
        test_ranges=(1, 3),
        hpf_factor=FilterMode.HPF_1G,
        sa_recall="SA_FDD",
        scs_khz=15,
        turntable_speed=6,
    ),
    BandGroupProfile(
        bands=(1, 3, 7),
        test_ranges=(1, 2, 4),
        hpf_factor=FilterMode.HPF_3G,
        sa_recall="SA_FDD",
        scs_khz=15,
        turntable_speed=6,
    ),
    BandGroupProfile(
        bands=(38, 40, 41),
        test_ranges=(1, 2, 4),
        hpf_factor=FilterMode.HPF_3G,
        sa_recall="SA_TDD",
        scs_khz=30,
        turntable_speed=4,
    ),
    BandGroupProfile(
        bands=(77, 78, 79),
        test_ranges=(1, 5, 6),
        hpf_factor=FilterMode.HPF_6G,
        sa_recall="SA_TDD",
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
    """Band 문자열("n78", "78")이 속한 BandGroupProfile 반환."""

    band_number = parse_band_number(band)
    for group in BAND_GROUPS:
        if band_number in group.bands:
            return group
    raise ValueError(f"Unknown band: {band!r}")


def resolve_range_id(band: str, test_type: TestType) -> int:
    """(Band, TestType) 조합에 쓰이는 전역 Range 인덱스(1~6) 반환."""

    band_number = parse_band_number(band)
    try:
        return RANGE_BY_BAND_TEST[(band_number, test_type)]
    except KeyError as exc:
        if test_type is TestType.BILOG and band_number in {5, 8, 20, 26, 28, 71}:
            raise ValueError(f"Bilog not supported for band {band!r}") from exc
        raise ValueError(
            f"No range mapping for band {band!r} and test type {test_type.value}"
        ) from exc
