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


def _default_ok() -> Response:
    return Response(id="response-id", status="ok")


def test_connect_equipment_sends_target_params_and_returns_state() -> None:
    client = _Client(
        _default_ok(),
        _default_ok(),
        _default_ok(),
        _default_ok(),
        _default_ok(),
    )
    config = commands.EquipmentConnectionConfig(
        fsv40_visa_resource="TCPIP0::192.168.0.2::inst0::INSTR",
        mt8000a_visa_resource="TCPIP0::192.168.0.3::inst0::INSTR",
        co3000_visa_resource="ASRL1::INSTR",
        controller_3d_visa_resource="ASRL2::INSTR",
        switch_box_ip_address="192.168.0.10",
        switch_box_port=5000,
    )

    assert commands.connect_equipment(
        client,
        config=config,
    ) == {
        "FSV40": True,
        "MT8000A": True,
        "CO3000": True,
        "Switch Box": True,
        "3D Controller": True,
    }
    assert client.calls == [
        ("FSV40", "Connect", {"VISA Resource": "TCPIP0::192.168.0.2::inst0::INSTR"}),
        ("MT8000A", "Connect", {"VISA Resource": "TCPIP0::192.168.0.3::inst0::INSTR"}),
        ("CO3000", "Connect", {"VISA Resource": "ASRL1::INSTR"}),
        ("Switch Box", "Connect", {"ip address": "192.168.0.10", "port": 5000}),
        ("3D Controller", "Connect", {"VISA Resource": "ASRL2::INSTR"}),
    ]


def test_connect_equipment_without_params_keeps_empty_param_compatibility() -> None:
    client = _Client(
        _default_ok(),
        _default_ok(),
        _default_ok(),
        _default_ok(),
        _default_ok(),
    )

    assert commands.connect_equipment(client) == {
        "FSV40": True,
        "MT8000A": True,
        "CO3000": True,
        "Switch Box": True,
        "3D Controller": True,
    }
    assert client.calls == [
        ("FSV40", "Connect", {}),
        ("MT8000A", "Connect", {}),
        ("CO3000", "Connect", {}),
        ("Switch Box", "Connect", {}),
        ("3D Controller", "Connect", {}),
    ]


def test_connect_equipment_with_config_sends_only_selected_visa_targets() -> None:
    client = _Client(_default_ok(), _default_ok())
    config = commands.EquipmentConnectionConfig(
        fsv40_visa_resource="TCPIP0::192.168.0.2::inst0::INSTR",
        mt8000a_visa_resource="",
        co3000_visa_resource="ASRL1::INSTR",
        controller_3d_visa_resource="",
        switch_box_ip_address="",
        switch_box_port=None,
    )

    assert commands.connect_equipment(client, config=config) == {
        "FSV40": True,
        "CO3000": True,
    }
    assert client.calls == [
        ("FSV40", "Connect", {"VISA Resource": "TCPIP0::192.168.0.2::inst0::INSTR"}),
        ("CO3000", "Connect", {"VISA Resource": "ASRL1::INSTR"}),
    ]


def test_connect_equipment_with_config_sends_switch_box_only_when_complete() -> None:
    client = _Client(_default_ok())
    config = commands.EquipmentConnectionConfig(
        fsv40_visa_resource="",
        mt8000a_visa_resource="",
        co3000_visa_resource="",
        controller_3d_visa_resource="",
        switch_box_ip_address="192.168.0.10",
        switch_box_port=5000,
    )

    assert commands.connect_equipment(client, config=config) == {"Switch Box": True}
    assert client.calls == [
        ("Switch Box", "Connect", {"ip address": "192.168.0.10", "port": 5000}),
    ]


def test_connect_equipment_raises_when_target_connect_returns_error() -> None:
    client = _Client(
        _default_ok(),
        Response(
            id="response-id",
            status="error",
            error={"message": "mt8000 failed"},
        ),
        _default_ok(),
    )

    with pytest.raises(commands.CommandError, match="MT8000A / Connect failed"):
        commands.connect_equipment(client)
    assert client.calls == [
        ("FSV40", "Connect", {}),
        ("MT8000A", "Connect", {}),
    ]


def test_setup_mt8000_sends_nr_call_params() -> None:
    client = _Client(_default_ok())

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
                "Band": 78,
                "BandWidth": 100,
                "Center Channel": 636666,
                "RB Size": 135,
                "RB Offset": 67,
                "Modulation": "QPSK",
                "Max Retry Count": 3,
                "Waiting Time": 5,
            },
        )
    ]


def test_setup_mt8000_sends_explicit_retry_and_waiting_time() -> None:
    client = _Client(_default_ok())

    assert commands.setup_mt8000(
        client,
        band=78,
        bw=100,
        modulation=Modulation.QPSK,
        rb_size=135,
        rb_offset=67,
        channel=636666,
        max_retry_count=7,
        waiting_time=11,
    ) is True
    assert client.calls == [
        (
            "MT8000A",
            "NR Call",
            {
                "Band": 78,
                "BandWidth": 100,
                "Center Channel": 636666,
                "RB Size": 135,
                "RB Offset": 67,
                "Modulation": "QPSK",
                "Max Retry Count": 7,
                "Waiting Time": 11,
            },
        )
    ]


def test_setup_mt8000_normalizes_pi_over_2_bpsk_modulation() -> None:
    client = _Client(_default_ok())

    assert commands.setup_mt8000(
        client,
        band=78,
        bw=100,
        modulation=Modulation.PI_OVER_2_BPSK,
        rb_size=135,
        rb_offset=67,
        channel=636666,
    ) is True
    assert client.calls[0][2]["Modulation"] == "PI/2 BPSK"


def test_call_handover_sends_nr_handover_params() -> None:
    client = _Client(_default_ok())

    assert commands.call_handover(
        client,
        mid_channel=636666,
        band=78,
        bw=100,
        modulation="256QAM",
        rb_size=135,
        rb_offset=67,
        channel=636666,
    ) is True
    assert client.calls == [
        (
            "MT8000A",
            "NR Handover",
            {
                "Mid Channel": 636666,
                "Band": 78,
                "BandWidth": 100,
                "Center Channel": 636666,
                "RB Size": 135,
                "RB Offset": 67,
                "Modulation": "256QAM",
            },
        )
    ]


def test_call_handover_sends_separate_mid_and_center_channel() -> None:
    client = _Client(_default_ok())

    assert commands.call_handover(
        client,
        mid_channel=636666,
        band=78,
        bw=100,
        modulation="256QAM",
        rb_size=135,
        rb_offset=67,
        channel=650000,
    ) is True
    assert client.calls[0][2]["Mid Channel"] == 636666
    assert client.calls[0][2]["Center Channel"] == 650000
    assert "Waiting Time" not in client.calls[0][2]
    assert "Max Retry Count" not in client.calls[0][2]


def test_set_reference_co3000_sends_default_params() -> None:
    client = _Client(_default_ok())

    assert commands.set_reference_co3000(client) is True
    assert client.calls == [("CO3000", "Set Reference", {})]


def test_self_align_fsv40_sends_default_params() -> None:
    client = _Client(_default_ok())

    assert commands.self_align_fsv40(client) is True
    assert client.calls == [("FSV40", "Self Alignment", {})]


def test_get_tdf_list_returns_file_names() -> None:
    client = _Client(_ok(**{"TDF File List": ["a.tdf", "b.tdf"]}))

    assert commands.get_tdf_list(client) == ["a.tdf", "b.tdf"]
    assert client.calls == [("FSV40", "Get TDF List", {})]


def test_get_tdf_list_rejects_non_list_result() -> None:
    client = _Client(_ok(**{"TDF File List": "a.tdf,b.tdf"}))

    with pytest.raises(commands.CommandError, match="TDF File List must be a list"):
        commands.get_tdf_list(client)


def test_get_tdf_list_rejects_missing_result_object() -> None:
    client = _Client(_default_ok())

    with pytest.raises(commands.CommandError, match="Result must be an object"):
        commands.get_tdf_list(client)


def test_get_tdf_list_rejects_non_string_items() -> None:
    client = _Client(_ok(**{"TDF File List": ["a.tdf", 7]}))

    with pytest.raises(
        commands.CommandError,
        match="TDF File List must contain only strings",
    ):
        commands.get_tdf_list(client)


def test_tdf_all_off_sends_default_params() -> None:
    client = _Client(_default_ok())

    assert commands.tdf_all_off(client) is True
    assert client.calls == [("FSV40", "TDF All Off", {})]


def test_set_tdf_sends_file_name_param() -> None:
    client = _Client(_default_ok())

    assert commands.set_tdf(client, tdf_file_name="a.tdf") is True
    assert client.calls == [("FSV40", "Set TDF", {"TDF File Name": "a.tdf"})]


@pytest.mark.parametrize(
    ("facade", "target", "command"),
    [
        (commands.set_reference_co3000, "CO3000", "Set Reference"),
        (commands.self_align_fsv40, "FSV40", "Self Alignment"),
        (commands.tdf_all_off, "FSV40", "TDF All Off"),
    ],
)
def test_instrument_set_commands_raise_on_error_response(
    facade: Any,
    target: str,
    command: str,
) -> None:
    client = _Client(
        Response(
            id="response-id",
            status="error",
            error={"message": "set failed"},
        )
    )

    with pytest.raises(commands.CommandError, match=f"{target} / {command} failed"):
        facade(client)
    assert client.calls == [(target, command, {})]


def test_setup_sa_sends_range_setting_params() -> None:
    client = _Client(_default_ok())

    assert commands.setup_sa(client, RANGE_6) is True

    assert client.calls == [
        (
            "FSV40",
            "Load SA Range Setting",
            {
                "SA Range Param": {
                    "Start Frequency": 6000.0,
                    "Stop Frequency": 18000.0,
                    "RBW": 1.0,
                    "VBW": 3.0,
                    "Sweep Point": 30001,
                    "Limit": -30.0,
                },
            },
        )
    ]


def test_setup_sa_startup_levels_sends_level_setting_params() -> None:
    client = _Client(_default_ok())

    assert commands.setup_sa_startup_levels(
        client,
        atten_level_db=1.5,
        next_peak_search_level_db=-20,
    ) is True

    assert client.calls == [
        (
            "FSV40",
            "Load SA Level Setting",
            {
                "SA Level Param": {
                    "Atten Level": 1.5,
                    "Next Peak Search Level": -20.0,
                },
            },
        )
    ]


def test_setup_sa_startup_levels_raises_on_error_response() -> None:
    client = _Client(
        Response(
            id="response-id",
            status="error",
            error={"message": "invalid level"},
        )
    )

    with pytest.raises(
        commands.CommandError,
        match="FSV40 / Load SA Level Setting failed",
    ):
        commands.setup_sa_startup_levels(
            client,
            atten_level_db=0,
            next_peak_search_level_db=-20,
        )


def test_measure_fundamental_returns_frequency() -> None:
    client = _Client(_ok(**{"Fundamental Frequency": 3550250000.0}))

    assert commands.measure_fundamental(client, target_freq=3550.0) == 3550.25
    assert client.calls == [
        (
            "FSV40",
            "Search Fundamental Frequency",
            {"Center Frequency": 3550.0},
        )
    ]


def test_measure_fundamental_rejects_non_numeric_frequency() -> None:
    client = _Client(_ok(**{"Fundamental Frequency": "3550.25"}))

    with pytest.raises(
        commands.CommandError,
        match=r"Result\.Fundamental Frequency must be a number",
    ):
        commands.measure_fundamental(client, target_freq=3550.0)


def test_measure_harmonics_returns_four_levels() -> None:
    client = _Client(_ok(Amplitude=[-42.1, -48, -51.0, -56.2]))

    assert commands.measure_harmonics(client, fundamental=3550.25) == [
        -42.1,
        -48.0,
        -51.0,
        -56.2,
    ]
    assert client.calls == [
        ("FSV40", "Mark Harmonic", {"Fundamental Frequency": 3550.25})
    ]


def test_set_switch_box_sends_input_then_filter() -> None:
    client = _Client(_default_ok(), _default_ok())

    assert commands.set_switch_box(
        client,
        input_path=InputPath.INPUT3,
        filter_path=FilterPath.HPF_6G,
    ) is True
    assert client.calls == [
        ("Switch Box", "Set Input", {"Input Path": 3}),
        ("Switch Box", "Set Filter", {"Filter Path": 6}),
    ]


def test_set_switch_box_raises_when_set_input_returns_error() -> None:
    client = _Client(
        Response(
            id="response-id",
            status="error",
            error={"message": "input failed"},
        ),
        _default_ok(),
    )

    with pytest.raises(commands.CommandError, match="Switch Box / Set Input failed"):
        commands.set_switch_box(
            client,
            input_path=InputPath.INPUT1,
            filter_path=FilterPath.THRU,
        )
    assert client.calls == [("Switch Box", "Set Input", {"Input Path": 1})]


def test_rotate_and_stop_turntable_send_co3000_commands() -> None:
    client = _Client(_default_ok(), _default_ok())

    commands.rotate_turntable(client, angle=360, turntable_speed=4)
    commands.stop_turntable(client)

    assert client.calls == [
        (
            "CO3000",
            "Move TurnTable",
            {
                "Turn Table Info": {
                    "Target Angle": 360.0,
                    "Turn Table Speed": 4,
                    "Fetch Interval": 10,
                },
            },
        ),
        ("CO3000", "Stop TurnTable", {}),
    ]


def test_check_call_status_returns_ok_and_connected() -> None:
    client = _Client(_ok(ok=True, connected=True))

    assert commands.check_call_status(client) is True
    assert client.calls == [("MT8000A", "Check Call Status", {})]


def test_check_call_status_returns_false_when_call_is_disconnected() -> None:
    client = _Client(_ok(ok=True, connected=False))

    assert commands.check_call_status(client) is False
    assert client.calls == [("MT8000A", "Check Call Status", {})]


def test_check_call_status_raises_when_status_check_failed() -> None:
    client = _Client(_ok(ok=False, connected=False))

    with pytest.raises(
        commands.CommandError,
        match="MT8000A / Check Call Status returned ok=false",
    ):
        commands.check_call_status(client)


def test_set_antenna_pol_routes_by_input_path() -> None:
    co3000_client = _Client(_default_ok())
    controller_client = _Client(_default_ok())

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


def test_default_response_without_result_is_success() -> None:
    client = _Client(Response(id="response-id", status="ok"))

    assert commands.setup_mt8000(
        client,
        band=78,
        bw=100,
        modulation=Modulation.QPSK,
        rb_size=135,
        rb_offset=67,
        channel=636666,
    ) is True


def test_measurement_command_missing_result_still_raises_command_error() -> None:
    client = _Client(Response(id="response-id", status="ok"))

    with pytest.raises(commands.CommandError, match="Result must be an object"):
        commands.measure_fundamental(client, target_freq=3550.0)


def test_none_returning_command_raises_when_status_is_error() -> None:
    client = _Client(
        Response(
            id="response-id",
            status="error",
            error={"message": "move failed"},
        )
    )

    with pytest.raises(commands.CommandError, match="CO3000 / Move TurnTable failed"):
        commands.rotate_turntable(client, angle=0, turntable_speed=6)


def test_measure_harmonics_rejects_wrong_level_count() -> None:
    client = _Client(_ok(Amplitude=[-42.0, -43.0, -44.0]))

    with pytest.raises(commands.CommandError, match="must contain 4 values"):
        commands.measure_harmonics(client, fundamental=3550.25)


def test_measure_harmonics_rejects_non_list_amplitude() -> None:
    client = _Client(_ok(Amplitude="-42.0,-43.0,-44.0,-45.0"))

    with pytest.raises(
        commands.CommandError,
        match=r"Result\.Amplitude must be a list",
    ):
        commands.measure_harmonics(client, fundamental=3550.25)
