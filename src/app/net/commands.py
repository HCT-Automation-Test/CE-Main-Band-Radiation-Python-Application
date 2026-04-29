"""FSM State들이 호출하는 고수준 command facade.

본문은 모두 `client.send_request(op_name, params)` 호출로 수렴.
op 이름과 반환 스키마는 명세 확정 후 확정한다.
"""
from __future__ import annotations

from typing import Any

from app.models.enums import AntennaPol, FilterPath, InputPath, Modulation
from app.models.test_range import TestRange


def connect_equipment(client: Any) -> bool:
    """LabVIEW 프로그램을 통해 장비 연결/상태 확인을 수행한다."""
    # TODO(spec): 장비별 연결 응답 스키마 확정 필요
    raise NotImplementedError("spec TODO: send_request op name pending")


def setup_mt8000(
    client: Any,
    *,
    band: int,
    bw: int,
    modulation: Modulation,
    rb_size: int,
    rb_offset: int,
    channel: int,
) -> bool:
    """MT8000A 셋업. §4.1.

    SCS는 MT8000A Recall file에 포함되어 자동 설정되므로 인자에 두지 않는다.
    Band 그룹의 scs_khz는 RB Allocation(RB size/offset 산출) 단계의 Python 로직에서만 사용.
    외부 프로그램은 band/bw/channel을 정수 코드로 받는다.
    """
    raise NotImplementedError("spec TODO: send_request op name pending")


def call_connect(client: Any) -> bool:
    """Call Connect 수행. §4.2."""
    raise NotImplementedError("spec TODO: send_request op name pending")


def measure_fundamental(client: Any, *, target_freq: float) -> float:
    """기본파 측정 후 fundamental frequency를 반환한다. §4.3."""
    raise NotImplementedError("spec TODO: send_request op name pending")


def set_switch_box(client: Any, *, input_path: InputPath, filter_path: FilterPath) -> bool:
    """Switch Box 경로 설정. §4.4 / §4.8."""
    raise NotImplementedError("spec TODO: send_request op name pending")


def setup_sa(client: Any, test_range: TestRange) -> bool:
    """FSV40 Spectrum Analyzer 셋업. §4.5."""
    raise NotImplementedError("spec TODO: send_request op name pending")


def rotate_turntable(client: Any, *, angle: float, turntable_speed: int) -> None:
    """CO3000 턴테이블 회전 시작. 완료/진행 상태는 이후 Event로 수신한다. §4.6."""
    raise NotImplementedError("spec TODO: send_request op name pending")


def stop_turntable(client: Any) -> None:
    """CO3000 턴테이블 즉시 정지. UI Stop 처리용. §4.6."""
    raise NotImplementedError("spec TODO: send_request op name pending")


def measure_harmonics(
    client: Any,
    *,
    fundamental: float,
) -> list[float]:
    """2nd~5th harmonic amplitude(dBm) 4개를 순서대로 반환한다. §4.7.

    외부 프로그램은 측정 중 `temp_dir/harmonic.png` 경로에 SA 스크린샷을
    남긴다고 가정한다.
    """
    raise NotImplementedError("spec TODO: send_request op name pending")


def measure_inband(client: Any, **kwargs: Any) -> Any:
    """In-Band 측정."""
    # TODO(spec): 파라미터/반환 스키마 확정 필요
    raise NotImplementedError("spec TODO: send_request op name pending")


def measure_bilog(client: Any, **kwargs: Any) -> Any:
    """Bilog 측정."""
    # TODO(spec): 파라미터/반환 스키마 확정 필요
    raise NotImplementedError("spec TODO: send_request op name pending")


def check_call_status(client: Any) -> bool:
    """현재 NR Call 연결 상태를 확인한다. TestTypeChange 등에서 호출."""
    raise NotImplementedError("spec TODO: send_request op name pending")


def set_antenna_pol(client: Any, *, pol: AntennaPol) -> bool:
    """안테나 편파 전환 (사용자 개입 훅과 연동)."""
    raise NotImplementedError("spec TODO: send_request op name pending")
