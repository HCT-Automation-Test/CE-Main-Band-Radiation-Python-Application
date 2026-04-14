"""FSM 실행 컨텍스트."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.events import RunnerEvents
from app.models.measurement_result import MeasurementResult
from app.models.test_case import TestCase


@dataclass
class Context:
    """FSM State들이 공유하는 실행 컨텍스트.

    `commands`는 `net.commands` 모듈 혹은 테스트용 mock facade 객체.
    """

    case: TestCase
    commands: Any
    events: RunnerEvents
    result: MeasurementResult = field(default_factory=MeasurementResult)
    # TODO(spec): cancellation token / pause flag 추가 지점
