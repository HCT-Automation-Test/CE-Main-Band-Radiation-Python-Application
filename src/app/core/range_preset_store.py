"""Range 프리셋 JSON 로더."""
from __future__ import annotations

from pathlib import Path

from app.models.range_preset import RangePreset


def load(path: Path) -> dict[str, RangePreset]:
    """JSON 파일에서 이름→RangePreset 매핑 로드."""
    # TODO(spec): JSON 스키마 확정 및 필드 정규화
    raise NotImplementedError("spec TODO")
