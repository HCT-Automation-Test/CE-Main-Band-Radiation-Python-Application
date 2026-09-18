"""Manual Test 서브 패널."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QWidget

if TYPE_CHECKING:
    from app.core.manual_test_service import ManualTestService


class ManualTestPanel(QWidget):
    """추후 개발될 Manual Test 화면."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        service: ManualTestService | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        # TODO(spec): 수동 시험 제어 UI 배치

    @property
    def service(self) -> ManualTestService | None:
        """후속 Manual UI가 사용할 Core service를 반환한다."""

        return self._service
