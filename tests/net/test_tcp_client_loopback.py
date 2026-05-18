from __future__ import annotations

import socket
import threading

import pytest

from app.net.mock_server import MockServer
from app.net.protocol import Event, Request, Response
from app.net.tcp_client import TcpClient, TcpClientError, TcpClientTimeoutError


def test_tcp_client_loopback_roundtrip(qtbot) -> None:
    def handle_request(request: Request) -> Response:
        return Response(
            id=request.id,
            status="ok",
            result={
                "target": request.target,
                "command": request.command,
                "received": request.params,
            },
        )

    server = MockServer(response_handler=handle_request)
    server.start()
    client = TcpClient()

    try:
        with qtbot.waitSignal(client.connected_changed, timeout=1000):
            client.connect_to(server.host, server.port)

        response = client.send_request("fsv", "ping", {"value": 7}, timeout=1.0)

        assert response.status == "ok"
        assert response.result == {
            "target": "fsv",
            "command": "ping",
            "received": {"value": 7},
        }
        assert server.received_requests[0].target == "fsv"
        assert server.received_requests[0].command == "ping"
        assert server.received_requests[0].params == {"value": 7}
    finally:
        client.disconnect_from_host()
        server.stop()


def test_tcp_client_emits_event(qtbot) -> None:
    server = MockServer()
    server.start()
    client = TcpClient()

    try:
        client.connect_to(server.host, server.port)

        event = Event(
            id="evt-1",
            target="co3000",
            command="turntable_complete",
            params={"angle": 360},
        )
        with qtbot.waitSignal(client.event_received, timeout=1000) as blocker:
            server.send_event(event)

        received = blocker.args[0]
        assert received == event
    finally:
        client.disconnect_from_host()
        server.stop()


def test_tcp_client_event_consumer_does_not_run_on_socket_thread(qtbot) -> None:
    server = MockServer()
    server.start()
    client = TcpClient()
    test_thread_id = threading.get_ident()
    received_thread_ids: list[int] = []

    def record_event_thread(_event: Event) -> None:
        received_thread_ids.append(threading.get_ident())

    client.event_received.connect(record_event_thread)

    try:
        with qtbot.waitSignal(client.connected_changed, timeout=1000):
            client.connect_to(server.host, server.port)

        server.send_event(
            Event(
                id="evt-thread",
                target="co3000",
                command="turntable_complete",
                params={},
            )
        )

        qtbot.waitUntil(lambda: len(received_thread_ids) == 1, timeout=1000)

        assert received_thread_ids == [test_thread_id]
    finally:
        client.disconnect_from_host()
        server.stop()


def test_tcp_client_response_timeout(qtbot) -> None:
    server = MockServer()
    server.enqueue_response(None)
    server.start()
    client = TcpClient()

    try:
        client.connect_to(server.host, server.port)

        with pytest.raises(TcpClientTimeoutError, match="TCP response timeout"):
            client.send_request("fsv", "silent", {}, timeout=0.1)
    finally:
        client.disconnect_from_host()
        server.stop()


def test_tcp_client_connect_failure(qtbot) -> None:
    client = TcpClient()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        unused_port = probe.getsockname()[1]

    try:
        with pytest.raises(TcpClientError, match="TCP 연결 실패"):
            client.connect_to("127.0.0.1", unused_port, timeout=0.2)
    finally:
        client.disconnect_from_host()
