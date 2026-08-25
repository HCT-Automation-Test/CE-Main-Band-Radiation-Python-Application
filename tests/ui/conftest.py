"""UI 테스트가 실제 데스크톱 창 스타일을 변경하지 않도록 격리한다."""
from __future__ import annotations

import pytest

from app.ui.main_window import MainWindow


@pytest.fixture(autouse=True)
def _block_native_main_window_style_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MainWindow 생성/상태 전환 중 실제 Windows user32 호출을 차단한다."""

    monkeypatch.setattr(
        MainWindow,
        "_set_windows_resize_frame_enabled",
        lambda _window, _enabled: None,
    )
