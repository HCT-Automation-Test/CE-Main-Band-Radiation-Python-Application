from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any

import pytest

from app.core.run_preparer import (
    RunPreparationError,
    RunPreparationRequest,
    RunPreparer,
    RunPreparationStopped,
)
from app.models.enums import (
    AntennaPol,
    DUTAxis,
    Generation,
    Modulation,
    NRBand,
    RBAllocation,
    TestChannel,
    TestType,
)
from app.models.test_case import TestCase
from app.models.test_run_settings import TestRunSettings
from app.report.rawdata_source import RawDataWorkbookKind
from app.report.rawdata_workbook import RawDataResultWorkbook


class _ReportWriter:
    def __init__(self, *, prepare_error: Exception | None = None) -> None:
        self.prepare_error = prepare_error
        self.prepare_calls: list[TestCase] = []

    def prepare_for_run(self, first_case: TestCase) -> None:
        self.prepare_calls.append(first_case)
        if self.prepare_error is not None:
            raise self.prepare_error


def _make_case(*, antenna_pol: AntennaPol = AntennaPol.H) -> TestCase:
    return TestCase(
        generation=Generation.NR_SA,
        band=NRBand.N78,
        bandwidth=100,
        test_type=TestType.HARMONIC,
        modulation=Modulation.QPSK,
        rb_allocation=RBAllocation.INNER_FULL,
        test_channel=TestChannel.MID,
        antenna_pol=antenna_pol,
        dut_axis=DUTAxis.X,
        dut_ant_position="Upper",
    )


def _make_settings(tmp_path: Path) -> TestRunSettings:
    template_path = tmp_path / "template.xlsx"
    template_path.write_bytes(b"template")
    return TestRunSettings(
        eut_name="SM-000",
        template_path=template_path,
        screenshot_root_dir=tmp_path / "screenshots",
        saturation_time_sec=5,
        connection_waiting_time_sec=5,
        atten_level_db=0,
        next_peak_search_level_db=6,
    )


def test_prepare_resolves_result_and_prepares_requested_start_case(
    tmp_path: Path,
) -> None:
    first_case = _make_case()
    second_case = _make_case(antenna_pol=AntennaPol.V)
    settings = _make_settings(tmp_path)
    request = RunPreparationRequest(
        cases=(first_case, second_case),
        settings=settings,
        start_index=1,
        stop_index=1,
    )
    result_path = tmp_path / "SM-000_CE Main_Radiation_NR.xlsx"
    resolver_calls: list[dict[str, Any]] = []
    factory_calls: list[tuple[Any, ...]] = []
    writer = _ReportWriter()
    events = object()

    def resolver(**kwargs: Any) -> RawDataResultWorkbook:
        resolver_calls.append(kwargs)
        return RawDataResultWorkbook(
            kind=RawDataWorkbookKind.NR,
            path=result_path,
            created=True,
        )

    def writer_factory(*args: Any) -> _ReportWriter:
        factory_calls.append(args)
        return writer

    prepared = RunPreparer(
        result_resolver=resolver,  # type: ignore[arg-type]
        report_writer_factory=writer_factory,  # type: ignore[arg-type]
    ).prepare(request, events=events)  # type: ignore[arg-type]

    assert resolver_calls == [
        {
            "screenshot_root_dir": settings.screenshot_root_dir,
            "eut_name": "SM-000",
            "generation": Generation.NR_SA,
        }
    ]
    assert factory_calls == [
        (result_path, settings.screenshot_root_dir, "SM-000", events)
    ]
    assert writer.prepare_calls == [second_case]
    assert prepared.result_workbook.path == result_path
    assert prepared.report_writer is writer


def test_prepare_wraps_result_resolver_failure(tmp_path: Path) -> None:
    request = RunPreparationRequest(
        cases=(_make_case(),),
        settings=_make_settings(tmp_path),
        start_index=0,
        stop_index=None,
    )

    def resolver(**kwargs: Any) -> RawDataResultWorkbook:
        _ = kwargs
        raise OSError("source unavailable")

    preparer = RunPreparer(
        result_resolver=resolver,  # type: ignore[arg-type]
        report_writer_factory=lambda *args: _ReportWriter(),  # type: ignore[arg-type]
    )

    with pytest.raises(RunPreparationError, match="RawData result 준비 실패"):
        preparer.prepare(request, events=object())  # type: ignore[arg-type]


def test_prepare_wraps_writer_factory_failure(tmp_path: Path) -> None:
    request = RunPreparationRequest(
        cases=(_make_case(),),
        settings=_make_settings(tmp_path),
        start_index=0,
        stop_index=None,
    )

    def resolver(**kwargs: Any) -> RawDataResultWorkbook:
        _ = kwargs
        return RawDataResultWorkbook(
            kind=RawDataWorkbookKind.NR,
            path=tmp_path / "result.xlsx",
            created=False,
        )

    def writer_factory(*args: Any) -> _ReportWriter:
        _ = args
        raise RuntimeError("writer unavailable")

    preparer = RunPreparer(
        result_resolver=resolver,  # type: ignore[arg-type]
        report_writer_factory=writer_factory,  # type: ignore[arg-type]
    )

    with pytest.raises(RunPreparationError, match="report writer 생성 실패"):
        preparer.prepare(request, events=object())  # type: ignore[arg-type]


def test_prepare_wraps_live_monitoring_failure(tmp_path: Path) -> None:
    request = RunPreparationRequest(
        cases=(_make_case(),),
        settings=_make_settings(tmp_path),
        start_index=0,
        stop_index=None,
    )
    result = RawDataResultWorkbook(
        kind=RawDataWorkbookKind.NR,
        path=tmp_path / "result.xlsx",
        created=False,
    )
    writer = _ReportWriter(prepare_error=RuntimeError("Excel unavailable"))
    preparer = RunPreparer(
        result_resolver=lambda **kwargs: result,  # type: ignore[arg-type]
        report_writer_factory=lambda *args: writer,  # type: ignore[arg-type]
    )

    with pytest.raises(RunPreparationError, match="Excel report 준비 실패"):
        preparer.prepare(request, events=object())  # type: ignore[arg-type]


def test_prepare_stop_after_resolver_skips_writer_factory(tmp_path: Path) -> None:
    request = RunPreparationRequest(
        cases=(_make_case(),),
        settings=_make_settings(tmp_path),
        start_index=0,
        stop_index=None,
    )
    result = RawDataResultWorkbook(
        kind=RawDataWorkbookKind.NR,
        path=tmp_path / "result.xlsx",
        created=True,
    )
    writer_calls: list[tuple[Any, ...]] = []

    def writer_factory(*args: Any) -> _ReportWriter:
        writer_calls.append(args)
        return _ReportWriter()

    preparer = RunPreparer(
        result_resolver=lambda **kwargs: result,  # type: ignore[arg-type]
        report_writer_factory=writer_factory,  # type: ignore[arg-type]
    )

    with pytest.raises(RunPreparationStopped):
        preparer.prepare(
            request,
            events=object(),  # type: ignore[arg-type]
            should_stop=lambda: True,
        )

    assert writer_calls == []


def test_run_preparation_request_is_immutable(tmp_path: Path) -> None:
    request = RunPreparationRequest(
        cases=(_make_case(),),
        settings=_make_settings(tmp_path),
        start_index=0,
        stop_index=None,
    )

    with pytest.raises(FrozenInstanceError):
        request.start_index = 1  # type: ignore[misc]
