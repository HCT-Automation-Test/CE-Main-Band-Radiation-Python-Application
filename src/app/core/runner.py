"""통합 세션 FSM 실행 컨트롤러. 내부에 QThread 워커를 둔다."""
from __future__ import annotations

import logging
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
from app.models.test_case import TestCase
from app.models.test_run_settings import TestRunSettings
from app.net import commands as default_commands
from app.net.tcp_client import TcpClient
from app.report.excel_writer import ExcelReportWriter
from app.report.report_writer import ReportWriter

logger = logging.getLogger(__name__)

EngineFactory = Callable[[SessionContext], FSMEngine]
ReportWriterFactory = Callable[[Path, Path, str, RunnerEvents], ReportWriter]
InstrumentConnectionBlocker = Callable[[], str | None]

_TEMP_DIR = Path("temp")
_START_READY_STATE = "Idle"
INSTRUMENT_SET_BLOCK_MESSAGE = "장비 Set이 진행 중입니다"
INSTRUMENT_CONNECTION_BLOCK_MESSAGE = (
    "시험 실행 중에는 Instrument Check 연결을 시작할 수 없습니다."
)


def _default_report_writer_factory(
    template_path: Path,
    screenshot_root_dir: Path,
    model_name: str,
    events: RunnerEvents,
) -> ReportWriter:
    return ReportWriter(
        excel_writer=ExcelReportWriter(template_path),
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

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        client: Any | None = None,
        commands: Any = default_commands,
        instrument_connection_service: InstrumentConnectionService | None = None,
        engine_factory: EngineFactory = build_session_engine,
        report_writer_factory: ReportWriterFactory = _default_report_writer_factory,
        tcp_host: str = "127.0.0.1",
        tcp_port: int = 5025,
        temp_dir: Path = _TEMP_DIR,
    ) -> None:
        super().__init__(parent)
        self.events = RunnerEvents(self)
        self._thread: QThread | None = None
        self._worker: _RunnerWorker | None = None
        self._ctx: SessionContext | None = None
        self._owns_client = client is None
        self._client = client if client is not None else TcpClient(self)
        self._commands = commands
        self._engine_factory = engine_factory
        self._report_writer_factory = report_writer_factory
        self._tcp_host = tcp_host
        self._tcp_port = tcp_port
        self._temp_dir = Path(temp_dir)
        self._equipment_state: dict[str, bool] = {}
        self._measurement_active = False
        self._restart_index: int | None = None
        self._shutting_down = False
        self._instrument_connection_blockers: list[InstrumentConnectionBlocker] = []
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
            )
        )
        self.events.state_changed.connect(self._on_state_changed)
        self._instrument_connection_service.connection_finished.connect(
            self._on_instrument_connection_finished
        )
        self._instrument_connection_service.error_occurred.connect(
            self._on_instrument_connection_error
        )
        self._instrument_connection_service.equipment_disconnected.connect(
            self._on_equipment_disconnected
        )

    @property
    def is_running(self) -> bool:
        """FSM worker thread 실행 여부."""
        return self._thread is not None and self._thread.isRunning()

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
    def restart_index(self) -> int | None:
        """Pause 후 재시작할 TestCase index를 반환한다."""

        return self._restart_index

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

    def initialize(self) -> None:
        """앱 시작 시 SessionInit 상태로 FSM worker를 기동한다."""
        if self.is_running:
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
        )
        self._ctx.equipment_state = dict(self._equipment_state)

        self._thread = QThread(self)
        self._worker = _RunnerWorker(self._ctx, self._engine_factory)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(
            self._thread.quit,
            Qt.ConnectionType.DirectConnection,
        )
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._on_thread_finished)
        self._thread.start()

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
        if not self.is_equipment_ready:
            self._emit_error("시험 시작 실패: Instrument Check 연결을 완료하세요")
            return
        if self._ctx is None or not self.is_running:
            self._emit_error("시험 시작 실패: Runner is not initialized")
            return
        if not self._is_waiting_for_start():
            self._emit_error("시험 시작 실패: Runner is not idle")
            return
        if not cases:
            self._emit_error("시험 시작 실패: TestCase queue is empty")
            return
        normalized_model_name = settings.eut_name
        template = settings.template_path
        screenshot_root = settings.screenshot_root_dir
        self._temp_dir.mkdir(parents=True, exist_ok=True)
        try:
            report_writer = self._report_writer_factory(
                template,
                screenshot_root,
                normalized_model_name,
                self.events,
            )
        except Exception as exc:
            self._emit_error(f"시험 시작 실패: report writer 생성 실패: {exc}")
            return

        ctx = self._ctx
        ctx.queue = list(cases)
        ctx.report_writer = report_writer
        restart_index = self._restart_index
        if start_index is None:
            if restart_index is not None and restart_index < len(cases):
                start_index = restart_index
                stop_index = None
            else:
                start_index = 0
        elif start_index < 0 or start_index >= len(cases):
            start_index = 0
        ctx.start_index = start_index
        ctx.stop_index = stop_index
        ctx.current_index = start_index
        ctx.paused = False
        ctx.stopped = False
        ctx.current_case_stop_requested = False
        ctx.current_angle = 0.0
        ctx.fundamental_frequency_mhz = None
        ctx.temp_dir = self._temp_dir
        ctx.settings = settings
        ctx.model_name = normalized_model_name
        ctx.template_path = template
        ctx.screenshot_root_dir = screenshot_root
        self._restart_index = None
        self._set_measurement_active(True)
        ctx.test_start_requested.set()

    def pause(self) -> None:
        """현재 TC 실행을 중단하고 같은 TC부터 다시 시작할 수 있게 한다."""
        if self._ctx is None or not self.is_measurement_active:
            return
        self._restart_index = self._ctx.current_index
        self._ctx.current_case_stop_requested = True
        self._ctx.paused = False
        self._ctx.user_action_completed.set()

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

    def shutdown(self) -> None:
        """Runner가 소유한 worker, 연결 서비스, TCP client를 정리한다."""

        if self._shutting_down:
            return
        self._shutting_down = True

        shutdown = getattr(self._instrument_connection_service, "shutdown", None)
        if shutdown is not None:
            shutdown()

        thread = self._thread
        self.stop()
        if thread is not None and thread.isRunning() and not thread.wait(1000):
            logger.error("Runner worker thread did not stop cleanly")

        if self._owns_client:
            close = getattr(self._client, "close", None)
            if close is not None:
                close()

    def _emit_error(self, message: str) -> None:
        logger.error(message)
        self.events.error.emit(message)

    def _is_waiting_for_start(self) -> bool:
        if self._worker is None or self._worker.engine is None:
            return False
        return self._worker.engine.current_state_name == _START_READY_STATE

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

    def _on_thread_finished(self) -> None:
        self._set_measurement_active(False)
        self._thread = None
        self._worker = None

    @Slot(str)
    def _on_state_changed(self, state_name: str) -> None:
        if state_name == _START_READY_STATE:
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
