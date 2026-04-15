"""FSM State들이 호출하는 고수준 command facade.

본문은 모두 `client.send_request(op_name, params)` 호출로 수렴.
op 이름과 반환 스키마는 명세 확정 후 확정한다.
"""
from __future__ import annotations

from typing import Any

from app.models.enums import AntennaPol, DUTAxis, FilterPath, InputPath, Modulation
from app.models.test_range import TestRange


def setup_mt8000(
    client: Any,
    *,
    band: str,
    bw: str,
    modulation: Modulation,
    rb_size: int,
    rb_offset: int,
    channel: str,
) -> None:
    """MT8000A 셋업. §4.1.

    SCS는 MT8000A Recall file에 포함되어 자동 설정되므로 인자에 두지 않는다.
    Band 그룹의 scs_khz는 RB Allocation(RB size/offset 산출) 단계의 Python 로직에서만 사용.
    """
    raise NotImplementedError("spec TODO: send_request op name pending")


def call_connect(client: Any) -> dict[str, Any]:
    """Call Connect 수행. §4.2."""
    raise NotImplementedError("spec TODO: send_request op name pending")


def measure_fundamental(client: Any, *, target_freq: float) -> dict[str, Any]:
    """기본파 측정. §4.3."""
    raise NotImplementedError("spec TODO: send_request op name pending")


def set_switch_box(client: Any, *, input_path: InputPath, filter_path: FilterPath) -> None:
    """Switch Box 경로 설정. §4.4 / §4.8."""
    raise NotImplementedError("spec TODO: send_request op name pending")


def setup_sa(client: Any, test_range: TestRange) -> None:
    """FSV40 Spectrum Analyzer 셋업. §4.5."""
    raise NotImplementedError("spec TODO: send_request op name pending")


def rotate_turntable(client: Any, *, axis: DUTAxis, angle: float) -> None:
    """CO3000 턴테이블 회전. §4.6."""
    raise NotImplementedError("spec TODO: send_request op name pending")


def set_turntable_speed(client: Any, *, speed: int) -> None:
    """CO3000 턴테이블 회전 속도 설정 (Band 그룹 공통 설정)."""
    raise NotImplementedError("spec TODO: send_request op name pending")


def measure_harmonics(
    client: Any,
    *,
    ranges: list[TestRange],
    fundamental: float,
) -> dict[str, Any]:
    """하모닉 피크 측정. §4.7."""
    raise NotImplementedError("spec TODO: send_request op name pending")


def set_antenna_pol(client: Any, *, pol: AntennaPol) -> None:
    """안테나 편파 전환 (사용자 개입 훅과 연동)."""
    raise NotImplementedError("spec TODO: send_request op name pending")
