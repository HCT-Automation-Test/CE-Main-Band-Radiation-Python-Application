"""MainWindow — 앱 메인 윈도우."""
from __future__ import annotations

import logging
import sys
import ctypes

from PySide6.QtCore import QEvent, QSize, Qt
from PySide6.QtGui import QCloseEvent, QShowEvent
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

# 먼저 `uv run pyside6-uic resources/main_window.ui -o src/app/ui/generated/main_window_ui.py`
# 실행해야 아래 임포트가 성공한다.
from app.core.runner import (
    INSTRUMENT_CONNECTION_BLOCK_MESSAGE,
    INSTRUMENT_SET_BLOCK_MESSAGE,
    Runner,
)
from app.core.tdf_service import TDF_OPERATION_IN_PROGRESS_MESSAGE, TdfService
from app.models.test_case import TestCase
from app.ui.generated.main_window_ui import Ui_MainWindow
from app.ui.instrument_check_panel import InstrumentCheckPanel
from app.ui.instrument_set_progress_dialog import InstrumentSetProgressDialog
from app.ui.manual_test_panel import ManualTestPanel
from app.ui.rf_filter_box_panel import RFFilterBoxPanel, RFSwitchBoxService
from app.ui.test_manager_panel import TestManagerPanel
from app.ui.test_plot_screenshot_panel import TestPlotScreenshotPanel

logger = logging.getLogger(__name__)

_DEFAULT_WINDOW_SIZE = QSize(1760, 940)
_UNBOUNDED_WINDOW_SIZE = QSize(16777215, 16777215)
_FSV40_NOT_CONNECTED_MESSAGE = "FSV40 연결을 먼저 완료하세요."
_GWL_STYLE = -16
_WS_THICKFRAME = 0x00040000
_WS_MAXIMIZEBOX = 0x00010000
_SWP_NOSIZE = 0x0001
_SWP_NOMOVE = 0x0002
_SWP_NOZORDER = 0x0004
_SWP_FRAMECHANGED = 0x0020


class _UserActionDialog(QDialog):
    """수동 조작 팝업이 Esc/reject로 사라지지 않도록 제한한다."""

    def reject(self) -> None:
        return

    def close_without_action(self) -> None:
        super().reject()


class MainWindow(QMainWindow):
    """최상위 메인 윈도우. 생성된 Ui_MainWindow를 컴포지션으로 보유."""

    def __init__(self, parent: QMainWindow | None = None) -> None:
        super().__init__(parent)
        self._ui = Ui_MainWindow()
        self._ui.setupUi(self)
        self._runner = Runner(self)
        self._instrument_set_active = False
        self._tdf_operation_active = False
        self._pending_tdf_operation: str | None = None
        self._pending_tdf_file_name: str | None = None
        self._tdf_progress_dialog: InstrumentSetProgressDialog | None = None
        self._tdf_service = TdfService(
            self,
            client=self._runner.client,
            commands=self._runner.commands,
        )
        self._rf_switch_box_service = RFSwitchBoxService(
            self,
            client=self._runner.client,
            commands=self._runner.commands,
        )
        self.setWindowFlag(Qt.WindowType.WindowMaximizeButtonHint, True)
        self._lock_default_window_size()
        self._setup_main_layout()
        self._connect_signals()

    def _connect_signals(self) -> None:
        """시그널/슬롯 연결 허브. TODO(spec): 도크/패널 결선."""
        self._navigation_button_group.idClicked.connect(
            self.on_navigation_button_clicked,
        )
        self._test_manager_panel.start_requested.connect(
            self.on_start_requested,
        )
        self._test_manager_panel.pause_requested.connect(
            self._runner.pause,
        )
        self._test_manager_panel.get_tdf_list_requested.connect(
            self.on_get_tdf_list_requested,
        )
        self._test_manager_panel.tdf_all_off_requested.connect(
            self.on_tdf_all_off_requested,
        )
        self._test_manager_panel.set_tdf_requested.connect(
            self.on_set_tdf_requested,
        )
        self._tdf_service.operation_started.connect(self.on_tdf_operation_started)
        self._tdf_service.tdf_list_received.connect(
            self._test_manager_panel.set_tdf_file_list,
        )
        self._tdf_service.operation_finished.connect(self.on_tdf_operation_finished)
        self._tdf_service.operation_failed.connect(self.on_tdf_operation_failed)
        self._runner.measurement_active_changed.connect(
            self.on_measurement_active_changed,
        )
        self._runner.events.current_case_changed.connect(
            self.on_current_case_changed,
        )
        self._runner.events.spectrum_analyzer_info_changed.connect(
            self._test_manager_panel.set_analyzer_info,
        )
        self._runner.events.switch_box_info_changed.connect(
            self._test_manager_panel.set_switch_box_info,
        )
        self._runner.events.switch_box_info_changed.connect(
            self._rf_filter_box_panel.set_switch_box_info,
        )
        self._runner.events.turntable_info_changed.connect(
            self._test_manager_panel.update_turntable_info,
        )
        self._runner.events.polarization_info_changed.connect(
            self._test_manager_panel.update_polarization_info,
        )
        self._runner.events.screenshot_saved.connect(
            self._test_plot_screenshot_panel.on_screenshot_saved,
        )
        self._runner.events.user_action_required.connect(
            self.on_user_action_required,
        )
        self._runner.events.session_finished.connect(
            self.on_session_finished,
        )
        self._runner.instrument_connection_service.connection_started.connect(
            self._test_manager_panel.set_connection_connecting,
        )
        self._runner.instrument_connection_service.connection_finished.connect(
            self._test_manager_panel.set_connection_state,
        )
        self._runner.instrument_connection_service.connection_finished.connect(
            self._rf_filter_box_panel.set_connection_state,
        )
        self._runner.instrument_connection_service.error_occurred.connect(
            self._test_manager_panel.set_connection_failed,
        )
        self._runner.instrument_connection_service.set_started.connect(
            self.on_instrument_set_started,
        )
        self._runner.instrument_connection_service.set_finished.connect(
            self.on_instrument_set_finished,
        )
        self._runner.instrument_connection_service.set_failed.connect(
            self.on_instrument_set_failed,
        )
        self._runner.instrument_connection_service.equipment_disconnected.connect(
            self.on_equipment_disconnected,
        )
        self.on_measurement_active_changed(self._runner.is_measurement_active)
        self._test_manager_panel.set_connection_state(self._runner.equipment_state)
        self._rf_filter_box_panel.set_connection_state(self._runner.equipment_state)

    def _setup_main_layout(self) -> None:
        """좌측 서브 윈도우 선택 버튼과 우측 화면 스택을 구성한다."""

        self._ui.titleLabel.hide()
        self._ui.centralLayout.setContentsMargins(10, 10, 10, 10)
        self._ui.centralLayout.setSpacing(0)

        main_container = QWidget(self)
        main_container.setObjectName("mainContent")
        main_layout = QHBoxLayout(main_container)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(14)

        navigation_panel = QWidget(main_container)
        navigation_panel.setObjectName("navigationPanel")
        navigation_panel.setFixedWidth(148)
        navigation_layout = QVBoxLayout(navigation_panel)
        navigation_layout.setContentsMargins(0, 0, 0, 0)
        navigation_layout.setSpacing(20)

        self._navigation_button_group = QButtonGroup(self)
        self._navigation_button_group.setExclusive(True)
        self._page_stack = QStackedWidget(main_container)
        self._page_stack.setObjectName("subWindowStack")
        self._page_stack.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self._instrument_check_panel = InstrumentCheckPanel(
            self._page_stack,
            service=self._runner.instrument_connection_service,
        )
        self._test_manager_panel = TestManagerPanel(self._page_stack)
        self._test_plot_screenshot_panel = TestPlotScreenshotPanel(self._page_stack)
        self._rf_filter_box_panel = RFFilterBoxPanel(
            self._page_stack,
            service=self._rf_switch_box_service,
        )

        self._add_navigation_page(
            navigation_layout,
            index=0,
            button_text="Instrument\nCheck",
            object_name="instrumentCheck",
            page_widget=self._instrument_check_panel,
        )
        self._add_navigation_page(
            navigation_layout,
            index=1,
            button_text="Manual\nTest",
            object_name="manualTest",
            page_widget=ManualTestPanel(self._page_stack),
        )
        self._add_navigation_page(
            navigation_layout,
            index=2,
            button_text="RF Filter\nBox",
            object_name="rfFilterBox",
            page_widget=self._rf_filter_box_panel,
        )
        self._add_navigation_page(
            navigation_layout,
            index=3,
            button_text="Test\nManager",
            object_name="testManager",
            page_widget=self._test_manager_panel,
        )
        self._add_navigation_page(
            navigation_layout,
            index=4,
            button_text="Test Plot\nScreenshot",
            object_name="testPlotScreenshot",
            page_widget=self._test_plot_screenshot_panel,
        )

        navigation_layout.addStretch(1)

        content_area = QWidget(main_container)
        content_area.setObjectName("subWindowContentArea")
        self._content_layout = QVBoxLayout(content_area)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(10)
        self._content_layout.addWidget(self._page_stack, 1)

        main_layout.addWidget(navigation_panel)
        main_layout.addWidget(content_area, 1)

        self._ui.centralLayout.addWidget(main_container, 1)
        self._navigation_button_group.button(0).setChecked(True)

        self.setStyleSheet(
            """
            QWidget#navigationPanel QPushButton[navigationButton="true"] {
                background: #f8f8f8;
                border: 1px solid #3f73a8;
                color: #111111;
                font-size: 23px;
                padding: 4px 6px;
                text-align: center;
            }

            QWidget#navigationPanel QPushButton[navigationButton="true"]:checked {
                background: #eaf3ff;
                border: 2px solid #2f69a6;
            }

            QWidget#navigationPanel QPushButton[navigationButton="true"]:hover {
                background: #f1f7ff;
            }
            """
        )

    def _add_navigation_page(
        self,
        navigation_layout: QVBoxLayout,
        *,
        index: int,
        button_text: str,
        object_name: str,
        page_widget: QWidget,
    ) -> None:
        """내비게이션 버튼과 연결된 스택 페이지를 추가한다."""

        button = QPushButton(button_text, self)
        button.setObjectName(f"{object_name}NavigationButton")
        button.setProperty("navigationButton", True)
        button.setCheckable(True)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFixedHeight(70)
        button.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self._navigation_button_group.addButton(button, index)
        navigation_layout.addWidget(button)

        page = self._create_page(page_widget)
        page.setObjectName(f"{object_name}Page")
        self._page_stack.addWidget(page)

    def _create_page(self, content_widget: QWidget) -> QWidget:
        """서브 윈도우 페이지 공통 외곽을 만든다."""

        page = QWidget(self._page_stack)
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)

        content_widget.setParent(page)
        content_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        page_layout.addWidget(content_widget, 1)
        return page

    def on_navigation_button_clicked(self, index: int) -> None:
        """내비게이션 버튼 클릭 시 우측 서브 윈도우를 전환한다."""

        self._page_stack.setCurrentIndex(index)

    def on_start_requested(self) -> None:
        """Test Manager의 시작 요청을 Runner에 전달한다."""

        settings = self._test_manager_panel.build_test_run_settings()
        if settings is None:
            return
        if self._runner.restart_index is None:
            self._test_manager_panel.reset_test_case_progress()
        self._runner.start(
            list(self._test_manager_panel.test_cases),
            settings=settings,
        )

    def on_get_tdf_list_requested(self) -> None:
        """TDF 파일 목록 조회 요청을 서비스에 전달한다."""

        if not self._ensure_tdf_operation_allowed():
            return
        self._pending_tdf_operation = "get_list"
        self._pending_tdf_file_name = None
        self._begin_tdf_operation_lock()
        self._tdf_service.get_tdf_list()

    def on_tdf_all_off_requested(self) -> None:
        """모든 TDF 비활성화 요청을 서비스에 전달한다."""

        if not self._ensure_tdf_operation_allowed():
            return
        self._pending_tdf_operation = "all_off"
        self._pending_tdf_file_name = None
        self._begin_tdf_operation_lock()
        self._tdf_service.tdf_all_off()

    def on_set_tdf_requested(self, tdf_file_name: str) -> None:
        """선택 TDF 활성화 요청을 서비스에 전달한다."""

        if not self._ensure_tdf_operation_allowed():
            return
        self._pending_tdf_operation = "set_tdf"
        self._pending_tdf_file_name = tdf_file_name
        self._begin_tdf_operation_lock()
        self._tdf_service.set_tdf(tdf_file_name)

    def on_tdf_operation_started(self) -> None:
        """TDF 작업 진행 상태를 UI에 반영한다."""

        self._begin_tdf_operation_lock()
        self._show_tdf_progress_dialog("TDF 작업 진행 중")

    def on_tdf_operation_finished(self, message: str) -> None:
        """TDF 작업 완료 상태를 UI에 반영한다."""

        self._tdf_operation_active = False
        self._test_manager_panel.set_tdf_operation_locked(False)
        self._close_tdf_progress_dialog()
        self._update_instrument_operation_lock()
        if self._pending_tdf_operation == "set_tdf" and self._pending_tdf_file_name:
            self._test_manager_panel.set_active_tdf_file_name(
                self._pending_tdf_file_name,
            )
        elif self._pending_tdf_operation == "all_off":
            self._test_manager_panel.clear_active_tdf_file_name()
        self._pending_tdf_operation = None
        self._pending_tdf_file_name = None
        self._show_info("TDF", message)

    def on_tdf_operation_failed(self, message: str) -> None:
        """TDF 작업 실패 상태를 UI에 반영한다."""

        self._tdf_operation_active = False
        self._test_manager_panel.set_tdf_operation_locked(False)
        self._close_tdf_progress_dialog()
        self._update_instrument_operation_lock()
        self._pending_tdf_operation = None
        self._pending_tdf_file_name = None
        self._show_warning("TDF", f"TDF 작업 실패: {message}")

    def on_measurement_active_changed(self, active: bool) -> None:
        """측정 실행 중에는 Instrument Check 재연결을 막는다."""

        _ = active
        self._update_instrument_operation_lock()

    def on_instrument_set_started(self) -> None:
        """Instrument Set 진행 중 UI 장비 작업을 차단한다."""

        self._instrument_set_active = True
        self._update_instrument_operation_lock()

    def on_instrument_set_finished(self) -> None:
        """Instrument Set 완료 후 장비 작업 차단 상태를 갱신한다."""

        self._instrument_set_active = False
        self._update_instrument_operation_lock()
        self._test_manager_panel.update_turntable_info(
            {
                "target_angle": 0,
                "current_angle": 0,
                "setting_speed": 4,
            }
        )
        self._test_manager_panel.update_polarization_info(
            {
                "polarization_3m": "V",
                "polarization_bilog": "V",
                "polarization_1m": "0°",
            }
        )

    def on_instrument_set_failed(self, message: str) -> None:
        """Instrument Set 실패 후 장비 작업 차단 상태를 갱신한다."""

        _ = message
        self._instrument_set_active = False
        self._update_instrument_operation_lock()

    def on_equipment_disconnected(self, states: dict[str, bool]) -> None:
        """Set 실패/timeout으로 장비가 disconnected로 전환되면 UI에 반영한다."""

        self._test_manager_panel.set_connection_state(states)
        self._rf_filter_box_panel.set_connection_state(states)
        self._instrument_check_panel.mark_all_equipment_disconnected()

    def _update_instrument_operation_lock(self) -> None:
        block_reason = None
        if self._runner.is_measurement_active:
            block_reason = INSTRUMENT_CONNECTION_BLOCK_MESSAGE
        elif self._instrument_set_active:
            block_reason = INSTRUMENT_SET_BLOCK_MESSAGE
        elif self._tdf_operation_active:
            block_reason = TDF_OPERATION_IN_PROGRESS_MESSAGE

        self._instrument_check_panel.set_connection_block_reason(block_reason)
        self._test_manager_panel.set_run_settings_locked(
            self._runner.is_measurement_active
            or self._instrument_set_active
            or self._tdf_operation_active
        )
        self._rf_filter_box_panel.set_operation_locked(block_reason is not None)
        self._test_manager_panel.set_pause_enabled(self._runner.is_measurement_active)

    def _ensure_tdf_operation_allowed(self) -> bool:
        block_reason = self._tdf_operation_block_reason()
        if block_reason:
            self._show_warning("TDF", block_reason)
            return False
        return True

    def _begin_tdf_operation_lock(self) -> None:
        """TDF 요청 직후 다른 장비 조작을 즉시 차단한다."""

        self._tdf_operation_active = True
        self._test_manager_panel.set_tdf_operation_locked(True)
        self._update_instrument_operation_lock()

    def _tdf_operation_block_reason(self) -> str | None:
        if self._runner.is_measurement_active:
            return INSTRUMENT_CONNECTION_BLOCK_MESSAGE
        if self._instrument_set_active:
            return INSTRUMENT_SET_BLOCK_MESSAGE
        if self._tdf_operation_active or self._tdf_service.is_running:
            return TDF_OPERATION_IN_PROGRESS_MESSAGE
        if self._runner.instrument_connection_service.is_connecting:
            return "장비 연결 요청이 진행 중입니다."
        if self._runner.equipment_state.get("FSV40") is not True:
            return _FSV40_NOT_CONNECTED_MESSAGE
        return None

    def _show_tdf_progress_dialog(self, initial_step: str) -> None:
        """TDF 작업 진행 상태를 modeless dialog로 표시한다."""

        self._close_tdf_progress_dialog()
        dialog = InstrumentSetProgressDialog(self, initial_step=initial_step)
        dialog.setObjectName("tdfProgressDialog")
        dialog.setWindowTitle("TDF 작업 진행 중")
        dialog.set_step(initial_step)
        self._tdf_progress_dialog = dialog
        dialog.start()

    def _close_tdf_progress_dialog(self) -> None:
        """TDF 완료/실패 또는 종료 시 진행 dialog를 닫는다."""

        dialog = self._tdf_progress_dialog
        if dialog is None:
            return
        self._tdf_progress_dialog = None
        dialog.close_without_action()
        dialog.setParent(None)
        dialog.deleteLater()

    def on_current_case_changed(self, case: TestCase) -> None:
        """현재 실행 중인 TestCase 요약 정보를 갱신한다."""

        self._test_manager_panel.set_current_case(case)
        self._test_manager_panel.mark_current_test_case(case)

    def on_session_finished(self) -> None:
        self._test_manager_panel.complete_current_test_case()
        self._show_info("시험 완료", "모든 시험이 완료되었습니다.")

    def _show_info(self, title: str, message: str) -> None:
        QMessageBox.information(self, title, message)

    def _show_warning(self, title: str, message: str) -> None:
        QMessageBox.warning(self, title, message)

    def on_user_action_required(self, message: str) -> None:
        """시험원이 수동 조작 완료를 입력할 수 있는 팝업을 표시한다."""

        existing_dialog = getattr(self, "_user_action_dialog", None)
        if existing_dialog is not None:
            close_without_action = getattr(existing_dialog, "close_without_action", None)
            if callable(close_without_action):
                close_without_action()
            else:
                existing_dialog.close()

        dialog = _UserActionDialog(self)
        dialog.setObjectName("userActionRequiredDialog")
        dialog.setWindowTitle("User Action Required")
        dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
        dialog.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        label = QLabel(message, dialog)
        label.setObjectName("userActionRequiredLabel")
        label.setWordWrap(True)
        layout.addWidget(label)

        button_layout = QHBoxLayout()
        button_layout.addStretch(1)

        stop_button = QPushButton("중단", dialog)
        stop_button.setObjectName("userActionStopButton")
        stop_button.clicked.connect(lambda _checked=False: self._runner.stop())
        stop_button.clicked.connect(dialog.accept)
        button_layout.addWidget(stop_button)

        complete_button = QPushButton("완료", dialog)
        complete_button.setObjectName("userActionCompleteButton")
        complete_button.clicked.connect(
            lambda _checked=False: self._runner.user_action_completed()
        )
        complete_button.clicked.connect(dialog.accept)
        button_layout.addWidget(complete_button)
        layout.addLayout(button_layout)

        dialog.finished.connect(lambda _result: self._clear_user_action_dialog(dialog))
        self._user_action_dialog = dialog
        dialog.show()

    def _clear_user_action_dialog(self, dialog: QDialog) -> None:
        """현재 수동 조작 팝업 참조를 정리한다."""

        if getattr(self, "_user_action_dialog", None) is dialog:
            self._user_action_dialog = None

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        """창 표시 후 네이티브 resize 테두리 정책을 다시 적용한다."""

        super().showEvent(event)
        if self.isMaximized() or self.isFullScreen():
            self._unlock_window_size()
            return
        self._lock_default_window_size()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        """윈도우 종료 전에 worker를 가진 하위 패널을 정리한다."""

        self._shutdown_child_panels()
        self._close_tdf_progress_dialog()
        self._tdf_service.shutdown()
        self._runner.shutdown()
        super().closeEvent(event)

    def event(self, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Destroy:
            self._shutdown_child_panels()
            self._close_tdf_progress_dialog()
            self._tdf_service.shutdown()
            self._runner.shutdown()
        return super().event(event)

    def _shutdown_child_panels(self) -> None:
        seen: set[int] = set()
        for widget in self.findChildren(QWidget):
            identifier = id(widget)
            if identifier in seen:
                continue
            seen.add(identifier)

            shutdown = getattr(widget, "shutdown", None)
            if callable(shutdown):
                shutdown()
                continue

            dispose = getattr(widget, "dispose", None)
            if callable(dispose):
                dispose()

    def showMaximized(self) -> None:  # noqa: N802
        """최대화 진입 전 크기 제한을 해제한다."""

        self._unlock_window_size()
        super().showMaximized()

    def showFullScreen(self) -> None:  # noqa: N802
        """전체화면 진입 전 크기 제한을 해제한다."""

        self._unlock_window_size()
        super().showFullScreen()

    def showNormal(self) -> None:  # noqa: N802
        """일반 창으로 돌아올 때 기본 크기로 다시 고정한다."""

        super().showNormal()
        self._lock_default_window_size()

    def changeEvent(self, event: QEvent) -> None:  # noqa: N802
        """타이틀바 상태 전환 시 크기 제한을 갱신한다."""

        super().changeEvent(event)
        if event.type() != QEvent.Type.WindowStateChange:
            return
        if self.isMaximized() or self.isFullScreen():
            self._unlock_window_size()
            return
        self._lock_default_window_size()

    def _lock_default_window_size(self) -> None:
        """일반 상태에서 창 크기를 기본 크기로 고정한다."""

        self.resize(_DEFAULT_WINDOW_SIZE)
        self.setMinimumSize(_DEFAULT_WINDOW_SIZE)
        self.setMaximumSize(_UNBOUNDED_WINDOW_SIZE)
        self._set_windows_resize_frame_enabled(False)

    def _unlock_window_size(self) -> None:
        """최대화/전체화면 전환을 위해 크기 제한을 해제한다."""

        self.setMinimumSize(0, 0)
        self.setMaximumSize(_UNBOUNDED_WINDOW_SIZE)
        self._set_windows_resize_frame_enabled(True)

    def _set_windows_resize_frame_enabled(self, enabled: bool) -> None:
        """Windows에서 드래그 resize 테두리만 켜고 끈다."""

        if sys.platform != "win32":
            return

        hwnd = int(self.winId())
        style = ctypes.windll.user32.GetWindowLongPtrW(hwnd, _GWL_STYLE)
        if enabled:
            style |= _WS_THICKFRAME | _WS_MAXIMIZEBOX
        else:
            style = (style & ~_WS_THICKFRAME) | _WS_MAXIMIZEBOX

        ctypes.windll.user32.SetWindowLongPtrW(hwnd, _GWL_STYLE, style)
        ctypes.windll.user32.SetWindowPos(
            hwnd,
            0,
            0,
            0,
            0,
            0,
            _SWP_NOMOVE | _SWP_NOSIZE | _SWP_NOZORDER | _SWP_FRAMECHANGED,
        )
