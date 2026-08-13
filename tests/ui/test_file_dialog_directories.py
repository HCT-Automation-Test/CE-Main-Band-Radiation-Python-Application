from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QLineEdit, QPushButton

from app.ui.test_manager_panel import TestManagerPanel as ManagerPanel


def test_excel_dialog_keeps_current_path_as_initial_location(
    qtbot,
    monkeypatch,
    tmp_path,
) -> None:
    panel = ManagerPanel()
    qtbot.addWidget(panel)
    current_path = tmp_path / "current.xlsx"
    panel.findChild(QLineEdit, "excelTemplatePathEdit").setText(str(current_path))

    def fake_get_open_file_name(parent, caption, directory, selected_filter):
        assert directory == str(current_path)
        return "", selected_filter

    monkeypatch.setattr(QFileDialog, "getOpenFileName", fake_get_open_file_name)

    panel.findChild(QPushButton, "excelTemplateBrowseButton").click()


def test_source_runtime_creates_csv_directory_for_load_and_save(
    qtbot,
    monkeypatch,
    tmp_path,
) -> None:
    runtime_directory = tmp_path.resolve()
    monkeypatch.chdir(runtime_directory)
    panel = ManagerPanel()
    qtbot.addWidget(panel)
    opened_directories: list[str] = []

    def fake_get_open_file_name(parent, caption, directory, selected_filter):
        opened_directories.append(directory)
        return "", selected_filter

    def fake_get_save_file_name(parent, caption, directory, selected_filter):
        opened_directories.append(directory)
        return "", selected_filter

    monkeypatch.setattr(QFileDialog, "getOpenFileName", fake_get_open_file_name)
    monkeypatch.setattr(QFileDialog, "getSaveFileName", fake_get_save_file_name)

    panel.findChild(QPushButton, "loadItemButton").click()
    panel.findChild(QPushButton, "saveItemButton").click()

    csv_directory = runtime_directory / "CSV"
    assert csv_directory.is_dir()
    assert opened_directories == [str(csv_directory), str(csv_directory)]


def test_frozen_runtime_uses_executable_directory_for_csv(
    qtbot,
    monkeypatch,
    tmp_path,
) -> None:
    executable_path = tmp_path.resolve() / "dist" / "measurement.exe"
    executable_path.parent.mkdir()
    monkeypatch.setattr(
        "app.ui.test_manager_panel.sys.frozen",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        "app.ui.test_manager_panel.sys.executable",
        str(executable_path),
    )
    panel = ManagerPanel()
    qtbot.addWidget(panel)
    opened_directories: list[str] = []

    def fake_get_save_file_name(parent, caption, directory, selected_filter):
        opened_directories.append(directory)
        return "", selected_filter

    monkeypatch.setattr(QFileDialog, "getSaveFileName", fake_get_save_file_name)

    panel.findChild(QPushButton, "saveItemButton").click()

    csv_directory = executable_path.parent / "CSV"
    assert csv_directory.is_dir()
    assert opened_directories == [str(csv_directory)]


def test_csv_dialog_always_returns_to_fixed_directory(
    qtbot,
    monkeypatch,
    tmp_path,
) -> None:
    runtime_directory = tmp_path.resolve()
    monkeypatch.chdir(runtime_directory)
    outside_directory = runtime_directory / "outside"
    outside_directory.mkdir()
    selected_path = outside_directory / "cases.csv"
    panel = ManagerPanel()
    qtbot.addWidget(panel)
    monkeypatch.setattr("app.ui.test_manager_panel.load_csv", lambda path: [])
    opened_directories: list[str] = []

    def fake_get_open_file_name(parent, caption, directory, selected_filter):
        opened_directories.append(directory)
        return str(selected_path), "CSV Files (*.csv)"

    def fake_get_save_file_name(parent, caption, directory, selected_filter):
        opened_directories.append(directory)
        return "", selected_filter

    monkeypatch.setattr(QFileDialog, "getOpenFileName", fake_get_open_file_name)
    monkeypatch.setattr(QFileDialog, "getSaveFileName", fake_get_save_file_name)

    panel.findChild(QPushButton, "loadItemButton").click()
    panel.findChild(QPushButton, "saveItemButton").click()

    fixed_directory = str(runtime_directory / "CSV")
    assert opened_directories == [fixed_directory, fixed_directory]


def test_deleted_csv_directory_is_recreated_before_next_dialog(
    qtbot,
    monkeypatch,
    tmp_path,
) -> None:
    runtime_directory = tmp_path.resolve()
    monkeypatch.chdir(runtime_directory)
    panel = ManagerPanel()
    qtbot.addWidget(panel)
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        lambda parent, caption, directory, selected_filter: ("", selected_filter),
    )
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        lambda parent, caption, directory, selected_filter: ("", selected_filter),
    )

    panel.findChild(QPushButton, "loadItemButton").click()
    csv_directory = runtime_directory / "CSV"
    csv_directory.rmdir()

    panel.findChild(QPushButton, "saveItemButton").click()

    assert csv_directory.is_dir()


def test_csv_directory_creation_failure_warns_and_uses_parent(
    qtbot,
    monkeypatch,
    tmp_path,
) -> None:
    runtime_directory = tmp_path.resolve()
    monkeypatch.chdir(runtime_directory)
    (runtime_directory / "CSV").write_text(
        "not a directory",
        encoding="utf-8",
    )
    panel = ManagerPanel()
    qtbot.addWidget(panel)
    warnings: list[str] = []
    opened_directories: list[str] = []
    monkeypatch.setattr(panel, "_show_warning", warnings.append)

    def fake_get_open_file_name(parent, caption, directory, selected_filter):
        opened_directories.append(directory)
        return "", selected_filter

    monkeypatch.setattr(QFileDialog, "getOpenFileName", fake_get_open_file_name)

    panel.findChild(QPushButton, "loadItemButton").click()

    assert len(warnings) == 1
    assert "CSV 폴더를 생성하지 못했습니다." in warnings[0]
    assert opened_directories == [str(runtime_directory)]
