from __future__ import annotations

import threading
import time

import pytest

from app.models.enums import AntennaPol, FilterPath, InputPath, Modulation
from app.models.test_range import RANGE_6
from app.net import commands
from app.net.mock_lv_server import MOCK_TDF_FILE_LIST, MockLvServer, _MINIMAL_PNG
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


def test_mock_lv_server_copies_random_screenshot_fixture(
    qtbot,
    tmp_path,
) -> None:
    fixture_dir = tmp_path / "mock_screenshots"
    fixture_dir.mkdir()
    fixture_bytes = {
        b"fixture-a-png": fixture_dir / "a.png",
        b"fixture-b-png": fixture_dir / "b.png",
    }
    for content, path in fixture_bytes.items():
        path.write_bytes(content)
    (fixture_dir / "ignored.jpg").write_bytes(b"ignored")

    server = MockLvServer(
        port=0,
        temp_dir=tmp_path,
        turntable_delay_sec=0.01,
        screenshot_fixture_dir=fixture_dir,
        screenshot_random_seed=7,
    )
    server.start()
    client = TcpClient()

    try:
        _connect(client, server, qtbot)

        assert commands.measure_fundamental(client, target_freq=3550.0) == 3550.25
        assert (tmp_path / "fundamental.png").read_bytes() in fixture_bytes

        assert commands.measure_harmonics(client, fundamental=3550.25) == [
            -42.1,
            -48.0,
            -51.0,
            -56.2,
        ]
        assert (tmp_path / "harmonic.png").read_bytes() in fixture_bytes
    finally:
        client.disconnect_from_host()
        server.stop()


@pytest.mark.parametrize("fixture_dir_name", ["missing", "empty"])
def test_mock_lv_server_falls_back_to_minimal_png_without_fixtures(
    qtbot,
    tmp_path,
    fixture_dir_name,
) -> None:
    fixture_dir = tmp_path / fixture_dir_name
    if fixture_dir_name == "empty":
        fixture_dir.mkdir()

    server = MockLvServer(
        port=0,
        temp_dir=tmp_path,
        turntable_delay_sec=0.01,
        screenshot_fixture_dir=fixture_dir,
    )
    server.start()
    client = TcpClient()

    try:
        _connect(client, server, qtbot)

        assert commands.measure_fundamental(client, target_freq=3550.0) == 3550.25
        assert (tmp_path / "fundamental.png").read_bytes() == _MINIMAL_PNG
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


def test_mock_lv_server_get_turntable_angle_returns_current_state(qtbot, tmp_path) -> None:
    server = MockLvServer(port=0, temp_dir=tmp_path, turntable_delay_sec=0.01)
    server.state.current_angle = 270.0
    server.start()
    client = TcpClient()

    try:
        _connect(client, server, qtbot)

        assert commands.get_turntable_angle(client) == 270.0
        request = server.received_requests[-1]
        assert request.target == "CO3000"
        assert request.command == "Get TurnTable Angle"
        assert request.params == {}
    finally:
        client.disconnect_from_host()
        server.stop()


def test_mock_lv_server_set_reference_sends_complete_event(qtbot, tmp_path) -> None:
    server = MockLvServer(
        port=0,
        temp_dir=tmp_path,
        set_reference_delay_sec=0.01,
    )
    server.start()
    client = TcpClient()
    events = []
    client.event_received.connect(events.append)

    try:
        _connect(client, server, qtbot)

        assert commands.set_reference_co3000(client)
        qtbot.waitUntil(
            lambda: any(
                event.target == "CO3000"
                and event.command == "set_reference_complete"
                for event in events
            ),
            timeout=1000,
        )

        request = server.received_requests[-1]
        assert request.target == "CO3000"
        assert request.command == "Set Reference"
        assert request.params == {}
    finally:
        client.disconnect_from_host()
        server.stop()


def test_mock_lv_server_self_alignment_sends_complete_event(qtbot, tmp_path) -> None:
    server = MockLvServer(
        port=0,
        temp_dir=tmp_path,
        self_alignment_delay_sec=0.01,
    )
    server.start()
    client = TcpClient()
    events = []
    client.event_received.connect(events.append)

    try:
        _connect(client, server, qtbot)

        assert commands.self_align_fsv40(client)
        qtbot.waitUntil(
            lambda: any(
                event.target == "FSV40"
                and event.command == "self_alignment_complete"
                for event in events
            ),
            timeout=1000,
        )

        request = server.received_requests[-1]
        assert request.target == "FSV40"
        assert request.command == "Self Alignment"
        assert request.params == {}
    finally:
        client.disconnect_from_host()
        server.stop()


def test_mock_lv_server_connect_equipment_completes_in_background(
    tmp_path,
) -> None:
    server = MockLvServer(port=0, temp_dir=tmp_path, turntable_delay_sec=0.01)
    server.start()
    client = TcpClient()
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
        assert [request.command for request in server.received_requests] == [
            "Connect",
            "Connect",
            "Connect",
            "Connect",
            "Connect",
        ]
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


@pytest.mark.parametrize(
    ("scenario", "target", "command", "unexpected_event"),
    [
        (
            "set-reference-timeout",
            "CO3000",
            "Set Reference",
            "set_reference_complete",
        ),
        (
            "self-alignment-timeout",
            "FSV40",
            "Self Alignment",
            "self_alignment_complete",
        ),
    ],
)
def test_mock_lv_server_set_timeout_scenarios(
    qtbot,
    tmp_path,
    scenario,
    target,
    command,
    unexpected_event,
) -> None:
    server = MockLvServer(
        port=0,
        temp_dir=tmp_path,
        scenario=scenario,
        set_reference_delay_sec=0.01,
        self_alignment_delay_sec=0.01,
    )
    server.start()
    client = TcpClient()
    events = []
    client.event_received.connect(events.append)

    try:
        _connect(client, server, qtbot)

        if target == "FSV40":
            assert commands.set_reference_co3000(client)
            qtbot.waitUntil(
                lambda: any(
                    event.target == "CO3000"
                    and event.command == "set_reference_complete"
                    for event in events
                ),
                timeout=1000,
            )
            events.clear()

        if command == "Set Reference":
            assert commands.set_reference_co3000(client)
        else:
            assert commands.self_align_fsv40(client)
        qtbot.wait(100)

        assert not any(
            event.target == target and event.command == unexpected_event
            for event in events
        )
    finally:
        client.disconnect_from_host()
        server.stop()


@pytest.mark.parametrize(
    ("scenario", "target", "command", "source_command", "message"),
    [
        (
            "set-reference-error",
            "CO3000",
            "Set Reference",
            "Set Reference",
            "mock set reference error",
        ),
        (
            "self-alignment-error",
            "FSV40",
            "Self Alignment",
            "Self Alignment",
            "mock self alignment error",
        ),
    ],
)
def test_mock_lv_server_set_error_scenarios(
    qtbot,
    tmp_path,
    scenario,
    target,
    command,
    source_command,
    message,
) -> None:
    server = MockLvServer(
        port=0,
        temp_dir=tmp_path,
        scenario=scenario,
        set_reference_delay_sec=0.01,
        self_alignment_delay_sec=0.01,
    )
    server.start()
    client = TcpClient()
    events = []
    client.event_received.connect(events.append)

    try:
        _connect(client, server, qtbot)

        if target == "FSV40":
            assert commands.set_reference_co3000(client)
            qtbot.waitUntil(
                lambda: any(
                    event.target == "CO3000"
                    and event.command == "set_reference_complete"
                    for event in events
                ),
                timeout=1000,
            )
            events.clear()

        if command == "Set Reference":
            assert commands.set_reference_co3000(client)
        else:
            assert commands.self_align_fsv40(client)
        qtbot.waitUntil(
            lambda: any(
                event.target == target and event.command == "equipment_error"
                for event in events
            ),
            timeout=1000,
        )

        event = next(
            event
            for event in events
            if event.target == target and event.command == "equipment_error"
        )
        assert event.params == {
            "command": source_command,
            "message": message,
        }
    finally:
        client.disconnect_from_host()
        server.stop()


def test_mock_lv_server_stop_cancels_pending_set_event_thread(qtbot, tmp_path) -> None:
    server = MockLvServer(
        port=0,
        temp_dir=tmp_path,
        set_reference_delay_sec=15.0,
    )
    server.start()
    client = TcpClient()

    try:
        _connect(client, server, qtbot)
        assert commands.set_reference_co3000(client)
        qtbot.waitUntil(lambda: bool(server._set_event_threads), timeout=1000)

        started = time.monotonic()
        server.stop()
        elapsed = time.monotonic() - started

        assert elapsed < 1.0
        assert server._set_event_threads == []
    finally:
        client.disconnect_from_host()
        server.stop()


def test_mock_lv_server_restart_resets_set_stop_flag(qtbot, tmp_path) -> None:
    server = MockLvServer(
        port=0,
        temp_dir=tmp_path,
        set_reference_delay_sec=0.01,
    )
    server.start()
    server.stop()
    server.start()
    client = TcpClient()
    events = []
    client.event_received.connect(events.append)

    try:
        _connect(client, server, qtbot)

        assert commands.set_reference_co3000(client)
        qtbot.waitUntil(
            lambda: any(
                event.target == "CO3000"
                and event.command == "set_reference_complete"
                for event in events
            ),
            timeout=1000,
        )
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


def test_mock_lv_server_handles_inband_command(qtbot, tmp_path) -> None:
    server = MockLvServer(port=0, temp_dir=tmp_path)
    server.start()
    client = TcpClient()

    try:
        _connect(client, server, qtbot)

        assert commands.measure_inband(client, limit=-30.0) == -42.1
        assert (tmp_path / "inband.png").is_file()

        request = server.received_requests[-1]
        assert (request.target, request.command, request.params) == (
            "FSV40",
            "Mark Inband",
            {"Limit": -30.0},
        )
    finally:
        client.disconnect_from_host()
        server.stop()


def test_mock_lv_server_handles_tdf_commands(qtbot, tmp_path) -> None:
    server = MockLvServer(port=0, temp_dir=tmp_path)
    server.start()
    client = TcpClient()

    try:
        _connect(client, server, qtbot)

        assert commands.get_tdf_list(client) == list(MOCK_TDF_FILE_LIST)
        assert commands.tdf_all_off(client)
        assert commands.set_tdf(client, tdf_file_name="NR_Radiated.tdf")

        requests = server.received_requests[-3:]
        assert [(request.target, request.command, request.params) for request in requests] == [
            ("FSV40", "Get TDF List", {}),
            ("FSV40", "TDF All Off", {}),
            ("FSV40", "Set TDF", {"TDF File Name": "NR_Radiated.tdf"}),
        ]
    finally:
        client.disconnect_from_host()
        server.stop()


def test_mock_lv_server_handles_preset(qtbot, tmp_path) -> None:
    server = MockLvServer(port=0, temp_dir=tmp_path)
    server.start()
    client = TcpClient()

    try:
        _connect(client, server, qtbot)

        assert commands.preset_sa(client)

        request = server.received_requests[-1]
        assert (request.target, request.command, request.params) == (
            "FSV40",
            "Preset",
            {},
        )
        assert server.state.last_preset_params == {}
        assert server.state.preset_count == 1
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
