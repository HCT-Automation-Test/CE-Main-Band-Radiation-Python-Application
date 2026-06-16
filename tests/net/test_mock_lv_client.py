from __future__ import annotations

import io
from typing import Any

from app.net.mock_lv_client import MockLvClientConsole, parse_line
from app.net.mock_lv_server import MOCK_TDF_FILE_LIST, MockLvServer
from app.net.protocol import Response
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


class _StaticClient:
    def send_request(
        self,
        target: str,
        command: str,
        params: dict[str, Any] | None = None,
        timeout: float = 10.0,
    ) -> Response:
        _ = (target, command, params, timeout)
        return Response(id="response-id", status="ok", result={"Amplitude": -42.1})


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


def test_mock_lv_client_measure_inband() -> None:
    output = io.StringIO()
    console = MockLvClientConsole(_StaticClient(), output=output, auto_events=False)

    assert console.execute_line("measure-inband limit=-30")

    text = output.getvalue()
    assert "REQUEST  FSV40 / Mark Inband" in text
    assert '"Limit": -30.0' in text
    assert "STATUS   ok" in text
    assert '"Amplitude": -42.1' in text
    assert "RETURN   -42.1" in text


def test_mock_lv_client_measure_harmonics_prints_marker_return(
    qtbot,
    tmp_path,
) -> None:
    server = MockLvServer(port=0, temp_dir=tmp_path)
    server.start()
    client = TcpClient()
    output = io.StringIO()
    console = MockLvClientConsole(client, output=output, auto_events=False)

    try:
        _connect(client, server, qtbot)

        assert console.execute_line("measure-harmonics fundamental=3550.25")

        text = output.getvalue()
        assert "REQUEST  FSV40 / Mark Harmonic" in text
        assert '"Amplitude": [-42.1, -48.0, -51.0, -56.2]' in text
        assert '"Frequency": [7100.5, 10650.75, 14201.0, 17751.25]' in text
        assert "RETURN   " in text
        assert '"order": 2' in text
        assert '"amplitude_dbm": -42.1' in text
        assert '"peak_frequency_mhz": 7100.5' in text
    finally:
        client.disconnect_from_host()
        server.stop()


def test_mock_lv_client_tdf_commands(qtbot, tmp_path) -> None:
    server = MockLvServer(port=0, temp_dir=tmp_path)
    server.start()
    client = TcpClient()
    output = io.StringIO()
    console = MockLvClientConsole(client, output=output, auto_events=False)

    try:
        _connect(client, server, qtbot)

        assert console.execute_line("tdf-list")
        assert console.execute_line("tdf-all-off")
        assert console.execute_line("set-tdf file=NR_Radiated.tdf")

        text = output.getvalue()
        assert "REQUEST  FSV40 / Get TDF List" in text
        assert "REQUEST  FSV40 / TDF All Off" in text
        assert "REQUEST  FSV40 / Set TDF" in text
        assert '"TDF File List": ' in text
        for file_name in MOCK_TDF_FILE_LIST:
            assert file_name in text
        assert '"TDF File Name": "NR_Radiated.tdf"' in text
        assert "RETURN   true" in text
    finally:
        client.disconnect_from_host()
        server.stop()


def test_mock_lv_client_help_includes_tdf_commands() -> None:
    output = io.StringIO()
    console = MockLvClientConsole(_NoopClient(), output=output)

    assert console.execute_line("help")

    text = output.getvalue()
    assert "tdf-list" in text
    assert "tdf-all-off" in text
    assert "set-tdf file=NR_Radiated.tdf" in text
    assert "measure-inband limit=-30" in text
