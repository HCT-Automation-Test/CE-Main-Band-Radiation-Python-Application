from __future__ import annotations

from pathlib import Path

import pytest

from app.models.enums import (
    AntennaPol,
    DUTAntPosition,
    DUTAxis,
    Modulation,
    NRBand,
    RBAllocation,
    TestChannel,
    TestType,
)
from app.models.test_case import TestCase
from app.report.screenshot_store import build_sa_screenshot_path, finalize_sa_screenshot


class _SignalRecorder:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def emit(self, message: str) -> None:
        self.messages.append(message)


class _Events:
    def __init__(self) -> None:
        self.screenshot_saved = _SignalRecorder()


def _make_case(
    *,
    band: NRBand,
    bandwidth: float,
    test_type: TestType,
    test_channel: TestChannel,
    dut_ant_position: DUTAntPosition,
) -> TestCase:
    return TestCase(
        band=band,
        bandwidth=bandwidth,
        test_type=test_type,
        modulation=Modulation.QPSK,
        rb_allocation=RBAllocation.INNER_FULL,
        test_channel=test_channel,
        antenna_pol=AntennaPol.H,
        dut_axis=DUTAxis.X,
        dut_ant_position=dut_ant_position,
    )


@pytest.mark.parametrize(
    ("case", "expected_name"),
    [
        (
            _make_case(
                band=NRBand.N5,
                bandwidth=20.0,
                test_type=TestType.INBAND,
                test_channel=TestChannel.MID,
                dut_ant_position=DUTAntPosition.LOWER,
            ),
            "SM-000_Traffic_5G_n5_LOWER_SA_836.500MHz_30MHz_1GHz_XH.png",
        ),
        (
            _make_case(
                band=NRBand.N5,
                bandwidth=20.0,
                test_type=TestType.HARMONIC,
                test_channel=TestChannel.MID,
                dut_ant_position=DUTAntPosition.LOWER,
            ),
            "SM-000_Traffic_5G_n5_LOWER_SA_836.500MHz_1GHz_12.75GHz_XH.png",
        ),
        (
            _make_case(
                band=NRBand.N1,
                bandwidth=10.0,
                test_type=TestType.BILOG,
                test_channel=TestChannel.LOW,
                dut_ant_position=DUTAntPosition.LOWER,
            ),
            "SM-000_Traffic_5G_n1_LOWER_SA_1925.000MHz_30MHz_1GHz_XH.png",
        ),
        (
            _make_case(
                band=NRBand.N1,
                bandwidth=10.0,
                test_type=TestType.INBAND,
                test_channel=TestChannel.LOW,
                dut_ant_position=DUTAntPosition.LOWER,
            ),
            "SM-000_Traffic_5G_n1_LOWER_SA_1925.000MHz_1GHz_3GHz_XH.png",
        ),
        (
            _make_case(
                band=NRBand.N1,
                bandwidth=10.0,
                test_type=TestType.HARMONIC,
                test_channel=TestChannel.LOW,
                dut_ant_position=DUTAntPosition.LOWER,
            ),
            "SM-000_Traffic_5G_n1_LOWER_SA_1925.000MHz_3GHz_12.75GHz_XH.png",
        ),
        (
            _make_case(
                band=NRBand.N77,
                bandwidth=30.0,
                test_type=TestType.BILOG,
                test_channel=TestChannel.LOW,
                dut_ant_position=DUTAntPosition.UPPER,
            ),
            "SM-000_Traffic_5G_n77_UPPER_SA_3315.000MHz_30MHz_1GHz_XH.png",
        ),
        (
            _make_case(
                band=NRBand.N77,
                bandwidth=30.0,
                test_type=TestType.INBAND,
                test_channel=TestChannel.LOW,
                dut_ant_position=DUTAntPosition.UPPER,
            ),
            "SM-000_Traffic_5G_n77_UPPER_SA_3315.000MHz_1GHz_6GHz_XH.png",
        ),
        (
            _make_case(
                band=NRBand.N77,
                bandwidth=30.0,
                test_type=TestType.HARMONIC,
                test_channel=TestChannel.LOW,
                dut_ant_position=DUTAntPosition.UPPER,
            ),
            "SM-000_Traffic_5G_n77_UPPER_SA_3315.000MHz_6GHz_18GHz_XH.png",
        ),
    ],
)
def test_build_sa_screenshot_path_uses_lookup_and_range_values(
    tmp_path: Path,
    case: TestCase,
    expected_name: str,
) -> None:
    path = build_sa_screenshot_path(
        root_dir=tmp_path,
        model_name="SM-000",
        test_case=case,
    )

    assert path == (
        tmp_path
        / "SM-000"
        / "Traffic"
        / "5G"
        / case.band.value
        / case.dut_ant_position.name
        / "SA"
        / expected_name
    )


def test_finalize_sa_screenshot_copies_file_and_emits_event(tmp_path: Path) -> None:
    case = _make_case(
        band=NRBand.N5,
        bandwidth=20.0,
        test_type=TestType.HARMONIC,
        test_channel=TestChannel.MID,
        dut_ant_position=DUTAntPosition.LOWER,
    )
    source = tmp_path / "temp" / "harmonic.png"
    source.parent.mkdir()
    source.write_bytes(b"png")
    events = _Events()

    destination = finalize_sa_screenshot(
        source_path=source,
        root_dir=tmp_path / "out",
        model_name="SM-000",
        test_case=case,
        events=events,
    )

    assert destination.read_bytes() == b"png"
    assert source.read_bytes() == b"png"
    assert events.screenshot_saved.messages == [str(destination)]


def test_build_sa_screenshot_path_sanitizes_model_name(tmp_path: Path) -> None:
    case = _make_case(
        band=NRBand.N1,
        bandwidth=10.0,
        test_type=TestType.INBAND,
        test_channel=TestChannel.LOW,
        dut_ant_position=DUTAntPosition.LOWER,
    )

    path = build_sa_screenshot_path(
        root_dir=tmp_path,
        model_name="SM:000",
        test_case=case,
    )

    assert "SM_000" in path.parts
    assert path.name.startswith("SM_000_Traffic_5G")


def test_build_sa_screenshot_path_rejects_empty_model_name(tmp_path: Path) -> None:
    case = _make_case(
        band=NRBand.N1,
        bandwidth=10.0,
        test_type=TestType.INBAND,
        test_channel=TestChannel.LOW,
        dut_ant_position=DUTAntPosition.LOWER,
    )

    with pytest.raises(ValueError, match="model_name is required"):
        build_sa_screenshot_path(
            root_dir=tmp_path,
            model_name=" ",
            test_case=case,
        )
