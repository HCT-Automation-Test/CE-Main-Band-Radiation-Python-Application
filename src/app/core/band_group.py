"""Band 그룹 상수 + (Band, TestType) → Range 인덱스 lookup."""
from __future__ import annotations

from app.models.band_group import BandGroupProfile
from app.models.enums import FilterMode, TestType
from app.models.switch_box import parse_band_number


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


# (band_number, TestType) → range_id. Bilog 불가 조합(n5/8/20/26/28/71)은 의도적으로 누락.
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
