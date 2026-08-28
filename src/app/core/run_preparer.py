"""측정 시작 전에 RawData 결과와 report writer를 준비한다."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

from app.core.events import RunnerEvents
from app.models.enums import Generation
from app.models.test_case import TestCase
from app.models.test_run_settings import TestRunSettings
from app.report.rawdata_workbook import (
    RawDataResultWorkbook,
    ensure_rawdata_result_workbook,
)
from app.report.report_writer import ReportWriter


class RawDataResultResolver(Protocol):
    """RawData result resolver 주입 계약."""

    def __call__(
        self,
        *,
        screenshot_root_dir: Path,
        eut_name: str,
        generation: Generation,
    ) -> RawDataResultWorkbook: ...


class ReportWriterFactory(Protocol):
    """Canonical result path 기반 report writer factory 계약."""

    def __call__(
        self,
        workbook_path: Path,
        screenshot_root_dir: Path,
        model_name: str,
        events: RunnerEvents,
    ) -> ReportWriter: ...


@dataclass(frozen=True)
class RunPreparationRequest:
    """UI thread에서 FSM worker로 전달하는 불변 Start 요청."""

    cases: tuple[TestCase, ...]
    settings: TestRunSettings
    start_index: int
    stop_index: int | None

    @property
    def first_case(self) -> TestCase:
        return self.cases[self.start_index]


@dataclass(frozen=True)
class PreparedRun:
    """측정 시작에 사용할 검증 완료 result와 writer."""

    result_workbook: RawDataResultWorkbook
    report_writer: ReportWriter


class RunPreparationError(RuntimeError):
    """측정 시작 준비 단계가 실패했을 때 발생한다."""


class RunPreparationStopped(RunPreparationError):
    """Stop 요청으로 다음 준비 단계에 진입하지 않을 때 발생한다."""


class RunPreparer:
    """RawData result 확보와 writer 준비를 순서대로 수행한다."""

    def __init__(
        self,
        *,
        result_resolver: RawDataResultResolver = ensure_rawdata_result_workbook,
        report_writer_factory: ReportWriterFactory,
    ) -> None:
        self._result_resolver = result_resolver
        self._report_writer_factory = report_writer_factory

    def prepare(
        self,
        request: RunPreparationRequest,
        *,
        events: RunnerEvents,
        should_stop: Callable[[], bool] | None = None,
    ) -> PreparedRun:
        """Canonical result를 확보하고 첫 TC의 live monitoring을 준비한다."""

        stop_requested = should_stop if should_stop is not None else lambda: False
        settings = request.settings
        first_case = request.first_case
        try:
            result_workbook = self._result_resolver(
                screenshot_root_dir=settings.screenshot_root_dir,
                eut_name=settings.eut_name,
                generation=first_case.generation,
            )
        except Exception as exc:
            raise RunPreparationError(
                f"RawData result 준비 실패: {exc}"
            ) from exc
        _raise_if_stopped(stop_requested)

        try:
            report_writer = self._report_writer_factory(
                result_workbook.path,
                settings.screenshot_root_dir,
                settings.eut_name,
                events,
            )
        except Exception as exc:
            raise RunPreparationError(
                f"report writer 생성 실패: {exc}"
            ) from exc
        _raise_if_stopped(stop_requested)

        try:
            report_writer.prepare_for_run(first_case)
        except Exception as exc:
            raise RunPreparationError(
                f"Excel report 준비 실패: {exc}"
            ) from exc
        _raise_if_stopped(stop_requested)

        return PreparedRun(
            result_workbook=result_workbook,
            report_writer=report_writer,
        )


def _raise_if_stopped(should_stop: Callable[[], bool]) -> None:
    if should_stop():
        raise RunPreparationStopped("시험 시작 준비가 중지되었습니다")
