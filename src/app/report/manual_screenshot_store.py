"""Manual Test Screenshot의 strict no-overwrite 저장소."""
from __future__ import annotations

import re
import shutil
from pathlib import Path

_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def normalize_manual_screenshot_name(value: str) -> str:
    """PNG 확장자를 제외한 기준 파일명을 검증한다."""

    normalized = value.strip()
    if normalized.lower().endswith(".png"):
        normalized = normalized[:-4].rstrip()
    if not normalized:
        raise ValueError("Screenshot File Name을 입력하세요.")
    if _INVALID_FILENAME_CHARS.search(normalized) or normalized in {".", ".."}:
        raise ValueError("Screenshot File Name에 사용할 수 없는 문자가 있습니다.")
    normalized = normalized.rstrip(" .")
    if not normalized:
        raise ValueError("Screenshot File Name을 입력하세요.")
    return normalized


def build_manual_screenshot_paths(
    *,
    directory: Path,
    base_name: str,
    shot_count: int,
    numbered: bool,
) -> tuple[Path, ...]:
    """Single/N-Capture의 최종 경로 전체를 미리 계산한다."""

    root = Path(directory)
    if not root.is_dir():
        raise ValueError("유효한 Screenshot 저장 폴더를 선택하세요.")
    if (
        isinstance(shot_count, bool)
        or not isinstance(shot_count, int)
        or shot_count <= 0
    ):
        raise ValueError("N Shots는 1 이상의 정수여야 합니다.")
    name = normalize_manual_screenshot_name(base_name)
    if numbered:
        return tuple(root / f"{name}_{index:03d}.png" for index in range(1, shot_count + 1))
    if shot_count != 1:
        raise ValueError("Single Capture의 shot_count는 1이어야 합니다.")
    return (root / f"{name}.png",)


def ensure_manual_screenshot_paths_available(paths: tuple[Path, ...]) -> None:
    """생성 예정 경로 중 하나라도 존재하면 전체 시작을 차단한다."""

    existing = next((path for path in paths if path.exists()), None)
    if existing is not None:
        raise FileExistsError(f"이미 존재하는 Screenshot 파일입니다: {existing}")


def save_manual_screenshot(*, source_path: Path, destination_path: Path) -> Path:
    """LV 임시 PNG를 덮어쓰지 않고 최종 경로에 복사한다."""

    source = Path(source_path)
    destination = Path(destination_path)
    if not source.is_file():
        raise FileNotFoundError(f"Screenshot 임시 파일을 찾을 수 없습니다: {source}")
    with source.open("rb") as source_check:
        if source_check.read(len(_PNG_SIGNATURE)) != _PNG_SIGNATURE:
            raise ValueError(f"유효한 PNG Screenshot 파일이 아닙니다: {source}")

    # exclusive create로 preflight 이후의 경합에서도 덮어쓰기를 막는다.
    created = False
    try:
        with source.open("rb") as source_file, destination.open("xb") as output_file:
            created = True
            shutil.copyfileobj(source_file, output_file)
    except FileExistsError as exc:
        raise FileExistsError(
            f"이미 존재하는 Screenshot 파일입니다: {destination}"
        ) from exc
    except Exception:
        if created:
            destination.unlink(missing_ok=True)
        raise
    return destination
