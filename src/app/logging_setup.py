"""로깅 구성. 파일 + 콘솔 + (UI 미러 훅 placeholder)."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

_DEFAULT_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def setup_logging(log_file: Optional[Path] = None, level: int = logging.INFO) -> None:
    """루트 로거 기본 구성. 이미 구성돼 있으면 no-op."""
    root = logging.getLogger()
    if root.handlers:
        return
    root.setLevel(level)

    formatter = logging.Formatter(_DEFAULT_FORMAT)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    if log_file is not None:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(formatter)
        root.addHandler(fh)

    # TODO(spec): UI QPlainTextEdit 미러 핸들러 부착 지점.
