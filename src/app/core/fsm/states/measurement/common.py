"""3타입 공통 측정 스텝 (Switch Box / SA / Turntable / Reset).

Harmonic, InBand, Bilog 측정 모두가 공유하는 장비 조작 스텝.
- SetSwitchBox → SetupSpectrumAnalyzer → RotateTurntable까지는 동일 경로.
- RotateTurntable에서 test_type에 따라 Measure(Harmonics|InBand|Bilog)로 분기.
- Measure 이후 ResetSwitchBox → CheckNextCase로 복귀.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.fsm.base import State, StateResult
from app.models.enums import TestType

if TYPE_CHECKING:
    from app.core.fsm.context import SessionContext


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
        return measurement_start_state_for(ctx.current_case.test_type, after_rotate=True)


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


def measurement_start_state_for(
    test_type: TestType, *, after_rotate: bool = False
) -> str:
    """test_type에 해당하는 측정 시작 state 이름을 반환한다.

    - after_rotate=False (기본): NRCallConnect / TestTypeChange 등에서 측정 시퀀스로 진입할 때.
      Harmonic은 MeasureFundamental부터 시작, InBand/Bilog는 공유 SetSwitchBox부터 시작.
    - after_rotate=True: RotateTurntable 이후 실제 측정 state로 분기할 때.
    """
    if after_rotate:
        mapping = {
            TestType.HARMONIC: "MeasureHarmonics",
            TestType.INBAND: "MeasureInBand",
            TestType.BILOG: "MeasureBilog",
        }
    else:
        mapping = {
            TestType.HARMONIC: "MeasureFundamental",
            TestType.INBAND: "SetSwitchBox",
            TestType.BILOG: "SetSwitchBox",
        }
    try:
        return mapping[test_type]
    except KeyError as exc:
        raise ValueError(f"unknown test_type: {test_type!r}") from exc
