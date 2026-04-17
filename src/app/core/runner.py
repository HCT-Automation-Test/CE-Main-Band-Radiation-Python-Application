"""통합 세션 FSM 실행 컨트롤러. 내부에 QThread 워커를 둔다."""
from __future__ import annotations

import logging

from PySide6.QtCore import QObject, QThread

from app.core.events import RunnerEvents
from app.models.test_case import TestCase

logger = logging.getLogger(__name__)


class Runner(QObject):
    """TC 큐를 통합 세션 FSM으로 실행하는 오케스트레이터.

    내부에서 `QThread`에 워커를 올려 FSMEngine을 돌린다.
    UI는 `events` 시그널만 구독.
    """

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.events = RunnerEvents(self)
        self._thread: QThread | None = None
        # TODO(spec): FSMEngine 인스턴스 및 TCP client 주입 방식 확정

    def start(self, cases: list[TestCase]) -> None:
        """세션 FSM 실행 시작.

        1. SessionContext 생성 (queue=cases, commands=..., events=self.events)
        2. build_session_engine(ctx)로 FSMEngine 구성
        3. QThread 워커에서 engine.run("SessionInit") 실행
        """
        # TODO(spec): QThread + Worker 패턴으로 구현
        raise NotImplementedError("spec TODO")

    def pause(self) -> None:
        """실행 일시정지. ctx.paused = True."""
        # TODO(spec): 인터럽션 토큰/플래그 정책 확정
        raise NotImplementedError("spec TODO")

    def stop(self) -> None:
        """실행 중단. ctx.stopped = True."""
        # TODO(spec): 안전 중단(현재 State exit 보장) 구현
        raise NotImplementedError("spec TODO")
