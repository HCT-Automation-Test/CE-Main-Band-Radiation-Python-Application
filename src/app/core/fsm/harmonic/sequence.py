"""Harmonic 시퀀스 State 순서 정의."""
from __future__ import annotations

from app.core.fsm.base import State
from app.core.fsm.harmonic.states import (
    CallConnectState,
    MeasureFundamentalState,
    MeasureHarmonicsState,
    ResetSwitchBoxState,
    RotateTurntableState,
    SetSwitchBoxState,
    SetupMT8000State,
    SetupSpectrumAnalyzerState,
)


class HarmonicSequence:
    """Harmonic 시퀀스. §4의 8단계를 순차 실행."""

    STATES: list[type[State]] = [
        SetupMT8000State,
        CallConnectState,
        MeasureFundamentalState,
        SetSwitchBoxState,
        SetupSpectrumAnalyzerState,
        RotateTurntableState,
        MeasureHarmonicsState,
        ResetSwitchBoxState,
    ]

    def states(self) -> list[State]:
        return [cls() for cls in self.STATES]
