from __future__ import annotations

from pathlib import Path

import pytest

from app.report.manual_screenshot_store import (
    build_manual_screenshot_paths,
    ensure_manual_screenshot_paths_available,
    normalize_manual_screenshot_name,
    save_manual_screenshot,
)


def test_build_single_and_numbered_manual_screenshot_paths(tmp_path: Path) -> None:
    assert build_manual_screenshot_paths(
        directory=tmp_path,
        base_name="capture.png",
        shot_count=1,
        numbered=False,
    ) == (tmp_path / "capture.png",)
    assert build_manual_screenshot_paths(
        directory=tmp_path,
        base_name="capture",
        shot_count=3,
        numbered=True,
    ) == (
        tmp_path / "capture_001.png",
        tmp_path / "capture_002.png",
        tmp_path / "capture_003.png",
    )


@pytest.mark.parametrize("name", ["", "..", "bad/name", "bad?.png", "...  "])
def test_manual_screenshot_name_rejects_invalid_values(name: str) -> None:
    with pytest.raises(ValueError):
        normalize_manual_screenshot_name(name)


def test_preflight_rejects_any_existing_destination(tmp_path: Path) -> None:
    paths = build_manual_screenshot_paths(
        directory=tmp_path,
        base_name="capture",
        shot_count=2,
        numbered=True,
    )
    paths[1].write_bytes(b"existing")

    with pytest.raises(FileExistsError, match="capture_002"):
        ensure_manual_screenshot_paths_available(paths)


def test_save_manual_screenshot_never_overwrites(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    destination = tmp_path / "result.png"
    source.write_bytes(b"\x89PNG\r\n\x1a\nnew")
    destination.write_bytes(b"old")

    with pytest.raises(FileExistsError):
        save_manual_screenshot(source_path=source, destination_path=destination)

    assert destination.read_bytes() == b"old"


def test_save_manual_screenshot_copies_valid_png(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    destination = tmp_path / "result.png"
    payload = b"\x89PNG\r\n\x1a\nfixture"
    source.write_bytes(payload)

    assert save_manual_screenshot(
        source_path=source,
        destination_path=destination,
    ) == destination
    assert destination.read_bytes() == payload
