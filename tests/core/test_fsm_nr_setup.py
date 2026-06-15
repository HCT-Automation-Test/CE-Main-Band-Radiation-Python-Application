from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

from app.core.fsm.base import StateResult
from app.core.fsm.context import SessionContext
from app.core.fsm.states.nr_setup import NRCallConnectState, NRCallDisconnectedState
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
        self.messages: list[str] = []

    def emit(self, message: str) -> None:
        self.messages.append(message)


class _Events:
    def __init__(self) -> None:
        self.error = _SignalRecorder()
        self.user_action_required = _SignalRecorder()


class _Commands:
    def __init__(
        self,
        connected: bool,
        *,
        exception: Exception | None = None,
    ) -> None:
        self.connected = connected
        self.exception = exception
        self.calls: list[tuple[Any, dict[str, Any]]] = []

    def setup_mt8000(self, client: Any, **params: Any) -> bool:
        self.calls.append((client, params))
        if self.exception is not None:
            raise self.exception
        return self.connected


def _make_case() -> TestCase:
    return TestCase(
        band=NRBand.N78,
        bandwidth=100.0,
        test_type=MeasurementTestType.HARMONIC,
        modulation=Modulation.QPSK,
        rb_allocation=RBAllocation.INNER_FULL,
        test_channel=ChannelEnum.MID,
        antenna_pol=AntennaPol.H,
        dut_axis=DUTAxis.X,
        dut_ant_position="Upper",
    )


def _make_settings(tmp_path: Path, *, connection_waiting_time_sec: int) -> TestRunSettings:
    template_path = tmp_path / "template.xlsx"
    screenshot_root_dir = tmp_path / "screenshots"
    template_path.write_bytes(b"template")
    screenshot_root_dir.mkdir(exist_ok=True)
    return TestRunSettings(
        eut_name="SM-000",
        template_path=template_path,
        screenshot_root_dir=screenshot_root_dir,
        saturation_time_sec=5,
        connection_waiting_time_sec=connection_waiting_time_sec,
        atten_level_db=0,
        next_peak_search_level_db=0,
        active_tdf_file_name="NR_Radiated.tdf",
    )


def _connect_mt8000a(ctx: SessionContext) -> SessionContext:
    ctx.equipment_state = {"MT8000A": True}
    return ctx


def test_nr_call_connect_calls_setup_mt8000_with_current_case_params() -> None:
    commands = _Commands(connected=True)
    client = object()
    ctx = _connect_mt8000a(SessionContext(
        queue=[_make_case()],
        commands=commands,
        events=_Events(),  # type: ignore[arg-type]
        client=client,
    ))

    result = NRCallConnectState().run(ctx)

    assert result is StateResult.OK
    assert commands.calls == [
        (
            client,
            {
                "band": 78,
                "bw": 100,
                "modulation": Modulation.QPSK,
                "rb_size": 135,
                "rb_offset": 67,
                "channel": 636666,
                "waiting_time": 5,
            },
        )
    ]


def test_nr_call_connect_uses_settings_connection_waiting_time(
    tmp_path: Path,
) -> None:
    commands = _Commands(connected=True)
    client = object()
    ctx = _connect_mt8000a(SessionContext(
        queue=[_make_case()],
        commands=commands,
        events=_Events(),  # type: ignore[arg-type]
        client=client,
        settings=_make_settings(tmp_path, connection_waiting_time_sec=7),
    ))

    result = NRCallConnectState().run(ctx)

    assert result is StateResult.OK
    assert commands.calls[0][1]["waiting_time"] == 7


def test_nr_call_connect_skips_when_mt8000a_is_not_connected() -> None:
    commands = _Commands(connected=True)
    events = _Events()
    ctx = _connect_mt8000a(SessionContext(
        queue=[_make_case()],
        commands=commands,
        events=events,  # type: ignore[arg-type]
    ))
    ctx.equipment_state = {"MT8000A": False}
    state = NRCallConnectState()

    result = state.run(ctx)

    assert result is StateResult.FAIL
    assert state.next_state(ctx, result) == "NRCallDisconnected"
    assert commands.calls == []
    assert events.error.messages


def test_nr_call_connect_continues_to_pending_transition_after_full_setup() -> None:
    commands = _Commands(connected=True)
    ctx = _connect_mt8000a(SessionContext(
        queue=[_make_case()],
        commands=commands,
        events=_Events(),  # type: ignore[arg-type]
    ))
    ctx.pending_transition_states = ["AntPolChange"]
    state = NRCallConnectState()

    result = state.run(ctx)

    assert result is StateResult.OK
    assert state.next_state(ctx, result) == "AntPolChange"
    assert ctx.pending_transition_states == []


def test_nr_call_connect_returns_fail_and_emits_error_on_false_result() -> None:
    commands = _Commands(connected=False)
    events = _Events()
    ctx = _connect_mt8000a(SessionContext(
        queue=[_make_case()],
        commands=commands,
        events=events,  # type: ignore[arg-type]
    ))
    state = NRCallConnectState()

    result = state.run(ctx)

    assert result is StateResult.FAIL
    assert state.next_state(ctx, result) == "NRCallDisconnected"
    assert events.error.messages == [
        "NR Call 연결 실패: setup_mt8000 returned false"
    ]


def test_nr_call_connect_returns_fail_and_emits_error_on_exception() -> None:
    commands = _Commands(connected=True, exception=RuntimeError("instrument timeout"))
    events = _Events()
    ctx = _connect_mt8000a(SessionContext(
        queue=[_make_case()],
        commands=commands,
        events=events,  # type: ignore[arg-type]
    ))
    state = NRCallConnectState()

    result = state.run(ctx)

    assert result is StateResult.FAIL
    assert state.next_state(ctx, result) == "NRCallDisconnected"
    assert events.error.messages == [
        "NR Call 연결 실패: instrument timeout"
    ]


def test_nr_call_disconnected_waits_for_user_action_before_reconnect() -> None:
    events = _Events()
    ctx = SessionContext(
        queue=[_make_case()],
        commands=_Commands(connected=True),
        events=events,  # type: ignore[arg-type]
    )
    state = NRCallDisconnectedState()

    def complete_action() -> None:
        time.sleep(0.02)
        ctx.user_action_completed.set()

    threading.Thread(target=complete_action, daemon=True).start()

    result = state.run(ctx)

    assert result is StateResult.OK
    assert events.user_action_required.messages == ["비행기 모드 On/Off 후 확인"]
    assert state.next_state(ctx, result) == "NRCallConnect"
