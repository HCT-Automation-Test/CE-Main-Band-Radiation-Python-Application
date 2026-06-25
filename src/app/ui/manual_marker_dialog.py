"""수동 마커 편집 dialog."""
from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QCloseEvent, QDoubleValidator, QKeyEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QGridLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QLineEdit,
)

_MAX_NEXT_PEAK_SEARCH_LEVEL_DB = 80.0


class ManualMarkerDialog(QDialog):
    """측정 중 FSV40 marker command를 반복 실행하는 modeless dialog."""

    peak_requested = Signal(int, float)
    next_peak_requested = Signal(int, float)
    marker_off_requested = Signal(int, float)
    all_marker_off_requested = Signal()
    completed = Signal()
    stop_requested = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        next_peak_search_level_db: float = 6.0,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("manualMarkerDialog")
        self.setWindowTitle("Manual Marker Edit")
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        self._allow_close = False
        self._setup_layout(next_peak_search_level_db)

    def close_without_action(self) -> None:
        """외부 정리 목적의 닫기를 허용한다."""

        self._allow_close = True
        super().reject()

    def reject(self) -> None:
        return

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        if self._allow_close:
            super().closeEvent(event)
            return
        event.ignore()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            event.ignore()
            return
        super().keyPressEvent(event)

    def _setup_layout(self, next_peak_search_level_db: float) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(14)

        title = QLabel("Marker 편집 후 확인 버튼 클릭", self)
        title.setObjectName("manualMarkerTitleLabel")
        title.setProperty("titleLabel", True)
        layout.addWidget(title)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(8)

        self._marker_combo = QComboBox(self)
        self._marker_combo.setObjectName("targetMarkerComboBox")
        for index in range(1, 11):
            self._marker_combo.addItem(f"Marker {index}", index)
        form.addRow("Target Marker", self._marker_combo)

        self._excursion_edit = QLineEdit(self)
        self._excursion_edit.setObjectName("nextPeakSearchLevelEdit")
        validator = QDoubleValidator(0.0, _MAX_NEXT_PEAK_SEARCH_LEVEL_DB, 3, self)
        validator.setNotation(QDoubleValidator.Notation.StandardNotation)
        self._excursion_edit.setValidator(validator)
        self._excursion_edit.setText(f"{float(next_peak_search_level_db):g}")
        form.addRow("Next Peak Search Level", self._excursion_edit)
        layout.addLayout(form)

        command_grid = QGridLayout()
        command_grid.setHorizontalSpacing(10)
        command_grid.setVerticalSpacing(10)

        peak_button = QPushButton("Peak", self)
        peak_button.setObjectName("markerPeakButton")
        peak_button.clicked.connect(lambda _checked=False: self._emit_marker_command(self.peak_requested))
        command_grid.addWidget(peak_button, 0, 0)

        next_button = QPushButton("Next Peak", self)
        next_button.setObjectName("markerNextPeakButton")
        next_button.clicked.connect(lambda _checked=False: self._emit_marker_command(self.next_peak_requested))
        command_grid.addWidget(next_button, 0, 1)

        off_button = QPushButton("OFF", self)
        off_button.setObjectName("markerOffButton")
        off_button.clicked.connect(lambda _checked=False: self._emit_marker_command(self.marker_off_requested))
        command_grid.addWidget(off_button, 0, 2)

        all_off_button = QPushButton("ALL Marker OFF", self)
        all_off_button.setObjectName("markerAllOffButton")
        all_off_button.clicked.connect(self.all_marker_off_requested.emit)
        command_grid.addWidget(all_off_button, 1, 0)

        stop_button = QPushButton("중단", self)
        stop_button.setObjectName("manualMarkerStopButton")
        stop_button.clicked.connect(self._on_stop_clicked)
        command_grid.addWidget(stop_button, 1, 1)

        complete_button = QPushButton("확인 (종료 후 스크린샷)", self)
        complete_button.setObjectName("manualMarkerCompleteButton")
        complete_button.clicked.connect(self._on_complete_clicked)
        command_grid.addWidget(complete_button, 1, 2)
        layout.addLayout(command_grid)

        self.setMinimumWidth(520)

    def _emit_marker_command(self, signal: Signal) -> None:
        excursion = self._excursion_value()
        if excursion is None:
            return
        signal.emit(self._marker_index(), excursion)

    def _marker_index(self) -> int:
        return int(self._marker_combo.currentData())

    def _excursion_value(self) -> float | None:
        text = self._excursion_edit.text().strip()
        try:
            value = float(text)
        except ValueError:
            self._show_invalid_excursion_message()
            return None
        if not 0.0 <= value <= _MAX_NEXT_PEAK_SEARCH_LEVEL_DB:
            self._show_invalid_excursion_message()
            return None
        return value

    def _show_invalid_excursion_message(self) -> None:
        QMessageBox.warning(
            self,
            "Manual Marker",
            f"Next Peak Search Level은 0 이상 {_MAX_NEXT_PEAK_SEARCH_LEVEL_DB:g} 이하의 실수여야 합니다.",
        )

    def _on_complete_clicked(self) -> None:
        self._allow_close = True
        self.completed.emit()
        self.accept()

    def _on_stop_clicked(self) -> None:
        self._allow_close = True
        self.stop_requested.emit()
        self.accept()
