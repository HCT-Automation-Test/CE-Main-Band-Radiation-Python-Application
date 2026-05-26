"""Instrument Check 연결/탐색 서비스."""
from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Sequence
from typing import Any

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot

from app.core import instrument_set
from app.models.enums import AntennaPol, InputPath
from app.net import commands as default_commands
from app.net.commands import EquipmentConnectionConfig
from app.net.tcp_client import TcpClient

logger = logging.getLogger(__name__)
_DETACHED_THREADS: list[QThread] = []

VisaResourceProvider = Callable[[], Sequence[str]]
ClientFactory = Callable[[], Any]
ConnectionGuard = Callable[[], str | None]

CONNECTION_IN_PROGRESS_MESSAGE = "장비 연결 요청이 이미 진행 중입니다."
INSTRUMENT_SET_IN_PROGRESS_MESSAGE = "장비 Set 작업이 이미 진행 중입니다."
CO3000_SET_REFERENCE_STEP_MESSAGE = "CO3000 Set Reference 진행 중"
CONTROLLER_3D_ANT_POL_VERTICAL_STEP_MESSAGE = (
    "3D Controller Ant Pol Vertical 진행 중"
)
FSV40_SELF_ALIGNMENT_STEP_MESSAGE = "FSV40 Self Alignment 진행 중"
CO3000_SET_REFERENCE_TIMEOUT_MESSAGE = (
    "장비 Set timeout: CO3000 Set Reference 완료 event를 수신하지 못했습니다."
)
FSV40_SELF_ALIGNMENT_TIMEOUT_MESSAGE = (
    "장비 Set timeout: FSV40 Self Alignment 완료 event를 수신하지 못했습니다."
)

REQUIRED_EQUIPMENT_NAMES: tuple[str, ...] = (
    "FSV40",
    "MT8000A",
    "CO3000",
    "Switch Box",
    "3D Controller",
)


def _disconnect_safely(signal: Any, slot: Any) -> None:
    try:
        signal.disconnect(slot)
    except (RuntimeError, TypeError):
        pass


def _forget_detached_thread(thread: QThread) -> None:
    if thread in _DETACHED_THREADS:
        _DETACHED_THREADS.remove(thread)


def _delete_detached_thread(thread: QThread) -> None:
    _forget_detached_thread(thread)
    thread.deleteLater()


def build_equipment_connection_config(
    *,
    mt8000a_visa_resource: str,
    fsv40_visa_resource: str,
    co3000_visa_resource: str,
    controller_3d_visa_resource: str,
    switch_box_ip_address: str,
    switch_box_port: int | str,
) -> EquipmentConnectionConfig:
    """UI 입력값을 장비 연결 command 설정으로 변환한다."""

    return EquipmentConnectionConfig(
        fsv40_visa_resource=fsv40_visa_resource.strip(),
        mt8000a_visa_resource=mt8000a_visa_resource.strip(),
        co3000_visa_resource=co3000_visa_resource.strip(),
        controller_3d_visa_resource=controller_3d_visa_resource.strip(),
        switch_box_ip_address=switch_box_ip_address.strip(),
        switch_box_port=int(switch_box_port),
    )


def normalize_equipment_state(states: dict[str, Any]) -> dict[str, bool]:
    """장비 상태 dict의 key/value를 FSM 판정용으로 정규화한다."""

    return {str(key): bool(value) for key, value in states.items()}


def missing_required_equipment(states: dict[str, Any]) -> list[str]:
    """필수 장비 중 상태 응답에 누락된 항목을 반환한다."""

    return [
        name
        for name in REQUIRED_EQUIPMENT_NAMES
        if name not in states
    ]


def disconnected_required_equipment(states: dict[str, Any]) -> list[str]:
    """필수 장비 중 연결 실패 상태인 항목을 반환한다."""

    return [
        name
        for name in REQUIRED_EQUIPMENT_NAMES
        if name in states and not bool(states[name])
    ]


def is_required_equipment_ready(states: dict[str, Any]) -> bool:
    """필수 장비가 모두 있고 모두 연결 완료인지 반환한다."""

    return (
        bool(states)
        and not missing_required_equipment(states)
        and not disconnected_required_equipment(states)
    )


def describe_equipment_not_ready(states: dict[str, Any]) -> str:
    """장비 준비 실패 원인을 사용자 로그용 문자열로 만든다."""

    if not states:
        return "equipment_state is empty"

    parts = []
    missing = missing_required_equipment(states)
    disconnected = disconnected_required_equipment(states)
    if missing:
        parts.append("missing equipment: " + ", ".join(missing))
    if disconnected:
        parts.append("disconnected equipment: " + ", ".join(disconnected))
    return "; ".join(parts) if parts else "equipment_state is not ready"


def should_preserve_equipment_state_on_connection_error(
    message: str,
    *,
    block_reason: str | None = None,
) -> bool:
    """실제 연결 실패가 아닌 차단 오류에서는 기존 장비 상태를 유지한다."""

    return message in {
        CONNECTION_IN_PROGRESS_MESSAGE,
        INSTRUMENT_SET_IN_PROGRESS_MESSAGE,
    } or (block_reason is not None and message == block_reason)


def disconnected_equipment_state() -> dict[str, bool]:
    """필수 장비 전체를 disconnected 상태로 표현한다."""

    return {name: False for name in REQUIRED_EQUIPMENT_NAMES}


def discover_visa_resources(
    provider: VisaResourceProvider | None = None,
) -> list[str]:
    """PC에서 VISA Resource 목록만 조회한다.

    실제 장비 연결/제어는 LabVIEW TCP command 경로에서만 수행한다.
    """

    if provider is not None:
        return sorted(str(resource) for resource in provider())

    import pyvisa

    resource_manager = pyvisa.ResourceManager()
    try:
        return sorted(str(resource) for resource in resource_manager.list_resources())
    finally:
        close = getattr(resource_manager, "close", None)
        if close is not None:
            close()


class _VisaDiscoveryWorker(QObject):
    """VISA Resource 탐색을 UI thread 밖에서 수행한다."""

    finished = Signal(list)
    failed = Signal(str)
    done = Signal()

    def __init__(self, provider: VisaResourceProvider | None = None) -> None:
        super().__init__()
        self._provider = provider

    @Slot()
    def run(self) -> None:
        try:
            self.finished.emit(discover_visa_resources(self._provider))
        except Exception as exc:
            self.failed.emit(str(exc))
        finally:
            self.done.emit()


class _ConnectionWorker(QObject):
    """장비 연결 요청을 UI thread 밖에서 수행한다."""

    started = Signal()
    finished = Signal(dict)
    failed = Signal(str)
    done = Signal()

    def __init__(
        self,
        *,
        client_factory: ClientFactory,
        owns_client: bool,
        commands: Any,
        tcp_host: str,
        tcp_port: int,
        config: EquipmentConnectionConfig,
    ) -> None:
        super().__init__()
        self._client_factory = client_factory
        self._owns_client = owns_client
        self._commands = commands
        self._tcp_host = tcp_host
        self._tcp_port = tcp_port
        self._config = config
        self._lock = threading.Lock()
        self._client: Any | None = None
        self._cancel_requested = False

    def cancel(self) -> None:
        """실행 중인 연결 작업에 취소를 요청하고 client를 닫는다."""

        with self._lock:
            self._cancel_requested = True
            client = self._client
        if self._owns_client:
            self._close_client(client)

    @Slot()
    def run(self) -> None:
        client = None
        try:
            client = self._client_factory()
            with self._lock:
                self._client = client
                cancel_requested = self._cancel_requested
            if cancel_requested:
                return

            self.started.emit()
            connect_to = getattr(client, "connect_to", None)
            if connect_to is not None:
                connect_to(self._tcp_host, self._tcp_port)
            states = self._commands.connect_equipment(client, config=self._config)
            if self._is_cancel_requested():
                return
            self.finished.emit(dict(states))
        except Exception as exc:
            if self._is_cancel_requested():
                return
            logger.exception("장비 연결 실패")
            self.failed.emit(str(exc))
        finally:
            if self._owns_client:
                self._close_client(client)
            with self._lock:
                if self._client is client:
                    self._client = None
            self.done.emit()

    def _is_cancel_requested(self) -> bool:
        with self._lock:
            return self._cancel_requested

    def _close_client(self, client: Any | None) -> None:
        if client is None:
            return
        close = getattr(client, "close", None)
        if close is not None:
            close()


class _EquipmentSetWorker(QObject):
    """장비 Set 작업을 UI thread 밖에서 순차 실행한다."""

    started = Signal()
    step_changed = Signal(str)
    finished = Signal()
    failed = Signal(str)
    done = Signal()

    def __init__(
        self,
        *,
        client_factory: ClientFactory,
        owns_client: bool,
        commands: Any,
        tcp_host: str,
        tcp_port: int,
        timeout_s: float,
    ) -> None:
        super().__init__()
        self._client_factory = client_factory
        self._owns_client = owns_client
        self._commands = commands
        self._tcp_host = tcp_host
        self._tcp_port = tcp_port
        self._timeout_s = timeout_s
        self._lock = threading.Lock()
        self._client: Any | None = None
        self._cancel_requested = False

    def cancel(self) -> None:
        """실행 중인 장비 Set 작업에 취소를 요청하고 client를 닫는다."""

        with self._lock:
            self._cancel_requested = True
            client = self._client
        if self._owns_client:
            self._close_client(client)

    @Slot()
    def run(self) -> None:
        client = None
        try:
            client = self._client_factory()
            with self._lock:
                self._client = client
                cancel_requested = self._cancel_requested
            if cancel_requested:
                return

            self.started.emit()
            connect_to = getattr(client, "connect_to", None)
            if connect_to is not None:
                connect_to(self._tcp_host, self._tcp_port)
            if self._is_cancel_requested():
                return

            if not self._set_reference_co3000(client):
                return
            if not self._set_controller_3d_ant_pol_vertical(client):
                return
            if not self._self_align_fsv40(client):
                return

            self.finished.emit()
        except Exception as exc:
            if self._is_cancel_requested():
                return
            logger.exception("장비 Set 실패")
            self.failed.emit(f"장비 Set 실패: {exc}")
        finally:
            if self._owns_client:
                self._close_client(client)
            with self._lock:
                if self._client is client:
                    self._client = None
            self.done.emit()

    def _set_reference_co3000(self, client: Any) -> bool:
        if self._is_cancel_requested():
            return False
        self.step_changed.emit(CO3000_SET_REFERENCE_STEP_MESSAGE)
        instrument_set.discard_equipment_set_events(
            client,
            target="CO3000",
            complete_command=instrument_set.COMMAND_SET_REFERENCE_COMPLETE,
        )
        self._commands.set_reference_co3000(client)
        if self._is_cancel_requested():
            return False
        try:
            instrument_set.wait_for_equipment_set_event(
                client,
                target="CO3000",
                complete_command=instrument_set.COMMAND_SET_REFERENCE_COMPLETE,
                source_command="Set Reference",
                timeout_s=self._timeout_s,
                cancel_requested=self._is_cancel_requested,
                accept_buffered_events=True,
            )
            if self._is_cancel_requested():
                return False
        except instrument_set.InstrumentSetTimeoutError:
            self.failed.emit(CO3000_SET_REFERENCE_TIMEOUT_MESSAGE)
            return False
        except instrument_set.InstrumentSetError as exc:
            self.failed.emit(f"장비 Set 실패: {exc}")
            return False
        return True

    def _set_controller_3d_ant_pol_vertical(self, client: Any) -> bool:
        return self._set_ant_pol_vertical(
            client,
            step_message=CONTROLLER_3D_ANT_POL_VERTICAL_STEP_MESSAGE,
            input_path=InputPath.INPUT3,
            target_label="3D Controller",
        )

    def _set_ant_pol_vertical(
        self,
        client: Any,
        *,
        step_message: str,
        input_path: InputPath,
        target_label: str,
    ) -> bool:
        if self._is_cancel_requested():
            return False
        self.step_changed.emit(step_message)
        configured = self._commands.set_antenna_pol(
            client,
            pol=AntennaPol.V,
            input_path=input_path,
        )
        if self._is_cancel_requested():
            return False
        if not configured:
            self.failed.emit(
                f"장비 Set 실패: {target_label} Ant Pol Vertical returned false"
            )
            return False
        return True

    def _self_align_fsv40(self, client: Any) -> bool:
        if self._is_cancel_requested():
            return False
        self.step_changed.emit(FSV40_SELF_ALIGNMENT_STEP_MESSAGE)
        instrument_set.discard_equipment_set_events(
            client,
            target="FSV40",
            complete_command=instrument_set.COMMAND_SELF_ALIGNMENT_COMPLETE,
        )
        self._commands.self_align_fsv40(client)
        if self._is_cancel_requested():
            return False
        try:
            instrument_set.wait_for_equipment_set_event(
                client,
                target="FSV40",
                complete_command=instrument_set.COMMAND_SELF_ALIGNMENT_COMPLETE,
                source_command="Self Alignment",
                timeout_s=self._timeout_s,
                cancel_requested=self._is_cancel_requested,
                accept_buffered_events=True,
            )
            if self._is_cancel_requested():
                return False
        except instrument_set.InstrumentSetTimeoutError:
            self.failed.emit(FSV40_SELF_ALIGNMENT_TIMEOUT_MESSAGE)
            return False
        except instrument_set.InstrumentSetError as exc:
            self.failed.emit(f"장비 Set 실패: {exc}")
            return False
        return True

    def _is_cancel_requested(self) -> bool:
        with self._lock:
            return self._cancel_requested

    def _close_client(self, client: Any | None) -> None:
        if client is None:
            return
        close = getattr(client, "close", None)
        if close is not None:
            close()


class InstrumentConnectionService(QObject):
    """Instrument Check 패널에서 사용하는 비동기 서비스."""

    visa_resources_discovered = Signal(list)
    visa_discovery_failed = Signal(str)
    connection_started = Signal()
    connection_finished = Signal(dict)
    error_occurred = Signal(str)
    set_started = Signal()
    set_step_changed = Signal(str)
    set_finished = Signal()
    set_failed = Signal(str)
    equipment_disconnected = Signal(dict)

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        client: Any | None = None,
        client_factory: ClientFactory | None = None,
        commands: Any = default_commands,
        tcp_host: str = "127.0.0.1",
        tcp_port: int = 5025,
        visa_resource_provider: VisaResourceProvider | None = None,
        connection_guard: ConnectionGuard | None = None,
        instrument_set_timeout_s: float = 900.0,
    ) -> None:
        super().__init__(parent)
        if client is not None and client_factory is not None:
            raise ValueError("client and client_factory cannot be used together")
        self._owns_client = client is None
        self._client_factory = (
            (lambda: client)
            if client is not None
            else (client_factory or (lambda: TcpClient()))
        )
        self._commands = commands
        self._tcp_host = tcp_host
        self._tcp_port = tcp_port
        self._visa_resource_provider = visa_resource_provider
        self._connection_guard = connection_guard
        self._instrument_set_timeout_s = instrument_set_timeout_s
        self._discovery_thread: QThread | None = None
        self._connection_thread: QThread | None = None
        self._set_thread: QThread | None = None
        self._discovery_worker: _VisaDiscoveryWorker | None = None
        self._connection_worker: _ConnectionWorker | None = None
        self._set_worker: _EquipmentSetWorker | None = None
        self._shutting_down = False

    @property
    def is_connecting(self) -> bool:
        """장비 연결 worker가 실행 중인지 반환한다."""

        return self._connection_thread is not None

    @property
    def is_setting(self) -> bool:
        """장비 Set worker가 실행 중인지 반환한다."""

        return self._set_thread is not None

    def refresh_visa_resources(self) -> None:
        """VISA Resource 목록 탐색을 시작한다."""

        if self._shutting_down or self._discovery_thread is not None:
            return

        thread = QThread(self)
        worker = _VisaDiscoveryWorker(self._visa_resource_provider)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_visa_resources_discovered)
        worker.failed.connect(self._on_visa_discovery_failed)
        worker.done.connect(thread.quit, Qt.ConnectionType.DirectConnection)
        worker.done.connect(
            self._on_discovery_worker_done,
            Qt.ConnectionType.DirectConnection,
        )
        worker.done.connect(worker.deleteLater)
        thread.finished.connect(self._on_discovery_finished)
        thread.finished.connect(thread.deleteLater)
        self._discovery_thread = thread
        self._discovery_worker = worker
        thread.start()

    def connect_equipment(self, config: EquipmentConnectionConfig) -> None:
        """LabVIEW TCP 서버에 장비 연결 요청을 보낸다."""

        if self._shutting_down:
            return

        if self._connection_thread is not None:
            self.error_occurred.emit(CONNECTION_IN_PROGRESS_MESSAGE)
            return

        if self._set_thread is not None:
            self.error_occurred.emit(INSTRUMENT_SET_IN_PROGRESS_MESSAGE)
            return

        if self._connection_guard is not None:
            block_reason = self._connection_guard()
            if block_reason:
                self.error_occurred.emit(block_reason)
                return

        thread = QThread(self)
        worker = _ConnectionWorker(
            client_factory=self._client_factory,
            owns_client=self._owns_client,
            commands=self._commands,
            tcp_host=self._tcp_host,
            tcp_port=self._tcp_port,
            config=config,
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.started.connect(self._on_connection_started)
        worker.finished.connect(self._on_connection_worker_finished)
        worker.failed.connect(self._on_connection_failed)
        worker.done.connect(thread.quit, Qt.ConnectionType.DirectConnection)
        worker.done.connect(
            self._on_connection_worker_done,
            Qt.ConnectionType.DirectConnection,
        )
        worker.done.connect(worker.deleteLater)
        thread.finished.connect(self._on_connection_finished)
        thread.finished.connect(thread.deleteLater)
        self._connection_thread = thread
        self._connection_worker = worker
        thread.start()

    def set_equipment(self, equipment_state: dict[str, bool]) -> None:
        """연결 완료된 장비에 Set Reference / Self Alignment를 순차 요청한다."""

        if self._shutting_down:
            return

        if self._connection_thread is not None:
            self._emit_set_failed(CONNECTION_IN_PROGRESS_MESSAGE)
            return

        if self._set_thread is not None:
            self._emit_set_failed(INSTRUMENT_SET_IN_PROGRESS_MESSAGE)
            return

        if self._connection_guard is not None:
            block_reason = self._connection_guard()
            if block_reason:
                self._emit_set_failed(block_reason)
                return

        if not is_required_equipment_ready(equipment_state):
            self._emit_set_failed(
                "장비 Set 실패: " + describe_equipment_not_ready(equipment_state)
            )
            return

        thread = QThread(self)
        worker = _EquipmentSetWorker(
            client_factory=self._client_factory,
            owns_client=self._owns_client,
            commands=self._commands,
            tcp_host=self._tcp_host,
            tcp_port=self._tcp_port,
            timeout_s=self._instrument_set_timeout_s,
        )
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.started.connect(self._on_set_started)
        worker.step_changed.connect(self._on_set_step_changed)
        worker.finished.connect(self._on_set_worker_finished)
        worker.failed.connect(self._on_set_failed)
        worker.done.connect(thread.quit, Qt.ConnectionType.DirectConnection)
        worker.done.connect(
            self._on_set_worker_done,
            Qt.ConnectionType.DirectConnection,
        )
        worker.done.connect(worker.deleteLater)
        thread.finished.connect(self._on_set_thread_finished)
        thread.finished.connect(thread.deleteLater)
        self._set_thread = thread
        self._set_worker = worker
        thread.start()

    def shutdown(self) -> None:
        """패널 종료 시 실행 중인 worker thread를 정리한다."""

        if self._shutting_down:
            return
        self._shutting_down = True

        if self._connection_worker is not None:
            self._connection_worker.cancel()
        if self._set_worker is not None:
            self._set_worker.cancel()

        self._detach_worker_signals()

        for thread in (
            self._discovery_thread,
            self._connection_thread,
            self._set_thread,
        ):
            if thread is None:
                continue
            thread.quit()
            if not thread.wait(1000):
                logger.error("Instrument worker thread did not stop cleanly")
                thread.setParent(None)
                _DETACHED_THREADS.append(thread)
                thread.finished.connect(
                    lambda thread=thread: _delete_detached_thread(thread),
                )
            else:
                thread.deleteLater()

        self._discovery_thread = None
        self._connection_thread = None
        self._set_thread = None
        self._discovery_worker = None
        self._connection_worker = None
        self._set_worker = None

    @Slot(list)
    def _on_visa_resources_discovered(self, resources: list[str]) -> None:
        if not self._shutting_down:
            self.visa_resources_discovered.emit(resources)

    @Slot(str)
    def _on_visa_discovery_failed(self, message: str) -> None:
        if not self._shutting_down:
            self.visa_discovery_failed.emit(message)

    @Slot()
    def _on_connection_started(self) -> None:
        if not self._shutting_down:
            self.connection_started.emit()

    @Slot(dict)
    def _on_connection_worker_finished(self, states: dict[str, bool]) -> None:
        if not self._shutting_down:
            self.connection_finished.emit(states)

    @Slot(str)
    def _on_connection_failed(self, message: str) -> None:
        if not self._shutting_down:
            self.error_occurred.emit(message)

    @Slot()
    def _on_set_started(self) -> None:
        if not self._shutting_down:
            self.set_started.emit()

    @Slot(str)
    def _on_set_step_changed(self, message: str) -> None:
        if not self._shutting_down:
            self.set_step_changed.emit(message)

    @Slot()
    def _on_set_worker_finished(self) -> None:
        if not self._shutting_down:
            self.set_finished.emit()

    @Slot(str)
    def _on_set_failed(self, message: str) -> None:
        if not self._shutting_down:
            self._emit_set_failed(message)
            self.equipment_disconnected.emit(disconnected_equipment_state())

    def _emit_set_failed(self, message: str) -> None:
        if not self._shutting_down:
            self.set_failed.emit(message)

    def _detach_worker_signals(self) -> None:
        if self._discovery_worker is not None:
            _disconnect_safely(
                self._discovery_worker.finished,
                self._on_visa_resources_discovered,
            )
            _disconnect_safely(
                self._discovery_worker.failed,
                self._on_visa_discovery_failed,
            )
            _disconnect_safely(
                self._discovery_worker.done,
                self._on_discovery_worker_done,
            )

        if self._connection_worker is not None:
            _disconnect_safely(
                self._connection_worker.started,
                self._on_connection_started,
            )
            _disconnect_safely(
                self._connection_worker.finished,
                self._on_connection_worker_finished,
            )
            _disconnect_safely(
                self._connection_worker.failed,
                self._on_connection_failed,
            )
            _disconnect_safely(
                self._connection_worker.done,
                self._on_connection_worker_done,
            )

        if self._set_worker is not None:
            _disconnect_safely(
                self._set_worker.started,
                self._on_set_started,
            )
            _disconnect_safely(
                self._set_worker.step_changed,
                self._on_set_step_changed,
            )
            _disconnect_safely(
                self._set_worker.finished,
                self._on_set_worker_finished,
            )
            _disconnect_safely(
                self._set_worker.failed,
                self._on_set_failed,
            )
            _disconnect_safely(
                self._set_worker.done,
                self._on_set_worker_done,
            )

        if self._discovery_thread is not None:
            _disconnect_safely(
                self._discovery_thread.finished,
                self._on_discovery_finished,
            )
            _disconnect_safely(
                self._discovery_thread.finished,
                self._discovery_thread.deleteLater,
            )

        if self._connection_thread is not None:
            _disconnect_safely(
                self._connection_thread.finished,
                self._on_connection_finished,
            )
            _disconnect_safely(
                self._connection_thread.finished,
                self._connection_thread.deleteLater,
            )

        if self._set_thread is not None:
            _disconnect_safely(
                self._set_thread.finished,
                self._on_set_thread_finished,
            )
            _disconnect_safely(
                self._set_thread.finished,
                self._set_thread.deleteLater,
            )

    def _on_discovery_finished(self) -> None:
        self._discovery_thread = None

    def _on_discovery_worker_done(self) -> None:
        self._discovery_worker = None

    def _on_connection_finished(self) -> None:
        self._connection_thread = None

    def _on_connection_worker_done(self) -> None:
        self._connection_worker = None

    def _on_set_thread_finished(self) -> None:
        self._set_thread = None

    def _on_set_worker_done(self) -> None:
        self._set_worker = None
