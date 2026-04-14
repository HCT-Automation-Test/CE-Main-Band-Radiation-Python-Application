"""Harmonic 시퀀스 8단계 State (§4)."""
from __future__ import annotations

from app.core.fsm.base import State, StateResult
from app.core.fsm.context import Context


class SetupMT8000State(State):
    """§4.1 — MT8000A에 Band/BW/Modulation/RB Size/Offset/Channel을 세팅한다."""

    name = "SetupMT8000"

    def run(self, ctx: Context) -> StateResult:
        # calls: net.commands.setup_mt8000(client, band=..., bw=..., modulation=..., rb_size=..., rb_offset=..., channel=...)
        raise NotImplementedError("spec TODO")


class CallConnectState(State):
    """§4.2 — Call Connect 수행. 연결 상태를 확인한다."""

    name = "CallConnect"

    def run(self, ctx: Context) -> StateResult:
        # calls: net.commands.call_connect(client)
        raise NotImplementedError("spec TODO")


class MeasureFundamentalState(State):
    """§4.3 — 기본파 주파수를 측정하여 Context.result.fundamental_freq_hz에 저장."""

    name = "MeasureFundamental"

    def run(self, ctx: Context) -> StateResult:
        # calls: net.commands.measure_fundamental(client, target_freq=...)
        raise NotImplementedError("spec TODO")


class SetSwitchBoxState(State):
    """§4.4 — Switch Box의 입력 경로/필터를 Range 프리셋에 맞게 전환한다."""

    name = "SetSwitchBox"

    def run(self, ctx: Context) -> StateResult:
        # calls: net.commands.set_switch_box(client, input_path=..., filter_path=...)
        raise NotImplementedError("spec TODO")


class SetupSpectrumAnalyzerState(State):
    """§4.5 — FSV40에 Range 프리셋(Start/Stop/RBW/VBW/Limit/SweepPoint)을 로드한다."""

    name = "SetupSpectrumAnalyzer"

    def run(self, ctx: Context) -> StateResult:
        # calls: net.commands.setup_sa(client, preset=...)
        raise NotImplementedError("spec TODO")


class RotateTurntableState(State):
    """§4.6 — CO3000 턴테이블을 해당 축/각도로 회전시킨다."""

    name = "RotateTurntable"

    def run(self, ctx: Context) -> StateResult:
        # calls: net.commands.rotate_turntable(client, axis=..., angle=...)
        raise NotImplementedError("spec TODO")


class MeasureHarmonicsState(State):
    """§4.7 — 각 Range에 대해 하모닉 피크를 측정하고 스크린샷을 저장한다."""

    name = "MeasureHarmonics"

    def run(self, ctx: Context) -> StateResult:
        # calls: net.commands.measure_harmonics(client, ranges=..., fundamental=...)
        raise NotImplementedError("spec TODO")


class ResetSwitchBoxState(State):
    """§4.8 — Switch Box를 기본 경로로 복원한다(시퀀스 정리)."""

    name = "ResetSwitchBox"

    def run(self, ctx: Context) -> StateResult:
        # calls: net.commands.set_switch_box(client, input_path=DEFAULT, filter_path=DEFAULT)
        raise NotImplementedError("spec TODO")
