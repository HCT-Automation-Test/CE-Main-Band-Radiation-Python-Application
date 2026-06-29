from __future__ import annotations

import socket
from pathlib import Path
from typing import Any

import pytest

from app.net import lv_server_process
from app.net.lv_server_process import LvServerError, LvServerManager


class _Process:
    def __init__(self) -> None:
        self.pid = 1234
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


def test_lv_server_manager_cleans_up_process_when_startup_wait_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exe = tmp_path / "Application.exe"
    exe.write_text("", encoding="utf-8")
    process = _Process()
    monkeypatch.setattr("subprocess.Popen", lambda *args, **kwargs: process)
    manager = LvServerManager(exe_path=exe, port=0, startup_wait_s=0)

    def fail_wait_until_port_open() -> None:
        raise LvServerError("port did not open")

    monkeypatch.setattr(manager, "_wait_until_port_open", fail_wait_until_port_open)

    with pytest.raises(LvServerError, match="port did not open"):
        manager.ensure_running()

    assert process.terminated is True
    assert manager._process is None


def test_lv_server_manager_rehides_window_when_already_running(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exe = tmp_path / "Application.exe"
    exe.write_text("", encoding="utf-8")
    process = _Process()
    calls: list[tuple[_Process, Path, float]] = []
    manager = LvServerManager(
        exe_path=exe,
        port=0,
        startup_wait_s=0,
        hide_window_poll_s=3.0,
    )
    manager._process = process

    monkeypatch.setattr(
        lv_server_process,
        "_start_hide_process_windows_worker",
        lambda process, *, exe_path, timeout_s: calls.append((process, exe_path, timeout_s)),
    )

    manager.ensure_running()

    assert calls == [(process, exe, 3.0)]


def test_lv_server_manager_starts_hidden_window_on_windows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exe = tmp_path / "Application.exe"
    exe.write_text("", encoding="utf-8")
    process = _Process()
    calls: list[dict[str, Any]] = []

    def popen(*args: Any, **kwargs: Any) -> _Process:
        _ = args
        calls.append(kwargs)
        return process

    monkeypatch.setattr(lv_server_process.sys, "platform", "win32")
    monkeypatch.setattr(lv_server_process.subprocess, "Popen", popen)
    monkeypatch.setattr(lv_server_process, "_hide_process_windows", lambda *args, **kwargs: None)
    manager = LvServerManager(exe_path=exe, port=0, startup_wait_s=0)

    manager.ensure_running()

    assert calls
    kwargs = calls[0]
    assert kwargs["creationflags"] == lv_server_process.subprocess.CREATE_NO_WINDOW
    startupinfo = kwargs["startupinfo"]
    assert startupinfo is not None
    assert startupinfo.dwFlags & lv_server_process.subprocess.STARTF_USESHOWWINDOW
    assert startupinfo.wShowWindow == lv_server_process.subprocess.SW_HIDE


def test_hide_process_windows_worker_runs_as_daemon(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exe = tmp_path / "Application.exe"
    exe.write_text("", encoding="utf-8")
    process = _Process()
    calls: list[dict[str, Any]] = []

    class Thread:
        def __init__(self, **kwargs: Any) -> None:
            calls.append(kwargs)

        def start(self) -> None:
            calls.append({"started": True})

    monkeypatch.setattr(lv_server_process.sys, "platform", "win32")
    monkeypatch.setattr(lv_server_process.threading, "Thread", Thread)

    lv_server_process._start_hide_process_windows_worker(
        process,
        exe_path=exe,
        timeout_s=3.0,
    )

    assert calls[0]["target"] is lv_server_process._hide_process_windows
    assert calls[0]["kwargs"] == {
        "process": process,
        "exe_path": exe,
        "timeout_s": 3.0,
    }
    assert calls[0]["name"] == "lv-window-hide"
    assert calls[0]["daemon"] is True
    assert calls[1] == {"started": True}


def test_hide_process_windows_polls_owned_pid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = _Process()
    calls: list[int] = []
    monotonic_values = iter([0.0, 0.0, 1.0])

    monkeypatch.setattr(lv_server_process.sys, "platform", "win32")
    monkeypatch.setattr(lv_server_process, "_HIDE_WINDOW_POLL_INTERVAL_S", 0.0)
    monkeypatch.setattr(lv_server_process.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(lv_server_process.time, "monotonic", lambda: next(monotonic_values))
    monkeypatch.setattr(
        lv_server_process,
        "_hide_windows_for_process",
        lambda pid, _exe_path, _exe_name: calls.append(pid) or True,
    )

    lv_server_process._hide_process_windows(process, timeout_s=0.5)

    assert calls == [process.pid, process.pid]


def test_hide_process_windows_logs_and_continues_on_hide_failure(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = _Process()

    monkeypatch.setattr(lv_server_process.sys, "platform", "win32")
    monkeypatch.setattr(
        lv_server_process,
        "_hide_windows_for_process",
        lambda _pid, _exe_path, _exe_name: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    lv_server_process._hide_process_windows(process, timeout_s=0.5)

    assert "LV Server window hide failed" in caplog.text

def test_is_target_window_process_accepts_matching_exe_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        lv_server_process,
        "_process_exe_path",
        lambda _pid: r"C:\Other Runtime\Application.exe".casefold(),
    )

    assert lv_server_process._is_target_window_process(
        4321,
        1234,
        r"C:\LV Inst Manager\Application.exe".casefold(),
        "application.exe",
    )
