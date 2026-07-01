"""Instrument Check 연결 설정 저장소."""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_INSTRUMENT_CONNECTION_SETTINGS_PATH = Path(
    "config/instrument_connection.json"
)


@dataclass(frozen=True)
class InstrumentConnectionSettings:
    """Instrument Check 입력 필드에 복원할 연결 설정."""

    mt8000a_visa_resource: str = ""
    fsv40_visa_resource: str = ""
    co3000_visa_resource: str = ""
    controller_3d_visa_resource: str = ""
    switch_box_ip_address: str = ""
    switch_box_port: int | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "InstrumentConnectionSettings":
        """JSON dict를 설정 객체로 변환한다."""

        return cls(
            mt8000a_visa_resource=str(data.get("mt8000a_visa_resource", "")),
            fsv40_visa_resource=str(data.get("fsv40_visa_resource", "")),
            co3000_visa_resource=str(data.get("co3000_visa_resource", "")),
            controller_3d_visa_resource=str(
                data.get("controller_3d_visa_resource", "")
            ),
            switch_box_ip_address=str(data.get("switch_box_ip_address", "")),
            switch_box_port=_optional_port(data.get("switch_box_port")),
        )


class InstrumentConnectionSettingsStore:
    """Instrument Check 연결 설정 JSON 파일을 읽고 쓴다."""

    def __init__(
        self,
        path: Path = DEFAULT_INSTRUMENT_CONNECTION_SETTINGS_PATH,
    ) -> None:
        self._path = Path(path)

    def load(self) -> InstrumentConnectionSettings:
        """저장된 설정을 읽고, 실패하면 빈 설정을 반환한다."""

        if not self._path.is_file():
            return InstrumentConnectionSettings()

        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("instrument connection settings must be an object")
            return InstrumentConnectionSettings.from_dict(data)
        except Exception:
            logger.warning(
                "Instrument connection settings load failed: %s",
                self._path,
                exc_info=True,
            )
            return InstrumentConnectionSettings()

    def save(self, settings: InstrumentConnectionSettings) -> None:
        """설정을 JSON 파일로 저장하고, 실패해도 앱 실행은 계속한다."""

        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(asdict(settings), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except Exception:
            logger.warning(
                "Instrument connection settings save failed: %s",
                self._path,
                exc_info=True,
            )


def _optional_port(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        port = int(value)
    except (TypeError, ValueError):
        return None
    if not 1 <= port <= 65535:
        return None
    return port
