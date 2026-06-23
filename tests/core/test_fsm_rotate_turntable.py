from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

import pytest

from app.core.fsm.base import StateResult
from app.core.fsm.context import SessionContext
from app.core.fsm.states.measurement import common as common_module
from app.core.fsm.states.measurement.common import (
    InitialTurntableZeroState,
    RotateTurntableState,
)
from app.models.enums import (
    AntennaPol,
    DUTAxis,
    Modulation,
    NRBand,
    RBAllocation,
    TestChannel as ChannelEnum,
    TestType as MeasurementTestType,
)
from app.models.test_case import TestCase
from app.models.test_run_settings import TestRunSettings


class _SignalRecorder:
    def __init__(self) -> None:
        self.values: list[Any] = []

    def emit(self, value: Any = None) -> None:
        self.values.append(value)


class _Events:
    def __init__(self) -> None:
        self.error = _SignalRecorder()
        self.progress = _SignalRecorder()
        self.turntable_info_changed = _SignalRecorder()


class _FakeSignal:
    def __init__(self) -> None:
        self._slots: list[Any] = []

    def connect(self, slot: Any, *args: Any, **kwargs: Any) -> None:
        self._slots.append(slot)

    def disconnect(self, slot: Any) -> None:
        self._slots.remove(slot)

    def emit(self, payload: Any) -> None:
        for slot in list(self._slots):
            slot(payload)


class _FakeClient:
    def __init__(self) -> None:
        self.event_received = _FakeSignal()
        self._event_buffer: list[_FakeEvent] = []

    def buffer_event(self, event: "_FakeEvent") -> None:
        self._event_buffer.append(event)

    def pop_events(self, predicate: Any) -> list["_FakeEvent"]:
        matched: list[_FakeEvent] = []
        remaining: list[_FakeEvent] = []
        for event in self._event_buffer:
            if predicate(event):
                matched.append(event)
            else:
                remaining.append(event)
        self._event_buffer = remaining
        return matched


class _FakeEvent:
    def __init__(
        self,
        command: str,
        params: dict[str, Any] | None = None,
        target: str = common_module._TARGET_TURNTABLE,
    ) -> None:
        self.target = target
        self.command = command
        self.params = params or {}


class _Commands:
    def __init__(
        self,
        *,
        raise_on_rotate: Exception | None = None,
        raise_on_angle_readback: Exception | None = None,
        buffer_on_rotate: _FakeEvent | list[_FakeEvent] | None = None,
        readback_angle: float | None = None,
    ) -> None:
        self.raise_on_rotate = raise_on_rotate
        self.raise_on_angle_readback = raise_on_angle_readback
        self.buffer_on_rotate = buffer_on_rotate
        self.readback_angle = readback_angle
        self.angle_calls: list[Any] = []
        self.rotate_calls: list[tuple[Any, dict[str, Any]]] = []
        self.stop_calls: list[Any] = []

    def get_turntable_angle(self, client: Any) -> float:
        self.angle_calls.append(client)
        if self.raise_on_angle_readback is not None:
            raise self.raise_on_angle_readback
        if self.readback_angle is None:
            raise AssertionError("readback_angle must be set")
        return self.readback_angle

    def rotate_turntable(self, client: Any, **kwargs: Any) -> None:
        self.rotate_calls.append((client, kwargs))
        if self.raise_on_rotate is not None:
            raise self.raise_on_rotate
        if self.buffer_on_rotate is not None:
            events = (
                self.buffer_on_rotate
                if isinstance(self.buffer_on_rotate, list)
                else [self.buffer_on_rotate]
            )
            for event in events:
                client.buffer_event(event)

    def stop_turntable(self, client: Any) -> None:
        self.stop_calls.append(client)


def _make_case(band: NRBand, test_type: MeasurementTestType, bandwidth: float) -> TestCase:
    return TestCase(
        band=band,
        bandwidth=bandwidth,
        test_type=test_type,
        modulation=Modulation.QPSK,
        rb_allocation=RBAllocation.INNER_FULL,
        test_channel=ChannelEnum.MID,
        antenna_pol=AntennaPol.H,
        dut_axis=DUTAxis.X,
        dut_ant_position="Upper",
    )


def _make_ctx(
    case: TestCase,
    *,
    commands: _Commands,
    client: _FakeClient | None = None,
    current_angle: float = 0.0,
    settings: TestRunSettings | None = None,
) -> tuple[SessionContext, _Events]:
    if commands.readback_angle is None:
        commands.readback_angle = current_angle
    events = _Events()
    ctx = SessionContext(
        queue=[case],
        commands=commands,
        events=events,  # type: ignore[arg-type]
        client=client if client is not None else _FakeClient(),
        current_angle=current_angle,
        settings=settings,
    )
    ctx.equipment_state = {"CO3000": True}
    return ctx, events


def _make_settings(
    tmp_path: Path,
    *,
    saturation_time_sec: float,
    custom_turntable_speed: int | None = None,
) -> TestRunSettings:
    template_path = tmp_path / "template.xlsx"
    screenshot_root_dir = tmp_path / "screenshots"
    template_path.write_bytes(b"template")
    screenshot_root_dir.mkdir(exist_ok=True)
    return TestRunSettings(
        eut_name="SM-000",
        template_path=template_path,
        screenshot_root_dir=screenshot_root_dir,
        saturation_time_sec=saturation_time_sec,
        connection_waiting_time_sec=5,
        atten_level_db=0,
        next_peak_search_level_db=0,
        active_tdf_file_name="NR_Radiated.tdf",
        custom_turntable_speed=custom_turntable_speed,
    )


@pytest.fixture(autouse=True)
def _shrink_timing(monkeypatch: pytest.MonkeyPatch) -> None:
    """테스트가 실시간을 기다리지 않도록 모듈 상수를 축소."""
    monkeypatch.setattr(common_module, "_POLL_INTERVAL_SEC", 0.01)
    monkeypatch.setattr(common_module, "_SETTLING_SEC", 0.05)
    monkeypatch.setattr(common_module, "_ROTATION_TIMEOUT_SEC", 1.0)


def _drive_state(state: RotateTurntableState, ctx: SessionContext) -> StateResult:
    """enter → run → exit 를 직접 호출 (engine 미존재)."""
    state.enter(ctx)
    try:
        return state.run(ctx)
    finally:
        state.exit(ctx)


def _emit_after(client: _FakeClient, delay: float, event: _FakeEvent) -> threading.Thread:
    def worker() -> None:
        time.sleep(delay)
        client.event_received.emit(event)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    return thread


@pytest.mark.parametrize(
    ("readback_angle", "expected_target"),
    [
        (0.0, 0.0),
        (179.9, 0.0),
        (180.0, 0.0),
        (180.1, 360.0),
        (360.0, 360.0),
    ],
)
def test_initial_turntable_zero_uses_nearest_reference_angle_and_speed_6(
    readback_angle: float,
    expected_target: float,
) -> None:
    commands = _Commands(readback_angle=readback_angle)
    client = _FakeClient()
    case = _make_case(NRBand.N78, MeasurementTestType.HARMONIC, bandwidth=100.0)
    ctx, events = _make_ctx(
        case,
        commands=commands,
        client=client,
        current_angle=0.0,
    )
    state = InitialTurntableZeroState()

    thread = _emit_after(
        client, 0.05, _FakeEvent(common_module._COMMAND_TURNTABLE_COMPLETE)
    )
    result = _drive_state(state, ctx)
    thread.join(timeout=1.0)

    assert result is StateResult.OK
    assert ctx.current_angle == expected_target
    assert commands.angle_calls == [client]
    assert commands.rotate_calls == [
        (client, {"angle": expected_target, "turntable_speed": 6}),
    ]
    assert commands.stop_calls == []
    assert events.progress.values == [0, 100]
    assert events.turntable_info_changed.values == [
        {"current_angle": readback_angle},
        {"target_angle": expected_target, "setting_speed": 6},
        {"current_angle": expected_target},
    ]
    assert state.next_state(ctx, result) == "AntPolChange"


def test_initial_turntable_zero_consumes_buffered_progress_and_complete() -> None:
    progress = _FakeEvent(
        common_module._COMMAND_TURNTABLE_PROGRESS,
        {"Current Angle": 30.0},
    )
    complete = _FakeEvent(common_module._COMMAND_TURNTABLE_COMPLETE)
    commands = _Commands(buffer_on_rotate=[progress, complete])
    client = _FakeClient()
    case = _make_case(NRBand.N78, MeasurementTestType.HARMONIC, bandwidth=100.0)
    ctx, events = _make_ctx(
        case,
        commands=commands,
        client=client,
        current_angle=180.0,
    )
    state = InitialTurntableZeroState()

    result = _drive_state(state, ctx)

    assert result is StateResult.OK
    assert ctx.current_angle == 0.0
    assert commands.angle_calls == [client]
    assert events.turntable_info_changed.values == [
        {"current_angle": 180.0},
        {"target_angle": 0.0, "setting_speed": 6},
        {"current_angle": 30.0},
        {"current_angle": 0.0},
    ]


def test_initial_turntable_zero_skips_when_co3000_is_not_connected() -> None:
    commands = _Commands()
    client = _FakeClient()
    case = _make_case(NRBand.N78, MeasurementTestType.HARMONIC, bandwidth=100.0)
    ctx, events = _make_ctx(
        case,
        commands=commands,
        client=client,
        current_angle=180.0,
    )
    ctx.equipment_state = {"CO3000": False}
    state = InitialTurntableZeroState()

    result = _drive_state(state, ctx)

    assert result is StateResult.OK
    assert state.next_state(ctx, result) == "AntPolChange"
    assert commands.angle_calls == []
    assert commands.rotate_calls == []
    assert ctx.current_angle == 180.0
    assert events.turntable_info_changed.values == []
    assert events.error.values


def test_initial_turntable_zero_readback_error_returns_fail() -> None:
    commands = _Commands(raise_on_angle_readback=RuntimeError("angle unavailable"))
    client = _FakeClient()
    case = _make_case(NRBand.N78, MeasurementTestType.HARMONIC, bandwidth=100.0)
    ctx, events = _make_ctx(
        case,
        commands=commands,
        client=client,
        current_angle=180.0,
    )
    state = InitialTurntableZeroState()

    result = _drive_state(state, ctx)

    assert result is StateResult.FAIL
    assert state.next_state(ctx, result) is None
    assert commands.angle_calls == [client]
    assert commands.rotate_calls == []
    assert commands.stop_calls == []
    assert ctx.current_angle == 180.0
    assert events.turntable_info_changed.values == []
    assert events.error.values == [
        "Turntable 현재 각도 조회 실패: angle unavailable"
    ]


def test_initial_turntable_zero_stop_requests_stop_turntable_and_fail() -> None:
    commands = _Commands()
    client = _FakeClient()
    case = _make_case(NRBand.N78, MeasurementTestType.HARMONIC, bandwidth=100.0)
    ctx, _ = _make_ctx(case, commands=commands, client=client, current_angle=180.0)
    state = InitialTurntableZeroState()

    def request_stop() -> None:
        time.sleep(0.05)
        ctx.stopped = True

    threading.Thread(target=request_stop, daemon=True).start()
    result = _drive_state(state, ctx)

    assert result is StateResult.FAIL
    assert commands.stop_calls == [client]
    assert ctx.current_angle == 180.0
    assert state.next_state(ctx, result) is None


def test_initial_turntable_zero_current_case_stop_requests_stop_and_fail() -> None:
    commands = _Commands()
    client = _FakeClient()
    case = _make_case(NRBand.N78, MeasurementTestType.HARMONIC, bandwidth=100.0)
    ctx, _ = _make_ctx(case, commands=commands, client=client, current_angle=180.0)
    state = InitialTurntableZeroState()

    def request_stop() -> None:
        time.sleep(0.05)
        ctx.current_case_stop_requested = True

    threading.Thread(target=request_stop, daemon=True).start()
    result = _drive_state(state, ctx)

    assert result is StateResult.FAIL
    assert commands.stop_calls == [client]
    assert ctx.current_angle == 180.0
    assert state.next_state(ctx, result) is None


def test_initial_turntable_zero_error_event_returns_fail() -> None:
    commands = _Commands()
    client = _FakeClient()
    case = _make_case(NRBand.N78, MeasurementTestType.HARMONIC, bandwidth=100.0)
    ctx, events = _make_ctx(
        case,
        commands=commands,
        client=client,
        current_angle=180.0,
    )
    state = InitialTurntableZeroState()

    thread = _emit_after(
        client,
        0.05,
        _FakeEvent(common_module._COMMAND_EQUIPMENT_ERROR, {"message": "stalled"}),
    )
    result = _drive_state(state, ctx)
    thread.join(timeout=1.0)

    assert result is StateResult.FAIL
    assert state.next_state(ctx, result) is None
    assert ctx.current_angle == 180.0
    assert commands.stop_calls == []
    assert events.error.values == ["Turntable 초기 0도 정렬 실패: stalled"]


def test_rotate_zero_to_360_with_band_group_speed() -> None:
    commands = _Commands()
    client = _FakeClient()
    case = _make_case(NRBand.N5, MeasurementTestType.HARMONIC, bandwidth=20.0)
    ctx, events = _make_ctx(case, commands=commands, client=client, current_angle=0.0)
    state = RotateTurntableState()

    thread = _emit_after(
        client, 0.05, _FakeEvent(common_module._COMMAND_TURNTABLE_COMPLETE)
    )
    result = _drive_state(state, ctx)
    thread.join(timeout=1.0)

    assert result is StateResult.OK
    assert ctx.current_angle == 360.0
    assert commands.rotate_calls == [
        (client, {"angle": 360.0, "turntable_speed": 5}),
    ]
    assert commands.stop_calls == []
    assert events.progress.values == [0, 100]
    assert events.turntable_info_changed.values == [
        {"target_angle": 360.0, "setting_speed": 5},
        {"current_angle": 360.0},
    ]
    assert state.next_state(ctx, result) == "MeasureHarmonics"


def test_rotate_consumes_buffered_complete_event_from_command() -> None:
    complete = _FakeEvent(common_module._COMMAND_TURNTABLE_COMPLETE)
    commands = _Commands(buffer_on_rotate=complete)
    client = _FakeClient()
    case = _make_case(NRBand.N5, MeasurementTestType.HARMONIC, bandwidth=20.0)
    ctx, events = _make_ctx(case, commands=commands, client=client, current_angle=0.0)
    state = RotateTurntableState()

    result = _drive_state(state, ctx)

    assert result is StateResult.OK
    assert ctx.current_angle == 360.0
    assert commands.stop_calls == []
    assert events.progress.values == [0, 100]


def test_rotate_discards_stale_complete_event_before_start(tmp_path: Path) -> None:
    commands = _Commands()
    client = _FakeClient()
    client.buffer_event(_FakeEvent(common_module._COMMAND_TURNTABLE_COMPLETE))
    case = _make_case(NRBand.N5, MeasurementTestType.HARMONIC, bandwidth=20.0)
    ctx, _ = _make_ctx(
        case,
        commands=commands,
        client=client,
        current_angle=0.0,
        settings=_make_settings(tmp_path, saturation_time_sec=0.0),
    )
    state = RotateTurntableState()

    started_at = time.monotonic()
    thread = _emit_after(
        client, 0.05, _FakeEvent(common_module._COMMAND_TURNTABLE_COMPLETE)
    )
    result = _drive_state(state, ctx)
    elapsed = time.monotonic() - started_at
    thread.join(timeout=1.0)

    assert result is StateResult.OK
    assert elapsed >= 0.04
    assert ctx.current_angle == 360.0


def test_rotate_discards_live_event_duplicate_from_buffer(tmp_path: Path) -> None:
    commands = _Commands()
    client = _FakeClient()
    case = _make_case(NRBand.N5, MeasurementTestType.HARMONIC, bandwidth=20.0)
    ctx, _ = _make_ctx(
        case,
        commands=commands,
        client=client,
        current_angle=0.0,
        settings=_make_settings(tmp_path, saturation_time_sec=0.0),
    )
    state = RotateTurntableState()

    def emit_sequence() -> None:
        time.sleep(0.02)
        complete = _FakeEvent(common_module._COMMAND_TURNTABLE_COMPLETE)
        client.buffer_event(complete)
        client.event_received.emit(complete)

    thread = threading.Thread(target=emit_sequence, daemon=True)
    thread.start()
    result = _drive_state(state, ctx)
    thread.join(timeout=1.0)

    assert result is StateResult.OK
    assert client.pop_events(lambda event: True) == []


def test_rotate_discards_live_progress_duplicate_from_buffer(tmp_path: Path) -> None:
    commands = _Commands()
    client = _FakeClient()
    case = _make_case(NRBand.N5, MeasurementTestType.HARMONIC, bandwidth=20.0)
    ctx, events = _make_ctx(
        case,
        commands=commands,
        client=client,
        current_angle=0.0,
        settings=_make_settings(tmp_path, saturation_time_sec=0.0),
    )
    state = RotateTurntableState()

    def emit_sequence() -> None:
        time.sleep(0.02)
        progress = _FakeEvent(
            common_module._COMMAND_TURNTABLE_PROGRESS,
            {"Current Angle": 90.0},
        )
        client.buffer_event(progress)
        client.event_received.emit(progress)
        time.sleep(0.02)
        complete = _FakeEvent(common_module._COMMAND_TURNTABLE_COMPLETE)
        client.buffer_event(complete)
        client.event_received.emit(complete)

    thread = threading.Thread(target=emit_sequence, daemon=True)
    thread.start()
    result = _drive_state(state, ctx)
    thread.join(timeout=1.0)

    assert result is StateResult.OK
    assert events.turntable_info_changed.values == [
        {"target_angle": 360.0, "setting_speed": 5},
        {"current_angle": 90.0},
        {"current_angle": 360.0},
    ]
    assert client.pop_events(lambda event: True) == []


def test_rotate_discards_buffered_progress_duplicate_from_late_signal(
    tmp_path: Path,
) -> None:
    progress = _FakeEvent(
        common_module._COMMAND_TURNTABLE_PROGRESS,
        {"Current Angle": 90.0},
    )
    complete = _FakeEvent(common_module._COMMAND_TURNTABLE_COMPLETE)
    commands = _Commands(buffer_on_rotate=[progress, complete])
    client = _FakeClient()
    case = _make_case(NRBand.N5, MeasurementTestType.HARMONIC, bandwidth=20.0)
    ctx, events = _make_ctx(
        case,
        commands=commands,
        client=client,
        current_angle=0.0,
        settings=_make_settings(tmp_path, saturation_time_sec=0.0),
    )
    state = RotateTurntableState()

    result = _drive_state(state, ctx)
    client.event_received.emit(progress)
    client.event_received.emit(complete)

    assert result is StateResult.OK
    assert events.turntable_info_changed.values == [
        {"target_angle": 360.0, "setting_speed": 5},
        {"current_angle": 90.0},
        {"current_angle": 360.0},
    ]


def test_rotate_consumes_buffered_progress_event_for_display_only() -> None:
    commands = _Commands(
        buffer_on_rotate=[
            _FakeEvent(
                common_module._COMMAND_TURNTABLE_PROGRESS,
                {"Current Angle": 90.0},
            ),
            _FakeEvent(common_module._COMMAND_TURNTABLE_COMPLETE),
        ]
    )
    client = _FakeClient()
    case = _make_case(NRBand.N5, MeasurementTestType.HARMONIC, bandwidth=20.0)
    ctx, events = _make_ctx(case, commands=commands, client=client, current_angle=0.0)
    state = RotateTurntableState()

    result = _drive_state(state, ctx)

    assert result is StateResult.OK
    assert ctx.current_angle == 360.0
    assert events.turntable_info_changed.values == [
        {"target_angle": 360.0, "setting_speed": 5},
        {"current_angle": 90.0},
        {"current_angle": 360.0},
    ]


def test_rotate_uses_last_valid_buffered_progress_angle() -> None:
    commands = _Commands(
        buffer_on_rotate=[
            _FakeEvent(
                common_module._COMMAND_TURNTABLE_PROGRESS,
                {"Current Angle": 30.0},
            ),
            _FakeEvent(
                common_module._COMMAND_TURNTABLE_PROGRESS,
                {"current_angle": 120.0},
            ),
            _FakeEvent(
                common_module._COMMAND_TURNTABLE_PROGRESS,
                {"Current Angle": "180.0"},
            ),
            _FakeEvent(common_module._COMMAND_TURNTABLE_COMPLETE),
        ]
    )
    client = _FakeClient()
    case = _make_case(NRBand.N5, MeasurementTestType.HARMONIC, bandwidth=20.0)
    ctx, events = _make_ctx(case, commands=commands, client=client, current_angle=0.0)
    state = RotateTurntableState()

    result = _drive_state(state, ctx)

    assert result is StateResult.OK
    assert ctx.current_angle == 360.0
    assert events.turntable_info_changed.values == [
        {"target_angle": 360.0, "setting_speed": 5},
        {"current_angle": 180.0},
        {"current_angle": 360.0},
    ]


def test_rotate_360_to_zero_toggle() -> None:
    commands = _Commands()
    client = _FakeClient()
    case = _make_case(NRBand.N78, MeasurementTestType.HARMONIC, bandwidth=100.0)
    ctx, _ = _make_ctx(case, commands=commands, client=client, current_angle=360.0)
    state = RotateTurntableState()

    thread = _emit_after(
        client, 0.05, _FakeEvent(common_module._COMMAND_TURNTABLE_COMPLETE)
    )
    result = _drive_state(state, ctx)
    thread.join(timeout=1.0)

    assert result is StateResult.OK
    assert ctx.current_angle == 0.0
    assert commands.rotate_calls == [
        (client, {"angle": 0.0, "turntable_speed": 3}),
    ]


def test_rotate_uses_settings_saturation_time_instead_of_fallback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(common_module, "_SETTLING_SEC", 0.5)
    monkeypatch.setattr(common_module, "_POLL_INTERVAL_SEC", 0.005)
    commands = _Commands()
    client = _FakeClient()
    case = _make_case(NRBand.N78, MeasurementTestType.HARMONIC, bandwidth=100.0)
    ctx, _ = _make_ctx(
        case,
        commands=commands,
        client=client,
        settings=_make_settings(tmp_path, saturation_time_sec=0.0),
    )
    state = RotateTurntableState()

    thread = _emit_after(
        client, 0.02, _FakeEvent(common_module._COMMAND_TURNTABLE_COMPLETE)
    )
    started_at = time.monotonic()
    result = _drive_state(state, ctx)
    elapsed = time.monotonic() - started_at
    thread.join(timeout=1.0)

    assert result is StateResult.OK
    assert elapsed < 0.3


def test_rotate_skips_when_co3000_is_not_connected() -> None:
    commands = _Commands()
    client = _FakeClient()
    case = _make_case(NRBand.N5, MeasurementTestType.HARMONIC, bandwidth=20.0)
    ctx, events = _make_ctx(case, commands=commands, client=client, current_angle=0.0)
    ctx.equipment_state = {"CO3000": False}
    state = RotateTurntableState()

    result = _drive_state(state, ctx)

    assert result is StateResult.OK
    assert state.next_state(ctx, result) == "MeasureHarmonics"
    assert commands.rotate_calls == []
    assert ctx.current_angle == 0.0
    assert events.turntable_info_changed.values == []
    assert events.error.values


def test_rotate_skip_keeps_360_degree_angle_when_co3000_is_not_connected() -> None:
    commands = _Commands()
    client = _FakeClient()
    case = _make_case(NRBand.N78, MeasurementTestType.HARMONIC, bandwidth=100.0)
    ctx, events = _make_ctx(case, commands=commands, client=client, current_angle=360.0)
    ctx.equipment_state = {"CO3000": False}
    state = RotateTurntableState()

    result = _drive_state(state, ctx)

    assert result is StateResult.OK
    assert state.next_state(ctx, result) == "MeasureHarmonics"
    assert commands.rotate_calls == []
    assert ctx.current_angle == 360.0
    assert events.turntable_info_changed.values == []
    assert events.error.values


def test_band_group_speed_for_n78() -> None:
    commands = _Commands()
    client = _FakeClient()
    case = _make_case(NRBand.N78, MeasurementTestType.HARMONIC, bandwidth=100.0)
    ctx, _ = _make_ctx(case, commands=commands, client=client)
    state = RotateTurntableState()

    thread = _emit_after(
        client, 0.05, _FakeEvent(common_module._COMMAND_TURNTABLE_COMPLETE)
    )
    _drive_state(state, ctx)
    thread.join(timeout=1.0)

    assert commands.rotate_calls[0][1]["turntable_speed"] == 3


def test_rotate_uses_custom_turntable_speed_from_settings(tmp_path: Path) -> None:
    commands = _Commands()
    client = _FakeClient()
    case = _make_case(NRBand.N78, MeasurementTestType.HARMONIC, bandwidth=100.0)
    ctx, events = _make_ctx(
        case,
        commands=commands,
        client=client,
        settings=_make_settings(
            tmp_path,
            saturation_time_sec=0.0,
            custom_turntable_speed=8,
        ),
    )
    state = RotateTurntableState()

    thread = _emit_after(
        client, 0.05, _FakeEvent(common_module._COMMAND_TURNTABLE_COMPLETE)
    )
    result = _drive_state(state, ctx)
    thread.join(timeout=1.0)

    assert result is StateResult.OK
    assert commands.rotate_calls[0][1]["turntable_speed"] == 8
    assert events.turntable_info_changed.values[0] == {
        "target_angle": 360.0,
        "setting_speed": 8,
    }


def test_ui_stop_triggers_stop_turntable_and_fail() -> None:
    commands = _Commands()
    client = _FakeClient()
    case = _make_case(NRBand.N5, MeasurementTestType.HARMONIC, bandwidth=20.0)
    ctx, events = _make_ctx(case, commands=commands, client=client, current_angle=0.0)
    state = RotateTurntableState()

    def request_stop() -> None:
        time.sleep(0.05)
        ctx.stopped = True

    threading.Thread(target=request_stop, daemon=True).start()
    result = _drive_state(state, ctx)

    assert result is StateResult.FAIL
    assert commands.stop_calls == [client]
    assert ctx.current_angle == 0.0
    assert state.next_state(ctx, result) is None
    assert events.error.values == []


def test_current_case_stop_triggers_stop_turntable_and_fail() -> None:
    commands = _Commands()
    client = _FakeClient()
    case = _make_case(NRBand.N5, MeasurementTestType.HARMONIC, bandwidth=20.0)
    ctx, events = _make_ctx(case, commands=commands, client=client, current_angle=0.0)
    state = RotateTurntableState()

    def request_stop() -> None:
        time.sleep(0.05)
        ctx.current_case_stop_requested = True

    threading.Thread(target=request_stop, daemon=True).start()
    result = _drive_state(state, ctx)

    assert result is StateResult.FAIL
    assert commands.stop_calls == [client]
    assert ctx.current_angle == 0.0
    assert state.next_state(ctx, result) is None
    assert events.error.values == []


def test_timeout_calls_stop_and_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(common_module, "_ROTATION_TIMEOUT_SEC", 0.1)
    commands = _Commands()
    client = _FakeClient()
    case = _make_case(NRBand.N5, MeasurementTestType.HARMONIC, bandwidth=20.0)
    ctx, events = _make_ctx(case, commands=commands, client=client)
    state = RotateTurntableState()

    result = _drive_state(state, ctx)

    assert result is StateResult.FAIL
    assert commands.stop_calls == [client]
    assert events.error.values == ["턴테이블 회전 타임아웃"]
    assert ctx.current_angle == 0.0
    assert state.next_state(ctx, result) is None


def test_error_event_marks_failure() -> None:
    commands = _Commands()
    client = _FakeClient()
    case = _make_case(NRBand.N5, MeasurementTestType.HARMONIC, bandwidth=20.0)
    ctx, events = _make_ctx(case, commands=commands, client=client)
    state = RotateTurntableState()

    err_event = _FakeEvent(
        common_module._COMMAND_EQUIPMENT_ERROR, {"message": "stalled"}
    )
    thread = _emit_after(client, 0.05, err_event)
    result = _drive_state(state, ctx)
    thread.join(timeout=1.0)

    assert result is StateResult.FAIL
    assert events.error.values == ["턴테이블 회전 실패: stalled"]
    assert commands.stop_calls == []
    assert ctx.current_angle == 0.0


def test_rotate_command_exception_returns_fail() -> None:
    commands = _Commands(raise_on_rotate=RuntimeError("send failed"))
    client = _FakeClient()
    case = _make_case(NRBand.N5, MeasurementTestType.HARMONIC, bandwidth=20.0)
    ctx, events = _make_ctx(case, commands=commands, client=client)
    state = RotateTurntableState()

    result = _drive_state(state, ctx)

    assert result is StateResult.FAIL
    assert events.error.values == ["턴테이블 회전 명령 실패: send failed"]
    assert commands.stop_calls == []


def test_inband_routes_to_measure_inband() -> None:
    commands = _Commands()
    client = _FakeClient()
    case = _make_case(NRBand.N78, MeasurementTestType.INBAND, bandwidth=100.0)
    ctx, _ = _make_ctx(case, commands=commands, client=client)
    state = RotateTurntableState()

    thread = _emit_after(
        client, 0.05, _FakeEvent(common_module._COMMAND_TURNTABLE_COMPLETE)
    )
    result = _drive_state(state, ctx)
    thread.join(timeout=1.0)

    assert state.next_state(ctx, result) == "MeasureInBand"


def test_progress_events_emit_current_angle_without_updating_context() -> None:
    commands = _Commands()
    client = _FakeClient()
    case = _make_case(NRBand.N5, MeasurementTestType.HARMONIC, bandwidth=20.0)
    ctx, events = _make_ctx(case, commands=commands, client=client)
    state = RotateTurntableState()
    angles_during_progress: list[float] = []

    def emit_sequence() -> None:
        time.sleep(0.02)
        client.event_received.emit(
            _FakeEvent(
                common_module._COMMAND_TURNTABLE_PROGRESS,
                {"Current Angle": 90.0},
            )
        )
        angles_during_progress.append(ctx.current_angle)
        time.sleep(0.02)
        client.event_received.emit(
            _FakeEvent(
                common_module._COMMAND_TURNTABLE_PROGRESS,
                {"Current Angle": "270.0"},
            )
        )
        angles_during_progress.append(ctx.current_angle)
        time.sleep(0.02)
        client.event_received.emit(
            _FakeEvent(common_module._COMMAND_TURNTABLE_COMPLETE)
        )

    thread = threading.Thread(target=emit_sequence, daemon=True)
    thread.start()
    result = _drive_state(state, ctx)
    thread.join(timeout=1.0)

    assert result is StateResult.OK
    assert angles_during_progress == [0.0, 0.0]
    assert ctx.current_angle == 360.0
    assert events.turntable_info_changed.values == [
        {"target_angle": 360.0, "setting_speed": 5},
        {"current_angle": 90.0},
        {"current_angle": 270.0},
        {"current_angle": 360.0},
    ]


def test_rapid_progress_events_are_coalesced_for_display() -> None:
    commands = _Commands()
    client = _FakeClient()
    case = _make_case(NRBand.N5, MeasurementTestType.HARMONIC, bandwidth=20.0)
    ctx, events = _make_ctx(case, commands=commands, client=client)
    state = RotateTurntableState()

    def emit_sequence() -> None:
        time.sleep(0.02)
        for angle in (90.0, 120.0, 180.0):
            client.event_received.emit(
                _FakeEvent(
                    common_module._COMMAND_TURNTABLE_PROGRESS,
                    {"Current Angle": angle},
                )
            )
            time.sleep(0.02)
        client.event_received.emit(
            _FakeEvent(common_module._COMMAND_TURNTABLE_COMPLETE)
        )

    thread = threading.Thread(target=emit_sequence, daemon=True)
    thread.start()
    result = _drive_state(state, ctx)
    thread.join(timeout=1.0)

    assert result is StateResult.OK
    assert events.progress.values == [0, 100]
    assert events.turntable_info_changed.values == [
        {"target_angle": 360.0, "setting_speed": 5},
        {"current_angle": 90.0},
        {"current_angle": 180.0},
        {"current_angle": 360.0},
    ]


def test_error_event_flushes_pending_progress_without_waiting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(common_module, "_PROGRESS_EMIT_INTERVAL_SEC", 10.0)
    commands = _Commands()
    client = _FakeClient()
    case = _make_case(NRBand.N5, MeasurementTestType.HARMONIC, bandwidth=20.0)
    ctx, events = _make_ctx(case, commands=commands, client=client)
    state = RotateTurntableState()

    def emit_sequence() -> None:
        time.sleep(0.02)
        client.event_received.emit(
            _FakeEvent(
                common_module._COMMAND_TURNTABLE_PROGRESS,
                {"Current Angle": 45.0},
            )
        )
        client.event_received.emit(
            _FakeEvent(
                common_module._COMMAND_TURNTABLE_PROGRESS,
                {"Current Angle": 90.0},
            )
        )
        client.event_received.emit(
            _FakeEvent(common_module._COMMAND_EQUIPMENT_ERROR, {"message": "stalled"})
        )

    thread = threading.Thread(target=emit_sequence, daemon=True)
    thread.start()
    started_at = time.monotonic()
    result = _drive_state(state, ctx)
    elapsed = time.monotonic() - started_at
    thread.join(timeout=1.0)

    assert result is StateResult.FAIL
    assert elapsed < 0.5
    assert events.error.values == ["턴테이블 회전 실패: stalled"]
    assert events.turntable_info_changed.values == [
        {"target_angle": 360.0, "setting_speed": 5},
        {"current_angle": 45.0},
        {"current_angle": 90.0},
    ]


def test_progress_event_ignores_unapproved_angle_key() -> None:
    commands = _Commands()
    client = _FakeClient()
    case = _make_case(NRBand.N5, MeasurementTestType.HARMONIC, bandwidth=20.0)
    ctx, events = _make_ctx(case, commands=commands, client=client)
    state = RotateTurntableState()

    def emit_sequence() -> None:
        time.sleep(0.02)
        client.event_received.emit(
            _FakeEvent(
                common_module._COMMAND_TURNTABLE_PROGRESS,
                {"current_angle": 90.0},
            )
        )
        time.sleep(0.02)
        client.event_received.emit(
            _FakeEvent(common_module._COMMAND_TURNTABLE_COMPLETE)
        )

    thread = threading.Thread(target=emit_sequence, daemon=True)
    thread.start()
    result = _drive_state(state, ctx)
    thread.join(timeout=1.0)

    assert result is StateResult.OK
    assert events.turntable_info_changed.values == [
        {"target_angle": 360.0, "setting_speed": 5},
        {"current_angle": 360.0},
    ]
