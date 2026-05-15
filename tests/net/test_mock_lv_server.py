from __future__ import annotations

import threading

import pytest

from app.models.enums import AntennaPol, FilterPath, InputPath, Modulation
from app.models.test_range import RANGE_6
from app.net import commands
from app.net.mock_lv_server import MockLvServer
from app.net.tcp_client import TcpClient


def _connect(client: TcpClient, server: MockLvServer, qtbot) -> None:
    with qtbot.waitSignal(client.connected_changed, timeout=1000):
        client.connect_to(server.host, server.port, timeout=1.0)


def test_mock_lv_server_harmonic_flow_creates_screenshots(
    qtbot,
    tmp_path,
) -> None:
    server = MockLvServer(port=0, temp_dir=tmp_path, turntable_delay_sec=0.01)
    server.start()
    client = TcpClient()
    events = []
    client.event_received.connect(events.append)

    try:
        _connect(client, server, qtbot)

        assert commands.connect_equipment(client) == {
            "FSV40": True,
            "MT8000A": True,
            "CO3000": True,
            "Switch Box": True,
            "3D Controller": True,
        }
        assert commands.setup_sa_startup_levels(
            client,
            atten_level_db=1.5,
            next_peak_search_level_db=-20,
        )
        assert commands.setup_mt8000(
            client,
            band=78,
            bw=100,
            modulation=Modulation.QPSK,
            rb_size=135,
            rb_offset=67,
            channel=636666,
        )
        assert commands.measure_fundamental(client, target_freq=3550.0) == 3550.25
        assert (tmp_path / "fundamental.png").is_file()

        assert commands.set_switch_box(
            client,
            input_path=InputPath.INPUT3,
            filter_path=FilterPath.HPF_6G,
        )
        assert commands.setup_sa(client, RANGE_6)
        commands.rotate_turntable(client, angle=360, turntable_speed=4)
        qtbot.waitUntil(
            lambda: any(event.command == "turntable_complete" for event in events),
            timeout=1000,
        )
        progress_events = [
            event for event in events if event.command == "turntable_progress"
        ]
        complete_events = [
            event for event in events if event.command == "turntable_complete"
        ]
        assert progress_events
        assert complete_events
        complete = complete_events[-1]
        assert complete.target == "CO3000"
        assert complete.command == "turntable_complete"
        assert complete.params == {}

        assert commands.measure_harmonics(client, fundamental=3550.25) == [
            -42.1,
            -48.0,
            -51.0,
            -56.2,
        ]
        assert (tmp_path / "harmonic.png").is_file()
        assert commands.set_antenna_pol(
            client,
            pol=AntennaPol.V,
            input_path=InputPath.INPUT3,
        )
        assert server.state.switch_input_path == 3
        assert server.state.switch_filter_path == 6
        assert server.state.antenna_pol == "V"
    finally:
        client.disconnect_from_host()
        server.stop()


def test_mock_lv_server_turntable_progress_event(qtbot, tmp_path) -> None:
    server = MockLvServer(port=0, temp_dir=tmp_path, turntable_delay_sec=0.01)
    server.start()
    client = TcpClient()
    events = []
    client.event_received.connect(events.append)

    try:
        _connect(client, server, qtbot)

        commands.rotate_turntable(client, angle=360, turntable_speed=4)

        qtbot.waitUntil(
            lambda: any(event.command == "turntable_progress" for event in events),
            timeout=1000,
        )
        progress = next(event for event in events if event.command == "turntable_progress")
        assert progress.params["Current Angle"] == 30.0
    finally:
        client.disconnect_from_host()
        server.stop()


def test_mock_lv_server_turntable_complete_after_background_connect(
    qtbot,
    tmp_path,
) -> None:
    server = MockLvServer(port=0, temp_dir=tmp_path, turntable_delay_sec=0.01)
    server.start()
    client = TcpClient()
    events = []
    client.event_received.connect(events.append)
    failures: list[BaseException] = []

    def connect_in_background() -> None:
        try:
            client.connect_to(server.host, server.port, timeout=1.0)
            commands.connect_equipment(client)
        except BaseException as exc:
            failures.append(exc)

    try:
        thread = threading.Thread(target=connect_in_background)
        thread.start()
        thread.join(timeout=2.0)

        assert not thread.is_alive()
        assert failures == []

        commands.rotate_turntable(client, angle=360, turntable_speed=4)

        qtbot.waitUntil(
            lambda: any(event.command == "turntable_complete" for event in events),
            timeout=1000,
        )
        complete = next(
            event for event in events if event.command == "turntable_complete"
        )
        assert complete.target == "CO3000"
        assert complete.params == {}
    finally:
        client.disconnect_from_host()
        server.stop()


def test_mock_lv_server_stop_turntable_suppresses_complete(qtbot, tmp_path) -> None:
    server = MockLvServer(port=0, temp_dir=tmp_path, turntable_delay_sec=0.3)
    server.start()
    client = TcpClient()
    events = []
    client.event_received.connect(events.append)

    try:
        _connect(client, server, qtbot)

        commands.rotate_turntable(client, angle=360, turntable_speed=4)
        commands.stop_turntable(client)
        qtbot.wait(500)

        assert not any(event.command == "turntable_complete" for event in events)
    finally:
        client.disconnect_from_host()
        server.stop()


def test_mock_lv_server_call_disconnected_scenario(qtbot, tmp_path) -> None:
    server = MockLvServer(port=0, temp_dir=tmp_path, scenario="call-disconnected")
    server.start()
    client = TcpClient()

    try:
        _connect(client, server, qtbot)
        commands.setup_mt8000(
            client,
            band=78,
            bw=100,
            modulation=Modulation.QPSK,
            rb_size=135,
            rb_offset=67,
            channel=636666,
        )

        assert commands.check_call_status(client) is False
    finally:
        client.disconnect_from_host()
        server.stop()


@pytest.mark.parametrize(
    ("scenario", "expected_command"),
    [
        ("turntable-error", "equipment_error"),
        ("turntable-timeout", None),
    ],
)
def test_mock_lv_server_turntable_scenarios(
    qtbot,
    tmp_path,
    scenario,
    expected_command,
) -> None:
    server = MockLvServer(
        port=0,
        temp_dir=tmp_path,
        scenario=scenario,
        turntable_delay_sec=0.01,
    )
    server.start()
    client = TcpClient()
    events = []
    client.event_received.connect(events.append)

    try:
        _connect(client, server, qtbot)
        commands.rotate_turntable(client, angle=360, turntable_speed=4)

        if expected_command is None:
            qtbot.wait(200)
            assert events == []
        else:
            qtbot.waitUntil(
                lambda: any(event.command == expected_command for event in events),
                timeout=1000,
            )
            assert any(event.command == expected_command for event in events)
    finally:
        client.disconnect_from_host()
        server.stop()


def test_mock_lv_server_bad_harmonic_result_scenario(qtbot, tmp_path) -> None:
    server = MockLvServer(port=0, temp_dir=tmp_path, scenario="bad-harmonic-result")
    server.start()
    client = TcpClient()

    try:
        _connect(client, server, qtbot)

        with pytest.raises(commands.CommandError, match="must contain 4 values"):
            commands.measure_harmonics(client, fundamental=3550.25)
    finally:
        client.disconnect_from_host()
        server.stop()


def test_mock_lv_server_rejects_unsupported_command(qtbot, tmp_path) -> None:
    server = MockLvServer(port=0, temp_dir=tmp_path)
    server.start()
    client = TcpClient()

    try:
        _connect(client, server, qtbot)

        response = client.send_request("FSV40", "Unknown Command", {}, timeout=1.0)

        assert response.status == "error"
        assert response.error == {"message": "unsupported command"}
    finally:
        client.disconnect_from_host()
        server.stop()
