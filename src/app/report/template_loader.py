"""Excel 템플릿/매핑 로더."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_template(path: Path) -> dict[str, Any]:
    """템플릿 매핑 JSON을 로드."""
    path = Path(path)
    # TODO(spec): 매핑 스키마 확정 후 타입/검증 추가
    return json.loads(path.read_text(encoding="utf-8"))
