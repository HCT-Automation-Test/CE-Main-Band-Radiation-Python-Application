"""Test Case 스키마 검증."""
from __future__ import annotations

from app.models.test_case import TestCase


def validate(case: TestCase) -> list[str]:
    """검증 에러 메시지 리스트 반환. 빈 리스트면 OK.

    TODO(spec): 밴드별 BW/RB 범위 등 도메인 규칙 확정 후 구현.
    """
    errors: list[str] = []
    return errors
