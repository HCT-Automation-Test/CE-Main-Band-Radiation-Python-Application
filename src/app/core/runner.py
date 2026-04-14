"""TC 큐 실행 컨트롤러. 내부에 QThread 워커를 둔다."""
from __future__ import annotations

import logging
from typing import Iterable

from PySide6.QtCore import QObject, QThread

from app.core.events import RunnerEvents
from app.models.test_case import TestCase

logger = logging.getLogger(__name__)


class Runner(QObject):
    """Test Case 리스트를 순차 실행하는 오케스트레이터.

    내부에서 `QThread`에 워커를 올려 FSM을 돌린다. UI는 `events` 시그널만 구독.
    """

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.events = RunnerEvents(self)
        self._thread: QThread | None = None
        # TODO(spec): worker 객체 및 TCP client 주입 방식 확정

    def start(self, cases: Iterable[TestCase]) -> None:
        """큐 실행 시작."""
        # TODO(spec): QThread + Worker 패턴으로 구현, FSM sequence 실행 루프 호출
        raise NotImplementedError("spec TODO")

    def pause(self) -> None:
        """실행 일시정지."""
        # TODO(spec): 인터럽션 토큰/플래그 정책 확정
        raise NotImplementedError("spec TODO")

    def stop(self) -> None:
        """실행 중단."""
        # TODO(spec): 안전 중단(현재 State exit 보장) 구현
        raise NotImplementedError("spec TODO")
