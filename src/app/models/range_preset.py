"""Range 프리셋 데이터 모델 (§3.4)."""
from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import FilterMode, InputPath


@dataclass
class RangePreset:
    """Spectrum Analyzer + Switch Box 파라미터 번들.

    주파수 관련 값은 MHz, limit는 dBm 기준이다.
    """

    start_freq: float
    stop_freq: float
    rbw: float
    vbw: float
    limit: float
    sweep_point: int
    input_path: InputPath
    filter_mode: FilterMode

    @property
    def sweep_points(self) -> int:
        return self.sweep_point
