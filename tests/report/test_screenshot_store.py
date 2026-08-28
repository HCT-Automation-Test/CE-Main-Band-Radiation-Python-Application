from __future__ import annotations

from pathlib import Path

import pytest

from app.models.enums import (
    AntennaPol,
    DUTAntPosition,
    DUTAxis,
    Generation,
    LTEBand,
    LTERBAllocation,
    Modulation,
    NRBand,
    RBAllocation,
    TestChannel,
    TestType,
)
from app.models.test_case import TestCase
from app.report.screenshot_store import (
    build_fundamental_screenshot_path,
    build_harmonic_precision_screenshot_path,
    build_sa_screenshot_path,
    finalize_fundamental_screenshot,
    finalize_harmonic_precision_screenshot,
    finalize_sa_screenshot,
)


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
    generation: Generation = Generation.NR_SA,
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
        generation=generation,
        anchor_band=LTEBand.B1 if generation is Generation.NR_NSA else None,
    )


def _make_lte_case(
    *,
    test_type: TestType = TestType.INBAND,
    band: LTEBand = LTEBand.B1,
    bandwidth: float = 20.0,
    test_channel: TestChannel = TestChannel.MID,
    dut_ant_position: DUTAntPosition = DUTAntPosition.LOWER,
    antenna_pol: AntennaPol = AntennaPol.H,
    dut_axis: DUTAxis = DUTAxis.X,
    rb_allocation: LTERBAllocation = LTERBAllocation.MID,
) -> TestCase:
    return TestCase(
        band=band,
        bandwidth=bandwidth,
        test_type=test_type,
        modulation=Modulation.QPSK,
        rb_allocation=rb_allocation,
        test_channel=test_channel,
        antenna_pol=antenna_pol,
        dut_axis=dut_axis,
        dut_ant_position=dut_ant_position,
        generation=Generation.LTE,
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
            "SM-000_Traffic_5G_SA_n5_LOWER_836.500MHz_30MHz_1GHz_XH.png",
        ),
        (
            _make_case(
                band=NRBand.N5,
                bandwidth=20.0,
                test_type=TestType.HARMONIC,
                test_channel=TestChannel.MID,
                dut_ant_position=DUTAntPosition.LOWER,
            ),
            "SM-000_Traffic_5G_SA_n5_LOWER_836.500MHz_1GHz_12.75GHz_XH.png",
        ),
        (
            _make_case(
                band=NRBand.N1,
                bandwidth=10.0,
                test_type=TestType.BILOG,
                test_channel=TestChannel.LOW,
                dut_ant_position=DUTAntPosition.LOWER,
            ),
            "SM-000_Traffic_5G_SA_n1_LOWER_1925.000MHz_30MHz_1GHz_XH.png",
        ),
        (
            _make_case(
                band=NRBand.N1,
                bandwidth=10.0,
                test_type=TestType.INBAND,
                test_channel=TestChannel.LOW,
                dut_ant_position=DUTAntPosition.LOWER,
            ),
            "SM-000_Traffic_5G_SA_n1_LOWER_1925.000MHz_1GHz_3GHz_XH.png",
        ),
        (
            _make_case(
                band=NRBand.N1,
                bandwidth=10.0,
                test_type=TestType.HARMONIC,
                test_channel=TestChannel.LOW,
                dut_ant_position=DUTAntPosition.LOWER,
            ),
            "SM-000_Traffic_5G_SA_n1_LOWER_1925.000MHz_3GHz_12.75GHz_XH.png",
        ),
        (
            _make_case(
                band=NRBand.N77,
                bandwidth=30.0,
                test_type=TestType.BILOG,
                test_channel=TestChannel.LOW,
                dut_ant_position=DUTAntPosition.UPPER,
            ),
            "SM-000_Traffic_5G_SA_n77_UPPER_3315.000MHz_30MHz_1GHz_XH.png",
        ),
        (
            _make_case(
                band=NRBand.N77,
                bandwidth=30.0,
                test_type=TestType.INBAND,
                test_channel=TestChannel.LOW,
                dut_ant_position=DUTAntPosition.UPPER,
            ),
            "SM-000_Traffic_5G_SA_n77_UPPER_3315.000MHz_1GHz_6GHz_XH.png",
        ),
        (
            _make_case(
                band=NRBand.N77,
                bandwidth=30.0,
                test_type=TestType.HARMONIC,
                test_channel=TestChannel.LOW,
                dut_ant_position=DUTAntPosition.UPPER,
            ),
            "SM-000_Traffic_5G_SA_n77_UPPER_3315.000MHz_6GHz_18GHz_XH.png",
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
        / "screenshots"
        / "Traffic"
        / "5G"
        / case.band.value
        / case.dut_ant_position.name
        / "SA"
        / expected_name
    )


def test_build_nsa_screenshot_path_uses_nsa_dir_and_filename(tmp_path: Path) -> None:
    case = _make_case(
        band=NRBand.N78,
        bandwidth=100.0,
        test_type=TestType.INBAND,
        test_channel=TestChannel.MID,
        dut_ant_position=DUTAntPosition.UPPER,
        generation=Generation.NR_NSA,
    )

    path = build_sa_screenshot_path(
        root_dir=tmp_path,
        model_name="SM-000",
        test_case=case,
    )

    assert path == (
        tmp_path
        / "SM-000"
        / "screenshots"
        / "Traffic"
        / "5G"
        / "n78"
        / "UPPER"
        / "NSA"
        / "SM-000_Traffic_5G_NSA_n78_UPPER_3549.990MHz_1GHz_6GHz_XH.png"
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


def test_build_harmonic_precision_screenshot_path_uses_precision_filename(
    tmp_path: Path,
) -> None:
    case = _make_case(
        band=NRBand.N79,
        bandwidth=100.0,
        test_type=TestType.HARMONIC,
        test_channel=TestChannel.MID,
        dut_ant_position=DUTAntPosition.UPPER,
    )

    path = build_harmonic_precision_screenshot_path(
        root_dir=tmp_path,
        model_name="SM-000",
        test_case=case,
        peak_frequency_mhz=14088.35,
        sweep_time_ms=100,
    )

    assert path == (
        tmp_path
        / "SM-000"
        / "screenshots"
        / "Traffic"
        / "5G"
        / "n79"
        / "UPPER"
        / "SA"
        / "SM-000_Traffic_5G_SA_n79_UPPER_14088.350MHz_XH_100ms.png"
    )


def test_build_nsa_harmonic_precision_screenshot_path_uses_nsa_dir_and_filename(
    tmp_path: Path,
) -> None:
    case = _make_case(
        band=NRBand.N79,
        bandwidth=100.0,
        test_type=TestType.HARMONIC,
        test_channel=TestChannel.MID,
        dut_ant_position=DUTAntPosition.UPPER,
        generation=Generation.NR_NSA,
    )

    path = build_harmonic_precision_screenshot_path(
        root_dir=tmp_path,
        model_name="SM-000",
        test_case=case,
        peak_frequency_mhz=14088.35,
        sweep_time_ms=100,
    )

    assert path == (
        tmp_path
        / "SM-000"
        / "screenshots"
        / "Traffic"
        / "5G"
        / "n79"
        / "UPPER"
        / "NSA"
        / "SM-000_Traffic_5G_NSA_n79_UPPER_14088.350MHz_XH_100ms.png"
    )


def test_finalize_harmonic_precision_screenshot_copies_file_and_emits_event(
    tmp_path: Path,
) -> None:
    case = _make_case(
        band=NRBand.N79,
        bandwidth=100.0,
        test_type=TestType.HARMONIC,
        test_channel=TestChannel.MID,
        dut_ant_position=DUTAntPosition.LOWER,
    )
    source = tmp_path / "temp" / "precision.png"
    source.parent.mkdir()
    source.write_bytes(b"precision")
    events = _Events()

    destination = finalize_harmonic_precision_screenshot(
        source_path=source,
        root_dir=tmp_path / "out",
        model_name="SM-000",
        test_case=case,
        peak_frequency_mhz=14088.3,
        sweep_time_ms=500,
        events=events,
    )

    assert destination.name == (
        "SM-000_Traffic_5G_SA_n79_LOWER_14088.300MHz_XH_500ms.png"
    )
    assert destination.read_bytes() == b"precision"
    assert source.read_bytes() == b"precision"
    assert events.screenshot_saved.messages == [str(destination)]


def test_build_fundamental_screenshot_path_uses_lookup_and_fixed_suffix(
    tmp_path: Path,
) -> None:
    case = _make_case(
        band=NRBand.N78,
        bandwidth=100.0,
        test_type=TestType.HARMONIC,
        test_channel=TestChannel.MID,
        dut_ant_position=DUTAntPosition.UPPER,
    )

    path = build_fundamental_screenshot_path(
        root_dir=tmp_path,
        model_name="SM-000",
        test_case=case,
    )

    assert path == (
        tmp_path
        / "SM-000"
        / "screenshots"
        / "Traffic"
        / "5G"
        / "n78"
        / "UPPER"
        / "SA"
        / "SM-000_Traffic_5G_SA_n78_UPPER_3549.990MHz_Fundamental Frequency.png"
    )


def test_build_nsa_fundamental_screenshot_path_uses_nsa_dir_and_filename(
    tmp_path: Path,
) -> None:
    case = _make_case(
        band=NRBand.N78,
        bandwidth=100.0,
        test_type=TestType.HARMONIC,
        test_channel=TestChannel.MID,
        dut_ant_position=DUTAntPosition.UPPER,
        generation=Generation.NR_NSA,
    )

    path = build_fundamental_screenshot_path(
        root_dir=tmp_path,
        model_name="SM-000",
        test_case=case,
    )

    assert path == (
        tmp_path
        / "SM-000"
        / "screenshots"
        / "Traffic"
        / "5G"
        / "n78"
        / "UPPER"
        / "NSA"
        / "SM-000_Traffic_5G_NSA_n78_UPPER_3549.990MHz_Fundamental Frequency.png"
    )


def test_finalize_fundamental_screenshot_copies_file_and_emits_event(
    tmp_path: Path,
) -> None:
    case = _make_case(
        band=NRBand.N78,
        bandwidth=100.0,
        test_type=TestType.HARMONIC,
        test_channel=TestChannel.MID,
        dut_ant_position=DUTAntPosition.UPPER,
    )
    source = tmp_path / "temp" / "fundamental.png"
    source.parent.mkdir()
    source.write_bytes(b"png")
    events = _Events()

    destination = finalize_fundamental_screenshot(
        source_path=source,
        root_dir=tmp_path / "out",
        model_name="SM-000",
        test_case=case,
        events=events,
    )

    assert destination.read_bytes() == b"png"
    assert source.read_bytes() == b"png"
    assert events.screenshot_saved.messages == [str(destination)]


def test_finalize_sa_screenshot_preserves_existing_file_and_saves_numbered_copy(
    tmp_path: Path,
) -> None:
    case = _make_case(
        band=NRBand.N5,
        bandwidth=20.0,
        test_type=TestType.HARMONIC,
        test_channel=TestChannel.MID,
        dut_ant_position=DUTAntPosition.LOWER,
    )
    root_dir = tmp_path / "out"
    source = tmp_path / "temp" / "harmonic.png"
    source.parent.mkdir()
    source.write_bytes(b"new")
    original = build_sa_screenshot_path(
        root_dir=root_dir,
        model_name="SM-000",
        test_case=case,
    )
    original.parent.mkdir(parents=True)
    original.write_bytes(b"existing")
    events = _Events()

    destination = finalize_sa_screenshot(
        source_path=source,
        root_dir=root_dir,
        model_name="SM-000",
        test_case=case,
        events=events,
    )

    assert original.read_bytes() == b"existing"
    assert destination == original.with_name(f"{original.stem}(1){original.suffix}")
    assert destination.read_bytes() == b"new"
    assert events.screenshot_saved.messages == [str(destination)]


def test_finalize_sa_screenshot_uses_next_available_numbered_copy(
    tmp_path: Path,
) -> None:
    case = _make_case(
        band=NRBand.N5,
        bandwidth=20.0,
        test_type=TestType.HARMONIC,
        test_channel=TestChannel.MID,
        dut_ant_position=DUTAntPosition.LOWER,
    )
    root_dir = tmp_path / "out"
    source = tmp_path / "temp" / "harmonic.png"
    source.parent.mkdir()
    source.write_bytes(b"new")
    original = build_sa_screenshot_path(
        root_dir=root_dir,
        model_name="SM-000",
        test_case=case,
    )
    first_copy = original.with_name(f"{original.stem}(1){original.suffix}")
    original.parent.mkdir(parents=True)
    original.write_bytes(b"existing")
    first_copy.write_bytes(b"existing-1")

    destination = finalize_sa_screenshot(
        source_path=source,
        root_dir=root_dir,
        model_name="SM-000",
        test_case=case,
    )

    assert original.read_bytes() == b"existing"
    assert first_copy.read_bytes() == b"existing-1"
    assert destination == original.with_name(f"{original.stem}(2){original.suffix}")
    assert destination.read_bytes() == b"new"


def test_finalize_harmonic_precision_screenshot_preserves_existing_file(
    tmp_path: Path,
) -> None:
    case = _make_case(
        band=NRBand.N79,
        bandwidth=100.0,
        test_type=TestType.HARMONIC,
        test_channel=TestChannel.MID,
        dut_ant_position=DUTAntPosition.LOWER,
    )
    root_dir = tmp_path / "out"
    source = tmp_path / "temp" / "precision.png"
    source.parent.mkdir()
    source.write_bytes(b"new-precision")
    original = build_harmonic_precision_screenshot_path(
        root_dir=root_dir,
        model_name="SM-000",
        test_case=case,
        peak_frequency_mhz=14088.3,
        sweep_time_ms=500,
    )
    original.parent.mkdir(parents=True)
    original.write_bytes(b"existing-precision")
    events = _Events()

    destination = finalize_harmonic_precision_screenshot(
        source_path=source,
        root_dir=root_dir,
        model_name="SM-000",
        test_case=case,
        peak_frequency_mhz=14088.3,
        sweep_time_ms=500,
        events=events,
    )

    assert original.read_bytes() == b"existing-precision"
    assert destination == original.with_name(f"{original.stem}(1){original.suffix}")
    assert destination.read_bytes() == b"new-precision"
    assert events.screenshot_saved.messages == [str(destination)]


def test_finalize_fundamental_screenshot_preserves_existing_file(
    tmp_path: Path,
) -> None:
    case = _make_case(
        band=NRBand.N78,
        bandwidth=100.0,
        test_type=TestType.HARMONIC,
        test_channel=TestChannel.MID,
        dut_ant_position=DUTAntPosition.UPPER,
    )
    root_dir = tmp_path / "out"
    source = tmp_path / "temp" / "fundamental.png"
    source.parent.mkdir()
    source.write_bytes(b"new-fundamental")
    original = build_fundamental_screenshot_path(
        root_dir=root_dir,
        model_name="SM-000",
        test_case=case,
    )
    original.parent.mkdir(parents=True)
    original.write_bytes(b"existing-fundamental")
    events = _Events()

    destination = finalize_fundamental_screenshot(
        source_path=source,
        root_dir=root_dir,
        model_name="SM-000",
        test_case=case,
        events=events,
    )

    assert original.read_bytes() == b"existing-fundamental"
    assert destination == original.with_name(f"{original.stem}(1){original.suffix}")
    assert destination.read_bytes() == b"new-fundamental"
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


def test_build_fundamental_screenshot_path_sanitizes_model_name(
    tmp_path: Path,
) -> None:
    case = _make_case(
        band=NRBand.N78,
        bandwidth=100.0,
        test_type=TestType.HARMONIC,
        test_channel=TestChannel.MID,
        dut_ant_position=DUTAntPosition.UPPER,
    )

    path = build_fundamental_screenshot_path(
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


def test_build_fundamental_screenshot_path_rejects_empty_model_name(
    tmp_path: Path,
) -> None:
    case = _make_case(
        band=NRBand.N78,
        bandwidth=100.0,
        test_type=TestType.HARMONIC,
        test_channel=TestChannel.MID,
        dut_ant_position=DUTAntPosition.UPPER,
    )

    with pytest.raises(ValueError, match="model_name is required"):
        build_fundamental_screenshot_path(
            root_dir=tmp_path,
            model_name=" ",
            test_case=case,
        )


def test_build_lte_sa_screenshot_path_matches_required_example(
    tmp_path: Path,
) -> None:
    case = _make_lte_case()

    path = build_sa_screenshot_path(
        root_dir=tmp_path,
        model_name="SM-000",
        test_case=case,
    )

    assert path == (
        tmp_path
        / "SM-000"
        / "screenshots"
        / "Traffic"
        / "4G"
        / "B1"
        / "Lower"
        / "SM-000_Traffic_4G_B1_LOWER_1950.000MHz_1GHz_3GHz_XH.png"
    )


def test_build_lte_fundamental_screenshot_path_uses_target_frequency(
    tmp_path: Path,
) -> None:
    case = _make_lte_case(test_type=TestType.HARMONIC)

    path = build_fundamental_screenshot_path(
        root_dir=tmp_path,
        model_name="SM-000",
        test_case=case,
    )

    assert path == (
        tmp_path
        / "SM-000"
        / "screenshots"
        / "Traffic"
        / "4G"
        / "B1"
        / "Lower"
        / "SM-000_Traffic_4G_B1_LOWER_1950.000MHz_Fundamental Frequency.png"
    )


def test_build_lte_precision_screenshot_path_uses_measured_peak(
    tmp_path: Path,
) -> None:
    case = _make_lte_case(test_type=TestType.HARMONIC)

    path = build_harmonic_precision_screenshot_path(
        root_dir=tmp_path,
        model_name="SM-000",
        test_case=case,
        peak_frequency_mhz=3900.125,
        sweep_time_ms=100,
    )

    assert path == (
        tmp_path
        / "SM-000"
        / "screenshots"
        / "Traffic"
        / "4G"
        / "B1"
        / "Lower"
        / "SM-000_Traffic_4G_B1_LOWER_3900.125MHz_XH_100ms.png"
    )


def test_finalize_lte_screenshot_preserves_duplicate_and_emits_event(
    tmp_path: Path,
) -> None:
    case = _make_lte_case()
    root_dir = tmp_path / "out"
    source = tmp_path / "temp" / "inband.png"
    source.parent.mkdir()
    source.write_bytes(b"new-lte")
    original = build_sa_screenshot_path(
        root_dir=root_dir,
        model_name="SM-000",
        test_case=case,
    )
    original.parent.mkdir(parents=True)
    original.write_bytes(b"existing-lte")
    events = _Events()

    destination = finalize_sa_screenshot(
        source_path=source,
        root_dir=root_dir,
        model_name="SM-000",
        test_case=case,
        events=events,
    )

    assert original.read_bytes() == b"existing-lte"
    assert destination == original.with_name(f"{original.stem}(1){original.suffix}")
    assert destination.read_bytes() == b"new-lte"
    assert source.read_bytes() == b"new-lte"
    assert events.screenshot_saved.messages == [str(destination)]
