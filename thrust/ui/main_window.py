from __future__ import annotations

import csv
from dataclasses import fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from scope.scope_config import ScopeConfig
from thrust.analysis.scope_log import analyze_scope_log
from thrust.ui.pages.common_settings_page import CommonSettingsPage
from thrust.ui.pages.scope_settings_page import ScopeSettingsPage
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
        form.addRow("Username:", self.username_edit)
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
    """Offline test settings only; runtime and joystick controls stay in the main window."""

    def __init__(self, scope_page: ScopeSettingsPage, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("THRUST offline test settings")
        self.resize(760, 680)

        tabs = QTabWidget()
        tabs.addTab(scope_page, "Offline test configuration")

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        layout.addWidget(buttons)


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
        self.advanced_dialog: AdvancedSettingsDialog | None = None

        # Keep joystick diagnostics in the main window and system settings below Run.
        self.joystick_panel = self.common_page.tabs.widget(1)
        self.common_page.tabs.removeTab(1)
        self.system_tabs = self.common_page.tabs
        self.joystick_panel.setMinimumWidth(450)
        self.joystick_panel.setMinimumHeight(470)
        self.joystick_panel.setMaximumHeight(520)
        self.system_tabs.setMinimumHeight(250)
        self.system_tabs.setMaximumHeight(330)

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

        self.connection_status = QLabel("WebDB disconnected · Offline mode")
        self.connection_status.setStyleSheet("color: #d6a35b;")

        self.participant_combo = QComboBox()
        self.participant_combo.setEditable(True)
        self.participant_combo.setPlaceholderText("Participant ID")
        self.participant_combo.setEnabled(False)

        self.test_combo = QComboBox()
        self.test_combo.setPlaceholderText("Connect to load test versions")
        self.test_combo.setEnabled(False)
        self.test_combo.currentIndexChanged.connect(self._load_selected_test)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Dummy test (no joystick)", "Real joystick"])

        selection_group = QGroupBox("Measurement session")
        selection_form = QFormLayout(selection_group)
        selection_form.addRow("Execution mode:", self.mode_combo)
        selection_form.addRow("Participant ID:", self.participant_combo)
        selection_form.addRow("Test version:", self.test_combo)

        self.test_summary = QLabel("Offline mode is active. Configure the test in Offline test settings.")
        self.test_summary.setWordWrap(True)
        self.test_summary.setMinimumHeight(56)
        self.test_summary.setStyleSheet("padding: 10px; border: 1px solid #59636e;")

        self.run_button = QPushButton("Start measurement")
        self.run_button.setMinimumHeight(44)
        self.run_button.clicked.connect(self._run_selected_measurement)

        self.advanced_button = QPushButton("Offline test settings")
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
        title.setStyleSheet("font-size: 28px; font-weight: bold;")
        subtitle = QLabel("Local measurement client · WebDB test versions with local runtime diagnostics")
        subtitle.setStyleSheet("color: #71808d;")

        status_row = QHBoxLayout()
        status_row.addWidget(self.connection_status)
        status_row.addStretch()
        status_row.addWidget(self.connect_button)
        status_row.addWidget(self.disconnect_button)

        left = QVBoxLayout()
        left.setSpacing(10)
        left.addWidget(selection_group)
        left.addWidget(self.test_summary)
        left.addWidget(self.run_button)
        left.addWidget(self.advanced_button)
        left.addWidget(self.system_tabs)

        right = QVBoxLayout()
        right.setSpacing(10)
        right.addWidget(self.joystick_panel)
        right.addStretch()

        columns = QGridLayout()
        columns.setHorizontalSpacing(12)
        columns.setVerticalSpacing(8)
        columns.addLayout(left, 0, 0)
        columns.addLayout(right, 0, 1)
        columns.setColumnStretch(0, 1)
        columns.setColumnStretch(1, 1)

        root.addWidget(title)
        root.addWidget(subtitle)
        root.addLayout(status_row)
        root.addLayout(columns, 1)
        root.addWidget(QLabel("Session log"))
        root.addWidget(self.log_output)

        self.setCentralWidget(central)
        self._activate_offline_mode(show_dialog=False)

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
            participants = self.client.list_participants()
            tests = self.client.list_tests()

            self.participant_combo.clear()
            for participant in participants:
                self.participant_combo.addItem(participant["participant_code"], participant["id"])

            self.test_combo.clear()
            for test in tests:
                if test.get("is_active", False):
                    self.test_combo.addItem(f'{test["name"]} · v{test["version"]}', test)

            self.offline_mode = False
            self.config_source_combo.setCurrentIndex(0)
            self.participant_combo.setEnabled(bool(participants))
            self.test_combo.setEnabled(bool(tests))
            self.connection_status.setText(f'Connected as {account["username"]}')
            self.connection_status.setStyleSheet("color: #4ba878;")
            self.connect_button.setVisible(False)
            self.disconnect_button.setVisible(True)
            self.advanced_button.setVisible(False)
            self.append_log(f"Loaded {len(participants)} participants and {len(tests)} active tests.")
            self._load_selected_test()

        except (WebDbError, KeyError, ValueError) as exc:
            self.append_log(f"WebDB connection failed: {exc}")
            self._activate_offline_mode(show_dialog=True, error=str(exc))

    def _disconnect_webdb(self) -> None:
        self._activate_offline_mode(show_dialog=False)
        self.append_log("WebDB disconnected. Offline mode is active.")

    def _offline_manifest(self) -> dict[str, Any]:
        return {
            "test": {
                "id": "",
                "test_code": "LOCAL_OFFLINE",
                "name": "Local offline SCoPE test",
                "version": "local",
                "analysis_profile": "SCOPE_STEP_RESPONSE_V1",
                "configuration": {},
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

        self.test_combo.clear()
        self.test_combo.addItem("Local offline SCoPE test · local", self.current_manifest["test"])
        self.test_combo.setCurrentIndex(0)
        self.test_combo.setEnabled(True)

        self.connection_status.setText("WebDB disconnected · Offline mode")
        self.connection_status.setStyleSheet("color: #d6a35b;")
        self.connect_button.setVisible(True)
        self.disconnect_button.setVisible(False)
        self.advanced_button.setVisible(True)
        self.run_button.setEnabled(True)
        self.test_summary.setText(
            "Offline mode is active. Test settings are local-only and are not synchronized to WebDB."
        )
        if show_dialog:
            QMessageBox.warning(
                self,
                "WebDB unavailable",
                f"THRUST switched to offline mode automatically.\n\n{error}",
            )
            self._open_advanced()

    def _load_selected_test(self, _index: int = -1) -> None:
        if self.offline_mode or self.client is None or self.test_combo.currentIndex() < 0:
            return

        selected = self.test_combo.currentData()
        if not isinstance(selected, dict):
            self.run_button.setEnabled(False)
            return

        try:
            self.current_manifest = self.client.get_test_configuration(selected["id"])
            test = self.current_manifest["test"]
            self._apply_web_configuration(test)
            self.test_summary.setText(
                f'Loaded {test["name"]} · version {test["version"]}\n'
                f'Analysis profile: {test["analysis_profile"]}\n'
                "The measurement engine will use this WebDB version-pinned configuration."
            )
            self.run_button.setEnabled(self.participant_combo.currentIndex() >= 0)
            self.append_log(f'Loaded test manifest: {test["test_code"]} v{test["version"]}')
        except (WebDbError, KeyError, TypeError, ValueError) as exc:
            self.current_manifest = None
            self.run_button.setEnabled(False)
            self.test_summary.setText(f"Configuration could not be loaded: {exc}")
            self.append_log(f"Test configuration failed: {exc}")

    def _configuration_from_web_test(self, test: dict[str, Any]) -> ScopeConfig:
        source = test.get("configuration")
        if not isinstance(source, dict):
            raise ValueError("Test configuration must be a JSON object.")

        config_data = dict(source)
        for obsolete_key in (
            "user", "profile_name", "expert_mode", "output_root", "use_dated_subfolders",
            "joystick_index", "break_axis", "axis_map", "deadzone",
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

    def _apply_web_configuration(self, test: dict[str, Any]) -> None:
        config = self._configuration_from_web_test(test)
        self.scope_page.apply_scope_config(config, self.common_page)

    def _open_advanced(self) -> None:
        if self.advanced_dialog is None:
            self.advanced_dialog = AdvancedSettingsDialog(self.scope_page, self)
        self.advanced_dialog.show()
        self.advanced_dialog.raise_()
        self.advanced_dialog.activateWindow()

    def _run_selected_measurement(self) -> None:
        if self.current_manifest is None:
            return

        participant_code = self.participant_combo.currentText().strip() or "LOCAL"
        test = self.current_manifest["test"]

        try:
            from thrust.runners.scope_runner import run_scope

            if self.offline_mode:
                config = self.scope_page.build_scope_config(self.common_page)
            else:
                config = self._configuration_from_web_test(test)
            config.user = participant_code
            config.profile_name = f'{test["test_code"]}_v{test["version"]}'
            config.validate()

            self.append_log(
                f"Starting {test['test_code']} v{test['version']} for participant {participant_code}."
            )
            step_path = ""
            if self.mode_combo.currentIndex() == 0:
                from thrust.dummy_runner import run_dummy
                raw_path = run_dummy(
                    participant_code=participant_code,
                    test_code=test["test_code"],
                    test_version=test["version"],
                    output_root=config.output_root,
                    log_callback=self.append_log,
                )
            else:
                session = run_scope(config, log_callback=self.append_log)
                raw_path = session.logfile_path
                step_path = session.step_path

            if not raw_path:
                raise RuntimeError("Measurement did not create a raw log.")

            analysis = analyze_scope_log(raw_path)
            if step_path and Path(step_path).is_file() and "normalized_step_response" not in analysis:
                with Path(step_path).open("r", encoding="utf-8", newline="") as handle:
                    reader = csv.DictReader(handle, delimiter="\t")
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

    def append_log(self, message: str) -> None:
        self.log_output.appendPlainText(message)
