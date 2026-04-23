"""통합 세션 FSM 실행 컨텍스트."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.events import RunnerEvents
from app.models.measurement_result import MeasurementResult
from app.models.test_case import TestCase


@dataclass
class SessionContext:
    """세션 전체를 관통하는 실행 컨텍스트.

    `commands`는 `net.commands` 모듈 혹은 테스트용 mock facade 객체.
    """

    queue: list[TestCase]
    commands: Any
    events: RunnerEvents
    client: Any | None = None
    current_index: int = 0
    results: list[MeasurementResult] = field(default_factory=list)
    paused: bool = False
    stopped: bool = False
    current_angle: float = 0.0
    # TODO(spec): equipment_state (장비 연결 상태 추적) 추가 지점

    @property
    def current_case(self) -> TestCase:
        """현재 실행 중인 TestCase."""
        return self.queue[self.current_index]

    @property
    def has_next_case(self) -> bool:
        """다음 TC가 존재하는지 여부."""
        return self.current_index < len(self.queue) - 1

    @property
    def prev_case(self) -> TestCase | None:
        """이전 TC. 첫 시험이면 None."""
        if self.current_index <= 0:
            return None
        return self.queue[self.current_index - 1]
