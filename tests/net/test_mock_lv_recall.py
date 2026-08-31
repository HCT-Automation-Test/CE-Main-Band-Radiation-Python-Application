from __future__ import annotations

import pytest

from app.net.mock_lv_server import MockLvServer
from app.net.protocol import Request


def _recall_request(params: dict[str, object]) -> Request:
    return Request(
        id="request-id",
        target="MT8000A",
        command="Recall Param",
        params=params,
    )


def test_mock_recall_param_stores_name_and_restores_call_state(tmp_path) -> None:
    server = MockLvServer(temp_dir=tmp_path)

    response = server._handle_request(
        _recall_request({"Recall Name": "NR_N78_SA.recall"})
    )

    assert response.status == "ok"
    assert response.result is None
    assert server.state.last_recall_name == "NR_N78_SA.recall"
    assert server.state.call_connected is True


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"Recall Name": ""},
        {"Recall Name": 123},
        {"Recall Name": "NR_N78_SA.recall", "Unexpected": True},
    ],
)
def test_mock_recall_param_rejects_invalid_params_without_state_change(
    tmp_path,
    params: dict[str, object],
) -> None:
    server = MockLvServer(temp_dir=tmp_path)
    server.state.last_recall_name = "previous.recall"
    server.state.call_connected = False

    response = server._handle_request(_recall_request(params))

    assert response.status == "error"
    assert response.result is None
    assert set(response.error) == {"message"}
    assert server.state.last_recall_name == "previous.recall"
    assert server.state.call_connected is False


def test_mock_recall_param_error_scenario_preserves_state(tmp_path) -> None:
    server = MockLvServer(temp_dir=tmp_path, scenario="recall-param-error")
    server.state.last_recall_name = "previous.recall"
    server.state.call_connected = False

    response = server._handle_request(
        _recall_request({"Recall Name": "NR_N78_SA.recall"})
    )

    assert response.status == "error"
    assert response.error == {"message": "Recall Param failed: equipment error"}
    assert server.state.last_recall_name == "previous.recall"
    assert server.state.call_connected is False
