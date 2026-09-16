from __future__ import annotations

from pathlib import Path

import os
os.environ.setdefault("SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS", "1")

import pygame
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


class CommonSettingsPage(QWidget):
    """Local-only runtime, hardware diagnostics and output settings."""

    def __init__(self) -> None:
        super().__init__()
        self.joystick = None
        self.joystick_active = False
        self.axis_indicators: list[QLabel] = []
        self.button_indicators: list[QLabel] = []
        self.hat_indicators: list[QLabel] = []

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._poll_joystick)

        self._build_variables()
        self._build_ui()

    def _build_variables(self) -> None:
        self.fullscreen_check = QCheckBox()
        self.fullscreen_check.setChecked(True)
        self.topmost_check = QCheckBox()
        self.topmost_check.setChecked(True)
        self.debug_output_check = QCheckBox()
        self.debug_output_check.setChecked(False)

        self.joystick_index_spin = QSpinBox()
        self.joystick_index_spin.setRange(0, 16)
        self.joystick_index_spin.setValue(0)
        self.joystick_index_spin.setMaximumWidth(80)

        self.break_axis_spin = QSpinBox()
        self.break_axis_spin.setRange(0, 16)
        self.break_axis_spin.setValue(5)
        self.break_axis_spin.setMaximumWidth(80)

        self.reset_axis_spin = QSpinBox()
        self.reset_axis_spin.setRange(0, 16)
        self.reset_axis_spin.setValue(6)
        self.reset_axis_spin.setMaximumWidth(80)

        self.output_root_edit = QLineEdit(str(Path.home() / "Documents" / "THRUST" / "scope"))
        self.output_browse_button = QPushButton("Browse")
        self.output_browse_button.clicked.connect(self._browse_output_root)
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

        self.aile_axis_spin = QSpinBox()
        self.elev_axis_spin = QSpinBox()
        self.thro_axis_spin = QSpinBox()
        self.rudd_axis_spin = QSpinBox()
        self.deadzone_edit = QLineEdit("100,100,100,100")
        self.deadzone_edit.setMaximumWidth(180)
        for spin, value in (
            (self.aile_axis_spin, 0),
            (self.elev_axis_spin, 1),
            (self.thro_axis_spin, 2),
            (self.rudd_axis_spin, 3),
        ):
            spin.setRange(0, 16)
            spin.setValue(value)
            spin.setMaximumWidth(80)

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabWidget()
        root_layout.addWidget(self.tabs)

        runtime_tab = QWidget()
        runtime_layout = QVBoxLayout(runtime_tab)
        runtime_group = QGroupBox("Local runtime")
        runtime_form = QFormLayout(runtime_group)
        runtime_form.addRow("Fullscreen:", self.fullscreen_check)
        runtime_form.addRow("Topmost:", self.topmost_check)
        runtime_form.addRow("Debug output:", self.debug_output_check)
        runtime_form.addRow("Joystick device:", self.joystick_index_spin)
        runtime_form.addRow("Break button/axis:", self.break_axis_spin)
        runtime_form.addRow("Reset button/axis:", self.reset_axis_spin)
        runtime_layout.addWidget(runtime_group)
        runtime_layout.addStretch()

        joystick_tab = QWidget()
        joystick_layout = QVBoxLayout(joystick_tab)
        mapping_group = QGroupBox("pygame axis mapping used by measurement")
        mapping_form = QFormLayout(mapping_group)
        mapping_form.addRow("AILE:", self.aile_axis_spin)
        mapping_form.addRow("ELEV:", self.elev_axis_spin)
        mapping_form.addRow("THRO:", self.thro_axis_spin)
        mapping_form.addRow("RUDD:", self.rudd_axis_spin)
        mapping_form.addRow("Deadzone A,E,T,R:", self.deadzone_edit)

        diagnostic_group = QGroupBox("Live joystick diagnostic")
        diagnostic_layout = QVBoxLayout(diagnostic_group)
        controls = QHBoxLayout()
        self.start_test_btn = QPushButton("Start joystick test")
        self.stop_test_btn = QPushButton("Stop")
        self.start_test_btn.clicked.connect(self._start_joystick_test)
        self.stop_test_btn.clicked.connect(self._stop_joystick_test)
        controls.addWidget(self.start_test_btn)
        controls.addWidget(self.stop_test_btn)
        controls.addStretch()
        diagnostic_layout.addLayout(controls)

        self.device_status = QLabel("Joystick test is stopped.")
        diagnostic_layout.addWidget(self.device_status)
        self.axis_grid = QGridLayout()
        diagnostic_layout.addLayout(self.axis_grid)
        self.button_grid = QGridLayout()
        diagnostic_layout.addLayout(self.button_grid)
        self.hat_grid = QGridLayout()
        diagnostic_layout.addLayout(self.hat_grid)
        joystick_layout.addWidget(mapping_group)
        joystick_layout.addWidget(diagnostic_group)
        joystick_layout.addStretch()

        output_tab = QWidget()
        output_layout = QVBoxLayout(output_tab)
        output_group = QGroupBox("Local output")
        output_form = QFormLayout(output_group)
        output_root_widget = QWidget()
        output_root_layout = QHBoxLayout(output_root_widget)
        output_root_layout.setContentsMargins(0, 0, 0, 0)
        output_root_layout.addWidget(self.output_root_edit, 1)
        output_root_layout.addWidget(self.output_browse_button)
        output_form.addRow("Output root:", output_root_widget)
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
        self.tabs.addTab(joystick_tab, "Joystick diagnostics")
        self.tabs.addTab(output_tab, "Output")

    def _browse_output_root(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select output root", self.output_root_edit.text().strip())
        if path:
            self.output_root_edit.setText(path)

    def export_common_dict(self) -> dict:
        return {
            "user": "LOCAL",
            "fullscreen": self.fullscreen_check.isChecked(),
            "topmost": self.topmost_check.isChecked(),
            "debug_output": self.debug_output_check.isChecked(),
            "joystick_index": self.joystick_index_spin.value(),
            "break_axis": self.break_axis_spin.value(),
            "reset_axis": self.reset_axis_spin.value(),
            "deadzone": self._parse_deadzone(),
            "axis_map": {
                "AILE": self.aile_axis_spin.value(),
                "ELEV": self.elev_axis_spin.value(),
                "THRO": self.thro_axis_spin.value(),
                "RUDD": self.rudd_axis_spin.value(),
            },
            "output_root": self.output_root_edit.text().strip(),
            "use_dated_subfolders": self.use_dated_subfolders_check.isChecked(),
            "save_raw_log": self.save_raw_log_check.isChecked(),
            "save_action_log": self.save_action_log_check.isChecked(),
            "save_step_file": self.save_step_file_check.isChecked(),
            "save_graph_pdf": self.save_graph_pdf_check.isChecked(),
            "auto_open_graph": self.auto_open_graph_check.isChecked(),
            "run_evaluation": self.run_evaluation_check.isChecked(),
            "show_graph": self.show_graph_check.isChecked(),
        }

    def _parse_deadzone(self) -> list[int]:
        parts = [part.strip() for part in self.deadzone_edit.text().replace(";", ",").split(",") if part.strip()]
        if len(parts) != 4:
            raise ValueError("Deadzone must contain 4 comma-separated integers.")
        return [int(value) for value in parts]

    def load_common_dict(self, data: dict) -> None:
        self.fullscreen_check.setChecked(data.get("fullscreen", True))
        self.topmost_check.setChecked(data.get("topmost", True))
        self.debug_output_check.setChecked(data.get("debug_output", False))
        self.joystick_index_spin.setValue(data.get("joystick_index", 0))
        self.break_axis_spin.setValue(data.get("break_axis", 5))
        self.reset_axis_spin.setValue(data.get("reset_axis", 6))
        deadzone = data.get("deadzone", [100, 100, 100, 100])
        self.deadzone_edit.setText(",".join(str(value) for value in deadzone))
        axis_map = data.get("axis_map", {})
        self.aile_axis_spin.setValue(axis_map.get("AILE", 0))
        self.elev_axis_spin.setValue(axis_map.get("ELEV", 1))
        self.thro_axis_spin.setValue(axis_map.get("THRO", 2))
        self.rudd_axis_spin.setValue(axis_map.get("RUDD", 3))
        self.output_root_edit.setText(data.get("output_root", self.output_root_edit.text()))
        self.use_dated_subfolders_check.setChecked(data.get("use_dated_subfolders", True))
        self.save_raw_log_check.setChecked(data.get("save_raw_log", True))
        self.save_action_log_check.setChecked(data.get("save_action_log", True))
        self.save_step_file_check.setChecked(data.get("save_step_file", True))
        self.save_graph_pdf_check.setChecked(data.get("save_graph_pdf", True))
        self.auto_open_graph_check.setChecked(data.get("auto_open_graph", True))
        self.run_evaluation_check.setChecked(data.get("run_evaluation", True))
        self.show_graph_check.setChecked(data.get("show_graph", False))

    def _indicator_style(self, active: bool, value: float = 0.0) -> str:
        if active:
            return "QLabel { background: #49b883; color: #07140d; border: 1px solid #9ff0c2; border-radius: 4px; padding: 3px 7px; }"
        if value < -0.05:
            background, border = "#2459a6", "#5d9cf2"
        elif value > 0.05:
            background, border = "#a8661d", "#f0ad55"
        else:
            background, border = "#263442", "#59636e"
        return f"QLabel {{ background: {background}; color: #e7edf2; border: 1px solid {border}; border-radius: 4px; padding: 3px 7px; }}"

    def _clear_grid(self, grid: QGridLayout, widgets: list[QLabel]) -> None:
        for widget in widgets:
            grid.removeWidget(widget)
            widget.deleteLater()
        widgets.clear()

    def _start_joystick_test(self) -> None:
        self._stop_joystick_test(clear_text=False)
        try:
            pygame.init()
            pygame.joystick.init()
            index = self.joystick_index_spin.value()
            if pygame.joystick.get_count() <= index:
                self.device_status.setText("No joystick available for the selected device index.")
                return
            self.joystick = pygame.joystick.Joystick(index)
            self.joystick.init()
            self.joystick_active = True
            self.device_status.setText(f"Connected: {self.joystick.get_name()}")
            self.timer.start(50)
        except Exception as exc:
            self.device_status.setText(f"Joystick start failed: {exc}")

    def _poll_joystick(self) -> None:
        if not self.joystick_active or self.joystick is None:
            return
        try:
            pygame.event.pump()
            axis_count = self.joystick.get_numaxes()
            self._clear_grid(self.axis_grid, self.axis_indicators)
            for index in range(axis_count):
                value = float(self.joystick.get_axis(index))
                label = QLabel(f"Axis {index}: {value:+.3f}")
                label.setStyleSheet(self._indicator_style(False, value))
                self.axis_grid.addWidget(label, index // 4, index % 4)
                self.axis_indicators.append(label)

            button_count = self.joystick.get_numbuttons()
            self._clear_grid(self.button_grid, self.button_indicators)
            for index in range(button_count):
                active = bool(self.joystick.get_button(index))
                label = QLabel(f"Button {index}: {'ON' if active else 'off'}")
                label.setStyleSheet(self._indicator_style(active))
                self.button_grid.addWidget(label, index // 4, index % 4)
                self.button_indicators.append(label)

            hat_count = self.joystick.get_numhats()
            self._clear_grid(self.hat_grid, self.hat_indicators)
            for index in range(hat_count):
                value = self.joystick.get_hat(index)
                active = value != (0, 0)
                label = QLabel(f"Hat {index}: {value}")
                label.setStyleSheet(self._indicator_style(active))
                self.hat_grid.addWidget(label, index // 2, index % 2)
                self.hat_indicators.append(label)
        except Exception as exc:
            self.device_status.setText(f"Joystick polling failed: {exc}")
            self._stop_joystick_test(clear_text=False)

    def _stop_joystick_test(self, clear_text: bool = True) -> None:
        self.timer.stop()
        self.joystick_active = False
        try:
            if self.joystick is not None:
                self.joystick.quit()
        except Exception:
            pass
        self.joystick = None
        try:
            pygame.joystick.quit()
            pygame.quit()
        except Exception:
            pass
        if clear_text:
            self.device_status.setText("Joystick test is stopped.")
