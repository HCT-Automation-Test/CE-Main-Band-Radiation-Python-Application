"""Harmonic 측정 상태 (기존 §4 기준, SetupMT8000/CallConnect는 NRCallConnect로 통합됨)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.fsm.base import State, StateResult

if TYPE_CHECKING:
    from app.core.fsm.context import SessionContext


class MeasureFundamentalState(State):
    """§4.3 — 기본파 주파수를 측정하여 결과에 저장한다."""

    name = "MeasureFundamental"

    def run(self, ctx: "SessionContext") -> StateResult:
        # calls: net.commands.measure_fundamental(client, target_freq=...)
        raise NotImplementedError("spec TODO")

    def next_state(
        self, ctx: "SessionContext", result: StateResult
    ) -> str | None:
        return "SetSwitchBox"


class SetSwitchBoxState(State):
    """§4.4 — Switch Box의 입력 경로/필터를 TestRange에 맞게 전환한다."""

    name = "SetSwitchBox"

    def run(self, ctx: "SessionContext") -> StateResult:
        # calls: net.commands.set_switch_box(client, input_path=..., filter_path=...)
        raise NotImplementedError("spec TODO")

    def next_state(
        self, ctx: "SessionContext", result: StateResult
    ) -> str | None:
        return "SetupSpectrumAnalyzer"


class SetupSpectrumAnalyzerState(State):
    """§4.5 — FSV40에 TestRange(Start/Stop/RBW/VBW/Limit/SweepPoint)을 로드한다."""

    name = "SetupSpectrumAnalyzer"

    def run(self, ctx: "SessionContext") -> StateResult:
        # calls: net.commands.setup_sa(client, test_range=...)
        raise NotImplementedError("spec TODO")

    def next_state(
        self, ctx: "SessionContext", result: StateResult
    ) -> str | None:
        return "RotateTurntable"


class RotateTurntableState(State):
    """§4.6 — CO3000 턴테이블을 해당 축/각도로 회전시킨다."""

    name = "RotateTurntable"

    def run(self, ctx: "SessionContext") -> StateResult:
        # calls: net.commands.rotate_turntable(client, axis=..., angle=..., turntable_speed=...)
        raise NotImplementedError("spec TODO")

    def next_state(
        self, ctx: "SessionContext", result: StateResult
    ) -> str | None:
        return "MeasureHarmonics"


class MeasureHarmonicsState(State):
    """§4.7 — 각 Range에 대해 하모닉 피크를 측정하고 스크린샷을 저장한다."""

    name = "MeasureHarmonics"

    def run(self, ctx: "SessionContext") -> StateResult:
        # calls: net.commands.measure_harmonics(client, fundamental=...)
        raise NotImplementedError("spec TODO")

    def next_state(
        self, ctx: "SessionContext", result: StateResult
    ) -> str | None:
        return "ResetSwitchBox"


class ResetSwitchBoxState(State):
    """§4.8 — Switch Box를 기본 경로로 복원한다(시퀀스 정리)."""

    name = "ResetSwitchBox"

    def run(self, ctx: "SessionContext") -> StateResult:
        # calls: net.commands.set_switch_box(client, input_path=DEFAULT, filter_path=DEFAULT)
        raise NotImplementedError("spec TODO")

    def next_state(
        self, ctx: "SessionContext", result: StateResult
    ) -> str | None:
        return "CheckNextCase"
