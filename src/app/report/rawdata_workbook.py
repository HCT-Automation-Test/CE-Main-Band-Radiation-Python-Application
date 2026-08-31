"""EUT/RAT별 RawData 결과 workbook lifecycle."""
from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from app.models.enums import Generation
from app.report.rawdata_source import (
    RawDataSourceError,
    RawDataWorkbookKind,
    resolve_rawdata_source,
    validate_rawdata_workbook,
    workbook_kind_for_generation,
)

_INVALID_EUT_NAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    "CLOCK$",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}


class RawDataWorkbookError(RuntimeError):
    """RawData 결과 workbook을 안전하게 확보할 수 없을 때 발생한다."""


@dataclass(frozen=True)
class RawDataResultWorkbook:
    """검증을 마친 canonical RawData 결과 workbook."""

    kind: RawDataWorkbookKind
    path: Path
    created: bool


def ensure_rawdata_result_workbook(
    *,
    screenshot_root_dir: Path,
    eut_name: str,
    generation: Generation,
    resource_root: Path | None = None,
) -> RawDataResultWorkbook:
    """기존 결과를 재사용하거나 기준 양식에서 새 결과를 복사한다."""

    kind = workbook_kind_for_generation(generation)
    safe_eut_name = validate_eut_name(eut_name)
    root = Path(screenshot_root_dir).resolve()
    result_directory = (root / safe_eut_name).resolve()
    result_path = (
        result_directory
        / f"{safe_eut_name}_CE Main_Radiation_{kind.value}.xlsx"
    ).resolve()
    _ensure_within_root(root, result_directory, field_name="EUT result directory")
    _ensure_within_root(root, result_path, field_name="RawData result workbook")

    if result_path.exists():
        _validate_existing_result(result_path, kind)
        return RawDataResultWorkbook(kind=kind, path=result_path, created=False)

    try:
        source = resolve_rawdata_source(generation, resource_root=resource_root)
    except RawDataSourceError as exc:
        raise RawDataWorkbookError(str(exc)) from exc

    _prepare_result_directory(root, result_directory)
    created = _copy_source_exclusively(source.path, result_path, kind)
    if not created:
        _validate_existing_result(result_path, kind)
    return RawDataResultWorkbook(kind=kind, path=result_path, created=created)


def validate_eut_name(eut_name: str) -> str:
    """Windows canonical 경로에 안전한 EUT Name만 허용한다."""

    if not isinstance(eut_name, str):
        raise RawDataWorkbookError("EUT Name must be a string")
    normalized = eut_name.strip()
    if not normalized:
        raise RawDataWorkbookError("EUT Name is required")
    if normalized != eut_name or normalized.endswith("."):
        raise RawDataWorkbookError(
            "EUT Name must not have leading/trailing whitespace or a trailing dot: "
            f"{eut_name!r}"
        )
    if normalized in {".", ".."}:
        raise RawDataWorkbookError(f"EUT Name is unsafe: {eut_name!r}")
    if _INVALID_EUT_NAME_CHARS.search(normalized):
        raise RawDataWorkbookError(
            f"EUT Name contains invalid filesystem characters: {eut_name!r}"
        )
    reserved_stem = normalized.split(".", 1)[0].upper()
    if reserved_stem in _WINDOWS_RESERVED_NAMES:
        raise RawDataWorkbookError(f"EUT Name is a reserved Windows name: {eut_name!r}")
    return normalized


def _ensure_within_root(root: Path, candidate: Path, *, field_name: str) -> None:
    if candidate != root and candidate.is_relative_to(root):
        return
    raise RawDataWorkbookError(f"{field_name} escapes screenshot root: {candidate}")


def _prepare_result_directory(root: Path, result_directory: Path) -> None:
    if root.exists() and not root.is_dir():
        raise RawDataWorkbookError(f"Screenshot root is not a directory: {root}")
    try:
        result_directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise RawDataWorkbookError(
            f"RawData result directory could not be created: {result_directory}: {exc}"
        ) from exc
    if not result_directory.is_dir():
        raise RawDataWorkbookError(
            f"RawData result directory is not a directory: {result_directory}"
        )


def _copy_source_exclusively(
    source_path: Path,
    result_path: Path,
    kind: RawDataWorkbookKind,
) -> bool:
    """기존 target을 덮어쓰지 않고 source를 복사한다.

    다른 실행 주체가 먼저 target을 만든 경우 ``False``를 반환한다. 현재 호출이
    target을 만든 뒤 실패하면 그 부분 파일만 제거한다.
    """

    created_by_this_call = False
    try:
        with result_path.open("xb") as result_file:
            created_by_this_call = True
            with source_path.open("rb") as source_file:
                shutil.copyfileobj(source_file, result_file)
            result_file.flush()
            os.fsync(result_file.fileno())
        _validate_result_workbook(result_path, kind)
    except FileExistsError:
        return False
    except Exception as exc:
        if created_by_this_call:
            try:
                result_path.unlink(missing_ok=True)
            except OSError as cleanup_exc:
                raise RawDataWorkbookError(
                    "RawData source copy failed and the partial result could not be "
                    f"removed: {result_path}: {cleanup_exc}"
                ) from exc
        if isinstance(exc, RawDataWorkbookError):
            raise
        raise RawDataWorkbookError(
            f"RawData source copy failed: {source_path} -> {result_path}: {exc}"
        ) from exc
    return True


def _validate_existing_result(path: Path, kind: RawDataWorkbookKind) -> None:
    if not path.is_file():
        raise RawDataWorkbookError(f"RawData result path is not a file: {path}")
    _validate_result_workbook(path, kind)


def _validate_result_workbook(path: Path, kind: RawDataWorkbookKind) -> None:
    try:
        validate_rawdata_workbook(path, kind)
    except RawDataSourceError as exc:
        raise RawDataWorkbookError(
            f"RawData result workbook is invalid: {path}: {exc}"
        ) from exc
