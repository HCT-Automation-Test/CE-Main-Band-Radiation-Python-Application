"""Band 그룹 JSON 로더."""
from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from app.models.band_group import BandGroupProfile
from app.models.switch_box import parse_filter_mode


_REQUIRED_FIELDS = (
    "bands",
    "test_ranges",
    "hpf_factor",
    "sa_recall",
    "scs_khz",
    "turntable_speed",
)


def _require_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"Field {field_name!r} must be an integer")
    return value


def _require_str(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"Field {field_name!r} must be a string")
    return value


def _require_int_tuple(value: Any, field_name: str) -> tuple[int, ...]:
    if not isinstance(value, list):
        raise ValueError(f"Field {field_name!r} must be a list of integers")
    return tuple(_require_int(item, f"{field_name}[]") for item in value)


def _parse_group(index: int, payload: Mapping[str, Any]) -> BandGroupProfile:
    payload_keys = set(payload)
    required_keys = set(_REQUIRED_FIELDS)

    missing_fields = sorted(required_keys - payload_keys)
    unexpected_fields = sorted(payload_keys - required_keys)
    if missing_fields or unexpected_fields:
        errors: list[str] = []
        if missing_fields:
            errors.append(
                f"Missing fields in band group #{index}: {', '.join(missing_fields)}"
            )
        if unexpected_fields:
            errors.append(
                f"Unexpected fields in band group #{index}: {', '.join(unexpected_fields)}"
            )
        raise ValueError(" ".join(errors))

    return BandGroupProfile(
        bands=_require_int_tuple(payload["bands"], "bands"),
        test_ranges=_require_int_tuple(payload["test_ranges"], "test_ranges"),
        hpf_factor=parse_filter_mode(_require_str(payload["hpf_factor"], "hpf_factor")),
        sa_recall=_require_str(payload["sa_recall"], "sa_recall"),
        scs_khz=_require_int(payload["scs_khz"], "scs_khz"),
        turntable_speed=_require_int(payload["turntable_speed"], "turntable_speed"),
    )


def load(path: Path) -> tuple[BandGroupProfile, ...]:
    """JSON 파일에서 BandGroupProfile 시퀀스 로드."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Band group JSON root must be an object")

    groups_payload = data.get("groups")
    if not isinstance(groups_payload, list):
        raise ValueError("Band group JSON must contain a 'groups' array")

    groups: list[BandGroupProfile] = []
    for index, group in enumerate(groups_payload):
        if not isinstance(group, Mapping):
            raise ValueError(f"Band group #{index} must be an object")
        groups.append(_parse_group(index, group))
    return tuple(groups)
