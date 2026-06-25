"""시험 실행 시작 시점의 사용자 입력 설정값."""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from pathlib import Path

_MAX_NEXT_PEAK_SEARCH_LEVEL_DB = 80.0
_MAX_CUSTOM_TURNTABLE_SPEED = 10
_SCREENSHOT_DIR_NAME = "screenshots"


def default_screenshot_root_dir() -> Path:
    """런타임 환경 기준 기본 스크린샷 저장 경로를 반환한다."""

    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / _SCREENSHOT_DIR_NAME
    return Path.home() / "Desktop" / _SCREENSHOT_DIR_NAME


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
    manual_marker_enabled: bool = False

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
        if screenshot_root_dir.exists() and not screenshot_root_dir.is_dir():
            raise ValueError("screenshot_root_dir must be a directory")
        if not math.isfinite(saturation_time_sec) or saturation_time_sec < 0:
            raise ValueError("saturation_time_sec must be a number greater than or equal to 0")
        if connection_waiting_time_sec <= 0:
            raise ValueError("connection_waiting_time_sec must be an integer greater than 0")
        if not math.isfinite(atten_level_db) or atten_level_db < 0:
            raise ValueError("atten_level_db must be a number greater than or equal to 0")
        if (
            not math.isfinite(next_peak_search_level_db)
            or next_peak_search_level_db <= 0
            or next_peak_search_level_db > _MAX_NEXT_PEAK_SEARCH_LEVEL_DB
        ):
            raise ValueError(
                "next_peak_search_level_db must be a number greater than 0 "
                f"and less than or equal to {_MAX_NEXT_PEAK_SEARCH_LEVEL_DB:g}"
            )
        if (
            custom_turntable_speed is not None
            and not 1 <= custom_turntable_speed <= _MAX_CUSTOM_TURNTABLE_SPEED
        ):
            raise ValueError(
                "custom_turntable_speed must be an integer between 1 and "
                f"{_MAX_CUSTOM_TURNTABLE_SPEED}"
            )

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
        object.__setattr__(
            self,
            "manual_marker_enabled",
            bool(self.manual_marker_enabled),
        )


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

