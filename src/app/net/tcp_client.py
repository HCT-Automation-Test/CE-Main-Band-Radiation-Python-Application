"""QTcpSocket 기반 TCP 클라이언트 래퍼."""
from __future__ import annotations

import logging
import queue
import threading
import time
import uuid
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtNetwork import QAbstractSocket, QTcpSocket

from app.net.protocol import (
    Event,
    ProtocolError,
    Request,
    Response,
    decode_frames,
    encode_frame,
)

logger = logging.getLogger(__name__)


class TcpClientError(RuntimeError):
    """TCP client transport 오류."""


class TcpClientTimeoutError(TimeoutError):
    """TCP client timeout 오류."""


@dataclass
class _SocketCommand:
    action: str
    timeout: float = 0.0
    host: str = ""
    port: int = 0
    request: Request | None = None
    done: threading.Event = field(default_factory=threading.Event)
    response: Response | None = None
    error: BaseException | None = None


class _SocketThread(QThread):
    """QTcpSocket을 소유하는 내부 worker thread."""

    event_message = Signal(object)
    connected_state_changed = Signal(bool)
    error_message = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._commands: queue.Queue[_SocketCommand] = queue.Queue()
        self._running = True

    def submit(self, command: _SocketCommand) -> None:
        self._commands.put(command)

    def run(self) -> None:
        socket = QTcpSocket()
        buffer = bytearray()
        responses: dict[str, Response] = {}

        try:
            while self._running:
                try:
                    command = self._commands.get(timeout=0.02)
                except queue.Empty:
                    self._poll_socket(socket, buffer, responses)
                    continue

                try:
                    self._handle_command(socket, buffer, responses, command)
                except Exception as exc:
                    command.error = exc
                    self._emit_error(str(exc))
                finally:
                    command.done.set()
        finally:
            self._close_socket(socket)

    def _handle_command(
        self,
        socket: QTcpSocket,
        buffer: bytearray,
        responses: dict[str, Response],
        command: _SocketCommand,
    ) -> None:
        if command.action == "connect":
            self._connect(socket, command.host, command.port, command.timeout)
            return
        if command.action == "disconnect":
            self._disconnect(socket)
            return
        if command.action == "send":
            if command.request is None:
                raise TcpClientError("request is not set")
            command.response = self._send_request(
                socket, buffer, responses, command.request, command.timeout
            )
            return
        if command.action == "stop":
            self._running = False
            return

        raise TcpClientError(f"unknown socket command: {command.action}")

    def _connect(self, socket: QTcpSocket, host: str, port: int, timeout: float) -> None:
        if socket.state() != QAbstractSocket.SocketState.UnconnectedState:
            socket.disconnectFromHost()
            socket.waitForDisconnected(500)

        socket.connectToHost(host, port)
        if not socket.waitForConnected(_timeout_msec(timeout)):
            raise TcpClientError(f"TCP 연결 실패: {socket.errorString()}")
        self.connected_state_changed.emit(True)

    def _disconnect(self, socket: QTcpSocket) -> None:
        self._close_socket(socket)

    def _send_request(
        self,
        socket: QTcpSocket,
        buffer: bytearray,
        responses: dict[str, Response],
        request: Request,
        timeout: float,
    ) -> Response:
        if socket.state() != QAbstractSocket.SocketState.ConnectedState:
            raise TcpClientError("TCP client is not connected")

        frame = encode_frame(request)
        written = socket.write(frame)
        if written != len(frame):
            raise TcpClientError(f"TCP frame write failed: {socket.errorString()}")
        socket.flush()
        if not self._wait_until_written(socket, timeout):
            raise TcpClientTimeoutError("TCP frame write timeout")

        deadline = time.monotonic() + timeout
        while True:
            response = responses.pop(request.id, None)
            if response is not None:
                return response

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TcpClientTimeoutError(
                    f"TCP response timeout: {request.target}.{request.command}"
                )

            wait_msec = min(50, _timeout_msec(remaining))
            if socket.bytesAvailable() <= 0 and not socket.waitForReadyRead(wait_msec):
                if socket.state() == QAbstractSocket.SocketState.UnconnectedState:
                    raise TcpClientError(f"TCP 연결 종료: {socket.errorString()}")
                continue
            self._read_and_dispatch(socket, buffer, responses)

    def _poll_socket(
        self,
        socket: QTcpSocket,
        buffer: bytearray,
        responses: dict[str, Response],
    ) -> None:
        if socket.state() != QAbstractSocket.SocketState.ConnectedState:
            return
        if socket.bytesAvailable() <= 0 and not socket.waitForReadyRead(20):
            if socket.state() == QAbstractSocket.SocketState.UnconnectedState:
                self.connected_state_changed.emit(False)
            return

        try:
            self._read_and_dispatch(socket, buffer, responses)
        except ProtocolError as exc:
            self._emit_error(str(exc))
            socket.abort()
            self.connected_state_changed.emit(False)

    def _read_and_dispatch(
        self,
        socket: QTcpSocket,
        buffer: bytearray,
        responses: dict[str, Response],
    ) -> None:
        data = bytes(socket.readAll())
        if not data:
            return

        buffer.extend(data)
        for message in decode_frames(buffer):
            if isinstance(message, Event):
                log = (
                    logger.debug
                    if message.target == "CO3000"
                    and message.command == "turntable_progress"
                    else logger.info
                )
                log(
                    "TCP event received: target=%s command=%s params=%s",
                    message.target,
                    message.command,
                    message.params,
                )
                self.event_message.emit(message)
            elif isinstance(message, Response):
                responses[message.id] = message
            else:
                self._emit_error(f"예상하지 않은 request 수신: {message.command}")

    def _close_socket(self, socket: QTcpSocket) -> None:
        if socket.state() == QAbstractSocket.SocketState.UnconnectedState:
            return

        socket.disconnectFromHost()
        if (
            socket.state() != QAbstractSocket.SocketState.UnconnectedState
            and not socket.waitForDisconnected(500)
        ):
            socket.abort()
        self.connected_state_changed.emit(False)

    def _wait_until_written(self, socket: QTcpSocket, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        while socket.bytesToWrite() > 0:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            socket.waitForBytesWritten(min(50, _timeout_msec(remaining)))
        return True

    def _emit_error(self, message: str) -> None:
        logger.error(message)
        self.error_message.emit(message)


def _timeout_msec(timeout: float) -> int:
    return max(1, int(timeout * 1000))


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
        self._thread: _SocketThread | None = None
        self._event_buffer: deque[Event] = deque(maxlen=1000)
        self._event_buffer_lock = threading.Lock()

    def connect_to(self, host: str, port: int, timeout: float = 5.0) -> None:
        """호스트에 연결 시도."""
        self._ensure_thread()
        command = _SocketCommand(
            action="connect",
            host=host,
            port=port,
            timeout=timeout,
        )
        self._submit_and_wait(command, timeout)

    def disconnect_from_host(self) -> None:
        """연결 종료."""
        thread = self._thread
        if thread is None:
            return

        try:
            disconnect_command = _SocketCommand(action="disconnect", timeout=1.0)
            self._submit_and_wait(disconnect_command, 1.0)
        finally:
            stop_command = _SocketCommand(action="stop")
            thread.submit(stop_command)
            stop_command.done.wait(1.0)
            if not thread.wait(1000):
                logger.error("TCP socket thread did not stop cleanly")
            self._thread = None


    def send_request(
        self,
        target: str,
        command: str,
        params: dict[str, Any] | None = None,
        timeout: float = 10.0,
    ) -> Response:
        """Request 전송 후 matching id의 Response를 동기 반환한다."""
        self._ensure_thread()
        request = Request(
            id=str(uuid.uuid4()),
            target=target,
            command=command,
            params=params or {},
        )
        socket_command = _SocketCommand(action="send", request=request, timeout=timeout)
        self._submit_and_wait(socket_command, timeout)
        if socket_command.response is None:
            raise TcpClientError("TCP response is empty")
        return socket_command.response

    def pop_events(self, predicate: Callable[[Event], bool]) -> list[Event]:
        """이미 수신된 비동기 Event 중 predicate와 맞는 항목을 꺼낸다."""

        with self._event_buffer_lock:
            matched: list[Event] = []
            remaining: deque[Event] = deque(maxlen=self._event_buffer.maxlen)
            while self._event_buffer:
                event = self._event_buffer.popleft()
                if predicate(event):
                    matched.append(event)
                else:
                    remaining.append(event)
            self._event_buffer = remaining
        return matched

    def close(self) -> None:
        """명시적 정리용 alias."""
        self.disconnect_from_host()

    def _ensure_thread(self) -> None:
        if self._thread is not None and self._thread.isRunning():
            return

        self._thread = _SocketThread()
        self._thread.event_message.connect(self._buffer_event, Qt.DirectConnection)
        self._thread.event_message.connect(self.event_received.emit)
        self._thread.connected_state_changed.connect(self.connected_changed.emit)
        self._thread.error_message.connect(self.error_occurred.emit)
        self._thread.start()

    def _buffer_event(self, event: Event) -> None:
        with self._event_buffer_lock:
            self._event_buffer.append(event)

    def _submit_and_wait(self, command: _SocketCommand, timeout: float) -> None:
        if self._thread is None:
            raise TcpClientError("TCP socket thread is not running")

        self._thread.submit(command)
        wait_timeout = max(1.0, timeout + 1.0)
        if not command.done.wait(wait_timeout):
            raise TcpClientTimeoutError(f"TCP command timeout: {command.action}")
        if command.error is not None:
            raise command.error
