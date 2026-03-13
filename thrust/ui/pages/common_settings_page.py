from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


class CommonSettingsPage(QWidget):
    def __init__(self) -> None:
        super().__init__()

        self._build_variables()
        self._build_ui()

    def _build_variables(self) -> None:
        self.user_edit = QLineEdit("Pilot")
        self.user_edit.setMaximumWidth(180)

        self.fullscreen_check = QCheckBox()
        self.fullscreen_check.setChecked(True)

        self.topmost_check = QCheckBox()
        self.topmost_check.setChecked(True)

        self.debug_output_check = QCheckBox()
        self.debug_output_check.setChecked(False)

        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(10, 1000)
        self.fps_spin.setValue(100)
        self.fps_spin.setMaximumWidth(100)

        self.joystick_index_spin = QSpinBox()
        self.joystick_index_spin.setRange(0, 16)
        self.joystick_index_spin.setValue(0)
        self.joystick_index_spin.setMaximumWidth(80)

        self.break_axis_spin = QSpinBox()
        self.break_axis_spin.setRange(0, 16)
        self.break_axis_spin.setValue(5)
        self.break_axis_spin.setMaximumWidth(80)

        self.output_root_edit = QLineEdit(str(Path.home() / "Documents" / "THRUST" / "scope"))
        self.output_browse_button = QPushButton("Browse")
        self.output_browse_button.clicked.connect(self._browse_output_root)

        self.profile_name_edit = QLineEdit("default")
        self.profile_name_edit.setMaximumWidth(180)

        self.use_dated_subfolders_check = QCheckBox()
        self.use_dated_subfolders_check.setChecked(True)

        self.save_raw_log_check = QCheckBox()
        self.save_raw_log_check.setChecked(True)

        self.save_action_log_check = QCheckBox()
        self.save_action_log_check.setChecked(True)

        self.save_step_file_check = QCheckBox()
        self.save_step_file_check.setChecked(True)

        self.save_graph_pdf_check = QCheckBox()
        self.save_graph_pdf_check.setChecked(True)

        self.auto_open_graph_check = QCheckBox()
        self.auto_open_graph_check.setChecked(True)

        self.run_evaluation_check = QCheckBox()
        self.run_evaluation_check.setChecked(True)

        self.show_graph_check = QCheckBox()
        self.show_graph_check.setChecked(False)

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(8)

        self.tabs = QTabWidget()

        runtime_tab = QWidget()
        runtime_layout = QVBoxLayout(runtime_tab)
        runtime_layout.setContentsMargins(8, 8, 8, 8)

        runtime_group = QGroupBox("Runtime")
        runtime_form = QFormLayout(runtime_group)
        runtime_form.addRow("User:", self.user_edit)
        runtime_form.addRow("Fullscreen:", self.fullscreen_check)
        runtime_form.addRow("Topmost:", self.topmost_check)
        runtime_form.addRow("Debug output:", self.debug_output_check)
        runtime_form.addRow("FPS:", self.fps_spin)
        runtime_form.addRow("Joystick index:", self.joystick_index_spin)
        runtime_form.addRow("Break axis:", self.break_axis_spin)

        runtime_layout.addWidget(runtime_group)
        runtime_layout.addStretch()

        output_tab = QWidget()
        output_layout = QVBoxLayout(output_tab)
        output_layout.setContentsMargins(8, 8, 8, 8)

        output_group = QGroupBox("Output")
        output_form = QFormLayout(output_group)

        output_root_widget = QWidget()
        output_root_layout = QHBoxLayout(output_root_widget)
        output_root_layout.setContentsMargins(0, 0, 0, 0)
        output_root_layout.setSpacing(6)
        output_root_layout.addWidget(self.output_root_edit, 1)
        output_root_layout.addWidget(self.output_browse_button)

        output_form.addRow("Output root:", output_root_widget)
        output_form.addRow("Profile name:", self.profile_name_edit)
        output_form.addRow("Dated subfolders:", self.use_dated_subfolders_check)
        output_form.addRow("Save raw log:", self.save_raw_log_check)
        output_form.addRow("Save action log:", self.save_action_log_check)
        output_form.addRow("Save step file:", self.save_step_file_check)
        output_form.addRow("Save graph PDF:", self.save_graph_pdf_check)
        output_form.addRow("Auto open graph:", self.auto_open_graph_check)
        output_form.addRow("Run evaluation:", self.run_evaluation_check)
        output_form.addRow("Show graph:", self.show_graph_check)

        output_layout.addWidget(output_group)
        output_layout.addStretch()

        self.tabs.addTab(runtime_tab, "Runtime")
        self.tabs.addTab(output_tab, "Output")

        root_layout.addWidget(self.tabs)

    def _browse_output_root(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            "Select output root",
            self.output_root_edit.text().strip(),
        )
        if path:
            self.output_root_edit.setText(path)