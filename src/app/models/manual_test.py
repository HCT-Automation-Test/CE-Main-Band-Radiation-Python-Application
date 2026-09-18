"""Manual Test 전용 입력 모델과 프리셋."""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum, IntEnum

from app.models.enums import InputPath


MANUAL_DETECTOR_MODES: tuple[str, ...] = (
    "Auto Peak",
    "Positive Peak",
    "Negative Peak",
    "Sample",
    "RMS",
    "Average",
    "Quasipeak",
    "CISPR Average",
    "RMS Average",
)


class ManualPresetId(IntEnum):
    """Manual Test에서만 사용하는 주파수 프리셋 식별자."""

    PRESET_1 = 1
    PRESET_2 = 2
    PRESET_3 = 3
    PRESET_4 = 4
    PRESET_5 = 5
    PRESET_6 = 6
    PRESET_7 = 7
    PRESET_8 = 8
    PRESET_9 = 9

    @property
    def label(self) -> str:
        return f"Preset {self.value}"


@dataclass(frozen=True)
class ManualFrequencyPreset:
    """TestCase Range와 독립적인 Manual 주파수 프리셋."""

    id: ManualPresetId
    start_frequency_mhz: float
    stop_frequency_mhz: float
    rbw_mhz: float
    vbw_mhz: float

    @property
    def label(self) -> str:
        return (
            f"{_format_frequency(self.start_frequency_mhz)} ~ "
            f"{_format_frequency(self.stop_frequency_mhz)}"
        )


def _format_frequency(frequency_mhz: float) -> str:
    if frequency_mhz >= 1000.0:
        return f"{frequency_mhz / 1000.0:g} GHz"
    return f"{frequency_mhz:g} MHz"


MANUAL_FREQUENCY_PRESETS: tuple[ManualFrequencyPreset, ...] = (
    ManualFrequencyPreset(ManualPresetId.PRESET_1, 30.0, 1000.0, 0.1, 0.3),
    ManualFrequencyPreset(ManualPresetId.PRESET_2, 1000.0, 3000.0, 1.0, 3.0),
    ManualFrequencyPreset(ManualPresetId.PRESET_3, 1000.0, 12750.0, 1.0, 3.0),
    ManualFrequencyPreset(ManualPresetId.PRESET_4, 3000.0, 12750.0, 1.0, 3.0),
    ManualFrequencyPreset(ManualPresetId.PRESET_5, 1000.0, 6000.0, 1.0, 3.0),
    ManualFrequencyPreset(ManualPresetId.PRESET_6, 6000.0, 18000.0, 1.0, 3.0),
    ManualFrequencyPreset(ManualPresetId.PRESET_7, 1000.0, 3000.0, 0.1, 0.3),
    ManualFrequencyPreset(ManualPresetId.PRESET_8, 1000.0, 4000.0, 3.0, 3.0),
    ManualFrequencyPreset(ManualPresetId.PRESET_9, 3000.0, 4000.0, 3.0, 3.0),
)

MANUAL_FREQUENCY_PRESETS_BY_ID = {
    preset.id: preset for preset in MANUAL_FREQUENCY_PRESETS
}


def get_manual_frequency_preset(
    preset_id: ManualPresetId | int,
) -> ManualFrequencyPreset:
    """프리셋 식별자에 대응하는 Manual 주파수 정의를 반환한다."""

    try:
        normalized = ManualPresetId(preset_id)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Unknown manual preset: {preset_id!r}") from exc
    return MANUAL_FREQUENCY_PRESETS_BY_ID[normalized]


class ManualMast(str, Enum):
    """Manual UI에 노출하는 Mast 선택지."""

    BILOG_3M = "3m Bilog"
    HORN_3M = "3m Horn"
    MAST_1M = "1m Mast"

    @property
    def input_path(self) -> InputPath:
        return {
            ManualMast.BILOG_3M: InputPath.INPUT1,
            ManualMast.HORN_3M: InputPath.INPUT2,
            ManualMast.MAST_1M: InputPath.INPUT3,
        }[self]


@dataclass(frozen=True)
class ManualSaSettings:
    """FSV40 Manual Set에 필요한 UI 입력값."""

    start_frequency_mhz: float
    stop_frequency_mhz: float
    rbw_mhz: float
    vbw_mhz: float
    sweep_point: int
    sweep_time_sec: float
    saturation_time_sec: float
    atten_level_db: float
    detector_mode: str
    limit_dbm: float

    def __post_init__(self) -> None:
        numeric_values = (
            self.start_frequency_mhz,
            self.stop_frequency_mhz,
            self.rbw_mhz,
            self.vbw_mhz,
            self.sweep_time_sec,
            self.saturation_time_sec,
            self.atten_level_db,
            self.limit_dbm,
        )
        if any(
            isinstance(value, bool)
            or not isinstance(value, int | float)
            or not math.isfinite(float(value))
            for value in numeric_values
        ):
            raise ValueError("숫자 입력은 유한한 값이어야 합니다.")
        if self.start_frequency_mhz < 0 or self.stop_frequency_mhz < 0:
            raise ValueError("주파수는 0 이상이어야 합니다.")
        if self.start_frequency_mhz >= self.stop_frequency_mhz:
            raise ValueError("Start Frequency는 Stop Frequency보다 작아야 합니다.")
        if self.rbw_mhz <= 0 or self.vbw_mhz <= 0:
            raise ValueError("RBW와 VBW는 0보다 커야 합니다.")
        if (
            isinstance(self.sweep_point, bool)
            or not isinstance(self.sweep_point, int)
        ):
            raise ValueError("Sweep Point는 정수여야 합니다.")
        if self.saturation_time_sec < 0:
            raise ValueError("Saturation Time은 0 이상이어야 합니다.")
        if self.detector_mode not in MANUAL_DETECTOR_MODES:
            raise ValueError(f"지원하지 않는 Detector Mode입니다: {self.detector_mode}")
