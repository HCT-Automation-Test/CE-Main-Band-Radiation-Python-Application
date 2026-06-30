"""LabVIEW Server 실행 프로세스 관리."""
from __future__ import annotations

import logging
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_LV_SERVER_HOST = "127.0.0.1"
DEFAULT_LV_SERVER_PORT = 5025
LV_SERVER_DIR_NAME = "LV Inst Manager"
LV_SERVER_EXE_NAME = "LV Inst Manager.exe"
_HIDE_WINDOW_POLL_TIMEOUT_S = 10.0
_HIDE_WINDOW_POLL_INTERVAL_S = 0.05


class LvServerError(RuntimeError):
    """LV Server 실행/종료 관리 오류."""


def default_lv_server_exe_path() -> Path:
    """실행 파일 또는 개발 작업 디렉터리 기준 LV Server exe 경로를 반환한다."""

    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        candidates = [
            exe_dir / LV_SERVER_DIR_NAME / LV_SERVER_EXE_NAME,
            Path(getattr(sys, "_MEIPASS", exe_dir)) / LV_SERVER_DIR_NAME / LV_SERVER_EXE_NAME,
        ]
        for candidate in candidates:
            if candidate.is_file():
                return candidate
        return candidates[0]
    return Path.cwd() / LV_SERVER_DIR_NAME / LV_SERVER_EXE_NAME


class LvServerManager:
    """Python 앱이 띄운 LV Server 프로세스만 관리한다."""

    def __init__(
        self,
        *,
        exe_path: Path | str | None = None,
        host: str = DEFAULT_LV_SERVER_HOST,
        port: int = DEFAULT_LV_SERVER_PORT,
        startup_wait_s: float = 10.0,
        terminate_timeout_s: float = 3.0,
        hide_window_poll_s: float = _HIDE_WINDOW_POLL_TIMEOUT_S,
    ) -> None:
        self.exe_path = Path(exe_path) if exe_path is not None else default_lv_server_exe_path()
        self.host = host
        self.port = int(port)
        self.startup_wait_s = float(startup_wait_s)
        self.terminate_timeout_s = float(terminate_timeout_s)
        self.hide_window_poll_s = float(hide_window_poll_s)
        self._process: subprocess.Popen[object] | None = None

    @property
    def is_running(self) -> bool:
        process = self._process
        return process is not None and process.poll() is None

    def ensure_running(self) -> None:
        """LV Server가 실행 중이 아니면 새로 실행한다."""

        if self.is_running:
            self._start_hide_window_worker()
            self._wait_until_port_open()
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
        startupinfo = None
        if sys.platform == "win32":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            startupinfo = _hidden_startupinfo()
        self._process = subprocess.Popen(
            [str(self.exe_path)],
            cwd=str(self.exe_path.parent),
            creationflags=creationflags,
            startupinfo=startupinfo,
        )
        try:
            self._start_hide_window_worker()
            if self._process.poll() is not None:
                exit_code = self._process.returncode
                raise LvServerError(f"LV Server가 시작 직후 종료되었습니다: exit_code={exit_code}")
            self._wait_until_port_open()
        except Exception:
            self.shutdown()
            raise

    def _start_hide_window_worker(self) -> None:
        process = self._process
        if process is None:
            return
        _start_hide_process_windows_worker(
            process,
            exe_path=self.exe_path,
            timeout_s=self.hide_window_poll_s,
        )

    def _wait_until_port_free(self) -> None:
        deadline = time.monotonic() + self.terminate_timeout_s
        while time.monotonic() < deadline:
            if self._is_port_free():
                return
            time.sleep(0.05)

    def _wait_until_port_open(self) -> None:
        if self.port <= 0 or self.startup_wait_s <= 0:
            return

        deadline = time.monotonic() + self.startup_wait_s
        while time.monotonic() < deadline:
            process = self._process
            if process is not None and process.poll() is not None:
                exit_code = process.returncode
                self._process = None
                raise LvServerError(
                    f"LV Server가 시작 직후 종료되었습니다: exit_code={exit_code}"
                )
            if self._is_port_open():
                return
            time.sleep(0.05)

        raise LvServerError(
            f"LV Server port {self.host}:{self.port}가 {self.startup_wait_s:.1f}초 안에 "
            "대기 상태로 전환되지 않았습니다."
        )

    def _is_port_free(self) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind((self.host, self.port))
            except OSError:
                return False
        return True


    def _is_port_open(self) -> bool:
        try:
            with socket.create_connection((self.host, self.port), timeout=0.1):
                return True
        except OSError:
            return False

def _hidden_startupinfo() -> subprocess.STARTUPINFO | None:
    if sys.platform != "win32":
        return None

    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 1)
    startupinfo.wShowWindow = getattr(subprocess, "SW_HIDE", 0)
    return startupinfo


def _start_hide_process_windows_worker(
    process: subprocess.Popen[object],
    *,
    exe_path: Path,
    timeout_s: float = _HIDE_WINDOW_POLL_TIMEOUT_S,
) -> None:
    if sys.platform != "win32" or timeout_s <= 0:
        return

    thread = threading.Thread(
        target=_hide_process_windows,
        kwargs={
            "process": process,
            "exe_path": exe_path,
            "timeout_s": timeout_s,
        },
        name="lv-window-hide",
        daemon=True,
    )
    thread.start()


def _hide_process_windows(
    process: subprocess.Popen[object],
    *,
    exe_path: Path | None = None,
    timeout_s: float = _HIDE_WINDOW_POLL_TIMEOUT_S,
) -> None:
    """LV가 늦게 만들거나 다시 띄우는 프론트 패널 창까지 숨긴다."""

    if sys.platform != "win32" or timeout_s <= 0:
        return

    pid = getattr(process, "pid", None)
    if not isinstance(pid, int):
        return

    resolved_exe_path = _casefold_resolved_path(exe_path) if exe_path is not None else None
    exe_name = exe_path.name.casefold() if exe_path is not None else None
    deadline = time.monotonic() + timeout_s
    while True:
        try:
            _hide_windows_for_process(pid, resolved_exe_path, exe_name)
        except Exception:
            logger.warning("LV Server window hide failed", exc_info=True)
            return

        poll = getattr(process, "poll", None)
        if callable(poll) and poll() is not None:
            return
        if time.monotonic() >= deadline:
            return
        time.sleep(_HIDE_WINDOW_POLL_INTERVAL_S)


def _hide_windows_for_process(
    pid: int,
    exe_path: str | None = None,
    exe_name: str | None = None,
) -> bool:
    import win32con
    import win32gui
    import win32process

    hidden = False

    def on_window(hwnd: int, _extra: object) -> bool:
        nonlocal hidden
        _thread_id, window_pid = win32process.GetWindowThreadProcessId(hwnd)
        if not _is_target_window_process(window_pid, pid, exe_path, exe_name):
            return True
        if win32gui.IsWindowVisible(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
            hidden = True
        return True

    win32gui.EnumWindows(on_window, None)
    return hidden


def _is_target_window_process(
    window_pid: int,
    owner_pid: int,
    exe_path: str | None,
    exe_name: str | None,
) -> bool:
    if window_pid == owner_pid:
        return True
    process_path = _process_exe_path(window_pid)
    if process_path is None:
        return False
    if exe_path is not None and process_path == exe_path:
        return True
    return exe_name is not None and Path(process_path).name.casefold() == exe_name


def _process_exe_path(pid: int) -> str | None:
    try:
        import win32api
        import win32con
        import win32process

        access = win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ
        handle = win32api.OpenProcess(access, False, pid)
        try:
            return _casefold_resolved_path(Path(win32process.GetModuleFileNameEx(handle, 0)))
        finally:
            win32api.CloseHandle(handle)
    except Exception:
        return None


def _casefold_resolved_path(path: Path) -> str:
    return str(path.resolve()).casefold()
