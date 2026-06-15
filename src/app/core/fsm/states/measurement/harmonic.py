"""Harmonic 전용 측정 상태.

공유 스텝(SetSwitchBox / SetupSpectrumAnalyzer / RotateTurntable / ResetSwitchBox)은
`measurement.common`으로 분리되어 있다.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from app.core.fsm.base import State, StateResult
from app.core.fsm.equipment import is_equipment_connected
from app.core.fsm.states.measurement.common import (
    _apply_spectrum_analyzer_preset_settings,
)
from app.core.fsm.states.measurement.reporting import append_and_write_report
from app.models.measurement_result import FundamentalResult, HarmonicResult
from app.models.nr_channel_lookup import resolve_target_frequency_mhz

if TYPE_CHECKING:
    from app.core.fsm.context import SessionContext

logger = logging.getLogger(__name__)

_HARMONIC_SCREENSHOT_NAME = "harmonic.png"
_FUNDAMENTAL_SCREENSHOT_NAME = "fundamental.png"
_FUNDAMENTAL_SPAN_MHZ = 200.0
_FUNDAMENTAL_RBW_MHZ = 1.0
_FUNDAMENTAL_VBW_MHZ = 1.0
_FUNDAMENTAL_SWEEP_POINT = 10001
_FUNDAMENTAL_TRACE_MODE = "View"


def _emit_error(ctx: "SessionContext", message: str) -> None:
    logger.error(message)
    if ctx.events is not None:
        ctx.events.error.emit(message)


def _emit_spectrum_analyzer_info(
    ctx: "SessionContext",
    info: dict[str, object],
) -> None:
    if ctx.events is None:
        return
    signal = getattr(ctx.events, "spectrum_analyzer_info_changed", None)
    if signal is not None:
        signal.emit(info)


def _normalize_harmonic_levels(raw_levels: object) -> list[float]:
    if isinstance(raw_levels, str | bytes):
        raise ValueError(
            "Harmonic 측정 응답 형식 오류: expected 4 numeric peak levels"
        )

    try:
        normalized = [float(level) for level in raw_levels]  # type: ignore[arg-type]
    except TypeError as exc:
        raise ValueError(
            "Harmonic 측정 응답 형식 오류: expected 4 numeric peak levels"
        ) from exc
    except ValueError as exc:
        raise ValueError(
            "Harmonic 측정 응답 형식 오류: expected 4 numeric peak levels"
        ) from exc

    if len(normalized) != 4:
        raise ValueError(
            f"Harmonic 측정 응답 형식 오류: expected 4 peak levels, got {len(normalized)}"
        )

    return normalized


def _recordable_peak(level_dbm: float, threshold_dbm: float) -> float | None:
    if level_dbm > threshold_dbm:
        return level_dbm
    return None


def _harmonic_screenshot_path(temp_dir: Path) -> Path:
    return temp_dir / _HARMONIC_SCREENSHOT_NAME


def _fundamental_screenshot_path(temp_dir: Path) -> Path:
    return temp_dir / _FUNDAMENTAL_SCREENSHOT_NAME


def _remove_stale_screenshot(path: Path) -> None:
    """측정 전 기존 스크린샷을 지워 stale 파일 오판을 막는다."""
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        raise ValueError(f"stale 스크린샷 삭제 실패: {path}") from exc


class MeasureFundamentalState(State):
    """§4.3 기본파 주파수를 측정하여 결과를 저장한다."""

    name = "MeasureFundamental"

    def run(self, ctx: "SessionContext") -> StateResult:
        if not is_equipment_connected(ctx, "FSV40"):
            _emit_error(ctx, "Fundamental 측정 스킵: FSV40이 연결되어 있지 않습니다.")
            return StateResult.OK

        test_case = ctx.current_case
        writer = ctx.report_writer
        if writer is not None:
            try:
                cached_frequency_mhz = writer.read_fundamental_frequency(test_case)
            except Exception as exc:
                _emit_error(ctx, f"Fundamental frequency 재사용 실패: {exc}")
                return StateResult.FAIL
            if cached_frequency_mhz is not None:
                ctx.fundamental_frequency_mhz = cached_frequency_mhz
                return StateResult.OK

        try:
            target_frequency_mhz = resolve_target_frequency_mhz(
                test_case.band,
                test_case.bandwidth,
                test_case.test_channel,
            )
        except Exception as exc:
            _emit_error(ctx, f"Fundamental 측정 준비 실패: {exc}")
            return StateResult.FAIL

        if ctx.temp_dir is None:
            _emit_error(
                ctx,
                "Fundamental 스크린샷 경로 생성 실패: temp_dir is not set",
            )
            return StateResult.FAIL

        screenshot_path = _fundamental_screenshot_path(ctx.temp_dir)
        prepared = _apply_spectrum_analyzer_preset_settings(
            ctx,
            failure_context="Fundamental 측정 실패",
        )
        if prepared is not StateResult.OK:
            return prepared

        try:
            _remove_stale_screenshot(screenshot_path)
            fundamental_frequency_mhz = float(
                ctx.commands.measure_fundamental(
                    ctx.client,
                    target_freq=target_frequency_mhz,
                )
            )
            half_span_mhz = _FUNDAMENTAL_SPAN_MHZ / 2
            _emit_spectrum_analyzer_info(
                ctx,
                {
                    "start_freq": target_frequency_mhz - half_span_mhz,
                    "stop_freq": target_frequency_mhz + half_span_mhz,
                    "trace_mode": _FUNDAMENTAL_TRACE_MODE,
                    "rbw": _FUNDAMENTAL_RBW_MHZ,
                    "vbw": _FUNDAMENTAL_VBW_MHZ,
                    "sweep_point": _FUNDAMENTAL_SWEEP_POINT,
                },
            )
        except Exception as exc:
            _emit_error(ctx, f"Fundamental 측정 실패: {exc}")
            return StateResult.FAIL

        if not screenshot_path.is_file():
            _emit_error(
                ctx,
                f"Fundamental 스크린샷 저장 실패: {screenshot_path} does not exist",
            )
            return StateResult.FAIL

        ctx.fundamental_frequency_mhz = fundamental_frequency_mhz
        result = FundamentalResult(
            screenshot_path=screenshot_path,
            fundamental_frequency_mhz=fundamental_frequency_mhz,
        )
        return append_and_write_report(
            ctx,
            result,
            lambda writer: writer.write_fundamental(ctx.current_case, result),
            "Fundamental 리포트 작성 실패: write_fundamental returned false",
        )

    def next_state(
        self, ctx: "SessionContext", result: StateResult
    ) -> str | None:
        if result is not StateResult.OK:
            return None
        return "SetSwitchBox"


class MeasureHarmonicsState(State):
    """§4.7 각 Range의 고조파를 측정하고 스크린샷을 저장한다."""

    name = "MeasureHarmonics"

    def run(self, ctx: "SessionContext") -> StateResult:
        if not is_equipment_connected(ctx, "FSV40"):
            _emit_error(ctx, "Harmonic 측정 스킵: FSV40이 연결되어 있지 않습니다.")
            return StateResult.OK

        fundamental_frequency_mhz = ctx.fundamental_frequency_mhz
        if fundamental_frequency_mhz is None:
            _emit_error(
                ctx,
                "Harmonic 측정 실패: fundamental_frequency_mhz is not set",
            )
            return StateResult.FAIL

        if ctx.temp_dir is None:
            _emit_error(
                ctx,
                "Harmonic 스크린샷 경로 생성 실패: temp_dir is not set",
            )
            return StateResult.FAIL

        screenshot_path = _harmonic_screenshot_path(ctx.temp_dir)
        try:
            _remove_stale_screenshot(screenshot_path)
            harmonic_levels = _normalize_harmonic_levels(
                ctx.commands.measure_harmonics(
                    ctx.client,
                    fundamental=fundamental_frequency_mhz,
                )
            )
        except Exception as exc:
            _emit_error(ctx, f"Harmonic 측정 실패: {exc}")
            return StateResult.FAIL

        if not screenshot_path.is_file():
            _emit_error(
                ctx,
                f"Harmonic 스크린샷 저장 실패: {screenshot_path} does not exist",
            )
            return StateResult.FAIL

        threshold_dbm = ctx.current_case.range_definition.limit - 10.0
        result = HarmonicResult(
            screenshot_path=screenshot_path,
            harmonic_2nd_peak_level_dbm=_recordable_peak(
                harmonic_levels[0], threshold_dbm
            ),
            harmonic_3rd_peak_level_dbm=_recordable_peak(
                harmonic_levels[1], threshold_dbm
            ),
            harmonic_4th_peak_level_dbm=_recordable_peak(
                harmonic_levels[2], threshold_dbm
            ),
            harmonic_5th_peak_level_dbm=_recordable_peak(
                harmonic_levels[3], threshold_dbm
            ),
        )
        return append_and_write_report(
            ctx,
            result,
            lambda writer: writer.write_harmonic(ctx.current_case, result),
            "Harmonic 리포트 작성 실패: write_harmonic returned false",
        )

    def next_state(
        self, ctx: "SessionContext", result: StateResult
    ) -> str | None:
        if result is not StateResult.OK:
            return None
        return "ResetSwitchBox"
