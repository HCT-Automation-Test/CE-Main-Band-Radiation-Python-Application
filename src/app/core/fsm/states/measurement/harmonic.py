"""Harmonic 전용 측정 상태.

공유 스텝(SetSwitchBox / SetupSpectrumAnalyzer / RotateTurntable / ResetSwitchBox)은
`measurement.common`으로 분리되었다.
"""
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
