"""사용자 테스트용 LabVIEW 장비 mock 서버."""
from __future__ import annotations

import argparse
import logging
import math
import random
import shutil
import signal
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from app.models.nsa_anchor import (
    NSAAnchorChannels,
    SUPPORTED_NSA_ANCHOR_BANDS,
    resolve_nsa_anchor_channels,
)
from app.net.mock_server import MockServer
from app.net.protocol import Event, Request, Response

logger = logging.getLogger(__name__)

MockLvScenario = Literal[
    "normal",
    "turntable-error",
    "turntable-timeout",
    "call-disconnected",
    "bad-harmonic-result",
    "set-reference-timeout",
    "self-alignment-timeout",
    "set-reference-error",
    "self-alignment-error",
    "nsa-scg-release-error",
    "nsa-scg-release-timeout",
    "nsa-anchor-handover-error",
    "nsa-anchor-handover-timeout",
    "nsa-anchor-profile-mismatch",
    "nsa-nr-call-error",
    "nsa-nr-call-timeout",
    "nsa-final-status-timeout",
    "nsa-call-error",
    "nsa-call-timeout",
    "recall-param-error",
    "manual-command-error",
    "manual-command-no-response",
]

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

_COMMAND_TURNTABLE_PROGRESS = "turntable_progress"
_COMMAND_TURNTABLE_COMPLETE = "turntable_complete"
_COMMAND_SET_REFERENCE_COMPLETE = "set_reference_complete"
_COMMAND_SELF_ALIGNMENT_COMPLETE = "self_alignment_complete"
_COMMAND_EQUIPMENT_ERROR = "equipment_error"
_TURNTABLE_STEP_DEGREE = 30.0
MOCK_TDF_FILE_LIST: tuple[str, ...] = (
    "2025_MAIN_LB Filter+1G HPF(30M-1G).tdf",
    "2025_MAIN_Bilog Filter+3G HPF(30M-13G).tdf",
    "2025_MAIN_UHB Filter+6G HPF(30M-26G).tdf",
    "NR_Radiated.tdf",
    "CE_Harmonic.tdf",
    "NR_Inband.tdf",
    "NR_Bilog.tdf",
    "SA_N78_100M.tdf",
    "SA_N77_100M.tdf",
    "SA_N79_100M.tdf",
    "Harmonic_3m.tdf",
    "Harmonic_Bilog.tdf",
    "Factory_Default.tdf",
)

_SUPPORTED_TARGETS = {
    _TARGET_FSV40,
    _TARGET_MT8000A,
    _TARGET_CO3000,
    _TARGET_SWITCH_BOX,
    _TARGET_3D_CONTROLLER,
}
_NSA_HANDOVER_REQUIRED_PARAMS = {
    "Band",
    "BandWidth",
    "Center Channel",
    "RB Size",
    "RB Offset",
    "Modulation",
    "Anchor UL Channel",
    "Max Retry Count",
    "Waiting Time",
}
_MANUAL_SA_REQUIRED_PARAMS = {
    "Start Frequency",
    "Stop Frequency",
    "RBW",
    "VBW",
    "Sweep Point",
    "Sweep Time",
    "Atten Level",
    "Detector Mode",
    "Limit",
}
_MANUAL_DETECTOR_MODES = {
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
_MANUAL_COMMANDS = {
    _COMMAND_LOAD_SA_MANUAL_SETTING,
    _COMMAND_PRESET,
    _COMMAND_MARKER_AUTO_MAX,
    _COMMAND_MARKER_SET_CENTER,
    _COMMAND_CLEAR_TRACE,
}
_NSA_ANCHOR_CHANNELS_BY_UL: dict[int, NSAAnchorChannels] = {
    channels.ul_channel: channels
    for band in SUPPORTED_NSA_ANCHOR_BANDS
    for channels in (resolve_nsa_anchor_channels(band),)
}

# 1x1 투명 PNG. 실제 화면 캡처 대신 파일 존재/형식 확인용으로만 사용한다.
_MINIMAL_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
    b"\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


@dataclass
class MockLvState:
    """Mock LV 서버가 유지하는 장비 상태."""

    connected_targets: set[str] = field(default_factory=set)
    call_connected: bool = False
    call_state_by_rem_dest: dict[str, int | None] = field(
        default_factory=lambda: {"8000A": None, "8821C": None}
    )
    anchor_dl_channel: int | None = None
    anchor_ul_channel: int | None = None
    last_nsa_nr_params: dict[str, Any] | None = None
    last_recall_name: str | None = None
    current_angle: float = 0.0
    switch_input_path: int | None = None
    switch_filter_path: int | None = None
    antenna_pol: str | None = None
    antenna_pol_3m: str | None = None
    antenna_pol_bilog: str | None = None
    antenna_pol_1m: str | None = None
    last_sa_range_params: dict[str, Any] | None = None
    last_sa_level_params: dict[str, Any] | None = None
    last_sa_precision_params: dict[str, Any] | None = None
    last_manual_sa_params: dict[str, Any] | None = None
    preset_count: int = 0
    manual_marker_state: dict[int, dict[str, Any]] = field(default_factory=dict)
    trace_clear_count: int = 0
    max_hold_enabled: bool = False
    turntable_stop_requested: threading.Event = field(default_factory=threading.Event)


class MockLvServer:
    """실제 LabVIEW 프로그램처럼 동작하는 도메인 mock 서버."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 5025,
        *,
        temp_dir: Path | str = "temp",
        scenario: MockLvScenario = "normal",
        turntable_delay_sec: float = 1.0,
        set_reference_delay_sec: float = 15.0,
        self_alignment_delay_sec: float = 15.0,
        manual_response_delay_sec: float = 0.0,
        screenshot_fixture_dir: Path | str | None = None,
        screenshot_random_seed: int | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.temp_dir = Path(temp_dir)
        self.scenario = scenario
        self.turntable_delay_sec = float(turntable_delay_sec)
        self.set_reference_delay_sec = float(set_reference_delay_sec)
        self.self_alignment_delay_sec = float(self_alignment_delay_sec)
        self.manual_response_delay_sec = float(manual_response_delay_sec)
        self.screenshot_fixture_dir = (
            Path(screenshot_fixture_dir)
            if screenshot_fixture_dir is not None
            else None
        )
        self._screenshot_random = random.Random(screenshot_random_seed)
        self.state = MockLvState()
        self._server = MockServer(
            host=host,
            port=port,
            response_handler=self._handle_request,
        )
        self._turntable_thread: threading.Thread | None = None
        self._set_stop_requested = threading.Event()
        self._set_event_threads: list[threading.Thread] = []

    @property
    def received_requests(self) -> list[Request]:
        """수신한 request 목록."""
        return self._server.received_requests

    def start(self) -> None:
        """서버를 시작하고 temp 디렉터리를 준비한다."""
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self._set_stop_requested.clear()
        self._server.start()
        self.port = self._server.port

    def stop(self) -> None:
        """서버를 종료한다."""
        self.state.turntable_stop_requested.set()
        self._set_stop_requested.set()
        self._server.stop()
        if self._turntable_thread is not None:
            self._turntable_thread.join(timeout=1.0)
            self._turntable_thread = None
        for thread in self._set_event_threads:
            thread.join(timeout=1.0)
        self._set_event_threads.clear()

    def _handle_request(self, request: Request) -> Response | None:
        if request.target not in _SUPPORTED_TARGETS:
            return _error(request, "unsupported command")

        target = request.target
        command = request.command
        params = request.params

        if command == _COMMAND_CONNECT:
            self.state.connected_targets.add(target)
            return _ok(request)

        if target == _TARGET_MT8000A:
            return self._handle_mt8000a(request)
        if target == _TARGET_FSV40:
            return self._handle_fsv40(request)
        if target == _TARGET_SWITCH_BOX:
            return self._handle_switch_box(request)
        if target == _TARGET_CO3000:
            return self._handle_co3000(request)
        if target == _TARGET_3D_CONTROLLER and command == _COMMAND_CHANGE_ANT_POL:
            pol = str(params.get("pol", ""))
            self.state.antenna_pol = pol
            self.state.antenna_pol_1m = pol
            return _ok(request)

        return _error(request, "unsupported command")

    def _handle_mt8000a(self, request: Request) -> Response:
        if request.command == _COMMAND_RECALL_PARAM:
            if set(request.params) != {"Recall Name"}:
                return _error(request, "invalid Recall Param Params")
            recall_name = request.params.get("Recall Name")
            if not isinstance(recall_name, str) or not recall_name:
                return _error(
                    request,
                    "Recall Param Params.Recall Name must be a non-empty string",
                )
            if self.scenario == "recall-param-error":
                return _error(request, "Recall Param failed: equipment error")
            connected = self.scenario != "call-disconnected"
            self.state.last_recall_name = recall_name
            self.state.call_connected = connected
            return _ok(request, {"ok": True, "connected": connected})
        if request.command == _COMMAND_NSA_HANDOVER:
            return self._handle_nsa_handover(request)
        if request.command == _COMMAND_NSA_CALL:
            return self._handle_nsa_call(request)
        if request.command in {_COMMAND_NR_CALL, _COMMAND_LTE_CALL}:
            self.state.call_connected = True
            return _ok(request)
        if request.command in {_COMMAND_NR_HANDOVER, _COMMAND_LTE_HANDOVER}:
            return _ok(request)
        if request.command == _COMMAND_CHECK_CALL_STATUS:
            connected = (
                False
                if self.scenario == "call-disconnected"
                else self.state.call_connected
            )
            return _ok(request, {"ok": True, "connected": connected})
        return _error(request, "unsupported command")

    def _handle_nsa_call(self, request: Request) -> Response:
        """첫 NSA TC의 Anchor와 NR Call 설정을 함께 적용한다."""

        params = request.params
        if set(params) != _NSA_HANDOVER_REQUIRED_PARAMS:
            return _error(request, "invalid NSA Call Params")

        try:
            nr_params = {
                "Band": _required_int(params, "Band", _COMMAND_NSA_CALL),
                "BandWidth": _required_int(params, "BandWidth", _COMMAND_NSA_CALL),
                "Center Channel": _required_int(
                    params, "Center Channel", _COMMAND_NSA_CALL
                ),
                "RB Size": _required_int(params, "RB Size", _COMMAND_NSA_CALL),
                "RB Offset": _required_int(params, "RB Offset", _COMMAND_NSA_CALL),
                "Modulation": _required_text(
                    params, "Modulation", _COMMAND_NSA_CALL
                ),
                "Max Retry Count": _required_int(
                    params, "Max Retry Count", _COMMAND_NSA_CALL
                ),
                "Waiting Time": _required_int(
                    params, "Waiting Time", _COMMAND_NSA_CALL
                ),
            }
            anchor_ul_channel = _required_int(
                params, "Anchor UL Channel", _COMMAND_NSA_CALL
            )
        except ValueError as exc:
            return _error(request, str(exc))

        anchor_channels = _NSA_ANCHOR_CHANNELS_BY_UL.get(anchor_ul_channel)
        if anchor_channels is None:
            return _error(
                request,
                f"unsupported NSA Anchor UL Channel: {anchor_ul_channel}",
            )
        if self.scenario == "nsa-call-error":
            return _error(request, "NSA Call failed: equipment error")
        if self.scenario == "nsa-call-timeout":
            return _error(request, "NSA Call failed: timeout")

        self.state.call_connected = True
        self.state.call_state_by_rem_dest = {"8000A": 8, "8821C": 6}
        self.state.anchor_dl_channel = anchor_channels.dl_channel
        self.state.anchor_ul_channel = anchor_channels.ul_channel
        self.state.last_nsa_nr_params = nr_params
        return _ok(request)

    def _handle_nsa_handover(self, request: Request) -> Response:
        """NSA Handover 단일 composite의 REM_DEST별 상태를 재현한다."""

        if set(request.params) != _NSA_HANDOVER_REQUIRED_PARAMS:
            return _error(request, "invalid NSA Handover Params")

        try:
            nr_params = {
                "Band": _required_int(request.params, "Band"),
                "BandWidth": _required_int(request.params, "BandWidth"),
                "Center Channel": _required_int(request.params, "Center Channel"),
                "RB Size": _required_int(request.params, "RB Size"),
                "RB Offset": _required_int(request.params, "RB Offset"),
                "Modulation": _required_text(request.params, "Modulation"),
                "Max Retry Count": _required_int(request.params, "Max Retry Count"),
                "Waiting Time": _required_int(request.params, "Waiting Time"),
            }
            anchor_ul_channel = _required_int(request.params, "Anchor UL Channel")
        except ValueError as exc:
            return _error(request, str(exc))

        anchor_channels = _NSA_ANCHOR_CHANNELS_BY_UL.get(anchor_ul_channel)
        if anchor_channels is None:
            return _error(
                request,
                f"unsupported NSA Anchor UL Channel: {anchor_ul_channel}",
            )

        self.state.call_connected = False
        self.state.last_nsa_nr_params = nr_params
        self.state.call_state_by_rem_dest["8000A"] = 9
        if self.scenario == "nsa-scg-release-error":
            return _error(request, "NSA Handover failed at scg_release: equipment error")
        if self.scenario == "nsa-scg-release-timeout":
            return _error(request, "NSA Handover failed at scg_release: timeout")

        self.state.call_state_by_rem_dest["8000A"] = 6
        self.state.call_state_by_rem_dest["8821C"] = 13
        if self.scenario == "nsa-anchor-handover-error":
            return _error(request, "NSA Handover failed at anchor_handover: equipment error")
        if self.scenario == "nsa-anchor-handover-timeout":
            return _error(request, "NSA Handover failed at anchor_handover: timeout")

        self.state.call_state_by_rem_dest["8821C"] = 6
        self.state.anchor_dl_channel = anchor_channels.dl_channel
        self.state.anchor_ul_channel = anchor_channels.ul_channel
        if self.scenario == "nsa-anchor-profile-mismatch":
            return _error(request, "NSA Handover failed at anchor_profile: mismatch")

        self.state.call_state_by_rem_dest["8000A"] = 7
        if self.scenario == "nsa-nr-call-error":
            return _error(request, "NSA Handover failed at nr_call: equipment error")
        if self.scenario == "nsa-nr-call-timeout":
            return _error(request, "NSA Handover failed at nr_call: timeout")
        if self.scenario == "nsa-final-status-timeout":
            return _error(request, "NSA Handover failed at final_status: timeout")

        self.state.call_state_by_rem_dest["8000A"] = 8
        self.state.call_connected = True
        return _ok(request)

    def _handle_fsv40(self, request: Request) -> Response | None:
        if request.command in _MANUAL_COMMANDS:
            return self._handle_manual_fsv40(request)
        if request.command == _COMMAND_LOAD_SA_LEVEL_SETTING:
            self.state.last_sa_level_params = dict(request.params)
            return _ok(request)
        if request.command == _COMMAND_LOAD_SA_RANGE_SETTING:
            self.state.last_sa_range_params = dict(request.params)
            return _ok(request)
        if request.command == _COMMAND_LOAD_SA_PRECISION_SETTING:
            self.state.last_sa_precision_params = dict(request.params)
            return _ok(request)
        if request.command == _COMMAND_SEARCH_FUNDAMENTAL_FREQUENCY:
            self._write_png("fundamental.png")
            center_freq = _coerce_float(request.params.get("Center Frequency"), 0.0)
            return _ok(
                request,
                {"Fundamental Frequency": (center_freq + 0.25) * 1_000_000.0},
            )
        if request.command == _COMMAND_MARK_HARMONIC:
            self._write_png("harmonic.png")
            return self._harmonic_response(request)
        if request.command == _COMMAND_MEASURE_HARMONIC:
            return self._harmonic_response(request)
        if request.command == _COMMAND_MARK_HARMONIC_PRECISION:
            self._write_png("precision.png")
            sweep_time_sec = 0.1
            if self.state.last_sa_precision_params is not None:
                sweep_time_sec = _coerce_float(
                    self.state.last_sa_precision_params.get("Sweep Time"),
                    0.1,
                )
            amplitude = -31.0 if math.isclose(sweep_time_sec, 0.1) else -34.0
            return _ok(request, {"Amplitude": amplitude})
        if request.command == _COMMAND_MARK_INBAND:
            self._write_png("inband.png")
            return self._inband_response(request)
        if request.command == _COMMAND_MEASURE_INBAND:
            return self._inband_response(request)
        if request.command == _COMMAND_GET_SCREENSHOT:
            self._write_png("screenshot.png")
            return _ok(request)
        if request.command in {
            _COMMAND_MARKER_PEAK,
            _COMMAND_MARKER_NEXT,
            _COMMAND_MARKER_OFF,
        }:
            _coerce_int(request.params.get("Marker Index"), 1)
            _coerce_float(request.params.get("Excursion"), 0.0)
            return _ok(request)
        if request.command == _COMMAND_MARKER_ALL_OFF:
            return _ok(request)
        if request.command == _COMMAND_SELF_ALIGNMENT:
            self._start_set_event(
                target=_TARGET_FSV40,
                complete_command=_COMMAND_SELF_ALIGNMENT_COMPLETE,
                source_command=_COMMAND_SELF_ALIGNMENT,
                delay_sec=self.self_alignment_delay_sec,
                timeout_scenario="self-alignment-timeout",
                error_scenario="self-alignment-error",
                error_message="mock self alignment error",
            )
            return _ok(request)
        if request.command == _COMMAND_GET_TDF_LIST:
            return _ok(request, {"TDF File List": list(MOCK_TDF_FILE_LIST)})
        if request.command == _COMMAND_TDF_ALL_OFF:
            return _ok(request)
        if request.command == _COMMAND_SET_TDF:
            return _ok(request)
        return _error(request, "unsupported command")

    def _handle_manual_fsv40(self, request: Request) -> Response | None:
        """Manual Test 계약을 검증하고 외부에서 관찰 가능한 최소 상태를 반영한다."""
        try:
            update_state = self._manual_state_update(request)
        except ValueError as exc:
            return _error(request, str(exc))

        if self.scenario == "manual-command-error":
            return _error(request, "mock manual command equipment error")

        update_state()
        if self.manual_response_delay_sec > 0:
            time.sleep(self.manual_response_delay_sec)
        if self.scenario == "manual-command-no-response":
            return None
        return _ok(request)

    def _manual_state_update(self, request: Request) -> Callable[[], None]:
        if request.command == _COMMAND_LOAD_SA_MANUAL_SETTING:
            params = _validated_manual_sa_params(request.params)

            def update_manual_setting() -> None:
                self.state.last_manual_sa_params = params

            return update_manual_setting

        if request.command == _COMMAND_PRESET:
            _require_empty_params(request.params, _COMMAND_PRESET)

            def update_preset() -> None:
                self.state.preset_count += 1

            return update_preset

        if request.command in {
            _COMMAND_MARKER_AUTO_MAX,
            _COMMAND_MARKER_SET_CENTER,
        }:
            marker_index, excursion = _validated_marker_params(request.params)

            def update_marker() -> None:
                self.state.manual_marker_state[marker_index] = {
                    "action": request.command,
                    "Excursion": excursion,
                }

            return update_marker

        if request.command == _COMMAND_CLEAR_TRACE:
            _require_empty_params(request.params, _COMMAND_CLEAR_TRACE)

            def update_trace() -> None:
                self.state.trace_clear_count += 1
                self.state.max_hold_enabled = True

            return update_trace

        raise ValueError(f"unsupported Manual command: {request.command}")

    def _harmonic_response(self, request: Request) -> Response:
        if self.scenario == "bad-harmonic-result":
            return _ok(request, {"Amplitude": [-42.1, -48.0, -51.0]})
        return _ok(
            request,
            {
                "Amplitude": [-42.1, -48.0, -51.0, -56.2],
                "Frequency": [
                    7100500000.0,
                    10650750000.0,
                    14201000000.0,
                    17751250000.0,
                ],
            },
        )

    def _inband_response(self, request: Request) -> Response:
        limit = _coerce_float(request.params.get("Limit"), -30.0)
        return _ok(request, {"Amplitude": limit - 12.1})

    def _handle_switch_box(self, request: Request) -> Response:
        if request.command == _COMMAND_SET_INPUT:
            self.state.switch_input_path = _coerce_int(
                request.params.get("Input Path"), 0
            )
            return _ok(request)
        if request.command == _COMMAND_SET_FILTER:
            self.state.switch_filter_path = _coerce_int(
                request.params.get("Filter Path"), 0
            )
            return _ok(request)
        if request.command == _COMMAND_SET_PATH:
            self.state.switch_input_path = _coerce_int(
                request.params.get("Input Path"), 0
            )
            self.state.switch_filter_path = _coerce_int(
                request.params.get("Filter Path"), 0
            )
            return _ok(request)
        return _error(request, "unsupported command")

    def _handle_co3000(self, request: Request) -> Response:
        if request.command == _COMMAND_MOVE_TURNTABLE:
            self._start_turntable(request.params)
            return _ok(request)
        if request.command == _COMMAND_STOP_TURNTABLE:
            self.state.turntable_stop_requested.set()
            return _ok(request)
        if request.command == _COMMAND_GET_TURNTABLE_ANGLE:
            return _ok(request, {"Current Angle": self.state.current_angle})
        if request.command == _COMMAND_CHANGE_ANT_POL:
            mast_index = _coerce_int(request.params.get("Mast Index"), 0)
            pol = str(request.params.get("pol", ""))
            if mast_index == 1:
                self.state.antenna_pol = pol
                self.state.antenna_pol_3m = pol
                return _ok(request)
            if mast_index == 2:
                self.state.antenna_pol = pol
                self.state.antenna_pol_bilog = pol
                return _ok(request)
            return _error(request, "unsupported Mast Index")
        if request.command == _COMMAND_SET_REFERENCE:
            self._start_set_event(
                target=_TARGET_CO3000,
                complete_command=_COMMAND_SET_REFERENCE_COMPLETE,
                source_command=_COMMAND_SET_REFERENCE,
                delay_sec=self.set_reference_delay_sec,
                timeout_scenario="set-reference-timeout",
                error_scenario="set-reference-error",
                error_message="mock set reference error",
            )
            return _ok(request)
        return _error(request, "unsupported command")

    def _start_set_event(
        self,
        *,
        target: str,
        complete_command: str,
        source_command: str,
        delay_sec: float,
        timeout_scenario: MockLvScenario,
        error_scenario: MockLvScenario,
        error_message: str,
    ) -> None:
        thread = threading.Thread(
            target=self._run_set_event,
            args=(
                target,
                complete_command,
                source_command,
                delay_sec,
                timeout_scenario,
                error_scenario,
                error_message,
                self._set_stop_requested,
            ),
            daemon=True,
        )
        self._set_event_threads.append(thread)
        thread.start()

    def _run_set_event(
        self,
        target: str,
        complete_command: str,
        source_command: str,
        delay_sec: float,
        timeout_scenario: MockLvScenario,
        error_scenario: MockLvScenario,
        error_message: str,
        stop_requested: threading.Event,
    ) -> None:
        if stop_requested.wait(max(0.0, delay_sec)):
            return
        if self.scenario == timeout_scenario:
            return
        if self.scenario == error_scenario:
            self._send_event(
                target,
                _COMMAND_EQUIPMENT_ERROR,
                {"command": source_command, "message": error_message},
            )
            return
        self._send_event(target, complete_command, {})

    def _start_turntable(self, params: dict[str, Any]) -> None:
        self.state.turntable_stop_requested.set()
        if self._turntable_thread is not None:
            self._turntable_thread.join(timeout=0.2)

        turntable_info = params.get("Turn Table Info")
        if not isinstance(turntable_info, dict):
            turntable_info = {}
        target_angle = _coerce_float(turntable_info.get("Target Angle"), 0.0)

        self.state.turntable_stop_requested = threading.Event()
        self._turntable_thread = threading.Thread(
            target=self._run_turntable,
            args=(target_angle, self.state.turntable_stop_requested),
            daemon=True,
        )
        self._turntable_thread.start()

    def _run_turntable(
        self,
        target_angle: float,
        stop_requested: threading.Event,
    ) -> None:
        if self.scenario == "turntable-timeout":
            return

        step_interval = max(0.0, self.turntable_delay_sec)
        start_angle = self.state.current_angle
        direction = 1.0 if target_angle >= start_angle else -1.0
        current_angle = start_angle

        while current_angle != target_angle:
            if stop_requested.wait(step_interval):
                return
            next_angle = current_angle + (_TURNTABLE_STEP_DEGREE * direction)
            if direction > 0:
                current_angle = min(next_angle, target_angle)
            else:
                current_angle = max(next_angle, target_angle)
            self._send_turntable_event(
                _COMMAND_TURNTABLE_PROGRESS,
                {"Current Angle": current_angle},
            )

        if stop_requested.is_set():
            return
        if self.scenario == "turntable-error":
            self._send_turntable_event(
                _COMMAND_EQUIPMENT_ERROR,
                {"message": "mock turntable error"},
            )
            return

        self.state.current_angle = target_angle
        self._send_turntable_event(_COMMAND_TURNTABLE_COMPLETE, {})

    def _send_turntable_event(self, command: str, params: dict[str, Any]) -> None:
        self._send_event(_TARGET_CO3000, command, params)

    def _send_event(self, target: str, command: str, params: dict[str, Any]) -> None:
        event = Event(
            id=f"evt-{uuid4()}",
            target=target,
            command=command,
            params=params,
        )
        try:
            self._server.send_event(event)
            logger.info(
                "Mock LV event sent: target=%s command=%s params=%s",
                target,
                command,
                params,
            )
        except TimeoutError:
            logger.warning("mock LV event 전송 실패: client is not connected")

    def _write_png(self, name: str) -> None:
        path = self.temp_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        fixture = self._select_screenshot_fixture()
        if fixture is not None:
            shutil.copy2(fixture, path)
            logger.info(
                "Mock LV screenshot fixture copied: source=%s destination=%s",
                fixture,
                path,
            )
            return
        path.write_bytes(_MINIMAL_PNG)

    def _select_screenshot_fixture(self) -> Path | None:
        if self.screenshot_fixture_dir is None:
            return None
        if not self.screenshot_fixture_dir.is_dir():
            logger.warning(
                "Mock LV screenshot fixture dir not found: %s",
                self.screenshot_fixture_dir,
            )
            return None

        fixtures = sorted(
            path
            for path in self.screenshot_fixture_dir.iterdir()
            if path.is_file() and path.suffix.lower() == ".png"
        )
        if not fixtures:
            logger.info(
                "Mock LV screenshot fixture dir has no PNG files: %s",
                self.screenshot_fixture_dir,
            )
            return None
        return self._screenshot_random.choice(fixtures)


def _ok(request: Request, result: dict[str, Any] | None = None) -> Response:
    return Response(id=request.id, status="ok", result=result)


def _error(request: Request, message: str) -> Response:
    return Response(id=request.id, status="error", error={"message": message})


def _required_int(
    params: dict[str, Any],
    key: str,
    context: str = "NSA Handover Params",
) -> int:
    value = params.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{context}.{key} must be an integer")
    return value


def _required_text(
    params: dict[str, Any],
    key: str,
    context: str = "NSA Handover Params",
) -> str:
    value = params.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{context}.{key} must be a non-empty string")
    return value


def _validated_manual_sa_params(params: dict[str, Any]) -> dict[str, Any]:
    if set(params) != _MANUAL_SA_REQUIRED_PARAMS:
        raise ValueError("invalid Load SA Manual Setting Params")

    number_fields = {
        "Start Frequency",
        "Stop Frequency",
        "RBW",
        "VBW",
        "Sweep Time",
        "Atten Level",
        "Limit",
    }
    for key in number_fields:
        value = params[key]
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValueError(f"Load SA Manual Setting Params.{key} must be a number")

    sweep_point = params["Sweep Point"]
    if isinstance(sweep_point, bool) or not isinstance(sweep_point, int):
        raise ValueError(
            "Load SA Manual Setting Params.Sweep Point must be an integer"
        )

    detector_mode = params["Detector Mode"]
    if detector_mode not in _MANUAL_DETECTOR_MODES:
        raise ValueError(
            "Load SA Manual Setting Params.Detector Mode is unsupported"
        )
    return dict(params)


def _validated_marker_params(params: dict[str, Any]) -> tuple[int, float]:
    if set(params) != {"Marker Index", "Excursion"}:
        raise ValueError("invalid Manual Marker Params")

    marker_index = params["Marker Index"]
    if isinstance(marker_index, bool) or not isinstance(marker_index, int):
        raise ValueError("Manual Marker Params.Marker Index must be an integer")

    excursion = params["Excursion"]
    if isinstance(excursion, bool) or not isinstance(excursion, int | float):
        raise ValueError("Manual Marker Params.Excursion must be a number")
    return marker_index, float(excursion)


def _require_empty_params(params: dict[str, Any], command: str) -> None:
    if params:
        raise ValueError(f"{command} Params must be empty")


def _coerce_float(value: Any, default: float) -> float:
    if isinstance(value, bool):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_int(value: Any, default: int) -> int:
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="사용자 테스트용 Mock LV 서버")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5025)
    parser.add_argument("--temp-dir", type=Path, default=Path("temp"))
    parser.add_argument(
        "--scenario",
        choices=[
            "normal",
            "turntable-error",
            "turntable-timeout",
            "call-disconnected",
            "bad-harmonic-result",
            "set-reference-timeout",
            "self-alignment-timeout",
            "set-reference-error",
            "self-alignment-error",
            "nsa-scg-release-error",
            "nsa-scg-release-timeout",
            "nsa-anchor-handover-error",
            "nsa-anchor-handover-timeout",
            "nsa-anchor-profile-mismatch",
            "nsa-nr-call-error",
            "nsa-nr-call-timeout",
            "nsa-final-status-timeout",
            "nsa-call-error",
            "nsa-call-timeout",
            "recall-param-error",
            "manual-command-error",
            "manual-command-no-response",
        ],
        default="normal",
    )
    parser.add_argument("--turntable-delay-sec", type=float, default=1.0)
    parser.add_argument("--set-reference-delay-sec", type=float, default=15.0)
    parser.add_argument("--self-alignment-delay-sec", type=float, default=15.0)
    parser.add_argument("--manual-response-delay-sec", type=float, default=0.0)
    parser.add_argument("--screenshot-fixture-dir", type=Path, default=None)
    parser.add_argument("--screenshot-random-seed", type=int, default=None)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    server = MockLvServer(
        host=args.host,
        port=args.port,
        temp_dir=args.temp_dir,
        scenario=args.scenario,
        turntable_delay_sec=args.turntable_delay_sec,
        set_reference_delay_sec=args.set_reference_delay_sec,
        self_alignment_delay_sec=args.self_alignment_delay_sec,
        manual_response_delay_sec=args.manual_response_delay_sec,
        screenshot_fixture_dir=args.screenshot_fixture_dir,
        screenshot_random_seed=args.screenshot_random_seed,
    )

    stopped = threading.Event()

    def stop_server(_signum: int, _frame: object) -> None:
        stopped.set()

    signal.signal(signal.SIGINT, stop_server)
    signal.signal(signal.SIGTERM, stop_server)

    server.start()
    logger.info(
        "Mock LV server started on %s:%s (scenario=%s, temp_dir=%s, "
        "screenshot_fixture_dir=%s)",
        server.host,
        server.port,
        server.scenario,
        server.temp_dir,
        server.screenshot_fixture_dir,
    )
    try:
        while not stopped.wait(0.2):
            pass
    finally:
        server.stop()
        logger.info("Mock LV server stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
