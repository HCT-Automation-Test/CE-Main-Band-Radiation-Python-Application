"""FSM State들이 호출하는 고수준 command facade.

본문은 모두 `client.send_request(target, command_name, params)` 호출로 수렴한다.
외부 LabVIEW 프로그램과 합의한 target/command 문자열은 이 모듈 상수로 고정한다.
"""
from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from app.models.enums import AntennaPol, FilterPath, InputPath, Modulation
from app.models.measurement_result import HarmonicMarker
from app.models.test_range import TestRange

_TARGET_FSV40 = "FSV40"
_TARGET_MT8000A = "MT8000A"
_TARGET_CO3000 = "CO3000"
_TARGET_SWITCH_BOX = "Switch Box"
_TARGET_3D_CONTROLLER = "3D Controller"

_COMMAND_CONNECT = "Connect"
_COMMAND_LOAD_SA_RANGE_SETTING = "Load SA Range Setting"
_COMMAND_LOAD_SA_LEVEL_SETTING = "Load SA Level Setting"
_COMMAND_LOAD_SA_PRECISION_SETTING = "Load SA Precision Setting"
_COMMAND_LOAD_SA_MANUAL_SETTING = "Load SA Manual Setting"
_COMMAND_PRESET = "Preset"
_COMMAND_SEARCH_FUNDAMENTAL_FREQUENCY = "Search Fundamental Frequency"
_COMMAND_MARK_HARMONIC = "Mark Harmonic"
_COMMAND_MEASURE_HARMONIC = "Measure Harmonic"
_COMMAND_MARK_HARMONIC_PRECISION = "Mark Precision"
_COMMAND_MARK_INBAND = "Mark Inband"
_COMMAND_MEASURE_INBAND = "Measure Inband"
_COMMAND_GET_SCREENSHOT = "Get Screenshot"
_COMMAND_MARKER_PEAK = "Marker Peak"
_COMMAND_MARKER_NEXT = "Marker Next"
_COMMAND_MARKER_OFF = "Marker OFF"
_COMMAND_MARKER_ALL_OFF = "Marker ALL OFF"
_COMMAND_MARKER_AUTO_MAX = "Marker Auto Max"
_COMMAND_MARKER_SET_CENTER = "Marker set Center"
_COMMAND_CLEAR_TRACE = "Clear Trace"
_COMMAND_NR_CALL = "NR Call"
_COMMAND_NR_HANDOVER = "NR Handover"
_COMMAND_NSA_CALL = "NSA Call"
_COMMAND_NSA_HANDOVER = "NSA Handover"
_COMMAND_LTE_CALL = "LTE Call"
_COMMAND_LTE_HANDOVER = "LTE Handover"
_COMMAND_RECALL_PARAM = "Recall Param"
_COMMAND_CHECK_CALL_STATUS = "Check Call Status"
_COMMAND_CHANGE_ANT_POL = "Change Ant Pol"
_COMMAND_MOVE_TURNTABLE = "Move TurnTable"
_COMMAND_STOP_TURNTABLE = "Stop TurnTable"
_COMMAND_GET_TURNTABLE_ANGLE = "Get TurnTable Angle"
_COMMAND_SET_INPUT = "Set Input"
_COMMAND_SET_FILTER = "Set Filter"
_COMMAND_SET_PATH = "Set Path"
_COMMAND_SET_REFERENCE = "Set Reference"
_COMMAND_SELF_ALIGNMENT = "Self Alignment"
_COMMAND_GET_TDF_LIST = "Get TDF List"
_COMMAND_TDF_ALL_OFF = "TDF All Off"
_COMMAND_SET_TDF = "Set TDF"

_HZ_PER_MHZ = 1_000_000.0
_LTE_BANDWIDTH_WIRE_VALUES = {
    1.4: "1.4",
    3.0: "3",
    5.0: "5",
    10.0: "10",
    15.0: "15",
    20.0: "20",
}
_MANUAL_DETECTOR_MODES = frozenset(
    {
        "Auto Peak",
        "Positive Peak",
        "Negative Peak",
        "Sample",
        "RMS",
        "Average",
        "Quasipeak",
        "CISPR Average",
        "RMS Average",
    }
)

_CONNECT_TARGETS = (
    _TARGET_FSV40,
    _TARGET_MT8000A,
    _TARGET_CO3000,
    _TARGET_SWITCH_BOX,
    _TARGET_3D_CONTROLLER,
)
_CO3000_MAST_INDEX_BY_INPUT_PATH = {
    InputPath.INPUT1: 2,
    InputPath.INPUT2: 1,
}


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
    switch_box_port: int | None


def _normalize_modulation(modulation: Modulation | str) -> str:
    value = modulation.value if isinstance(modulation, Modulation) else str(modulation)
    if value == "pi/2 BPSK":
        return "PI/2 BPSK"
    return value


def _normalize_lte_bandwidth(bw: int | float) -> str:
    """LTE bandwidth를 LabVIEW enum 변환용 문자열로 정규화한다."""
    if isinstance(bw, bool) or not isinstance(bw, int | float):
        raise ValueError(f"Invalid LTE bandwidth: {bw!r}")

    normalized = float(bw)
    if not math.isfinite(normalized):
        raise ValueError(f"Invalid LTE bandwidth: {bw!r}")

    try:
        return _LTE_BANDWIDTH_WIRE_VALUES[normalized]
    except KeyError as exc:
        supported = ", ".join(_LTE_BANDWIDTH_WIRE_VALUES.values())
        raise ValueError(
            f"Unsupported LTE bandwidth: {bw!r}. Supported bandwidths: {supported}"
        ) from exc


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


def _build_nsa_handover_params(
    *,
    band: int,
    bw: int,
    modulation: Modulation | str,
    rb_size: int,
    rb_offset: int,
    channel: int,
    anchor_ul_channel: int,
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
        "Anchor UL Channel": int(anchor_ul_channel),
        "Max Retry Count": int(max_retry_count),
        "Waiting Time": int(waiting_time),
    }


def _build_lte_call_params(
    *,
    bw: int | float,
    ul_channel: int,
    rb_offset: int,
    max_retry_count: int,
    waiting_time: int,
) -> dict[str, Any]:
    return {
        "BandWidth": _normalize_lte_bandwidth(bw),
        "UL Channel": int(ul_channel),
        "RB Offset": int(rb_offset),
        "Max Retry Count": int(max_retry_count),
        "Waiting Time": int(waiting_time),
    }


def _build_lte_handover_params(
    *,
    bw: int | float,
    dl_channel: int,
    ul_channel: int,
    rb_offset: int,
    max_retry_count: int,
    waiting_time: int,
) -> dict[str, Any]:
    return {
        "BandWidth": _normalize_lte_bandwidth(bw),
        "DL Channel": int(dl_channel),
        "UL Channel": int(ul_channel),
        "RB Offset": int(rb_offset),
        "Max Retry Count": int(max_retry_count),
        "Waiting Time": int(waiting_time),
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


def _selected_connect_targets(
    config: EquipmentConnectionConfig | None,
) -> tuple[str, ...]:
    if config is None:
        return _CONNECT_TARGETS

    targets: list[str] = []
    if config.fsv40_visa_resource.strip():
        targets.append(_TARGET_FSV40)
    if config.mt8000a_visa_resource.strip():
        targets.append(_TARGET_MT8000A)
    if config.co3000_visa_resource.strip():
        targets.append(_TARGET_CO3000)
    if config.switch_box_ip_address.strip() and config.switch_box_port is not None:
        targets.append(_TARGET_SWITCH_BOX)
    if config.controller_3d_visa_resource.strip():
        targets.append(_TARGET_3D_CONTROLLER)
    return tuple(targets)


def connect_equipment(
    client: Any,
    *,
    config: EquipmentConnectionConfig | None = None,
) -> dict[str, bool]:
    """LabVIEW 프로그램을 통해 장비 연결/상태 확인을 수행한다."""
    states: dict[str, bool] = {}
    for target in _selected_connect_targets(config):
        params = _build_connect_params(config, target)
        response = client.send_request(target, _COMMAND_CONNECT, params)
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


def setup_lte_mt8000(
    client: Any,
    *,
    bw: int | float,
    ul_channel: int,
    rb_offset: int,
    max_retry_count: int = 3,
    waiting_time: int = 5,
) -> bool:
    """현재 Recall 설정을 사용해 MT8000A LTE Call을 시작한다."""
    response = _send_request(
        client,
        _TARGET_MT8000A,
        _COMMAND_LTE_CALL,
        _build_lte_call_params(
            bw=bw,
            ul_channel=ul_channel,
            rb_offset=rb_offset,
            max_retry_count=max_retry_count,
            waiting_time=waiting_time,
        ),
    )
    return _action_ok(response, _TARGET_MT8000A, _COMMAND_LTE_CALL)


def setup_nsa_mt8000(
    client: Any,
    *,
    band: int,
    bw: int,
    modulation: Modulation | str,
    rb_size: int,
    rb_offset: int,
    channel: int,
    anchor_ul_channel: int,
    max_retry_count: int = 3,
    waiting_time: int = 5,
) -> bool:
    """LTE Anchor와 NR SCG를 함께 설정하여 NSA Call을 시작한다."""
    response = _send_request(
        client,
        _TARGET_MT8000A,
        _COMMAND_NSA_CALL,
        _build_nsa_handover_params(
            band=band,
            bw=bw,
            modulation=modulation,
            rb_size=rb_size,
            rb_offset=rb_offset,
            channel=channel,
            anchor_ul_channel=anchor_ul_channel,
            max_retry_count=max_retry_count,
            waiting_time=waiting_time,
        ),
    )
    return _action_ok(response, _TARGET_MT8000A, _COMMAND_NSA_CALL)


def recall_param(client: Any, *, recall_name: str) -> bool:
    """MT8000A Recall을 적용하고 LV가 확인한 Call 연결 상태를 반환한다."""
    response = _send_request(
        client,
        _TARGET_MT8000A,
        _COMMAND_RECALL_PARAM,
        {"Recall Name": recall_name},
    )
    result = _result_dict(response, _TARGET_MT8000A, _COMMAND_RECALL_PARAM)
    ok = _boolean(result, "ok", _TARGET_MT8000A, _COMMAND_RECALL_PARAM)
    if not ok:
        raise CommandError(
            f"{_TARGET_MT8000A} / {_COMMAND_RECALL_PARAM} returned ok=false"
        )
    return _boolean(
        result,
        "connected",
        _TARGET_MT8000A,
        _COMMAND_RECALL_PARAM,
    )


def call_handover(
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
    """NR Call Handover를 수행한다."""
    response = _send_request(
        client,
        _TARGET_MT8000A,
        _COMMAND_NR_HANDOVER,
        _build_handover_params(
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
    return _action_ok(response, _TARGET_MT8000A, _COMMAND_NR_HANDOVER)


def nsa_handover(
    client: Any,
    *,
    band: int,
    bw: int,
    modulation: Modulation | str,
    rb_size: int,
    rb_offset: int,
    channel: int,
    anchor_ul_channel: int,
    max_retry_count: int = 3,
    waiting_time: int = 5,
) -> bool:
    """LTE Anchor 변경과 NR SCG 재연결을 단일 composite로 수행한다."""

    response = _send_request(
        client,
        _TARGET_MT8000A,
        _COMMAND_NSA_HANDOVER,
        _build_nsa_handover_params(
            band=band,
            bw=bw,
            modulation=modulation,
            rb_size=rb_size,
            rb_offset=rb_offset,
            channel=channel,
            anchor_ul_channel=anchor_ul_channel,
            max_retry_count=max_retry_count,
            waiting_time=waiting_time,
        ),
    )
    return _action_ok(response, _TARGET_MT8000A, _COMMAND_NSA_HANDOVER)


def lte_call_handover(
    client: Any,
    *,
    bw: int | float,
    dl_channel: int,
    ul_channel: int,
    rb_offset: int,
    max_retry_count: int = 3,
    waiting_time: int = 5,
) -> bool:
    """같은 LTE Recall 내에서 다음 Test Case 설정으로 Handover한다."""
    response = _send_request(
        client,
        _TARGET_MT8000A,
        _COMMAND_LTE_HANDOVER,
        _build_lte_handover_params(
            bw=bw,
            dl_channel=dl_channel,
            ul_channel=ul_channel,
            rb_offset=rb_offset,
            max_retry_count=max_retry_count,
            waiting_time=waiting_time,
        ),
    )
    return _action_ok(response, _TARGET_MT8000A, _COMMAND_LTE_HANDOVER)


def set_reference_co3000(client: Any) -> bool:
    response = _send_request(client, _TARGET_CO3000, _COMMAND_SET_REFERENCE, {})
    return _action_ok(response, _TARGET_CO3000, _COMMAND_SET_REFERENCE)


def self_align_fsv40(client: Any) -> bool:
    response = _send_request(client, _TARGET_FSV40, _COMMAND_SELF_ALIGNMENT, {})
    return _action_ok(response, _TARGET_FSV40, _COMMAND_SELF_ALIGNMENT)


def get_tdf_list(client: Any) -> list[str]:
    """FSV40에 저장된 TDF 파일 목록을 조회한다."""

    response = _send_request(client, _TARGET_FSV40, _COMMAND_GET_TDF_LIST, {})
    result = _result_dict(response, _TARGET_FSV40, _COMMAND_GET_TDF_LIST)
    tdf_file_list = result.get("TDF File List")
    if isinstance(tdf_file_list, str | bytes) or not isinstance(
        tdf_file_list,
        Sequence,
    ):
        raise CommandError(
            f"{_TARGET_FSV40} / {_COMMAND_GET_TDF_LIST} "
            "Result.TDF File List must be a list"
        )
    normalized = [str(file_name) for file_name in tdf_file_list]
    if any(not isinstance(file_name, str) for file_name in tdf_file_list):
        raise CommandError(
            f"{_TARGET_FSV40} / {_COMMAND_GET_TDF_LIST} "
            "Result.TDF File List must contain only strings"
        )
    return normalized


def tdf_all_off(client: Any) -> bool:
    """FSV40의 모든 TDF를 비활성화한다."""

    response = _send_request(client, _TARGET_FSV40, _COMMAND_TDF_ALL_OFF, {})
    return _action_ok(response, _TARGET_FSV40, _COMMAND_TDF_ALL_OFF)


def set_tdf(client: Any, *, tdf_file_name: str) -> bool:
    """선택한 TDF 파일 하나를 FSV40에 활성화한다."""

    response = _send_request(
        client,
        _TARGET_FSV40,
        _COMMAND_SET_TDF,
        {"TDF File Name": str(tdf_file_name)},
    )
    return _action_ok(response, _TARGET_FSV40, _COMMAND_SET_TDF)


def measure_fundamental(client: Any, *, target_freq: float) -> float:
    """기본파 측정 후 fundamental frequency를 MHz로 반환한다. §4.3.

    요청의 Center Frequency는 MHz로 전송하고, LV 응답의 Fundamental Frequency는
    Hz로 수신한다. Python 내부/리포트/FSM은 MHz 기준을 유지한다.
    """
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
    frequency_hz = _number(
        result,
        "Fundamental Frequency",
        _TARGET_FSV40,
        _COMMAND_SEARCH_FUNDAMENTAL_FREQUENCY,
    )
    return frequency_hz / _HZ_PER_MHZ


def set_switch_input(client: Any, *, input_path: InputPath) -> bool:
    """Switch Box 입력 경로만 설정한다."""

    response = _send_request(
        client,
        _TARGET_SWITCH_BOX,
        _COMMAND_SET_INPUT,
        {"Input Path": int(input_path)},
    )
    return _action_ok(response, _TARGET_SWITCH_BOX, _COMMAND_SET_INPUT)


def set_switch_filter(client: Any, *, filter_path: FilterPath) -> bool:
    """Switch Box 필터 경로만 설정한다."""

    response = _send_request(
        client,
        _TARGET_SWITCH_BOX,
        _COMMAND_SET_FILTER,
        {"Filter Path": int(filter_path)},
    )
    return _action_ok(response, _TARGET_SWITCH_BOX, _COMMAND_SET_FILTER)


def set_switch_box(client: Any, *, input_path: InputPath, filter_path: FilterPath) -> bool:
    """Switch Box 경로 설정. §4.4 / §4.8."""
    response = _send_request(
        client,
        _TARGET_SWITCH_BOX,
        _COMMAND_SET_PATH,
        {
            "Input Path": int(input_path),
            "Filter Path": int(filter_path),
        },
    )
    return _action_ok(response, _TARGET_SWITCH_BOX, _COMMAND_SET_PATH)


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


def setup_sa_manual(
    client: Any,
    *,
    start_frequency_mhz: float,
    stop_frequency_mhz: float,
    rbw_mhz: float,
    vbw_mhz: float,
    sweep_point: int,
    sweep_time_sec: float,
    atten_level_db: float,
    detector_mode: str,
    limit_dbm: float,
) -> bool:
    """Manual Test용 FSV40 설정을 적용한다.

    주파수와 RBW/VBW는 MHz, Sweep Time은 초, Atten Level은 dB,
    Limit은 dBm 단위다.
    """
    if isinstance(sweep_point, bool) or not isinstance(sweep_point, int):
        raise ValueError("sweep_point must be an integer")
    if detector_mode not in _MANUAL_DETECTOR_MODES:
        supported = ", ".join(sorted(_MANUAL_DETECTOR_MODES))
        raise ValueError(
            f"Unsupported detector mode: {detector_mode!r}. "
            f"Supported detector modes: {supported}"
        )

    response = _send_request(
        client,
        _TARGET_FSV40,
        _COMMAND_LOAD_SA_MANUAL_SETTING,
        {
            "Start Frequency": float(start_frequency_mhz),
            "Stop Frequency": float(stop_frequency_mhz),
            "RBW": float(rbw_mhz),
            "VBW": float(vbw_mhz),
            "Sweep Point": sweep_point,
            "Sweep Time": float(sweep_time_sec),
            "Atten Level": float(atten_level_db),
            "Detector Mode": detector_mode,
            "Limit": float(limit_dbm),
        },
    )
    return _action_ok(response, _TARGET_FSV40, _COMMAND_LOAD_SA_MANUAL_SETTING)


def preset_sa(client: Any) -> bool:
    """FSV40을 Preset 상태로 초기화한다."""
    response = _send_request(client, _TARGET_FSV40, _COMMAND_PRESET, {})
    return _action_ok(response, _TARGET_FSV40, _COMMAND_PRESET)


def clear_trace(client: Any) -> bool:
    """FSV40 Trace 누적값을 지우고 Max Hold 적용 완료를 기다린다."""
    response = _send_request(client, _TARGET_FSV40, _COMMAND_CLEAR_TRACE, {})
    return _action_ok(response, _TARGET_FSV40, _COMMAND_CLEAR_TRACE)


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


def get_turntable_angle(client: Any) -> float:
    response = _send_request(
        client,
        _TARGET_CO3000,
        _COMMAND_GET_TURNTABLE_ANGLE,
        {},
    )
    result = _result_dict(response, _TARGET_CO3000, _COMMAND_GET_TURNTABLE_ANGLE)
    current_angle = _number(
        result,
        "Current Angle",
        _TARGET_CO3000,
        _COMMAND_GET_TURNTABLE_ANGLE,
    )
    if not math.isfinite(current_angle) or not 0.0 <= current_angle <= 360.0:
        raise CommandError(
            f"{_TARGET_CO3000} / {_COMMAND_GET_TURNTABLE_ANGLE} "
            "Result.Current Angle must be between 0 and 360"
        )
    return current_angle


def stop_turntable(client: Any) -> None:
    """CO3000 턴테이블 즉시 정지. UI Stop 처리용. §4.6."""
    response = _send_request(client, _TARGET_CO3000, _COMMAND_STOP_TURNTABLE)
    _require_action_ok(response, _TARGET_CO3000, _COMMAND_STOP_TURNTABLE)


def measure_harmonics(
    client: Any,
    *,
    fundamental: float,
) -> list[HarmonicMarker]:
    """2nd~5th harmonic amplitude(dBm)와 peak frequency(MHz)를 순서대로 반환한다. §4.7.

    외부 프로그램은 측정 중 `temp_dir/harmonic.png` 경로에 SA 스크린샷을
    남긴다고 가정한다. LV 응답의 Frequency는 Hz로 수신하고, Python 내부에서는
    MHz 기준을 유지한다.
    """
    response = _send_request(
        client,
        _TARGET_FSV40,
        _COMMAND_MARK_HARMONIC,
        {"Fundamental Frequency": float(fundamental)},
    )
    result = _result_dict(response, _TARGET_FSV40, _COMMAND_MARK_HARMONIC)
    return _harmonic_markers_from_result(result, _COMMAND_MARK_HARMONIC)


def measure_harmonic_manual(
    client: Any,
    *,
    fundamental: float,
) -> list[HarmonicMarker]:
    """수동 마커 모드 Harmonic 측정 결과를 반환한다."""
    response = _send_request(
        client,
        _TARGET_FSV40,
        _COMMAND_MEASURE_HARMONIC,
        {"Fundamental Frequency": float(fundamental)},
    )
    result = _result_dict(response, _TARGET_FSV40, _COMMAND_MEASURE_HARMONIC)
    return _harmonic_markers_from_result(result, _COMMAND_MEASURE_HARMONIC)


def setup_sa_precision(
    client: Any,
    *,
    peak_frequency: float,
    sweep_time: int,
) -> bool:
    """FSV40 정밀측정 SA 설정.

    Python 내부 sweep_time 인자는 ms 기준이고, LV 프로토콜에는 s 기준으로 전송한다.
    """
    response = _send_request(
        client,
        _TARGET_FSV40,
        _COMMAND_LOAD_SA_PRECISION_SETTING,
        {
            "Peak Frequency": float(peak_frequency),
            "Sweep Time": float(sweep_time / 1000),
        },
    )
    return _action_ok(response, _TARGET_FSV40, _COMMAND_LOAD_SA_PRECISION_SETTING)


def measure_harmonic_precision(client: Any) -> float:
    """Harmonic 정밀측정 amplitude(dBm)를 반환한다."""
    response = _send_request(
        client,
        _TARGET_FSV40,
        _COMMAND_MARK_HARMONIC_PRECISION,
        {},
    )
    result = _result_dict(response, _TARGET_FSV40, _COMMAND_MARK_HARMONIC_PRECISION)
    return _number(result, "Amplitude", _TARGET_FSV40, _COMMAND_MARK_HARMONIC_PRECISION)


def measure_inband(client: Any, *, limit: float) -> float:
    """In-Band 측정 amplitude(dBm)를 반환한다."""
    response = _send_request(
        client,
        _TARGET_FSV40,
        _COMMAND_MARK_INBAND,
        {"Limit": float(limit)},
    )
    result = _result_dict(response, _TARGET_FSV40, _COMMAND_MARK_INBAND)
    return _number(result, "Amplitude", _TARGET_FSV40, _COMMAND_MARK_INBAND)


def measure_bilog(client: Any, *, limit: float) -> float:
    """Bilog 측정 amplitude(dBm)를 반환한다."""
    return measure_inband(client, limit=limit)


def measure_inband_manual(client: Any, *, limit: float) -> float:
    """수동 마커 모드 In-Band 측정 amplitude(dBm)를 반환한다."""
    response = _send_request(
        client,
        _TARGET_FSV40,
        _COMMAND_MEASURE_INBAND,
        {"Limit": float(limit)},
    )
    result = _result_dict(response, _TARGET_FSV40, _COMMAND_MEASURE_INBAND)
    return _number(result, "Amplitude", _TARGET_FSV40, _COMMAND_MEASURE_INBAND)


def measure_bilog_manual(client: Any, *, limit: float) -> float:
    """수동 마커 모드 Bilog 측정 amplitude(dBm)를 반환한다."""
    return measure_inband_manual(client, limit=limit)


def get_screenshot(client: Any) -> bool:
    """현재 FSV40 화면을 temp/screenshot.png로 저장한다."""
    response = _send_request(client, _TARGET_FSV40, _COMMAND_GET_SCREENSHOT, {})
    return _action_ok(response, _TARGET_FSV40, _COMMAND_GET_SCREENSHOT)


def marker_peak(client: Any, *, marker_index: int, excursion: float) -> bool:
    return _send_marker_command(
        client,
        _COMMAND_MARKER_PEAK,
        marker_index=marker_index,
        excursion=excursion,
    )


def marker_next(client: Any, *, marker_index: int, excursion: float) -> bool:
    return _send_marker_command(
        client,
        _COMMAND_MARKER_NEXT,
        marker_index=marker_index,
        excursion=excursion,
    )


def marker_off(client: Any, *, marker_index: int, excursion: float) -> bool:
    return _send_marker_command(
        client,
        _COMMAND_MARKER_OFF,
        marker_index=marker_index,
        excursion=excursion,
    )


def marker_all_off(client: Any) -> bool:
    response = _send_request(client, _TARGET_FSV40, _COMMAND_MARKER_ALL_OFF, {})
    return _action_ok(response, _TARGET_FSV40, _COMMAND_MARKER_ALL_OFF)


def marker_auto_max(
    client: Any,
    *,
    marker_index: int,
    excursion: float = 0.0,
) -> bool:
    return _send_marker_command(
        client,
        _COMMAND_MARKER_AUTO_MAX,
        marker_index=marker_index,
        excursion=excursion,
    )


def marker_set_center(
    client: Any,
    *,
    marker_index: int,
    excursion: float = 0.0,
) -> bool:
    return _send_marker_command(
        client,
        _COMMAND_MARKER_SET_CENTER,
        marker_index=marker_index,
        excursion=excursion,
    )


def check_call_status(client: Any) -> bool:
    """현재 NR/LTE Call 연결 상태를 확인한다. CallCheck 등에서 호출."""
    response = _send_request(client, _TARGET_MT8000A, _COMMAND_CHECK_CALL_STATUS)
    result = _result_dict(response, _TARGET_MT8000A, _COMMAND_CHECK_CALL_STATUS)
    ok = _boolean(result, "ok", _TARGET_MT8000A, _COMMAND_CHECK_CALL_STATUS)
    if not ok:
        raise CommandError(f"{_TARGET_MT8000A} / {_COMMAND_CHECK_CALL_STATUS} returned ok=false")
    return _boolean(
        result,
        "connected",
        _TARGET_MT8000A,
        _COMMAND_CHECK_CALL_STATUS,
    )


def _antenna_pol_target_and_params(
    *,
    pol: AntennaPol,
    input_path: InputPath,
) -> tuple[str, dict[str, Any]]:
    if input_path is InputPath.INPUT3:
        return _TARGET_3D_CONTROLLER, {"pol": pol.value}

    try:
        mast_index = _CO3000_MAST_INDEX_BY_INPUT_PATH[input_path]
    except KeyError as exc:
        raise CommandError(f"Unsupported antenna input path: {input_path!r}") from exc
    return _TARGET_CO3000, {"pol": pol.value, "Mast Index": mast_index}


def set_antenna_pol(client: Any, *, pol: AntennaPol, input_path: InputPath) -> bool:
    """안테나 편파 전환 (사용자 개입 훅과 연동)."""
    target, params = _antenna_pol_target_and_params(
        pol=pol,
        input_path=input_path,
    )
    response = _send_request(
        client,
        target,
        _COMMAND_CHANGE_ANT_POL,
        params,
    )
    return _action_ok(response, target, _COMMAND_CHANGE_ANT_POL)


def _harmonic_markers_from_result(
    result: dict[str, Any],
    command: str,
) -> list[HarmonicMarker]:
    amplitudes = _number_list(
        result,
        "Amplitude",
        _TARGET_FSV40,
        command,
        expected_count=4,
    )
    frequencies_hz = _number_list(
        result,
        "Frequency",
        _TARGET_FSV40,
        command,
        expected_count=4,
    )
    frequencies_mhz = [frequency_hz / _HZ_PER_MHZ for frequency_hz in frequencies_hz]
    return [
        HarmonicMarker(
            order=order,
            amplitude_dbm=amplitude,
            peak_frequency_mhz=frequency,
        )
        for order, amplitude, frequency in zip(
            (2, 3, 4, 5),
            amplitudes,
            frequencies_mhz,
            strict=True,
        )
    ]


def _send_marker_command(
    client: Any,
    command: str,
    *,
    marker_index: int,
    excursion: float,
) -> bool:
    response = _send_request(
        client,
        _TARGET_FSV40,
        command,
        {
            "Marker Index": int(marker_index),
            "Excursion": float(excursion),
        },
    )
    return _action_ok(response, _TARGET_FSV40, command)


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


def _number_list(
    result: dict[str, Any],
    key: str,
    target: str,
    command: str,
    *,
    expected_count: int,
) -> list[float]:
    values = result.get(key)
    if isinstance(values, str | bytes) or not isinstance(values, Sequence):
        raise CommandError(f"{target} / {command} Result.{key} must be a list")

    normalized = [_coerce_number(value, target, command, key) for value in values]
    if len(normalized) != expected_count:
        raise CommandError(
            f"{target} / {command} Result.{key} must contain "
            f"{expected_count} values, got {len(normalized)}"
        )
    return normalized


def _coerce_number(value: Any, target: str, command: str, key: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise CommandError(f"{target} / {command} Result.{key} must be a number")
    return float(value)
