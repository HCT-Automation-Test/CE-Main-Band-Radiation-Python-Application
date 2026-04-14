"""Test Case CSV 로더/세이버 및 Range 확장 로직."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from app.models.range_preset import RangePreset
from app.models.test_case import TestCase


def load_csv(path: Path) -> list[TestCase]:
    """CSV에서 `TestCase` 리스트 로드."""
    # TODO(spec): CSV 스키마(필드 순서, 구분자, 헤더 다국어) 확정 후 구현
    raise NotImplementedError("spec TODO")


def save_csv(path: Path, cases: Iterable[TestCase]) -> None:
    """`TestCase` 리스트를 CSV로 저장."""
    # TODO(spec): CSV 스키마 확정 후 구현
    raise NotImplementedError("spec TODO")


def expand_ranges(
    cases: Iterable[TestCase],
    presets: dict[str, RangePreset],
) -> list[TestCase]:
    """UI에서 다중 Range를 선택한 경우 Range별로 TC를 분해.

    TODO(spec): 확장 규칙(카테시안? 선택 리스트?) 확정 필요.
    """
    raise NotImplementedError("spec TODO")
