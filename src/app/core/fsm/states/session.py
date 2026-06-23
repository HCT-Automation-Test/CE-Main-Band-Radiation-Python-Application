"""세션 제어 상태: Init, Idle, CheckNextCase, TestEnd."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.core.fsm.base import State, StateResult
from app.core.fsm.states.measurement.common import measurement_start_state_for
from app.core.instrument_connection import (
    describe_equipment_not_ready,
    is_selected_equipment_ready,
)
from app.models.band_group import find_band_group
from app.models.enums import InputPath

if TYPE_CHECKING:
    from app.core.fsm.context import SessionContext
    from app.models.test_case import TestCase

logger = logging.getLogger(__name__)

_WAIT_INTERVAL_SEC = 0.1


def _emit_error(ctx: "SessionContext", message: str) -> None:
    logger.error(message)
    if ctx.events is not None:
        ctx.events.error.emit(message)


def _wait_for_event(ctx: "SessionContext", event_name: str) -> bool:
    event = getattr(ctx, event_name)
    while not ctx.stopped and not ctx.current_case_stop_requested:
        if event.wait(_WAIT_INTERVAL_SEC):
            event.clear()
            if ctx.stopped or ctx.current_case_stop_requested:
                return False
            return True
    return False


def _uses_3d_controller_mast(input_path: InputPath) -> bool:
    return input_path is InputPath.INPUT3


def _antenna_pol_setup_required(
    prev_case: "TestCase",
    current_case: "TestCase",
) -> bool:
    if prev_case.antenna_pol != current_case.antenna_pol:
        return True

    prev_uses_3d_mast = _uses_3d_controller_mast(
        prev_case.range_definition.input_path
    )
    current_uses_3d_mast = _uses_3d_controller_mast(
        current_case.range_definition.input_path
    )
    return prev_uses_3d_mast != current_uses_3d_mast


def _transition_states_for(
    prev_case: "TestCase",
    current_case: "TestCase",
) -> list[str]:
    transition_states: list[str] = []

    if prev_case.band != current_case.band:
        prev_recall = find_band_group(prev_case.band).mt8000_recall
        current_recall = find_band_group(current_case.band).mt8000_recall
        if prev_recall != current_recall:
            transition_states.append("RecallChange")
        else:
            transition_states.append("Handover")

    if prev_case.dut_axis != current_case.dut_axis:
        transition_states.append("DUTAxisChange")
    if _antenna_pol_setup_required(prev_case, current_case):
        transition_states.append("AntPolChange")
    if prev_case.test_type != current_case.test_type:
        transition_states.append("TestTypeChange")

    return transition_states


class SessionInitState(State):
    """모든 장비 연결 상태를 확인한다."""

    name = "SessionInit"

    def run(self, ctx: "SessionContext") -> StateResult:
        if not _wait_for_event(ctx, "equipment_connect_requested"):
            return StateResult.FAIL

        if ctx.client is None:
            _emit_error(ctx, "장비 연결 확인 실패: TCP client is not set")
            return StateResult.RETRY

        if not ctx.equipment_state:
            _emit_error(ctx, "장비 연결 확인 실패: equipment_state is empty")
            return StateResult.RETRY

        if not is_selected_equipment_ready(ctx.equipment_state):
            _emit_error(
                ctx,
                "장비 연결 확인 실패: "
                + describe_equipment_not_ready(ctx.equipment_state),
            )
            return StateResult.RETRY

        return StateResult.OK

    def next_state(
        self, ctx: "SessionContext", result: StateResult
    ) -> str | None:
        if result is not StateResult.OK:
            return None
        return "Idle"


class IdleState(State):
    """시험 시작 대기 상태. 사용자가 TC 큐를 구성한 뒤 시험을 시작한다."""

    name = "Idle"

    def run(self, ctx: "SessionContext") -> StateResult:
        if not _wait_for_event(ctx, "test_start_requested"):
            return StateResult.FAIL

        if not ctx.queue:
            _emit_error(ctx, "시험 시작 실패: TestCase queue is empty")
            return StateResult.RETRY
        if ctx.report_writer is None:
            _emit_error(ctx, "시험 시작 실패: report_writer is not set")
            return StateResult.RETRY
        if ctx.temp_dir is None:
            _emit_error(ctx, "시험 시작 실패: temp_dir is not set")
            return StateResult.RETRY
        if ctx.settings is None:
            _emit_error(ctx, "시험 시작 실패: settings is required")
            return StateResult.RETRY
        if not ctx.model_name:
            _emit_error(ctx, "시험 시작 실패: model_name is required")
            return StateResult.RETRY
        if ctx.template_path is None:
            _emit_error(ctx, "시험 시작 실패: template_path is required")
            return StateResult.RETRY
        if ctx.screenshot_root_dir is None:
            _emit_error(ctx, "시험 시작 실패: screenshot_root_dir is required")
            return StateResult.RETRY

        ctx.current_index = ctx.start_index
        ctx.fundamental_frequency_mhz = None
        ctx.pending_transition_states.clear()
        ctx.stopped = False
        ctx.current_case_stop_requested = False
        if ctx.events is not None:
            ctx.events.current_case_changed.emit(ctx.current_case)
            ctx.events.tc_started.emit(ctx.current_index)
        return StateResult.OK

    def next_state(
        self, ctx: "SessionContext", result: StateResult
    ) -> str | None:
        if result is not StateResult.OK:
            return None
        return "InitialTurntableZero"


class CheckNextCaseState(State):
    """다음 TC 정보를 확인하고 적절한 전환 상태로 분기한다."""

    name = "CheckNextCase"

    def __init__(self) -> None:
        self._previous_case = None
        self._advanced = False

    def run(self, ctx: "SessionContext") -> StateResult:
        self._previous_case = ctx.current_case
        self._advanced = False
        ctx.pending_transition_states.clear()
        if ctx.events is not None:
            ctx.events.tc_finished.emit(ctx.current_index)

        if ctx.stop_index is not None and ctx.current_index >= ctx.stop_index:
            return StateResult.OK
        if not ctx.has_next_case:
            return StateResult.OK

        ctx.current_index += 1
        ctx.fundamental_frequency_mhz = None
        self._advanced = True
        if ctx.events is not None:
            ctx.events.current_case_changed.emit(ctx.current_case)
            ctx.events.tc_started.emit(ctx.current_index)
        return StateResult.OK

    def next_state(
        self, ctx: "SessionContext", result: StateResult
    ) -> str | None:
        if result is not StateResult.OK:
            return None
        if not self._advanced:
            return "TestEnd"

        prev_case = self._previous_case
        current_case = ctx.current_case
        if prev_case is None:
            return measurement_start_state_for(current_case.test_type)

        transition_states = _transition_states_for(prev_case, current_case)
        if transition_states:
            ctx.pending_transition_states = transition_states[1:]
            return transition_states[0]
        return measurement_start_state_for(current_case.test_type)


class TestEndState(State):
    """모든 시험이 완료되었음을 알린다. Idle로 복귀."""

    name = "TestEnd"

    def run(self, ctx: "SessionContext") -> StateResult:
        if ctx.events is not None:
            ctx.events.session_finished.emit()
        ctx.queue = []
        ctx.current_index = 0
        ctx.stop_index = None
        ctx.fundamental_frequency_mhz = None
        ctx.pending_transition_states.clear()
        return StateResult.OK

    def next_state(
        self, ctx: "SessionContext", result: StateResult
    ) -> str | None:
        if result is not StateResult.OK:
            return None
        return "Idle"
