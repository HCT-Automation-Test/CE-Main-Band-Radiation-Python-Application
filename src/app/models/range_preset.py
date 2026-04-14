"""Range 프리셋 데이터 모델 (§3.4)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class RangePreset:
    """Spectrum Analyzer + Switch Box 파라미터 번들.

    TODO(spec): 단위(Hz/kHz), 경로 표현 규칙은 명세 §3.4 확정 후 재정비.
    """

    start_freq_hz: float
    stop_freq_hz: float
    rbw_hz: float
    vbw_hz: float
    limit_dbm: float
    sweep_point: int
    input_path: str
    filter_path: str

    @property
    def sweep_points(self) -> int:
        return self.sweep_point
