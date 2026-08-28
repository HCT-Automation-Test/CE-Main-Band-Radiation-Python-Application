from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import pytest

from app.core.run_preparer import RunPreparationError, RunPreparationRequest, RunPreparer
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
    TestChannel as ChannelEnum,
    TestType as MeasurementTestType,
)
from app.models.test_case import TestCase
from app.models.test_run_settings import TestRunSettings
from app.report.rawdata_source import RawDataWorkbookKind, resolve_rawdata_source
from app.report.rawdata_workbook import ensure_rawdata_result_workbook
from app.report.screenshot_store import (
    build_fundamental_screenshot_path,
    build_harmonic_precision_screenshot_path,
    build_sa_screenshot_path,
)


class _Writer:
    def __init__(self, workbook_path: Path) -> None:
        self.workbook_path = workbook_path
        self.prepared_cases: list[TestCase] = []

    def prepare_for_run(self, first_case: TestCase) -> None:
        self.prepared_cases.append(first_case)


@pytest.mark.parametrize(
    ("generation", "expected_kind", "expected_suffix"),
    [
        (Generation.NR_SA, RawDataWorkbookKind.NR, "NR.xlsx"),
        (Generation.LTE, RawDataWorkbookKind.LTE, "LTE.xlsx"),
    ],
)
def test_run_preparer_creates_then_reuses_canonical_result_without_source_change(
    tmp_path: Path,
    generation: Generation,
    expected_kind: RawDataWorkbookKind,
    expected_suffix: str,
) -> None:
    request = _make_request(tmp_path, generation=generation, eut_name="EUT-300")
    source_before = resolve_rawdata_source(generation)
    factory_calls: list[tuple[Path, Path, str, Any]] = []
    writers: list[_Writer] = []

    def writer_factory(
        workbook_path: Path,
        screenshot_root_dir: Path,
        model_name: str,
        events: Any,
    ) -> _Writer:
        factory_calls.append(
            (workbook_path, screenshot_root_dir, model_name, events)
        )
        writer = _Writer(workbook_path)
        writers.append(writer)
        return writer

    events = object()
    preparer = RunPreparer(
        result_resolver=ensure_rawdata_result_workbook,
        report_writer_factory=writer_factory,  # type: ignore[arg-type]
    )

    first = preparer.prepare(request, events=events)  # type: ignore[arg-type]
    second = preparer.prepare(request, events=events)  # type: ignore[arg-type]

    expected_path = (
        request.settings.screenshot_root_dir
        / "EUT-300"
        / f"EUT-300_CE Main_Radiation_{expected_suffix}"
    ).resolve()
    assert first.result_workbook.kind is expected_kind
    assert first.result_workbook.created
    assert not second.result_workbook.created
    assert first.result_workbook.path == expected_path
    assert second.result_workbook.path == expected_path
    assert [call[:3] for call in factory_calls] == [
        (expected_path, request.settings.screenshot_root_dir, "EUT-300"),
        (expected_path, request.settings.screenshot_root_dir, "EUT-300"),
    ]
    assert all(call[3] is events for call in factory_calls)
    assert all(writer.prepared_cases == [request.first_case] for writer in writers)
    assert resolve_rawdata_source(generation).sha256 == source_before.sha256


def test_nr_sa_and_nsa_requests_share_one_canonical_result(tmp_path: Path) -> None:
    writers: list[_Writer] = []

    def writer_factory(workbook_path: Path, *args: Any) -> _Writer:
        _ = args
        writer = _Writer(workbook_path)
        writers.append(writer)
        return writer

    preparer = RunPreparer(
        result_resolver=ensure_rawdata_result_workbook,
        report_writer_factory=writer_factory,  # type: ignore[arg-type]
    )
    sa = preparer.prepare(
        _make_request(tmp_path, generation=Generation.NR_SA, eut_name="Shared-EUT"),
        events=object(),  # type: ignore[arg-type]
    )
    nsa = preparer.prepare(
        _make_request(tmp_path, generation=Generation.NR_NSA, eut_name="Shared-EUT"),
        events=object(),  # type: ignore[arg-type]
    )

    assert sa.result_workbook.created
    assert not nsa.result_workbook.created
    assert nsa.result_workbook.path == sa.result_workbook.path
    assert [writer.workbook_path for writer in writers] == [
        sa.result_workbook.path,
        sa.result_workbook.path,
    ]


@pytest.mark.parametrize(
    ("generation", "rat_dir"),
    [
        (Generation.NR_SA, "5G"),
        (Generation.NR_NSA, "5G"),
        (Generation.LTE, "4G"),
    ],
)
def test_all_screenshot_variants_use_eut_scoped_directory(
    tmp_path: Path,
    generation: Generation,
    rat_dir: str,
) -> None:
    request = _make_request(tmp_path, generation=generation, eut_name="EUT-300")
    case = request.first_case
    paths = (
        build_sa_screenshot_path(
            root_dir=request.settings.screenshot_root_dir,
            model_name=request.settings.eut_name,
            test_case=case,
        ),
        build_fundamental_screenshot_path(
            root_dir=request.settings.screenshot_root_dir,
            model_name=request.settings.eut_name,
            test_case=case,
        ),
        build_harmonic_precision_screenshot_path(
            root_dir=request.settings.screenshot_root_dir,
            model_name=request.settings.eut_name,
            test_case=case,
            peak_frequency_mhz=3900.125,
            sweep_time_ms=100,
        ),
    )
    expected_root = tmp_path / "EUT-300" / "screenshots" / "Traffic" / rat_dir
    legacy_root = tmp_path / "screenshots" / "EUT-300"

    assert all(path.is_relative_to(expected_root) for path in paths)
    assert all(path.parts.count("EUT-300") == 1 for path in paths)
    assert all(not path.is_relative_to(legacy_root) for path in paths)


def test_legacy_screenshots_workbook_is_ignored(tmp_path: Path) -> None:
    eut_name = "Legacy-EUT"
    filename = f"{eut_name}_CE Main_Radiation_NR.xlsx"
    source = resolve_rawdata_source(Generation.NR_SA)
    legacy_path = tmp_path / "screenshots" / eut_name / filename
    legacy_path.parent.mkdir(parents=True)
    shutil.copy2(source.path, legacy_path)

    result = ensure_rawdata_result_workbook(
        screenshot_root_dir=tmp_path,
        eut_name=eut_name,
        generation=Generation.NR_SA,
    )

    assert result.created
    assert result.path == (tmp_path / eut_name / filename).resolve()
    assert result.path != legacy_path.resolve()
    assert legacy_path.is_file()


def test_invalid_eut_fails_before_writer_creation(tmp_path: Path) -> None:
    writer_calls: list[tuple[Any, ...]] = []

    def writer_factory(*args: Any) -> _Writer:
        writer_calls.append(args)
        return _Writer(args[0])

    preparer = RunPreparer(
        result_resolver=ensure_rawdata_result_workbook,
        report_writer_factory=writer_factory,  # type: ignore[arg-type]
    )

    with pytest.raises(RunPreparationError, match="RawData result 준비 실패"):
        preparer.prepare(
            _make_request(tmp_path, generation=Generation.NR_SA, eut_name="bad/name"),
            events=object(),  # type: ignore[arg-type]
        )

    assert writer_calls == []
    assert not (tmp_path / "bad").exists()
    assert not (tmp_path / "screenshots" / "bad").exists()


def _make_request(
    tmp_path: Path,
    *,
    generation: Generation,
    eut_name: str,
) -> RunPreparationRequest:
    settings = TestRunSettings(
        eut_name=eut_name,
        screenshot_root_dir=tmp_path,
        saturation_time_sec=5,
        connection_waiting_time_sec=5,
        atten_level_db=0,
        next_peak_search_level_db=6,
    )
    return RunPreparationRequest(
        cases=(_make_case(generation),),
        settings=settings,
        start_index=0,
        stop_index=None,
    )


def _make_case(generation: Generation) -> TestCase:
    if generation is Generation.LTE:
        return TestCase(
            generation=generation,
            band=LTEBand.B1,
            bandwidth=10,
            test_type=MeasurementTestType.INBAND,
            modulation=Modulation.QPSK,
            rb_allocation=LTERBAllocation.MID,
            test_channel=ChannelEnum.MID,
            antenna_pol=AntennaPol.H,
            dut_axis=DUTAxis.X,
            dut_ant_position=DUTAntPosition.LOWER,
        )
    return TestCase(
        generation=generation,
        band=NRBand.N78,
        bandwidth=100,
        test_type=MeasurementTestType.HARMONIC,
        modulation=Modulation.QPSK,
        rb_allocation=RBAllocation.INNER_FULL,
        test_channel=ChannelEnum.MID,
        antenna_pol=AntennaPol.H,
        dut_axis=DUTAxis.X,
        dut_ant_position=DUTAntPosition.UPPER,
        anchor_band=LTEBand.B1 if generation is Generation.NR_NSA else None,
    )
