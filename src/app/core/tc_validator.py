"""Test Case 검증."""
from __future__ import annotations

from collections.abc import Iterable

from app.models.enums import Generation
from app.models.lte_supported_bandwidths import validate_lte_supported_bandwidth
from app.models.nsa_anchor import validate_anchor_band_for_generation
from app.models.supported_bandwidths import validate_supported_bandwidth
from app.models.test_case import TestCase


def validate(case: TestCase) -> list[str]:
    """검증 에러 메시지 리스트를 반환한다. 빈 리스트면 OK."""

    try:
        validate_anchor_band_for_generation(case.generation, case.anchor_band)
        if case.generation is Generation.LTE:
            validate_lte_supported_bandwidth(case.band, case.bandwidth)
        else:
            validate_supported_bandwidth(case.band, case.bandwidth)
    except ValueError as exc:
        return [str(exc)]
    return []


def validate_queue(cases: Iterable[TestCase]) -> list[str]:
    """개별 TestCase와 단일 Generation 실행 Queue 규칙을 검증한다."""

    case_list = list(cases)
    errors: list[str] = []
    generations = {case.generation for case in case_list}
    if len(generations) > 1:
        detected = ", ".join(sorted(generation.value for generation in generations))
        errors.append(
            f"Generation 혼합 Queue는 실행할 수 없습니다: {detected}"
        )

    for index, case in enumerate(case_list, start=1):
        errors.extend(
            f"Test Case {index}: {message}" for message in validate(case)
        )
    return errors
