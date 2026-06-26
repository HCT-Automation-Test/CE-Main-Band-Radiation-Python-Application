from __future__ import annotations

import socket
from pathlib import Path
from typing import Any

import pytest

from app.net.lv_server_process import LvServerError, LvServerManager


class _Process:
    def __init__(self) -> None:
        self.terminated = False
        self.killed = False
        self.returncode = None

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        self.terminated = True
        self.returncode = 0

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9

    def wait(self, timeout: float | None = None) -> int:
        _ = timeout
        return self.returncode or 0


def test_lv_server_manager_reports_missing_exe(tmp_path: Path) -> None:
    manager = LvServerManager(exe_path=tmp_path / "missing.exe")

    with pytest.raises(LvServerError, match="LV Server exe"):
        manager.ensure_running()


def test_lv_server_manager_blocks_when_port_is_occupied(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exe = tmp_path / "Application.exe"
    exe.write_text("", encoding="utf-8")
    calls: list[Any] = []
    monkeypatch.setattr("subprocess.Popen", lambda *args, **kwargs: calls.append(args))

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        manager = LvServerManager(exe_path=exe, port=port)

        with pytest.raises(LvServerError, match="이미 사용 중"):
            manager.ensure_running()

    assert calls == []


def test_lv_server_manager_shutdown_terminates_owned_process(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exe = tmp_path / "Application.exe"
    exe.write_text("", encoding="utf-8")
    process = _Process()
    monkeypatch.setattr("subprocess.Popen", lambda *args, **kwargs: process)
    manager = LvServerManager(exe_path=exe, port=0, startup_wait_s=0)

    manager.ensure_running()
    manager.shutdown()

    assert process.terminated is True
