from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from thrust.ui.pages.common_settings_page import CommonSettingsPage
from thrust.ui.pages.scope_settings_page import ScopeSettingsPage


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("THRUST")
        self.resize(1400, 900)

        self.program_selector = QComboBox()
        self.program_selector.addItems(["SCoPE", "SimPLE"])
        self.program_selector.currentIndexChanged.connect(self._on_program_changed)

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

        self.run_button = QPushButton("Run")
        self.save_button = QPushButton("Save profile")
        self.load_button = QPushButton("Load profile")

        self.run_button.clicked.connect(self._run_selected_program)

        central = QWidget()
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(central)

        header_layout = QHBoxLayout()
        header_text_layout = QVBoxLayout()
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
        root_layout.addWidget(self.common_page)
        root_layout.addWidget(self.page_stack, 1)
        root_layout.addLayout(button_layout)

    def _build_simple_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        label = QLabel("SimPLE settings will be added later.")
        layout.addWidget(label)
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
                run_scope(config)

            else:
                QMessageBox.information(self, "Not ready", "SimPLE integration will be added later.")
        except Exception as exc:
            QMessageBox.critical(self, "Run failed", f"{type(exc).__name__}: {exc}")