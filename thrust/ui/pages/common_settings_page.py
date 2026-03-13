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
    QVBoxLayout,
    QWidget,
)


class CommonSettingsPage(QWidget):
    def __init__(self) -> None:
        super().__init__()

        self.user_edit = QLineEdit("Pilot")

        self.fullscreen_check = QCheckBox()
        self.fullscreen_check.setChecked(True)

        self.topmost_check = QCheckBox()
        self.topmost_check.setChecked(True)

        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(10, 1000)
        self.fps_spin.setValue(100)

        self.joystick_index_spin = QSpinBox()
        self.joystick_index_spin.setRange(0, 16)
        self.joystick_index_spin.setValue(0)

        self.break_axis_spin = QSpinBox()
        self.break_axis_spin.setRange(0, 16)
        self.break_axis_spin.setValue(5)

        self.output_root_edit = QLineEdit(str(Path.home() / "Documents" / "THRUST" / "scope"))
        self.output_browse_button = QPushButton("Browse")
        self.output_browse_button.clicked.connect(self._browse_output_root)

        self.profile_name_edit = QLineEdit("default")

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

        root_layout = QVBoxLayout(self)
        root_layout.setSpacing(12)

        runtime_group = QGroupBox("Common runtime")
        runtime_form = QFormLayout(runtime_group)
        runtime_form.addRow("User:", self.user_edit)
        runtime_form.addRow("Fullscreen:", self.fullscreen_check)
        runtime_form.addRow("Topmost:", self.topmost_check)
        runtime_form.addRow("FPS:", self.fps_spin)
        runtime_form.addRow("Joystick index:", self.joystick_index_spin)
        runtime_form.addRow("Break axis:", self.break_axis_spin)

        output_group = QGroupBox("Common output")
        output_form = QFormLayout(output_group)

        output_row = QHBoxLayout()
        output_row.addWidget(self.output_root_edit, 1)
        output_row.addWidget(self.output_browse_button)

        output_form.addRow("Output root:", output_row)
        output_form.addRow("Profile name:", self.profile_name_edit)
        output_form.addRow("Dated subfolders:", self.use_dated_subfolders_check)
        output_form.addRow("Save raw log:", self.save_raw_log_check)
        output_form.addRow("Save action log:", self.save_action_log_check)
        output_form.addRow("Save step file:", self.save_step_file_check)
        output_form.addRow("Save graph PDF:", self.save_graph_pdf_check)
        output_form.addRow("Auto open graph:", self.auto_open_graph_check)
        output_form.addRow("Run evaluation:", self.run_evaluation_check)
        output_form.addRow("Show graph:", self.show_graph_check)

        root_layout.addWidget(runtime_group)
        root_layout.addWidget(output_group)
        root_layout.addStretch()

    def _browse_output_root(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            "Select output root",
            self.output_root_edit.text().strip(),
        )
        if path:
            self.output_root_edit.setText(path)