"""Band 그룹 프로파일 데이터 모델."""
from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import FilterMode


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
