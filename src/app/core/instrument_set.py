"""Instrument Set 완료 event 대기 유틸리티."""
from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import Qt

logger = logging.getLogger(__name__)

COMMAND_SET_REFERENCE_COMPLETE = "set_reference_complete"
COMMAND_SELF_ALIGNMENT_COMPLETE = "self_alignment_complete"
COMMAND_EQUIPMENT_ERROR = "equipment_error"

_POLL_INTERVAL_S = 0.05


class InstrumentSetTimeoutError(TimeoutError):
    """Instrument Set 완료 event 대기 timeout."""


class InstrumentSetError(RuntimeError):
    """Instrument Set 실패 event 수신."""


def wait_for_equipment_set_event(
    client: Any,
    *,
    target: str,
    complete_command: str,
    source_command: str,
    timeout_s: float,
    cancel_requested: Callable[[], bool] | None = None,
    accept_buffered_events: bool = False,
) -> None:
    """Instrument Set 명령 접수 후 완료/실패 event를 기다린다."""

    completed = threading.Event()
    lock = threading.Lock()
    failed_message: str | None = None

    def is_target_event(event: Any) -> bool:
        return (
            getattr(event, "target", None) == target
            and getattr(event, "command", None)
            in {complete_command, COMMAND_EQUIPMENT_ERROR}
        )

    def handle_event(event: Any) -> None:
        nonlocal failed_message
        if not is_target_event(event):
            return

        command = getattr(event, "command", None)
        if command == complete_command:
            completed.set()
            return
        if command == COMMAND_EQUIPMENT_ERROR:
            with lock:
                failed_message = _error_message(event, target, source_command)
            completed.set()

    def drain_buffered_events() -> None:
        pop_events = getattr(client, "pop_events", None)
        if pop_events is None:
            return
        try:
            events = list(pop_events(is_target_event))
        except Exception as exc:
            logger.warning("TCP event buffer read failed: %s", exc)
            return
        for event in events:
            handle_event(event)

    client.event_received.connect(handle_event, Qt.ConnectionType.DirectConnection)
    try:
        deadline = time.monotonic() + float(timeout_s)
        if accept_buffered_events:
            drain_buffered_events()
        else:
            discard_equipment_set_events(
                client,
                target=target,
                complete_command=complete_command,
            )
        while not completed.wait(_POLL_INTERVAL_S):
            if cancel_requested is not None and cancel_requested():
                return
            drain_buffered_events()
            if completed.is_set():
                break
            if time.monotonic() >= deadline:
                raise InstrumentSetTimeoutError(
                    f"{target} / {source_command} completion timeout"
                )

        with lock:
            message = failed_message
        if message is not None:
            raise InstrumentSetError(message)
    finally:
        try:
            client.event_received.disconnect(handle_event)
        except (RuntimeError, TypeError):
            pass


def discard_equipment_set_events(
    client: Any,
    *,
    target: str,
    complete_command: str,
) -> None:
    """Instrument Set 명령 전 남아 있는 이전 완료/실패 event를 제거한다."""

    pop_events = getattr(client, "pop_events", None)
    if pop_events is None:
        return
    try:
        pop_events(
            lambda event: getattr(event, "target", None) == target
            and getattr(event, "command", None)
            in {complete_command, COMMAND_EQUIPMENT_ERROR}
        )
    except Exception as exc:
        logger.warning("TCP event buffer discard failed: %s", exc)


def _error_message(event: Any, target: str, source_command: str) -> str:
    params = getattr(event, "params", {}) or {}
    if isinstance(params, dict):
        message = params.get("message")
        if message:
            return f"{target} / {source_command} failed: {message}"
    return f"{target} / {source_command} failed"
