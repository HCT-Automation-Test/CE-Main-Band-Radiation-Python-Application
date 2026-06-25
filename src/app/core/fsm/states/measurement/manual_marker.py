"""수동 마커 편집 측정 흐름에서 공유하는 helper."""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.core.fsm.base import StateResult

if TYPE_CHECKING:
    from app.core.fsm.context import SessionContext

logger = logging.getLogger(__name__)

_MANUAL_SCREENSHOT_NAME = "screenshot.png"
_USER_ACTION_WAIT_INTERVAL_SEC = 0.2


def manual_screenshot_path(temp_dir: Path) -> Path:
    """LV Get Screenshot command가 남기는 임시 스크린샷 경로를 반환한다."""

    return temp_dir / _MANUAL_SCREENSHOT_NAME


def remove_stale_manual_screenshot(path: Path) -> None:
    """수동 마커 모드 측정 전 stale screenshot.png를 제거한다."""

    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        raise ValueError(f"stale 스크린샷 제거 실패: {path}") from exc


def wait_for_manual_marker_edit(
    ctx: "SessionContext",
    *,
    test_type: object,
) -> StateResult:
    """UI 수동 마커 편집 완료 신호를 기다린다."""

    ctx.user_action_completed.clear()
    signal = getattr(ctx.events, "manual_marker_edit_required", None)
    if signal is None:
        _emit_error(ctx, "수동 마커 편집 실패: manual_marker_edit_required signal is not set")
        return StateResult.FAIL

    signal.emit(
        {
            "test_type": test_type,
            "next_peak_search_level_db": _current_next_peak_search_level(ctx),
        }
    )

    while not ctx.stopped and not ctx.current_case_stop_requested:
        if ctx.user_action_completed.wait(_USER_ACTION_WAIT_INTERVAL_SEC):
            if ctx.stopped or ctx.current_case_stop_requested:
                return StateResult.FAIL
            ctx.user_action_completed.clear()
            return StateResult.OK

    return StateResult.FAIL


def restore_sa_level_settings(ctx: "SessionContext") -> StateResult:
    """마커 편집 중 변경될 수 있는 SA level 설정을 시작 설정값으로 원복한다."""

    settings = ctx.settings
    if settings is None:
        _emit_error(ctx, "수동 마커 편집 종료 실패: settings is required")
        return StateResult.FAIL

    try:
        restored = ctx.commands.setup_sa_startup_levels(
            ctx.client,
            atten_level_db=settings.atten_level_db,
            next_peak_search_level_db=settings.next_peak_search_level_db,
        )
    except Exception as exc:
        _emit_error(ctx, f"수동 마커 편집 종료 실패: SA Level 원복 실패: {exc}")
        return StateResult.FAIL

    if restored:
        return StateResult.OK

    _emit_error(
        ctx,
        "수동 마커 편집 종료 실패: setup_sa_startup_levels returned false",
    )
    return StateResult.FAIL


def capture_manual_screenshot(ctx: "SessionContext", screenshot_path: Path) -> StateResult:
    """Get Screenshot을 호출하고 temp/screenshot.png 생성 여부를 확인한다."""

    try:
        captured = ctx.commands.get_screenshot(ctx.client)
    except Exception as exc:
        _emit_error(ctx, f"수동 마커 스크린샷 저장 실패: {exc}")
        return StateResult.FAIL

    if not captured:
        _emit_error(ctx, "수동 마커 스크린샷 저장 실패: get_screenshot returned false")
        return StateResult.FAIL

    if screenshot_path.is_file():
        return StateResult.OK

    _emit_error(
        ctx,
        f"수동 마커 스크린샷 저장 실패: {screenshot_path} does not exist",
    )
    return StateResult.FAIL


def complete_manual_marker_edit(
    ctx: "SessionContext",
    *,
    test_type: object,
    screenshot_path: Path,
) -> StateResult:
    """수동 마커 편집 완료 대기, SA level 원복, 스크린샷 저장을 순서대로 수행한다."""

    result = wait_for_manual_marker_edit(ctx, test_type=test_type)
    if result is not StateResult.OK:
        return result

    result = restore_sa_level_settings(ctx)
    if result is not StateResult.OK:
        return result

    return capture_manual_screenshot(ctx, screenshot_path)


def _current_next_peak_search_level(ctx: "SessionContext") -> float:
    settings = getattr(ctx, "settings", None)
    if settings is None:
        return 6.0
    return float(settings.next_peak_search_level_db)


def _emit_error(ctx: "SessionContext", message: str) -> None:
    logger.error(message)
    if ctx.events is not None:
        ctx.events.error.emit(message)
