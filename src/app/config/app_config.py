"""애플리케이션 설정 로더."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class AppConfig:
    """런타임 설정값. JSON에서 로드."""

    tcp_host: str
    tcp_port: int
    tcp_timeout_s: float
    excel_template_path: Path

    @classmethod
    def load(cls, path: Path) -> "AppConfig":
        """JSON 파일에서 설정을 읽어 인스턴스 생성."""
        path = Path(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        # TODO(spec): 필드 검증/기본값/환경변수 오버라이드 정책 확정
        return cls(
            tcp_host=str(data["tcp_host"]),
            tcp_port=int(data["tcp_port"]),
            tcp_timeout_s=float(data.get("tcp_timeout_s", 5.0)),
            excel_template_path=Path(data["excel_template_path"]),
        )
