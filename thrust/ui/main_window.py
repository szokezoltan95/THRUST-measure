from __future__ import annotations

import json
import os
import sys
import threading
from dataclasses import fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QObject, QSettings, QTimer, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QActionGroup, QColor, QDesktopServices, QFont, QGuiApplication, QPalette
from PyQt6.QtSvgWidgets import QSvgWidget
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QAbstractItemView,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QTextBrowser,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from scope.scope_config import ScopeConfig
from simple.simple_config import SimpleConfig
from thrust.analysis.artifact import build_analysis_artifact, save_analysis_artifact
from thrust.analysis.local_graph import save_local_response_graph
from thrust.analysis.scope_log import analyze_scope_log
from thrust.analysis.simple_log import analyze_simple_log
from thrust.runners.simple_runner import run_simple
from thrust.ui.pages.common_settings_page import CommonSettingsPage
from thrust.ui.pages.scope_settings_page import ScopeSettingsPage
from thrust.ui.pages.simple_settings_page import SimpleSettingsPage
from thrust.ui.axis_assignment_dialog import AxisAssignmentDialog
from thrust.tx16smk3_led import DEFAULTS, LedController, LedStyle, STATES
from thrust.ui.legacy_import_dialog import LegacyImportDialog
from thrust.webdb_client import DEFAULT_WEBDB_URL, WebDbClient, WebDbError
from thrust.updater import UpdateWorker, current_version, display_version
from thrust.joystick_profiles import joystick_profile_key
from thrust.raw_compression import compress_raw_log
from thrust.upload_queue import MeasurementUploadQueue


class MeasurementUploadDialog(QDialog):
    retry_requested = pyqtSignal()
    disconnect_requested = pyqtSignal()

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("Measurement upload")
        self.setMinimumSize(500, 360)
        self.setWindowModality(Qt.WindowModality.NonModal)

        self.stage_label = QLabel("Preparing measurement upload…")
        self.stage_label.setObjectName("appTitle")
        self.detail_label = QLabel("The measurement is safely stored locally while it is prepared.")
        self.detail_label.setWordWrap(True)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 1000)
        self.progress_bar.setValue(0)
        self.activity_log = QPlainTextEdit()
        self.activity_log.setReadOnly(True)
        self.activity_log.setMinimumHeight(160)
        self.archive_label = QLabel()
        self.archive_label.setWordWrap(True)
        self.archive_label.setVisible(False)

        self.retry_button = QPushButton("Retry upload")
        self.retry_button.setVisible(False)
        self.retry_button.clicked.connect(self.retry_requested.emit)
        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.clicked.connect(self.disconnect_requested.emit)
        self.close_button = QPushButton("Close")
        self.close_button.setEnabled(False)
        self.close_button.clicked.connect(self.accept)
        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(self.disconnect_button)
        buttons.addWidget(self.retry_button)
        buttons.addWidget(self.close_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self.stage_label)
        layout.addWidget(self.detail_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.activity_log, 1)
        layout.addWidget(self.archive_label)
        layout.addLayout(buttons)
        self._last_stage = ""

    def set_connection_controls(self, connected: bool, disconnect_enabled: bool = True) -> None:
        self.disconnect_button.setVisible(connected)
        self.disconnect_button.setEnabled(disconnect_enabled)

    def add_detail(self, message: str) -> None:
        self.activity_log.appendPlainText(f"[{datetime.now().astimezone():%H:%M:%S}] {message}")

    def set_progress(self, stage: str, current: int | None, total: int | None, detail: str) -> None:
        self.stage_label.setText(stage)
        self.detail_label.setText(detail)
        if stage != self._last_stage:
            self.add_detail(stage)
            self._last_stage = stage
        if current is None or total is None or total <= 0:
            self.progress_bar.setRange(0, 0)
            return
        self.progress_bar.setRange(0, 1000)
        self.progress_bar.setValue(min(1000, int(current * 1000 / total)))
        self.progress_bar.setFormat(f"%p% · {current / 1024 / 1024:.1f} / {total / 1024 / 1024:.1f} MB")

    def prepare_retry(self) -> None:
        self.retry_button.setVisible(False)
        self.close_button.setEnabled(False)
        self.archive_label.setVisible(False)
        self.progress_bar.setRange(0, 1000)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Preparing…")
        self.add_detail("Starting a new upload attempt.")
        self._last_stage = ""

    def show_waiting_for_connection(self, participant: str, test: str) -> None:
        self.stage_label.setText("Upload waiting for WebDB connection")
        self.detail_label.setText(
            f"A measurement is safely queued on this computer. Connect to WebDB to upload it.\n"
            f"Participant: {participant or '—'}\nTest: {test or '—'}"
        )
        self.progress_bar.setRange(0, 1000)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Waiting for connection")
        self.retry_button.setVisible(False)
        self.close_button.setEnabled(True)
        self._last_stage = ""

    def show_idle(self, queued_count: int = 0) -> None:
        self.stage_label.setText("No active processing")
        self.detail_label.setText(
            "The application is idle." if not queued_count
            else f"{queued_count} measurement(s) are saved in the local upload queue and await a WebDB connection."
        )
        self.progress_bar.setRange(0, 1000)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Idle" if not queued_count else "Waiting for WebDB")
        self.retry_button.setVisible(False)
        self.archive_label.setVisible(False)
        self.close_button.setEnabled(True)
        self._last_stage = ""

    def begin_new_upload(self) -> None:
        self.activity_log.clear()
        self.retry_button.setVisible(False)
        self.close_button.setEnabled(False)
        self.archive_label.setVisible(False)
        self.progress_bar.setRange(0, 1000)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Preparing…")
        self._last_stage = ""

    def show_failure(self, message: str, archive_path: str, receipt: dict[str, Any] | None = None) -> None:
        self.stage_label.setText("Upload could not be completed")
        receipt = receipt or {}
        summary = receipt.get("session_summary", {})
        details = [message]
        if receipt:
            details.extend([
                f"Participant: {receipt.get('participant_code', '—')}",
                f"Test: {receipt.get('test_label', '—')}",
                f"Started: {receipt.get('started_at', '—')}",
                f"Completed tasks: {summary.get('completed', '—')} · mistakes: {summary.get('mistakes', '—')}",
                f"Status: {'incomplete' if summary.get('aborted') else 'completed'}",
            ])
        self.detail_label.setText("\n".join(details))
        self.progress_bar.setRange(0, 1000)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Upload failed")
        self.archive_label.setText(f"Local measurement file is preserved at:\n{archive_path}")
        self.archive_label.setVisible(True)
        self.retry_button.setVisible(True)
        self.close_button.setEnabled(True)
        self.add_detail(f"Upload failed: {message}")
        self.add_detail(f"Local measurement file preserved: {archive_path}")

    def show_success(self, measurement_id: str, archive_path: str, receipt: dict[str, Any] | None = None) -> None:
        self.stage_label.setText("Measurement stored in WebDB")
        receipt = receipt or {}
        summary = receipt.get("session_summary", {})
        result_lines = [f"Participant: {receipt.get('participant_code', '—')}",
                        f"Test: {receipt.get('test_label', '—')}",
                        f"Started: {receipt.get('started_at', '—')}",
                        f"Completed tasks: {summary.get('completed', '—')}",
                        f"Mistakes: {summary.get('mistakes', '—')}",
                        f"Status: {'incomplete' if summary.get('aborted') else 'completed'}",
                        f"WebDB measurement ID: {measurement_id}"]
        self.detail_label.setText("\n".join(result_lines))
        self.progress_bar.setRange(0, 1000)
        self.progress_bar.setValue(1000)
        self.progress_bar.setFormat("Complete")
        self.archive_label.setText(f"Local archive: {archive_path}")
        self.archive_label.setVisible(True)
        self.retry_button.setVisible(False)
        self.close_button.setEnabled(True)
        self.add_detail(f"WebDB confirmed storage (measurement {measurement_id}).")


class MeasurementUploadWorker(QObject):
    progress = pyqtSignal(str, object, object, str)
    succeeded = pyqtSignal(object, str, object)
    failed = pyqtSignal(str, str)
    finished = pyqtSignal()

    def __init__(self, payload: dict[str, Any]) -> None:
        super().__init__()
        self.payload = payload
        self.local_path = str(payload["raw_log_path"])

    def run(self) -> None:
        try:
            self.progress.emit("Compressing raw log", None, None, "Compressing the measurement log in the background.")
            archive_path = compress_raw_log(
                self.local_path,
                progress_callback=lambda stage, current, total: self.progress.emit(
                    stage, current, total,
                    "Compressing the measurement log." if stage == "Compressing raw log"
                    else "Checking the compressed archive before upload.",
                ),
            )
            self.local_path = str(archive_path)
            queue_id = self.payload.get("queue_id")
            if queue_id:
                MeasurementUploadQueue().update(
                    str(queue_id), raw_log_path=self.local_path, queue_status="uploading"
                )
            self.progress.emit("Analyzing measurement", None, None, "Preparing the measurement results and metadata.")
            if self.payload["is_simple"]:
                analysis = analyze_simple_log(archive_path, started_at=self.payload["started_at"])
            else:
                analysis = analyze_scope_log(archive_path)
            analysis = build_analysis_artifact(
                archive_path,
                analysis,
                started_at=self.payload["started_at"],
                test=self.payload["test"],
                parameters=self.payload["session_parameters"],
                runtime=self.payload["runtime"],
                session_summary=self.payload["session_summary"],
            )
            analysis_path = save_analysis_artifact(archive_path, analysis)
            graph_path: str | None = None
            if self.payload["create_local_graph"]:
                try:
                    graph_path = str(save_local_response_graph(
                        archive_path, analysis,
                        participant_id=self.payload["participant_code"],
                    ))
                except Exception as graph_error:
                    self.progress.emit(
                        "Preparing upload package", None, None,
                        f"Local graph could not be created ({graph_error}); continuing with upload.",
                    )
            self.progress.emit(
                "Preparing upload package", None, None,
                f"Analysis saved locally ({analysis_path}). Encoding the archive for WebDB.",
            )
            uploaded = self.payload["client"].upload_measurement(
                participant_id=self.payload["participant_id"],
                test_definition_id=self.payload["test_definition_id"],
                started_at=analysis.get("started_at") or self.payload["started_at"],
                raw_log_path=archive_path,
                analysis_data=analysis,
                status=self.payload["status"],
                precompressed=True,
                progress_callback=lambda stage, current, total, detail: self.progress.emit(
                    stage, current, total, detail,
                ),
            )
            self.local_path = str(archive_path)
            self.succeeded.emit(uploaded, self.local_path, graph_path)
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}", self.local_path)
        finally:
            self.finished.emit()


class LoginDialog(QDialog):
    def __init__(self, server: str, username: str, password: str, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("Connect to THRUST WebDB")
        self.setMinimumWidth(390)

        self.server_edit = QLineEdit(server)
        self.username_edit = QLineEdit(username)
        self.password_edit = QLineEdit(password)
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)

        form = QFormLayout()
        form.addRow("WebDB address:", self.server_edit)
        form.addRow("E-mail / Participant ID / username:", self.username_edit)
        form.addRow("Password:", self.password_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def values(self) -> tuple[str, str, str]:
        return (
            self.server_edit.text().strip(),
            self.username_edit.text(),
            self.password_edit.text(),
        )


class AdvancedSettingsDialog(QDialog):
    """State-aware settings dialog for runtime and, when offline, test settings."""

    def __init__(self, common_page: CommonSettingsPage, scope_page: ScopeSettingsPage, simple_page: SimpleSettingsPage, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("THRUST settings")
        self.resize(820, 720)

        self.tabs = QTabWidget()
        self.runtime_tab_index = self.tabs.addTab(common_page, "Joystick and runtime")
        self.scope_tab_index = self.tabs.addTab(scope_page, "Offline SCoPE")
        self.simple_tab_index = self.tabs.addTab(simple_page, "Offline SimPLE")

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)
        layout.addWidget(buttons)

    def set_offline_visible(self, visible: bool) -> None:
        self.tabs.setTabVisible(self.scope_tab_index, visible)
        self.tabs.setTabVisible(self.simple_tab_index, visible)

    def set_measurement_mode(self, is_simple: bool) -> None:
        self.tabs.setCurrentIndex(self.simple_tab_index if is_simple else self.scope_tab_index)


class MainWindow(QMainWindow):
    catalogue_checked = pyqtSignal(object, object, object, object)
    reconnect_checked = pyqtSignal(object, object, object, object)
    remote_disconnect = pyqtSignal(object)
    led_error = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("THRUST · measurement client")
        self.resize(620, 800)
        self.setMinimumSize(500, 700)
        self.settings = QSettings("THRUST", "THRUST-measure")
        self._update_worker: UpdateWorker | None = None
        self._available_update: dict[str, Any] | None = None
        self.about_dialog: QDialog | None = None
        self.about_version_label: QLabel | None = None
        self.about_update_status: QLabel | None = None
        self.about_release_notes: QTextBrowser | None = None
        self.install_update_button: QPushButton | None = None
        self._about_status_message = "Check for updates to see whether a newer version is available."
        self.led_styles = {}
        for state in STATES:
            color, animation = DEFAULTS[state]
            try:
                self.led_styles[state] = LedStyle(
                    str(self.settings.value(f"lights/{state}/color", color)),
                    str(self.settings.value(f"lights/{state}/animation", animation)),
                )
            except ValueError:
                self.led_styles[state] = LedStyle(color, animation)
        self.led_controller: LedController | None = None
        self.led_error.connect(lambda error: self.append_log(f"TX16SMK3 lights: {error}"))
        self.theme_mode = str(self.settings.value("appearance/theme", "system"))
        if self.theme_mode not in {"system", "dark", "light"}:
            self.theme_mode = "system"
        self._system_palette = QApplication.palette()

        self.client: WebDbClient | None = None
        self.current_manifest: dict[str, Any] | None = None
        self.available_tests: list[dict[str, Any]] = []
        self.offline_mode = True
        self._catalogue_check_in_flight = False
        self._catalogue_generation = 0
        self._auto_reconnect = False
        self._catalogue_connection_ok = False
        self._reconnect_in_flight = False
        self._measurement_active = False
        self._upload_in_progress = False
        self._upload_dialog: MeasurementUploadDialog | None = None
        self._upload_worker: MeasurementUploadWorker | None = None
        self._upload_thread: threading.Thread | None = None
        self._pending_upload_payload: dict[str, Any] | None = None
        self._upload_retry_attempt = 0
        self._upload_activity_stage = ""
        self._joystick_connected = False
        self._upload_queue = MeasurementUploadQueue()
        queued_uploads = self._upload_queue.pending()
        self._queued_upload_count = len(queued_uploads)
        if queued_uploads:
            self._pending_upload_payload = queued_uploads[0]
        self._measurement_lock = threading.Lock()
        self._remote_disconnect_requested = False
        self._presence_stop_event: threading.Event | None = None
        self._presence_thread: threading.Thread | None = None
        self._presence_participant_id: str | None = None
        self._presence_test_definition_id: str | None = None
        self.log_history: list[str] = []
        self.log_dialog: QDialog | None = None
        self.log_view: QPlainTextEdit | None = None

        self.common_page = CommonSettingsPage()
        self.scope_page = ScopeSettingsPage()
        self.simple_page = SimpleSettingsPage()
        self.advanced_dialog: AdvancedSettingsDialog | None = None
        self.common_page.joystick_status_changed.connect(self._set_joystick_status)
        self.common_page.joystick_values_changed.connect(self._update_joystick_feedback)
        self.joystick_bars: dict[str, QProgressBar] = {}
        self.axis_labels: dict[str, QLabel] = {}
        self.joystick_device_names: list[str] = []
        self._axis_test_extremes: dict[str, set[str]] = {
            role: set() for role in ("LX", "LY", "RX", "RY", "BREAK", "RESET")
        }

        self.server_edit = QLineEdit(DEFAULT_WEBDB_URL)
        self.username_edit = QLineEdit()
        self.password_edit = QLineEdit()
        self.config_source_combo = QComboBox()
        self.config_source_combo.addItems(["WebDB", "Local offline"])
        self.config_source_combo.setVisible(False)

        self.connection_action_button = QPushButton("Connect")
        self.connection_action_button.clicked.connect(self._connection_action_clicked)

        self.connection_status = QLabel("● WebDB DISCONNECTED · Offline mode")
        self.connection_status.setObjectName("connectionStatus")
        self.connection_status.setProperty("connectionState", "disconnected")

        self.program_selector = QComboBox()
        self.program_selector.addItem("SCoPE", "SCOPE")
        self.program_selector.addItem("SimPLE", "SIMPLE")
        self.program_selector.setVisible(False)
        self.mode_button_group = QButtonGroup(self)
        self.mode_button_group.setExclusive(True)
        mode_switch = QWidget()
        mode_switch_layout = QHBoxLayout(mode_switch)
        mode_switch_layout.setContentsMargins(0, 0, 0, 0)
        mode_switch_layout.setSpacing(5)
        self.mode_buttons: dict[str, QPushButton] = {}
        for label, mode in (("SCoPE", "SCOPE"), ("SimPLE", "SIMPLE")):
            button = QPushButton(label)
            button.setCheckable(True)
            button.setObjectName("modeSwitchOption")
            button.setMinimumHeight(36)
            self.mode_button_group.addButton(button)
            self.mode_buttons[mode] = button
            button.clicked.connect(lambda _checked=False, index=0 if mode == "SCOPE" else 1: self.program_selector.setCurrentIndex(index))
            mode_switch_layout.addWidget(button, 1)

        self.participant_combo = QComboBox()
        self.participant_combo.setEditable(True)
        self.participant_combo.setPlaceholderText("Participant ID")
        self.participant_combo.setEnabled(False)
        self.participant_combo.currentIndexChanged.connect(lambda _: self._update_run_availability())
        self.participant_combo.editTextChanged.connect(lambda _: self._update_run_availability())
        self.participant_combo.currentIndexChanged.connect(lambda _: self._sync_selection_labels())
        self.participant_combo.editTextChanged.connect(lambda _: self._sync_selection_labels())
        self.participant_button = QPushButton("Select participant")
        self.participant_button.setObjectName("selectionPicker")
        self.participant_button.setFixedHeight(34)
        self.participant_button.clicked.connect(self._choose_participant)
        self.participant_combo.setVisible(False)

        self.test_combo = QComboBox()
        self.test_combo.setPlaceholderText("Connect to load test versions")
        self.test_combo.setEnabled(False)
        self.test_combo.currentIndexChanged.connect(self._load_selected_test)
        self.test_combo.currentIndexChanged.connect(lambda _: self._sync_selection_labels())
        self.test_button = QPushButton("Select test version")
        self.test_button.setObjectName("selectionPicker")
        self.test_button.setFixedHeight(34)
        self.test_button.clicked.connect(self._choose_test)
        self.test_combo.setVisible(False)
        self.program_selector.currentIndexChanged.connect(self._refresh_test_choices)
        self.program_selector.currentIndexChanged.connect(self._measurement_mode_changed)

        selection_group = QGroupBox("Participant and test")
        selection_group_layout = QVBoxLayout(selection_group)
        selection_group_layout.addWidget(mode_switch)
        selection_form = QFormLayout()
        self.test_row_label = QLabel("Test version:")
        self.test_row_widget = QWidget()
        self.test_row_layout = QHBoxLayout(self.test_row_widget)
        self.test_row_layout.setContentsMargins(0, 0, 0, 0)
        self.test_row_layout.addWidget(self.test_button)
        self.local_settings_button = QPushButton("Local settings")
        self.local_settings_button.setObjectName("selectionPicker")
        self.local_settings_button.setFixedHeight(34)
        self.local_settings_button.clicked.connect(self._open_advanced)
        self.local_settings_button.setVisible(False)
        self.test_row_layout.addWidget(self.local_settings_button)
        selection_form.addRow("Participant ID:", self.participant_button)
        selection_form.addRow(self.test_row_label, self.test_row_widget)
        selection_group_layout.addLayout(selection_form)
        selection_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        joystick_group = QGroupBox("Joystick link")
        joystick_layout = QVBoxLayout(joystick_group)
        joystick_row = QHBoxLayout()
        self.joystick_selector = QComboBox()
        self.joystick_selector.setPlaceholderText("Select joystick")
        self.joystick_selector.currentIndexChanged.connect(self._select_joystick)
        self.joystick_selector.setVisible(False)
        self.joystick_button = QPushButton("SELECT JOYSTICK · DISCONNECTED")
        self.joystick_button.setObjectName("joystickButton")
        self.joystick_button.setFixedHeight(30)
        self.joystick_button.setProperty("state", "disconnected")
        self.joystick_button.clicked.connect(self._choose_joystick)
        self.joystick_button.setText("Select Joystick")
        joystick_row.addWidget(self.joystick_button, 1)
        joystick_layout.addLayout(joystick_row)

        feedback_grid = QGridLayout()
        self.joystick_bars = {}
        self.axis_bar_stacks: dict[str, QStackedWidget] = {}
        self.axis_placeholders: dict[str, QLabel] = {}
        self.axis_rows: dict[str, QWidget] = {}
        self._axis_spins = {
            "LX": self.common_page.lx_axis_spin,
            "LY": self.common_page.ly_axis_spin,
            "RX": self.common_page.rx_axis_spin,
            "RY": self.common_page.ry_axis_spin,
            "BREAK": self.common_page.break_axis_spin,
            "RESET": self.common_page.reset_axis_spin,
        }
        for row, name in enumerate(("LX", "LY", "RX", "RY", "BREAK", "RESET")):
            axis_row = QWidget()
            axis_row_layout = QHBoxLayout(axis_row)
            axis_row_layout.setContentsMargins(0, 0, 0, 0)
            axis_row_layout.setSpacing(7)
            label = QLabel(name)
            label.setMinimumWidth(48)
            self.axis_labels[name] = label
            bar = QProgressBar()
            bar.setRange(-100, 100)
            bar.setValue(0)
            bar.setTextVisible(False)
            bar.setFixedHeight(8)
            bar.setObjectName("miniAxis")
            self.joystick_bars[name] = bar
            axis_row_layout.addWidget(label)
            if name == "RESET":
                stack = QStackedWidget()
                stack.setFixedHeight(14)
                placeholder = QLabel("—")
                placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
                placeholder.setObjectName("axisPlaceholder")
                placeholder.setToolTip("RESET visualization is not used in SCoPE")
                stack.addWidget(bar)
                stack.addWidget(placeholder)
                stack.setCurrentWidget(placeholder)
                self.axis_bar_stacks[name] = stack
                self.axis_placeholders[name] = placeholder
                axis_row_layout.addWidget(stack, 1)
            else:
                axis_row_layout.addWidget(bar, 1)
            feedback_grid.addWidget(axis_row, row, 0)
            self.axis_rows[name] = axis_row
            self._axis_spins[name].valueChanged.connect(self._on_axis_mapping_changed)
        joystick_layout.addLayout(feedback_grid)

        self.axis_assignment_button = QPushButton("Configure joystick…")
        self.axis_assignment_button.setObjectName("axisAssignmentButton")
        self.axis_assignment_button.setMinimumHeight(38)
        self.axis_assignment_button.clicked.connect(self._open_axis_assignment)
        joystick_layout.addWidget(self.axis_assignment_button)
        joystick_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.run_button = QPushButton("Start measurement")
        self.run_button.setObjectName("startMeasurement")
        self.run_button.setMinimumHeight(62)
        self.run_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.run_button.clicked.connect(self._run_selected_measurement)

        self.local_graphs_checkbox = QCheckBox("Create local response graphs after measurement")
        self.local_graphs_checkbox.setToolTip("Generate and open a Matplotlib PDF of the averaged and median response curves.")
        self.local_graphs_checkbox.setChecked(
            self.settings.value("measurement/local_response_graphs", False, type=bool)
        )
        self.local_graphs_checkbox.toggled.connect(
            lambda enabled: self.settings.setValue("measurement/local_response_graphs", enabled)
        )

        self.measurement_status = {}
        status_row = QHBoxLayout()
        status_row.setContentsMargins(0, 0, 0, 0)
        status_row.setSpacing(8)
        for key in ("webdb", "participant", "test", "joystick"):
            indicator = QLabel()
            indicator.setObjectName("measurementStatus")
            indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
            indicator.setFixedHeight(28)
            indicator.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.measurement_status[key] = indicator
            status_row.addWidget(indicator, 1)

        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(10)

        title_row = QHBoxLayout()
        self.logo_widget: QSvgWidget | None = None
        if (Path(__file__).resolve().parent / "THRUST_LOGO.svg").is_file():
            self.logo_widget = QSvgWidget()
            self.logo_widget.setFixedSize(160, 48)
            self.logo_widget.setAccessibleName("THRUST")
            title_row.addWidget(self.logo_widget)
        else:
            title = QLabel("THRUST")
            title.setObjectName("appTitle")
            title_row.addWidget(title)
        title_row.addStretch()
        self.appearance_button = QToolButton()
        self.appearance_button.setObjectName("appearanceButton")
        self.appearance_button.setText("◐")
        self.appearance_button.setToolTip("Choose system, dark or light colors")
        self.appearance_button.setAccessibleName("Appearance")
        self.theme_menu = QMenu(self.appearance_button)
        self.theme_actions: dict[str, Any] = {}
        self.theme_action_group = QActionGroup(self.theme_menu)
        self.theme_action_group.setExclusive(True)
        for label, value in (("System", "system"), ("Dark", "dark"), ("Light", "light")):
            action = self.theme_menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(value == self.theme_mode)
            self.theme_action_group.addAction(action)
            action.triggered.connect(lambda _checked=False, selected=value: self._set_theme_mode(selected))
            self.theme_actions[value] = action
        self.appearance_button.clicked.connect(self._show_theme_menu)
        title_row.addWidget(self.appearance_button)
        self.logs_button = QPushButton("Logs")
        self.logs_button.setObjectName("logsButton")
        self.logs_button.clicked.connect(self._open_logs)
        title_row.addWidget(self.logs_button)
        self.legacy_import_button = QPushButton("Legacy files")
        self.legacy_import_button.setObjectName("legacyImportButton")
        self.legacy_import_button.setToolTip("Convert and optionally upload old measurement logs")
        self.legacy_import_button.clicked.connect(self._open_legacy_import)
        title_row.addWidget(self.legacy_import_button)
        self.about_button = QPushButton("About")
        self.about_button.setToolTip("Copyright and open-source license")
        self.about_button.clicked.connect(self._open_about)
        title_row.addWidget(self.about_button)
        self.update_button = QPushButton("Check for updates")
        self.update_button.setToolTip("Check GitHub for a newer THRUST-measure release")
        self.update_button.clicked.connect(self._update_button_clicked)
        session_actions = QWidget()
        session_actions_layout = QVBoxLayout(session_actions)
        session_actions_layout.setContentsMargins(0, 0, 0, 0)
        session_actions_layout.setSpacing(4)
        session_actions_layout.addWidget(self.connection_status)

        self.activity_status = QLabel("Idle")
        self.activity_status.setObjectName("activityStatus")
        self.activity_status.setProperty("state", "idle")
        self.activity_status.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.activity_status.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        session_actions_layout.addWidget(self.activity_status)

        session_button_column = QWidget()
        session_button_layout = QVBoxLayout(session_button_column)
        session_button_layout.setContentsMargins(0, 0, 0, 0)
        session_button_layout.addWidget(self.connection_action_button)
        session_button_layout.addStretch()

        session_ribbon = QGroupBox("System status")
        session_ribbon_layout = QHBoxLayout(session_ribbon)
        session_ribbon_layout.setContentsMargins(10, 4, 10, 4)
        session_ribbon_layout.addWidget(session_actions, 1)
        session_ribbon_layout.addWidget(session_button_column)

        controls_panel = QWidget()
        controls_layout = QVBoxLayout(controls_panel)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(8)
        controls_layout.addWidget(selection_group)
        controls_layout.addWidget(joystick_group)
        controls_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        root.addLayout(title_row)
        root.addWidget(session_ribbon)
        root.addWidget(controls_panel)
        root.addWidget(self.local_graphs_checkbox)
        root.addWidget(self.run_button)
        root.addLayout(status_row)
        self.footer_log_label = QLabel("Ready")
        self.footer_log_label.setObjectName("footerLog")
        self.footer_log_label.setFixedHeight(24)
        self.footer_log_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        root.addWidget(self.footer_log_label)

        self.setCentralWidget(central)
        self._apply_theme()
        self._refresh_activity_status()
        style_hints = QGuiApplication.styleHints()
        if hasattr(style_hints, "colorSchemeChanged"):
            style_hints.colorSchemeChanged.connect(self._system_theme_changed)
        self._activate_offline_mode(show_dialog=False)
        self._refresh_joystick_selector()
        self.joystick_scan_timer = QTimer(self)
        self.joystick_scan_timer.timeout.connect(self._poll_joystick_devices)
        self.joystick_scan_timer.start(1000)
        self.catalogue_checked.connect(self._apply_catalogue_check)
        self.reconnect_checked.connect(self._apply_reconnect_check)
        self.remote_disconnect.connect(self._apply_remote_disconnect)
        self.catalogue_timer = QTimer(self)
        self.catalogue_timer.timeout.connect(self._check_webdb_catalogue)
        self.catalogue_timer.start(5_000)
        QTimer.singleShot(0, self._auto_connect_joystick)
        if self.settings.value("lights/enabled", False, type=bool):
            self._set_lights_enabled(True)
        last_update_check = float(self.settings.value("updates/last_check", 0))
        if datetime.now(timezone.utc).timestamp() - last_update_check >= 86_400:
            QTimer.singleShot(5_000, lambda: self._check_for_updates(manual=False))

    def _update_button_clicked(self) -> None:
        self._check_for_updates(manual=True)

    def _install_available_update(self) -> None:
        update = self._available_update
        if update is None:
            return
        installed = display_version(current_version())
        target = display_version(str(update["version"]))
        answer = QMessageBox.question(
            self,
            "Update THRUST-measure",
            f"Install THRUST-measure {target} over version {installed}? The app will close and reopen after the update.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._start_update_worker("download", update)

    def _check_for_updates(self, manual: bool) -> None:
        if self._update_worker is not None and self._update_worker.isRunning():
            return
        self.update_button.setEnabled(False)
        self.update_button.setText("Checking…")
        self._about_status_message = "Checking GitHub Releases…"
        self._refresh_about_update_state()
        self._start_update_worker("check", manual=manual)

    def _start_update_worker(self, operation: str, update: dict[str, Any] | None = None, manual: bool = False) -> None:
        if operation == "download":
            self.update_button.setEnabled(False)
            self.install_update_button.setEnabled(False)
            self.install_update_button.setText("Downloading update…")
            self._about_status_message = f"Downloading version {display_version(str(update['version']))}…"
            self._refresh_about_update_state()
        worker = UpdateWorker(operation, update, self)
        worker.result_ready.connect(lambda result: self._handle_update_result(result, manual))
        worker.finished.connect(lambda: self._update_worker_finished(worker))
        worker.finished.connect(worker.deleteLater)
        self._update_worker = worker
        worker.start()

    def _update_worker_finished(self, worker: UpdateWorker) -> None:
        if self._update_worker is worker:
            self._update_worker = None

    def _refresh_about_update_state(self) -> None:
        if self.about_version_label is None:
            return
        installed = display_version(current_version())
        self.about_version_label.setText(f"Installed version  ·  {installed}")
        self.about_update_status.setText(self._about_status_message)
        if self._available_update is not None:
            target = display_version(str(self._available_update["version"]))
            self.install_update_button.setText(f"Install update to {target}")
            self.install_update_button.setVisible(True)
            notes = str(self._available_update.get("body") or "").strip()
            self.about_release_notes.setMarkdown(notes or "_This release has no published changelog._")
            self.about_release_notes.setVisible(True)
        else:
            self.install_update_button.setVisible(False)
            self.about_release_notes.clear()
            self.about_release_notes.setVisible(False)

    def _handle_update_result(self, result: dict[str, Any], manual: bool) -> None:
        self.update_button.setEnabled(True)
        self.update_button.setText("Check for updates")
        if result.get("operation") == "check" and result.get("ok"):
            self.settings.setValue("updates/last_check", datetime.now(timezone.utc).timestamp())
        if not result.get("ok"):
            self._about_status_message = f"Could not check for updates: {result.get('error', 'Unknown error')}"
            if result.get("operation") == "download" and self.install_update_button is not None:
                self.install_update_button.setEnabled(True)
                self.install_update_button.setText(
                    f"Install update to {display_version(str(self._available_update['version']))}"
                    if self._available_update else "Install update"
                )
            self._refresh_about_update_state()
            if manual or result.get("operation") == "download":
                QMessageBox.warning(self, "THRUST-measure update", str(result.get("error", "Update failed.")))
            return
        if result.get("operation") == "check":
            self._available_update = result.get("update")
            if self._available_update is None:
                self._about_status_message = f"You are using the latest available version ({display_version(current_version())})."
            else:
                installed = display_version(current_version())
                target = display_version(str(self._available_update["version"]))
                self._about_status_message = f"Update available  ·  {installed}  →  {target}"
            self._refresh_about_update_state()
            return
        if result.get("operation") == "download":
            try:
                self._launch_update_helper(Path(result["path"]))
            except Exception as exc:
                self._about_status_message = f"Could not start the updater: {exc}"
                if self.install_update_button is not None:
                    self.install_update_button.setEnabled(True)
                self._refresh_about_update_state()
                QMessageBox.warning(self, "THRUST-measure update", str(exc))

    def _launch_update_helper(self, archive: Path) -> None:
        executable = Path(sys.executable).resolve()
        if sys.platform == "darwin":
            app_bundle = next((parent for parent in executable.parents if parent.suffix == ".app"), None)
            if app_bundle is None:
                raise RuntimeError("Could not locate the THRUST-measure application bundle.")
            target = app_bundle
            helper = app_bundle / "Contents" / "MacOS" / "THRUST-updater"
        else:
            target = executable.parent
            helper_name = "THRUST-updater.exe" if sys.platform == "win32" else "THRUST-updater"
            helper = target / helper_name
        if not helper.is_file():
            raise RuntimeError("The built-in update helper is missing. Reinstall this version before updating.")
        import subprocess
        subprocess.Popen(
            [str(helper), str(archive), str(target), str(os.getpid())],
            cwd=str(target),
            start_new_session=True,
        )
        self.update_button.setEnabled(False)
        self.update_button.setText("Installing…")
        QTimer.singleShot(500, QApplication.quit)

    def _set_lights_enabled(self, enabled: bool) -> None:
        if not enabled:
            if self.led_controller is not None:
                self.led_controller.stop()
                self.led_controller = None
            return
        if self.led_controller is None:
            self.led_controller = LedController(self.led_styles, on_error=self.led_error.emit)
            self.led_controller.start()
        else:
            self.led_controller.set_styles(self.led_styles)
        if not self._measurement_active:
            self.led_controller.set_state("ready" if self.run_button.isEnabled() else "idle")

    def closeEvent(self, event) -> None:
        self._set_lights_enabled(False)
        super().closeEvent(event)

    def _open_about(self) -> None:
        if self.about_dialog is None:
            dialog = QDialog(self)
            dialog.setWindowTitle("About THRUST-measure")
            dialog.setMinimumWidth(560)
            dialog.resize(600, 760)
            layout = QVBoxLayout(dialog)
            heading = QLabel("THRUST-measure · SCoPE · SimPLE")
            heading.setObjectName("appTitle")
            layout.addWidget(heading)
            layout.addWidget(QLabel("Copyright © 2026 Zoltán Szőke · MIT License"))

            update_group = QGroupBox("Software updates")
            update_layout = QVBoxLayout(update_group)
            self.about_version_label = QLabel()
            self.about_version_label.setObjectName("aboutVersion")
            update_layout.addWidget(self.about_version_label)
            self.about_update_status = QLabel()
            self.about_update_status.setWordWrap(True)
            self.about_update_status.setObjectName("aboutUpdateStatus")
            update_layout.addWidget(self.about_update_status)
            self.about_release_notes = QTextBrowser()
            self.about_release_notes.setOpenExternalLinks(True)
            self.about_release_notes.setMaximumHeight(160)
            self.about_release_notes.setVisible(False)
            update_layout.addWidget(self.about_release_notes)
            update_actions = QHBoxLayout()
            update_actions.addWidget(self.update_button)
            self.install_update_button = QPushButton()
            self.install_update_button.clicked.connect(self._install_available_update)
            self.install_update_button.setVisible(False)
            update_actions.addWidget(self.install_update_button)
            update_layout.addLayout(update_actions)
            layout.addWidget(update_group)
            self._refresh_about_update_state()

            license_text = QPlainTextEdit()
            license_text.setReadOnly(True)
            license_text.setPlainText(Path(__file__).with_name("LICENSE.txt").read_text(encoding="utf-8"))
            license_text.setMinimumHeight(240)
            layout.addWidget(license_text, 1)
            actions = QHBoxLayout()
            actions.addStretch()
            close_button = QPushButton("Close")
            close_button.clicked.connect(dialog.accept)
            actions.addWidget(close_button)
            layout.addLayout(actions)
            self.about_dialog = dialog
        self.about_dialog.show()
        self.about_dialog.raise_()
        self.about_dialog.activateWindow()

    def _refresh_joystick_selector(self) -> None:
        devices = self.common_page.available_joysticks()
        previous = self.joystick_selector.currentData()
        changed = devices != self.joystick_device_names
        if changed:
            self.joystick_selector.blockSignals(True)
            self.joystick_selector.clear()
            for index, name in enumerate(devices):
                self.joystick_selector.addItem(f"{index}: {name}", index)
            if not devices:
                self.joystick_selector.addItem("No joystick detected", -1)
            elif isinstance(previous, int) and 0 <= previous < len(devices):
                self.joystick_selector.setCurrentIndex(previous)
            else:
                self.joystick_selector.setCurrentIndex(0)
            self.joystick_selector.blockSignals(False)
            self.joystick_device_names = devices

        self._update_run_availability(self.common_page.joystick_active)
        if not devices:
            if self.common_page.joystick_active:
                self.common_page.stop_joystick()
            self._set_joystick_status(False, "No joystick detected")
        elif len(devices) == 1 and not self.common_page.joystick_active:
            self._select_joystick(self.joystick_selector.currentIndex())

    def _selected_theme_is_dark(self) -> bool:
        if self.theme_mode == "dark":
            return True
        if self.theme_mode == "light":
            return False
        scheme = QGuiApplication.styleHints().colorScheme()
        if scheme == Qt.ColorScheme.Dark:
            return True
        if scheme == Qt.ColorScheme.Light:
            return False
        return self._system_palette.color(QPalette.ColorRole.Window).lightness() < 128

    def _set_theme_mode(self, theme_mode: str) -> None:
        self.theme_mode = theme_mode if theme_mode in {"system", "dark", "light"} else "system"
        self.settings.setValue("appearance/theme", self.theme_mode)
        for key, action in self.theme_actions.items():
            action.setChecked(key == self.theme_mode)
        self._apply_theme()

    def _open_axis_assignment(self) -> None:
        mapping = {role: spin.value() for role, spin in self._axis_spins.items()}
        dialog = AxisAssignmentDialog(self.common_page, mapping, self,
                                      self.led_controller is not None, self.led_styles)
        try:
            if dialog.exec() == QDialog.DialogCode.Accepted:
                if dialog.axis_count > 0:
                    mapping = dialog.values()
                    for role, axis_index in mapping.items():
                        spin = self._axis_spins[role]
                        spin.setMaximum(max(spin.maximum(), axis_index))
                        spin.setValue(axis_index)
                    self._save_joystick_profile(mapping)
                self.led_styles = dialog.led_styles
                for state, style in self.led_styles.items():
                    self.settings.setValue(f"lights/{state}/color", style.color)
                    self.settings.setValue(f"lights/{state}/animation", style.animation)
                self.settings.setValue("lights/enabled", dialog.lights_enabled.isChecked())
                self._set_lights_enabled(dialog.lights_enabled.isChecked())
                self._update_joystick_feedback(self.common_page.latest_axis_values)
        finally:
            dialog.stop()

    def _sync_selection_labels(self) -> None:
        participant = self.participant_combo.currentText().strip()
        self.participant_button.setText(participant or "Select participant")
        test = self.test_combo.currentData()
        self.test_button.setText(self.test_combo.currentText() if test else "Select test version")

    def _choose_from_table(self, title: str, combo: QComboBox, columns: tuple[str, ...]) -> None:
        if combo.count() == 0:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.resize(560, min(520, 130 + combo.count() * 38))
        table = QTableWidget(combo.count(), len(columns), dialog)
        table.setHorizontalHeaderLabels(columns)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        for row in range(combo.count()):
            value = combo.itemData(row)
            if columns == ("Participant",):
                values = (combo.itemText(row),)
            elif isinstance(value, dict):
                values = (str(value.get("name", "")), str(value.get("version", "")))
            else:
                values = (combo.itemText(row), "")
            for column, text in enumerate(values):
                table.setItem(row, column, QTableWidgetItem(text))
        table.resizeColumnsToContents()
        table.horizontalHeader().setStretchLastSection(True)
        if combo.currentIndex() >= 0:
            table.selectRow(combo.currentIndex())
        layout = QVBoxLayout(dialog)
        layout.addWidget(table)
        table.cellClicked.connect(lambda row, _column: (combo.setCurrentIndex(row), dialog.accept()))
        dialog.exec()

    def _choose_participant(self) -> None:
        if self.offline_mode:
            dialog = QDialog(self)
            dialog.setWindowTitle("Participant ID")
            dialog.setMinimumWidth(340)
            layout = QVBoxLayout(dialog)
            edit = QLineEdit(self.participant_combo.currentText())
            edit.setPlaceholderText("Enter participant ID")
            layout.addWidget(edit)
            buttons = QDialogButtonBox(
                QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
            )
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            layout.addWidget(buttons)
            edit.returnPressed.connect(dialog.accept)
            if dialog.exec() == QDialog.DialogCode.Accepted and edit.text().strip():
                self.participant_combo.setCurrentText(edit.text().strip())
                self._sync_selection_labels()
            return
        self._choose_from_table("Choose participant", self.participant_combo, ("Participant",))

    def _choose_test(self) -> None:
        self._choose_from_table("Choose test version", self.test_combo, ("Test", "Version"))

    def _show_theme_menu(self) -> None:
        self.theme_menu.exec(
            self.appearance_button.mapToGlobal(self.appearance_button.rect().bottomLeft())
        )

    def _system_theme_changed(self, *_args: object) -> None:
        if self.theme_mode == "system":
            self._apply_theme()

    def _apply_theme(self) -> None:
        dark = self._selected_theme_is_dark()
        if self.logo_widget is not None:
            logo_dir = Path(__file__).resolve().parent
            logo_path = logo_dir / ("THRUST_LOGO.svg" if dark else "THRUST_LOGO_black.svg")
            if not logo_path.is_file():
                logo_path = logo_dir / "THRUST_LOGO.svg"
            self.logo_widget.load(str(logo_path))
        colors = (
            {
                "window": "#111820", "surface": "#18232d", "surface_alt": "#202e39",
                "input": "#0d151c", "text": "#edf3f7", "muted": "#a5b5c1",
                "border": "#405563", "accent": "#55c7df", "selection": "#175269",
                "button": "#243b49", "button_hover": "#315568", "disabled": "#26313a",
                "disabled_text": "#aab3ba", "log": "#0b1218", "scroll": "#314552",
            }
            if dark else
            {
                "window": "#eef2f5", "surface": "#ffffff", "surface_alt": "#e6edf2",
                "input": "#ffffff", "text": "#17232c", "muted": "#526574",
                "border": "#aabac5", "accent": "#087d9b", "selection": "#b9e4ee",
                "button": "#e0e9ee", "button_hover": "#cadce5", "disabled": "#71262b",
                "disabled_text": "#ffffff", "log": "#f8fafb", "scroll": "#9aacb8",
            }
        )
        palette = QPalette()
        role_colors = {
            QPalette.ColorRole.Window: colors["window"],
            QPalette.ColorRole.WindowText: colors["text"],
            QPalette.ColorRole.Base: colors["input"],
            QPalette.ColorRole.AlternateBase: colors["surface_alt"],
            QPalette.ColorRole.ToolTipBase: colors["surface"],
            QPalette.ColorRole.ToolTipText: colors["text"],
            QPalette.ColorRole.Text: colors["text"],
            QPalette.ColorRole.Button: colors["button"],
            QPalette.ColorRole.ButtonText: colors["text"],
            QPalette.ColorRole.BrightText: "#ffffff" if dark else "#111820",
            QPalette.ColorRole.Highlight: colors["selection"],
            QPalette.ColorRole.HighlightedText: colors["text"] if dark else "#10212a",
            QPalette.ColorRole.Link: colors["accent"],
            QPalette.ColorRole.PlaceholderText: colors["muted"],
        }
        for role, value in role_colors.items():
            palette.setColor(role, QColor(value))
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(colors["disabled_text"]))
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(colors["disabled_text"]))
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor(colors["disabled_text"]))
        app = QApplication.instance()
        if app is not None:
            app.setFont(QFont("Segoe UI", 10))
            app.setPalette(palette)
            app.setStyleSheet(f"""
                QWidget {{ color: {colors['text']}; font-size: 10pt; }}
                QMainWindow, QDialog, QWidget#centralWidget {{ background: {colors['window']}; }}
                QGroupBox {{ color: {colors['text']}; background: {colors['surface']}; border: 1px solid {colors['border']}; border-radius: 8px; margin-top: 10px; padding: 12px 10px 10px; font-weight: 600; }}
                QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 5px; color: {colors['accent']}; }}
                QLabel {{ color: {colors['text']}; background: transparent; }}
                QLabel#appTitle {{ color: {colors['text']}; font-size: 23pt; font-weight: 800; }}
                QToolButton#appearanceButton {{ color: {colors['text']}; background: {colors['surface']}; border: 1px solid {colors['border']}; border-radius: 7px; min-width: 38px; min-height: 38px; font-size: 17pt; padding: 0; }}
                QToolButton#appearanceButton:hover {{ color: {colors['accent']}; border-color: {colors['accent']}; background: {colors['surface_alt']}; }}
                QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit, QTimeEdit, QDateTimeEdit, QPlainTextEdit, QTextEdit {{ color: {colors['text']}; background: {colors['input']}; border: 1px solid {colors['border']}; border-radius: 4px; padding: 6px 8px; selection-background-color: {colors['selection']}; selection-color: {colors['text']}; }}
    QTextBrowser,
                QPlainTextEdit#detailedLog {{ background: {colors['log']}; font-family: monospace; font-size: 9pt; }}
                QLabel#footerLog {{ color: {colors['muted']}; padding-left: 4px; }}
                QComboBox::drop-down {{ background: {colors['button']}; border: 0; width: 24px; }}
                QComboBox QAbstractItemView {{ color: {colors['text']}; background: {colors['surface']}; selection-background-color: {colors['selection']}; selection-color: {colors['text']}; border: 1px solid {colors['border']}; outline: 0; }}
                QPushButton {{ color: {colors['text']}; background: {colors['button']}; border: 1px solid {colors['border']}; border-radius: 5px; padding: 7px 12px; }}
                QPushButton:hover {{ background: {colors['button_hover']}; border-color: {colors['accent']}; }}
                QPushButton:pressed {{ background: {colors['selection']}; }}
                QPushButton:disabled {{ color: {colors['disabled_text']}; background: {colors['disabled']}; border-color: {colors['disabled']}; }}
                QPushButton#modeSwitchOption {{ color: {colors['muted']}; background: {colors['surface_alt']}; font-size: 11pt; font-weight: 700; padding: 7px 16px; }}
                QPushButton#modeSwitchOption:checked {{ color: {colors['text']}; background: {colors['selection']}; border-color: {colors['accent']}; }}
                QPushButton#selectionPicker {{ text-align: left; min-height: 24px; padding: 3px 10px; font-weight: 600; }}
                QPushButton#joystickButton {{ text-align: center; min-height: 24px; padding: 3px 8px; font-weight: 600; }}
                QPushButton#joystickButton:hover {{ border-color: {colors['accent']}; }}
                QPushButton#joystickButton[state="connected"] {{ color: #20b865; }}
                QPushButton#joystickButton[state="testing"] {{ color: #e5a126; }}
                QPushButton#joystickButton[state="disconnected"] {{ color: #ef5962; }}
                QPushButton#axisAssignmentButton {{ text-align: center; padding: 6px 10px; font-weight: 600; }}
                QLabel#axisPlaceholder {{ color: {colors['muted']}; background: {colors['surface_alt']}; border: 1px dashed {colors['border']}; border-radius: 3px; }}
                QLabel#measurementStatus {{ background: transparent; border: none; font-size: 8pt; font-weight: 700; letter-spacing: .3px; }}
                QLabel#measurementStatus[state="ready"] {{ color: #20b865; }}
                QLabel#measurementStatus[state="error"] {{ color: #ef5962; }}
                QLabel#measurementStatus[state="warning"] {{ color: #e59b24; }}
                QLabel#activityStatus[state="idle"] {{ color: {colors['muted']}; }}
                QLabel#activityStatus[state="processing"] {{ color: #e5a126; font-weight: 700; }}
                QLabel#activityStatus[state="uploading"] {{ color: #4b9cff; font-weight: 700; }}
                QLabel#activityStatus[state="warning"] {{ color: #e59b24; font-weight: 700; }}
                QLabel#activityStatus[state="active"] {{ color: #20b865; font-weight: 700; }}
                QPushButton#startMeasurement {{ color: #ffffff; background: #16804b; border: 1px solid #27a967; border-radius: 8px; padding: 13px 16px; font-size: 13pt; font-weight: 800; letter-spacing: .4px; }}
                QPushButton#startMeasurement:hover:enabled {{ background: #1b9959; }}
                QPushButton#startMeasurement:disabled {{ color: #f7eeee; background: #76252c; border-color: #9e343c; }}
                QCheckBox {{ color: {colors['text']}; spacing: 8px; }}
                QCheckBox::indicator {{ width: 17px; height: 17px; border: 1px solid {colors['border']}; border-radius: 3px; background: {colors['input']}; }}
                QCheckBox::indicator:checked {{ background: {colors['accent']}; border-color: {colors['accent']}; }}
                QProgressBar#miniAxis {{ color: {colors['text']}; background: {colors['surface_alt']}; border: 1px solid {colors['border']}; border-radius: 3px; }}
                QProgressBar#miniAxis::chunk {{ background: {colors['accent']}; border-radius: 2px; }}
                QProgressBar#miniAxis[axisTestState="disconnected"]::chunk {{ background: #ef5962; }}
                QProgressBar#miniAxis[axisTestState="testing"]::chunk {{ background: #e5a126; }}
                QProgressBar#miniAxis[axisTestState="complete"]::chunk {{ background: #2d8cff; }}
                QProgressBar#miniAxis[axisTestState="unused"]::chunk {{ background: {colors['muted']}; }}
                QLabel#joystickLed[connectionState="connected"], QLabel#connectionStatus[connectionState="connected"] {{ color: #159653; font-weight: 700; }}
                QLabel#joystickLed[connectionState="disconnected"], QLabel#connectionStatus[connectionState="disconnected"] {{ color: #d34852; font-weight: 700; }}
                QLabel#connectionStatus[connectionState="warning"] {{ color: #b97911; font-weight: 700; }}
                QTabWidget::pane {{ border: 1px solid {colors['border']}; background: {colors['surface']}; }}
                QTabBar::tab {{ color: {colors['text']}; background: {colors['surface_alt']}; border: 1px solid {colors['border']}; padding: 8px 12px; }}
                QTabBar::tab:selected {{ color: {colors['text']}; background: {colors['surface']}; border-bottom-color: {colors['accent']}; }}
                QScrollBar:vertical, QScrollBar:horizontal {{ background: {colors['surface']}; border: 0; margin: 0; }}
                QScrollBar:vertical {{ width: 12px; }} QScrollBar:horizontal {{ height: 12px; }}
                QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{ background: {colors['scroll']}; border-radius: 5px; min-height: 24px; min-width: 24px; }}
                QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
                QToolTip {{ color: {colors['text']}; background: {colors['surface']}; border: 1px solid {colors['border']}; }}
                QMenu {{ color: {colors['text']}; background: {colors['surface']}; border: 1px solid {colors['border']}; }}
                QMenu::item:selected {{ color: {colors['text']}; background: {colors['selection']}; }}
            """)

    def _update_run_availability(self, joystick_present: bool | None = None) -> None:
        connected = self.common_page.joystick_active if joystick_present is None else joystick_present
        mapping_valid = self._axis_assignments_valid()
        required_axes = self._required_joystick_test_axes()
        axes_tested = self._joystick_axes_tested(required_axes)
        joystick_ready = connected and mapping_valid and axes_tested
        participant_ready = bool(
            self.participant_combo.currentText().strip()
            if self.offline_mode
            else self.participant_combo.currentData()
        )
        test_ready = bool(self.current_manifest and self.test_combo.currentIndex() >= 0)
        upload_blocks_online_run = self._pending_upload_payload is not None and not self.offline_mode
        self.run_button.setEnabled(joystick_ready and test_ready and participant_ready and
                                   (self.offline_mode or self._catalogue_connection_ok)
                                   and not self._upload_in_progress and not upload_blocks_online_run)
        if self.led_controller is not None and not self._measurement_active:
            self.led_controller.set_state("ready" if self.run_button.isEnabled() else "idle")
        webdb_ready = not self.offline_mode and self._catalogue_connection_ok
        self._set_status_indicator(
            "webdb", webdb_ready, "WEBDB · CONNECTED", "WEBDB · OFFLINE",
            state="ready" if webdb_ready else "warning",
        )
        self._set_status_indicator("participant", participant_ready, "PARTICIPANT · OK", "SELECT PARTICIPANT")
        self._set_status_indicator("test", test_ready, "TEST · OK", "SELECT TEST")
        if not connected:
            joystick_text, joystick_error, joystick_state = "JOYSTICK · DISCONNECTED", "JOYSTICK · DISCONNECTED", "error"
            self.joystick_button.setText("Select joystick · DISCONNECTED")
            self.joystick_button.setProperty("state", "disconnected")
            joystick_tooltip = "Connect a joystick to begin the axis test."
        elif not mapping_valid:
            joystick_text, joystick_error, joystick_state = "JOYSTICK · CONFIGURE AXES", "JOYSTICK · CONFIGURE AXES", "warning"
            self.joystick_button.setText(f"{self._connected_joystick_name()} · CONFIGURE AXES")
            self.joystick_button.setProperty("state", "testing")
            joystick_tooltip = "Open Configure joystick and assign a unique axis to LX, LY, RX and RY."
        elif not axes_tested:
            complete_count = sum(
                self._joystick_axes_tested([role]) for role in required_axes
            )
            joystick_text = f"JOYSTICK · TEST {complete_count}/{len(required_axes)}"
            joystick_error, joystick_state = joystick_text, "warning"
            self.joystick_button.setText(f"{self._connected_joystick_name()} · PERFORM JOYSTICK TEST")
            self.joystick_button.setProperty("state", "testing")
            joystick_tooltip = "Move every listed axis to its negative and positive limits. The bars turn blue when verified."
        else:
            joystick_text, joystick_error, joystick_state = "JOYSTICK · READY", "JOYSTICK · READY", "ready"
            self.joystick_button.setText(f"{self._connected_joystick_name()} · READY")
            self.joystick_button.setProperty("state", "connected")
            joystick_tooltip = "Joystick axis test complete."
        self.joystick_button.setToolTip(joystick_tooltip)
        self.joystick_button.style().unpolish(self.joystick_button)
        self.joystick_button.style().polish(self.joystick_button)
        self._set_status_indicator(
            "joystick", joystick_ready, joystick_text, joystick_error, state=joystick_state
        )
        self._refresh_activity_status()

    def _required_joystick_test_axes(self) -> list[str]:
        roles = ["LX", "LY", "RX", "RY"]
        if self._axis_spins["BREAK"].value() >= 0:
            roles.append("BREAK")
        if str(self.program_selector.currentData() or "SCOPE") == "SIMPLE":
            roles.append("RESET")
        return roles

    def _axis_assignments_valid(self) -> bool:
        if not self.common_page.joystick_active or self.common_page.joystick is None:
            return False
        try:
            count = int(self.common_page.joystick.get_numaxes())
        except Exception:
            return False
        roles = self._required_joystick_test_axes()
        indices = [int(self._axis_spins[role].value()) for role in roles]
        if any(index < 0 or index >= count for index in indices):
            return False
        gimbal_indices = [int(self._axis_spins[role].value()) for role in ("LX", "LY", "RX", "RY")]
        return len(set(gimbal_indices)) == len(gimbal_indices) and len(set(indices)) == len(indices)

    def _joystick_axes_tested(self, roles: list[str]) -> bool:
        return all({"negative", "positive"}.issubset(self._axis_test_extremes.get(role, set())) for role in roles)

    def _connected_joystick_name(self) -> str:
        device_index = self.joystick_selector.currentData()
        if isinstance(device_index, int) and 0 <= device_index < len(self.joystick_device_names):
            return self.joystick_device_names[device_index]
        return "Joystick"

    def _reset_joystick_axis_test(self) -> None:
        for progress in self._axis_test_extremes.values():
            progress.clear()

    def _on_axis_mapping_changed(self, _value: int = 0) -> None:
        self._reset_joystick_axis_test()
        self._update_joystick_feedback(self.common_page.latest_axis_values)
        if hasattr(self, "run_button"):
            self._update_run_availability()

    def _set_status_indicator(
        self, key: str, ready: bool, good_text: str, error_text: str, *, state: str | None = None
    ) -> None:
        indicator = self.measurement_status.get(key)
        if indicator is None:
            return
        text = good_text if ready else error_text
        next_state = state or ("ready" if ready else "error")
        if indicator.text() == text and indicator.property("state") == next_state:
            return
        indicator.setText(text)
        indicator.setProperty("state", next_state)
        indicator.style().unpolish(indicator)
        indicator.style().polish(indicator)

    def _refresh_activity_status(self) -> None:
        if not hasattr(self, "activity_status"):
            return
        queued_count = self._queued_upload_count
        if self._upload_in_progress:
            stage = self._upload_activity_stage or "Processing measurement"
            lowered = stage.lower()
            state = "uploading" if "uploading measurement" in lowered or "waiting for webdb" in lowered else "processing"
            text = f"{stage} · {queued_count} in queue"
        elif self._measurement_active:
            if self._upload_activity_stage:
                state = "processing" if any(word in self._upload_activity_stage.lower() for word in ("analy", "saving", "prepar")) else "active"
                text = self._upload_activity_stage
            else:
                state = "active"
                text = "Measurement running"
        elif queued_count:
            state = "warning"
            text = f"Upload pending · {queued_count} in queue"
        else:
            state = "idle"
            text = "Idle"
        self.activity_status.setText(text)
        if self.activity_status.property("state") != state:
            self.activity_status.setProperty("state", state)
            self.activity_status.style().unpolish(self.activity_status)
            self.activity_status.style().polish(self.activity_status)
        self.connection_action_button.setToolTip(
            f"Open activity details · {queued_count} measurement(s) in the persistent upload queue."
            if queued_count else "Open recent processing details."
        )

    def _update_activity_progress(self, stage: str, _current: object, _total: object, _detail: str) -> None:
        self._upload_activity_stage = stage
        self._refresh_activity_status()

    def _connection_action_clicked(self) -> None:
        if self.offline_mode or self.client is None:
            self._open_login()
        else:
            self._show_measurement_upload()

    def _refresh_connection_action(self) -> None:
        connected = not self.offline_mode and self.client is not None
        self.connection_action_button.setText("Details" if connected else "Connect")
        self.connection_action_button.setToolTip(
            "View activity details or disconnect from WebDB" if connected
            else "Connect to WebDB"
        )
        if self._upload_dialog is not None:
            self._upload_dialog.set_connection_controls(
                connected, not self._measurement_active and not self._upload_in_progress
            )

    def _measurement_mode_changed(self, _index: int = 0) -> None:
        self._update_joystick_feedback(self.common_page.latest_axis_values)
        if hasattr(self, "run_button"):
            self._update_run_availability()

    def _poll_joystick_devices(self) -> None:
        self._refresh_joystick_selector()

    def _auto_connect_joystick(self) -> None:
        self._refresh_joystick_selector()

    def _choose_joystick(self) -> None:
        self._choose_from_table("Choose joystick", self.joystick_selector, ("Device",))

    def _select_joystick(self, index: int) -> None:
        device_index = self.joystick_selector.itemData(index)
        if device_index is None or int(device_index) < 0:
            self._set_joystick_status(False, "No joystick detected")
            return
        self._reset_joystick_axis_test()
        if self.common_page.select_joystick(int(device_index), connect=True):
            self._apply_joystick_profile()

    def _joystick_profile_identity(self) -> tuple[str, str, str] | None:
        joystick = self.common_page.joystick
        if not self.common_page.joystick_active or joystick is None:
            return None
        try:
            name = str(joystick.get_name() or "").strip()
        except Exception:
            name = ""
        try:
            guid = str(joystick.get_guid() or "").strip()
        except Exception:
            guid = ""
        key = joystick_profile_key(guid, name)
        return (key, guid, name) if key else None

    def _apply_joystick_profile(self) -> None:
        identity = self._joystick_profile_identity()
        if identity is None:
            return
        key, _guid, name = identity
        raw_profile = self.settings.value(f"joystick_profiles/{key}", "")
        if not raw_profile:
            self.axis_assignment_button.setToolTip(
                "Axis assignments are saved automatically for this joystick after configuration."
            )
            return
        try:
            profile = json.loads(str(raw_profile))
            mapping = profile["mapping"]
            axis_count = int(self.common_page.joystick.get_numaxes())
            if not all(
                isinstance(mapping.get(role), int) and 0 <= mapping[role] < axis_count
                for role in self._axis_spins
            ):
                raise ValueError("Saved joystick profile has invalid axis assignments.")
        except (ValueError, TypeError, KeyError, json.JSONDecodeError):
            self.axis_assignment_button.setToolTip(
                "The saved axis profile is invalid. Open Configure joystick to replace it."
            )
            return
        for role, axis_index in mapping.items():
            if role in self._axis_spins:
                self._axis_spins[role].setValue(axis_index)
        self.axis_assignment_button.setToolTip(f"Saved axis assignments loaded for {name or 'this joystick'}.")
        self._update_joystick_feedback(self.common_page.latest_axis_values)

    def _save_joystick_profile(self, mapping: dict[str, int]) -> None:
        identity = self._joystick_profile_identity()
        if identity is None:
            return
        key, guid, name = identity
        profile = {"guid": guid, "name": name, "mapping": mapping}
        self.settings.setValue(f"joystick_profiles/{key}", json.dumps(profile, sort_keys=True))
        self.axis_assignment_button.setToolTip(f"Axis assignments will load automatically for {name or 'this joystick'}.")

    def _set_joystick_status(self, connected: bool, status: str) -> None:
        if connected != self._joystick_connected:
            self._reset_joystick_axis_test()
        self._joystick_connected = connected
        if connected:
            device_index = self.joystick_selector.currentData()
            device_name = (
                self.joystick_device_names[int(device_index)]
                if isinstance(device_index, int) and 0 <= device_index < len(self.joystick_device_names)
                else "Joystick"
            )
        self.joystick_button.setText(f"{device_name} · PERFORM JOYSTICK TEST") if connected else self.joystick_button.setText("Select Joystick · DISCONNECTED")
        self.joystick_button.setProperty("state", "testing" if connected else "disconnected")
        self.joystick_button.style().unpolish(self.joystick_button)
        self.joystick_button.style().polish(self.joystick_button)
        self._update_joystick_feedback(self.common_page.latest_axis_values)
        if hasattr(self, "run_button"):
            self._update_run_availability(connected)

    def _update_joystick_feedback(self, values: object) -> None:
        axis_values = values if isinstance(values, list) else []
        required_axes = self._required_joystick_test_axes()
        progress_changed = False
        for role, bar in self.joystick_bars.items():
            axis_index = self._axis_spins[role].value()
            available = self.common_page.joystick_active and 0 <= axis_index < len(axis_values)
            if role == "RESET":
                is_simple = str(self.program_selector.currentData() or "SCOPE") == "SIMPLE"
                self.axis_bar_stacks[role].setCurrentWidget(
                    bar if is_simple and available else self.axis_placeholders[role]
                )
            if available:
                value = float(axis_values[axis_index])
                bar.setValue(int(max(-1.0, min(1.0, value)) * 100))
                if role in required_axes:
                    if value <= -0.95 and "negative" not in self._axis_test_extremes[role]:
                        self._axis_test_extremes[role].add("negative")
                        progress_changed = True
                    if value >= 0.95 and "positive" not in self._axis_test_extremes[role]:
                        self._axis_test_extremes[role].add("positive")
                        progress_changed = True
            if not self.common_page.joystick_active:
                state = "disconnected"
            elif role not in required_axes:
                state = "unused"
            elif self._joystick_axes_tested([role]):
                state = "complete"
            else:
                state = "testing"
            if bar.property("axisTestState") != state:
                bar.setProperty("axisTestState", state)
                bar.style().unpolish(bar)
                bar.style().polish(bar)
            if role in required_axes:
                reached = self._axis_test_extremes[role]
                label_text = f"{role}  {'−✓' if 'negative' in reached else '−○'} {'+✓' if 'positive' in reached else '+○'}"
            else:
                label_text = role
            if self.axis_labels[role].text() != label_text:
                self.axis_labels[role].setText(label_text)
        if progress_changed and hasattr(self, "run_button"):
            self._update_run_availability()

    def _open_login(self) -> None:
        dialog = LoginDialog(
            self.server_edit.text().strip() or DEFAULT_WEBDB_URL,
            self.username_edit.text(),
            self.password_edit.text(),
            self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            server, username, password = dialog.values()
            self.server_edit.setText(server)
            self.username_edit.setText(username)
            self.password_edit.setText(password)
            self._connect_webdb()

    def _connect_webdb(self, *, show_dialog: bool = True) -> None:
        self._auto_reconnect = True
        with self._measurement_lock:
            self._remote_disconnect_requested = False
        try:
            self.client = WebDbClient(self.server_edit.text().strip() or DEFAULT_WEBDB_URL)
            self._catalogue_generation += 1
            account = self.client.login(self.username_edit.text(), self.password_edit.text())
            tests = self.client.list_tests()
            role = str(account.get("role", ""))

            self.participant_combo.clear()
            if role == "student":
                participant_id = account.get("participant_id")
                participant_code = account.get("participant_code") or participant_id or "STUDENT"
                self.participant_combo.addItem(str(participant_code), participant_id)
                self.participant_combo.setCurrentIndex(0)
                self.participant_combo.setEditable(False)
                self.participant_combo.setEnabled(False)
            else:
                participants = self.client.list_participants()
                for participant in participants:
                    self.participant_combo.addItem(participant["participant_code"], participant["id"])
                self.participant_combo.setEditable(True)
                self.participant_combo.setEnabled(bool(participants))

            self.available_tests = [test for test in tests if test.get("is_active", False)]
            self.offline_mode = False
            self._catalogue_connection_ok = True
            self.config_source_combo.setCurrentIndex(0)
            self._refresh_test_choices()
            self._sync_selection_labels()
            identity = account.get("participant_code") if role == "student" else account.get("username", "")
            self.connection_status.setText(f"● WebDB CONNECTED · {identity}")
            self._set_connection_state("connected")
            self._refresh_connection_action()
            self._update_selection_mode_controls()
            if self.advanced_dialog is not None:
                self.advanced_dialog.set_offline_visible(False)
            self.append_log(f"Loaded {len(tests)} active tests for {role or 'user'}.")
            self._load_selected_test()
            self._start_presence_reporting()
            if self._pending_upload_payload is not None:
                QTimer.singleShot(0, self._resume_pending_upload)

        except (WebDbError, KeyError, ValueError) as exc:
            self.append_log(f"WebDB connection failed: {exc}")
            self._activate_offline_mode(show_dialog=show_dialog, error=str(exc))

    def _start_presence_reporting(self) -> None:
        self._stop_presence_reporting()
        client = self.client
        if client is None or self.offline_mode:
            return
        stop_event = threading.Event()
        self._presence_stop_event = stop_event

        def report() -> None:
            pending_disconnect = False
            try:
                while not stop_event.is_set():
                    measuring = self._measurement_active
                    try:
                        response = client.report_presence(
                            "measuring" if measuring else "idle",
                            participant_id=self._presence_participant_id if measuring else None,
                            test_definition_id=self._presence_test_definition_id if measuring else None,
                        )
                        if response.get("status") == "disconnect_pending":
                            pending_disconnect = True
                            with self._measurement_lock:
                                self._remote_disconnect_requested = True
                        if pending_disconnect:
                            with self._measurement_lock:
                                ready_to_disconnect = not self._measurement_active
                            if ready_to_disconnect:
                                confirmation = client.report_presence("disconnect_ack")
                                if confirmation.get("status") == "disconnect":
                                    self.remote_disconnect.emit(client)
                                    return
                    except WebDbError:
                        pass
                    if stop_event.wait(1 if pending_disconnect else 10):
                        break
            finally:
                try:
                    client.report_presence("disconnected")
                except WebDbError:
                    pass

        self._presence_thread = threading.Thread(
            target=report,
            daemon=True,
            name="webdb-client-presence",
        )
        self._presence_thread.start()

    def _stop_presence_reporting(self) -> None:
        stop_event = self._presence_stop_event
        self._presence_stop_event = None
        thread = self._presence_thread
        self._presence_thread = None
        if stop_event is not None:
            stop_event.set()
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=1)

    def _disconnect_webdb(self) -> None:
        self._auto_reconnect = False
        self._activate_offline_mode(show_dialog=False)
        with self._measurement_lock:
            self._remote_disconnect_requested = False
        self.append_log("WebDB disconnected. Offline mode is active.")

    def _apply_remote_disconnect(self, client: WebDbClient) -> None:
        if client is not self.client:
            return
        self._auto_reconnect = False
        self.password_edit.clear()
        self._activate_offline_mode(show_dialog=False)
        self.append_log("WebDB session ended by an administrator after the measurement finished.")
        QMessageBox.information(
            self, "WebDB session ended",
            "An administrator disconnected this THRUST-measure session. "
            "The current measurement has finished. Sign in again to reconnect.",
        )

    def _check_webdb_catalogue(self) -> None:
        if self._measurement_active or self._upload_in_progress:
            return
        client = self.client
        if client is None or self.offline_mode:
            if (self._auto_reconnect and not self._reconnect_in_flight
                    and self.username_edit.text() and self.password_edit.text()):
                self._reconnect_in_flight = True
                generation = self._catalogue_generation
                url = self.server_edit.text().strip() or DEFAULT_WEBDB_URL
                username, password = self.username_edit.text(), self.password_edit.text()

                def reconnect() -> None:
                    replacement = WebDbClient(url, timeout=8)
                    try:
                        if self._measurement_active:
                            return
                        account = replacement.login(username, password)
                        if self._measurement_active:
                            return
                        tests = replacement.list_tests()
                        if self._measurement_active:
                            return
                        participants = replacement.list_participants() if replacement.role != "student" else None
                        self.reconnect_checked.emit(generation, replacement, (account, tests, participants), None)
                    except (WebDbError, KeyError, ValueError) as exc:
                        self.reconnect_checked.emit(generation, replacement, None, str(exc))

                threading.Thread(target=reconnect, daemon=True, name="webdb-reconnect").start()
            return
        if self._catalogue_check_in_flight:
            return
        self._catalogue_check_in_flight = True
        generation = self._catalogue_generation

        def fetch() -> None:
            try:
                if self._measurement_active:
                    return
                tests = client.list_tests()
                if self._measurement_active:
                    return
                participants = client.list_participants() if client.role != "student" else None
                self.catalogue_checked.emit(generation, client, (tests, participants), None)
            except (WebDbError, KeyError, ValueError) as exc:
                self.catalogue_checked.emit(generation, client, None, str(exc))

        threading.Thread(target=fetch, daemon=True, name="webdb-catalogue").start()

    def _apply_reconnect_check(self, generation: int, client: WebDbClient, result: object, error: object) -> None:
        if generation != self._catalogue_generation or not self._auto_reconnect or not self.offline_mode:
            return
        self._reconnect_in_flight = False
        if error is not None:
            self.append_log(f"WebDB reconnection failed: {error}")
            return
        account, tests, participants = result
        self.client = client
        with self._measurement_lock:
            self._remote_disconnect_requested = False
        self._catalogue_generation += 1
        self._catalogue_connection_ok = True
        self.offline_mode = False
        self.config_source_combo.setCurrentIndex(0)
        self.participant_combo.clear()
        if client.role == "student":
            participant_id = account.get("participant_id")
            self.participant_combo.addItem(str(account.get("participant_code") or participant_id or "STUDENT"), participant_id)
            self.participant_combo.setEditable(False)
            self.participant_combo.setEnabled(False)
        else:
            for participant in participants:
                self.participant_combo.addItem(participant["participant_code"], participant["id"])
            self.participant_combo.setEditable(True)
            self.participant_combo.setEnabled(bool(participants))
        self.available_tests = [test for test in tests if test.get("is_active", False)]
        self._refresh_test_choices()
        self._sync_selection_labels()
        self.connection_status.setText(f"● WebDB CONNECTED · {account.get('participant_code') if client.role == 'student' else account.get('username', '')}")
        self._set_connection_state("connected")
        self._refresh_connection_action()
        self._update_selection_mode_controls()
        if self.advanced_dialog is not None:
            self.advanced_dialog.set_offline_visible(False)
        self.append_log("WebDB reconnected; participants and tests refreshed.")
        self._update_run_availability()
        self._start_presence_reporting()

    def _apply_catalogue_check(self, generation: int, client: WebDbClient, result: object, error: object) -> None:
        if generation != self._catalogue_generation or client is not self.client or self.offline_mode:
            return
        self._catalogue_check_in_flight = False
        if error is not None:
            self._catalogue_connection_ok = False
            self._set_connection_state("warning")
            self.connection_status.setText("● WebDB UNREACHABLE · retrying")
            self.append_log(f"WebDB periodic check failed: {error}")
            self._update_run_availability()
            return
        self._catalogue_connection_ok = True
        self._set_connection_state("connected")
        identity = (client.account or {}).get("participant_code") if client.role == "student" else (client.account or {}).get("username", "")
        self.connection_status.setText(f"● WebDB CONNECTED · {identity}")
        tests, participants = result
        active = [test for test in tests if test.get("is_active", False)]
        if participants is not None:
            before = [(self.participant_combo.itemData(i), self.participant_combo.itemText(i))
                      for i in range(self.participant_combo.count())]
            after = [(participant["id"], participant["participant_code"]) for participant in participants]
            if before != after:
                selected_id = self.participant_combo.currentData()
                selected_text = self.participant_combo.currentText().strip()
                self.participant_combo.blockSignals(True)
                self.participant_combo.clear()
                for participant_id, code in after:
                    self.participant_combo.addItem(code, participant_id)
                match = self.participant_combo.findData(selected_id)
                if match >= 0:
                    self.participant_combo.setCurrentIndex(match)
                elif selected_text and not selected_id:
                    self.participant_combo.setCurrentText(selected_text)
                else:
                    self.participant_combo.setCurrentIndex(-1)
                self.participant_combo.blockSignals(False)
                self.append_log("Participant list updated from WebDB.")
        if active != self.available_tests:
            self.available_tests = active
            self._refresh_test_choices()
            self.append_log("Test versions updated from WebDB.")
        self._sync_selection_labels()
        self._update_run_availability()

    def _offline_manifest(self, mode: str = "SCOPE") -> dict[str, Any]:
        is_simple = mode.upper() == "SIMPLE"
        return {
            "test": {
                "id": "",
                "test_code": "LOCAL_SIMPLE" if is_simple else "LOCAL_SCOPE",
                "name": "Local offline SimPLE test" if is_simple else "Local offline SCoPE test",
                "version": "local",
                "analysis_profile": "SIMPLE_FLIGHT_V1" if is_simple else "SCOPE_STEP_RESPONSE_V1",
                "configuration": SimpleConfig().to_dict() if is_simple else {},
            }
        }

    def _activate_offline_mode(self, show_dialog: bool, error: str = "") -> None:
        self._stop_presence_reporting()
        self._catalogue_generation += 1
        self._catalogue_check_in_flight = False
        self._reconnect_in_flight = False
        self.offline_mode = True
        self._catalogue_connection_ok = False
        self.client = None
        self.current_manifest = None
        self.config_source_combo.setCurrentIndex(1)

        self.participant_combo.clear()
        self.participant_combo.addItem("LOCAL")
        self.participant_combo.setCurrentText("LOCAL")
        self.participant_combo.setEnabled(True)
        self._sync_selection_labels()

        self.available_tests = [
            self._offline_manifest("SCOPE")["test"],
            self._offline_manifest("SIMPLE")["test"],
        ]
        self._refresh_test_choices()

        self.connection_status.setText("● WebDB DISCONNECTED · Offline mode")
        self._set_connection_state("warning")
        self._refresh_connection_action()
        self._update_selection_mode_controls()
        if self.advanced_dialog is not None:
            self.advanced_dialog.set_offline_visible(True)
        self._update_run_availability()
        if show_dialog:
            QMessageBox.warning(
                self,
                "WebDB unavailable",
                f"THRUST switched to offline mode automatically.\n\n{error}",
            )
            self._open_advanced()

    def _refresh_test_choices(self, _index: int = -1) -> None:
        mode = str(self.program_selector.currentData() or "SCOPE")
        previous = self.test_combo.currentData()
        previous_id = previous.get("id") if isinstance(previous, dict) else None
        matching = [
            test for test in self.available_tests
            if str(test.get("analysis_profile", "")).upper().startswith(mode)
        ]
        self.test_combo.blockSignals(True)
        self.test_combo.clear()
        for test in matching:
            self.test_combo.addItem(f'{test["name"]} · v{test["version"]}', test)
        saved_index = next(
            (i for i, test in enumerate(matching) if test.get("id") == previous_id),
            0,
        )
        self.test_combo.setCurrentIndex(saved_index if matching else -1)
        self.test_combo.setPlaceholderText("No available versions for this mode")
        self.test_combo.setEnabled(bool(matching))
        self.test_combo.blockSignals(False)
        self._sync_selection_labels()
        for button_mode, button in self.mode_buttons.items():
            button.setChecked(button_mode == mode)
        self.axis_bar_stacks["RESET"].setCurrentWidget(
            self.joystick_bars["RESET"] if mode == "SIMPLE" else self.axis_placeholders["RESET"]
        )
        self.current_manifest = None
        if matching:
            self._load_selected_test()
        else:
            self.append_log(f"No active {mode} test version is available.")
        self._update_run_availability()

    def _set_connection_state(self, state: str) -> None:
        self.connection_status.setProperty("connectionState", state)
        self.connection_status.style().unpolish(self.connection_status)
        self.connection_status.style().polish(self.connection_status)

    def _load_selected_test(self, _index: int = -1) -> None:
        if self.test_combo.currentIndex() < 0:
            return
        if self.offline_mode:
            selected = self.test_combo.currentData()
            if not isinstance(selected, dict):
                self.current_manifest = None
                self.run_button.setEnabled(False)
                return
            self.current_manifest = {"test": selected}
            is_simple = str(selected.get("analysis_profile", "")).upper().startswith("SIMPLE")
            if is_simple:
                self.simple_page.load_simple_config(SimpleConfig.from_dict(selected.get("configuration")))
            else:
                self.scope_page.load_scope_config(ScopeConfig())
            if self.advanced_dialog is not None:
                self.advanced_dialog.set_measurement_mode(is_simple)
            self._update_run_availability()
            return
        if self.client is None:
            return

        selected = self.test_combo.currentData()
        if not isinstance(selected, dict):
            self.run_button.setEnabled(False)
            return

        try:
            self.current_manifest = self.client.get_test_configuration(selected["id"])
            test = self.current_manifest["test"]
            self._apply_web_configuration(test)
            self._update_run_availability()
            self.append_log(f'Loaded test manifest: {test["test_code"]} v{test["version"]}')
        except (WebDbError, KeyError, TypeError, ValueError) as exc:
            self.current_manifest = None
            self.run_button.setEnabled(False)
            self.append_log(f"Test configuration failed: {exc}")

    def _configuration_from_web_test(self, test: dict[str, Any]) -> ScopeConfig:
        source = test.get("configuration")
        if not isinstance(source, dict):
            raise ValueError("Test configuration must be a JSON object.")

        config_data = dict(source)
        for obsolete_key in (
            "user", "profile_name", "expert_mode", "output_root", "use_dated_subfolders",
            "joystick_index", "break_axis", "reset_axis", "axis_map", "deadzone",
        ):
            config_data.pop(obsolete_key, None)

        legacy_mapping = {"sampling_hz": "fps", "timeout_s": "action_timeout_s"}
        for source_key, target_key in legacy_mapping.items():
            if source_key in config_data and target_key not in config_data:
                config_data[target_key] = config_data[source_key]

        visual = config_data.pop("visual", None)
        if isinstance(visual, dict):
            visual_mapping = {
                "screen_bg": "screen_background",
                "gimbal_bg": "gimbal_background",
                "grid": "grid_color",
                "label": "label_color",
                "prompt": "prompt_color",
            }
            for source_key, target_key in visual_mapping.items():
                if source_key in visual and target_key not in config_data:
                    config_data[target_key] = visual[source_key]
            for key in (
                "stick_outline", "stick_fill", "zone_idle_outline", "zone_idle_fill",
                "zone_ok_outline", "zone_ok_fill",
            ):
                if key in visual and key not in config_data:
                    config_data[key] = visual[key]

        known_fields = {item.name for item in fields(ScopeConfig)}
        config_data = {key: value for key, value in config_data.items() if key in known_fields}
        config = ScopeConfig.from_dict(config_data)
        config.validate()
        return config

    def _simple_configuration_from_web_test(self, test: dict[str, Any]) -> SimpleConfig:
        source = test.get("configuration")
        if not isinstance(source, dict):
            raise ValueError("SimPLE configuration must be a JSON object.")
        return SimpleConfig.from_dict(source)

    def _apply_web_configuration(self, test: dict[str, Any]) -> None:
        is_simple = str(test.get("analysis_profile", "")).upper().startswith("SIMPLE")
        if is_simple:
            self.simple_page.load_simple_config(self._simple_configuration_from_web_test(test))
        else:
            config = self._configuration_from_web_test(test)
            self.scope_page.apply_scope_config(config, self.common_page)
        if self.advanced_dialog is not None:
            self.advanced_dialog.set_measurement_mode(is_simple)

    def _open_advanced(self) -> None:
        if not self.offline_mode:
            return
        if self.advanced_dialog is None:
            self.advanced_dialog = AdvancedSettingsDialog(self.common_page, self.scope_page, self.simple_page, self)
        self.advanced_dialog.set_offline_visible(self.offline_mode)
        if self.current_manifest:
            self.advanced_dialog.set_measurement_mode(str(self.current_manifest["test"].get("analysis_profile", "")).upper().startswith("SIMPLE"))
        self.advanced_dialog.show()
        self.advanced_dialog.raise_()
        self.advanced_dialog.activateWindow()

    def _begin_measurement_upload(self, payload: dict[str, Any]) -> None:
        if not payload.get("queue_id"):
            payload["queue_id"] = self._upload_queue.enqueue(payload)
            self._queued_upload_count = len(self._upload_queue.pending())
        self._pending_upload_payload = payload
        self._upload_in_progress = True
        if self._upload_dialog is None:
            self._upload_dialog = MeasurementUploadDialog(self)
            self._upload_dialog.retry_requested.connect(self._retry_measurement_upload)
            self._upload_dialog.disconnect_requested.connect(self._disconnect_from_details)
        else:
            self._upload_dialog.begin_new_upload()
        self._upload_dialog.set_progress(
            "Preparing measurement upload", None, None,
            "The measurement remains saved on this computer while it is processed and uploaded.",
        )
        self._upload_activity_stage = "Preparing measurement"
        self._update_run_availability()
        self._start_measurement_upload_worker(payload)

    def _show_measurement_upload(self) -> None:
        if self._upload_dialog is None:
            self._upload_dialog = MeasurementUploadDialog(self)
            self._upload_dialog.retry_requested.connect(self._retry_measurement_upload)
            self._upload_dialog.disconnect_requested.connect(self._disconnect_from_details)
            if self._pending_upload_payload is not None:
                self._upload_dialog.show_waiting_for_connection(
                    str(self._pending_upload_payload.get("participant_code", "")),
                    str(self._pending_upload_payload.get("test_label", "")),
                )
            else:
                self._upload_dialog.show_idle(len(self._upload_queue.pending()))
        self._refresh_connection_action()
        self._upload_dialog.set_connection_controls(
            not self.offline_mode and self.client is not None,
            not self._measurement_active and not self._upload_in_progress,
        )
        self._upload_dialog.show()
        self._upload_dialog.raise_()
        self._upload_dialog.activateWindow()

    def _disconnect_from_details(self) -> None:
        if self._measurement_active or self._upload_in_progress:
            return
        if self._upload_dialog is not None:
            self._upload_dialog.hide()
        self._disconnect_webdb()

    def _retry_measurement_upload(self) -> None:
        if self._pending_upload_payload is None:
            return
        if self.client is not None and not self.offline_mode:
            self._pending_upload_payload["client"] = self.client
        self._upload_in_progress = True
        self._upload_activity_stage = "Retrying upload"
        self._upload_dialog.prepare_retry()
        self._update_run_availability()
        self._start_measurement_upload_worker(self._pending_upload_payload)

    def _resume_pending_upload(self) -> None:
        payload = self._pending_upload_payload
        if payload is None or self.client is None or self.offline_mode or self._upload_in_progress:
            return
        archive = Path(str(payload.get("raw_log_path", "")))
        if not archive.is_file():
            compressed_fallback = archive.with_name(archive.name + ".gz")
            if compressed_fallback.is_file():
                archive = compressed_fallback
                payload["raw_log_path"] = str(archive)
                queue_id = payload.get("queue_id")
                if queue_id:
                    self._upload_queue.update(str(queue_id), raw_log_path=str(archive))
            else:
                self._measurement_upload_failed(f"Queued measurement file is missing: {archive}", str(archive))
                return
        payload["client"] = self.client
        self._upload_in_progress = True
        self._upload_activity_stage = "Resuming pending upload"
        if self._upload_dialog is None:
            self._upload_dialog = MeasurementUploadDialog(self)
            self._upload_dialog.retry_requested.connect(self._retry_measurement_upload)
            self._upload_dialog.disconnect_requested.connect(self._disconnect_from_details)
        self._upload_dialog.begin_new_upload()
        self._upload_dialog.set_progress(
            "Resuming pending upload", None, None,
            "A saved measurement was found. Uploading it now that WebDB is connected.",
        )
        self._start_measurement_upload_worker(payload)

    def _retry_queued_upload_if_connected(self) -> None:
        if (self._pending_upload_payload is None or self._upload_in_progress
                or self.client is None or self.offline_mode):
            return
        self._retry_measurement_upload()

    def _start_measurement_upload_worker(self, payload: dict[str, Any]) -> None:
        worker = MeasurementUploadWorker(payload)
        self._upload_worker = worker
        worker.progress.connect(self._upload_dialog.set_progress)
        worker.progress.connect(self._update_activity_progress)
        worker.succeeded.connect(self._measurement_upload_succeeded)
        worker.failed.connect(self._measurement_upload_failed)
        worker.finished.connect(self._measurement_upload_worker_finished)
        thread = threading.Thread(target=worker.run, daemon=True, name="measurement-upload")
        self._upload_thread = thread
        thread.start()

    def _measurement_upload_succeeded(self, uploaded: object, archive_path: str, graph_path: object) -> None:
        result = uploaded if isinstance(uploaded, dict) else {}
        measurement_id = str(result.get("id", "unknown"))
        self.append_log(
            f"Measurement uploaded: {measurement_id} "
            f"({result.get('raw_size_bytes', 0)} bytes, SHA-256 {result.get('raw_sha256', '')})."
        )
        self.append_log(f"Measurement finished and archived in WebDB. Local archive: {archive_path}")
        if graph_path:
            graph = Path(str(graph_path))
            self.append_log(f"Local response graph saved: {graph}")
            self._open_local_file(graph)
        queue_id = self._pending_upload_payload.get("queue_id") if self._pending_upload_payload else None
        if queue_id:
            self._upload_queue.remove(str(queue_id))
        self._upload_retry_attempt = 0
        if self._upload_dialog is not None:
            self._upload_dialog.show_success(measurement_id, archive_path, self._pending_upload_payload)
        remaining = self._upload_queue.pending()
        self._pending_upload_payload = remaining[0] if remaining else None
        self._queued_upload_count = len(remaining)
        self._upload_in_progress = False
        self._upload_activity_stage = ""
        if self._pending_upload_payload is not None:
            QTimer.singleShot(2500, self._resume_pending_upload)
        self._update_run_availability()
        QTimer.singleShot(0, self._check_webdb_catalogue)

    def _measurement_upload_failed(self, message: str, archive_path: str) -> None:
        self.append_log(f"Measurement upload failed: {message}")
        self.append_log(f"Measurement file remains available locally: {archive_path}")
        if self._pending_upload_payload is not None:
            self._pending_upload_payload["raw_log_path"] = archive_path
            queue_id = self._pending_upload_payload.get("queue_id")
            if queue_id:
                self._upload_queue.update(
                    str(queue_id), raw_log_path=archive_path, queue_status="failed", last_error=message
                )
        if self._upload_dialog is None:
            self._upload_dialog = MeasurementUploadDialog(self)
            self._upload_dialog.retry_requested.connect(self._retry_measurement_upload)
            self._upload_dialog.disconnect_requested.connect(self._disconnect_from_details)
        self._upload_dialog.show_failure(message, archive_path, self._pending_upload_payload)
        self._upload_in_progress = False
        self._upload_activity_stage = "Upload pending"
        self._update_run_availability()
        if self.client is not None and not self.offline_mode and Path(archive_path).is_file():
            delay_seconds = min(30 * (2 ** self._upload_retry_attempt), 300)
            self._upload_retry_attempt += 1
            QTimer.singleShot(delay_seconds * 1000, self._retry_queued_upload_if_connected)

    def _measurement_upload_worker_finished(self) -> None:
        self._upload_worker = None
        self._upload_thread = None

    def _run_selected_measurement(self) -> None:
        if self.current_manifest is None:
            return
        with self._measurement_lock:
            if self._remote_disconnect_requested:
                return
            self._measurement_active = True
        self._upload_activity_stage = "Measurement running"
        self._refresh_activity_status()

        participant_code = self.participant_combo.currentText().strip() or "LOCAL"
        test = self.current_manifest["test"]
        profile_name = f'{test["test_code"]}_v{test["version"]}'
        is_simple = (
            str(test.get("analysis_profile", "")).upper().startswith("SIMPLE")
            or str(test.get("test_code", "")).upper().startswith("SIMPLE")
        )

        create_local_graph = self.local_graphs_checkbox.isChecked()
        try:
            if not self.common_page.joystick_active:
                message = "Cannot start measurement: no joystick is connected."
                self.append_log(message)
                QMessageBox.warning(self, "Joystick unavailable", message)
                return

            selected_participant_id = self.participant_combo.currentData()
            self._presence_participant_id = str(selected_participant_id) if selected_participant_id else None
            selected_test_id = test.get("id")
            self._presence_test_definition_id = str(selected_test_id) if selected_test_id else None
            self.catalogue_timer.stop()
            runtime = self.common_page.export_common_dict()
            runtime["debug_output"] = True
            runtime["joystick_name"] = self.joystick_selector.currentText().strip()
            selected_joystick = self.joystick_selector.currentData()
            runtime["joystick_index"] = int(selected_joystick) if isinstance(selected_joystick, int) and selected_joystick >= 0 else 0
            if is_simple:
                config = (
                    self.simple_page.build_simple_config()
                    if self.offline_mode
                    else self._simple_configuration_from_web_test(test)
                )
                if config.background_image_id:
                    if self.client is None:
                        raise RuntimeError("The selected WebDB background requires a connection.")
                    runtime["background_image_path"] = str(
                        self.client.download_background(config.background_image_id)
                    )
                    self.append_log(f"Loaded SimPLE background {config.background_image_id}.")
                self.append_log(f"Starting SimPLE {test['test_code']} v{test['version']} for participant {participant_code}.")
                session = run_simple(
                    config, runtime, participant=participant_code, profile_name=profile_name,
                    log_callback=self.append_log,
                    state_callback=self.led_controller.set_state if self.led_controller else None,
                    compress_output=self.offline_mode,
                )
                if getattr(session, "aborted", False) and not getattr(session, "samples", 0):
                    self.append_log("Measurement cancelled before recording.")
                    return
                raw_path = session.logfile_path
                if not raw_path:
                    raise RuntimeError("SimPLE did not create a raw log.")
            else:
                from thrust.runners.scope_runner import run_scope
                config = (
                    self.scope_page.build_scope_config(self.common_page)
                    if self.offline_mode
                    else self._configuration_from_web_test(test)
                )
                # Joystick channel assignments and break/reset axes are local hardware settings,
                # so they must override the test definition for both online and offline runs.
                config.axis_map = dict(runtime["axis_map"])
                config.deadzone = list(runtime["deadzone"])
                config.break_axis = int(runtime["break_axis"])
                config.reset_axis = int(runtime["reset_axis"])
                config.user = participant_code
                config.profile_name = profile_name
                config.debug_output = True
                config.validate()
                self.append_log(
                    f"Starting {test['test_code']} v{test['version']} for participant {participant_code}."
                )
                session = run_scope(config, log_callback=self.append_log,
                                    state_callback=self.led_controller.set_state if self.led_controller else None,
                                    compress_output=self.offline_mode)
                if getattr(session, "aborted", False) and not getattr(session, "samples", 0):
                    self.append_log("Measurement cancelled before recording.")
                    return
                raw_path = session.logfile_path
                if not raw_path:
                    raise RuntimeError("Measurement did not create a raw log.")

            if not self.offline_mode:
                participant_id = self.participant_combo.currentData()
                if not participant_id:
                    raise RuntimeError("Participant has no valid WebDB ID.")
                if self.client is None:
                    raise RuntimeError("WebDB client is not connected.")
                session_parameters = config.to_dict()
                for local_only in ("user", "output_root", "profile_name", "fullscreen", "topmost", "debug_output"):
                    session_parameters.pop(local_only, None)
                upload_payload = {
                    "client": self.client,
                    "participant_id": str(participant_id),
                    "participant_code": participant_code,
                    "test_definition_id": str(test["id"]),
                    "test": dict(test),
                    "started_at": session.started_at,
                    "raw_log_path": raw_path,
                    "is_simple": is_simple,
                    "session_parameters": session_parameters,
                    "runtime": dict(runtime),
                    "session_summary": {
                        "completed": getattr(session, "total_completed", 0),
                        "mistakes": getattr(session, "total_mistakes", 0),
                        "attempts": getattr(session, "total_attempts", 0),
                        "timing_schedule_s": getattr(session, "timing_schedule_s", None),
                        "timing_seed": getattr(session, "timing_seed", None),
                        "timing_schedule_version": getattr(session, "timing_schedule_version", 1),
                        "crashes": getattr(session, "crash_count", 0),
                        "aborted": getattr(session, "aborted", False),
                        "abort_reason": getattr(session, "abort_reason", ""),
                    },
                    "status": "incomplete" if getattr(session, "aborted", False) else "recorded",
                    "create_local_graph": create_local_graph,
                    "test_label": f"{test.get('test_code', 'Test')} v{test.get('version', '')}",
                }
                self.append_log("Measurement finished. Compressing and uploading it to WebDB in the background.")
                self._begin_measurement_upload(upload_payload)
                return

            self._upload_activity_stage = "Analyzing measurement"
            self._refresh_activity_status()
            QApplication.processEvents()
            if is_simple:
                analysis = analyze_simple_log(raw_path, started_at=session.started_at)
            else:
                analysis = analyze_scope_log(raw_path)

            session_parameters = config.to_dict()
            for local_only in ("user", "output_root", "profile_name", "fullscreen", "topmost", "debug_output"):
                session_parameters.pop(local_only, None)
            analysis = build_analysis_artifact(
                raw_path,
                analysis,
                started_at=session.started_at,
                test=test,
                parameters=session_parameters,
                runtime=runtime,
                session_summary={
                    "completed": getattr(session, "total_completed", 0),
                    "mistakes": getattr(session, "total_mistakes", 0),
                    "attempts": getattr(session, "total_attempts", 0),
                    "timing_schedule_s": getattr(session, "timing_schedule_s", None),
                    "timing_seed": getattr(session, "timing_seed", None),
                    "timing_schedule_version": getattr(session, "timing_schedule_version", 1),
                    "crashes": getattr(session, "crash_count", 0),
                    "aborted": getattr(session, "aborted", False),
                    "abort_reason": getattr(session, "abort_reason", ""),
                },
            )
            self._upload_activity_stage = "Saving local results"
            self._refresh_activity_status()
            QApplication.processEvents()
            analysis_path = save_analysis_artifact(raw_path, analysis)
            self.append_log(f"Measurement analysis saved: {analysis_path}")
            if create_local_graph:
                try:
                    graph_path = save_local_response_graph(raw_path, analysis, participant_id=participant_code)
                    self.append_log(f"Local response graph saved: {graph_path}")
                    self._open_local_file(graph_path)
                except Exception as graph_error:
                    self.append_log(f"Local response graph could not be created: {graph_error}")

            if self.offline_mode:
                self.append_log(f"Offline measurement finished. Raw log: {raw_path}")
                message = (
                    f"Participant: {participant_code}\n"
                    f"Test: {profile_name}\n"
                    f"Started: {session.started_at}\n"
                    f"Completed tasks: {getattr(session, 'total_completed', 0)}\n"
                    f"Mistakes: {getattr(session, 'total_mistakes', 0)}\n"
                    f"Status: {'incomplete' if getattr(session, 'aborted', False) else 'completed'}\n\n"
                    f"Local measurement file:\n{raw_path}\n\n"
                    f"Analysis file:\n{analysis_path}"
                )
                QMessageBox.information(self, "Measurement receipt", message)
                return

        except Exception as exc:
            self.append_log(f"Measurement failed: {type(exc).__name__}: {exc}")
            QMessageBox.critical(self, "Measurement failed", f"{type(exc).__name__}: {exc}")
        finally:
            if self._measurement_active:
                with self._measurement_lock:
                    self._measurement_active = False
                if not self._upload_in_progress:
                    self._upload_activity_stage = ""
                self._update_run_availability()
                self._presence_participant_id = None
                self._presence_test_definition_id = None
                # Ignore a catalogue result started just before the session.
                self._catalogue_generation += 1
                self._catalogue_check_in_flight = False
                self._reconnect_in_flight = False
                self.catalogue_timer.start(5_000)

    def _open_local_file(self, path: Path) -> None:
        try:
            resolved = path.resolve()
            if not resolved.is_file():
                self.append_log(f"PDF was not found: {resolved}")
                return
            opened = QDesktopServices.openUrl(QUrl.fromLocalFile(str(resolved)))
            if opened:
                self.append_log(f"Opened PDF with the system default viewer: {resolved}")
            else:
                self.append_log(f"Could not open PDF automatically. Open it manually: {resolved}")
        except Exception as exc:
            self.append_log(f"Could not open PDF automatically: {exc}. File: {path}")

    def append_log(self, message: str) -> None:
        now = datetime.now().astimezone()
        entry = f"[{now:%Y-%m-%d %H:%M:%S}] {message}"
        self.log_history.append(entry)
        if self.log_view is not None:
            self.log_view.appendPlainText(entry)
        compact = " ".join(message.split())
        if len(compact) > 150:
            compact = compact[:147] + "…"
        self.footer_log_label.setText(f"{now:%H:%M:%S} · {compact}")
        self.footer_log_label.setToolTip(entry)

    def _open_logs(self) -> None:
        if self.log_dialog is None:
            dialog = QDialog(self)
            dialog.setWindowTitle("THRUST · detailed logs")
            dialog.resize(900, 600)
            layout = QVBoxLayout(dialog)
            self.log_view = QPlainTextEdit()
            self.log_view.setObjectName("detailedLog")
            self.log_view.setReadOnly(True)
            self.log_view.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
            layout.addWidget(self.log_view)
            close_button = QPushButton("Close")
            close_button.clicked.connect(dialog.close)
            layout.addWidget(close_button)
            self.log_dialog = dialog
            for entry in self.log_history:
                self.log_view.appendPlainText(entry)
        self.log_dialog.show()
        self.log_dialog.raise_()
        self.log_dialog.activateWindow()

    def _open_legacy_import(self) -> None:
        dialog = LegacyImportDialog(self.server_edit.text().strip(), self.username_edit.text(), self)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.show()

    def _update_selection_mode_controls(self) -> None:
        offline = self.offline_mode
        self.test_button.setVisible(not offline)
        self.local_settings_button.setVisible(offline)
        self.test_row_label.setText("Local settings:" if offline else "Test version:")



