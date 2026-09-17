from __future__ import annotations

from typing import Any

import pytest

from app.models.enums import AntennaPol, FilterPath, InputPath, Modulation
from app.models.test_range import RANGE_6
from app.net import commands
from app.net.protocol import Response
from app.net.tcp_client import TcpClientTimeoutError


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


def test_connect_equipment_marks_target_false_and_continues_on_error_response() -> None:
    client = _Client(
        _default_ok(),
        Response(
            id="response-id",
            status="error",
            error={"message": "mt8000 failed"},
        ),
        _default_ok(),
        _default_ok(),
        _default_ok(),
    )

    assert commands.connect_equipment(client) == {
        "FSV40": True,
        "MT8000A": False,
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


def test_connect_equipment_raises_transport_errors() -> None:
    class _TransportClient:
        def send_request(self, target: str, command: str, params: dict[str, Any]) -> Response:
            _ = target, command, params
            raise RuntimeError("transport down")

    with pytest.raises(RuntimeError, match="transport down"):
        commands.connect_equipment(_TransportClient())


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


@pytest.mark.parametrize(
    ("bw", "expected_wire_value"),
    [
        (1.4, "1.4"),
        (3, "3"),
        (5.0, "5"),
        (10, "10"),
        (15.0, "15"),
        (20, "20"),
    ],
)
def test_setup_lte_mt8000_sends_canonical_bandwidth_string(
    bw: int | float,
    expected_wire_value: str,
) -> None:
    client = _Client(_default_ok())

    assert commands.setup_lte_mt8000(
        client,
        bw=bw,
        ul_channel=18300,
        rb_offset=24,
    ) is True
    assert client.calls == [
        (
            "MT8000A",
            "LTE Call",
            {
                "BandWidth": expected_wire_value,
                "UL Channel": 18300,
                "RB Offset": 24,
                "Max Retry Count": 3,
                "Waiting Time": 5,
            },
        )
    ]


@pytest.mark.parametrize(
    "bw",
    [1.3, 2, True, "10", float("nan"), float("inf"), float("-inf")],
)
def test_setup_lte_mt8000_rejects_invalid_bandwidth_before_send(bw: Any) -> None:
    client = _Client()

    with pytest.raises(ValueError, match="LTE bandwidth"):
        commands.setup_lte_mt8000(
            client,
            bw=bw,
            ul_channel=18300,
            rb_offset=24,
        )

    assert client.calls == []


def test_setup_lte_mt8000_raises_on_error_response() -> None:
    client = _Client(
        Response(id="response-id", status="error", error="call failed")
    )

    with pytest.raises(commands.CommandError, match="MT8000A / LTE Call failed"):
        commands.setup_lte_mt8000(
            client,
            bw=10,
            ul_channel=18300,
            rb_offset=24,
        )


def test_setup_nsa_mt8000_sends_flat_process_params() -> None:
    client = _Client(_default_ok())

    assert commands.setup_nsa_mt8000(
        client,
        band=78,
        bw=100,
        modulation=Modulation.QPSK,
        rb_size=135,
        rb_offset=67,
        channel=636666,
        anchor_ul_channel=18300,
    ) is True
    assert client.calls == [
        (
            "MT8000A",
            "NSA Call",
            {
                "Band": 78,
                "BandWidth": 100,
                "Center Channel": 636666,
                "RB Size": 135,
                "RB Offset": 67,
                "Modulation": "QPSK",
                "Anchor UL Channel": 18300,
                "Max Retry Count": 3,
                "Waiting Time": 5,
            },
        )
    ]


def test_setup_nsa_mt8000_normalizes_modulation_and_explicit_options() -> None:
    client = _Client(_default_ok())

    assert commands.setup_nsa_mt8000(
        client,
        band=78,
        bw=100,
        modulation=Modulation.PI_OVER_2_BPSK,
        rb_size=135,
        rb_offset=67,
        channel=640000,
        anchor_ul_channel=20525,
        max_retry_count=7,
        waiting_time=11,
    ) is True
    params = client.calls[0][2]
    assert params["Modulation"] == "PI/2 BPSK"
    assert params["Max Retry Count"] == 7
    assert params["Waiting Time"] == 11
    assert set(params) == {
        "Band",
        "BandWidth",
        "Center Channel",
        "RB Size",
        "RB Offset",
        "Modulation",
        "Anchor UL Channel",
        "Max Retry Count",
        "Waiting Time",
    }


@pytest.mark.parametrize("result", [None, "ignored", [1, 2], {"ok": False}])
def test_setup_nsa_mt8000_accepts_any_result_when_status_is_ok(result: Any) -> None:
    client = _Client(Response(id="response-id", status="ok", result=result))

    assert commands.setup_nsa_mt8000(
        client,
        band=78,
        bw=100,
        modulation="QPSK",
        rb_size=135,
        rb_offset=67,
        channel=636666,
        anchor_ul_channel=18300,
    ) is True


def test_setup_nsa_mt8000_raises_on_error_response() -> None:
    client = _Client(
        Response(id="response-id", status="error", error={"message": "call failed"})
    )

    with pytest.raises(commands.CommandError, match="MT8000A / NSA Call failed"):
        commands.setup_nsa_mt8000(
            client,
            band=78,
            bw=100,
            modulation="QPSK",
            rb_size=135,
            rb_offset=67,
            channel=636666,
            anchor_ul_channel=18300,
        )


def test_setup_nsa_mt8000_propagates_transport_timeout() -> None:
    class _TimeoutClient:
        def send_request(
            self, target: str, command: str, params: dict[str, Any]
        ) -> Response:
            _ = target, command, params
            raise TimeoutError("NSA Call timeout")

    with pytest.raises(TimeoutError, match="NSA Call timeout"):
        commands.setup_nsa_mt8000(
            _TimeoutClient(),
            band=78,
            bw=100,
            modulation="QPSK",
            rb_size=135,
            rb_offset=67,
            channel=636666,
            anchor_ul_channel=18300,
        )


def test_recall_param_sends_only_recall_name_and_returns_connected() -> None:
    client = _Client(_ok(ok=True, connected=True))

    assert commands.recall_param(client, recall_name="5GNR_SA_TDD") is True
    assert client.calls == [
        (
            "MT8000A",
            "Recall Param",
            {"Recall Name": "5GNR_SA_TDD"},
        )
    ]


def test_recall_param_returns_false_when_lv_reports_disconnected() -> None:
    client = _Client(_ok(ok=True, connected=False))

    assert commands.recall_param(client, recall_name="5GNR_SA_TDD") is False


def test_recall_param_raises_when_internal_call_check_failed() -> None:
    client = _Client(_ok(ok=False, connected=False))

    with pytest.raises(
        commands.CommandError,
        match="MT8000A / Recall Param returned ok=false",
    ):
        commands.recall_param(client, recall_name="5GNR_SA_TDD")


def test_recall_param_raises_default_error_message() -> None:
    client = _Client(
        Response(
            id="response-id",
            status="error",
            error={"message": "recall file not found"},
        )
    )

    with pytest.raises(commands.CommandError, match="recall file not found"):
        commands.recall_param(client, recall_name="MISSING_RECALL")


def test_recall_param_propagates_transport_timeout() -> None:
    class _TimeoutClient:
        def send_request(
            self,
            target: str,
            command: str,
            params: dict[str, Any],
        ) -> Response:
            _ = target, command, params
            raise TimeoutError("Recall Param timeout")

    with pytest.raises(TimeoutError, match="Recall Param timeout"):
        commands.recall_param(_TimeoutClient(), recall_name="5GNR_SA_TDD")


def test_lte_call_handover_sends_params() -> None:
    client = _Client(_default_ok())

    assert commands.lte_call_handover(
        client,
        bw=10.0,
        dl_channel=550,
        ul_channel=18550,
        rb_offset=49,
        max_retry_count=7,
        waiting_time=11,
    ) is True
    assert client.calls == [
        (
            "MT8000A",
            "LTE Handover",
            {
                "BandWidth": "10",
                "DL Channel": 550,
                "UL Channel": 18550,
                "RB Offset": 49,
                "Max Retry Count": 7,
                "Waiting Time": 11,
            },
        )
    ]


def test_call_handover_sends_nr_handover_params() -> None:
    client = _Client(_default_ok())

    assert commands.call_handover(
        client,
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
                "Band": 78,
                "BandWidth": 100,
                "Center Channel": 636666,
                "RB Size": 135,
                "RB Offset": 67,
                "Modulation": "256QAM",
                "Max Retry Count": 3,
                "Waiting Time": 5,
            },
        )
    ]


def test_call_handover_sends_current_center_channel_and_options() -> None:
    client = _Client(_default_ok())

    assert commands.call_handover(
        client,
        band=78,
        bw=100,
        modulation="256QAM",
        rb_size=135,
        rb_offset=67,
        channel=650000,
        max_retry_count=7,
        waiting_time=11,
    ) is True
    assert client.calls[0][2]["Center Channel"] == 650000
    assert client.calls[0][2]["Max Retry Count"] == 7
    assert client.calls[0][2]["Waiting Time"] == 11
    assert "Mid Channel" not in client.calls[0][2]
    assert "Wating Time" not in client.calls[0][2]
    assert "Max Retrey Count" not in client.calls[0][2]


def test_nsa_handover_sends_exact_default_params() -> None:
    client = _Client(_default_ok())

    assert commands.nsa_handover(
        client,
        band=78,
        bw=100,
        modulation=Modulation.QPSK,
        rb_size=135,
        rb_offset=67,
        channel=636666,
        anchor_ul_channel=18300,
    ) is True
    assert client.calls == [
        (
            "MT8000A",
            "NSA Handover",
            {
                "Band": 78,
                "BandWidth": 100,
                "Center Channel": 636666,
                "RB Size": 135,
                "RB Offset": 67,
                "Modulation": "QPSK",
                "Anchor UL Channel": 18300,
                "Max Retry Count": 3,
                "Waiting Time": 5,
            },
        )
    ]


def test_nsa_handover_normalizes_modulation_and_sends_explicit_options() -> None:
    client = _Client(_default_ok())

    assert commands.nsa_handover(
        client,
        band=78,
        bw=100,
        modulation=Modulation.PI_OVER_2_BPSK,
        rb_size=135,
        rb_offset=67,
        channel=640000,
        anchor_ul_channel=20525,
        max_retry_count=7,
        waiting_time=11,
    ) is True
    params = client.calls[0][2]
    assert params["Modulation"] == "PI/2 BPSK"
    assert params["Max Retry Count"] == 7
    assert params["Waiting Time"] == 11
    assert set(params) == {
        "Band",
        "BandWidth",
        "Center Channel",
        "RB Size",
        "RB Offset",
        "Modulation",
        "Anchor UL Channel",
        "Max Retry Count",
        "Waiting Time",
    }


@pytest.mark.parametrize("result", [None, "ignored", [1, 2], {"unexpected": True}])
def test_nsa_handover_accepts_any_result_when_status_is_ok(result: Any) -> None:
    client = _Client(Response(id="response-id", status="ok", result=result))

    assert commands.nsa_handover(
        client,
        band=78,
        bw=100,
        modulation="QPSK",
        rb_size=135,
        rb_offset=67,
        channel=636666,
        anchor_ul_channel=18300,
    ) is True


def test_nsa_handover_raises_when_status_is_error() -> None:
    client = _Client(
        Response(
            id="response-id",
            status="error",
            error={"message": "handover failed"},
        )
    )

    with pytest.raises(commands.CommandError, match="MT8000A / NSA Handover failed"):
        commands.nsa_handover(
            client,
            band=78,
            bw=100,
            modulation="QPSK",
            rb_size=135,
            rb_offset=67,
            channel=636666,
            anchor_ul_channel=18300,
        )


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
    client = _Client(
        _ok(
            Amplitude=[-42.1, -48, -51.0, -56.2],
            Frequency=[7100500000.0, 10650750000.0, 14201000000.0, 17751250000.0],
        )
    )

    markers = commands.measure_harmonics(client, fundamental=3550.25)
    assert [(marker.order, marker.amplitude_dbm, marker.peak_frequency_mhz) for marker in markers] == [
        (2, -42.1, 7100.5),
        (3, -48.0, 10650.75),
        (4, -51.0, 14201.0),
        (5, -56.2, 17751.25),
    ]
    assert client.calls == [
        ("FSV40", "Mark Harmonic", {"Fundamental Frequency": 3550.25})
    ]

def test_measure_harmonic_manual_uses_measure_harmonic() -> None:
    client = _Client(
        _ok(
            Amplitude=[-42.1, -48, -51.0, -56.2],
            Frequency=[7100500000.0, 10650750000.0, 14201000000.0, 17751250000.0],
        )
    )

    markers = commands.measure_harmonic_manual(client, fundamental=3550.25)

    assert [(marker.order, marker.amplitude_dbm, marker.peak_frequency_mhz) for marker in markers] == [
        (2, -42.1, 7100.5),
        (3, -48.0, 10650.75),
        (4, -51.0, 14201.0),
        (5, -56.2, 17751.25),
    ]
    assert client.calls == [
        ("FSV40", "Measure Harmonic", {"Fundamental Frequency": 3550.25})
    ]


def test_measure_inband_returns_amplitude() -> None:
    client = _Client(_ok(Amplitude=-42.1))

    assert commands.measure_inband(client, limit=-30.0) == -42.1
    assert client.calls == [
        ("FSV40", "Mark Inband", {"Limit": -30.0})
    ]

def test_measure_inband_manual_uses_measure_inband() -> None:
    client = _Client(_ok(Amplitude=-42.1))

    assert commands.measure_inband_manual(client, limit=-30.0) == -42.1
    assert client.calls == [
        ("FSV40", "Measure Inband", {"Limit": -30.0})
    ]


def test_manual_marker_commands_use_expected_protocol() -> None:
    client = _Client(_default_ok(), _default_ok(), _default_ok(), _default_ok(), _default_ok())

    assert commands.get_screenshot(client)
    assert commands.marker_peak(client, marker_index=2, excursion=6.5)
    assert commands.marker_next(client, marker_index=3, excursion=7.5)
    assert commands.marker_off(client, marker_index=4, excursion=8.5)
    assert commands.marker_all_off(client)

    assert client.calls == [
        ("FSV40", "Get Screenshot", {}),
        ("FSV40", "Marker Peak", {"Marker Index": 2, "Excursion": 6.5}),
        ("FSV40", "Marker Next", {"Marker Index": 3, "Excursion": 7.5}),
        ("FSV40", "Marker OFF", {"Marker Index": 4, "Excursion": 8.5}),
        ("FSV40", "Marker ALL OFF", {}),
    ]


def test_setup_sa_precision_sends_peak_frequency_and_sweep_time() -> None:
    client = _Client(_default_ok())

    assert commands.setup_sa_precision(
        client,
        peak_frequency=14088.35,
        sweep_time=100,
    )
    assert client.calls == [
        (
            "FSV40",
            "Load SA Precision Setting",
            {"Peak Frequency": 14088.35, "Sweep Time": 0.1},
        )
    ]


def test_measure_harmonic_precision_returns_amplitude() -> None:
    client = _Client(_ok(Amplitude=-28.7))

    assert commands.measure_harmonic_precision(client) == -28.7
    assert client.calls == [("FSV40", "Mark Precision", {})]


def test_measure_inband_rejects_missing_amplitude() -> None:
    client = _Client(_ok())

    with pytest.raises(
        commands.CommandError,
        match=r"Result\.Amplitude must be a number",
    ):
        commands.measure_inband(client, limit=-30.0)


def test_measure_inband_rejects_non_numeric_amplitude() -> None:
    client = _Client(_ok(Amplitude="-42.1"))

    with pytest.raises(
        commands.CommandError,
        match=r"Result\.Amplitude must be a number",
    ):
        commands.measure_inband(client, limit=-30.0)


def test_measure_bilog_uses_mark_inband_and_returns_amplitude() -> None:
    client = _Client(_ok(Amplitude=-47.2))

    assert commands.measure_bilog(client, limit=-46.0) == -47.2
    assert client.calls == [("FSV40", "Mark Inband", {"Limit": -46.0})]


def test_measure_bilog_rejects_missing_amplitude() -> None:
    client = _Client(_ok())

    with pytest.raises(
        commands.CommandError,
        match=r"Result\.Amplitude must be a number",
    ):
        commands.measure_bilog(client, limit=-46.0)


def test_measure_bilog_rejects_non_numeric_amplitude() -> None:
    client = _Client(_ok(Amplitude="-47.2"))

    with pytest.raises(
        commands.CommandError,
        match=r"Result\.Amplitude must be a number",
    ):
        commands.measure_bilog(client, limit=-46.0)


def test_set_switch_box_sends_set_path() -> None:
    client = _Client(_default_ok())

    assert commands.set_switch_box(
        client,
        input_path=InputPath.INPUT3,
        filter_path=FilterPath.HPF_6G,
    ) is True
    assert client.calls == [
        ("Switch Box", "Set Path", {"Input Path": 3, "Filter Path": 6}),
    ]


def test_set_switch_input_sends_input_only() -> None:
    client = _Client(_default_ok())

    assert commands.set_switch_input(client, input_path=InputPath.INPUT2) is True
    assert client.calls == [
        ("Switch Box", "Set Input", {"Input Path": 2}),
    ]


def test_set_switch_filter_sends_filter_only() -> None:
    client = _Client(_default_ok())

    assert commands.set_switch_filter(client, filter_path=FilterPath.PORT_14) is True
    assert client.calls == [
        ("Switch Box", "Set Filter", {"Filter Path": 20}),
    ]


def test_set_switch_box_raises_when_set_path_returns_error() -> None:
    client = _Client(
        Response(
            id="response-id",
            status="error",
            error={"message": "path failed"},
        ),
    )

    with pytest.raises(commands.CommandError, match="Switch Box / Set Path failed"):
        commands.set_switch_box(
            client,
            input_path=InputPath.INPUT1,
            filter_path=FilterPath.THRU,
        )
    assert client.calls == [
        ("Switch Box", "Set Path", {"Input Path": 1, "Filter Path": 1})
    ]


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


def test_get_turntable_angle_sends_co3000_command_and_returns_current_angle() -> None:
    client = _Client(_ok(**{"Current Angle": 270.5}))

    assert commands.get_turntable_angle(client) == 270.5
    assert client.calls == [("CO3000", "Get TurnTable Angle", {})]


@pytest.mark.parametrize(
    "result",
    [
        {},
        {"Current Angle": "270"},
        {"Current Angle": True},
        {"Current Angle": -0.1},
        {"Current Angle": 360.1},
        {"Current Angle": float("inf")},
    ],
)
def test_get_turntable_angle_rejects_invalid_current_angle(
    result: dict[str, Any],
) -> None:
    client = _Client(Response(id="response-id", status="ok", result=result))

    with pytest.raises(commands.CommandError, match="Current Angle"):
        commands.get_turntable_angle(client)


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
    co3000_client = _Client(_default_ok(), _default_ok())
    controller_client = _Client(_default_ok())

    assert commands.set_antenna_pol(
        co3000_client,
        pol=AntennaPol.H,
        input_path=InputPath.INPUT1,
    ) is True
    assert commands.set_antenna_pol(
        co3000_client,
        pol=AntennaPol.V,
        input_path=InputPath.INPUT2,
    ) is True
    assert commands.set_antenna_pol(
        controller_client,
        pol=AntennaPol.V,
        input_path=InputPath.INPUT3,
    ) is True

    assert co3000_client.calls == [
        ("CO3000", "Change Ant Pol", {"pol": "H", "Mast Index": 2}),
        ("CO3000", "Change Ant Pol", {"pol": "V", "Mast Index": 1}),
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
    client = _Client(
        _ok(
            Amplitude=[-42.0, -43.0, -44.0],
            Frequency=[7100500000.0, 10650750000.0, 14201000000.0, 17751250000.0],
        )
    )

    with pytest.raises(commands.CommandError, match="must contain 4 values"):
        commands.measure_harmonics(client, fundamental=3550.25)


def test_measure_harmonics_rejects_non_list_amplitude() -> None:
    client = _Client(
        _ok(
            Amplitude="-42.0,-43.0,-44.0,-45.0",
            Frequency=[7100500000.0, 10650750000.0, 14201000000.0, 17751250000.0],
        )
    )

    with pytest.raises(
        commands.CommandError,
        match=r"Result\.Amplitude must be a list",
    ):
        commands.measure_harmonics(client, fundamental=3550.25)


def test_measure_harmonics_rejects_missing_frequency() -> None:
    client = _Client(_ok(Amplitude=[-42.0, -43.0, -44.0, -45.0]))

    with pytest.raises(
        commands.CommandError,
        match=r"Result\.Frequency must be a list",
    ):
        commands.measure_harmonics(client, fundamental=3550.25)


def test_measure_harmonics_rejects_wrong_frequency_count() -> None:
    client = _Client(
        _ok(
            Amplitude=[-42.0, -43.0, -44.0, -45.0],
            Frequency=[7100500000.0, 10650750000.0, 14201000000.0],
        )
    )

    with pytest.raises(commands.CommandError, match="Frequency must contain 4 values"):
        commands.measure_harmonics(client, fundamental=3550.25)


def test_measure_harmonic_precision_rejects_missing_amplitude() -> None:
    client = _Client(_ok())

    with pytest.raises(
        commands.CommandError,
        match=r"Result\.Amplitude must be a number",
    ):
        commands.measure_harmonic_precision(client)


def test_manual_sa_and_action_facades_use_exact_protocol() -> None:
    client = _Client(*[_default_ok() for _ in range(5)])

    assert commands.setup_sa_manual(
        client,
        start_frequency_mhz=30.0,
        stop_frequency_mhz=1000.0,
        rbw_mhz=0.1,
        vbw_mhz=0.3,
        sweep_point=10001,
        sweep_time_sec=0.1,
        atten_level_db=10.0,
        detector_mode="RMS",
        limit_dbm=-36.0,
    )
    assert commands.preset_sa(client)
    assert commands.marker_auto_max(client, marker_index=1)
    assert commands.marker_set_center(client, marker_index=2)
    assert commands.clear_trace(client)

    assert client.calls == [
        (
            "FSV40",
            "Load SA Manual Setting",
            {
                "SA Manual Param": {
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
            },
        ),
        ("FSV40", "Preset", {}),
        ("FSV40", "Marker Auto Max", {"Marker Index": 1, "Excursion": 0.0}),
        ("FSV40", "Marker set Center", {"Marker Index": 2, "Excursion": 0.0}),
        ("FSV40", "Clear Trace", {}),
    ]


@pytest.mark.parametrize(
    "detector_mode",
    [
        "Auto Peak",
        "Positive Peak",
        "Negative Peak",
        "Sample",
        "RMS",
        "Average",
        "Quasipeak",
        "CISPR Average",
        "RMS Average",
    ],
)
def test_setup_sa_manual_accepts_contract_detector_modes(detector_mode: str) -> None:
    client = _Client(_default_ok())

    assert commands.setup_sa_manual(
        client,
        start_frequency_mhz=30,
        stop_frequency_mhz=1000,
        rbw_mhz=0.1,
        vbw_mhz=0.3,
        sweep_point=10001,
        sweep_time_sec=0.1,
        atten_level_db=10,
        detector_mode=detector_mode,
        limit_dbm=-36,
    )


def test_setup_sa_manual_rejects_invalid_sweep_point_and_detector_mode() -> None:
    client = _Client()
    kwargs = {
        "start_frequency_mhz": 30.0,
        "stop_frequency_mhz": 1000.0,
        "rbw_mhz": 0.1,
        "vbw_mhz": 0.3,
        "sweep_time_sec": 0.1,
        "atten_level_db": 10.0,
        "limit_dbm": -36.0,
    }

    with pytest.raises(ValueError, match="sweep_point must be an integer"):
        commands.setup_sa_manual(
            client,
            sweep_point=10001.0,  # type: ignore[arg-type]
            detector_mode="RMS",
            **kwargs,
        )
    with pytest.raises(ValueError, match="Unsupported detector mode"):
        commands.setup_sa_manual(
            client,
            sweep_point=10001,
            detector_mode="Peak",
            **kwargs,
        )
    assert client.calls == []


@pytest.mark.parametrize(
    "response",
    [
        Response(id="response-id", status="ok"),
        Response(id="response-id", status="ok", result="ignored"),
        Response(id="response-id", status="ok", result={"ok": False}),
    ],
)
def test_manual_action_success_depends_only_on_status(response: Response) -> None:
    assert commands.clear_trace(_Client(response)) is True


def test_manual_action_propagates_command_error() -> None:
    client = _Client(
        Response(
            id="response-id",
            status="error",
            error={"message": "equipment rejected Clear Trace"},
        )
    )

    with pytest.raises(commands.CommandError, match="equipment rejected Clear Trace"):
        commands.clear_trace(client)


def test_manual_action_propagates_transport_timeout_without_retry() -> None:
    class _TimeoutClient:
        def __init__(self) -> None:
            self.calls = 0

        def send_request(
            self,
            target: str,
            command: str,
            params: dict[str, Any],
        ) -> Response:
            _ = target, command, params
            self.calls += 1
            raise TcpClientTimeoutError("TCP response timeout")

    client = _TimeoutClient()
    with pytest.raises(TcpClientTimeoutError, match="TCP response timeout"):
        commands.clear_trace(client)
    assert client.calls == 1
