"""FSM 측정 상태에서 호출하는 리포트 작성 인터페이스."""
from __future__ import annotations

from typing import Protocol

from app.models.measurement_result import (
    BilogResult,
    FundamentalResult,
    HarmonicResult,
    InbandResult,
)
from app.models.test_case import TestCase


class ReportWriter(Protocol):
    """측정 상태가 사용하는 리포트 작성자의 최소 인터페이스."""

    def write_fundamental(
        self,
        test_case: TestCase,
        result: FundamentalResult,
    ) -> bool:
        """기본파 측정 결과를 기록하고 성공 여부를 반환한다."""
        ...

    def write_harmonic(
        self,
        test_case: TestCase,
        result: HarmonicResult,
    ) -> bool:
        """Harmonic 측정 결과를 기록하고 성공 여부를 반환한다."""
        ...

    def write_inband(
        self,
        test_case: TestCase,
        result: InbandResult,
    ) -> bool:
        """In-Band 측정 결과를 기록하고 성공 여부를 반환한다."""
        ...

    def write_bilog(
        self,
        test_case: TestCase,
        result: BilogResult,
    ) -> bool:
        """Bilog 측정 결과를 기록하고 성공 여부를 반환한다."""
        ...
