from __future__ import annotations

from typing import Any

import pytest

from app.models.enums import AntennaPol, FilterPath, InputPath, Modulation
from app.models.test_range import RANGE_6
from app.net import commands
from app.net.protocol import Response


class _Client:
    def __init__(self, *responses: Response) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, str, dict[str, Any]]] = []

    def send_request(
        self,
        target: str,
        command: str,
        params: dict[str, Any] | None = None,
    ) -> Response:
        self.calls.append((target, command, params or {}))
        return self.responses.pop(0)


def _ok(**result: Any) -> Response:
    return Response(id="response-id", status="ok", result=result)


def test_connect_equipment_connects_all_targets_and_returns_state() -> None:
    client = _Client(
        _ok(ok=True),
        _ok(ok=True),
        _ok(ok=True),
        _ok(ok=False),
        _ok(ok=True),
    )

    assert commands.connect_equipment(client) == {
        "FSV40": True,
        "MT8000A": True,
        "CO3000": True,
        "Switch Box": False,
        "3D Controller": True,
    }
    assert client.calls == [
        ("FSV40", "Connect", {}),
        ("MT8000A", "Connect", {}),
        ("CO3000", "Connect", {}),
        ("Switch Box", "Connect", {}),
        ("3D Controller", "Connect", {}),
    ]


def test_setup_mt8000_sends_nr_call_params() -> None:
    client = _Client(_ok(ok=True))

    result = commands.setup_mt8000(
        client,
        band=78,
        bw=100,
        modulation=Modulation.QPSK,
        rb_size=135,
        rb_offset=67,
        channel=636666,
    )

    assert result is True
    assert client.calls == [
        (
            "MT8000A",
            "NR Call",
            {
                "band": 78,
                "bw": 100,
                "modulation": "QPSK",
                "rb_size": 135,
                "rb_offset": 67,
                "channel": 636666,
            },
        )
    ]


def test_setup_sa_sends_range_setting_params() -> None:
    client = _Client(_ok(ok=True))

    assert commands.setup_sa(client, RANGE_6) is True

    assert client.calls == [
        (
            "FSV40",
            "Load SA Range Setting",
            {
                "range_id": 6,
                "range_name": "range_6",
                "start_freq_mhz": 6000.0,
                "stop_freq_mhz": 18000.0,
                "rbw_mhz": 1.0,
                "vbw_mhz": 3.0,
                "limit_dbm": -30.0,
                "sweep_point": 30001,
            },
        )
    ]


def test_measure_fundamental_returns_frequency() -> None:
    client = _Client(_ok(frequency_mhz=3550.25))

    assert commands.measure_fundamental(client, target_freq=3550.0) == 3550.25
    assert client.calls == [
        (
            "FSV40",
            "Search Fundamental Frequency",
            {"target_freq_mhz": 3550.0},
        )
    ]


def test_measure_harmonics_returns_four_levels() -> None:
    client = _Client(_ok(levels_dbm=[-42.1, -48, -51.0, -56.2]))

    assert commands.measure_harmonics(client, fundamental=3550.25) == [
        -42.1,
        -48.0,
        -51.0,
        -56.2,
    ]
    assert client.calls == [
        ("FSV40", "Mark Harmonic", {"fundamental_mhz": 3550.25})
    ]


def test_set_switch_box_sends_input_then_filter() -> None:
    client = _Client(_ok(ok=True), _ok(ok=True))

    assert commands.set_switch_box(
        client,
        input_path=InputPath.INPUT3,
        filter_path=FilterPath.HPF_6G,
    ) is True
    assert client.calls == [
        ("Switch Box", "Set Input", {"input_path": 3}),
        ("Switch Box", "Set Filter", {"filter_path": 6}),
    ]


def test_set_switch_box_stops_when_set_input_returns_false() -> None:
    client = _Client(_ok(ok=False), _ok(ok=True))

    assert commands.set_switch_box(
        client,
        input_path=InputPath.INPUT1,
        filter_path=FilterPath.THRU,
    ) is False
    assert client.calls == [("Switch Box", "Set Input", {"input_path": 1})]


def test_rotate_and_stop_turntable_send_co3000_commands() -> None:
    client = _Client(_ok(ok=True), _ok(ok=True))

    commands.rotate_turntable(client, angle=360, turntable_speed=4)
    commands.stop_turntable(client)

    assert client.calls == [
        (
            "CO3000",
            "Move TurnTable",
            {"angle": 360.0, "turntable_speed": 4},
        ),
        ("CO3000", "Stop TurnTable", {}),
    ]


def test_check_call_status_returns_ok_and_connected() -> None:
    client = _Client(_ok(ok=True, connected=True))

    assert commands.check_call_status(client) is True
    assert client.calls == [("MT8000A", "Check Call Status", {})]


def test_set_antenna_pol_routes_by_input_path() -> None:
    co3000_client = _Client(_ok(ok=True))
    controller_client = _Client(_ok(ok=True))

    assert commands.set_antenna_pol(
        co3000_client,
        pol=AntennaPol.H,
        input_path=InputPath.INPUT1,
    ) is True
    assert commands.set_antenna_pol(
        controller_client,
        pol=AntennaPol.V,
        input_path=InputPath.INPUT3,
    ) is True

    assert co3000_client.calls == [
        ("CO3000", "Change Ant Pol", {"pol": "H"})
    ]
    assert controller_client.calls == [
        ("3D Controller", "Change Ant Pol", {"pol": "V"})
    ]


def test_status_error_raises_command_error() -> None:
    client = _Client(
        Response(
            id="response-id",
            status="error",
            error={"message": "failed"},
        )
    )

    with pytest.raises(commands.CommandError, match="MT8000A / NR Call failed"):
        commands.setup_mt8000(
            client,
            band=78,
            bw=100,
            modulation=Modulation.QPSK,
            rb_size=135,
            rb_offset=67,
            channel=636666,
        )


def test_missing_result_raises_command_error() -> None:
    client = _Client(Response(id="response-id", status="ok"))

    with pytest.raises(commands.CommandError, match="Result must be an object"):
        commands.setup_mt8000(
            client,
            band=78,
            bw=100,
            modulation=Modulation.QPSK,
            rb_size=135,
            rb_offset=67,
            channel=636666,
        )


def test_invalid_ok_type_raises_command_error() -> None:
    client = _Client(_ok(ok="yes"))

    with pytest.raises(commands.CommandError, match="Result.ok must be a bool"):
        commands.setup_mt8000(
            client,
            band=78,
            bw=100,
            modulation=Modulation.QPSK,
            rb_size=135,
            rb_offset=67,
            channel=636666,
        )


def test_none_returning_command_raises_when_ok_is_false() -> None:
    client = _Client(_ok(ok=False))

    with pytest.raises(commands.CommandError, match="returned ok=false"):
        commands.rotate_turntable(client, angle=0, turntable_speed=6)


def test_measure_harmonics_rejects_wrong_level_count() -> None:
    client = _Client(_ok(levels_dbm=[-42.0, -43.0, -44.0]))

    with pytest.raises(commands.CommandError, match="must contain 4 values"):
        commands.measure_harmonics(client, fundamental=3550.25)
