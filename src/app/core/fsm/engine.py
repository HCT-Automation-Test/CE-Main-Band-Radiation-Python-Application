"""통합 세션 FSM 전이 엔진."""
from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from app.core.fsm.base import State, StateResult

if TYPE_CHECKING:
    from app.core.fsm.context import SessionContext

logger = logging.getLogger(__name__)

_POLL_INTERVAL_SEC = 0.1


class FSMEngine:
    """통합 세션 FSM 전이 엔진.

    State 인스턴스를 name으로 등록하고, enter → run → exit → next_state
    루프를 실행한다. QThread 워커 내에서 동기적으로 호출된다.
    """

    def __init__(self, ctx: "SessionContext") -> None:
        self._ctx = ctx
        self._states: dict[str, State] = {}
        self._current_state_name: str | None = None

    def register(self, state: State) -> None:
        """State를 name으로 등록한다. 중복 name은 ValueError."""
        if state.name in self._states:
            raise ValueError(f"State name 중복: {state.name!r}")
        self._states[state.name] = state

    @property
    def current_state_name(self) -> str | None:
        """현재 실행 중인 상태 이름."""
        return self._current_state_name

    def run(self, initial_state: str = "SessionInit") -> None:
        """FSM 메인 루프. 상태 전이를 반복한다.

        의사 코드:
        1. _current_state_name = initial_state
        2. while _current_state_name is not None:
           a. state = _states[_current_state_name]
           b. ctx.events.state_changed.emit(state.name)
           c. state.enter(ctx)
           d. result = state.run(ctx)
           e. state.exit(ctx)
           f. _current_state_name = state.next_state(ctx, result)
        3. 루프 종료 시 세션 완료
        """
        if initial_state not in self._states:
            raise ValueError(f"등록되지 않은 초기 State: {initial_state!r}")

        self._current_state_name = initial_state
        while self._current_state_name is not None:
            self._wait_if_paused()
            if self._ctx.stopped:
                break

            state_name = self._current_state_name
            try:
                state = self._states[state_name]
            except KeyError as exc:
                raise ValueError(f"등록되지 않은 State: {state_name!r}") from exc

            if self._ctx.events is not None:
                self._ctx.events.state_changed.emit(state.name)

            result = self._run_state(state)
            if self._ctx.stopped:
                break
            if result is StateResult.RETRY:
                continue
            if result is StateResult.WAIT_USER:
                self._ctx.paused = True
                continue

            self._current_state_name = state.next_state(self._ctx, result)

        self._current_state_name = None

    def _run_state(self, state: State) -> StateResult:
        entered = False
        try:
            state.enter(self._ctx)
            entered = True
            return state.run(self._ctx)
        finally:
            if entered:
                state.exit(self._ctx)

    def _wait_if_paused(self) -> None:
        while self._ctx.paused and not self._ctx.stopped:
            time.sleep(_POLL_INTERVAL_SEC)


def build_session_engine(ctx: "SessionContext") -> FSMEngine:
    """모든 상태를 등록한 세션 엔진을 구성한다."""
    from app.core.fsm.states.measurement.bilog import MeasureBilogState
    from app.core.fsm.states.measurement.common import (
        ResetSwitchBoxState,
        RotateTurntableState,
        SetSwitchBoxState,
        SetupSpectrumAnalyzerState,
    )
    from app.core.fsm.states.measurement.harmonic import (
        MeasureFundamentalState,
        MeasureHarmonicsState,
    )
    from app.core.fsm.states.measurement.inband import MeasureInBandState
    from app.core.fsm.states.nr_setup import (
        NRCallConnectState,
        NRCallDisconnectedState,
    )
    from app.core.fsm.states.session import (
        CheckNextCaseState,
        IdleState,
        SessionInitState,
        TestEndState,
    )
    from app.core.fsm.states.transition import (
        AntPolChangeState,
        DUTAxisChangeState,
        HandoverState,
        RecallChangeState,
        TestTypeChangeState,
    )

    engine = FSMEngine(ctx)

    # 세션 제어 상태
    engine.register(SessionInitState())
    engine.register(IdleState())
    engine.register(CheckNextCaseState())
    engine.register(TestEndState())

    # NR 연결 관리 상태
    engine.register(NRCallConnectState())
    engine.register(NRCallDisconnectedState())

    # 시험 간 전환 상태
    engine.register(AntPolChangeState())
    engine.register(HandoverState())
    engine.register(RecallChangeState())
    engine.register(DUTAxisChangeState())
    engine.register(TestTypeChangeState())

    # 측정 공유 스텝 (Harmonic / InBand / Bilog 공통)
    engine.register(SetSwitchBoxState())
    engine.register(SetupSpectrumAnalyzerState())
    engine.register(RotateTurntableState())
    engine.register(ResetSwitchBoxState())

    # Harmonic 전용 측정 상태
    engine.register(MeasureFundamentalState())
    engine.register(MeasureHarmonicsState())

    # InBand / Bilog 측정 상태 (스켈레톤)
    engine.register(MeasureInBandState())
    engine.register(MeasureBilogState())

    return engine
