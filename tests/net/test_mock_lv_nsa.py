from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest

from app.net.mock_lv_server import MockLvServer
from app.net.protocol import Request


def _nsa_request(**overrides: Any) -> Request:
    params = {
        "Band": 78,
        "BandWidth": 100,
        "Center Channel": 636666,
        "RB Size": 135,
        "RB Offset": 67,
        "Modulation": "QPSK",
        "Anchor UL Channel": 18300,
        "Max Retry Count": 3,
        "Waiting Time": 5,
    }
    params.update(overrides)
    return Request(
        id="request-id",
        target="MT8000A",
        command="NSA Handover",
        params=params,
    )


def _state_snapshot(server: MockLvServer) -> tuple[Any, ...]:
    state = server.state
    return (
        state.call_connected,
        deepcopy(state.call_state_by_rem_dest),
        state.anchor_dl_channel,
        state.anchor_ul_channel,
        deepcopy(state.last_nsa_nr_params),
    )


def test_mock_nsa_handover_completes_anchor_change_from_existing_nsa_state(
    tmp_path,
) -> None:
    server = MockLvServer(temp_dir=tmp_path)
    server.state.call_connected = True
    server.state.call_state_by_rem_dest = {"8000A": 8, "8821C": 6}
    server.state.anchor_dl_channel = 1575
    server.state.anchor_ul_channel = 19575

    response = server._handle_request(_nsa_request())

    assert response.status == "ok"
    assert response.result is None
    assert response.error is None
    assert server.state.call_connected is True
    assert server.state.call_state_by_rem_dest == {"8000A": 8, "8821C": 6}
    assert server.state.anchor_dl_channel == 300
    assert server.state.anchor_ul_channel == 18300
    assert server.state.last_nsa_nr_params == {
        "Band": 78,
        "BandWidth": 100,
        "Center Channel": 636666,
        "RB Size": 135,
        "RB Offset": 67,
        "Modulation": "QPSK",
        "Max Retry Count": 3,
        "Waiting Time": 5,
    }


@pytest.mark.parametrize(
    ("scenario", "expected_states", "anchor_set", "message"),
    [
        (
            "nsa-scg-release-error",
            {"8000A": 9, "8821C": None},
            False,
            "NSA Handover failed at scg_release: equipment error",
        ),
        (
            "nsa-scg-release-timeout",
            {"8000A": 9, "8821C": None},
            False,
            "NSA Handover failed at scg_release: timeout",
        ),
        (
            "nsa-anchor-handover-error",
            {"8000A": 6, "8821C": 13},
            False,
            "NSA Handover failed at anchor_handover: equipment error",
        ),
        (
            "nsa-anchor-handover-timeout",
            {"8000A": 6, "8821C": 13},
            False,
            "NSA Handover failed at anchor_handover: timeout",
        ),
        (
            "nsa-anchor-profile-mismatch",
            {"8000A": 6, "8821C": 6},
            True,
            "NSA Handover failed at anchor_profile: mismatch",
        ),
        (
            "nsa-nr-call-error",
            {"8000A": 7, "8821C": 6},
            True,
            "NSA Handover failed at nr_call: equipment error",
        ),
        (
            "nsa-nr-call-timeout",
            {"8000A": 7, "8821C": 6},
            True,
            "NSA Handover failed at nr_call: timeout",
        ),
        (
            "nsa-final-status-timeout",
            {"8000A": 7, "8821C": 6},
            True,
            "NSA Handover failed at final_status: timeout",
        ),
    ],
)
def test_mock_nsa_handover_failure_preserves_partial_rem_dest_state(
    tmp_path,
    scenario: str,
    expected_states: dict[str, int | None],
    anchor_set: bool,
    message: str,
) -> None:
    server = MockLvServer(temp_dir=tmp_path, scenario=scenario)

    response = server._handle_request(_nsa_request())

    assert response.status == "error"
    assert response.result is None
    assert response.error == {"message": message}
    assert server.state.call_connected is False
    assert server.state.call_state_by_rem_dest == expected_states
    if anchor_set:
        assert (server.state.anchor_dl_channel, server.state.anchor_ul_channel) == (
            300,
            18300,
        )
    else:
        assert server.state.anchor_dl_channel is None
        assert server.state.anchor_ul_channel is None


@pytest.mark.parametrize(
    "nsa_request",
    [
        _nsa_request(**{"Anchor UL Channel": 36275}),
        _nsa_request(**{"Anchor DL Channel": 300}),
        _nsa_request(**{"BandWidth": "100"}),
        _nsa_request(**{"Unexpected Anchor Field": 1}),
    ],
)
def test_mock_nsa_handover_rejects_unsupported_anchor_or_invalid_payload_without_state_change(
    tmp_path,
    nsa_request: Request,
) -> None:
    server = MockLvServer(temp_dir=tmp_path)
    server.state.call_connected = True
    server.state.call_state_by_rem_dest = {"8000A": 8, "8821C": 6}
    server.state.anchor_dl_channel = 1575
    server.state.anchor_ul_channel = 19575
    server.state.last_nsa_nr_params = {"Band": 77}
    before = _state_snapshot(server)

    response = server._handle_request(nsa_request)

    assert response.status == "error"
    assert response.result is None
    assert set(response.error) == {"message"}
    assert _state_snapshot(server) == before
