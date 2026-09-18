"""통합 세션 FSM 실행 컨트롤러. 내부에 QThread 워커를 둔다."""
from __future__ import annotations

import logging
import sys
import time
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot

from app.core.events import RunnerEvents
from app.core.fsm.context import SessionContext
from app.core.fsm.engine import FSMEngine, build_session_engine
from app.core.instrument_connection import (
    InstrumentConnectionService,
    describe_equipment_not_ready,
    is_selected_equipment_ready,
    normalize_equipment_state,
    should_preserve_equipment_state_on_connection_error,
)
from app.core.run_preparer import (
    RawDataResultResolver,
    ReportWriterFactory,
    RunPreparer,
    RunPreparationRequest,
)
from app.core.tc_validator import validate_queue
from app.models.test_case import TestCase
from app.models.test_run_settings import TestRunSettings
from app.net import commands as default_commands
from app.net.lv_server_process import LvServerManager
from app.net.tcp_client import TcpClient
from app.report.excel_writer import ExcelReportWriter
from app.report.rawdata_workbook import ensure_rawdata_result_workbook
from app.report.report_writer import ReportWriter

logger = logging.getLogger(__name__)

EngineFactory = Callable[[SessionContext], FSMEngine]
InstrumentConnectionBlocker = Callable[[], str | None]
StartBlocker = Callable[[], str | None]

_TEMP_DIR = Path("temp")
_START_READY_STATE = "Idle"
_START_READY_TIMEOUT_SEC = 1.0
_START_READY_POLL_SEC = 0.01
_SHUTDOWN_WAIT_MS = 1000
_THREAD_GENERATION_PROPERTY = "runner_generation"

# 종료 제한 시간을 넘긴 Runner는 부모 UI와 분리한 뒤 스레드가 끝날 때까지 보존한다.
_SHUTDOWN_KEEPERS: dict[int, "Runner"] = {}
INSTRUMENT_SET_BLOCK_MESSAGE = "장비 Set이 진행 중입니다"
INSTRUMENT_CONNECTION_BLOCK_MESSAGE = (
    "시험 실행 중에는 Instrument Check 연결을 시작할 수 없습니다."
)


def _default_report_writer_factory(
    workbook_path: Path,
    screenshot_root_dir: Path,
    model_name: str,
    events: RunnerEvents,
) -> ReportWriter:
    return ReportWriter(
        excel_writer=ExcelReportWriter(workbook_path),
        screenshot_root_dir=screenshot_root_dir,
        model_name=model_name,
        events=events,
    )


class _RunnerWorker(QObject):
    """QThread 안에서 FSMEngine을 실행하는 worker."""

    finished = Signal()

    def __init__(
        self,
        ctx: SessionContext,
        engine_factory: EngineFactory,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._ctx = ctx
        self._engine_factory = engine_factory
        self.engine: FSMEngine | None = None

    @Slot()
    def run(self) -> None:
        try:
            self.engine = self._engine_factory(self._ctx)
            self.engine.run("SessionInit")
        except Exception as exc:
            logger.exception("FSM 실행 실패")
            if self._ctx.events is not None:
                self._ctx.events.error.emit(f"FSM 실행 실패: {exc}")
        finally:
            self.finished.emit()


class Runner(QObject):
    """측정 세션 전체를 조립하고 TC 큐를 FSM으로 실행하는 컨트롤러.

    내부에서 `QThread`에 워커를 올려 FSMEngine을 돌린다.
    UI는 `events` 시그널만 구독.
    """

    measurement_active_changed = Signal(bool)
    shutdown_finished = Signal()
    _thread_destroyed_relay = Signal()

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        client: Any | None = None,
        commands: Any = default_commands,
        instrument_connection_service: InstrumentConnectionService | None = None,
        engine_factory: EngineFactory = build_session_engine,
        report_writer_factory: ReportWriterFactory = _default_report_writer_factory,
        rawdata_result_resolver: RawDataResultResolver = (
            ensure_rawdata_result_workbook
        ),
        tcp_host: str = "127.0.0.1",
        tcp_port: int = 5025,
        temp_dir: Path = _TEMP_DIR,
        lv_server_manager: Any | None = None,
    ) -> None:
        super().__init__(parent)
        self.events = RunnerEvents(self)
        self._thread: QThread | None = None
        self._worker: _RunnerWorker | None = None
        self._ctx: SessionContext | None = None
        self._generation = 0
        self._active_generation: int | None = None
        self._cleanup_thread: QThread | None = None
        self._cleanup_worker: _RunnerWorker | None = None
        self._pending_thread_completion: tuple[bool, bool, bool] | None = None
        self._owns_client = client is None
        self._client = client if client is not None else TcpClient(self)
        self._commands = commands
        self._engine_factory = engine_factory
        self._run_preparer = RunPreparer(
            result_resolver=rawdata_result_resolver,
            report_writer_factory=report_writer_factory,
        )
        self._tcp_host = tcp_host
        self._tcp_port = tcp_port
        self._temp_dir = Path(temp_dir)
        self._lv_server_manager = (
            lv_server_manager
            if lv_server_manager is not None
            else (
                LvServerManager(host=self._tcp_host, port=self._tcp_port)
                if self._owns_client and getattr(sys, "frozen", False)
                else None
            )
        )
        self._equipment_state: dict[str, bool] = {}
        self._measurement_active = False
        self._session_completed_normally = False
        self._shutting_down = False
        self._shutdown_complete = False
        self._shutdown_finished_emitted = False
        self._client_closed = False
        self._instrument_connection_blockers: list[InstrumentConnectionBlocker] = []
        self._start_blockers: list[StartBlocker] = []
        self._instrument_connection_service = (
            instrument_connection_service
            if instrument_connection_service is not None
            else InstrumentConnectionService(
                self,
                client=self._client,
                commands=self._commands,
                tcp_host=self._tcp_host,
                tcp_port=self._tcp_port,
                connection_guard=self._instrument_connection_block_reason,
                lv_server_manager=self._lv_server_manager,
            )
        )
        self.events.session_finished.connect(self._on_session_finished)
        self.events.start_rejected.connect(self._on_start_rejected)
        self._instrument_connection_service.connection_finished.connect(
            self._on_instrument_connection_finished
        )
        self._instrument_connection_service.error_occurred.connect(
            self._on_instrument_connection_error
        )
        self._instrument_connection_service.equipment_disconnected.connect(
            self._on_equipment_disconnected
        )
        self._thread_destroyed_relay.connect(
            self._on_thread_destroyed,
            Qt.ConnectionType.QueuedConnection,
        )

    @property
    def is_running(self) -> bool:
        """현재 FSM 세대의 정리가 아직 완료되지 않았는지 반환한다."""

        return self._active_generation is not None

    @property
    def context(self) -> SessionContext | None:
        """테스트/상위 조립 코드에서 현재 컨텍스트를 확인하기 위한 접근자."""
        return self._ctx

    @property
    def instrument_connection_service(self) -> InstrumentConnectionService:
        """Instrument Check UI가 사용할 Runner 소유 연결 서비스를 반환한다."""

        return self._instrument_connection_service

    @property
    def client(self) -> Any:
        """외부 LabVIEW TCP 서버와 통신하는 공용 client를 반환한다."""

        return self._client

    @property
    def commands(self) -> Any:
        """Runner와 보조 서비스가 공유할 command facade를 반환한다."""

        return self._commands

    @property
    def temp_dir(self) -> Path:
        """보조 서비스와 공유하는 LV 임시 파일 경로를 반환한다."""

        return self._temp_dir


    @property
    def equipment_state(self) -> dict[str, bool]:
        """마지막으로 확인된 장비 연결 상태를 반환한다."""

        return dict(self._equipment_state)

    @property
    def is_equipment_ready(self) -> bool:
        """모든 장비가 연결 완료 상태인지 반환한다."""

        return is_selected_equipment_ready(self._equipment_state)

    @property
    def is_measurement_active(self) -> bool:
        """측정 실행이 진행 중인지 반환한다."""

        return self._measurement_active

    @property
    def is_equipment_connecting(self) -> bool:
        """Instrument Check 연결 작업이 진행 중인지 반환한다."""

        return bool(getattr(self._instrument_connection_service, "is_connecting", False))

    @property
    def is_equipment_setting(self) -> bool:
        """Instrument Set 작업이 진행 중인지 반환한다."""

        return bool(getattr(self._instrument_connection_service, "is_setting", False))

    def add_instrument_connection_blocker(
        self,
        provider: InstrumentConnectionBlocker,
    ) -> None:
        """Instrument Check/Set 요청 직전 추가 차단 사유를 등록한다."""

        self._instrument_connection_blockers.append(provider)

    def add_start_blocker(self, provider: StartBlocker) -> None:
        """시험 시작 요청 직전 추가 차단 사유를 등록한다."""

        self._start_blockers.append(provider)

    def initialize(self) -> None:
        """앱 시작 시 SessionInit 상태로 FSM worker를 기동한다."""
        if self._shutting_down or self.is_running:
            return

        self._temp_dir.mkdir(parents=True, exist_ok=True)
        self._ctx = SessionContext(
            queue=[],
            commands=self._commands,
            events=self.events,
            client=self._client,
            tcp_host=self._tcp_host,
            tcp_port=self._tcp_port,
            temp_dir=self._temp_dir,
            run_preparer=self._run_preparer,
        )
        self._ctx.equipment_state = dict(self._equipment_state)

        self._generation += 1
        generation = self._generation
        thread = QThread(self)
        worker = _RunnerWorker(self._ctx, self._engine_factory)
        thread.setProperty(_THREAD_GENERATION_PROPERTY, generation)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(
            thread.quit,
            Qt.ConnectionType.DirectConnection,
        )
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(
            self._on_thread_finished,
            Qt.ConnectionType.QueuedConnection,
        )
        thread.destroyed.connect(self._thread_destroyed_relay)

        self._thread = thread
        self._worker = worker
        self._active_generation = generation
        thread.start()

    def connect_equipment(self) -> None:
        """기존 호출부 호환용 장비 준비 상태 재통지 shim."""

        if not self.is_equipment_ready:
            self._emit_error(
                "장비 준비 상태 통지 실패: "
                + describe_equipment_not_ready(self._equipment_state)
            )
            return
        self.mark_equipment_ready(self._equipment_state)

    def mark_equipment_ready(self, states: dict[str, bool]) -> None:
        """Instrument Check에서 확인된 장비 준비 상태를 FSM gate에 전달한다."""

        self._equipment_state = normalize_equipment_state(states)
        if not self.is_equipment_ready:
            self._emit_error(
                "장비 준비 상태 통지 실패: "
                + describe_equipment_not_ready(self._equipment_state)
            )
            return
        if not self.is_running:
            self.initialize()
        if self._ctx is None:
            self._emit_error("장비 준비 상태 통지 실패: SessionContext is not initialized")
            return
        self._ctx.equipment_state = dict(self._equipment_state)
        self._ctx.equipment_connect_requested.set()

    def start(
        self,
        cases: list[TestCase],
        *,
        settings: TestRunSettings,
        start_index: int | None = None,
        stop_index: int | None = None,
    ) -> None:
        """Idle 상태에서 시험 실행 요청을 주입한다."""
        if self.is_equipment_connecting:
            self._emit_error("시험 시작 실패: 장비 연결이 진행 중입니다")
            return
        if self.is_equipment_setting:
            self._emit_error(f"시험 시작 실패: {INSTRUMENT_SET_BLOCK_MESSAGE}")
            return
        if self.is_measurement_active:
            self._emit_error("시험 시작 실패: Runner is not idle")
            return
        for provider in self._start_blockers:
            block_reason = provider()
            if block_reason:
                self._emit_error(f"시험 시작 실패: {block_reason}")
                return
        if not self.is_equipment_ready:
            self._emit_error("시험 시작 실패: Instrument Check 연결을 완료하세요")
            return
        if not self._ensure_start_ready():
            self._emit_error("시험 시작 실패: Runner is not idle")
            return
        if not cases:
            self._emit_error("시험 시작 실패: TestCase queue is empty")
            return
        queue_errors = validate_queue(cases)
        if queue_errors:
            self._emit_error(f"시험 시작 실패: {queue_errors[0]}")
            return
        if start_index is None or start_index < 0 or start_index >= len(cases):
            start_index = 0

        ctx = self._ctx
        ctx.pending_run_request = RunPreparationRequest(
            cases=tuple(cases),
            settings=settings,
            start_index=start_index,
            stop_index=stop_index,
        )
        ctx.paused = False
        ctx.stopped = False
        ctx.current_case_stop_requested = False
        self._session_completed_normally = False
        self._set_measurement_active(True)
        ctx.test_start_requested.set()

    def pause(self) -> None:
        """이전 호환용 shim. 정지와 동일하게 처리한다."""

        self.stop()

    def resume(self) -> None:
        """일시정지 해제."""
        if self._ctx is not None:
            self._ctx.paused = False

    def stop(self) -> None:
        """실행 중단. ctx.stopped = True."""
        if self._ctx is None:
            return
        self._ctx.stopped = True
        self._ctx.paused = False
        self._ctx.equipment_connect_requested.set()
        self._ctx.test_start_requested.set()
        self._ctx.user_action_completed.set()

    def user_action_completed(self) -> None:
        """수동 조작 요청 상태에서 UI 확인 완료를 전달한다."""
        if self._ctx is not None:
            self._ctx.user_action_completed.set()

    def marker_peak(self, marker_index: int, excursion: float) -> bool:
        """수동 마커 편집 dialog에서 Marker Peak를 요청한다."""

        return self._run_marker_command(
            "Marker Peak",
            self._commands.marker_peak,
            marker_index=marker_index,
            excursion=excursion,
        )

    def marker_next(self, marker_index: int, excursion: float) -> bool:
        """수동 마커 편집 dialog에서 Marker Next를 요청한다."""

        return self._run_marker_command(
            "Marker Next",
            self._commands.marker_next,
            marker_index=marker_index,
            excursion=excursion,
        )

    def marker_off(self, marker_index: int, excursion: float) -> bool:
        """수동 마커 편집 dialog에서 Marker OFF를 요청한다."""

        return self._run_marker_command(
            "Marker OFF",
            self._commands.marker_off,
            marker_index=marker_index,
            excursion=excursion,
        )

    def marker_all_off(self) -> bool:
        """수동 마커 편집 dialog에서 모든 marker OFF를 요청한다."""

        try:
            ok = bool(self._commands.marker_all_off(self._client))
        except Exception as exc:
            self._emit_error(f"Marker ALL OFF 실패: {exc}")
            return False
        if not ok:
            self._emit_error("Marker ALL OFF 실패: marker_all_off returned false")
        return ok

    def _run_marker_command(
        self,
        label: str,
        command: Callable[..., bool],
        *,
        marker_index: int,
        excursion: float,
    ) -> bool:
        try:
            ok = bool(
                command(
                    self._client,
                    marker_index=marker_index,
                    excursion=excursion,
                )
            )
        except Exception as exc:
            self._emit_error(f"{label} 실패: {exc}")
            return False
        if not ok:
            self._emit_error(f"{label} 실패: command returned false")
        return ok

    def shutdown(self) -> bool:
        """자원을 정리하고 완료 여부를 반환한다.

        제한 시간 안에 worker가 끝나지 않으면 ``False``를 반환하고,
        비동기 정리가 끝난 뒤 ``shutdown_finished``를 한 번 방출한다.
        """

        if self._shutdown_complete:
            return True
        if self._shutting_down:
            return False

        self._shutting_down = True

        shutdown = getattr(self._instrument_connection_service, "shutdown", None)
        if shutdown is not None:
            shutdown()

        thread = self._thread
        generation = self._active_generation
        self.stop()
        if thread is not None and thread.isRunning():
            if not thread.wait(_SHUTDOWN_WAIT_MS):
                logger.error("Runner worker thread did not stop cleanly")
                self._retain_until_shutdown_finished()
                return False

        if thread is not None and generation is not None:
            self._finalize_thread(thread, generation)
        elif generation is None:
            self._complete_shutdown()

        return self._shutdown_complete

    def _emit_error(self, message: str) -> None:
        logger.error(message)
        self.events.error.emit(message)

    def _is_waiting_for_start(self) -> bool:
        if (
            self._active_generation is None
            or self._ctx is None
            or self._ctx.stopped
            or self._thread is None
            or not self._thread.isRunning()
            or self._worker is None
            or self._worker.engine is None
        ):
            return False
        return self._worker.engine.current_state_name == _START_READY_STATE

    def _ensure_start_ready(self) -> bool:
        if self._shutting_down:
            return False
        if self._ctx is None or not self.is_running:
            self.initialize()
        if self._ctx is None:
            return False
        if not self.is_running:
            return False
        if self._ctx.stopped:
            return False
        if self._is_waiting_for_start():
            return True

        self._ctx.equipment_state = dict(self._equipment_state)
        self._ctx.equipment_connect_requested.set()
        deadline = time.monotonic() + _START_READY_TIMEOUT_SEC
        while time.monotonic() < deadline:
            if self._ctx.stopped:
                return False
            if self._is_waiting_for_start():
                return True
            if not self.is_running:
                return False
            time.sleep(_START_READY_POLL_SEC)
        return self._is_waiting_for_start()

    def _instrument_connection_block_reason(self) -> str | None:
        if self.is_measurement_active:
            return INSTRUMENT_CONNECTION_BLOCK_MESSAGE
        for provider in self._instrument_connection_blockers:
            reason = provider()
            if reason:
                return reason
        return None

    def _set_measurement_active(self, active: bool) -> None:
        if self._measurement_active == active:
            return
        self._measurement_active = active
        self.measurement_active_changed.emit(active)

    @Slot()
    def _on_thread_finished(self) -> None:
        sender = self.sender()
        if not isinstance(sender, QThread):
            logger.warning("Runner thread finished signal has an invalid sender")
            return
        generation = sender.property(_THREAD_GENERATION_PROPERTY)
        if not isinstance(generation, int):
            logger.warning("Runner thread finished signal has no generation")
            return
        self._finalize_thread(sender, generation)

    def _finalize_thread(self, thread: QThread, generation: int) -> None:
        """일치하는 실행 세대만 정리하고 QThread 삭제를 한 곳에서 예약한다."""

        if self._thread is not thread or self._active_generation != generation:
            logger.debug("Ignoring stale Runner thread completion: generation=%s", generation)
            return

        # QThread.finished는 native thread의 TLS 정리가 끝나기 직전에 방출될 수 있다.
        # deleteLater 전에 wait()로 native tail까지 끝났음을 동기화한다.
        thread.wait()

        ctx = self._ctx
        was_measurement_active = self._measurement_active
        completed_normally = self._session_completed_normally
        stopped = bool(ctx is not None and ctx.stopped)

        # 활성 참조를 먼저 비우되, deleteLater가 실제 처리될 때까지 세대는 유지한다.
        # finished 직후 새 QThread를 만들면 이전 QThread의 DeferredDelete와 경쟁할 수 있다.
        self._cleanup_thread = thread
        self._cleanup_worker = self._worker
        self._thread = None
        self._worker = None
        self._pending_thread_completion = (
            was_measurement_active,
            completed_normally,
            stopped,
        )
        self._set_measurement_active(False)
        thread.deleteLater()

    @Slot()
    def _on_thread_destroyed(self) -> None:
        """QThread의 DeferredDelete까지 끝난 세대만 최종 완료 처리한다."""

        if self._active_generation is None or self._cleanup_thread is None:
            logger.debug("Ignoring stale Runner thread destruction")
            return

        completion = self._pending_thread_completion
        self._cleanup_thread = None
        self._cleanup_worker = None
        self._pending_thread_completion = None
        self._active_generation = None

        if self._shutting_down:
            self._complete_shutdown()
            return
        if completion is None:
            logger.warning("Runner thread destruction has no completion state")
            return

        was_measurement_active, completed_normally, stopped = completion
        if not was_measurement_active or completed_normally:
            return
        if stopped:
            self.events.session_stopped.emit()
            return
        self.events.session_failed.emit()

    def _retain_until_shutdown_finished(self) -> None:
        """부모가 파괴되어도 실행 중인 Runner 전체가 살아 있도록 보존한다."""

        if self.parent() is not None:
            self.setParent(None)
        _SHUTDOWN_KEEPERS[id(self)] = self

    def _complete_shutdown(self) -> None:
        """모든 Runner 자원의 종료 완료를 한 번만 알린다."""

        if self._shutdown_complete or self._active_generation is not None:
            return

        if self._owns_client and not self._client_closed:
            self._client_closed = True
            close = getattr(self._client, "close", None)
            if close is not None:
                try:
                    close()
                except Exception:
                    logger.exception("Runner TCP client close failed")

        self._shutdown_complete = True
        if not self._shutdown_finished_emitted:
            self._shutdown_finished_emitted = True
            self.shutdown_finished.emit()
        _SHUTDOWN_KEEPERS.pop(id(self), None)

    @Slot()
    def _on_session_finished(self) -> None:
        self._session_completed_normally = True
        self._set_measurement_active(False)

    @Slot()
    def _on_start_rejected(self) -> None:
        self._set_measurement_active(False)

    @Slot(dict)
    def _on_instrument_connection_finished(self, states: dict[str, bool]) -> None:
        self._equipment_state = normalize_equipment_state(states)
        if self.is_equipment_ready:
            self.mark_equipment_ready(self._equipment_state)
            return
        self._emit_error(
            "장비 연결 실패: "
            + describe_equipment_not_ready(self._equipment_state)
        )

    @Slot(dict)
    def _on_equipment_disconnected(self, states: dict[str, bool]) -> None:
        _ = states
        self._equipment_state = {}
        if self._ctx is not None:
            self._ctx.equipment_state = {}

    @Slot(str)
    def _on_instrument_connection_error(self, message: str) -> None:
        block_reason = self._instrument_connection_block_reason()
        if not should_preserve_equipment_state_on_connection_error(
            message,
            block_reason=block_reason,
        ):
            self._equipment_state = {}
        self._emit_error(f"장비 연결 실패: {message}")
