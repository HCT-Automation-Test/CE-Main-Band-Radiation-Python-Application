"""측정 결과 모델."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias


@dataclass
class FundamentalResult:
    """MeasureFundamental 상태의 측정 결과."""

    screenshot_path: Path | None = None
    fundamental_frequency_mhz: float | None = None


@dataclass
class HarmonicResult:
    """MeasureHarmonics 상태의 측정 결과."""

    screenshot_path: Path | None = None
    harmonic_2nd_peak_level_dbm: float | None = None
    harmonic_3rd_peak_level_dbm: float | None = None
    harmonic_4th_peak_level_dbm: float | None = None
    harmonic_5th_peak_level_dbm: float | None = None

    @property
    def has_recordable_peak(self) -> bool:
        """Excel에 기입할 limit 초과 peak가 있는지 반환한다."""
        return any(
            peak_level is not None
            for peak_level in (
                self.harmonic_2nd_peak_level_dbm,
                self.harmonic_3rd_peak_level_dbm,
                self.harmonic_4th_peak_level_dbm,
                self.harmonic_5th_peak_level_dbm,
            )
        )


@dataclass
class InbandResult:
    """MeasureInBand 상태의 측정 결과."""

    screenshot_path: Path | None = None
    inband_peak_level_dbm: float | None = None

    @property
    def has_recordable_peak(self) -> bool:
        """Excel에 기입할 limit 초과 peak가 있는지 반환한다."""
        return self.inband_peak_level_dbm is not None


@dataclass
class BilogResult:
    """MeasureBilog 상태의 측정 결과."""

    screenshot_path: Path | None = None
    bilog_peak_level_dbm: float | None = None

    @property
    def has_recordable_peak(self) -> bool:
        """Excel에 기입할 limit 초과 peak가 있는지 반환한다."""
        return self.bilog_peak_level_dbm is not None


MeasurementResult: TypeAlias = (
    FundamentalResult | HarmonicResult | InbandResult | BilogResult
)
