"""SA 스크린샷 저장소."""
from __future__ import annotations

from pathlib import Path


class ScreenshotStore:
    """스크린샷 파일 저장 경로 관리."""

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = Path(base_dir)
        # TODO(spec): 세션/TC별 하위 폴더 구조 확정

    def save(self, image_bytes: bytes, name: str) -> Path:
        """바이트를 파일로 저장하고 경로 반환."""
        raise NotImplementedError("spec TODO")
