"""Harmonic 전용 측정 상태."""
from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import TYPE_CHECKING

from app.core.fsm.base import State, StateResult
from app.core.fsm.equipment import is_equipment_connected
from app.core.fsm.states.measurement.common import (
    RotateTurntableState,
    _wait_for_saturation_time,
)
from app.core.fsm.states.measurement.manual_marker import (
    complete_manual_marker_edit,
    manual_screenshot_path,
    remove_stale_manual_screenshot,
)
from app.core.fsm.states.measurement.reporting import append_and_write_report
from app.models.measurement_result import (
    FundamentalResult,
    HarmonicMarker,
    HarmonicPrecisionCandidate,
    HarmonicResult,
)
from app.report.screenshot_store import finalize_harmonic_precision_screenshot

if TYPE_CHECKING:
    from app.core.fsm.context import SessionContext

logger = logging.getLogger(__name__)

_HARMONIC_SCREENSHOT_NAME = "harmonic.png"
_PRECISION_SCREENSHOT_NAME = "precision.png"
_FUNDAMENTAL_SCREENSHOT_NAME = "fundamental.png"
_FUNDAMENTAL_SPAN_MHZ = 200.0
_FUNDAMENTAL_RBW_MHZ = 1.0
_FUNDAMENTAL_VBW_MHZ = 1.0
_FUNDAMENTAL_SWEEP_POINT = 10001
_FUNDAMENTAL_TRACE_MODE = "View"
_HARMONIC_ORDERS = (2, 3, 4, 5)
_PRECISION_INITIAL_SWEEP_TIME_MS = 100
_PRECISION_RECHECK_SWEEP_TIME_MS = 500


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


def _normalize_harmonic_markers(raw_markers: object) -> list[HarmonicMarker]:
    if isinstance(raw_markers, str | bytes):
        raise ValueError(
            "Harmonic 측정 응답 형식 오류: expected 4 harmonic markers"
        )

    try:
        markers = list(raw_markers)  # type: ignore[arg-type]
    except TypeError as exc:
        raise ValueError(
            "Harmonic 측정 응답 형식 오류: expected 4 harmonic markers"
        ) from exc

    if len(markers) != 4:
        raise ValueError(
            f"Harmonic 측정 응답 형식 오류: expected 4 harmonic markers, got {len(markers)}"
        )

    normalized: list[HarmonicMarker] = []
    for expected_order, marker in zip(_HARMONIC_ORDERS, markers, strict=True):
        order = getattr(marker, "order", expected_order)
        amplitude = getattr(marker, "amplitude_dbm", None)
        frequency = getattr(marker, "peak_frequency_mhz", None)
        try:
            marker_order = int(order)
            amplitude_dbm = float(amplitude)
            peak_frequency_mhz = float(frequency)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "Harmonic 측정 응답 형식 오류: expected numeric amplitude/frequency"
            ) from exc
        if marker_order != expected_order:
            raise ValueError(
                "Harmonic 측정 응답 형식 오류: expected marker order "
                f"{expected_order}, got {marker_order}"
            )
        normalized.append(
            HarmonicMarker(
                order=marker_order,
                amplitude_dbm=amplitude_dbm,
                peak_frequency_mhz=peak_frequency_mhz,
            )
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


def _precision_screenshot_path(temp_dir: Path) -> Path:
    return temp_dir / _PRECISION_SCREENSHOT_NAME


def _remove_stale_screenshot(path: Path) -> None:
    """측정 전 기존 스크린샷 파일을 삭제한다."""
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        raise ValueError(f"stale 스크린샷 삭제 실패: {path}") from exc


def _precision_threshold_dbm(ctx: "SessionContext") -> float:
    return ctx.current_case.range_definition.limit - 3.0


def _build_precision_candidates(
    ctx: "SessionContext",
    markers: list[HarmonicMarker],
) -> list[HarmonicPrecisionCandidate]:
    threshold_dbm = _precision_threshold_dbm(ctx)
    candidates: list[HarmonicPrecisionCandidate] = []
    for marker in markers:
        if marker.amplitude_dbm == 0.0:
            logger.info(
                "Harmonic Precision skip: %sth amplitude is 0, manual measurement range",
                marker.order,
            )
            continue
        if marker.amplitude_dbm >= threshold_dbm:
            logger.info(
                "Harmonic Precision candidate: %sth peak=%.3fMHz amplitude=%.3fdBm",
                marker.order,
                marker.peak_frequency_mhz,
                marker.amplitude_dbm,
            )
            candidates.append(
                HarmonicPrecisionCandidate(
                    order=marker.order,
                    amplitude_dbm=marker.amplitude_dbm,
                    peak_frequency_mhz=marker.peak_frequency_mhz,
                )
            )
            continue
        logger.info(
            "Harmonic Precision skip: %sth amplitude %.3fdBm below threshold %.3fdBm",
            marker.order,
            marker.amplitude_dbm,
            threshold_dbm,
        )
    return candidates


def _build_harmonic_result(
    ctx: "SessionContext",
    *,
    screenshot_path: Path,
    harmonic_markers: list[HarmonicMarker],
) -> HarmonicResult:
    """Harmonic marker 결과를 기존 판정 기준의 리포트 결과로 변환한다."""

    threshold_dbm = ctx.current_case.range_definition.limit - 10.0
    return HarmonicResult(
        screenshot_path=screenshot_path,
        harmonic_2nd_peak_level_dbm=_recordable_peak(
            harmonic_markers[0].amplitude_dbm, threshold_dbm
        ),
        harmonic_3rd_peak_level_dbm=_recordable_peak(
            harmonic_markers[1].amplitude_dbm, threshold_dbm
        ),
        harmonic_4th_peak_level_dbm=_recordable_peak(
            harmonic_markers[2].amplitude_dbm, threshold_dbm
        ),
        harmonic_5th_peak_level_dbm=_recordable_peak(
            harmonic_markers[3].amplitude_dbm, threshold_dbm
        ),
    )


class MeasureFundamentalState(State):
    """기본파 주파수를 측정하여 결과를 저장한다."""

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
            target_frequency_mhz = test_case.frequency_mhz
        except Exception as exc:
            _emit_error(ctx, f"Fundamental 측정 준비 실패: {exc}")
            return StateResult.FAIL

        if ctx.temp_dir is None:
            _emit_error(ctx, "Fundamental 스크린샷 경로 생성 실패: temp_dir is not set")
            return StateResult.FAIL

        screenshot_path = _fundamental_screenshot_path(ctx.temp_dir)
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
    """각 Range의 고조파를 측정하고 스크린샷을 저장한다."""

    name = "MeasureHarmonics"

    def run(self, ctx: "SessionContext") -> StateResult:
        ctx.harmonic_precision_candidates = []
        if not is_equipment_connected(ctx, "FSV40"):
            _emit_error(ctx, "Harmonic 측정 스킵: FSV40이 연결되어 있지 않습니다.")
            return StateResult.OK

        fundamental_frequency_mhz = ctx.fundamental_frequency_mhz
        if fundamental_frequency_mhz is None:
            _emit_error(ctx, "Harmonic 측정 실패: fundamental_frequency_mhz is not set")
            return StateResult.FAIL

        if ctx.temp_dir is None:
            _emit_error(ctx, "Harmonic 스크린샷 경로 생성 실패: temp_dir is not set")
            return StateResult.FAIL

        screenshot_path = _harmonic_screenshot_path(ctx.temp_dir)
        try:
            _remove_stale_screenshot(screenshot_path)
            harmonic_markers = _normalize_harmonic_markers(
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

        result = _build_harmonic_result(
            ctx,
            screenshot_path=screenshot_path,
            harmonic_markers=harmonic_markers,
        )
        written = append_and_write_report(
            ctx,
            result,
            lambda writer: writer.write_harmonic(ctx.current_case, result),
            "Harmonic 리포트 작성 실패: write_harmonic returned false",
        )
        if written is StateResult.OK:
            ctx.harmonic_precision_candidates = _build_precision_candidates(
                ctx,
                harmonic_markers,
            )
        return written

    def next_state(
        self, ctx: "SessionContext", result: StateResult
    ) -> str | None:
        if result is not StateResult.OK:
            return None
        if ctx.harmonic_precision_candidates:
            return "MeasureHarmonicPrecision"
        return "ResetSwitchBox"


class MeasureHarmonicsManualState(State):
    """수동 마커 모드 Harmonic 측정 후 사용자 편집 스크린샷을 저장한다."""

    name = "MeasureHarmonicsManual"

    def run(self, ctx: "SessionContext") -> StateResult:
        ctx.harmonic_precision_candidates = []
        if not is_equipment_connected(ctx, "FSV40"):
            _emit_error(ctx, "Harmonic 수동 측정 스킵: FSV40이 연결되어 있지 않습니다.")
            return StateResult.OK

        fundamental_frequency_mhz = ctx.fundamental_frequency_mhz
        if fundamental_frequency_mhz is None:
            _emit_error(ctx, "Harmonic 수동 측정 실패: fundamental_frequency_mhz is not set")
            return StateResult.FAIL

        if ctx.temp_dir is None:
            _emit_error(ctx, "Harmonic 수동 스크린샷 경로 생성 실패: temp_dir is not set")
            return StateResult.FAIL

        screenshot_path = manual_screenshot_path(ctx.temp_dir)
        try:
            remove_stale_manual_screenshot(screenshot_path)
            harmonic_markers = _normalize_harmonic_markers(
                ctx.commands.measure_harmonic_manual(
                    ctx.client,
                    fundamental=fundamental_frequency_mhz,
                )
            )
        except Exception as exc:
            _emit_error(ctx, f"Harmonic 수동 측정 실패: {exc}")
            return StateResult.FAIL

        result = complete_manual_marker_edit(
            ctx,
            test_type=ctx.current_case.test_type,
            screenshot_path=screenshot_path,
        )
        if result is not StateResult.OK:
            return result

        harmonic_result = _build_harmonic_result(
            ctx,
            screenshot_path=screenshot_path,
            harmonic_markers=harmonic_markers,
        )
        written = append_and_write_report(
            ctx,
            harmonic_result,
            lambda writer: writer.write_harmonic(ctx.current_case, harmonic_result),
            "Harmonic 리포트 작성 실패: write_harmonic returned false",
        )
        if written is StateResult.OK:
            ctx.harmonic_precision_candidates = _build_precision_candidates(
                ctx,
                harmonic_markers,
            )
        return written

    def next_state(
        self, ctx: "SessionContext", result: StateResult
    ) -> str | None:
        if result is not StateResult.OK:
            return None
        if ctx.harmonic_precision_candidates:
            return "MeasureHarmonicPrecision"
        return "ResetSwitchBox"


class MeasureHarmonicPrecisionState(State):
    """Harmonic 정밀측정 후보를 order/sweep 별로 측정하고 스크린샷을 저장한다."""

    name = "MeasureHarmonicPrecision"

    def run(self, ctx: "SessionContext") -> StateResult:
        if not is_equipment_connected(ctx, "FSV40"):
            _emit_error(ctx, "Harmonic Precision 측정 스킵: FSV40이 연결되어 있지 않습니다.")
            return StateResult.OK

        candidates = list(ctx.harmonic_precision_candidates)
        if not candidates:
            logger.info("Harmonic Precision skip: no candidates")
            return StateResult.OK

        if ctx.temp_dir is None:
            _emit_error(
                ctx,
                "Harmonic Precision 스크린샷 경로 생성 실패: temp_dir is not set",
            )
            return StateResult.FAIL

        threshold_dbm = _precision_threshold_dbm(ctx)
        for candidate in candidates:
            amplitude_100ms = self._run_precision_job(
                ctx,
                candidate=candidate,
                sweep_time_ms=_PRECISION_INITIAL_SWEEP_TIME_MS,
            )
            if amplitude_100ms is None:
                return StateResult.FAIL
            if amplitude_100ms >= threshold_dbm:
                logger.info(
                    "Harmonic Precision retry: %sth 500ms because 100ms amplitude=%.3fdBm >= %.3fdBm",
                    candidate.order,
                    amplitude_100ms,
                    threshold_dbm,
                )
                amplitude_500ms = self._run_precision_job(
                    ctx,
                    candidate=candidate,
                    sweep_time_ms=_PRECISION_RECHECK_SWEEP_TIME_MS,
                )
                if amplitude_500ms is None:
                    return StateResult.FAIL

        return StateResult.OK

    def next_state(
        self, ctx: "SessionContext", result: StateResult
    ) -> str | None:
        if result is not StateResult.OK:
            return None
        return "ResetSwitchBox"

    def _run_precision_job(
        self,
        ctx: "SessionContext",
        *,
        candidate: HarmonicPrecisionCandidate,
        sweep_time_ms: int,
    ) -> float | None:
        if (
            not math.isfinite(candidate.peak_frequency_mhz)
            or candidate.peak_frequency_mhz <= 0
        ):
            _emit_error(
                ctx,
                "Harmonic Precision 측정 실패: invalid peak frequency "
                f"{candidate.peak_frequency_mhz!r}",
            )
            return None

        assert ctx.temp_dir is not None
        screenshot_path = _precision_screenshot_path(ctx.temp_dir)
        logger.info(
            "Harmonic Precision start: %sth %sms peak=%.3fMHz",
            candidate.order,
            sweep_time_ms,
            candidate.peak_frequency_mhz,
        )
        try:
            _remove_stale_screenshot(screenshot_path)
            configured = ctx.commands.setup_sa_precision(
                ctx.client,
                peak_frequency=candidate.peak_frequency_mhz,
                sweep_time=sweep_time_ms,
            )
            if not configured:
                _emit_error(
                    ctx,
                    "Harmonic Precision SA 설정 실패: setup_sa_precision returned false",
                )
                return None
            if not _wait_for_saturation_time(ctx):
                return None

            rotation_result = self._rotate_turntable(ctx)
            if rotation_result is not StateResult.OK:
                return None

            amplitude_dbm = float(ctx.commands.measure_harmonic_precision(ctx.client))
        except Exception as exc:
            _emit_error(ctx, f"Harmonic Precision 측정 실패: {exc}")
            return None

        if not screenshot_path.is_file():
            _emit_error(
                ctx,
                f"Harmonic Precision 스크린샷 저장 실패: {screenshot_path} does not exist",
            )
            return None

        try:
            destination = finalize_harmonic_precision_screenshot(
                source_path=screenshot_path,
                root_dir=ctx.screenshot_root_dir,
                model_name=ctx.model_name,
                test_case=ctx.current_case,
                peak_frequency_mhz=candidate.peak_frequency_mhz,
                sweep_time_ms=sweep_time_ms,
                events=ctx.events,
            )
        except Exception as exc:
            _emit_error(ctx, f"Harmonic Precision 스크린샷 저장 실패: {exc}")
            return None

        logger.info("Harmonic Precision saved: %s", destination)
        return amplitude_dbm

    def _rotate_turntable(self, ctx: "SessionContext") -> StateResult:
        state = RotateTurntableState()
        entered = False
        try:
            state.enter(ctx)
            entered = True
            return state.run(ctx)
        finally:
            if entered:
                state.exit(ctx)

