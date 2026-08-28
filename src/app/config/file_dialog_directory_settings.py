"""런타임 기준 파일 대화상자 경로."""
from __future__ import annotations

import sys
from pathlib import Path


def runtime_base_directory() -> Path:
    """배포 EXE 또는 개발 작업 디렉터리를 반환한다."""

    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd().resolve()
