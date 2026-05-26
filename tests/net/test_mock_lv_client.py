from __future__ import annotations

import io
from typing import Any

from app.net.mock_lv_client import MockLvClientConsole, parse_line
from app.net.mock_lv_server import MockLvServer
from app.net.tcp_client import TcpClient


def _connect(client: TcpClient, server: MockLvServer, qtbot) -> None:
    with qtbot.waitSignal(client.connected_changed, timeout=1000):
        client.connect_to(server.host, server.port, timeout=1.0)


def test_parse_line_handles_key_value_and_quoted_json() -> None:
    name, args = parse_line(
        "raw target=FSV40 command=\"Unknown Command\" params='{\"x\": 1}'"
    )

    assert name == "raw"
    assert args == {
        "target": "FSV40",
        "command": "Unknown Command",
        "params": '{"x": 1}',
    }


def test_parse_line_normalizes_hyphenated_keys() -> None:
    name, args = parse_line("rotate turntable-speed=4 wait=true")

    assert name == "rotate"
    assert args == {"turntable_speed": "4", "wait": "true"}


class _NoopClient:
    def send_request(
        self,
        target: str,
        command: str,
        params: dict[str, Any] | None = None,
        timeout: float = 10.0,
    ) -> None:
        _ = (target, command, params, timeout)


def test_unknown_command_keeps_console_alive() -> None:
    output = io.StringIO()
    console = MockLvClientConsole(_NoopClient(), output=output)

    assert console.execute_line("unknown-command")
    assert "unknown command: unknown-command" in output.getvalue()


def test_mock_lv_client_connect_and_measure_fundamental(qtbot, tmp_path) -> None:
    server = MockLvServer(port=0, temp_dir=tmp_path)
    server.start()
    client = TcpClient()
    output = io.StringIO()
    console = MockLvClientConsole(client, output=output, auto_events=False)

    try:
        _connect(client, server, qtbot)

        assert console.execute_line("connect")
        assert console.execute_line("measure-fundamental target_freq=3550")

        text = output.getvalue()
        assert "REQUEST  FSV40 / Connect" in text
        assert "REQUEST  FSV40 / Search Fundamental Frequency" in text
        assert "STATUS   ok" in text
        assert "Fundamental Frequency" in text
    finally:
        client.disconnect_from_host()
        server.stop()


def test_mock_lv_client_rotate_can_wait_for_complete_event(qtbot, tmp_path) -> None:
    server = MockLvServer(port=0, temp_dir=tmp_path, turntable_delay_sec=0.01)
    server.start()
    client = TcpClient()
    output = io.StringIO()
    console = MockLvClientConsole(client, output=output, auto_events=False)

    try:
        _connect(client, server, qtbot)

        assert console.execute_line("rotate angle=60 speed=4 wait=true timeout=2")

        text = output.getvalue()
        assert "REQUEST  CO3000 / Move TurnTable" in text
        assert "EVENT    CO3000 / turntable_complete" in text
        assert "WAIT     CO3000 / turntable_complete completed" in text
    finally:
        client.disconnect_from_host()
        server.stop()


def test_mock_lv_client_raw_error_response_does_not_exit(qtbot, tmp_path) -> None:
    server = MockLvServer(port=0, temp_dir=tmp_path)
    server.start()
    client = TcpClient()
    output = io.StringIO()
    console = MockLvClientConsole(client, output=output, auto_events=False)

    try:
        _connect(client, server, qtbot)

        assert console.execute_line(
            "raw target=FSV40 command=\"Unknown Command\" params='{}'"
        )
        assert console.execute_line("events")

        text = output.getvalue()
        assert "REQUEST  FSV40 / Unknown Command" in text
        assert "STATUS   error" in text
        assert "unsupported command" in text
        assert "No events." in text
    finally:
        client.disconnect_from_host()
        server.stop()
