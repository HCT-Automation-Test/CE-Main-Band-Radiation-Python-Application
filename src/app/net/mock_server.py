"""개발/테스트용 loopback TCP mock 서버."""
from __future__ import annotations

import logging
import queue
import socket
import threading
import time
from collections.abc import Callable

from app.net.protocol import (
    Event,
    Message,
    ProtocolError,
    Request,
    Response,
    decode_frames,
    encode_frame,
)

logger = logging.getLogger(__name__)

ResponseHandler = Callable[[Request], Response | Event | None]
ScriptedResponse = Response | Event | ResponseHandler | None
_NO_SCRIPTED_RESPONSE = object()


class MockServer:
    """간이 TCP 서버 스텁. 테스트 픽스처에서 사용."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 0,
        *,
        response_handler: ResponseHandler | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.response_handler = response_handler
        self.requests: queue.Queue[Request] = queue.Queue()
        self.received_requests: list[Request] = []

        self._scripted_responses: queue.Queue[ScriptedResponse] = queue.Queue()
        self._server_socket: socket.socket | None = None
        self._client_socket: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop_requested = threading.Event()
        self._client_connected = threading.Condition()

    def start(self) -> None:
        """서버 시작. 바인드한 포트를 self.port에 기록한다."""
        if self._thread is not None and self._thread.is_alive():
            return

        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.port))
        server_socket.listen(1)
        server_socket.settimeout(0.1)

        self._server_socket = server_socket
        self.port = server_socket.getsockname()[1]
        self._stop_requested.clear()
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """서버 종료."""
        self._stop_requested.set()
        self._close_socket(self._client_socket)
        self._close_socket(self._server_socket)
        self._client_socket = None
        self._server_socket = None
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None

    def enqueue_response(self, response: ScriptedResponse) -> None:
        """다음 요청에 대해 사용할 응답을 등록한다."""
        self._scripted_responses.put(response)

    def send_message(self, message: Message, timeout: float = 1.0) -> None:
        """현재 연결된 client로 event/response frame을 직접 전송한다."""
        client_socket = self._wait_for_client(timeout)
        client_socket.sendall(encode_frame(message))

    def send_event(self, event: Event, timeout: float = 1.0) -> None:
        """현재 연결된 client로 event frame을 전송한다."""
        self.send_message(event, timeout=timeout)

    def _serve(self) -> None:
        while not self._stop_requested.is_set():
            try:
                assert self._server_socket is not None
                client_socket, _address = self._server_socket.accept()
            except socket.timeout:
                continue
            except OSError:
                break

            client_socket.settimeout(0.1)
            with self._client_connected:
                self._client_socket = client_socket
                self._client_connected.notify_all()

            try:
                self._handle_client(client_socket)
            finally:
                self._close_socket(client_socket)
                with self._client_connected:
                    if self._client_socket is client_socket:
                        self._client_socket = None

    def _handle_client(self, client_socket: socket.socket) -> None:
        buffer = bytearray()
        while not self._stop_requested.is_set():
            try:
                chunk = client_socket.recv(4096)
            except socket.timeout:
                continue
            except OSError:
                break

            if not chunk:
                break
            buffer.extend(chunk)

            try:
                messages = decode_frames(buffer)
            except ProtocolError:
                logger.exception("mock server frame parse failed")
                break

            for message in messages:
                if not isinstance(message, Request):
                    logger.warning("mock server ignored non-request message: %s", message)
                    continue
                self.requests.put(message)
                self.received_requests.append(message)
                response = self._next_response(message)
                if response is not None:
                    client_socket.sendall(encode_frame(response))

    def _next_response(self, request: Request) -> Response | Event | None:
        try:
            scripted = self._scripted_responses.get_nowait()
        except queue.Empty:
            scripted = _NO_SCRIPTED_RESPONSE

        if callable(scripted):
            return scripted(request)
        if scripted is not _NO_SCRIPTED_RESPONSE:
            return scripted
        if self.response_handler is not None:
            return self.response_handler(request)
        return Response(id=request.id, op=request.op, result={"ok": True}, error=None)

    def _wait_for_client(self, timeout: float) -> socket.socket:
        deadline = time.monotonic() + timeout
        with self._client_connected:
            while self._client_socket is None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("mock server client connection timeout")
                self._client_connected.wait(remaining)
            return self._client_socket

    @staticmethod
    def _close_socket(target: socket.socket | None) -> None:
        if target is None:
            return
        try:
            target.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            target.close()
        except OSError:
            pass
