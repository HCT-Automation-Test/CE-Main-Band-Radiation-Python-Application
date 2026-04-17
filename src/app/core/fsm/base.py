"""FSM 베이스: State ABC 및 결과 enum."""
from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.core.fsm.context import SessionContext


class StateResult(Enum):
    """State `run()` 결과 코드."""

    OK = "ok"
    RETRY = "retry"
    FAIL = "fail"
    WAIT_USER = "wait_user"


class State(ABC):
    """시퀀스 단위 상태. 하위 클래스는 `name`을 정의한다."""

    name: str = "State"

    def enter(self, ctx: "SessionContext") -> None:
        """상태 진입 훅. 기본 no-op."""
        return None

    @abstractmethod
    def run(self, ctx: "SessionContext") -> StateResult:
        """상태 본 작업. 결과 코드를 반환해야 한다."""
        raise NotImplementedError

    def exit(self, ctx: "SessionContext") -> None:
        """상태 이탈 훅. 기본 no-op."""
        return None

    @abstractmethod
    def next_state(
        self, ctx: "SessionContext", result: StateResult
    ) -> str | None:
        """다음 상태 이름을 반환한다. None이면 FSM 종료."""
        raise NotImplementedError
