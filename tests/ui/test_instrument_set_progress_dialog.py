from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QLabel, QPushButton

from app.ui.instrument_set_progress_dialog import (
    InstrumentSetProgressDialog,
    format_elapsed_time,
)


def test_format_elapsed_time_uses_hh_mm_ss() -> None:
    assert format_elapsed_time(0) == "00:00:00"
    assert format_elapsed_time(201) == "00:03:21"
    assert format_elapsed_time(3661) == "01:01:01"


def test_instrument_set_progress_dialog_is_modeless_and_has_no_cancel(qtbot) -> None:
    dialog = InstrumentSetProgressDialog(initial_step="CO3000 Set Reference 진행 중")
    qtbot.addWidget(dialog)

    dialog.start()

    assert dialog.isVisible()
    assert dialog.property("progressDialog") is True
    assert not dialog.isModal()
    step_label = dialog.findChild(QLabel, "instrumentSetProgressStepLabel")
    elapsed_label = dialog.findChild(QLabel, "instrumentSetProgressElapsedLabel")
    assert step_label is not None
    assert elapsed_label is not None
    assert step_label.text() == "CO3000 Set Reference 진행 중"
    assert elapsed_label.text() == "00:00:00"
    assert not any(
        button.text().replace("&", "").lower() == "cancel"
        for button in dialog.findChildren(QPushButton)
    )


def test_instrument_set_progress_dialog_ignores_close_and_escape(qtbot) -> None:
    dialog = InstrumentSetProgressDialog()
    qtbot.addWidget(dialog)
    dialog.start()

    dialog.close()
    qtbot.wait(0)
    assert dialog.isVisible()

    dialog.reject()
    qtbot.wait(0)
    assert dialog.isVisible()

    qtbot.keyClick(dialog, Qt.Key.Key_Escape)
    qtbot.wait(0)
    assert dialog.isVisible()

    dialog.close_without_action()
    qtbot.wait(0)
    assert not dialog.isVisible()


def test_instrument_set_progress_dialog_updates_step_and_elapsed(qtbot) -> None:
    dialog = InstrumentSetProgressDialog()
    qtbot.addWidget(dialog)
    dialog.start()

    dialog.set_step("FSV40 Self Alignment 진행 중")
    dialog._started_monotonic -= 65
    timer = dialog.findChild(QTimer, "instrumentSetProgressElapsedTimer")
    assert timer is not None
    timer.timeout.emit()

    step_label = dialog.findChild(QLabel, "instrumentSetProgressStepLabel")
    elapsed_label = dialog.findChild(QLabel, "instrumentSetProgressElapsedLabel")
    assert step_label is not None
    assert elapsed_label is not None
    assert step_label.text() == "FSV40 Self Alignment 진행 중"
    assert elapsed_label.text() == "00:01:05"


def test_progress_dialog_style_survives_object_name_change(qtbot) -> None:
    dialog = InstrumentSetProgressDialog()
    qtbot.addWidget(dialog)

    dialog.setObjectName("tdfProgressDialog")

    assert dialog.property("progressDialog") is True
    assert 'QDialog[progressDialog="true"]' in dialog.styleSheet()
