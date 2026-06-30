from __future__ import annotations

import logging
from collections.abc import Sequence

import pytest

from app.core.fsm.base import State, StateResult
from app.core.fsm.context import SessionContext
from app.core.fsm.engine import FSMEngine
from app.models.enums import FilterPath, InputPath


class _SignalRecorder:
    def __init__(self) -> None:
        self.values: list[object] = []

    def emit(self, value: object) -> None:
        self.values.append(value)


class _Events:
    def __init__(self) -> None:
        self.state_changed = _SignalRecorder()
        self.switch_box_info_changed = _SignalRecorder()
        self.error = _SignalRecorder()


class _Commands:
    def __init__(self) -> None:
        self.switch_box_calls: list[dict[str, object]] = []

    def set_switch_box(
        self,
        client: object,
        *,
        input_path: InputPath,
        filter_path: FilterPath,
    ) -> bool:
        self.switch_box_calls.append(
            {"input_path": input_path, "filter_path": filter_path}
        )
        return True


class _State(State):
    def __init__(
        self,
        name: str,
        log: list[str],
        *,
        results: Sequence[StateResult] = (StateResult.OK,),
        next_name: str | None = None,
        raises: Exception | None = None,
    ) -> None:
        self.name = name
        self._log = log
        self._results = list(results)
        self._next_name = next_name
        self._raises = raises

    def enter(self, ctx: SessionContext) -> None:
        self._log.append(f"{self.name}.enter")

    def run(self, ctx: SessionContext) -> StateResult:
        self._log.append(f"{self.name}.run")
        if self._raises is not None:
            raise self._raises
        return self._results.pop(0)

    def exit(self, ctx: SessionContext) -> None:
        self._log.append(f"{self.name}.exit")

    def next_state(
        self, ctx: SessionContext, result: StateResult
    ) -> str | None:
        self._log.append(f"{self.name}.next")
        return self._next_name


def _make_engine(events: _Events | None = None) -> FSMEngine:
    ctx = SessionContext(
        queue=[],
        commands=object(),
        events=events,  # type: ignore[arg-type]
    )
    return FSMEngine(ctx)


def test_engine_runs_registered_states_in_order() -> None:
    events = _Events()
    engine = _make_engine(events)
    log: list[str] = []
    engine.register(_State("A", log, next_name="B"))
    engine.register(_State("B", log, next_name=None))

    engine.run("A")

    assert log == [
        "A.enter",
        "A.run",
        "A.exit",
        "A.next",
        "B.enter",
        "B.run",
        "B.exit",
        "B.next",
    ]
    assert events.state_changed.values == ["A", "B"]
    assert engine.current_state_name is None


def test_engine_logs_state_entry(caplog: pytest.LogCaptureFixture) -> None:
    engine = _make_engine()
    log: list[str] = []
    engine.register(_State("A", log, next_name="B"))
    engine.register(_State("B", log, next_name=None))

    with caplog.at_level(logging.INFO, logger="app.core.fsm.engine"):
        engine.run("A")

    messages = [
        record.getMessage()
        for record in caplog.records
        if record.name == "app.core.fsm.engine"
    ]
    assert messages == [
        "FSM state entered: A",
        "FSM state entered: B",
    ]


def test_engine_retries_same_state_for_retry_result() -> None:
    engine = _make_engine()
    log: list[str] = []
    engine.register(
        _State("A", log, results=(StateResult.RETRY, StateResult.OK))
    )

    engine.run("A")

    assert log == [
        "A.enter",
        "A.run",
        "A.exit",
        "A.enter",
        "A.run",
        "A.exit",
        "A.next",
    ]


def test_engine_returns_to_idle_after_current_case_stop_request() -> None:
    events = _Events()
    ctx = SessionContext(
        queue=[],
        commands=object(),
        events=events,  # type: ignore[arg-type]
    )
    engine = FSMEngine(ctx)
    log: list[str] = []

    class _StopRequestedState(_State):
        def run(self, ctx: SessionContext) -> StateResult:
            result = super().run(ctx)
            ctx.current_case_stop_requested = True
            return result

    engine.register(_StopRequestedState("Measure", log, next_name="Next"))
    engine.register(_State("Next", log, next_name=None))
    engine.register(_State("Idle", log, next_name=None))
    ctx.test_start_requested.set()

    engine.run("Measure")

    assert log == [
        "Measure.enter",
        "Measure.run",
        "Measure.exit",
        "Idle.enter",
        "Idle.run",
        "Idle.exit",
        "Idle.next",
    ]
    assert events.state_changed.values == ["Measure", "Idle"]
    assert not ctx.current_case_stop_requested
    assert not ctx.test_start_requested.is_set()


def test_engine_resets_switch_box_on_current_case_stop_request() -> None:
    events = _Events()
    commands = _Commands()
    ctx = SessionContext(
        queue=[],
        commands=commands,
        events=events,  # type: ignore[arg-type]
        client=object(),
        equipment_state={"Switch Box": True},
    )
    engine = FSMEngine(ctx)
    log: list[str] = []

    class _StopRequestedState(_State):
        def run(self, ctx: SessionContext) -> StateResult:
            result = super().run(ctx)
            ctx.current_case_stop_requested = True
            return result

    engine.register(_StopRequestedState("Measure", log, next_name=None))
    engine.register(_State("Idle", log, next_name=None))
    ctx.test_start_requested.set()

    engine.run("Measure")

    assert commands.switch_box_calls == [
        {"input_path": InputPath.INPUT2, "filter_path": FilterPath.THRU}
    ]
    assert events.switch_box_info_changed.values == [
        {"mast": "3m", "filter": "THRU"}
    ]


def test_engine_resets_switch_box_for_each_current_case_stop_in_same_session() -> None:
    events = _Events()
    commands = _Commands()
    ctx = SessionContext(
        queue=[],
        commands=commands,
        events=events,  # type: ignore[arg-type]
        client=object(),
        equipment_state={"Switch Box": True},
    )
    engine = FSMEngine(ctx)
    log: list[str] = []

    class _StopRequestedState(_State):
        def run(self, ctx: SessionContext) -> StateResult:
            result = super().run(ctx)
            ctx.current_case_stop_requested = True
            return result

    class _RestartOnceIdleState(_State):
        def __init__(self) -> None:
            super().__init__(
                "Idle",
                log,
                results=(StateResult.OK, StateResult.OK),
                next_name=None,
            )
            self._run_count = 0

        def run(self, ctx: SessionContext) -> StateResult:
            self._run_count += 1
            return super().run(ctx)

        def next_state(
            self, ctx: SessionContext, result: StateResult
        ) -> str | None:
            super().next_state(ctx, result)
            if self._run_count == 1:
                return "Measure"
            return None

    engine.register(
        _StopRequestedState(
            "Measure",
            log,
            results=(StateResult.OK, StateResult.OK),
            next_name=None,
        )
    )
    engine.register(_RestartOnceIdleState())
    ctx.test_start_requested.set()

    engine.run("Measure")

    assert commands.switch_box_calls == [
        {"input_path": InputPath.INPUT2, "filter_path": FilterPath.THRU},
        {"input_path": InputPath.INPUT2, "filter_path": FilterPath.THRU},
    ]
    assert events.state_changed.values == ["Measure", "Idle", "Measure", "Idle"]
    assert not ctx.current_case_stop_requested


def test_engine_resets_switch_box_on_stop_request() -> None:
    events = _Events()
    commands = _Commands()
    ctx = SessionContext(
        queue=[],
        commands=commands,
        events=events,  # type: ignore[arg-type]
        client=object(),
        equipment_state={"Switch Box": True},
    )
    engine = FSMEngine(ctx)
    log: list[str] = []

    class _StopRequestedState(_State):
        def run(self, ctx: SessionContext) -> StateResult:
            result = super().run(ctx)
            ctx.stopped = True
            return result

    engine.register(_StopRequestedState("Measure", log, next_name=None))

    engine.run("Measure")

    assert commands.switch_box_calls == [
        {"input_path": InputPath.INPUT2, "filter_path": FilterPath.THRU}
    ]


def test_engine_does_not_reset_switch_box_when_disconnected_on_stop() -> None:
    events = _Events()
    commands = _Commands()
    ctx = SessionContext(
        queue=[],
        commands=commands,
        events=events,  # type: ignore[arg-type]
        client=object(),
        equipment_state={"Switch Box": False},
    )
    engine = FSMEngine(ctx)
    log: list[str] = []

    class _StopRequestedState(_State):
        def run(self, ctx: SessionContext) -> StateResult:
            result = super().run(ctx)
            ctx.stopped = True
            return result

    engine.register(_StopRequestedState("Measure", log, next_name=None))

    engine.run("Measure")

    assert commands.switch_box_calls == []


def test_engine_resets_switch_box_when_fail_ends_session() -> None:
    events = _Events()
    commands = _Commands()
    ctx = SessionContext(
        queue=[],
        commands=commands,
        events=events,  # type: ignore[arg-type]
        client=object(),
        equipment_state={"Switch Box": True},
    )
    engine = FSMEngine(ctx)
    log: list[str] = []

    engine.register(
        _State("Measure", log, results=(StateResult.FAIL,), next_name=None)
    )

    engine.run("Measure")

    assert log == [
        "Measure.enter",
        "Measure.run",
        "Measure.exit",
        "Measure.next",
    ]
    assert commands.switch_box_calls == [
        {"input_path": InputPath.INPUT2, "filter_path": FilterPath.THRU}
    ]
    assert events.switch_box_info_changed.values == [
        {"mast": "3m", "filter": "THRU"}
    ]


def test_engine_does_not_reset_switch_box_when_fail_routes_to_next_state() -> None:
    events = _Events()
    commands = _Commands()
    ctx = SessionContext(
        queue=[],
        commands=commands,
        events=events,  # type: ignore[arg-type]
        client=object(),
        equipment_state={"Switch Box": True},
    )
    engine = FSMEngine(ctx)
    log: list[str] = []

    engine.register(
        _State(
            "Measure",
            log,
            results=(StateResult.FAIL,),
            next_name="NRCallDisconnected",
        )
    )
    engine.register(_State("NRCallDisconnected", log, next_name=None))

    engine.run("Measure")

    assert log == [
        "Measure.enter",
        "Measure.run",
        "Measure.exit",
        "Measure.next",
        "NRCallDisconnected.enter",
        "NRCallDisconnected.run",
        "NRCallDisconnected.exit",
        "NRCallDisconnected.next",
    ]
    assert commands.switch_box_calls == []


def test_engine_resets_switch_box_when_state_raises() -> None:
    events = _Events()
    commands = _Commands()
    ctx = SessionContext(
        queue=[],
        commands=commands,
        events=events,  # type: ignore[arg-type]
        client=object(),
        equipment_state={"Switch Box": True},
    )
    engine = FSMEngine(ctx)
    log: list[str] = []
    engine.register(_State("Measure", log, raises=RuntimeError("boom")))

    with pytest.raises(RuntimeError, match="boom"):
        engine.run("Measure")

    assert log == ["Measure.enter", "Measure.run", "Measure.exit"]
    assert commands.switch_box_calls == [
        {"input_path": InputPath.INPUT2, "filter_path": FilterPath.THRU}
    ]


def test_engine_does_not_reset_switch_box_when_disconnected_on_fail() -> None:
    events = _Events()
    commands = _Commands()
    ctx = SessionContext(
        queue=[],
        commands=commands,
        events=events,  # type: ignore[arg-type]
        client=object(),
        equipment_state={"Switch Box": False},
    )
    engine = FSMEngine(ctx)
    log: list[str] = []

    engine.register(
        _State("Measure", log, results=(StateResult.FAIL,), next_name=None)
    )

    engine.run("Measure")

    assert commands.switch_box_calls == []

def test_engine_logs_retried_state_entry(
    caplog: pytest.LogCaptureFixture,
) -> None:
    engine = _make_engine()
    log: list[str] = []
    engine.register(
        _State("A", log, results=(StateResult.RETRY, StateResult.OK))
    )

    with caplog.at_level(logging.INFO, logger="app.core.fsm.engine"):
        engine.run("A")

    messages = [
        record.getMessage()
        for record in caplog.records
        if record.name == "app.core.fsm.engine"
    ]
    assert messages == [
        "FSM state entered: A",
        "FSM state entered: A",
    ]


def test_engine_calls_exit_when_state_raises() -> None:
    engine = _make_engine()
    log: list[str] = []
    engine.register(_State("A", log, raises=RuntimeError("boom")))

    with pytest.raises(RuntimeError, match="boom"):
        engine.run("A")

    assert log == ["A.enter", "A.run", "A.exit"]


def test_engine_rejects_unknown_initial_state() -> None:
    engine = _make_engine()

    with pytest.raises(ValueError, match="등록되지 않은 초기 State"):
        engine.run("Missing")
