"""파일 대화상자 디렉터리 설정 저장소."""
from __future__ import annotations

import json
import logging
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_SETTINGS_DIRECTORY_NAME = "config"
_SETTINGS_FILE_NAME = "file_dialog_directories.json"


def runtime_base_directory() -> Path:
    """배포 EXE 또는 개발 작업 디렉터리를 반환한다."""

    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd().resolve()


def default_file_dialog_directory_settings_path() -> Path:
    """실행 환경 기준 파일 대화상자 설정 경로를 반환한다."""

    return (
        runtime_base_directory()
        / _SETTINGS_DIRECTORY_NAME
        / _SETTINGS_FILE_NAME
    )


@dataclass(frozen=True)
class FileDialogDirectorySettings:
    """파일 종류별 대화상자 시작 디렉터리 설정."""

    excel_directory: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FileDialogDirectorySettings":
        """JSON dict를 설정 객체로 변환한다."""

        excel_directory = data.get("excel_directory", "")
        if not isinstance(excel_directory, str):
            excel_directory = ""
        return cls(excel_directory=excel_directory)


class FileDialogDirectorySettingsStore:
    """파일 대화상자 디렉터리 설정을 JSON 파일로 읽고 쓴다."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = (
            default_file_dialog_directory_settings_path()
            if path is None
            else Path(path)
        )

    def load(self) -> FileDialogDirectorySettings:
        """저장된 설정을 읽고, 실패하면 빈 설정을 반환한다."""

        if not self._path.is_file():
            return FileDialogDirectorySettings()

        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("file dialog directory settings must be an object")
            return FileDialogDirectorySettings.from_dict(data)
        except Exception:
            logger.warning(
                "File dialog directory settings load failed: %s",
                self._path,
                exc_info=True,
            )
            return FileDialogDirectorySettings()

    def save(self, settings: FileDialogDirectorySettings) -> None:
        """설정을 JSON 파일로 저장하고, 실패해도 앱 실행은 계속한다."""

        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(asdict(settings), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except Exception:
            logger.warning(
                "File dialog directory settings save failed: %s",
                self._path,
                exc_info=True,
            )
