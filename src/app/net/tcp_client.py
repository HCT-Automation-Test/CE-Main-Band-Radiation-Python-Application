"""QTcpSocket 기반 TCP 클라이언트 래퍼."""
from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QObject, Signal

from app.net.protocol import Event, Response

logger = logging.getLogger(__name__)

# TODO(spec): framing 결정 — 현재는 newline-delimited JSON을 가정.
# 명세 확정 후 길이 프리픽스(4-byte big-endian)로 교체 가능.


class TcpClient(QObject):
    """외부 LabVIEW 프로그램과의 TCP 연결 래퍼.

    - Request/Response는 id로 매칭
    - Event는 `event_received` 시그널로 UI/Runner에 전달
    """

    event_received = Signal(object)        # app.net.protocol.Event
    connected_changed = Signal(bool)
    error_occurred = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        # TODO(spec): QTcpSocket 인스턴스화 및 신호 연결
        self._socket: Any = None

    def connect_to(self, host: str, port: int) -> None:
        """호스트에 연결 시도."""
        raise NotImplementedError("spec TODO")

    def disconnect_from_host(self) -> None:
        """연결 종료."""
        raise NotImplementedError("spec TODO")

    def send_request(self, op: str, params: dict[str, Any], timeout: float) -> Response:
        """Request 전송 후 응답(또는 future)을 반환.

        TODO(spec): 반환 타입 확정 (동기 Response vs QFuture vs asyncio.Future).
        """
        raise NotImplementedError("spec TODO")
