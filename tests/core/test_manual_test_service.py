from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QObject, QThread, Signal

from app.core.manual_test_service import (
    FSV40_NOT_CONNECTED_MESSAGE,
    MANUAL_OPERATION_IN_PROGRESS_MESSAGE,
    ManualTestCapabilities,
    ManualTestService,
    manual_test_capabilities,
)
from app.models.manual_test import ManualSaSettings
from app.net import commands as net_commands
from app.net.mock_lv_server import MockLvServer
from app.net.tcp_client import TcpClient


@pytest.mark.parametrize(
    ("equipment_state", "expected"),
    [
        ({}, ManualTestCapabilities()),
        (
            {"FSV40": True},
            ManualTestCapabilities(fsv40=True, marker=True, capture=True),
        ),
        (
            {"CO3000": True},
            ManualTestCapabilities(turntable=True, mast_3m=True),
        ),
        (
            {"3D Controller": True},
            ManualTestCapabilities(mast_1m=True),
        ),
        (
            {"FSV40": True, "CO3000": True},
            ManualTestCapabilities(
                fsv40=True,
                marker=True,
                capture=True,
                turntable=True,
                mast_3m=True,
                semi_auto=True,
            ),
        ),
    ],
)
def test_manual_capabilities_use_only_equipment_connection_state(
    equipment_state: dict[str, bool],
    expected: ManualTestCapabilities,
) -> None:
    assert manual_test_capabilities(equipment_state) == expected


def test_manual_capabilities_ignore_non_equipment_state() -> None:
    capabilities = manual_test_capabilities(
        {
            "FSV40": True,
            "TestCase": False,
            "Call": False,
            "RF Filter": False,
            "Queue": False,
        }
    )

    assert capabilities == ManualTestCapabilities(
        fsv40=True,
        marker=True,
        capture=True,
    )


class _EventClient(QObject):
    event_received = Signal(object)

    def pop_events(self, _predicate) -> list[object]:
        return []


class _ManualCommands:
    def __init__(self, client: _EventClient, temp_dir: Path) -> None:
        self.client = client
        self.temp_dir = temp_dir
        self.calls: list[tuple[object, ...]] = []
        self.emit_turntable_complete = True

    def setup_sa_manual(self, _client, **params) -> bool:
        self.calls.append(("setup_sa_manual", params))
        return True

    def preset_sa(self, _client) -> bool:
        self.calls.append(("preset_sa",))
        return True

    def clear_trace(self, _client) -> bool:
        self.calls.append(("clear_trace",))
        return True

    def marker_peak(self, _client, *, marker_index: int, excursion: float) -> bool:
        self.calls.append(("marker_peak", marker_index, excursion))
        return True

    def marker_next(self, _client, *, marker_index: int, excursion: float) -> bool:
        self.calls.append(("marker_next", marker_index, excursion))
        return True

    def marker_off(self, _client, *, marker_index: int, excursion: float) -> bool:
        self.calls.append(("marker_off", marker_index, excursion))
        return True

    def marker_all_off(self, _client) -> bool:
        self.calls.append(("marker_all_off",))
        return True

    def marker_auto_max(self, _client, *, marker_index: int, excursion: float) -> bool:
        self.calls.append(("marker_auto_max", marker_index, excursion))
        return True

    def marker_set_center(self, _client, *, marker_index: int, excursion: float) -> bool:
        self.calls.append(("marker_set_center", marker_index, excursion))
        return True

    def get_screenshot(self, _client) -> bool:
        self.calls.append(("get_screenshot",))
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        (self.temp_dir / "screenshot.png").write_bytes(
            b"\x89PNG\r\n\x1a\nfixture"
        )
        return True

    def get_turntable_angle(self, _client) -> float:
        self.calls.append(("get_turntable_angle",))
        return 90.0

    def rotate_turntable(self, _client, *, angle: float, turntable_speed: int) -> None:
        self.calls.append(("rotate_turntable", angle, turntable_speed))
        if self.emit_turntable_complete:
            self.client.event_received.emit(
                SimpleNamespace(
                    target="CO3000",
                    command="turntable_complete",
                    params={},
                )
            )

    def stop_turntable(self, _client) -> None:
        self.calls.append(("stop_turntable",))


def _manual_settings(*, saturation_time_sec: float = 0.0) -> ManualSaSettings:
    return ManualSaSettings(
        start_frequency_mhz=1000.0,
        stop_frequency_mhz=12750.0,
        rbw_mhz=1.0,
        vbw_mhz=3.0,
        sweep_point=30001,
        sweep_time_sec=0.1,
        saturation_time_sec=saturation_time_sec,
        atten_level_db=0.0,
        detector_mode="RMS",
        limit_dbm=-30.0,
    )


def _connect_fsv40(service: ManualTestService) -> None:
    service.set_equipment_state({"FSV40": True})


def test_manual_service_uses_timer_lifecycle_without_worker_thread(
    qtbot,
    tmp_path: Path,
) -> None:
    client = _EventClient()
    commands = _ManualCommands(client, tmp_path)
    service = ManualTestService(client=client, commands=commands, temp_dir=tmp_path)
    _connect_fsv40(service)
    events: list[tuple[object, ...]] = []
    service.running_changed.connect(lambda value: events.append(("running", value)))
    service.operation_started.connect(lambda name: events.append(("started", name)))
    service.step_changed.connect(lambda step: events.append(("step", step)))
    service.operation_finished.connect(lambda name: events.append(("finished", name)))

    assert service.clear_trace()
    assert service.is_running
    assert service.current_operation == "Trace Clear"
    assert commands.calls == []
    assert service.findChildren(QThread) == []

    qtbot.waitUntil(lambda: not service.is_running, timeout=1000)

    assert events == [
        ("running", True),
        ("started", "Trace Clear"),
        ("step", "Trace Clear 실행 중"),
        ("finished", "Trace Clear"),
        ("running", False),
    ]


def test_manual_service_recovers_after_command_error(qtbot, tmp_path: Path) -> None:
    client = _EventClient()
    commands = _ManualCommands(client, tmp_path)
    service = ManualTestService(client=client, commands=commands, temp_dir=tmp_path)
    _connect_fsv40(service)
    failures: list[tuple[str, str]] = []
    service.operation_failed.connect(
        lambda operation, message: failures.append((operation, message)),
    )

    commands.clear_trace = lambda _client: (_ for _ in ()).throw(RuntimeError("boom"))
    assert service.clear_trace()
    qtbot.waitUntil(lambda: not service.is_running, timeout=1000)
    assert failures == [("Trace Clear", "boom")]

    commands.clear_trace = lambda _client: True
    assert service.clear_trace()
    qtbot.waitUntil(lambda: not service.is_running, timeout=1000)


def test_manual_stop_before_first_timer_step_sends_no_command(
    qtbot,
    tmp_path: Path,
) -> None:
    client = _EventClient()
    commands = _ManualCommands(client, tmp_path)
    service = ManualTestService(client=client, commands=commands, temp_dir=tmp_path)
    _connect_fsv40(service)
    cancelled: list[str] = []
    service.operation_cancelled.connect(cancelled.append)

    assert service.clear_trace()
    service.request_stop()
    qtbot.wait(10)

    assert commands.calls == []
    assert cancelled == ["Trace Clear"]
    assert not service.is_running


def test_manual_service_rejects_competing_operation_while_waiting_for_event(
    qtbot,
    tmp_path: Path,
) -> None:
    client = _EventClient()
    commands = _ManualCommands(client, tmp_path)
    commands.emit_turntable_complete = False
    service = ManualTestService(client=client, commands=commands, temp_dir=tmp_path)
    _connect_fsv40(service)
    failures: list[tuple[str, str]] = []
    service.operation_failed.connect(
        lambda operation, message: failures.append((operation, message)),
    )

    assert service.move_turntable(angle=360.0, speed=6)
    qtbot.waitUntil(lambda: ("rotate_turntable", 360.0, 6) in commands.calls)
    assert not service.clear_trace()
    assert failures[-1] == ("Trace Clear", MANUAL_OPERATION_IN_PROGRESS_MESSAGE)

    service.request_stop()
    assert not service.is_running


def test_manual_service_guard_rejects_before_command(tmp_path: Path) -> None:
    client = _EventClient()
    commands = _ManualCommands(client, tmp_path)
    service = ManualTestService(
        client=client,
        commands=commands,
        temp_dir=tmp_path,
        operation_guard=lambda: "다른 작업 진행 중",
    )
    _connect_fsv40(service)
    failures: list[tuple[str, str]] = []
    service.operation_failed.connect(
        lambda operation, message: failures.append((operation, message)),
    )

    assert not service.clear_trace()
    assert commands.calls == []
    assert failures == [("Trace Clear", "다른 작업 진행 중")]
    assert not service.is_running


def test_manual_service_shutdown_cancels_timer_and_rejects_new_work(
    qtbot,
    tmp_path: Path,
) -> None:
    client = _EventClient()
    commands = _ManualCommands(client, tmp_path)
    service = ManualTestService(client=client, commands=commands, temp_dir=tmp_path)
    _connect_fsv40(service)
    failures: list[tuple[str, str]] = []
    service.operation_failed.connect(
        lambda operation, message: failures.append((operation, message)),
    )

    assert service.clear_trace()
    service.shutdown()
    qtbot.wait(10)

    assert commands.calls == []
    assert not service.is_running
    assert not service.clear_trace()
    assert failures == [
        ("Trace Clear", "Manual Test 서비스를 종료하는 중입니다."),
    ]


def test_manual_service_repeats_fifty_real_client_commands_without_threads(
    qtbot,
    tmp_path: Path,
) -> None:
    server = MockLvServer(port=0, temp_dir=tmp_path)
    server.start()
    client = TcpClient()
    service = ManualTestService(
        client=client,
        commands=net_commands,
        temp_dir=tmp_path,
    )
    _connect_fsv40(service)
    finished: list[str] = []
    failures: list[tuple[str, str]] = []
    service.operation_finished.connect(finished.append)
    service.operation_failed.connect(
        lambda operation, message: failures.append((operation, message)),
    )

    try:
        with qtbot.waitSignal(client.connected_changed, timeout=1000):
            client.connect_to(server.host, server.port, timeout=1.0)
        for _index in range(50):
            assert service.clear_trace()
            qtbot.waitUntil(lambda: not service.is_running, timeout=1000)
            assert service.findChildren(QThread) == []

        assert finished == ["Trace Clear"] * 50
        assert failures == []
    finally:
        service.shutdown()
        client.disconnect_from_host()
        server.stop()


def test_manual_service_applies_exact_sa_wire_fields_without_saturation(
    qtbot,
    tmp_path: Path,
) -> None:
    client = _EventClient()
    commands = _ManualCommands(client, tmp_path)
    service = ManualTestService(client=client, commands=commands, temp_dir=tmp_path)
    _connect_fsv40(service)

    assert service.apply_sa_settings(_manual_settings(saturation_time_sec=2.5))
    qtbot.waitUntil(lambda: not service.is_running, timeout=1000)

    assert commands.calls == [
        (
            "setup_sa_manual",
            {
                "start_frequency_mhz": 1000.0,
                "stop_frequency_mhz": 12750.0,
                "rbw_mhz": 1.0,
                "vbw_mhz": 3.0,
                "sweep_point": 30001,
                "sweep_time_sec": 0.1,
                "atten_level_db": 0.0,
                "detector_mode": "RMS",
                "limit_dbm": -30.0,
            },
        )
    ]


@pytest.mark.parametrize(
    ("operation_name", "invoke"),
    [
        ("FSV40 Set", lambda service: service.apply_sa_settings(_manual_settings())),
        ("FSV40 Preset", lambda service: service.preset_sa()),
        ("Trace Clear", lambda service: service.clear_trace()),
    ],
)
def test_manual_fsv40_actions_reject_disconnected_before_command(
    tmp_path: Path,
    operation_name,
    invoke,
) -> None:
    client = _EventClient()
    commands = _ManualCommands(client, tmp_path)
    service = ManualTestService(client=client, commands=commands, temp_dir=tmp_path)
    failures: list[tuple[str, str]] = []
    service.operation_failed.connect(
        lambda operation, message: failures.append((operation, message)),
    )

    assert not invoke(service)

    assert commands.calls == []
    assert failures == [(operation_name, FSV40_NOT_CONNECTED_MESSAGE)]
    assert not service.is_running


def test_manual_sa_failure_releases_busy_for_next_command(qtbot, tmp_path: Path) -> None:
    client = _EventClient()
    commands = _ManualCommands(client, tmp_path)
    commands.setup_sa_manual = lambda _client, **_params: False
    service = ManualTestService(client=client, commands=commands, temp_dir=tmp_path)
    _connect_fsv40(service)
    failures: list[tuple[str, str]] = []
    service.operation_failed.connect(
        lambda operation, message: failures.append((operation, message)),
    )

    assert service.apply_sa_settings(_manual_settings())
    qtbot.waitUntil(lambda: not service.is_running, timeout=1000)

    assert failures == [
        ("FSV40 Set", "Load SA Manual Setting returned false"),
    ]
    assert service.preset_sa()
    qtbot.waitUntil(lambda: not service.is_running, timeout=1000)
    assert commands.calls == [("preset_sa",)]


def test_manual_marker_actions_preserve_payload_and_fixed_fillers(
    qtbot,
    tmp_path: Path,
) -> None:
    client = _EventClient()
    commands = _ManualCommands(client, tmp_path)
    service = ManualTestService(client=client, commands=commands, temp_dir=tmp_path)
    _connect_fsv40(service)

    actions = (
        lambda: service.marker_peak(1, 0.0),
        lambda: service.marker_next(2, 7.5),
        lambda: service.marker_off(3, 0.0),
        service.marker_all_off,
        lambda: service.marker_auto_max(4),
        lambda: service.marker_set_center(5),
    )
    for action in actions:
        assert action()
        qtbot.waitUntil(lambda: not service.is_running, timeout=1000)

    assert commands.calls == [
        ("marker_peak", 1, 0.0),
        ("marker_next", 2, 7.5),
        ("marker_off", 3, 0.0),
        ("marker_all_off",),
        ("marker_auto_max", 4, 0.0),
        ("marker_set_center", 5, 0.0),
    ]


@pytest.mark.parametrize(
    ("operation_name", "invoke"),
    [
        ("Marker Peak", lambda service: service.marker_peak(1, 0.0)),
        ("Marker Next", lambda service: service.marker_next(1, 6.0)),
        ("Marker OFF", lambda service: service.marker_off(1, 0.0)),
        ("Marker ALL OFF", lambda service: service.marker_all_off()),
        ("Marker Auto Max", lambda service: service.marker_auto_max(1)),
        ("Marker to Center", lambda service: service.marker_set_center(1)),
    ],
)
def test_manual_marker_actions_reject_disconnected_before_command(
    tmp_path: Path,
    operation_name,
    invoke,
) -> None:
    client = _EventClient()
    commands = _ManualCommands(client, tmp_path)
    service = ManualTestService(client=client, commands=commands, temp_dir=tmp_path)
    failures: list[tuple[str, str]] = []
    service.operation_failed.connect(
        lambda operation, message: failures.append((operation, message)),
    )

    assert not invoke(service)

    assert commands.calls == []
    assert failures == [(operation_name, FSV40_NOT_CONNECTED_MESSAGE)]


def test_manual_marker_timeout_releases_busy(qtbot, tmp_path: Path) -> None:
    client = _EventClient()
    commands = _ManualCommands(client, tmp_path)
    service = ManualTestService(client=client, commands=commands, temp_dir=tmp_path)
    _connect_fsv40(service)
    failures: list[tuple[str, str]] = []
    service.operation_failed.connect(
        lambda operation, message: failures.append((operation, message)),
    )

    commands.marker_next = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        TimeoutError("marker response timeout")
    )
    assert service.marker_next(1, 6.0)
    qtbot.waitUntil(lambda: not service.is_running, timeout=1000)

    assert failures == [("Marker Next", "marker response timeout")]
    commands.marker_next = lambda *_args, **_kwargs: True
    assert service.marker_next(1, 6.0)
    qtbot.waitUntil(lambda: not service.is_running, timeout=1000)


def test_manual_marker_rejects_second_click_while_pending(qtbot, tmp_path: Path) -> None:
    client = _EventClient()
    commands = _ManualCommands(client, tmp_path)
    service = ManualTestService(client=client, commands=commands, temp_dir=tmp_path)
    _connect_fsv40(service)
    failures: list[tuple[str, str]] = []
    service.operation_failed.connect(
        lambda operation, message: failures.append((operation, message)),
    )

    assert service.marker_peak(1, 0.0)
    assert not service.marker_off(1, 0.0)
    qtbot.waitUntil(lambda: not service.is_running, timeout=1000)

    assert commands.calls == [("marker_peak", 1, 0.0)]
    assert failures == [("Marker OFF", MANUAL_OPERATION_IN_PROGRESS_MESSAGE)]


def test_manual_service_capture_many_preserves_order(
    qtbot,
    tmp_path: Path,
) -> None:
    client = _EventClient()
    temp_dir = tmp_path / "temp"
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    commands = _ManualCommands(client, temp_dir)
    service = ManualTestService(client=client, commands=commands, temp_dir=temp_dir)
    saved: list[str] = []
    service.screenshot_saved.connect(saved.append)

    assert service.capture_many(
        directory=output_dir,
        base_name="capture",
        interval_sec=0,
        shot_count=3,
    )
    qtbot.waitUntil(lambda: not service.is_running, timeout=1000)

    assert [Path(path).name for path in saved] == [
        "capture_001.png",
        "capture_002.png",
        "capture_003.png",
    ]
    assert [call[0] for call in commands.calls] == [
        "get_screenshot",
        "clear_trace",
        "get_screenshot",
        "clear_trace",
        "get_screenshot",
    ]


def test_manual_service_capture_preflight_sends_no_command_on_collision(
    qtbot,
    tmp_path: Path,
) -> None:
    client = _EventClient()
    temp_dir = tmp_path / "temp"
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "capture_002.png").write_bytes(b"existing")
    commands = _ManualCommands(client, temp_dir)
    service = ManualTestService(client=client, commands=commands, temp_dir=temp_dir)
    failures: list[tuple[str, str]] = []
    service.operation_failed.connect(
        lambda operation, message: failures.append((operation, message)),
    )

    assert service.capture_many(
        directory=output_dir,
        base_name="capture",
        interval_sec=0,
        shot_count=3,
    )
    qtbot.waitUntil(lambda: not service.is_running, timeout=1000)

    assert commands.calls == []
    assert failures and "capture_002.png" in failures[0][1]


def test_manual_service_semi_auto_uses_explicit_saturation_and_rotation_order(
    qtbot,
    tmp_path: Path,
) -> None:
    client = _EventClient()
    commands = _ManualCommands(client, tmp_path)
    service = ManualTestService(client=client, commands=commands, temp_dir=tmp_path)

    assert service.run_semi_auto(speed=4, saturation_time_sec=0)
    qtbot.waitUntil(lambda: not service.is_running, timeout=1000)

    assert commands.calls == [
        ("get_turntable_angle",),
        ("rotate_turntable", 0.0, 6),
        ("clear_trace",),
        ("rotate_turntable", 360.0, 4),
    ]


def test_manual_service_stop_stops_active_turntable(qtbot, tmp_path: Path) -> None:
    client = _EventClient()
    commands = _ManualCommands(client, tmp_path)
    commands.emit_turntable_complete = False
    service = ManualTestService(
        client=client,
        commands=commands,
        temp_dir=tmp_path,
        turntable_timeout_sec=5.0,
    )
    cancelled: list[str] = []
    failures: list[tuple[str, str]] = []
    service.operation_cancelled.connect(cancelled.append)
    service.operation_failed.connect(
        lambda operation, message: failures.append((operation, message)),
    )

    assert service.move_turntable(angle=360.0, speed=6)
    qtbot.waitUntil(
        lambda: any(call[0] == "rotate_turntable" for call in commands.calls),
        timeout=1000,
    )
    service.request_stop()
    qtbot.waitUntil(lambda: not service.is_running, timeout=1000)

    assert ("stop_turntable",) in commands.calls
    assert cancelled == ["Turntable 360°"]
    assert failures == []


def test_manual_service_reports_stop_command_failure(qtbot, tmp_path: Path) -> None:
    client = _EventClient()
    commands = _ManualCommands(client, tmp_path)
    commands.emit_turntable_complete = False
    service = ManualTestService(
        client=client,
        commands=commands,
        temp_dir=tmp_path,
        turntable_timeout_sec=5.0,
    )
    cancelled: list[str] = []
    failures: list[tuple[str, str]] = []
    service.operation_cancelled.connect(cancelled.append)
    service.operation_failed.connect(
        lambda operation, message: failures.append((operation, message)),
    )

    def fail_stop(_client) -> None:
        commands.calls.append(("stop_turntable",))
        raise RuntimeError("transport disconnected")

    commands.stop_turntable = fail_stop

    assert service.move_turntable(angle=360.0, speed=6)
    qtbot.waitUntil(
        lambda: any(call[0] == "rotate_turntable" for call in commands.calls),
        timeout=1000,
    )
    service.request_stop()
    qtbot.waitUntil(lambda: not service.is_running, timeout=1000)

    assert cancelled == []
    assert failures == [
        ("Turntable 360°", "Turntable 정지 실패: transport disconnected"),
    ]


def test_manual_service_timeout_stops_turntable_and_reports_failure(
    qtbot,
    tmp_path: Path,
) -> None:
    client = _EventClient()
    commands = _ManualCommands(client, tmp_path)
    commands.emit_turntable_complete = False
    service = ManualTestService(
        client=client,
        commands=commands,
        temp_dir=tmp_path,
        turntable_timeout_sec=0.01,
    )
    failures: list[tuple[str, str]] = []
    service.operation_failed.connect(
        lambda operation, message: failures.append((operation, message)),
    )

    assert service.move_turntable(angle=360.0, speed=6)
    qtbot.waitUntil(lambda: not service.is_running, timeout=1000)

    assert ("stop_turntable",) in commands.calls
    assert failures == [("Turntable 360°", "Turntable 회전 타임아웃")]


def test_manual_service_stop_during_angle_query_skips_rotation(
    qtbot,
    tmp_path: Path,
) -> None:
    client = _EventClient()
    commands = _ManualCommands(client, tmp_path)
    service = ManualTestService(client=client, commands=commands, temp_dir=tmp_path)

    def get_turntable_angle(_client) -> float:
        commands.calls.append(("get_turntable_angle",))
        service.request_stop()
        return 90.0

    commands.get_turntable_angle = get_turntable_angle

    assert service.run_semi_auto(speed=6, saturation_time_sec=0)
    qtbot.waitUntil(lambda: not service.is_running, timeout=1000)

    assert commands.calls == [("get_turntable_angle",)]
