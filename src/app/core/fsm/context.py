"""통합 세션 FSM 실행 컨텍스트."""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.core.events import RunnerEvents
from app.models.test_case import TestCase
from app.models.test_run_settings import TestRunSettings

if TYPE_CHECKING:
    from app.models.measurement_result import HarmonicPrecisionCandidate
    from app.report.report_writer import ReportWriter


@dataclass
class SessionContext:
    """세션 전체를 관통하는 실행 컨텍스트.

    `commands`는 `net.commands` 모듈 혹은 테스트용 mock facade 객체.
    """

    queue: list[TestCase]
    commands: Any
    events: RunnerEvents
    client: Any | None = None
    report_writer: ReportWriter | None = None
    tcp_host: str = "127.0.0.1"
    tcp_port: int = 5025
    current_index: int = 0
    start_index: int = 0
    stop_index: int | None = None
    paused: bool = False
    stopped: bool = False
    current_case_stop_requested: bool = False
    current_angle: float = 0.0
    fundamental_frequency_mhz: float | None = None
    last_applied_factor_keyword: str | None = None
    temp_dir: Path | None = None
    settings: TestRunSettings | None = None
    model_name: str = ""
    template_path: Path | None = None
    screenshot_root_dir: Path | None = None
    equipment_state: dict[str, Any] = field(default_factory=dict)
    harmonic_precision_candidates: list["HarmonicPrecisionCandidate"] = field(
        default_factory=list
    )
    equipment_connect_requested: threading.Event = field(
        default_factory=threading.Event
    )
    test_start_requested: threading.Event = field(default_factory=threading.Event)
    user_action_completed: threading.Event = field(default_factory=threading.Event)
    pending_transition_states: list[str] = field(default_factory=list)

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

    def pop_pending_transition_state(self) -> str | None:
        """연속 전환이 필요한 경우 다음 전환 상태를 꺼낸다."""
        if not self.pending_transition_states:
            return None
        return self.pending_transition_states.pop(0)
