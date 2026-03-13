from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
    QFileDialog,
)
from pathlib import Path
from scope.scope_config import ScopeConfig


from thrust.ui.pages.common_settings_page import CommonSettingsPage
from thrust.ui.pages.scope_settings_page import ScopeSettingsPage


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("THRUST")
        self.resize(1500, 920)

        self.program_selector = QComboBox()
        self.program_selector.addItems(["SCoPE", "SimPLE"])
        self.program_selector.currentIndexChanged.connect(self._on_program_changed)
        self.program_selector.setMinimumWidth(160)

        self.title_label = QLabel("THRUST")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.title_label.setStyleSheet("font-size: 24px; font-weight: bold;")

        self.subtitle_label = QLabel("Training Hub for UAV Research, Simulation and Testing")
        self.subtitle_label.setStyleSheet("color: gray;")

        self.common_page = CommonSettingsPage()
        self.scope_page = ScopeSettingsPage()
        self.simple_page = self._build_simple_page()

        self.page_stack = QStackedWidget()
        self.page_stack.addWidget(self.scope_page)
        self.page_stack.addWidget(self.simple_page)

        self.right_scroll = QScrollArea()
        self.right_scroll.setWidgetResizable(True)
        self.right_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.right_scroll.setWidget(self.page_stack)

        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMinimumHeight(220)

        self.clear_log_button = QPushButton("Clear log")
        self.clear_log_button.clicked.connect(self.log_output.clear)

        self.left_panel = QWidget()
        left_layout = QVBoxLayout(self.left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        common_title = QLabel("Common settings")
        common_title.setStyleSheet("font-size: 18px; font-weight: bold;")

        log_group = QGroupBox("Session log")
        log_layout = QVBoxLayout(log_group)
        log_layout.addWidget(self.log_output)
        log_layout.addWidget(self.clear_log_button)

        left_layout.addWidget(common_title)
        left_layout.addWidget(self.common_page)
        left_layout.addWidget(log_group, 1)

        self.left_panel.setMinimumWidth(360)
        self.left_panel.setMaximumWidth(500)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.addWidget(self.left_panel)
        self.splitter.addWidget(self.right_scroll)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([410, 1090])

        self.run_button = QPushButton("Run")
        self.save_button = QPushButton("Save profile")
        self.load_button = QPushButton("Load profile")

        self.run_button.setMinimumHeight(40)
        self.save_button.setMinimumHeight(40)
        self.load_button.setMinimumHeight(40)

        self.run_button.clicked.connect(self._run_selected_program)

        central = QWidget()
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(12)

        header_layout = QHBoxLayout()
        header_text_layout = QVBoxLayout()
        header_text_layout.setSpacing(2)
        header_text_layout.addWidget(self.title_label)
        header_text_layout.addWidget(self.subtitle_label)

        header_layout.addLayout(header_text_layout)
        header_layout.addStretch()
        header_layout.addWidget(QLabel("Program:"))
        header_layout.addWidget(self.program_selector)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.load_button)
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.run_button)

        root_layout.addLayout(header_layout)
        root_layout.addWidget(self.splitter, 1)
        root_layout.addLayout(button_layout)
        
        self.save_button.clicked.connect(self._save_profile)
        self.load_button.clicked.connect(self._load_profile)

    def append_log(self, message: str) -> None:
        self.log_output.appendPlainText(message)

    def _build_simple_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        title = QLabel("SimPLE settings")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")

        placeholder = QLabel("SimPLE settings will be added later.")
        placeholder.setStyleSheet(
            "border: 1px solid #888; border-radius: 8px; padding: 12px;"
        )

        layout.addWidget(title)
        layout.addWidget(placeholder)
        layout.addStretch()

        return page

    def _on_program_changed(self, index: int) -> None:
        self.page_stack.setCurrentIndex(index)

    def _run_selected_program(self) -> None:
        program = self.program_selector.currentText()

        try:
            if program == "SCoPE":
                from thrust.runners.scope_runner import run_scope

                config = self.scope_page.build_scope_config(self.common_page)
                config.validate()

                self.append_log("SCoPE config created successfully.")
                self.append_log("Starting SCoPE session...")

                run_scope(config, log_callback=self.append_log)

                self.append_log("SCoPE session finished.")

            else:
                QMessageBox.information(
                    self,
                    "Not ready",
                    "SimPLE integration will be added later.",
                )

        except Exception as exc:
            self.append_log(f"Run failed: {type(exc).__name__}: {exc}")
            QMessageBox.critical(
                self,
                "Run failed",
                f"{type(exc).__name__}: {exc}",
            )
            
    def _default_scope_profile_dir(self) -> Path:
        return Path.cwd() / "profiles" / "scope"

    def _save_profile(self) -> None:
        program = self.program_selector.currentText()

        try:
            if program == "SCoPE":
                config = self.scope_page.build_scope_config(self.common_page)
                config.validate()

                profile_dir = self._default_scope_profile_dir()
                profile_dir.mkdir(parents=True, exist_ok=True)

                suggested = profile_dir / f"{config.profile_name}.json"
                file_path, _ = QFileDialog.getSaveFileName(
                    self,
                    "Save SCoPE profile",
                    str(suggested),
                    "JSON files (*.json)",
                )
                if not file_path:
                    return

                config.save_json(file_path)
                self.append_log(f"Profile saved: {file_path}")

            else:
                QMessageBox.information(self, "Not ready", "SimPLE profile support will be added later.")

        except Exception as exc:
            self.append_log(f"Profile save failed: {type(exc).__name__}: {exc}")
            QMessageBox.critical(self, "Save failed", f"{type(exc).__name__}: {exc}")

    def _load_profile(self) -> None:
        program = self.program_selector.currentText()

        try:
            if program == "SCoPE":
                profile_dir = self._default_scope_profile_dir()
                profile_dir.mkdir(parents=True, exist_ok=True)

                file_path, _ = QFileDialog.getOpenFileName(
                    self,
                    "Load SCoPE profile",
                    str(profile_dir),
                    "JSON files (*.json)",
                )
                if not file_path:
                    return

                cfg = ScopeConfig.load_json(file_path)
                self.scope_page.apply_scope_config(cfg, self.common_page)
                self.append_log(f"Profile loaded: {file_path}")

            else:
                QMessageBox.information(self, "Not ready", "SimPLE profile support will be added later.")

        except Exception as exc:
            self.append_log(f"Profile load failed: {type(exc).__name__}: {exc}")
            QMessageBox.critical(self, "Load failed", f"{type(exc).__name__}: {exc}")