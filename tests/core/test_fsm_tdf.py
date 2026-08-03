from __future__ import annotations

from typing import Any

import pytest

from app.core.fsm.base import StateResult
from app.core.fsm.context import SessionContext
from app.core.fsm.states.tdf import ApplyTdfState, resolve_tdf_file_name
from app.models.enums import (
    AntennaPol,
    DUTAxis,
    Modulation,
    NRBand,
    RBAllocation,
    TestChannel as NRTestChannel,
    TestType as NRTestType,
)
from app.models.test_case import TestCase


class _SignalRecorder:
    def __init__(self) -> None:
        self.values: list[Any] = []

    def emit(self, value: Any) -> None:
        self.values.append(value)


class _Events:
    def __init__(self) -> None:
        self.error = _SignalRecorder()


class _Commands:
    def __init__(
        self,
        tdf_file_names: list[str],
        *,
        set_result: bool = True,
        list_exception: Exception | None = None,
    ) -> None:
        self.tdf_file_names = tdf_file_names
        self.set_result = set_result
        self.list_exception = list_exception
        self.calls: list[tuple[Any, ...]] = []

    def get_tdf_list(self, client: Any) -> list[str]:
        self.calls.append(("get_tdf_list", client))
        if self.list_exception is not None:
            raise self.list_exception
        return self.tdf_file_names

    def set_tdf(self, client: Any, *, tdf_file_name: str) -> bool:
        self.calls.append(("set_tdf", client, tdf_file_name))
        return self.set_result


def _make_case(
    band: NRBand = NRBand.N78,
    *,
    bandwidth: float = 100.0,
    test_type: NRTestType = NRTestType.HARMONIC,
) -> TestCase:
    return TestCase(
        band=band,
        bandwidth=bandwidth,
        test_type=test_type,
        modulation=Modulation.QPSK,
        rb_allocation=RBAllocation.INNER_FULL,
        test_channel=NRTestChannel.MID,
        antenna_pol=AntennaPol.H,
        dut_axis=DUTAxis.X,
        dut_ant_position="Upper",
    )


def _make_ctx(
    queue: list[TestCase],
    commands: _Commands,
    *,
    fsv40_connected: bool = True,
) -> tuple[SessionContext, _Events, object]:
    events = _Events()
    client = object()
    ctx = SessionContext(
        queue=queue,
        commands=commands,
        events=events,  # type: ignore[arg-type]
        client=client,
        equipment_state={"FSV40": fsv40_connected},
    )
    return ctx, events, client


def test_resolve_tdf_file_name_returns_full_unique_match() -> None:
    file_name = "2025_MAIN_Bilog Filter+3G HPF(30M-13G).tdf"

    assert resolve_tdf_file_name(["other.tdf", file_name], "3G HPF") == file_name


def test_resolve_tdf_file_name_rejects_missing_match() -> None:
    with pytest.raises(ValueError, match="일치하는 TDF 파일이 없습니다"):
        resolve_tdf_file_name(["other.tdf"], "3G HPF")


def test_resolve_tdf_file_name_is_case_sensitive() -> None:
    with pytest.raises(ValueError, match="일치하는 TDF 파일이 없습니다"):
        resolve_tdf_file_name(["main+3g hpf.tdf"], "3G HPF")


def test_resolve_tdf_file_name_rejects_multiple_matches() -> None:
    with pytest.raises(ValueError, match="2개입니다"):
        resolve_tdf_file_name(
            ["first+3G HPF.tdf", "second+3G HPF.tdf"],
            "3G HPF",
        )


def test_apply_tdf_uses_current_case_factor_and_routes_to_measurement() -> None:
    file_name = "2025_MAIN_UHB Filter+6G HPF(30M-26G).tdf"
    commands = _Commands([file_name])
    ctx, events, client = _make_ctx([_make_case()], commands)
    state = ApplyTdfState()

    result = state.run(ctx)

    assert result is StateResult.OK
    assert state.next_state(ctx, result) == "MeasureFundamental"
    assert commands.calls == [
        ("get_tdf_list", client),
        ("set_tdf", client, file_name),
    ]
    assert ctx.last_applied_factor_keyword == "6G HPF"
    assert events.error.values == []


def test_apply_tdf_skips_same_successful_factor() -> None:
    file_name = "main+6G HPF.tdf"
    commands = _Commands([file_name])
    cases = [_make_case(NRBand.N77), _make_case(NRBand.N78)]
    ctx, _, _ = _make_ctx(cases, commands)
    state = ApplyTdfState()

    assert state.run(ctx) is StateResult.OK
    ctx.current_index = 1
    assert state.run(ctx) is StateResult.OK

    assert [call[0] for call in commands.calls] == ["get_tdf_list", "set_tdf"]


def test_apply_tdf_reapplies_changed_and_previous_factor() -> None:
    commands = _Commands(["main+3G HPF.tdf", "main+6G HPF.tdf"])
    cases = [
        _make_case(NRBand.N78),
        _make_case(NRBand.N1, bandwidth=20.0),
        _make_case(NRBand.N77),
    ]
    ctx, _, _ = _make_ctx(cases, commands)
    state = ApplyTdfState()

    for index in range(len(cases)):
        ctx.current_index = index
        assert state.run(ctx) is StateResult.OK

    assert [
        call[2] for call in commands.calls if call[0] == "set_tdf"
    ] == ["main+6G HPF.tdf", "main+3G HPF.tdf", "main+6G HPF.tdf"]


def test_apply_tdf_fails_without_unique_match() -> None:
    commands = _Commands(["first+6G HPF.tdf", "second+6G HPF.tdf"])
    ctx, events, _ = _make_ctx([_make_case()], commands)
    state = ApplyTdfState()

    result = state.run(ctx)

    assert result is StateResult.FAIL
    assert state.next_state(ctx, result) is None
    assert [call[0] for call in commands.calls] == ["get_tdf_list"]
    assert ctx.last_applied_factor_keyword is None
    assert "2개입니다" in events.error.values[0]


def test_apply_tdf_fails_without_match_and_does_not_set() -> None:
    commands = _Commands(["other.tdf"])
    ctx, events, _ = _make_ctx([_make_case()], commands)
    state = ApplyTdfState()

    result = state.run(ctx)

    assert result is StateResult.FAIL
    assert state.next_state(ctx, result) is None
    assert [call[0] for call in commands.calls] == ["get_tdf_list"]
    assert ctx.last_applied_factor_keyword is None
    assert "일치하는 TDF 파일이 없습니다" in events.error.values[0]


def test_apply_tdf_fails_when_list_request_raises() -> None:
    commands = _Commands([], list_exception=RuntimeError("timeout"))
    ctx, events, _ = _make_ctx([_make_case()], commands)

    state = ApplyTdfState()
    result = state.run(ctx)

    assert result is StateResult.FAIL
    assert state.next_state(ctx, result) is None
    assert ctx.last_applied_factor_keyword is None
    assert events.error.values == ["TDF 자동 적용 실패: timeout"]


def test_apply_tdf_fails_when_set_returns_false() -> None:
    commands = _Commands(["main+6G HPF.tdf"], set_result=False)
    ctx, events, _ = _make_ctx([_make_case()], commands)

    state = ApplyTdfState()
    result = state.run(ctx)

    assert result is StateResult.FAIL
    assert state.next_state(ctx, result) is None
    assert [call[0] for call in commands.calls] == ["get_tdf_list", "set_tdf"]
    assert ctx.last_applied_factor_keyword is None
    assert "set_tdf returned false" in events.error.values[0]


def test_apply_tdf_skips_disconnected_fsv40_without_recording_success() -> None:
    commands = _Commands(["main+6G HPF.tdf"])
    ctx, events, _ = _make_ctx(
        [_make_case()],
        commands,
        fsv40_connected=False,
    )

    result = ApplyTdfState().run(ctx)

    assert result is StateResult.OK
    assert commands.calls == []
    assert ctx.last_applied_factor_keyword is None
    assert events.error.values == []
