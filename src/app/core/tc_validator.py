"""Test Case 검증."""
from __future__ import annotations

from collections.abc import Iterable

from app.models.enums import Generation
from app.models.lte_supported_bandwidths import validate_lte_supported_bandwidth
from app.models.supported_bandwidths import validate_supported_bandwidth
from app.models.test_case import TestCase


def validate(case: TestCase) -> list[str]:
    """검증 에러 메시지 리스트를 반환한다. 빈 리스트면 OK."""

    try:
        if case.generation is Generation.LTE:
            validate_lte_supported_bandwidth(case.band, case.bandwidth)
        else:
            validate_supported_bandwidth(case.band, case.bandwidth)
    except ValueError as exc:
        return [str(exc)]
    return []


def validate_queue(cases: Iterable[TestCase]) -> list[str]:
    """NR 계열과 LTE가 섞인 실행 Queue를 거부한다."""

    generation_families = {
        "LTE" if case.generation is Generation.LTE else "NR" for case in cases
    }
    if len(generation_families) > 1:
        return ["NR/LTE 혼합 Queue는 실행할 수 없습니다"]
    return []
