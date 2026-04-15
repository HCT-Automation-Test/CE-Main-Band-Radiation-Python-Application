"""Test Case CSV 로더/세이버 및 TestType 기반 Range 해석 로직."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Iterable

from app.models.band_group import resolve_range_id
from app.models.enums import TestType
from app.models.test_case import TestCase


def load_csv(path: Path) -> list[TestCase]:
    """CSV에서 `TestCase` 리스트 로드."""
    # TODO(spec): CSV 스키마(필드 순서, 구분자, 헤더 다국어) 확정 후 구현
    raise NotImplementedError("spec TODO")


def save_csv(path: Path, cases: Iterable[TestCase]) -> None:
    """`TestCase` 리스트를 CSV로 저장."""
    # TODO(spec): CSV 스키마 확정 후 구현
    raise NotImplementedError("spec TODO")


def resolve_test_range(case: TestCase, test_type: TestType) -> TestCase:
    """band/test type 조합에 맞는 Range를 채운 TestCase 사본을 반환한다."""

    return replace(case, test_range=resolve_range_id(case.band, test_type))
