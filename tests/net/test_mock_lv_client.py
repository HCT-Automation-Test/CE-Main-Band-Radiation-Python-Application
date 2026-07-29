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
        assert '"Frequency": [7100500000.0, 10650750000.0, 14201000000.0, 17751250000.0]' in text
        assert "RETURN   " in text
        assert '"order": 2' in text
        assert '"amplitude_dbm": -42.1' in text
        assert '"peak_frequency_mhz": 7100.5' in text
    finally:
        client.disconnect_from_host()
        server.stop()



def test_mock_lv_client_manual_commands(qtbot, tmp_path) -> None:
    server = MockLvServer(port=0, temp_dir=tmp_path)
    server.start()
    client = TcpClient()
    output = io.StringIO()
    console = MockLvClientConsole(client, output=output, auto_events=False)

    try:
        _connect(client, server, qtbot)

        assert console.execute_line("measure-harmonic-manual fundamental=3550.25")
        assert console.execute_line("measure-inband-manual limit=-30")
        assert console.execute_line("get-screenshot")
        assert console.execute_line("marker-peak marker=2 excursion=6.5")
        assert console.execute_line("marker-next marker=3 excursion=7.5")
        assert console.execute_line("marker-off marker=4 excursion=8.5")
        assert console.execute_line("marker-all-off")

        text = output.getvalue()
        assert "REQUEST  FSV40 / Measure Harmonic" in text
        assert "REQUEST  FSV40 / Measure Inband" in text
        assert "REQUEST  FSV40 / Get Screenshot" in text
        assert "REQUEST  FSV40 / Marker Peak" in text
        assert "REQUEST  FSV40 / Marker Next" in text
        assert "REQUEST  FSV40 / Marker OFF" in text
        assert "REQUEST  FSV40 / Marker ALL OFF" in text
        assert '"Fundamental Frequency": 3550.25' in text
        assert '"Limit": -30.0' in text
        assert '"Marker Index": 2' in text
        assert '"Excursion": 6.5' in text
        assert (tmp_path / "screenshot.png").is_file()
    finally:
        client.disconnect_from_host()
        server.stop()


def test_mock_lv_client_lte_call_handover_and_status_aliases(qtbot, tmp_path) -> None:
    server = MockLvServer(port=0, temp_dir=tmp_path)
    server.start()
    client = TcpClient()
    output = io.StringIO()
    console = MockLvClientConsole(client, output=output, auto_events=False)

    try:
        _connect(client, server, qtbot)

        assert console.execute_line(
            "setup-lte-mt8000 bw=1.4 ul_channel=18000 rb_offset=0"
        )
        assert console.execute_line("check-call")
        assert console.execute_line(
            "lte-handover bw=10.0 mid_channel=18300 ul_channel=18500 "
            "rb_offset=99 max_retry_count=7 waiting_time=11"
        )
        assert console.execute_line("check-call-status")

        assert [
            (request.target, request.command, request.params)
            for request in server.received_requests
        ] == [
            (
                "MT8000A",
                "LTE Call",
                {
                    "BandWidth": "1.4",
                    "UL Channel": 18000,
                    "RB Offset": 0,
                    "Max Retry Count": 3,
                    "Waiting Time": 5,
                },
            ),
            ("MT8000A", "Check Call Status", {}),
            (
                "MT8000A",
                "LTE Handover",
                {
                    "BandWidth": "10",
                    "Mid Channel": 18300,
                    "UL Channel": 18500,
                    "RB Offset": 99,
                    "Max Retry Count": 7,
                    "Waiting Time": 11,
                },
            ),
            ("MT8000A", "Check Call Status", {}),
        ]

        text = output.getvalue()
        assert "REQUEST  MT8000A / LTE Call" in text
        assert "REQUEST  MT8000A / LTE Handover" in text
        assert text.count("REQUEST  MT8000A / Check Call Status") == 2
        assert text.count("RETURN   true") == 4
    finally:
        client.disconnect_from_host()
        server.stop()


def test_mock_lv_client_nr_handover_passes_retry_and_waiting_time(
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

        assert console.execute_line(
            "handover mid_channel=636666 band=78 bw=100 modulation=QPSK "
            "rb_size=135 rb_offset=67 channel=640000 "
            "max_retry_count=9 waiting_time=12"
        )

        request = server.received_requests[-1]
        assert (request.target, request.command, request.params) == (
            "MT8000A",
            "NR Handover",
            {
                "Mid Channel": 636666,
                "Band": 78,
                "BandWidth": 100,
                "Center Channel": 640000,
                "RB Size": 135,
                "RB Offset": 67,
                "Modulation": "QPSK",
                "Max Retry Count": 9,
                "Waiting Time": 12,
            },
        )
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
    assert "setup-lte-mt8000 bw=20 ul_channel=18100 rb_offset=0" in text
    assert "lte-handover bw=20 mid_channel=18300" in text
    assert "handover mid_channel=636666" in text
    assert "[max_retry_count=3] [waiting_time=5]" in text
    assert "check-call-status (alias: check-call)" in text
