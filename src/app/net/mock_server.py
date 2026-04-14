"""개발/테스트용 loopback TCP mock 서버."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class MockServer:
    """간이 TCP 서버 스텁. 테스트 픽스처에서 사용."""

    def __init__(self, host: str = "127.0.0.1", port: int = 0) -> None:
        self.host = host
        self.port = port
        # TODO(spec): 응답 규칙(scripted responses)/이벤트 주입 훅 정의

    def start(self) -> None:
        """서버 시작. 바인드한 포트를 self.port에 기록한다."""
        raise NotImplementedError("spec TODO")

    def stop(self) -> None:
        """서버 종료."""
        raise NotImplementedError("spec TODO")
