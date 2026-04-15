"""Range 프리셋 JSON 로더."""
from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from app.models.switch_box import parse_filter_mode, parse_input_path
from app.models.range_preset import RangePreset


_REQUIRED_FIELDS = (
    "start_freq",
    "stop_freq",
    "rbw",
    "vbw",
    "limit",
    "sweep_point",
    "input_path",
    "filter_mode",
)


def _require_number(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"Field {field_name!r} must be a number")
    return float(value)


def _require_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"Field {field_name!r} must be an integer")
    return value


def _require_str(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"Field {field_name!r} must be a string")
    return value


def _parse_preset(name: str, payload: Mapping[str, Any]) -> RangePreset:
    payload_keys = set(payload)
    required_keys = set(_REQUIRED_FIELDS)

    missing_fields = sorted(required_keys - payload_keys)
    unexpected_fields = sorted(payload_keys - required_keys)
    if missing_fields or unexpected_fields:
        errors: list[str] = []
        if missing_fields:
            errors.append(f"Missing fields in range preset {name!r}: {', '.join(missing_fields)}")
        if unexpected_fields:
            errors.append(
                f"Unexpected fields in range preset {name!r}: {', '.join(unexpected_fields)}"
            )
        raise ValueError(" ".join(errors))

    return RangePreset(
        start_freq=_require_number(payload["start_freq"], "start_freq"),
        stop_freq=_require_number(payload["stop_freq"], "stop_freq"),
        rbw=_require_number(payload["rbw"], "rbw"),
        vbw=_require_number(payload["vbw"], "vbw"),
        limit=_require_number(payload["limit"], "limit"),
        sweep_point=_require_int(payload["sweep_point"], "sweep_point"),
        input_path=parse_input_path(_require_str(payload["input_path"], "input_path")),
        filter_mode=parse_filter_mode(_require_str(payload["filter_mode"], "filter_mode")),
    )


def load(path: Path) -> dict[str, RangePreset]:
    """JSON 파일에서 이름→RangePreset 매핑 로드."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Range preset JSON root must be an object")

    presets: dict[str, RangePreset] = {}
    for name, payload in data.items():
        if name.startswith("_"):
            continue
        if not isinstance(name, str):
            raise ValueError("Range preset names must be strings")
        if not isinstance(payload, Mapping):
            raise ValueError(f"Range preset {name!r} must be an object")

        presets[name] = _parse_preset(name, payload)

    return presets
