"""시험 간 전환 상태: 편파, Handover, Recall, DUT Axis, TestType 변경."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.core.fsm.base import State, StateResult
from app.core.fsm.call_routing import (
    call_disconnected_state_for,
    call_entry_state_for,
)
from app.core.fsm.equipment import is_equipment_connected
from app.core.fsm.transition_flow import next_transition_or
from app.models.enums import AntennaPol, Generation, InputPath
from app.models.lte_channel_lookup import resolve_dl_channel
from app.models.nsa_anchor import resolve_nsa_anchor_channels
from app.models.nr_channel_lookup import resolve_call_channel
from app.models.switch_box import parse_band_number

if TYPE_CHECKING:
    from app.core.fsm.context import SessionContext

logger = logging.getLogger(__name__)
_USER_ACTION_WAIT_INTERVAL_SEC = 0.1


def _emit_error(ctx: "SessionContext", message: str) -> None:
    logger.error(message)
    if ctx.events is not None:
        ctx.events.error.emit(message)


def _emit_polarization_info(
    ctx: "SessionContext",
    *,
    pol: AntennaPol,
    input_path: InputPath,
) -> None:
    if ctx.events is None:
        return
    signal = getattr(ctx.events, "polarization_info_changed", None)
    if signal is None:
        return

    pol_value = pol.value
    if input_path is InputPath.INPUT1:
        signal.emit({"polarization_bilog": pol_value})
    elif input_path is InputPath.INPUT2:
        signal.emit({"polarization_3m": pol_value})
    elif input_path is InputPath.INPUT3:
        # TODO(spec): 1m Mast angle readback/event 프로토콜 협의 필요.
        # 현재 H -> 90°, V -> 0° 매핑은 표시용 임시값이다.
        angle = "0°" if pol is AntennaPol.V else "90°"
        signal.emit({"polarization_1m": angle})
    else:
        _emit_error(ctx, f"Unknown input path for polarization display: {input_path!r}")


class AntPolChangeState(State):
    """안테나 편파(Ant Pol) 변경 설정을 수행한다.

    설정 성공 시 남은 전환과 TDF 적용을 거쳐 측정으로 진입하고,
    설정 실패/예외는 에러를 발생시킨 뒤 FSM을 종료한다.
    """

    name = "AntPolChange"

    def run(self, ctx: "SessionContext") -> StateResult:
        # TODO(spec): 편파 변경 후 사용자 확인/장비 응답 순서 확정 필요.
        test_case = ctx.current_case
        input_path = test_case.range_definition.input_path
        pol = test_case.antenna_pol
        required_equipment = (
            "3D Controller" if input_path is InputPath.INPUT3 else "CO3000"
        )
        if not is_equipment_connected(ctx, required_equipment):
            _emit_error(
                ctx,
                f"Antenna Pol 설정 스킵: {required_equipment}가 연결되어 있지 않습니다.",
            )
            return StateResult.OK

        try:
            configured = ctx.commands.set_antenna_pol(
                ctx.client,
                pol=pol,
                input_path=input_path,
            )
        except Exception as exc:
            _emit_error(ctx, f"Antenna Pol 설정 실패: {exc}")
            return StateResult.FAIL

        if configured:
            _emit_polarization_info(ctx, pol=pol, input_path=input_path)
            return StateResult.OK

        _emit_error(ctx, "Antenna Pol 설정 실패: set_antenna_pol returned false")
        return StateResult.FAIL

    def next_state(
        self, ctx: "SessionContext", result: StateResult
    ) -> str | None:
        if result is not StateResult.OK:
            return None
        if ctx.prev_case is None or ctx.current_index == ctx.start_index:
            return "SetupSpectrumAnalyzerStartupLevel"
        return next_transition_or(ctx, "ApplyTdf")


class HandoverState(State):
    """NR Band 간 Handover. Call을 유지한 채 Band를 전환한다.

    Handover 성공 시 → 남은 전환 및 TDF 적용으로 전이
    Handover 실패(Call 끊김) 시 → NRCallDisconnected로 전이
    """

    name = "Handover"

    def run(self, ctx: "SessionContext") -> StateResult:
        if not is_equipment_connected(ctx, "MT8000A"):
            _emit_error(ctx, "NR Handover 스킵: MT8000A가 연결되어 있지 않습니다.")
            return StateResult.FAIL

        test_case = ctx.current_case
        prev_case = ctx.prev_case
        if prev_case is None:
            _emit_error(ctx, "NR Handover 실패: previous test case is not set")
            return StateResult.FAIL

        waiting_time = 5
        if ctx.settings is not None:
            waiting_time = ctx.settings.connection_waiting_time_sec

        try:
            band = parse_band_number(test_case.band.value)
            bw = int(test_case.bandwidth)
            channel = resolve_call_channel(
                test_case.band,
                test_case.bandwidth,
                test_case.test_channel,
            )
            handed_over = ctx.commands.call_handover(
                ctx.client,
                band=band,
                bw=bw,
                modulation=test_case.modulation,
                rb_size=test_case.rb_size,
                rb_offset=test_case.rb_offset,
                channel=channel,
                waiting_time=waiting_time,
            )
        except Exception as exc:
            _emit_error(ctx, f"NR Handover 실패: {exc}")
            return StateResult.FAIL

        if handed_over:
            return StateResult.OK

        _emit_error(ctx, "NR Handover 실패: call_handover returned false")
        return StateResult.FAIL

    def next_state(
        self, ctx: "SessionContext", result: StateResult
    ) -> str | None:
        if result is StateResult.OK:
            return next_transition_or(ctx, "ApplyTdf")
        if result is StateResult.FAIL:
            return "NRCallDisconnected"
        return None


class NSAHandoverState(State):
    """LTE Anchor Band 변경과 목표 NR 설정을 단일 composite로 적용한다."""

    name = "NSAHandover"

    def run(self, ctx: "SessionContext") -> StateResult:
        if not is_equipment_connected(ctx, "MT8000A"):
            _emit_error(ctx, "NSA Handover 스킵: MT8000A가 연결되어 있지 않습니다.")
            return StateResult.FAIL

        test_case = ctx.current_case
        prev_case = ctx.prev_case
        if prev_case is None:
            _emit_error(ctx, "NSA Handover 실패: previous test case is not set")
            return StateResult.FAIL
        if (
            prev_case.generation is not Generation.NR_NSA
            or test_case.generation is not Generation.NR_NSA
        ):
            _emit_error(ctx, "NSA Handover 실패: NR_NSA test cases are required")
            return StateResult.FAIL
        if prev_case.anchor_band == test_case.anchor_band:
            _emit_error(ctx, "NSA Handover 실패: anchor_band is unchanged")
            return StateResult.FAIL

        waiting_time = 5
        if ctx.settings is not None:
            waiting_time = ctx.settings.connection_waiting_time_sec

        try:
            band = parse_band_number(test_case.band.value)
            bw = int(test_case.bandwidth)
            channel = resolve_call_channel(
                test_case.band,
                test_case.bandwidth,
                test_case.test_channel,
            )
            if test_case.anchor_band is None:
                raise ValueError("NR_NSA requires anchor_band")
            anchor_channels = resolve_nsa_anchor_channels(test_case.anchor_band)
            handed_over = ctx.commands.nsa_handover(
                ctx.client,
                band=band,
                bw=bw,
                modulation=test_case.modulation,
                rb_size=test_case.rb_size,
                rb_offset=test_case.rb_offset,
                channel=channel,
                anchor_ul_channel=anchor_channels.ul_channel,
                waiting_time=waiting_time,
            )
        except Exception as exc:
            _emit_error(ctx, f"NSA Handover 실패: {exc}")
            return StateResult.FAIL

        if handed_over:
            return StateResult.OK

        _emit_error(ctx, "NSA Handover 실패: nsa_handover returned false")
        return StateResult.FAIL

    def next_state(
        self, ctx: "SessionContext", result: StateResult
    ) -> str | None:
        if result is StateResult.OK:
            return next_transition_or(ctx, "ApplyTdf")
        if result is StateResult.FAIL:
            return "NRCallDisconnected"
        return None


class LTEHandoverState(State):
    """같은 LTE Recall 내에서 현재 Band 설정으로 Handover한다."""

    name = "LTEHandover"

    def run(self, ctx: "SessionContext") -> StateResult:
        if not is_equipment_connected(ctx, "MT8000A"):
            _emit_error(ctx, "LTE Handover 스킵: MT8000A가 연결되어 있지 않습니다.")
            return StateResult.FAIL

        test_case = ctx.current_case
        prev_case = ctx.prev_case
        if prev_case is None:
            _emit_error(ctx, "LTE Handover 실패: previous test case is not set")
            return StateResult.FAIL

        waiting_time = 5
        if ctx.settings is not None:
            waiting_time = ctx.settings.connection_waiting_time_sec

        try:
            dl_channel = resolve_dl_channel(
                test_case.band,
                test_case.bandwidth,
                test_case.test_channel,
            )
            handed_over = ctx.commands.lte_call_handover(
                ctx.client,
                bw=test_case.bandwidth,
                dl_channel=dl_channel,
                ul_channel=test_case.channel_number,
                rb_offset=test_case.rb_offset,
                waiting_time=waiting_time,
            )
        except Exception as exc:
            _emit_error(ctx, f"LTE Handover 실패: {exc}")
            return StateResult.FAIL

        if handed_over:
            return StateResult.OK

        _emit_error(ctx, "LTE Handover 실패: lte_call_handover returned false")
        return StateResult.FAIL

    def next_state(
        self, ctx: "SessionContext", result: StateResult
    ) -> str | None:
        if result is StateResult.OK:
            return next_transition_or(ctx, "ApplyTdf")
        if result is StateResult.FAIL:
            return "LTECallDisconnected"
        return None


class RecallChangeState(State):
    """LV에 Recall 적용과 Call 재연결 확인을 요청한다."""

    name = "RecallChange"

    def __init__(self) -> None:
        self._call_disconnected = False

    def run(self, ctx: "SessionContext") -> StateResult:
        self._call_disconnected = False
        if not is_equipment_connected(ctx, "MT8000A"):
            _emit_error(ctx, "Recall 변경 실패: MT8000A가 연결되어 있지 않습니다.")
            return StateResult.FAIL

        recall_id = ctx.current_case.mt8000_recall
        try:
            recalled = ctx.commands.recall_param(
                ctx.client,
                recall_name=recall_id,
            )
        except Exception as exc:
            _emit_error(ctx, f"Recall 변경 실패: {exc}")
            return StateResult.FAIL

        ctx.last_applied_recall_id = recall_id
        if not recalled:
            self._call_disconnected = True
            call_connect_state = call_entry_state_for(ctx)
            if (
                ctx.pending_transition_states
                and ctx.pending_transition_states[0] == call_connect_state
            ):
                ctx.pop_pending_transition_state()
        return StateResult.OK

    def next_state(
        self, ctx: "SessionContext", result: StateResult
    ) -> str | None:
        if result is not StateResult.OK:
            return None
        if self._call_disconnected:
            return call_disconnected_state_for(ctx)
        return next_transition_or(ctx, "ApplyTdf")


class DUTAxisChangeState(State):
    """DUT Axis 변경. 시험원이 DUT의 Position을 전환 후 확인.

    수동 조작 완료 후 현재 Generation의 Call 상태로 전이하여 재연결한다.
    """

    name = "DUTAxisChange"

    def run(self, ctx: "SessionContext") -> StateResult:
        # calls: ctx.events.user_action_required.emit("DUT Axis 변경: X → Y")
        # TODO(spec): 사용자 확인 대기
        prev_axis = ctx.prev_case.dut_axis.value
        current_axis = ctx.current_case.dut_axis.value
        ctx.user_action_completed.clear()

        if ctx.events is not None:
            ctx.events.user_action_required.emit(
                f"DUT Axis 변경: {prev_axis} -> {current_axis}"
            )

        while not ctx.stopped and not ctx.current_case_stop_requested:
            if ctx.user_action_completed.wait(_USER_ACTION_WAIT_INTERVAL_SEC):
                if ctx.stopped or ctx.current_case_stop_requested:
                    return StateResult.FAIL
                ctx.user_action_completed.clear()
                return StateResult.OK

        return StateResult.FAIL

    def next_state(
        self, ctx: "SessionContext", result: StateResult
    ) -> str | None:
        if result is not StateResult.OK:
            return None
        return call_entry_state_for(ctx)


class CallCheckState(State):
    """시험 간 전환의 마지막에 현재 Call 연결 상태를 확인한다.

    Ant Pol 설정 또는 Test Type 변경 후 장비 재설정 없이 Call 연결 상태만
    확인한 뒤 TDF 적용을 거쳐 현재 Test Type의 측정 시작 state로 진입한다.
    - Call 유지 시 → TDF 적용 state
    - Call 끊김 시 → Generation별 CallDisconnected
    """

    name = "CallCheck"

    def run(self, ctx: "SessionContext") -> StateResult:
        generation_label = (
            "LTE" if ctx.current_case.generation is Generation.LTE else "NR"
        )
        if not is_equipment_connected(ctx, "MT8000A"):
            _emit_error(
                ctx,
                f"{generation_label} Call 상태 확인 스킵: "
                "MT8000A가 연결되어 있지 않습니다.",
            )
            return StateResult.FAIL

        try:
            call_connected = ctx.commands.check_call_status(ctx.client)
        except Exception as exc:
            _emit_error(ctx, f"{generation_label} Call 상태 확인 실패: {exc}")
            return StateResult.FAIL

        if call_connected:
            return StateResult.OK

        _emit_error(
            ctx,
            f"{generation_label} Call 끊김 감지: "
            "check_call_status returned disconnected",
        )
        return StateResult.FAIL

    def next_state(
        self, ctx: "SessionContext", result: StateResult
    ) -> str | None:
        if result is StateResult.OK:
            return next_transition_or(ctx, "ApplyTdf")
        if result is StateResult.FAIL:
            return call_disconnected_state_for(ctx)
        return None
