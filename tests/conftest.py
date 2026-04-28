"""pytest 공유 fixture."""
from __future__ import annotations

import shutil
import uuid
from pathlib import Path

import pytest


@pytest.fixture
def placeholder_fixture() -> None:
    """TODO(spec): 공용 픽스처 추가."""
    return None


@pytest.fixture
def tmp_path() -> Path:
    """Windows sandbox에서 pytest 기본 0o700 temp dir 생성을 피한다."""
    root = Path("test-temp")
    root.mkdir(mode=0o777, exist_ok=True)

    path = root / f"t_{uuid.uuid4().hex}"
    path.mkdir(mode=0o777)

    yield path

    shutil.rmtree(path, ignore_errors=True)
