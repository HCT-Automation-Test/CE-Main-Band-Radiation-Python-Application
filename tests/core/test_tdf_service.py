from __future__ import annotations

import threading
from typing import Any

from app.core.tdf_service import (
    TDF_OPERATION_IN_PROGRESS_MESSAGE,
    TdfService,
    _DETACHED_THREADS,
)


class _Commands:
    def __init__(self, *, release_timeout_s: float = 1.0) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.started = threading.Event()
        self.release = threading.Event()
        self.release_timeout_s = release_timeout_s

    def get_tdf_list(self, client: Any) -> list[str]:
        self.calls.append(("get_tdf_list", client))
        self.started.set()
        self.release.wait(self.release_timeout_s)
        return ["a.tdf", "b.tdf"]

    def tdf_all_off(self, client: Any) -> bool:
        self.calls.append(("tdf_all_off", client))
        self.started.set()
        return True

    def set_tdf(self, client: Any, *, tdf_file_name: str) -> bool:
        self.calls.append(("set_tdf", client, tdf_file_name))
        self.started.set()
        return True


def test_tdf_service_get_list_runs_async_and_emits_list(qtbot) -> None:
    client = object()
    commands = _Commands()
    service = TdfService(client=client, commands=commands)
    received: list[list[str]] = []
    service.tdf_list_received.connect(received.append)

    service.get_tdf_list()
    qtbot.waitUntil(commands.started.is_set, timeout=1000)

    with qtbot.waitSignal(service.operation_finished, timeout=1000):
        commands.release.set()
    qtbot.waitUntil(lambda: not service.is_running, timeout=1000)

    assert received == [["a.tdf", "b.tdf"]]
    assert commands.calls == [("get_tdf_list", client)]


def test_tdf_service_rejects_duplicate_operation(qtbot) -> None:
    commands = _Commands()
    service = TdfService(client=object(), commands=commands)

    service.get_tdf_list()
    qtbot.waitUntil(commands.started.is_set, timeout=1000)

    with qtbot.waitSignal(service.operation_failed, timeout=1000) as blocker:
        service.tdf_all_off()

    commands.release.set()
    qtbot.waitUntil(lambda: not service.is_running, timeout=1000)
    assert blocker.args == [TDF_OPERATION_IN_PROGRESS_MESSAGE]


def test_tdf_service_set_tdf_passes_file_name(qtbot) -> None:
    client = object()
    commands = _Commands()
    service = TdfService(client=client, commands=commands)

    with qtbot.waitSignal(service.operation_finished, timeout=1000):
        service.set_tdf("a.tdf")
    qtbot.waitUntil(lambda: not service.is_running, timeout=1000)

    assert commands.calls == [("set_tdf", client, "a.tdf")]


def test_tdf_service_shutdown_detaches_thread_when_worker_is_still_blocked(qtbot) -> None:
    commands = _Commands(release_timeout_s=5.0)
    service = TdfService(client=object(), commands=commands)
    detached_count = len(_DETACHED_THREADS)

    service.get_tdf_list()
    qtbot.waitUntil(commands.started.is_set, timeout=1000)

    service.shutdown()

    assert len(_DETACHED_THREADS) == detached_count + 1
    assert not service.is_running

    commands.release.set()
    qtbot.waitUntil(lambda: len(_DETACHED_THREADS) == detached_count, timeout=1000)
