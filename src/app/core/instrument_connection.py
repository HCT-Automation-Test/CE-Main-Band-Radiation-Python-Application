"""Instrument Check 연결/탐색 서비스."""
from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Sequence
from typing import Any

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot

from app.net import commands as default_commands
from app.net.commands import EquipmentConnectionConfig
from app.net.tcp_client import TcpClient

logger = logging.getLogger(__name__)
_DETACHED_THREADS: list[QThread] = []

VisaResourceProvider = Callable[[], Sequence[str]]
ClientFactory = Callable[[], Any]


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


class InstrumentConnectionService(QObject):
    """Instrument Check 패널에서 사용하는 비동기 서비스."""

    visa_resources_discovered = Signal(list)
    visa_discovery_failed = Signal(str)
    connection_started = Signal()
    connection_finished = Signal(dict)
    error_occurred = Signal(str)

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
        self._discovery_thread: QThread | None = None
        self._connection_thread: QThread | None = None
        self._discovery_worker: _VisaDiscoveryWorker | None = None
        self._connection_worker: _ConnectionWorker | None = None
        self._shutting_down = False

    @property
    def is_connecting(self) -> bool:
        """장비 연결 worker가 실행 중인지 반환한다."""

        return self._connection_thread is not None

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
            self.error_occurred.emit("장비 연결 요청이 이미 진행 중입니다.")
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

    def shutdown(self) -> None:
        """패널 종료 시 실행 중인 worker thread를 정리한다."""

        if self._shutting_down:
            return
        self._shutting_down = True

        if self._connection_worker is not None:
            self._connection_worker.cancel()

        self._detach_worker_signals()

        for thread in (self._discovery_thread, self._connection_thread):
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
        self._discovery_worker = None
        self._connection_worker = None

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

    def _on_discovery_finished(self) -> None:
        self._discovery_thread = None

    def _on_discovery_worker_done(self) -> None:
        self._discovery_worker = None

    def _on_connection_finished(self) -> None:
        self._connection_thread = None

    def _on_connection_worker_done(self) -> None:
        self._connection_worker = None
