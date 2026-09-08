from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
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
from thrust.ui.pages.common_settings_page import CommonSettingsPage
from thrust.ui.pages.scope_settings_page import ScopeSettingsPage
from thrust.webdb_client import WebDbClient, WebDbError


class AdvancedSettingsDialog(QDialog):
    """Keeps technical controls available without cluttering the primary workflow."""

    def __init__(self, common_page: CommonSettingsPage, scope_page: ScopeSettingsPage, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("THRUST advanced settings")
        self.resize(760, 760)

        tabs = QTabWidget()
        tabs.addTab(common_page, "Runtime and output")
        tabs.addTab(scope_page, "SCoPE")

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        layout.addWidget(buttons)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("THRUST · WebDB measurement client")
        self.resize(960, 720)

        self.client: WebDbClient | None = None
        self.current_manifest: dict[str, Any] | None = None
        self.common_page = CommonSettingsPage()
        self.scope_page = ScopeSettingsPage()
        self.advanced_dialog: AdvancedSettingsDialog | None = None

        self.server_edit = QLineEdit("http://localhost:8080")
        self.username_edit = QLineEdit()
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.connect_button = QPushButton("Connect to WebDB")
        self.connect_button.clicked.connect(self._connect_webdb)

        connection_group = QGroupBox("Web database")
        connection_form = QFormLayout(connection_group)
        connection_form.addRow("Server URL:", self.server_edit)
        connection_form.addRow("Username:", self.username_edit)
        connection_form.addRow("Password:", self.password_edit)
        connection_form.addRow("", self.connect_button)

        self.connection_status = QLabel("Not connected")
        self.connection_status.setStyleSheet("color: #b56b6b;")

        self.participant_combo = QComboBox()
        self.participant_combo.setPlaceholderText("Connect to load participants")
        self.participant_combo.setEnabled(False)

        self.test_combo = QComboBox()
        self.test_combo.setPlaceholderText("Connect to load tests")
        self.test_combo.setEnabled(False)
        self.test_combo.currentIndexChanged.connect(self._load_selected_test)

        selection_group = QGroupBox("Measurement session")
        selection_form = QFormLayout(selection_group)
        selection_form.addRow("Participant ID:", self.participant_combo)
        selection_form.addRow("Test version:", self.test_combo)

        self.test_summary = QLabel("No test configuration loaded.")
        self.test_summary.setWordWrap(True)
        self.test_summary.setMinimumHeight(80)
        self.test_summary.setStyleSheet("padding: 12px; border: 1px solid #59636e;")

        self.run_button = QPushButton("Start selected measurement")
        self.run_button.setMinimumHeight(46)
        self.run_button.setEnabled(False)
        self.run_button.clicked.connect(self._run_selected_measurement)

        self.advanced_button = QPushButton("Advanced settings")
        self.advanced_button.clicked.connect(self._open_advanced)

        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMinimumHeight(170)

        self.clear_log_button = QPushButton("Clear log")
        self.clear_log_button.clicked.connect(self.log_output.clear)

        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(28, 24, 28, 24)
        root.setSpacing(16)

        title = QLabel("THRUST")
        title.setStyleSheet("font-size: 30px; font-weight: bold;")
        subtitle = QLabel("Local measurement client · configuration and participant data from WebDB")
        subtitle.setStyleSheet("color: #71808d;")

        status_row = QHBoxLayout()
        status_row.addWidget(self.connection_status)
        status_row.addStretch()
        status_row.addWidget(self.advanced_button)

        root.addWidget(title)
        root.addWidget(subtitle)
        root.addWidget(connection_group)
        root.addLayout(status_row)
        root.addWidget(selection_group)
        root.addWidget(self.test_summary)
        root.addWidget(self.run_button)
        root.addWidget(QLabel("Session log"))
        root.addWidget(self.log_output, 1)
        root.addWidget(self.clear_log_button)

        self.setCentralWidget(central)

    def _connect_webdb(self) -> None:
        try:
            self.client = WebDbClient(self.server_edit.text().strip())
            account = self.client.login(self.username_edit.text(), self.password_edit.text())
            participants = self.client.list_participants()
            tests = self.client.list_tests()

            self.participant_combo.clear()
            for participant in participants:
                self.participant_combo.addItem(
                    participant["participant_code"],
                    participant["id"],
                )

            self.test_combo.clear()
            for test in tests:
                if test.get("is_active", False):
                    self.test_combo.addItem(
                        f'{test["name"]} · v{test["version"]}',
                        test,
                    )

            self.participant_combo.setEnabled(bool(participants))
            self.test_combo.setEnabled(bool(tests))
            self.connection_status.setText(f'Connected as {account["username"]}')
            self.connection_status.setStyleSheet("color: #4ba878;")
            self.append_log(f"Loaded {len(participants)} participants and {len(tests)} tests.")
            self._load_selected_test()

        except (WebDbError, KeyError, ValueError) as exc:
            self.client = None
            self.connection_status.setText("Connection failed")
            self.connection_status.setStyleSheet("color: #b56b6b;")
            self.append_log(f"WebDB connection failed: {exc}")
            QMessageBox.critical(self, "WebDB connection failed", str(exc))

    def _load_selected_test(self, _index: int = -1) -> None:
        if self.client is None or self.test_combo.currentIndex() < 0:
            self.run_button.setEnabled(False)
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
                "The measurement engine will use this version-pinned configuration."
            )
            self.run_button.setEnabled(self.participant_combo.currentIndex() >= 0)
            self.append_log(f'Loaded test manifest: {test["test_code"]} v{test["version"]}')
        except (WebDbError, KeyError, TypeError, ValueError) as exc:
            self.current_manifest = None
            self.run_button.setEnabled(False)
            self.test_summary.setText(f"Configuration could not be loaded: {exc}")
            self.append_log(f"Test configuration failed: {exc}")

    def _apply_web_configuration(self, test: dict[str, Any]) -> None:
        source = test.get("configuration")
        if not isinstance(source, dict):
            raise ValueError("Test configuration must be a JSON object.")

        config = ScopeConfig()
        simple_mapping = {
            "sampling_hz": "fps",
            "difficulty": "difficulty",
            "timeout_s": "action_timeout_s",
            "hold_time_s": "hold_time_s",
            "max_completed_actions": "max_completed_actions",
        }
        for source_key, target_key in simple_mapping.items():
            if source_key in source:
                setattr(config, target_key, source[source_key])

        visual = source.get("visual", {})
        if isinstance(visual, dict):
            visual_mapping = {
                "screen_bg": "screen_background",
                "gimbal_bg": "gimbal_background",
                "stick_outline": "stick_outline",
                "stick_fill": "stick_fill",
                "zone_idle_outline": "zone_idle_outline",
                "zone_idle_fill": "zone_idle_fill",
                "zone_ok_outline": "zone_ok_outline",
                "zone_ok_fill": "zone_ok_fill",
                "grid": "grid_color",
                "label": "label_color",
                "prompt": "prompt_color",
            }
            for source_key, target_key in visual_mapping.items():
                if source_key in visual:
                    setattr(config, target_key, visual[source_key])

        config.validate()
        self.scope_page.load_scope_config(config)

    def _open_advanced(self) -> None:
        if self.advanced_dialog is None:
            self.advanced_dialog = AdvancedSettingsDialog(
                self.common_page,
                self.scope_page,
                self,
            )
        self.advanced_dialog.show()
        self.advanced_dialog.raise_()
        self.advanced_dialog.activateWindow()

    def _run_selected_measurement(self) -> None:
        if self.current_manifest is None:
            return

        participant_code = self.participant_combo.currentText().strip()
        test = self.current_manifest["test"]

        try:
            from thrust.runners.scope_runner import run_scope

            config = self.scope_page.build_scope_config(self.common_page)
            config.user = participant_code
            config.profile_name = f'{test["test_code"]}_v{test["version"]}'
            config.validate()

            self.append_log(
                f"Starting {test['test_code']} v{test['version']} for participant {participant_code}."
            )
            run_scope(config, log_callback=self.append_log)
            self.append_log("Measurement finished. Raw and derived files remain local for now.")
        except Exception as exc:
            self.append_log(f"Measurement failed: {type(exc).__name__}: {exc}")
            QMessageBox.critical(self, "Measurement failed", f"{type(exc).__name__}: {exc}")

    def append_log(self, message: str) -> None:
        self.log_output.appendPlainText(message)
