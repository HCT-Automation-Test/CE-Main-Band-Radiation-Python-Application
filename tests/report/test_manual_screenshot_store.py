from __future__ import annotations

from pathlib import Path

import pytest

from app.report.manual_screenshot_store import (
    build_manual_screenshot_paths,
    ensure_manual_screenshot_paths_available,
    save_manual_screenshot,
)


def test_build_manual_screenshot_paths(tmp_path: Path) -> None:
    assert build_manual_screenshot_paths(
        directory=tmp_path,
        base_name="capture.png",
        shot_count=1,
        numbered=False,
    ) == (tmp_path / "capture.png",)
    assert build_manual_screenshot_paths(
        directory=tmp_path,
        base_name="capture",
        shot_count=2,
        numbered=True,
    ) == (
        tmp_path / "capture_001.png",
        tmp_path / "capture_002.png",
    )


def test_manual_screenshot_preflight_rejects_collision(tmp_path: Path) -> None:
    paths = build_manual_screenshot_paths(
        directory=tmp_path,
        base_name="capture",
        shot_count=2,
        numbered=True,
    )
    paths[1].write_bytes(b"existing")

    with pytest.raises(FileExistsError, match="capture_002"):
        ensure_manual_screenshot_paths_available(paths)


def test_save_manual_screenshot_copies_png_without_overwrite(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    destination = tmp_path / "capture.png"
    payload = b"\x89PNG\r\n\x1a\nfixture"
    source.write_bytes(payload)

    assert save_manual_screenshot(
        source_path=source,
        destination_path=destination,
    ) == destination
    assert destination.read_bytes() == payload

    with pytest.raises(FileExistsError):
        save_manual_screenshot(
            source_path=source,
            destination_path=destination,
        )
