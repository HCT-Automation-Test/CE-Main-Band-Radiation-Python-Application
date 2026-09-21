from __future__ import annotations

from typing import Any

import pytest

from app.core.manual_test_service import (
    MANUAL_OPERATION_IN_PROGRESS_MESSAGE,
    MANUAL_SERVICE_SHUTTING_DOWN_MESSAGE,
    ManualTestCapabilities,
    ManualTestService,
    manual_test_capabilities,
)
from app.models.manual_test import ManualSaSettings


class _Commands:
    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []
        self.result = True
        self.error: Exception | None = None

    def _record(self, *call: object) -> bool:
        self.calls.append(call)
        if self.error is not None:
            raise self.error
        return self.result

    def setup_sa_manual(self, _client: Any, **params: object) -> bool:
        return self._record("setup_sa_manual", params)

    def preset_sa(self, _client: Any) -> bool:
        return self._record("preset_sa")

    def clear_trace(self, _client: Any) -> bool:
        return self._record("clear_trace")

    def marker_peak(self, _client: Any, **params: object) -> bool:
        return self._record("marker_peak", params)

    def marker_next(self, _client: Any, **params: object) -> bool:
        return self._record("marker_next", params)

    def marker_off(self, _client: Any, **params: object) -> bool:
        return self._record("marker_off", params)

    def marker_all_off(self, _client: Any) -> bool:
        return self._record("marker_all_off")

    def marker_auto_max(self, _client: Any, **params: object) -> bool:
        return self._record("marker_auto_max", params)

    def marker_set_center(self, _client: Any, **params: object) -> bool:
        return self._record("marker_set_center", params)


def _settings() -> ManualSaSettings:
    return ManualSaSettings(
        start_frequency_mhz=1000.0,
        stop_frequency_mhz=12750.0,
        rbw_mhz=1.0,
        vbw_mhz=3.0,
        sweep_point=30001,
        sweep_time_sec=0.1,
        saturation_time_sec=2.5,
        atten_level_db=0.0,
        detector_mode="RMS",
        limit_dbm=-30.0,
    )


def _run_fsv40_operation(
    service: ManualTestService,
    operation: str,
) -> bool:
    if operation == "set":
        return service.apply_sa_settings(_settings())
    if operation == "preset":
        return service.preset_sa()
    if operation == "trace_clear":
        return service.clear_trace()
    raise AssertionError(f"Unknown FSV40 operation: {operation}")


_FSV40_OPERATIONS = (
    (
        "set",
        "FSV40 Set",
        (
            "setup_sa_manual",
            {
                "start_frequency_mhz": 1000.0,
                "stop_frequency_mhz": 12750.0,
                "rbw_mhz": 1.0,
                "vbw_mhz": 3.0,
                "sweep_point": 30001,
                "sweep_time_sec": 0.1,
                "atten_level_db": 0.0,
                "detector_mode": "RMS",
                "limit_dbm": -30.0,
            },
        ),
        "Load SA Manual Setting returned false",
    ),
    ("preset", "FSV40 Preset", ("preset_sa",), "FSV40 Preset returned false"),
    ("trace_clear", "Trace Clear", ("clear_trace",), "Trace Clear returned false"),
)


def _run_marker_operation(
    service: ManualTestService,
    operation: str,
) -> bool:
    if operation == "peak":
        return service.marker_peak(2, 3.5)
    if operation == "next":
        return service.marker_next(2, 3.5)
    if operation == "off":
        return service.marker_off(2, 3.5)
    if operation == "all_off":
        return service.marker_all_off()
    if operation == "auto":
        return service.marker_auto_max(2)
    if operation == "center":
        return service.marker_set_center(2)
    raise AssertionError(f"Unknown Marker operation: {operation}")


_MARKER_OPERATIONS = (
    (
        "peak",
        "Marker Peak",
        ("marker_peak", {"marker_index": 2, "excursion": 3.5}),
        "Marker Peak returned false",
    ),
    (
        "next",
        "Marker Next",
        ("marker_next", {"marker_index": 2, "excursion": 3.5}),
        "Marker Next returned false",
    ),
    (
        "off",
        "Marker OFF",
        ("marker_off", {"marker_index": 2, "excursion": 3.5}),
        "Marker OFF returned false",
    ),
    (
        "all_off",
        "Marker ALL OFF",
        ("marker_all_off",),
        "Marker ALL OFF returned false",
    ),
    (
        "auto",
        "Marker Auto Max",
        ("marker_auto_max", {"marker_index": 2, "excursion": 0.0}),
        "Marker Auto Max returned false",
    ),
    (
        "center",
        "Marker to Center",
        ("marker_set_center", {"marker_index": 2, "excursion": 0.0}),
        "Marker to Center returned false",
    ),
)


@pytest.mark.parametrize(
    ("equipment_state", "expected"),
    [
        ({}, ManualTestCapabilities()),
        ({"FSV40": True}, ManualTestCapabilities(fsv40=True, marker=True)),
        ({"FSV40": False}, ManualTestCapabilities()),
        ({"CO3000": True, "3D Controller": True}, ManualTestCapabilities()),
    ],
)
def test_manual_capabilities_only_expose_fsv40(
    equipment_state: dict[str, bool],
    expected: ManualTestCapabilities,
) -> None:
    assert manual_test_capabilities(equipment_state) == expected


@pytest.mark.parametrize(
    ("operation", "operation_name", "expected_call", "_false_message"),
    _FSV40_OPERATIONS,
)
def test_manual_fsv40_command_runs_once_and_releases_state(
    operation: str,
    operation_name: str,
    expected_call: tuple[object, ...],
    _false_message: str,
) -> None:
    commands = _Commands()
    service = ManualTestService(client=object(), commands=commands)
    signals: list[tuple[object, ...]] = []
    service.running_changed.connect(lambda active: signals.append(("running", active)))
    service.operation_started.connect(
        lambda name: signals.append(
            ("started", name, service.is_running, service.current_operation)
        )
    )
    service.operation_finished.connect(
        lambda name: signals.append(("finished", name, service.is_running))
    )

    assert _run_fsv40_operation(service, operation)

    assert commands.calls == [expected_call]
    assert signals == [
        ("running", True),
        ("started", operation_name, True, operation_name),
        ("finished", operation_name, True),
        ("running", False),
    ]
    assert not service.is_running
    assert service.current_operation is None


@pytest.mark.parametrize(
    ("error", "error_message"),
    [
        (None, None),
        (RuntimeError("transport failed"), "transport failed"),
    ],
)
@pytest.mark.parametrize(
    ("operation", "operation_name", "expected_call", "false_message"),
    _FSV40_OPERATIONS,
)
def test_manual_fsv40_command_failure_releases_state(
    operation: str,
    operation_name: str,
    expected_call: tuple[object, ...],
    false_message: str,
    error: Exception | None,
    error_message: str | None,
) -> None:
    commands = _Commands()
    commands.result = False if error is None else True
    commands.error = error
    service = ManualTestService(client=object(), commands=commands)
    failures: list[tuple[str, str]] = []
    running: list[bool] = []
    service.operation_failed.connect(
        lambda name, detail: failures.append((name, detail))
    )
    service.running_changed.connect(running.append)

    assert not _run_fsv40_operation(service, operation)

    assert commands.calls == [expected_call]
    assert failures == [(operation_name, error_message or false_message)]
    assert running == [True, False]
    assert not service.is_running
    assert service.current_operation is None


def test_manual_service_rejects_reentrant_command() -> None:
    commands = _Commands()
    service = ManualTestService(client=object(), commands=commands)
    failures: list[tuple[str, str]] = []
    nested_results: list[bool] = []
    service.operation_failed.connect(
        lambda name, message: failures.append((name, message))
    )
    service.operation_started.connect(
        lambda _name: nested_results.append(service.preset_sa())
    )

    assert service.clear_trace()

    assert commands.calls == [("clear_trace",)]
    assert nested_results == [False]
    assert failures == [("FSV40 Preset", MANUAL_OPERATION_IN_PROGRESS_MESSAGE)]


@pytest.mark.parametrize(
    ("operation", "operation_name", "_expected_call", "_false_message"),
    _FSV40_OPERATIONS,
)
def test_manual_fsv40_guard_rejects_before_command(
    operation: str,
    operation_name: str,
    _expected_call: tuple[object, ...],
    _false_message: str,
) -> None:
    commands = _Commands()
    service = ManualTestService(
        client=object(),
        commands=commands,
        operation_guard=lambda: "다른 작업 진행 중",
    )
    failures: list[tuple[str, str]] = []
    service.operation_failed.connect(
        lambda name, message: failures.append((name, message))
    )

    assert not _run_fsv40_operation(service, operation)

    assert commands.calls == []
    assert failures == [(operation_name, "다른 작업 진행 중")]
    assert not service.is_running
    assert service.current_operation is None


def test_manual_service_shutdown_rejects_new_command() -> None:
    commands = _Commands()
    service = ManualTestService(client=object(), commands=commands)
    failures: list[tuple[str, str]] = []
    service.operation_failed.connect(
        lambda name, message: failures.append((name, message))
    )

    service.shutdown()

    assert not service.preset_sa()
    assert commands.calls == []
    assert failures == [("FSV40 Preset", MANUAL_SERVICE_SHUTTING_DOWN_MESSAGE)]


@pytest.mark.parametrize(
    ("operation", "operation_name", "expected_call", "_false_message"),
    _MARKER_OPERATIONS,
)
def test_manual_marker_command_runs_once_and_releases_state(
    operation: str,
    operation_name: str,
    expected_call: tuple[object, ...],
    _false_message: str,
) -> None:
    commands = _Commands()
    service = ManualTestService(client=object(), commands=commands)
    finished: list[str] = []
    service.operation_finished.connect(finished.append)

    assert _run_marker_operation(service, operation)

    assert commands.calls == [expected_call]
    assert finished == [operation_name]
    assert not service.is_running
    assert service.current_operation is None


@pytest.mark.parametrize(
    ("error", "error_message"),
    [
        (None, None),
        (RuntimeError("transport failed"), "transport failed"),
    ],
)
@pytest.mark.parametrize(
    ("operation", "operation_name", "expected_call", "false_message"),
    _MARKER_OPERATIONS,
)
def test_manual_marker_command_failure_releases_state(
    operation: str,
    operation_name: str,
    expected_call: tuple[object, ...],
    false_message: str,
    error: Exception | None,
    error_message: str | None,
) -> None:
    commands = _Commands()
    commands.result = False if error is None else True
    commands.error = error
    service = ManualTestService(client=object(), commands=commands)
    failures: list[tuple[str, str]] = []
    service.operation_failed.connect(
        lambda name, detail: failures.append((name, detail))
    )

    assert not _run_marker_operation(service, operation)

    assert commands.calls == [expected_call]
    assert failures == [(operation_name, error_message or false_message)]
    assert not service.is_running
    assert service.current_operation is None


@pytest.mark.parametrize(
    ("operation", "operation_name", "_expected_call", "_false_message"),
    _MARKER_OPERATIONS,
)
def test_manual_marker_guard_rejects_before_command(
    operation: str,
    operation_name: str,
    _expected_call: tuple[object, ...],
    _false_message: str,
) -> None:
    commands = _Commands()
    service = ManualTestService(
        client=object(),
        commands=commands,
        operation_guard=lambda: "다른 작업 진행 중",
    )
    failures: list[tuple[str, str]] = []
    service.operation_failed.connect(
        lambda name, message: failures.append((name, message))
    )

    assert not _run_marker_operation(service, operation)

    assert commands.calls == []
    assert failures == [(operation_name, "다른 작업 진행 중")]
    assert not service.is_running
    assert service.current_operation is None
