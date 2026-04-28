"""SA 스크린샷 저장소."""
from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

from app.models.nr_channel_lookup import resolve_target_frequency_mhz
from app.models.test_case import TestCase

_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_TRAFFIC_DIR = "Traffic"
_RAT_DIR = "5G"
_SA_DIR = "SA"
_FUNDAMENTAL_SUFFIX = "Fundamental Frequency"


def _sanitize_path_part(value: str, *, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} is required")

    sanitized = _INVALID_FILENAME_CHARS.sub("_", normalized).strip(" .")
    if not sanitized:
        raise ValueError(f"{field_name} has no valid filesystem characters")
    return sanitized


def _format_compact_mhz(value_mhz: float) -> str:
    return f"{value_mhz:.15g}MHz"


def _format_range_frequency(value_mhz: float) -> str:
    if value_mhz >= 1000.0:
        return f"{value_mhz / 1000.0:.15g}GHz"
    return _format_compact_mhz(value_mhz)


def _format_target_frequency(value_mhz: float) -> str:
    return f"{value_mhz:.3f}MHz"


def build_sa_screenshot_path(
    *,
    root_dir: Path,
    model_name: str,
    test_case: TestCase,
) -> Path:
    """TestCase와 Range 정의로 최종 SA 스크린샷 경로를 만든다."""

    model = _sanitize_path_part(model_name, field_name="model_name")
    test_range = test_case.range_definition
    target_frequency_mhz = resolve_target_frequency_mhz(
        test_case.band,
        test_case.bandwidth,
        test_case.test_channel,
    )
    band = test_case.band.value
    dut_ant_position = test_case.dut_ant_position.name
    axis_pol = f"{test_case.dut_axis.value}{test_case.antenna_pol.value}"

    filename = (
        f"{model}_{_TRAFFIC_DIR}_{_RAT_DIR}_{band}_{dut_ant_position}_"
        f"{_SA_DIR}_{_format_target_frequency(target_frequency_mhz)}_"
        f"{_format_range_frequency(test_range.start_freq)}_"
        f"{_format_range_frequency(test_range.stop_freq)}_{axis_pol}.png"
    )

    return (
        Path(root_dir)
        / model
        / _TRAFFIC_DIR
        / _RAT_DIR
        / band
        / dut_ant_position
        / _SA_DIR
        / filename
    )


def build_fundamental_screenshot_path(
    *,
    root_dir: Path,
    model_name: str,
    test_case: TestCase,
) -> Path:
    """Fundamental SA 스크린샷의 최종 저장 경로를 만든다."""

    model = _sanitize_path_part(model_name, field_name="model_name")
    target_frequency_mhz = resolve_target_frequency_mhz(
        test_case.band,
        test_case.bandwidth,
        test_case.test_channel,
    )
    band = test_case.band.value
    dut_ant_position = test_case.dut_ant_position.name

    filename = (
        f"{model}_{_TRAFFIC_DIR}_{_RAT_DIR}_{band}_{dut_ant_position}_"
        f"{_SA_DIR}_{_format_target_frequency(target_frequency_mhz)}_"
        f"{_FUNDAMENTAL_SUFFIX}.png"
    )

    return (
        Path(root_dir)
        / model
        / _TRAFFIC_DIR
        / _RAT_DIR
        / band
        / dut_ant_position
        / _SA_DIR
        / filename
    )


def finalize_sa_screenshot(
    *,
    source_path: Path,
    root_dir: Path | None,
    model_name: str,
    test_case: TestCase,
    events: Any | None = None,
) -> Path:
    """임시 SA 스크린샷을 최종 폴더/파일명으로 복사하고 경로를 반환한다."""

    if root_dir is None:
        raise ValueError("screenshot_root_dir is required")
    if not source_path.is_file():
        raise FileNotFoundError(f"{source_path} does not exist")

    destination = build_sa_screenshot_path(
        root_dir=root_dir,
        model_name=model_name,
        test_case=test_case,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, destination)

    if events is not None and hasattr(events, "screenshot_saved"):
        events.screenshot_saved.emit(str(destination))
    return destination


def finalize_fundamental_screenshot(
    *,
    source_path: Path,
    root_dir: Path | None,
    model_name: str,
    test_case: TestCase,
    events: Any | None = None,
) -> Path:
    """Fundamental SA 스크린샷을 최종 폴더/파일명으로 복사하고 경로를 반환한다."""

    if root_dir is None:
        raise ValueError("screenshot_root_dir is required")
    if not source_path.is_file():
        raise FileNotFoundError(f"{source_path} does not exist")

    destination = build_fundamental_screenshot_path(
        root_dir=root_dir,
        model_name=model_name,
        test_case=test_case,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, destination)

    if events is not None and hasattr(events, "screenshot_saved"):
        events.screenshot_saved.emit(str(destination))
    return destination


class ScreenshotStore:
    """스크린샷 파일 저장 경로 관리."""

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = Path(base_dir)

    def save(self, image_bytes: bytes, name: str) -> Path:
        """바이트를 파일로 저장하고 경로를 반환한다."""

        filename = _sanitize_path_part(name, field_name="name")
        path = self.base_dir / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(image_bytes)
        return path
