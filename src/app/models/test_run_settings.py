"""시험 실행 시작 시점의 사용자 입력 설정값."""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TestRunSettings:
    """Test Manager Start 입력값 묶음."""

    __test__ = False

    eut_name: str
    template_path: Path
    screenshot_root_dir: Path
    saturation_time_sec: float
    connection_waiting_time_sec: int
    atten_level_db: float
    next_peak_search_level_db: float
    active_tdf_file_name: str
    custom_turntable_speed: int | None = None

    def __post_init__(self) -> None:
        eut_name = self.eut_name.strip()
        active_tdf_file_name = self.active_tdf_file_name.strip()
        template_path = Path(self.template_path)
        screenshot_root_dir = Path(self.screenshot_root_dir)
        saturation_time_sec = float(self.saturation_time_sec)
        connection_waiting_time_sec = _coerce_int(
            self.connection_waiting_time_sec,
            field_name="connection_waiting_time_sec",
        )
        atten_level_db = float(self.atten_level_db)
        next_peak_search_level_db = float(self.next_peak_search_level_db)
        custom_turntable_speed = None
        if self.custom_turntable_speed is not None:
            custom_turntable_speed = _coerce_int(
                self.custom_turntable_speed,
                field_name="custom_turntable_speed",
            )

        if not eut_name:
            raise ValueError("eut_name is required")
        if not active_tdf_file_name:
            raise ValueError("active_tdf_file_name is required")
        if not template_path.is_file():
            raise ValueError("template_path must be an existing file")
        if not screenshot_root_dir.is_dir():
            raise ValueError("screenshot_root_dir must be an existing directory")
        if not math.isfinite(saturation_time_sec) or saturation_time_sec < 0:
            raise ValueError("saturation_time_sec must be a number greater than or equal to 0")
        if connection_waiting_time_sec <= 0:
            raise ValueError("connection_waiting_time_sec must be an integer greater than 0")
        if not math.isfinite(atten_level_db) or atten_level_db < 0:
            raise ValueError("atten_level_db must be a number greater than or equal to 0")
        if not math.isfinite(next_peak_search_level_db):
            raise ValueError("next_peak_search_level_db must be a number")
        if custom_turntable_speed is not None and custom_turntable_speed <= 0:
            raise ValueError("custom_turntable_speed must be an integer greater than 0")

        object.__setattr__(self, "eut_name", eut_name)
        object.__setattr__(self, "active_tdf_file_name", active_tdf_file_name)
        object.__setattr__(self, "template_path", template_path)
        object.__setattr__(self, "screenshot_root_dir", screenshot_root_dir)
        object.__setattr__(self, "saturation_time_sec", saturation_time_sec)
        object.__setattr__(
            self,
            "connection_waiting_time_sec",
            connection_waiting_time_sec,
        )
        object.__setattr__(self, "atten_level_db", atten_level_db)
        object.__setattr__(self, "next_peak_search_level_db", next_peak_search_level_db)
        object.__setattr__(self, "custom_turntable_speed", custom_turntable_speed)


def _coerce_int(value: int | float | str, *, field_name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not value.is_integer():
            raise ValueError(f"{field_name} must be an integer")
        return int(value)
    text = str(value).strip()
    if not text:
        raise ValueError(f"{field_name} must be an integer")
    try:
        return int(text)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an integer") from exc
