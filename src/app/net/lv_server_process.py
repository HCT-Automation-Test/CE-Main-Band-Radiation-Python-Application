"""LabVIEW Server 실행 프로세스 관리."""
from __future__ import annotations

import logging
import socket
import subprocess
import sys
import time
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_LV_SERVER_HOST = "127.0.0.1"
DEFAULT_LV_SERVER_PORT = 5025
LV_SERVER_DIR_NAME = "LV Inst Manager"
LV_SERVER_EXE_NAME = "Application.exe"


class LvServerError(RuntimeError):
    """LV Server 실행/종료 관리 오류."""


def default_lv_server_exe_path() -> Path:
    """실행 파일 또는 개발 작업 디렉터리 기준 LV Server exe 경로를 반환한다."""

    if getattr(sys, "frozen", False):
        base_dir = Path(sys.executable).resolve().parent
    else:
        base_dir = Path.cwd()
    return base_dir / LV_SERVER_DIR_NAME / LV_SERVER_EXE_NAME


class LvServerManager:
    """Python 앱이 띄운 LV Server 프로세스만 관리한다."""

    def __init__(
        self,
        *,
        exe_path: Path | str | None = None,
        host: str = DEFAULT_LV_SERVER_HOST,
        port: int = DEFAULT_LV_SERVER_PORT,
        startup_wait_s: float = 0.2,
        terminate_timeout_s: float = 3.0,
    ) -> None:
        self.exe_path = Path(exe_path) if exe_path is not None else default_lv_server_exe_path()
        self.host = host
        self.port = int(port)
        self.startup_wait_s = float(startup_wait_s)
        self.terminate_timeout_s = float(terminate_timeout_s)
        self._process: subprocess.Popen[object] | None = None

    @property
    def is_running(self) -> bool:
        process = self._process
        return process is not None and process.poll() is None

    def ensure_running(self) -> None:
        """LV Server가 실행 중이 아니면 새로 실행한다."""

        if self.is_running:
            return
        self._process = None
        self._start_process()

    def restart(self) -> None:
        """Python이 띄운 LV Server를 종료한 뒤 다시 실행한다."""

        self.shutdown()
        self._wait_until_port_free()
        self._start_process()

    def shutdown(self) -> None:
        """Python이 소유한 LV Server 프로세스만 종료한다."""

        process = self._process
        self._process = None
        if process is None or process.poll() is not None:
            return

        process.terminate()
        try:
            process.wait(timeout=self.terminate_timeout_s)
        except subprocess.TimeoutExpired:
            logger.warning("LV Server did not terminate; killing owned process")
            process.kill()
            process.wait(timeout=self.terminate_timeout_s)

    def _start_process(self) -> None:
        if not self.exe_path.is_file():
            raise LvServerError(f"LV Server exe를 찾을 수 없습니다: {self.exe_path}")
        if not self._is_port_free():
            raise LvServerError(
                f"LV Server port {self.host}:{self.port}가 이미 사용 중입니다. "
                "점유 프로그램을 종료한 뒤 다시 시도하세요."
            )

        creationflags = 0
        if sys.platform == "win32":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        self._process = subprocess.Popen(
            [str(self.exe_path)],
            cwd=str(self.exe_path.parent),
            creationflags=creationflags,
        )
        if self.startup_wait_s > 0:
            time.sleep(self.startup_wait_s)
        if self._process.poll() is not None:
            exit_code = self._process.returncode
            self._process = None
            raise LvServerError(f"LV Server가 시작 직후 종료되었습니다: exit_code={exit_code}")

    def _wait_until_port_free(self) -> None:
        deadline = time.monotonic() + self.terminate_timeout_s
        while time.monotonic() < deadline:
            if self._is_port_free():
                return
            time.sleep(0.05)

    def _is_port_free(self) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind((self.host, self.port))
            except OSError:
                return False
        return True
