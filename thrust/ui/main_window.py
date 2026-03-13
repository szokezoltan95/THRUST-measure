from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("THRUST")
        self.resize(1200, 800)

        self.program_selector = QComboBox()
        self.program_selector.addItems(["SCoPE", "SimPLE"])
        self.program_selector.currentIndexChanged.connect(self._on_program_changed)

        self.title_label = QLabel("THRUST")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.title_label.setStyleSheet("font-size: 24px; font-weight: bold;")

        self.subtitle_label = QLabel("Training Hub for UAV Research, Simulation and Testing")
        self.subtitle_label.setStyleSheet("color: gray;")

        self.common_placeholder = QLabel("Common settings placeholder")
        self.common_placeholder.setMinimumHeight(120)
        self.common_placeholder.setStyleSheet(
            "border: 1px solid #888; border-radius: 8px; padding: 12px;"
        )

        self.scope_page = self._build_scope_page()
        self.simple_page = self._build_simple_page()

        self.page_stack = QStackedWidget()
        self.page_stack.addWidget(self.scope_page)
        self.page_stack.addWidget(self.simple_page)

        self.run_button = QPushButton("Run")
        self.save_button = QPushButton("Save profile")
        self.load_button = QPushButton("Load profile")

        self.run_button.setMinimumHeight(40)
        self.save_button.setMinimumHeight(40)
        self.load_button.setMinimumHeight(40)

        central = QWidget()
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(12)

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
        root_layout.addWidget(self.common_placeholder)
        root_layout.addWidget(self.page_stack, 1)
        root_layout.addLayout(button_layout)

    def _build_scope_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        title = QLabel("SCoPE settings")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")

        placeholder = QLabel("SCoPE-specific configuration will be added here.")
        placeholder.setStyleSheet("border: 1px solid #888; border-radius: 8px; padding: 12px;")

        layout.addWidget(title)
        layout.addWidget(placeholder)
        layout.addStretch()

        return page

    def _build_simple_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        title = QLabel("SimPLE settings")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")

        placeholder = QLabel("SimPLE-specific configuration will be added here.")
        placeholder.setStyleSheet("border: 1px solid #888; border-radius: 8px; padding: 12px;")

        layout.addWidget(title)
        layout.addWidget(placeholder)
        layout.addStretch()

        return page

    def _on_program_changed(self, index: int) -> None:
        self.page_stack.setCurrentIndex(index)