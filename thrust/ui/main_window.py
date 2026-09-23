from __future__ import annotations

import csv
import os
import sys
from dataclasses import fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from scope.scope_config import ScopeConfig
from simple.simple_config import SimpleConfig
from thrust.analysis.scope_log import analyze_scope_log
from thrust.analysis.simple_log import analyze_simple_log, save_step_graph, write_step_response
from thrust.paths import ASSETS_DIR, SIMPLE_OUTPUT_DIR
from thrust.runners.simple_runner import run_simple
from thrust.ui.pages.common_settings_page import CommonSettingsPage
from thrust.ui.pages.scope_settings_page import ScopeSettingsPage
from thrust.ui.pages.simple_settings_page import SimpleSettingsPage
from thrust.webdb_client import WebDbClient, WebDbError


DEFAULT_WEBDB_URL = "http://thrust.webdb"


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
        if self.tabs.isVisible():
            self.tabs.setCurrentIndex(self.simple_tab_index if is_simple else self.scope_tab_index)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("THRUST · measurement client")
        self.resize(1200, 820)

        self.client: WebDbClient | None = None
        self.current_manifest: dict[str, Any] | None = None
        self.offline_mode = True

        self.common_page = CommonSettingsPage()
        self.scope_page = ScopeSettingsPage()
        self.simple_page = SimpleSettingsPage()
        self.advanced_dialog: AdvancedSettingsDialog | None = None
        self.common_page.joystick_status_changed.connect(self._set_joystick_status)
        self.common_page.joystick_values_changed.connect(self._update_joystick_feedback)
        self.joystick_bars: dict[str, QProgressBar] = {}
        self.joystick_device_names: list[str] = []

        self.server_edit = QLineEdit(DEFAULT_WEBDB_URL)
        self.username_edit = QLineEdit()
        self.password_edit = QLineEdit()
        self.config_source_combo = QComboBox()
        self.config_source_combo.addItems(["WebDB", "Local offline"])
        self.config_source_combo.setVisible(False)

        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(self._open_login)
        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.clicked.connect(self._disconnect_webdb)
        self.disconnect_button.setVisible(False)

        self.connection_status = QLabel("● WebDB DISCONNECTED · Offline mode")
        self.connection_status.setStyleSheet("font-weight: 700; color: #ed6262;")

        self.participant_combo = QComboBox()
        self.participant_combo.setEditable(True)
        self.participant_combo.setPlaceholderText("Participant ID")
        self.participant_combo.setEnabled(False)

        self.test_combo = QComboBox()
        self.test_combo.setPlaceholderText("Connect to load test versions")
        self.test_combo.setEnabled(False)
        self.test_combo.currentIndexChanged.connect(self._load_selected_test)

        selection_group = QGroupBox("Test selection")
        selection_form = QFormLayout(selection_group)
        selection_form.addRow("Participant ID:", self.participant_combo)
        selection_form.addRow("Test version:", self.test_combo)

        joystick_group = QGroupBox("Joystick link")
        joystick_layout = QVBoxLayout(joystick_group)
        joystick_row = QHBoxLayout()
        self.joystick_selector = QComboBox()
        self.joystick_selector.setPlaceholderText("Select joystick")
        self.joystick_selector.currentIndexChanged.connect(self._select_joystick)
        joystick_row.addWidget(QLabel("Device:"))
        joystick_row.addWidget(self.joystick_selector, 1)
        joystick_layout.addLayout(joystick_row)

        joystick_status_row = QHBoxLayout()
        self.joystick_led = QLabel("● DISCONNECTED")
        self.joystick_led.setObjectName("joystickLed")
        self.joystick_status_text = QLabel("Searching for joystick…")
        joystick_status_row.addWidget(self.joystick_led)
        joystick_status_row.addWidget(self.joystick_status_text, 1)
        joystick_layout.addLayout(joystick_status_row)

        feedback_grid = QGridLayout()
        for row, name in enumerate(("AILE", "ELEV", "THRO", "RUDD")):
            label = QLabel(name)
            bar = QProgressBar()
            bar.setRange(-100, 100)
            bar.setValue(0)
            bar.setTextVisible(False)
            bar.setFixedHeight(8)
            bar.setObjectName("miniAxis")
            self.joystick_bars[name] = bar
            feedback_grid.addWidget(label, row, 0)
            feedback_grid.addWidget(bar, row, 1)
        joystick_layout.addLayout(feedback_grid)

        self.run_button = QPushButton("Start measurement")
        self.run_button.setMinimumHeight(44)
        self.run_button.clicked.connect(self._run_selected_measurement)

        self.advanced_button = QPushButton("Settings")
        self.advanced_button.clicked.connect(self._open_advanced)

        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMinimumHeight(90)
        self.log_output.setMaximumHeight(150)

        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(10)

        title = QLabel("THRUST")
        title.setStyleSheet("font-size: 30px; font-weight: 800; letter-spacing: 2px; color: #eaf5ff;")
        subtitle = QLabel("UAV CONTROL PERFORMANCE · MEASUREMENT CENTER")
        subtitle.setStyleSheet("color: #7892aa; letter-spacing: 1px;")
        title_row = QHBoxLayout()
        title_block = QVBoxLayout()
        title_block.addWidget(title)
        title_block.addWidget(subtitle)
        title_row.addLayout(title_block)
        title_row.addStretch()
        for filename, label in (("scope_logo.png", "SCoPE"), ("simple_logo.png", "SimPLE")):
            logo_path = ASSETS_DIR / filename
            if logo_path.is_file():
                logo = QLabel()
                logo.setToolTip(label)
                logo.setPixmap(QPixmap(str(logo_path)).scaled(124, 48, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                title_row.addWidget(logo)

        session_actions = QWidget()
        session_actions_layout = QHBoxLayout(session_actions)
        session_actions_layout.setContentsMargins(0, 0, 0, 0)
        session_actions_layout.addWidget(self.connection_status)
        session_actions_layout.addStretch()
        session_actions_layout.addWidget(self.connect_button)
        session_actions_layout.addWidget(self.disconnect_button)
        session_actions_layout.addWidget(self.advanced_button)

        session_ribbon = QGroupBox("Measurement session")
        session_ribbon_layout = QHBoxLayout(session_ribbon)
        session_ribbon_layout.setContentsMargins(10, 4, 10, 4)
        session_ribbon_layout.addWidget(session_actions)

        left = QVBoxLayout()
        left.setSpacing(10)
        left.addWidget(selection_group)
        left.addWidget(self.run_button)
        right = QVBoxLayout()
        right.setSpacing(10)
        right.addWidget(joystick_group)
        right.addStretch()

        columns = QGridLayout()
        columns.setHorizontalSpacing(12)
        columns.setVerticalSpacing(8)
        columns.addLayout(left, 0, 0)
        columns.addLayout(right, 0, 1)
        columns.setColumnStretch(0, 1)
        columns.setColumnStretch(1, 1)

        root.addLayout(title_row)
        root.addWidget(session_ribbon)
        root.addLayout(columns, 1)
        root.addWidget(QLabel("Session log"))
        root.addWidget(self.log_output)

        self.setCentralWidget(central)
        self.setStyleSheet("""
            QMainWindow { background: #111820; color: #e7edf2; }
            QGroupBox { border: 1px solid #344553; border-radius: 8px; margin-top: 10px; padding: 12px 10px 10px; font-weight: 600; }
            QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; color: #8fc7d8; }
            QPushButton { background: #203542; border: 1px solid #4c7180; border-radius: 5px; padding: 7px 12px; }
            QPushButton:hover { background: #2a4d5d; }
            QComboBox, QLineEdit { background: #19242d; border: 1px solid #405563; border-radius: 4px; padding: 5px; }
            QProgressBar#miniAxis { background: #1a2730; border: 1px solid #3b5661; border-radius: 3px; }
            QProgressBar#miniAxis::chunk { background: #4da6bd; border-radius: 2px; }
            QLabel#joystickLed { font-weight: 700; color: #e05252; }
        """)
        self._activate_offline_mode(show_dialog=False)
        self._refresh_joystick_selector()
        self.joystick_scan_timer = QTimer(self)
        self.joystick_scan_timer.timeout.connect(self._poll_joystick_devices)
        self.joystick_scan_timer.start(1000)
        QTimer.singleShot(0, self._auto_connect_joystick)

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

        self._update_run_availability(bool(devices))
        if not devices:
            if self.common_page.joystick_active:
                self.common_page.stop_joystick()
            self._set_joystick_status(False, "No joystick detected")
        elif not self.common_page.joystick_active:
            self._select_joystick(self.joystick_selector.currentIndex())

    def _update_run_availability(self, joystick_present: bool | None = None) -> None:
        connected = self.common_page.joystick_active if joystick_present is None else joystick_present
        self.run_button.setEnabled(bool(connected))

    def _poll_joystick_devices(self) -> None:
        self._refresh_joystick_selector()

    def _auto_connect_joystick(self) -> None:
        self._refresh_joystick_selector()

    def _select_joystick(self, index: int) -> None:
        device_index = self.joystick_selector.itemData(index)
        if device_index is None or int(device_index) < 0:
            self._set_joystick_status(False, "No joystick detected")
            return
        self.common_page.select_joystick(int(device_index), connect=True)

    def _set_joystick_status(self, connected: bool, status: str) -> None:
        self.joystick_led.setText("● CONNECTED" if connected else "● DISCONNECTED")
        self.joystick_led.setStyleSheet(
            "font-weight: 700; color: #52d18a;" if connected else "font-weight: 700; color: #ed6262;"
        )
        self.joystick_status_text.setText(status)
        if hasattr(self, "run_button"):
            self._update_run_availability(connected)

    def _update_joystick_feedback(self, values: object) -> None:
        if not isinstance(values, list):
            return
        for index, name in enumerate(("AILE", "ELEV", "THRO", "RUDD")):
            value = float(values[index]) if index < len(values) else 0.0
            self.joystick_bars[name].setValue(int(max(-1.0, min(1.0, value)) * 100))

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

    def _connect_webdb(self) -> None:
        try:
            self.client = WebDbClient(self.server_edit.text().strip() or DEFAULT_WEBDB_URL)
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

            self.test_combo.clear()
            for test in tests:
                if test.get("is_active", False):
                    self.test_combo.addItem(f'{test["name"]} · v{test["version"]}', test)

            self.offline_mode = False
            self.config_source_combo.setCurrentIndex(0)
            self.test_combo.setEnabled(bool(tests))
            identity = account.get("participant_code") if role == "student" else account.get("username", "")
            self.connection_status.setText(f"● WebDB CONNECTED · {identity}")
            self.connection_status.setStyleSheet("font-weight: 700; color: #52d18a;")
            self.connect_button.setVisible(False)
            self.disconnect_button.setVisible(True)
            self.advanced_button.setVisible(True)
            if self.advanced_dialog is not None:
                self.advanced_dialog.set_offline_visible(False)
            self.append_log(f"Loaded {len(tests)} active tests for {role or 'user'}.")
            self._load_selected_test()

        except (WebDbError, KeyError, ValueError) as exc:
            self.append_log(f"WebDB connection failed: {exc}")
            self._activate_offline_mode(show_dialog=True, error=str(exc))

    def _disconnect_webdb(self) -> None:
        self._activate_offline_mode(show_dialog=False)
        self.append_log("WebDB disconnected. Offline mode is active.")

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
        self.offline_mode = True
        self.client = None
        self.current_manifest = self._offline_manifest()
        self.config_source_combo.setCurrentIndex(1)

        self.participant_combo.clear()
        self.participant_combo.addItem("LOCAL")
        self.participant_combo.setCurrentText("LOCAL")
        self.participant_combo.setEnabled(True)

        self.test_combo.blockSignals(True)
        self.test_combo.clear()
        scope_test = self._offline_manifest("SCOPE")["test"]
        simple_test = self._offline_manifest("SIMPLE")["test"]
        self.test_combo.addItem("SCoPE · local offline", scope_test)
        self.test_combo.addItem("SimPLE · local offline", simple_test)
        self.test_combo.setCurrentIndex(0)
        self.test_combo.blockSignals(False)
        self.test_combo.setEnabled(True)
        self._load_selected_test(0)

        self.connection_status.setText("● WebDB DISCONNECTED · Offline mode")
        self.connection_status.setStyleSheet("color: #d6a35b;")
        self.connect_button.setVisible(True)
        self.disconnect_button.setVisible(False)
        self.advanced_button.setVisible(True)
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
            self.run_button.setEnabled(self.participant_combo.currentIndex() >= 0)
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
        if self.advanced_dialog is None:
            self.advanced_dialog = AdvancedSettingsDialog(self.common_page, self.scope_page, self.simple_page, self)
        self.advanced_dialog.set_offline_visible(self.offline_mode)
        if self.current_manifest:
            self.advanced_dialog.set_measurement_mode(str(self.current_manifest["test"].get("analysis_profile", "")).upper().startswith("SIMPLE"))
        self.advanced_dialog.show()
        self.advanced_dialog.raise_()
        self.advanced_dialog.activateWindow()

    def _run_selected_measurement(self) -> None:
        if self.current_manifest is None:
            return

        participant_code = self.participant_combo.currentText().strip() or "LOCAL"
        test = self.current_manifest["test"]
        profile_name = f'{test["test_code"]}_v{test["version"]}'
        is_simple = (
            str(test.get("analysis_profile", "")).upper().startswith("SIMPLE")
            or str(test.get("test_code", "")).upper().startswith("SIMPLE")
        )

        try:
            if not self.common_page.joystick_active:
                message = "Cannot start measurement: no joystick is connected."
                self.append_log(message)
                QMessageBox.warning(self, "Joystick unavailable", message)
                return

            runtime = self.common_page.export_common_dict()
            if is_simple:
                config = (
                    self.simple_page.build_simple_config()
                    if self.offline_mode
                    else self._simple_configuration_from_web_test(test)
                )
                self.append_log(f"Starting SimPLE {test['test_code']} v{test['version']} for participant {participant_code}.")
                session = run_simple(
                    config, runtime, participant=participant_code, profile_name=profile_name,
                    log_callback=self.append_log,
                )
                raw_path = session.logfile_path
                if not raw_path:
                    raise RuntimeError("SimPLE did not create a raw log.")
                analysis = analyze_simple_log(raw_path, started_at=session.started_at)
                base_dir = Path(raw_path).parent.parent
                if runtime.get("save_step_file", True):
                    step_path = base_dir / "steps" / (Path(raw_path).stem + "_step.tsv")
                    analysis.setdefault("artifacts", {})["step_response"] = Path(
                        write_step_response(step_path, analysis)
                    ).name
                if runtime.get("save_graph_pdf", True):
                    graph_path = base_dir / "graphs" / (Path(raw_path).stem + "_response.pdf")
                    analysis.setdefault("artifacts", {})["step_response_graph"] = Path(
                        save_step_graph(graph_path, analysis)
                    ).name
                    if runtime.get("auto_open_graph", False):
                        self._open_local_file(graph_path)
            else:
                from thrust.runners.scope_runner import run_scope
                config = (
                    self.scope_page.build_scope_config(self.common_page)
                    if self.offline_mode
                    else self._configuration_from_web_test(test)
                )
                config.user = participant_code
                config.profile_name = profile_name
                config.validate()
                self.append_log(
                    f"Starting {test['test_code']} v{test['version']} for participant {participant_code}."
                )
                session = run_scope(config, log_callback=self.append_log)
                raw_path = session.logfile_path
                step_path = session.step_path
                if not raw_path:
                    raise RuntimeError("Measurement did not create a raw log.")
                analysis = analyze_scope_log(raw_path)
                if step_path and Path(step_path).is_file() and "normalized_step_response" not in analysis:
                    with Path(step_path).open("r", encoding="utf-8", newline="") as handle:
                        reader = csv.DictReader(handle, delimiter="\\t")
                        curves = {
                            name: [] for name in (
                                "Time[s]", "AMEA", "AMED", "ASTD", "EMEA", "EMED", "ESTD",
                                "TMEA", "TMED", "TSTD", "RMEA", "RMED", "RSTD",
                            )
                        }
                        for row in reader:
                            for name in curves:
                                if row.get(name) not in (None, ""):
                                    curves[name].append(float(row[name]))
                        analysis["normalized_step_response"] = {
                            "schema_version": "scope-normalized-response-v1",
                            "columns": curves,
                        }

            if self.offline_mode:
                self.append_log(f"Offline measurement finished. Raw log: {raw_path}")
                return

            participant_id = self.participant_combo.currentData()
            if not participant_id:
                raise RuntimeError("Participant has no valid WebDB ID.")
            if self.client is None:
                raise RuntimeError("WebDB client is not connected.")

            uploaded = self.client.upload_measurement(
                participant_id=str(participant_id),
                test_definition_id=str(test["id"]),
                started_at=analysis.get("started_at") or datetime.now(timezone.utc).isoformat(),
                raw_log_path=raw_path,
                analysis_data=analysis,
            )
            self.append_log(
                f"Measurement uploaded: {uploaded.get('id', 'unknown')} "
                f"({uploaded.get('raw_size_bytes', 0)} bytes, SHA-256 {uploaded.get('raw_sha256', '')})."
            )
            self.append_log("Measurement finished and archived in WebDB.")
        except Exception as exc:
            self.append_log(f"Measurement failed: {type(exc).__name__}: {exc}")
            QMessageBox.critical(self, "Measurement failed", f"{type(exc).__name__}: {exc}")

    @staticmethod
    def _open_local_file(path: Path) -> None:
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(path))
            elif sys.platform == "darwin":
                os.system(f'open "{path}"')
            else:
                os.system(f'xdg-open "{path}"')
        except Exception:
            pass

    def append_log(self, message: str) -> None:
        self.log_output.appendPlainText(message)
