from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QFileDialog, QLineEdit, QPushButton

from app.config import file_dialog_directory_settings
from app.config.file_dialog_directory_settings import (
    FileDialogDirectorySettings,
    FileDialogDirectorySettingsStore,
    default_file_dialog_directory_settings_path,
)
from app.ui.test_manager_panel import TestManagerPanel as ManagerPanel


def test_excel_dialog_keeps_current_path_as_initial_location(
    qtbot,
    monkeypatch,
    tmp_path,
) -> None:
    current_path = tmp_path / "current.xlsx"
    current_path.touch()
    stored_directory = tmp_path / "stored"
    stored_directory.mkdir()
    store = FileDialogDirectorySettingsStore(tmp_path / "settings.json")
    store.save(
        FileDialogDirectorySettings(excel_directory=str(stored_directory)),
    )
    panel = ManagerPanel(file_dialog_settings_store=store)
    qtbot.addWidget(panel)
    panel.findChild(QLineEdit, "excelTemplatePathEdit").setText(str(current_path))

    def fake_get_open_file_name(parent, caption, directory, selected_filter):
        assert directory == str(current_path)
        return "", selected_filter

    monkeypatch.setattr(QFileDialog, "getOpenFileName", fake_get_open_file_name)

    panel.findChild(QPushButton, "excelTemplateBrowseButton").click()


def test_excel_dialog_does_not_follow_csv_dialog_directory(
    qtbot,
    monkeypatch,
    tmp_path,
) -> None:
    runtime_directory = tmp_path.resolve()
    monkeypatch.chdir(runtime_directory)
    store = FileDialogDirectorySettingsStore(runtime_directory / "settings.json")
    panel = ManagerPanel(file_dialog_settings_store=store)
    qtbot.addWidget(panel)
    opened_directories: list[tuple[str, str]] = []

    def fake_get_open_file_name(parent, caption, directory, selected_filter):
        opened_directories.append((caption, directory))
        return "", selected_filter

    monkeypatch.setattr(QFileDialog, "getOpenFileName", fake_get_open_file_name)

    panel.findChild(QPushButton, "loadItemButton").click()
    panel.findChild(QPushButton, "excelTemplateBrowseButton").click()

    assert opened_directories == [
        ("Test Case CSV 불러오기", str(runtime_directory / "CSV")),
        ("Excel 양식 선택", str(runtime_directory)),
    ]


def test_excel_directory_is_restored_by_new_panel(
    qtbot,
    monkeypatch,
    tmp_path,
) -> None:
    excel_directory = tmp_path / "excel"
    excel_directory.mkdir()
    selected_path = excel_directory / "template.xlsx"
    selected_path.touch()
    store = FileDialogDirectorySettingsStore(tmp_path / "settings.json")
    first_panel = ManagerPanel(file_dialog_settings_store=store)
    qtbot.addWidget(first_panel)
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        lambda parent, caption, directory, selected_filter: (
            str(selected_path),
            selected_filter,
        ),
    )

    first_panel.findChild(QPushButton, "excelTemplateBrowseButton").click()

    second_panel = ManagerPanel(file_dialog_settings_store=store)
    qtbot.addWidget(second_panel)
    opened_directories: list[str] = []

    def fake_get_open_file_name(parent, caption, directory, selected_filter):
        opened_directories.append(directory)
        return "", selected_filter

    monkeypatch.setattr(QFileDialog, "getOpenFileName", fake_get_open_file_name)
    second_panel.findChild(QPushButton, "excelTemplateBrowseButton").click()

    assert opened_directories == [str(excel_directory.resolve())]
    assert store.load() == FileDialogDirectorySettings(
        excel_directory=str(excel_directory.resolve()),
    )


def test_cancelled_excel_dialog_does_not_change_stored_directory(
    qtbot,
    monkeypatch,
    tmp_path,
) -> None:
    excel_directory = tmp_path / "excel"
    excel_directory.mkdir()
    store = FileDialogDirectorySettingsStore(tmp_path / "settings.json")
    expected_settings = FileDialogDirectorySettings(
        excel_directory=str(excel_directory),
    )
    store.save(expected_settings)
    panel = ManagerPanel(file_dialog_settings_store=store)
    qtbot.addWidget(panel)
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        lambda parent, caption, directory, selected_filter: ("", selected_filter),
    )

    panel.findChild(QPushButton, "excelTemplateBrowseButton").click()

    assert store.load() == expected_settings


@pytest.mark.parametrize("settings_contents", [None, "{broken", "[]"])
def test_missing_or_corrupt_excel_settings_fall_back_to_runtime_directory(
    qtbot,
    monkeypatch,
    tmp_path,
    settings_contents,
) -> None:
    runtime_directory = tmp_path.resolve()
    monkeypatch.chdir(runtime_directory)
    settings_path = runtime_directory / "settings.json"
    if settings_contents is not None:
        settings_path.write_text(settings_contents, encoding="utf-8")
    panel = ManagerPanel(
        file_dialog_settings_store=FileDialogDirectorySettingsStore(settings_path),
    )
    qtbot.addWidget(panel)
    opened_directories: list[str] = []

    def fake_get_open_file_name(parent, caption, directory, selected_filter):
        opened_directories.append(directory)
        return "", selected_filter

    monkeypatch.setattr(QFileDialog, "getOpenFileName", fake_get_open_file_name)
    panel.findChild(QPushButton, "excelTemplateBrowseButton").click()

    assert opened_directories == [str(runtime_directory)]


def test_deleted_excel_directory_falls_back_to_runtime_directory(
    qtbot,
    monkeypatch,
    tmp_path,
) -> None:
    runtime_directory = tmp_path.resolve()
    monkeypatch.chdir(runtime_directory)
    store = FileDialogDirectorySettingsStore(runtime_directory / "settings.json")
    store.save(
        FileDialogDirectorySettings(
            excel_directory=str(runtime_directory / "deleted"),
        ),
    )
    panel = ManagerPanel(file_dialog_settings_store=store)
    qtbot.addWidget(panel)
    opened_directories: list[str] = []

    def fake_get_open_file_name(parent, caption, directory, selected_filter):
        opened_directories.append(directory)
        return "", selected_filter

    monkeypatch.setattr(QFileDialog, "getOpenFileName", fake_get_open_file_name)
    panel.findChild(QPushButton, "excelTemplateBrowseButton").click()

    assert opened_directories == [str(runtime_directory)]


def test_excel_selection_does_not_change_fixed_csv_directory(
    qtbot,
    monkeypatch,
    tmp_path,
) -> None:
    runtime_directory = tmp_path.resolve()
    monkeypatch.chdir(runtime_directory)
    excel_directory = runtime_directory / "excel"
    excel_directory.mkdir()
    selected_path = excel_directory / "template.xlsx"
    selected_path.touch()
    panel = ManagerPanel(
        file_dialog_settings_store=FileDialogDirectorySettingsStore(
            runtime_directory / "settings.json",
        ),
    )
    qtbot.addWidget(panel)
    opened_directories: list[str] = []

    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        lambda parent, caption, directory, selected_filter: (
            str(selected_path),
            selected_filter,
        ),
    )

    def fake_get_save_file_name(parent, caption, directory, selected_filter):
        opened_directories.append(directory)
        return "", selected_filter

    monkeypatch.setattr(QFileDialog, "getSaveFileName", fake_get_save_file_name)

    panel.findChild(QPushButton, "excelTemplateBrowseButton").click()
    panel.findChild(QPushButton, "saveItemButton").click()

    assert opened_directories == [str(runtime_directory / "CSV")]


def test_source_runtime_uses_runtime_config_directory(
    monkeypatch,
    tmp_path,
) -> None:
    runtime_directory = tmp_path.resolve()
    monkeypatch.chdir(runtime_directory)
    monkeypatch.delattr(
        file_dialog_directory_settings.sys,
        "frozen",
        raising=False,
    )

    assert default_file_dialog_directory_settings_path() == (
        runtime_directory / "config" / "file_dialog_directories.json"
    )


def test_frozen_runtime_uses_executable_config_directory(
    monkeypatch,
    tmp_path,
) -> None:
    executable_path = tmp_path.resolve() / "dist" / "measurement.exe"
    executable_path.parent.mkdir()
    monkeypatch.setattr(
        file_dialog_directory_settings.sys,
        "frozen",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        file_dialog_directory_settings.sys,
        "executable",
        str(executable_path),
    )

    assert default_file_dialog_directory_settings_path() == (
        executable_path.parent / "config" / "file_dialog_directories.json"
    )


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
        file_dialog_directory_settings.sys,
        "frozen",
        True,
        raising=False,
    )
    monkeypatch.setattr(
        file_dialog_directory_settings.sys,
        "executable",
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
