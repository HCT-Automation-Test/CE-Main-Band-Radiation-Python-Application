"""RF Switch Box 수동 제어 패널."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QRectF, QSize, Qt, Signal, Slot
from PySide6.QtGui import QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.models.enums import FilterPath, InputPath
from app.net import commands as default_commands

logger = logging.getLogger(__name__)

_BACKGROUND_PATH = (
    Path(__file__).resolve().parents[3] / "resources" / "images" / "rf_switch_box_bd.png"
)
_CANVAS_WIDTH = 1098
_CANVAS_HEIGHT = 747
_BUTTON_WIDTH = 80
_BUTTON_HEIGHT = 20
_OUTPUT_WIDTH = 80
_OUTPUT_HEIGHT = 21

_INPUT_BUTTONS: tuple[tuple[str, InputPath, tuple[int, int]], ...] = (
    ("Bilog", InputPath.INPUT1, (50, 369)),
    ("3M HORN", InputPath.INPUT2, (50, 394)),
    ("1M HORN", InputPath.INPUT3, (50, 419)),
)

_FILTER_BUTTONS: tuple[tuple[str, FilterPath, tuple[int, int]], ...] = (
    ("Thru", FilterPath.THRU, (509, 20)),
    ("Direct-amp", FilterPath.DIRECT_AMP, (509, 94)),
    ("1 GHz HPF", FilterPath.HPF_1G, (509, 119)),
    ("3 GHz HPF", FilterPath.HPF_3G, (509, 144)),
    ("7 GHz HPF", FilterPath.HPF_7G, (509, 169)),
    ("6 GHz HPF", FilterPath.HPF_6G, (509, 194)),
    ("BAND 1", FilterPath.PORT_1, (509, 219)),
    ("BAND 3", FilterPath.PORT_2, (509, 244)),
    ("BAND 5", FilterPath.PORT_3, (509, 269)),
    ("BAND 7", FilterPath.PORT_4, (509, 294)),
    ("BAND 8", FilterPath.PORT_5, (509, 319)),
    ("BAND 20", FilterPath.PORT_6, (509, 344)),
    ("BAND 26", FilterPath.PORT_7, (509, 444)),
    ("BAND 28", FilterPath.PORT_8, (509, 469)),
    ("BAND 38", FilterPath.PORT_9, (509, 494)),
    ("BAND 40", FilterPath.PORT_10, (509, 519)),
    ("BAND 41", FilterPath.PORT_11, (509, 544)),
    ("BAND 71", FilterPath.PORT_12, (509, 569)),
    ("BAND 77", FilterPath.PORT_13, (509, 594)),
    ("BAND 78", FilterPath.PORT_14, (509, 619)),
    ("BAND 79", FilterPath.PORT_15, (509, 644)),
    ("GSM900", FilterPath.PORT_16, (509, 669)),
    ("DCS1800", FilterPath.PORT_17, (509, 694)),
    ("Port 18", FilterPath.PORT_18, (509, 719)),
)

_INPUT_LABELS = {input_path: label for label, input_path, _pos in _INPUT_BUTTONS}
_FILTER_LABELS = {filter_path: label for label, filter_path, _pos in _FILTER_BUTTONS}
_INPUT_BY_INFO_LABEL = {
    "bilog": InputPath.INPUT1,
    "input1": InputPath.INPUT1,
    "input 1": InputPath.INPUT1,
    "3m": InputPath.INPUT2,
    "3m horn": InputPath.INPUT2,
    "input2": InputPath.INPUT2,
    "input 2": InputPath.INPUT2,
    "1m": InputPath.INPUT3,
    "1m horn": InputPath.INPUT3,
    "input3": InputPath.INPUT3,
    "input 3": InputPath.INPUT3,
}
_FILTER_BY_INFO_LABEL = {
    "thru": FilterPath.THRU,
    "direct amp": FilterPath.DIRECT_AMP,
    "direct-amp": FilterPath.DIRECT_AMP,
    "1g hpf": FilterPath.HPF_1G,
    "1 ghz hpf": FilterPath.HPF_1G,
    "3g hpf": FilterPath.HPF_3G,
    "3 ghz hpf": FilterPath.HPF_3G,
    "7g hpf": FilterPath.HPF_7G,
    "7 ghz hpf": FilterPath.HPF_7G,
    "6g hpf": FilterPath.HPF_6G,
    "6 ghz hpf": FilterPath.HPF_6G,
}
for _index in range(1, 19):
    _FILTER_BY_INFO_LABEL[f"port {_index}"] = FilterPath[f"PORT_{_index}"]


def _style_button(button: QPushButton) -> None:
    button.setCheckable(True)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setStyleSheet(
        """
        QPushButton {
            background: #f7f7f7;
            border: 1px solid #808080;
            color: #111111;
            font-size: 11px;
            padding: 0;
        }
        QPushButton:checked {
            background: #d71920;
            border: 1px solid #8f0f14;
            color: #ffffff;
        }
        QPushButton:disabled {
            background: #eeeeee;
            color: #888888;
        }
        """
    )


def _display_input(input_path: InputPath | None) -> str:
    if input_path is None:
        return "Unknown"
    return _INPUT_LABELS[input_path]


def _display_filter(filter_path: FilterPath | None) -> str:
    if filter_path is None:
        return "Unknown"
    return _FILTER_LABELS[filter_path]


def _value_code(input_path: InputPath, filter_path: FilterPath) -> int:
    return int(input_path) * 100 + int(filter_path)


def _point_on_button(center: tuple[int, int]) -> tuple[int, int]:
    return (center[0] - _BUTTON_WIDTH // 2, center[1] - _BUTTON_HEIGHT // 2)


class RFSwitchBoxService(QObject):
    """RF Switch Box 수동 조작을 즉시 실행한다."""

    operation_started = Signal()
    switch_box_set = Signal(object, object)
    switch_filter_set = Signal(object)
    operation_failed = Signal(str)
    operation_finished = Signal(str)

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        client: Any,
        commands: Any = default_commands,
    ) -> None:
        super().__init__(parent)
        self._client = client
        self._commands = commands
        self._running = False
        self._shutting_down = False

    @property
    def is_running(self) -> bool:
        return self._running

    def set_switch_box(self, input_path: InputPath, filter_path: FilterPath) -> None:
        if not self._begin_operation():
            return
        try:
            ok = self._commands.set_switch_box(
                self._client,
                input_path=input_path,
                filter_path=filter_path,
            )
            if ok:
                self.switch_box_set.emit(input_path, filter_path)
                self.operation_finished.emit("Switch Box 경로 설정 완료")
            else:
                self.operation_failed.emit("Switch Box SET returned false")
        except Exception as exc:
            logger.exception("Switch Box 수동 제어 실패")
            self.operation_failed.emit(str(exc))
        finally:
            self._finish_operation()

    def set_thru(self) -> None:
        if not self._begin_operation():
            return
        try:
            ok = self._commands.set_switch_filter(
                self._client,
                filter_path=FilterPath.THRU,
            )
            if ok:
                self.switch_filter_set.emit(FilterPath.THRU)
                self.operation_finished.emit("Switch Box THRU 설정 완료")
            else:
                self.operation_failed.emit("Switch Box Thru returned false")
        except Exception as exc:
            logger.exception("Switch Box 수동 제어 실패")
            self.operation_failed.emit(str(exc))
        finally:
            self._finish_operation()

    def shutdown(self) -> None:
        self._shutting_down = True

    def _begin_operation(self) -> bool:
        if self._shutting_down:
            return False
        if self._running:
            self.operation_failed.emit("Switch Box 작업이 이미 진행 중입니다.")
            return False
        self._running = True
        self.operation_started.emit()
        return True

    def _finish_operation(self) -> None:
        self._running = False


class _CircuitCanvas(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("rfSwitchBoxCanvas")
        self._background = QPixmap(str(_BACKGROUND_PATH))
        self._base_size = self._background.size()
        if self._background.isNull():
            self._base_size = QSize(_CANVAS_WIDTH, _CANVAS_HEIGHT)
        self._content_rect = QRectF(0, 0, self._base_size.width(), self._base_size.height())
        self.setMinimumSize(0, 0)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._current_input: InputPath | None = None
        self._current_filter: FilterPath | None = None
        self._input_group = QButtonGroup(self)
        self._input_group.setExclusive(True)
        self._filter_group = QButtonGroup(self)
        self._filter_group.setExclusive(True)
        self.input_selected: dict[QPushButton, InputPath] = {}
        self.filter_selected: dict[QPushButton, FilterPath] = {}
        self._button_centers: dict[QPushButton, tuple[int, int]] = {}
        self._create_buttons()
        output = QLabel("Output", self)
        output.setObjectName("rfSwitchOutputLabel")
        output.setAlignment(Qt.AlignmentFlag.AlignCenter)
        output.setFrameShape(QFrame.Shape.Box)
        self._output_label = output
        self._layout_overlay_widgets()

    def sizeHint(self) -> QSize:
        return self._base_size

    def resizeEvent(self, event: object) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._layout_overlay_widgets()

    def set_current_path(
        self,
        input_path: InputPath | None,
        filter_path: FilterPath | None,
    ) -> None:
        self._current_input = input_path
        self._current_filter = filter_path
        self.update()

    def set_selected_path(
        self,
        input_path: InputPath | None,
        filter_path: FilterPath | None,
    ) -> None:
        self._set_group_checked(self._input_group, input_path)
        self._set_group_checked(self._filter_group, filter_path)

    def _create_buttons(self) -> None:
        for label, input_path, center in _INPUT_BUTTONS:
            button = QPushButton(label, self)
            button.setObjectName(f"inputButton{int(input_path)}")
            _style_button(button)
            x, y = _point_on_button(center)
            button.setGeometry(x, y, _BUTTON_WIDTH, _BUTTON_HEIGHT)
            self._input_group.addButton(button, int(input_path))
            self.input_selected[button] = input_path
            self._button_centers[button] = center

        for label, filter_path, center in _FILTER_BUTTONS:
            button = QPushButton(label, self)
            button.setObjectName(f"filterButton{int(filter_path):02d}")
            _style_button(button)
            x, y = _point_on_button(center)
            button.setGeometry(x, y, _BUTTON_WIDTH, _BUTTON_HEIGHT)
            self._filter_group.addButton(button, int(filter_path))
            self.filter_selected[button] = filter_path
            self._button_centers[button] = center

    def _set_group_checked(
        self,
        group: QButtonGroup,
        value: InputPath | FilterPath | None,
    ) -> None:
        previous = group.exclusive()
        group.setExclusive(False)
        for button in group.buttons():
            button.setChecked(False)
        group.setExclusive(previous)
        if value is None:
            return
        button = group.button(int(value))
        if button is not None:
            button.setChecked(True)

    def paintEvent(self, event: object) -> None:  # noqa: N802
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self._content_rect = self._scaled_content_rect()
        if not self._background.isNull():
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            painter.drawPixmap(self._content_rect, self._background, self._background.rect())
        if self._current_input is not None and self._current_filter is not None:
            painter.save()
            painter.translate(self._content_rect.left(), self._content_rect.top())
            painter.scale(self._scale_factor(), self._scale_factor())
            self._draw_active_path(painter)
            painter.restore()
        painter.end()

    def _layout_overlay_widgets(self) -> None:
        self._content_rect = self._scaled_content_rect()
        for button, _input_path in self.input_selected.items():
            center = self._button_centers[button]
            self._set_scaled_geometry(button, center, _BUTTON_WIDTH, _BUTTON_HEIGHT)
        for button, _filter_path in self.filter_selected.items():
            center = self._button_centers[button]
            self._set_scaled_geometry(button, center, _BUTTON_WIDTH, _BUTTON_HEIGHT)
        self._set_scaled_geometry(
            self._output_label,
            (1008 + _OUTPUT_WIDTH // 2, 371 + _OUTPUT_HEIGHT // 2),
            _OUTPUT_WIDTH,
            _OUTPUT_HEIGHT,
        )

    def _set_scaled_geometry(
        self,
        widget: QWidget,
        center: tuple[int, int],
        width: int,
        height: int,
    ) -> None:
        scale = self._scale_factor()
        x = round(self._content_rect.left() + (center[0] - width / 2) * scale)
        y = round(self._content_rect.top() + (center[1] - height / 2) * scale)
        widget.setGeometry(
            x,
            y,
            max(1, round(width * scale)),
            max(1, round(height * scale)),
        )

    def _scaled_content_rect(self) -> QRectF:
        base_width = self._base_size.width()
        base_height = self._base_size.height()
        if base_width <= 0 or base_height <= 0:
            return QRectF(self.rect())
        scale = min(self.width() / base_width, self.height() / base_height)
        width = base_width * scale
        height = base_height * scale
        return QRectF(
            (self.width() - width) / 2,
            (self.height() - height) / 2,
            width,
            height,
        )

    def _scale_factor(self) -> float:
        if self._base_size.width() <= 0:
            return 1.0
        return self._content_rect.width() / self._base_size.width()

    def _draw_active_path(self, painter: QPainter) -> None:
        if self._current_input is None or self._current_filter is None:
            return

        code = _value_code(self._current_input, self._current_filter)
        first = (code // 100) * 100
        second = code % 100
        painter.setPen(QPen(Qt.GlobalColor.red, 2))

        def line(x1: int, y1: int, x2: int, y2: int) -> None:
            painter.drawLine(x1, y1, x2, y2)

        if first == 100:
            line(87, 369, 127, 369)
            line(127, 369, 192, 394)
        elif first == 200:
            line(87, 394, 127, 394)
            line(127, 394, 192, 394)
        elif first == 300:
            line(87, 419, 127, 419)
            line(127, 419, 192, 394)

        line(192, 394, 247, 394)

        if 2 <= second <= 12:
            y = 69 + (second - 1) * 25
            line(247, 394, 312, 381)
            line(312, 381, 339, 381)
            line(339, 381, 339, 206)
            line(339, 206, 366, 206)
            line(366, 206, 431, y)
            line(431, y, 471, y)
            line(546, y, 586, y)
            line(586, y, 651, 206)
            line(651, 206, 678, 206)
            line(678, 206, 678, 381)
            line(678, 381, 705, 381)
            line(705, 381, 770, 394)
        elif 13 <= second <= 24:
            y = 444 + (second - 13) * 25
            line(247, 394, 312, 406)
            line(312, 406, 339, 406)
            line(339, 406, 339, 581)
            line(339, 581, 366, 581)
            line(366, 581, 431, y)
            line(431, y, 471, y)
            line(546, y, 586, y)
            line(586, y, 651, 581)
            line(651, 581, 678, 581)
            line(678, 581, 678, 406)
            line(678, 406, 705, 406)
            line(705, 406, 770, 394)

        if second == 1:
            line(247, 394, 312, 381)
            line(312, 381, 339, 381)
            line(339, 381, 339, 206)
            line(339, 206, 366, 206)
            line(366, 206, 431, 69)
            line(431, 69, 459, 69)
            line(459, 69, 459, 19)
            line(459, 20, 469, 20)
            line(549, 20, 879, 20)
            line(879, 20, 879, 369)
            line(879, 369, 905, 369)
            line(905, 369, 970, 381)
        else:
            line(770, 394, 808, 394)
            line(868, 394, 905, 394)
            line(905, 394, 970, 381)
        line(970, 381, 1010, 381)


class RFFilterBoxPanel(QWidget):
    """RF Switch Box 수동 제어 화면."""

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        service: RFSwitchBoxService | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("rfFilterBoxPanel")
        self._service = service
        self._selected_input: InputPath | None = None
        self._selected_filter: FilterPath | None = None
        self._current_input: InputPath | None = None
        self._current_filter: FilterPath | None = None
        self._switch_box_connected = False
        self._operation_locked = False
        self._service_running = False
        self._build_ui()
        self._connect_canvas_buttons()
        self._connect_service()
        self._update_status()
        self._update_button_state()

    def shutdown(self) -> None:
        if self._service is not None:
            shutdown = getattr(self._service, "shutdown", None)
            if callable(shutdown):
                shutdown()

    def set_connection_state(self, states: dict[str, bool]) -> None:
        self._switch_box_connected = states.get("Switch Box") is True
        self._update_button_state()

    def set_operation_locked(self, locked: bool) -> None:
        self._operation_locked = locked
        self._update_button_state()

    def set_switch_box_info(self, info: object) -> None:
        input_path, filter_path = self._parse_switch_box_info(info)
        if input_path is not None:
            self._current_input = input_path
            self._selected_input = input_path
        if filter_path is not None:
            self._current_filter = filter_path
            self._selected_filter = filter_path
        self._canvas.set_current_path(self._current_input, self._current_filter)
        self._canvas.set_selected_path(self._selected_input, self._selected_filter)
        self._update_status()
        self._set_message("FSM 상태 반영 완료")

    def clear_switch_box_info(self) -> None:
        self._current_input = None
        self._current_filter = None
        self._selected_input = None
        self._selected_filter = None
        self._canvas.set_current_path(None, None)
        self._canvas.set_selected_path(None, None)
        self._update_status()
        self._update_button_state()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(10)

        header = QWidget(self)
        header.setObjectName("rfSwitchHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        self._current_input_label = QLabel("Input: Unknown", header)
        self._current_input_label.setObjectName("currentInputLabel")
        self._current_filter_label = QLabel("Filter: Unknown", header)
        self._current_filter_label.setObjectName("currentFilterLabel")
        self._status_label = QLabel("Switch Box not connected", header)
        self._status_label.setObjectName("operationStatusLabel")
        self._status_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )

        self._set_button = QPushButton("SET", header)
        self._set_button.setObjectName("setSwitchBoxButton")
        self._set_button.setFixedHeight(34)
        self._set_button.clicked.connect(self._on_set_clicked)
        self._thru_button = QPushButton("Thru!", header)
        self._thru_button.setObjectName("thruSwitchBoxButton")
        self._thru_button.setFixedHeight(34)
        self._thru_button.clicked.connect(self._on_thru_clicked)

        header_layout.addWidget(self._current_input_label)
        header_layout.addWidget(self._current_filter_label)
        header_layout.addWidget(self._status_label, 1)
        header_layout.addWidget(self._set_button)
        header_layout.addWidget(self._thru_button)
        root_layout.addWidget(header)

        scroll_area = QScrollArea(self)
        scroll_area.setObjectName("rfSwitchScrollArea")
        scroll_area.setWidgetResizable(True)
        scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._canvas = _CircuitCanvas(scroll_area)
        scroll_area.setWidget(self._canvas)
        root_layout.addWidget(scroll_area, 1)

    def _connect_canvas_buttons(self) -> None:
        for button, input_path in self._canvas.input_selected.items():
            button.clicked.connect(
                lambda _checked=False, value=input_path: self._select_input(value)
            )
        for button, filter_path in self._canvas.filter_selected.items():
            button.clicked.connect(
                lambda _checked=False, value=filter_path: self._select_filter(value)
            )

    def _connect_service(self) -> None:
        if self._service is None:
            return
        self._service.operation_started.connect(self._on_operation_started)
        self._service.switch_box_set.connect(self._on_switch_box_set)
        self._service.switch_filter_set.connect(self._on_switch_filter_set)
        self._service.operation_finished.connect(self._on_operation_finished)
        self._service.operation_failed.connect(self._on_operation_failed)

    def _select_input(self, input_path: InputPath) -> None:
        self._selected_input = input_path
        self._canvas.set_selected_path(self._selected_input, self._selected_filter)
        self._update_button_state()
        self._set_message(f"Selected Input: {_display_input(input_path)}")

    def _select_filter(self, filter_path: FilterPath) -> None:
        self._selected_filter = filter_path
        self._canvas.set_selected_path(self._selected_input, self._selected_filter)
        self._update_button_state()
        self._set_message(f"Selected Filter: {_display_filter(filter_path)}")

    def _on_set_clicked(self) -> None:
        if self._service is None:
            self._set_message("Switch Box service is not configured")
            return
        if self._selected_input is None or self._selected_filter is None:
            self._set_message("Input과 Filter를 선택하세요.")
            return
        self._service.set_switch_box(self._selected_input, self._selected_filter)

    def _on_thru_clicked(self) -> None:
        if self._service is None:
            self._set_message("Switch Box service is not configured")
            return
        self._selected_filter = FilterPath.THRU
        self._canvas.set_selected_path(self._selected_input, self._selected_filter)
        self._service.set_thru()

    @Slot()
    def _on_operation_started(self) -> None:
        self._service_running = True
        self._set_message("Switch Box command running...")
        self._update_button_state()

    @Slot(object, object)
    def _on_switch_box_set(
        self,
        input_path: InputPath,
        filter_path: FilterPath,
    ) -> None:
        self._current_input = input_path
        self._current_filter = filter_path
        self._selected_input = input_path
        self._selected_filter = filter_path
        self._canvas.set_current_path(self._current_input, self._current_filter)
        self._canvas.set_selected_path(self._selected_input, self._selected_filter)
        self._update_status()

    @Slot(object)
    def _on_switch_filter_set(self, filter_path: FilterPath) -> None:
        self._current_filter = filter_path
        self._selected_filter = filter_path
        self._canvas.set_current_path(self._current_input, self._current_filter)
        self._canvas.set_selected_path(self._selected_input, self._selected_filter)
        self._update_status()

    @Slot(str)
    def _on_operation_finished(self, message: str) -> None:
        self._service_running = False
        self._set_message(message)
        self._update_button_state()

    @Slot(str)
    def _on_operation_failed(self, message: str) -> None:
        self._service_running = False
        self._set_message(f"Switch Box command failed: {message}")
        self._canvas.set_selected_path(self._selected_input, self._selected_filter)
        self._update_button_state()

    def _update_status(self) -> None:
        self._current_input_label.setText(f"Input: {_display_input(self._current_input)}")
        self._current_filter_label.setText(
            f"Filter: {_display_filter(self._current_filter)}"
        )

    def _set_message(self, message: str) -> None:
        self._status_label.setText(message)

    def _update_button_state(self) -> None:
        enabled = (
            self._switch_box_connected
            and not self._operation_locked
            and not self._service_running
        )
        for button in self._canvas.findChildren(QPushButton):
            button.setEnabled(enabled)
        self._thru_button.setEnabled(enabled)
        self._set_button.setEnabled(
            enabled
            and self._selected_input is not None
            and self._selected_filter is not None
        )
        if not self._switch_box_connected:
            self._set_message("Switch Box not connected")
        elif self._operation_locked:
            self._set_message("Instrument operation is locked")

    def _parse_switch_box_info(
        self,
        info: object,
    ) -> tuple[InputPath | None, FilterPath | None]:
        input_value = self._read_info_value(info, ("mast", "input", "input_path"))
        filter_value = self._read_info_value(
            info,
            ("filter", "filter_path", "filter_mode"),
        )
        return self._parse_input(input_value), self._parse_filter(filter_value)

    def _read_info_value(self, info: object, keys: tuple[str, ...]) -> object | None:
        for key in keys:
            if isinstance(info, dict) and key in info:
                return info[key]
            if hasattr(info, key):
                return getattr(info, key)
        return None

    def _parse_input(self, value: object | None) -> InputPath | None:
        if isinstance(value, InputPath):
            return value
        if isinstance(value, int):
            try:
                return InputPath(value)
            except ValueError:
                return None
        if not isinstance(value, str):
            return None
        return _INPUT_BY_INFO_LABEL.get(value.strip().lower())

    def _parse_filter(self, value: object | None) -> FilterPath | None:
        if isinstance(value, FilterPath):
            return value
        if isinstance(value, int):
            try:
                return FilterPath(value)
            except ValueError:
                return None
        if not isinstance(value, str):
            return None
        return _FILTER_BY_INFO_LABEL.get(value.strip().lower())
