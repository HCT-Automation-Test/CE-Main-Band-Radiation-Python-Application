"""FSM State들이 호출하는 고수준 command facade.

본문은 모두 `client.send_request(target, command_name, params)` 호출로 수렴한다.
외부 LabVIEW 프로그램과 합의한 target/command 문자열은 이 모듈 상수로 고정한다.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from app.models.enums import AntennaPol, FilterPath, InputPath, Modulation
from app.models.test_range import TestRange

_TARGET_FSV40 = "FSV40"
_TARGET_MT8000A = "MT8000A"
_TARGET_CO3000 = "CO3000"
_TARGET_SWITCH_BOX = "Switch Box"
_TARGET_3D_CONTROLLER = "3D Controller"

_COMMAND_CONNECT = "Connect"
_COMMAND_LOAD_SA_RANGE_SETTING = "Load SA Range Setting"
_COMMAND_LOAD_SA_LEVEL_SETTING = "Load SA Level Setting"
_COMMAND_SEARCH_FUNDAMENTAL_FREQUENCY = "Search Fundamental Frequency"
_COMMAND_MARK_HARMONIC = "Mark Harmonic"
_COMMAND_NR_CALL = "NR Call"
_COMMAND_NR_HANDOVER = "NR Handover"
_COMMAND_CHECK_CALL_STATUS = "Check Call Status"
_COMMAND_CHANGE_ANT_POL = "Change Ant Pol"
_COMMAND_MOVE_TURNTABLE = "Move TurnTable"
_COMMAND_STOP_TURNTABLE = "Stop TurnTable"
_COMMAND_SET_INPUT = "Set Input"
_COMMAND_SET_FILTER = "Set Filter"
_COMMAND_SET_REFERENCE = "Set Reference"
_COMMAND_SELF_ALIGNMENT = "Self Alignment"

_CONNECT_TARGETS = (
    _TARGET_FSV40,
    _TARGET_MT8000A,
    _TARGET_CO3000,
    _TARGET_SWITCH_BOX,
    _TARGET_3D_CONTROLLER,
)


class CommandError(RuntimeError):
    """외부 프로그램 command 응답 오류."""


@dataclass(frozen=True)
class EquipmentConnectionConfig:
    """장비 연결에 필요한 Python 내부 설정값."""

    fsv40_visa_resource: str
    mt8000a_visa_resource: str
    co3000_visa_resource: str
    controller_3d_visa_resource: str
    switch_box_ip_address: str
    switch_box_port: int


def _normalize_modulation(modulation: Modulation | str) -> str:
    value = modulation.value if isinstance(modulation, Modulation) else str(modulation)
    if value == "pi/2 BPSK":
        return "PI/2 BPSK"
    return value


def _build_mt8000_params(
    *,
    band: int,
    bw: int,
    modulation: Modulation | str,
    rb_size: int,
    rb_offset: int,
    channel: int,
    max_retry_count: int,
    waiting_time: int,
) -> dict[str, Any]:
    return {
        "Band": int(band),
        "BandWidth": int(bw),
        "Center Channel": int(channel),
        "RB Size": int(rb_size),
        "RB Offset": int(rb_offset),
        "Modulation": _normalize_modulation(modulation),
        "Max Retry Count": int(max_retry_count),
        "Waiting Time": int(waiting_time),
    }


def _build_handover_params(
    *,
    mid_channel: int,
    band: int,
    bw: int,
    modulation: Modulation | str,
    rb_size: int,
    rb_offset: int,
    channel: int,
) -> dict[str, Any]:
    return {
        "Mid Channel": int(mid_channel),
        "Band": int(band),
        "BandWidth": int(bw),
        "Center Channel": int(channel),
        "RB Size": int(rb_size),
        "RB Offset": int(rb_offset),
        "Modulation": _normalize_modulation(modulation),
    }


def _build_connect_params(
    config: EquipmentConnectionConfig | None,
    target: str,
) -> dict[str, Any]:
    if config is None:
        return {}
    if target == _TARGET_FSV40:
        return {"VISA Resource": config.fsv40_visa_resource}
    if target == _TARGET_MT8000A:
        return {"VISA Resource": config.mt8000a_visa_resource}
    if target == _TARGET_CO3000:
        return {"VISA Resource": config.co3000_visa_resource}
    if target == _TARGET_SWITCH_BOX:
        return {
            "ip address": config.switch_box_ip_address,
            "port": int(config.switch_box_port),
        }
    if target == _TARGET_3D_CONTROLLER:
        return {"VISA Resource": config.controller_3d_visa_resource}
    return {}


def connect_equipment(
    client: Any,
    *,
    config: EquipmentConnectionConfig | None = None,
) -> dict[str, bool]:
    """LabVIEW 프로그램을 통해 장비 연결/상태 확인을 수행한다."""
    states: dict[str, bool] = {}
    for target in _CONNECT_TARGETS:
        params = _build_connect_params(config, target)
        response = _send_request(client, target, _COMMAND_CONNECT, params)
        states[target] = _action_ok(response, target, _COMMAND_CONNECT)
    return states



def setup_mt8000(
    client: Any,
    *,
    band: int,
    bw: int,
    modulation: Modulation | str,
    rb_size: int,
    rb_offset: int,
    channel: int,
    max_retry_count: int = 3,
    waiting_time: int = 5,
) -> bool:
    """MT8000A 셋업. §4.1.

    SCS는 MT8000A Recall file에 포함되어 자동 설정되므로 인자에 두지 않는다.
    Band 그룹의 scs_khz는 RB Allocation(RB size/offset 산출) 단계의 Python 로직에서만 사용.
    외부 프로그램은 band/bw/channel을 정수 코드로 받는다.
    """
    response = _send_request(
        client,
        _TARGET_MT8000A,
        _COMMAND_NR_CALL,
        _build_mt8000_params(
            band=band,
            bw=bw,
            modulation=modulation,
            rb_size=rb_size,
            rb_offset=rb_offset,
            channel=channel,
            max_retry_count=max_retry_count,
            waiting_time=waiting_time,
        ),
    )
    return _action_ok(response, _TARGET_MT8000A, _COMMAND_NR_CALL)


def call_handover(
    client: Any,
    *,
    mid_channel: int,
    band: int,
    bw: int,
    modulation: Modulation | str,
    rb_size: int,
    rb_offset: int,
    channel: int,
) -> bool:
    """Call Handover 수행."""
    response = _send_request(
        client,
        _TARGET_MT8000A,
        _COMMAND_NR_HANDOVER,
        _build_handover_params(
            mid_channel=mid_channel,
            band=band,
            bw=bw,
            modulation=modulation,
            rb_size=rb_size,
            rb_offset=rb_offset,
            channel=channel,
        ),
    )
    return _action_ok(response, _TARGET_MT8000A, _COMMAND_NR_HANDOVER)


def set_reference_co3000(client: Any) -> bool:
    response = _send_request(client, _TARGET_CO3000, _COMMAND_SET_REFERENCE, {})
    return _action_ok(response, _TARGET_CO3000, _COMMAND_SET_REFERENCE)


def self_align_fsv40(client: Any) -> bool:
    response = _send_request(client, _TARGET_FSV40, _COMMAND_SELF_ALIGNMENT, {})
    return _action_ok(response, _TARGET_FSV40, _COMMAND_SELF_ALIGNMENT)


def measure_fundamental(client: Any, *, target_freq: float) -> float:
    """기본파 측정 후 fundamental frequency를 반환한다. §4.3."""
    response = _send_request(
        client,
        _TARGET_FSV40,
        _COMMAND_SEARCH_FUNDAMENTAL_FREQUENCY,
        {"Center Frequency": float(target_freq)},
    )
    result = _result_dict(
        response,
        _TARGET_FSV40,
        _COMMAND_SEARCH_FUNDAMENTAL_FREQUENCY,
    )
    return _number(
        result,
        "Fundamental Frequency",
        _TARGET_FSV40,
        _COMMAND_SEARCH_FUNDAMENTAL_FREQUENCY,
    )


def set_switch_box(client: Any, *, input_path: InputPath, filter_path: FilterPath) -> bool:
    """Switch Box 경로 설정. §4.4 / §4.8."""
    input_response = _send_request(
        client,
        _TARGET_SWITCH_BOX,
        _COMMAND_SET_INPUT,
        {"Input Path": int(input_path)},
    )
    input_ok = _action_ok(input_response, _TARGET_SWITCH_BOX, _COMMAND_SET_INPUT)
    if not input_ok:
        return False

    filter_response = _send_request(
        client,
        _TARGET_SWITCH_BOX,
        _COMMAND_SET_FILTER,
        {"Filter Path": int(filter_path)},
    )
    return _action_ok(filter_response, _TARGET_SWITCH_BOX, _COMMAND_SET_FILTER)


def setup_sa(client: Any, test_range: TestRange) -> bool:
    """FSV40 Spectrum Analyzer 셋업. §4.5."""
    response = _send_request(
        client,
        _TARGET_FSV40,
        _COMMAND_LOAD_SA_RANGE_SETTING,
        {
            "SA Range Param": {
                "Start Frequency": float(test_range.start_freq),
                "Stop Frequency": float(test_range.stop_freq),
                "RBW": float(test_range.rbw),
                "VBW": float(test_range.vbw),
                "Sweep Point": int(test_range.sweep_point),
                "Limit": float(test_range.limit),
            },
        },
    )
    return _action_ok(response, _TARGET_FSV40, _COMMAND_LOAD_SA_RANGE_SETTING)


def setup_sa_startup_levels(
    client: Any,
    *,
    atten_level_db: float,
    next_peak_search_level_db: float,
) -> bool:
    """시험 시작 전 FSV40 레벨 설정을 1회 적용한다."""
    response = _send_request(
        client,
        _TARGET_FSV40,
        _COMMAND_LOAD_SA_LEVEL_SETTING,
        {
            "SA Level Param": {
                "Atten Level": float(atten_level_db),
                "Next Peak Search Level": float(next_peak_search_level_db),
            },
        },
    )
    return _action_ok(response, _TARGET_FSV40, _COMMAND_LOAD_SA_LEVEL_SETTING)


def rotate_turntable(client: Any, *, angle: float, turntable_speed: int) -> None:
    """CO3000 턴테이블 회전 시작. 완료/진행 상태는 이후 Event로 수신한다. §4.6."""
    response = _send_request(
        client,
        _TARGET_CO3000,
        _COMMAND_MOVE_TURNTABLE,
        {
            "Turn Table Info": {
                "Target Angle": float(angle),
                "Turn Table Speed": int(turntable_speed),
                "Fetch Interval": 10,
            },
        },
    )
    _require_action_ok(response, _TARGET_CO3000, _COMMAND_MOVE_TURNTABLE)


def stop_turntable(client: Any) -> None:
    """CO3000 턴테이블 즉시 정지. UI Stop 처리용. §4.6."""
    response = _send_request(client, _TARGET_CO3000, _COMMAND_STOP_TURNTABLE)
    _require_action_ok(response, _TARGET_CO3000, _COMMAND_STOP_TURNTABLE)


def measure_harmonics(
    client: Any,
    *,
    fundamental: float,
) -> list[float]:
    """2nd~5th harmonic amplitude(dBm) 4개를 순서대로 반환한다. §4.7.

    외부 프로그램은 측정 중 `temp_dir/harmonic.png` 경로에 SA 스크린샷을
    남긴다고 가정한다.
    """
    response = _send_request(
        client,
        _TARGET_FSV40,
        _COMMAND_MARK_HARMONIC,
        {"Fundamental Frequency": float(fundamental)},
    )
    result = _result_dict(response, _TARGET_FSV40, _COMMAND_MARK_HARMONIC)
    levels = result.get("Amplitude")
    if isinstance(levels, str | bytes) or not isinstance(levels, Sequence):
        raise CommandError("FSV40 / Mark Harmonic Result.Amplitude must be a list")

    normalized = [
        _coerce_number(level, _TARGET_FSV40, _COMMAND_MARK_HARMONIC, "Amplitude")
        for level in levels
    ]
    if len(normalized) != 4:
        raise CommandError(
            "FSV40 / Mark Harmonic Result.Amplitude must contain "
            f"4 values, got {len(normalized)}"
        )
    return normalized


def measure_inband(client: Any, **kwargs: Any) -> Any:
    """In-Band 측정."""
    # TODO(spec): 파라미터/반환 스키마 확정 필요
    raise NotImplementedError("spec TODO: send_request command name pending")


def measure_bilog(client: Any, **kwargs: Any) -> Any:
    """Bilog 측정."""
    # TODO(spec): 파라미터/반환 스키마 확정 필요
    raise NotImplementedError("spec TODO: send_request command name pending")


def check_call_status(client: Any) -> bool:
    """현재 NR Call 연결 상태를 확인한다. TestTypeChange 등에서 호출."""
    response = _send_request(client, _TARGET_MT8000A, _COMMAND_CHECK_CALL_STATUS)
    result = _result_dict(response, _TARGET_MT8000A, _COMMAND_CHECK_CALL_STATUS)
    ok = _boolean(result, "ok", _TARGET_MT8000A, _COMMAND_CHECK_CALL_STATUS)
    connected = _boolean(
        result,
        "connected",
        _TARGET_MT8000A,
        _COMMAND_CHECK_CALL_STATUS,
    )
    return ok and connected


def set_antenna_pol(client: Any, *, pol: AntennaPol, input_path: InputPath) -> bool:
    """안테나 편파 전환 (사용자 개입 훅과 연동)."""
    target = (
        _TARGET_3D_CONTROLLER
        if input_path is InputPath.INPUT3
        else _TARGET_CO3000
    )
    response = _send_request(
        client,
        target,
        _COMMAND_CHANGE_ANT_POL,
        {"pol": pol.value},
    )
    return _action_ok(response, target, _COMMAND_CHANGE_ANT_POL)


def _send_request(
    client: Any,
    target: str,
    command: str,
    params: dict[str, Any] | None = None,
) -> Any:
    response = client.send_request(target, command, params or {})
    status = getattr(response, "status", None)
    if status != "ok":
        error = getattr(response, "error", None)
        raise CommandError(f"{target} / {command} failed: {error or status!r}")
    return response


def _result_dict(response: Any, target: str, command: str) -> dict[str, Any]:
    result = getattr(response, "result", None)
    if not isinstance(result, dict):
        raise CommandError(f"{target} / {command} Result must be an object")
    return result


def _action_ok(response: Any, target: str, command: str) -> bool:
    return getattr(response, "status", None) == "ok"


def _require_action_ok(response: Any, target: str, command: str) -> None:
    if not _action_ok(response, target, command):
        raise CommandError(f"{target} / {command} returned ok=false")


def _boolean(result: dict[str, Any], key: str, target: str, command: str) -> bool:
    value = result.get(key)
    if not isinstance(value, bool):
        raise CommandError(f"{target} / {command} Result.{key} must be a bool")
    return value


def _number(
    result: dict[str, Any],
    key: str,
    target: str,
    command: str,
) -> float:
    return _coerce_number(result.get(key), target, command, key)


def _coerce_number(value: Any, target: str, command: str, key: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise CommandError(f"{target} / {command} Result.{key} must be a number")
    return float(value)
