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

if TYPE_CHECKING:
    from app.core.fsm.context import SessionContext

logger = logging.getLogger(__name__)

_WAIT_INTERVAL_SEC = 0.1


def _emit_error(ctx: "SessionContext", message: str) -> None:
    logger.error(message)
    if ctx.events is not None:
        ctx.events.error.emit(message)


def _wait_for_event(ctx: "SessionContext", event_name: str) -> bool:
    event = getattr(ctx, event_name)
    while not ctx.stopped:
        if event.wait(_WAIT_INTERVAL_SEC):
            event.clear()
            return True
    return False


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

        ctx.current_index = 0
        ctx.fundamental_frequency_mhz = None
        ctx.stopped = False
        if ctx.events is not None:
            ctx.events.current_case_changed.emit(ctx.current_case)
            ctx.events.tc_started.emit(ctx.current_index)
        return StateResult.OK

    def next_state(
        self, ctx: "SessionContext", result: StateResult
    ) -> str | None:
        if result is not StateResult.OK:
            return None
        return "AntPolChange"


class CheckNextCaseState(State):
    """다음 TC 정보를 확인하고 적절한 전환 상태로 분기한다."""

    name = "CheckNextCase"

    def __init__(self) -> None:
        self._previous_case = None
        self._advanced = False

    def run(self, ctx: "SessionContext") -> StateResult:
        self._previous_case = ctx.current_case
        self._advanced = False
        if ctx.events is not None:
            ctx.events.tc_finished.emit(ctx.current_index)

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

        # TODO(spec): Band 변경 + Recall 필요 판정 규칙 확정
        if prev_case.band != current_case.band:
            return "Handover"
        if prev_case.dut_axis != current_case.dut_axis:
            return "DUTAxisChange"
        if prev_case.antenna_pol != current_case.antenna_pol:
            return "AntPolChange"
        if prev_case.test_type != current_case.test_type:
            return "TestTypeChange"
        return measurement_start_state_for(current_case.test_type)


class TestEndState(State):
    """모든 시험이 완료되었음을 알린다. Idle로 복귀."""

    name = "TestEnd"

    def run(self, ctx: "SessionContext") -> StateResult:
        ctx.queue = []
        ctx.current_index = 0
        ctx.fundamental_frequency_mhz = None
        return StateResult.OK

    def next_state(
        self, ctx: "SessionContext", result: StateResult
    ) -> str | None:
        if result is not StateResult.OK:
            return None
        return "Idle"
