"""Test Case 검증."""
from __future__ import annotations

from app.models.supported_bandwidths import validate_supported_bandwidth
from app.models.test_case import TestCase


def validate(case: TestCase) -> list[str]:
    """검증 에러 메시지 리스트를 반환한다. 빈 리스트면 OK."""

    try:
        validate_supported_bandwidth(case.band, case.bandwidth)
    except ValueError as exc:
        return [str(exc)]
    return []
