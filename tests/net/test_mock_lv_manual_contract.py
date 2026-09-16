from __future__ import annotations

from typing import Any

import pytest

from app.net.mock_lv_server import MockLvServer
from app.net.protocol import Request


def _manual_request(
    command: str,
    params: dict[str, Any] | None = None,
    *,
    request_id: str = "manual-request",
) -> Request:
    return Request(
        id=request_id,
        target="FSV40",
        command=command,
        params=params or {},
    )


def test_mock_lv_server_manual_contract_updates_state_without_transport() -> None:
    server = MockLvServer()
    manual_params = {
        "Start Frequency": 30.0,
        "Stop Frequency": 1000.0,
        "RBW": 0.1,
        "VBW": 0.3,
        "Sweep Point": 10001,
        "Sweep Time": 0.1,
        "Atten Level": 10.0,
        "Detector Mode": "RMS",
        "Limit": -36.0,
    }
    requests = [
        _manual_request(
            "Load SA Manual Setting",
            {"SA Manual Param": manual_params},
            request_id="set",
        ),
        _manual_request("Preset", request_id="preset"),
        _manual_request(
            "Marker Auto Max",
            {"Marker Index": 1, "Excursion": 0.0},
            request_id="auto-max",
        ),
        _manual_request(
            "Marker set Center",
            {"Marker Index": 2, "Excursion": 0.0},
            request_id="center",
        ),
        _manual_request("Clear Trace", request_id="clear"),
    ]

    responses = [server._handle_request(request) for request in requests]

    assert [response.id for response in responses if response is not None] == [
        "set",
        "preset",
        "auto-max",
        "center",
        "clear",
    ]
    assert all(
        response is not None and response.status == "ok" for response in responses
    )
    assert server.state.last_manual_sa_params == manual_params
    assert server.state.preset_count == 1
    assert server.state.manual_marker_state == {
        1: {"action": "Marker Auto Max", "Excursion": 0.0},
        2: {"action": "Marker set Center", "Excursion": 0.0},
    }
    assert server.state.trace_clear_count == 1
    assert server.state.max_hold_enabled is True


@pytest.mark.parametrize(
    "params",
    [
        {
            "Start Frequency": 30.0,
            "Stop Frequency": 1000.0,
            "RBW": 0.1,
            "VBW": 0.3,
            "Sweep Point": 10001,
            "Sweep Time": 0.1,
            "Atten Level": 10.0,
            "Detector Mode": "RMS",
            "Limit": -36.0,
        },
        {"SA Range Param": {}},
        {"SA Manual Param": "invalid"},
    ],
)
def test_mock_lv_server_manual_contract_rejects_invalid_payload_without_state(
    params: dict[str, Any],
) -> None:
    server = MockLvServer()

    response = server._handle_request(
        _manual_request("Load SA Manual Setting", params)
    )

    assert response is not None
    assert response.status == "error"
    assert response.error == {"message": "invalid Load SA Manual Setting Params"}
    assert server.state.last_manual_sa_params is None


def test_mock_lv_server_manual_equipment_error_does_not_update_state() -> None:
    server = MockLvServer(scenario="manual-command-error")

    response = server._handle_request(_manual_request("Clear Trace"))

    assert response is not None
    assert response.status == "error"
    assert response.error == {"message": "mock manual command equipment error"}
    assert server.state.trace_clear_count == 0
    assert server.state.max_hold_enabled is False


def test_mock_lv_server_manual_no_response_can_follow_completed_action() -> None:
    server = MockLvServer(scenario="manual-command-no-response")

    response = server._handle_request(_manual_request("Clear Trace"))

    assert response is None
    assert server.state.trace_clear_count == 1
    assert server.state.max_hold_enabled is True
