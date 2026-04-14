"""측정 결과 모델."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class MeasurementResult:
    """시퀀스 1회 실행 결과."""

    fundamental_freq_hz: float = 0.0
    harmonic_peaks: list[dict[str, Any]] = field(default_factory=list)
    screenshot_paths: list[Path] = field(default_factory=list)
    pass_fail: bool = False
    raw_meta: dict[str, Any] = field(default_factory=dict)
    # TODO(spec): harmonic_peaks 항목 스키마 확정 (order, freq, level, limit, margin 등)
