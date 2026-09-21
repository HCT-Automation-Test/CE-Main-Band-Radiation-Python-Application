"""Manual Test Screenshot 저장 경로와 no-overwrite 복사를 제공한다."""
from __future__ import annotations

import re
import shutil
from pathlib import Path

_INVALID_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def build_manual_screenshot_paths(
    *,
    directory: Path,
    base_name: str,
    shot_count: int,
    numbered: bool,
) -> tuple[Path, ...]:
    root = Path(directory)
    if not root.is_dir():
        raise ValueError("유효한 Screenshot 저장 폴더를 선택하세요.")
    if isinstance(shot_count, bool) or not isinstance(shot_count, int) or shot_count <= 0:
        raise ValueError("N Shots는 1 이상의 정수여야 합니다.")

    name = base_name.strip()
    if name.lower().endswith(".png"):
        name = name[:-4].rstrip()
    if not name or _INVALID_FILENAME_CHARS.search(name) or name in {".", ".."}:
        raise ValueError("유효한 Screenshot File Name을 입력하세요.")
    name = name.rstrip(" .")
    if not name:
        raise ValueError("유효한 Screenshot File Name을 입력하세요.")

    if numbered:
        return tuple(
            root / f"{name}_{index:03d}.png"
            for index in range(1, shot_count + 1)
        )
    if shot_count != 1:
        raise ValueError("Single Capture의 shot_count는 1이어야 합니다.")
    return (root / f"{name}.png",)


def ensure_manual_screenshot_paths_available(paths: tuple[Path, ...]) -> None:
    existing = next((path for path in paths if path.exists()), None)
    if existing is not None:
        raise FileExistsError(f"이미 존재하는 Screenshot 파일입니다: {existing}")


def save_manual_screenshot(*, source_path: Path, destination_path: Path) -> Path:
    source = Path(source_path)
    destination = Path(destination_path)
    if not source.is_file():
        raise FileNotFoundError(f"Screenshot 임시 파일을 찾을 수 없습니다: {source}")
    with source.open("rb") as source_file:
        if source_file.read(len(_PNG_SIGNATURE)) != _PNG_SIGNATURE:
            raise ValueError(f"유효한 PNG Screenshot 파일이 아닙니다: {source}")

    try:
        with source.open("rb") as source_file, destination.open("xb") as output_file:
            shutil.copyfileobj(source_file, output_file)
    except FileExistsError as exc:
        raise FileExistsError(
            f"이미 존재하는 Screenshot 파일입니다: {destination}"
        ) from exc
    return destination
