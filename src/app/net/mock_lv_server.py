"""사용자 테스트용 LabVIEW 장비 mock 서버."""
from __future__ import annotations

import argparse
import logging
import random
import shutil
import signal
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

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
_COMMAND_SEARCH_FUNDAMENTAL_FREQUENCY = "Search Fundamental Frequency"
_COMMAND_MARK_HARMONIC = "Mark Harmonic"
_COMMAND_MARK_HARMONIC_PRECISION = "Mark Harmonic Precision"
_COMMAND_MARK_INBAND = "Mark Inband"
_COMMAND_NR_CALL = "NR Call"
_COMMAND_NR_HANDOVER = "NR Handover"
_COMMAND_CHECK_CALL_STATUS = "Check Call Status"
_COMMAND_CHANGE_ANT_POL = "Change Ant Pol"
_COMMAND_MOVE_TURNTABLE = "Move TurnTable"
_COMMAND_STOP_TURNTABLE = "Stop TurnTable"
_COMMAND_GET_TURNTABLE_ANGLE = "Get TurnTable Angle"
_COMMAND_SET_INPUT = "Set Input"
_COMMAND_SET_FILTER = "Set Filter"
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
    current_angle: float = 0.0
    switch_input_path: int | None = None
    switch_filter_path: int | None = None
    antenna_pol: str | None = None
    last_sa_range_params: dict[str, Any] | None = None
    last_sa_level_params: dict[str, Any] | None = None
    last_sa_precision_params: dict[str, Any] | None = None
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

    def _handle_request(self, request: Request) -> Response:
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
            self.state.antenna_pol = str(params.get("pol", ""))
            return _ok(request)

        return _error(request, "unsupported command")

    def _handle_mt8000a(self, request: Request) -> Response:
        if request.command == _COMMAND_NR_CALL:
            self.state.call_connected = True
            return _ok(request)
        if request.command == _COMMAND_NR_HANDOVER:
            return _ok(request)
        if request.command == _COMMAND_CHECK_CALL_STATUS:
            connected = (
                False
                if self.scenario == "call-disconnected"
                else self.state.call_connected
            )
            return _ok(request, {"ok": True, "connected": connected})
        return _error(request, "unsupported command")

    def _handle_fsv40(self, request: Request) -> Response:
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
            if self.scenario == "bad-harmonic-result":
                return _ok(request, {"Amplitude": [-42.1, -48.0, -51.0]})
            return _ok(
                request,
                {
                    "Amplitude": [-42.1, -48.0, -51.0, -56.2],
                    "Frequency": [7100.5, 10650.75, 14201.0, 17751.25],
                },
            )
        if request.command == _COMMAND_MARK_HARMONIC_PRECISION:
            self._write_png("precision.png")
            sweep_time = 100
            if self.state.last_sa_precision_params is not None:
                sweep_time = _coerce_int(
                    self.state.last_sa_precision_params.get("Sweep Time"),
                    100,
                )
            amplitude = -31.0 if sweep_time == 100 else -34.0
            return _ok(request, {"Amplitude": amplitude})
        if request.command == _COMMAND_MARK_INBAND:
            self._write_png("inband.png")
            limit = _coerce_float(request.params.get("Limit"), -30.0)
            return _ok(request, {"Amplitude": limit - 12.1})
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
            self.state.antenna_pol = str(request.params.get("pol", ""))
            return _ok(request)
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
        ],
        default="normal",
    )
    parser.add_argument("--turntable-delay-sec", type=float, default=1.0)
    parser.add_argument("--set-reference-delay-sec", type=float, default=15.0)
    parser.add_argument("--self-alignment-delay-sec", type=float, default=15.0)
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
