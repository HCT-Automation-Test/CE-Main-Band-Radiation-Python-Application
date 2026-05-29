"""시험 간 전환 상태: AntPolChange, Handover, RecallChange, DUTAxisChange, TestTypeChange."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.core.fsm.base import State, StateResult
from app.core.fsm.equipment import is_equipment_connected
from app.models.band_group import find_band_group
from app.models.enums import AntennaPol, InputPath, TestChannel
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
    if input_path in (InputPath.INPUT1, InputPath.INPUT2):
        signal.emit(
            {
                "polarization_3m": pol_value,
                "polarization_bilog": pol_value,
            }
        )
    elif input_path is InputPath.INPUT3:
        # TODO(spec): 1m Mast angle readback/event 프로토콜 협의 필요.
        # 현재 H -> 90°, V -> 0° 매핑은 표시용 임시값이다.
        angle = "0°" if pol is AntennaPol.V else "90°"
        signal.emit({"polarization_1m": angle})
    else:
        _emit_error(ctx, f"Unknown input path for polarization display: {input_path!r}")


class AntPolChangeState(State):
    """안테나 편파(Ant Pol) 변경 설정을 수행한다.

    설정 성공 시 현재 TC의 측정 시작 state로 전이하고, 설정 실패/예외는
    에러를 발생시킨 뒤 FSM을 종료한다.
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
            return StateResult.OK

        if configured:
            _emit_polarization_info(ctx, pol=pol, input_path=input_path)
            return StateResult.OK

        _emit_error(ctx, "Antenna Pol 설정 실패: set_antenna_pol returned false")
        return StateResult.OK

    def next_state(
        self, ctx: "SessionContext", result: StateResult
    ) -> str | None:
        if result is not StateResult.OK:
            return None
        if ctx.prev_case is None or ctx.current_index == ctx.start_index:
            return "SetupSpectrumAnalyzerStartupLevel"
        return "MeasureFundamental"


class HandoverState(State):
    """NR Band 간 Handover. Call을 유지한 채 Band를 전환한다.

    Handover 성공 시 → MeasureFundamental로 전이
    Handover 실패(Call 끊김) 시 → NRCallDisconnected로 전이
    """

    name = "Handover"

    def run(self, ctx: "SessionContext") -> StateResult:
        if not is_equipment_connected(ctx, "MT8000A"):
            _emit_error(ctx, "NR Handover 스킵: MT8000A가 연결되어 있지 않습니다.")
            return StateResult.OK

        test_case = ctx.current_case
        prev_case = ctx.prev_case
        if prev_case is None:
            _emit_error(ctx, "NR Handover 실패: previous test case is not set")
            return StateResult.OK

        try:
            band = parse_band_number(test_case.band.value)
            bw = int(test_case.bandwidth)
            mid_channel = resolve_call_channel(
                prev_case.band,
                prev_case.bandwidth,
                TestChannel.MID,
            )
            channel = resolve_call_channel(
                test_case.band,
                test_case.bandwidth,
                test_case.test_channel,
            )
            handed_over = ctx.commands.call_handover(
                ctx.client,
                mid_channel=mid_channel,
                band=band,
                bw=bw,
                modulation=test_case.modulation,
                rb_size=test_case.rb_size,
                rb_offset=test_case.rb_offset,
                channel=channel,
            )
        except Exception as exc:
            _emit_error(ctx, f"NR Handover 실패: {exc}")
            return StateResult.OK

        if handed_over:
            return StateResult.OK

        _emit_error(ctx, "NR Handover 실패: call_handover returned false")
        return StateResult.OK

    def next_state(
        self, ctx: "SessionContext", result: StateResult
    ) -> str | None:
        if result is StateResult.OK:
            return "MeasureFundamental"
        if result is StateResult.FAIL:
            return "NRCallDisconnected"
        return None


class RecallChangeState(State):
    """NR 장비 Recall file 변경. 시험원의 수동 조작을 요청한다.

    Band 변경 과정에서 Recall file 교체가 필요한 경우 사용.
    수동 조작 완료 후 NRCallConnect로 전이하여 풀 Setup + 재연결.
    """

    name = "RecallChange"

    def run(self, ctx: "SessionContext") -> StateResult:
        prev_case = ctx.prev_case
        current_case = ctx.current_case
        if prev_case is None:
            _emit_error(ctx, "Recall 변경 실패: previous test case is not set")
            return StateResult.FAIL

        try:
            prev_recall = find_band_group(prev_case.band).mt8000_recall
            current_recall = find_band_group(current_case.band).mt8000_recall
        except ValueError as exc:
            _emit_error(ctx, f"Recall 변경 실패: {exc}")
            return StateResult.FAIL

        ctx.user_action_completed.clear()
        if ctx.events is not None:
            ctx.events.user_action_required.emit(
                f"MT8000A Recall 변경: {prev_recall} -> {current_recall}"
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
        return "NRCallConnect"


class DUTAxisChangeState(State):
    """DUT Axis 변경. 시험원이 DUT의 Position을 전환 후 확인.

    수동 조작 완료 후 NRCallConnect로 전이하여 풀 Setup + 재연결.
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
        return "NRCallConnect"


class TestTypeChangeState(State):
    """같은 Band/AntPol/DUT Axis에서 test_type만 변경된 경우.

    장비 재설정 없이 NR Call 연결 상태만 확인하고, test_type에 맞는
    측정 시작 state로 진입한다.
    - Call 유지 시 → 해당 test_type 측정 시작 state
    - Call 끊김 시 → NRCallDisconnected
    """

    name = "TestTypeChange"

    def run(self, ctx: "SessionContext") -> StateResult:
        if not is_equipment_connected(ctx, "MT8000A"):
            _emit_error(ctx, "NR Call 상태 확인 스킵: MT8000A가 연결되어 있지 않습니다.")
            return StateResult.OK

        try:
            call_connected = ctx.commands.check_call_status(ctx.client)
        except Exception as exc:
            _emit_error(ctx, f"NR Call 상태 확인 실패: {exc}")
            return StateResult.OK

        if call_connected:
            return StateResult.OK

        _emit_error(ctx, "NR Call 끊김 감지: check_call_status returned disconnected")
        return StateResult.FAIL

    def next_state(
        self, ctx: "SessionContext", result: StateResult
    ) -> str | None:
        if result is StateResult.OK:
            return "MeasureFundamental"
        if result is StateResult.FAIL:
            return "NRCallDisconnected"
        return None
