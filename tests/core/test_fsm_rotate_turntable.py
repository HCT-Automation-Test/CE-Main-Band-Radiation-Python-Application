from __future__ import annotations

import threading
import time
from typing import Any

import pytest

from app.core.fsm.base import StateResult
from app.core.fsm.context import SessionContext
from app.core.fsm.states.measurement import common as common_module
from app.core.fsm.states.measurement.common import RotateTurntableState
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


class _SignalRecorder:
    def __init__(self) -> None:
        self.values: list[Any] = []

    def emit(self, value: Any = None) -> None:
        self.values.append(value)


class _Events:
    def __init__(self) -> None:
        self.error = _SignalRecorder()
        self.progress = _SignalRecorder()


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


class _FakeEvent:
    def __init__(self, op: str, params: dict[str, Any] | None = None) -> None:
        self.op = op
        self.params = params or {}


class _Commands:
    def __init__(self, *, raise_on_rotate: Exception | None = None) -> None:
        self.raise_on_rotate = raise_on_rotate
        self.rotate_calls: list[tuple[Any, dict[str, Any]]] = []
        self.stop_calls: list[Any] = []

    def rotate_turntable(self, client: Any, **kwargs: Any) -> None:
        self.rotate_calls.append((client, kwargs))
        if self.raise_on_rotate is not None:
            raise self.raise_on_rotate

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
) -> tuple[SessionContext, _Events]:
    events = _Events()
    ctx = SessionContext(
        queue=[case],
        commands=commands,
        events=events,  # type: ignore[arg-type]
        client=client if client is not None else _FakeClient(),
        current_angle=current_angle,
    )
    return ctx, events


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


def test_rotate_zero_to_360_with_band_group_speed() -> None:
    commands = _Commands()
    client = _FakeClient()
    case = _make_case(NRBand.N5, MeasurementTestType.HARMONIC, bandwidth=20.0)
    ctx, events = _make_ctx(case, commands=commands, client=client, current_angle=0.0)
    state = RotateTurntableState()

    thread = _emit_after(client, 0.05, _FakeEvent(common_module._OP_TURNTABLE_COMPLETE))
    result = _drive_state(state, ctx)
    thread.join(timeout=1.0)

    assert result is StateResult.OK
    assert ctx.current_angle == 360.0
    assert commands.rotate_calls == [
        (client, {"angle": 360.0, "turntable_speed": 6}),
    ]
    assert commands.stop_calls == []
    assert events.progress.values == [0, 100]
    assert state.next_state(ctx, result) == "MeasureHarmonics"


def test_rotate_360_to_zero_toggle() -> None:
    commands = _Commands()
    client = _FakeClient()
    case = _make_case(NRBand.N78, MeasurementTestType.HARMONIC, bandwidth=100.0)
    ctx, _ = _make_ctx(case, commands=commands, client=client, current_angle=360.0)
    state = RotateTurntableState()

    thread = _emit_after(client, 0.05, _FakeEvent(common_module._OP_TURNTABLE_COMPLETE))
    result = _drive_state(state, ctx)
    thread.join(timeout=1.0)

    assert result is StateResult.OK
    assert ctx.current_angle == 0.0
    assert commands.rotate_calls == [
        (client, {"angle": 0.0, "turntable_speed": 4}),
    ]


def test_band_group_speed_for_n78() -> None:
    commands = _Commands()
    client = _FakeClient()
    case = _make_case(NRBand.N78, MeasurementTestType.HARMONIC, bandwidth=100.0)
    ctx, _ = _make_ctx(case, commands=commands, client=client)
    state = RotateTurntableState()

    thread = _emit_after(client, 0.05, _FakeEvent(common_module._OP_TURNTABLE_COMPLETE))
    _drive_state(state, ctx)
    thread.join(timeout=1.0)

    assert commands.rotate_calls[0][1]["turntable_speed"] == 4


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
        common_module._OP_TURNTABLE_ERROR, {"message": "stalled"}
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

    thread = _emit_after(client, 0.05, _FakeEvent(common_module._OP_TURNTABLE_COMPLETE))
    result = _drive_state(state, ctx)
    thread.join(timeout=1.0)

    assert state.next_state(ctx, result) == "MeasureInBand"


def test_progress_events_are_ignored_until_complete() -> None:
    commands = _Commands()
    client = _FakeClient()
    case = _make_case(NRBand.N5, MeasurementTestType.HARMONIC, bandwidth=20.0)
    ctx, _ = _make_ctx(case, commands=commands, client=client)
    state = RotateTurntableState()

    def emit_sequence() -> None:
        time.sleep(0.02)
        client.event_received.emit(
            _FakeEvent(common_module._OP_TURNTABLE_PROGRESS, {"current_angle": 90.0})
        )
        time.sleep(0.02)
        client.event_received.emit(
            _FakeEvent(common_module._OP_TURNTABLE_PROGRESS, {"current_angle": 270.0})
        )
        time.sleep(0.02)
        client.event_received.emit(
            _FakeEvent(common_module._OP_TURNTABLE_COMPLETE)
        )

    thread = threading.Thread(target=emit_sequence, daemon=True)
    thread.start()
    result = _drive_state(state, ctx)
    thread.join(timeout=1.0)

    assert result is StateResult.OK
    assert ctx.current_angle == 360.0
