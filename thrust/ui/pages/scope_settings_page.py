from __future__ import annotations

import os

os.environ["SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS"] = "1"

import pygame

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from scope.scope_config import ScopeConfig


class ScopeSettingsPage(QWidget):
    def __init__(self) -> None:
        super().__init__()

        self.joystick = None
        self.joystick_active = False

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._poll_joystick)

        self._build_variables()
        self._build_ui()
        self.load_scope_config(ScopeConfig())

    def _build_variables(self) -> None:
        self.difficulty_edit = QLineEdit("hard")
        self.difficulty_edit.setMaximumWidth(140)

        self.timeout_spin = QDoubleSpinBox()
        self.timeout_spin.setRange(0.1, 60.0)
        self.timeout_spin.setDecimals(2)
        self.timeout_spin.setValue(3.0)
        self.timeout_spin.setMaximumWidth(110)

        self.hold_time_spin = QDoubleSpinBox()
        self.hold_time_spin.setRange(0.1, 60.0)
        self.hold_time_spin.setDecimals(2)
        self.hold_time_spin.setValue(0.5)
        self.hold_time_spin.setMaximumWidth(110)

        self.stick_max_spin = QSpinBox()
        self.stick_max_spin.setRange(100, 5000)
        self.stick_max_spin.setValue(1000)
        self.stick_max_spin.setMaximumWidth(110)

        self.deadzone_edit = QLineEdit("100,100,100,100")
        self.deadzone_edit.setMaximumWidth(180)

        self.max_actions_spin = QSpinBox()
        self.max_actions_spin.setRange(1, 10000)
        self.max_actions_spin.setValue(50)
        self.max_actions_spin.setMaximumWidth(110)

        self.countdown_spin = QSpinBox()
        self.countdown_spin.setRange(0, 60)
        self.countdown_spin.setValue(3)
        self.countdown_spin.setMaximumWidth(110)

        self.seed_edit = QLineEdit("")
        self.seed_edit.setMaximumWidth(140)

        self.expert_mode_check = QCheckBox()
        self.expert_mode_check.setChecked(False)

        self.aile_axis_spin = QSpinBox()
        self.elev_axis_spin = QSpinBox()
        self.thro_axis_spin = QSpinBox()
        self.rudd_axis_spin = QSpinBox()
        for spin, value in (
            (self.aile_axis_spin, 0),
            (self.elev_axis_spin, 1),
            (self.thro_axis_spin, 2),
            (self.rudd_axis_spin, 3),
        ):
            spin.setRange(0, 16)
            spin.setValue(value)
            spin.setMaximumWidth(80)

        self.gui_gimbal_size_spin = QSpinBox()
        self.gui_gimbal_size_spin.setRange(150, 2000)
        self.gui_gimbal_size_spin.setValue(500)
        self.gui_gimbal_size_spin.setMaximumWidth(110)

        self.gui_stick_zone_spin = QSpinBox()
        self.gui_stick_zone_spin.setRange(10, 1000)
        self.gui_stick_zone_spin.setValue(200)
        self.gui_stick_zone_spin.setMaximumWidth(110)

        self.gui_stick_radius_spin = QSpinBox()
        self.gui_stick_radius_spin.setRange(1, 100)
        self.gui_stick_radius_spin.setValue(20)
        self.gui_stick_radius_spin.setMaximumWidth(110)

        self.gui_stick_outline_width_spin = QSpinBox()
        self.gui_stick_outline_width_spin.setRange(1, 30)
        self.gui_stick_outline_width_spin.setValue(6)
        self.gui_stick_outline_width_spin.setMaximumWidth(110)

        self.gui_zone_outline_width_spin = QSpinBox()
        self.gui_zone_outline_width_spin.setRange(1, 30)
        self.gui_zone_outline_width_spin.setValue(8)
        self.gui_zone_outline_width_spin.setMaximumWidth(110)

        self.gui_gimbal_border_width_spin = QSpinBox()
        self.gui_gimbal_border_width_spin.setRange(1, 40)
        self.gui_gimbal_border_width_spin.setValue(12)
        self.gui_gimbal_border_width_spin.setMaximumWidth(110)

        self.gui_gimbal_cross_width_spin = QSpinBox()
        self.gui_gimbal_cross_width_spin.setRange(1, 20)
        self.gui_gimbal_cross_width_spin.setValue(6)
        self.gui_gimbal_cross_width_spin.setMaximumWidth(110)

        self.color_buttons = {}
        self.colors = {
            "screen_background": "#000000",
            "gimbal_background": "#808080",
            "stick_outline": "#1e2cff",
            "stick_fill": "#ffffff",
            "zone_idle_outline": "#ff0000",
            "zone_idle_fill": "#ff0000",
            "zone_ok_outline": "#00cc00",
            "zone_ok_fill": "#00cc00",
            "grid_color": "#ffffff",
            "label_color": "#ffffff",
            "prompt_color": "#ff0000",
        }

    def _build_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()
        outer_layout.addWidget(self.tabs)

        self.tab_experiment = QWidget()
        self.tab_runtime = QWidget()
        self.tab_appearance = QWidget()

        self.tabs.addTab(self.tab_experiment, "Experiment")
        self.tabs.addTab(self.tab_runtime, "Runtime / Joystick")
        self.tabs.addTab(self.tab_appearance, "Appearance")

        self._build_experiment_tab()
        self._build_runtime_tab()
        self._build_appearance_tab()

    def _build_experiment_tab(self) -> None:
        layout = QHBoxLayout(self.tab_experiment)

        left_group = QGroupBox("Task")
        left_form = QFormLayout(left_group)
        left_form.addRow("Difficulty:", self.difficulty_edit)
        left_form.addRow("Action timeout [s]:", self.timeout_spin)
        left_form.addRow("Hold time [s]:", self.hold_time_spin)
        left_form.addRow("Stick max:", self.stick_max_spin)
        left_form.addRow("Deadzone A,E,T,R:", self.deadzone_edit)

        right_group = QGroupBox("Session")
        right_form = QFormLayout(right_group)
        right_form.addRow("Completed actions:", self.max_actions_spin)
        right_form.addRow("Countdown [s]:", self.countdown_spin)
        right_form.addRow("Random seed:", self.seed_edit)
        right_form.addRow("Expert mode:", self.expert_mode_check)

        layout.addWidget(left_group, 1)
        layout.addWidget(right_group, 1)

    def _build_runtime_tab(self) -> None:
        layout = QHBoxLayout(self.tab_runtime)

        mapping_group = QGroupBox("Axis mapping")
        mapping_form = QFormLayout(mapping_group)
        mapping_form.addRow("AILE axis:", self.aile_axis_spin)
        mapping_form.addRow("ELEV axis:", self.elev_axis_spin)
        mapping_form.addRow("THRO axis:", self.thro_axis_spin)
        mapping_form.addRow("RUDD axis:", self.rudd_axis_spin)

        joystick_group = QGroupBox("Joystick test")
        joystick_layout = QVBoxLayout(joystick_group)

        btn_row = QHBoxLayout()
        self.start_test_btn = QPushButton("Start test")
        self.stop_test_btn = QPushButton("Stop test")
        self.start_test_btn.clicked.connect(self._start_joystick_test)
        self.stop_test_btn.clicked.connect(self._stop_joystick_test)

        btn_row.addWidget(self.start_test_btn)
        btn_row.addWidget(self.stop_test_btn)
        btn_row.addStretch()

        self.joystick_status = QTextEdit()
        self.joystick_status.setReadOnly(True)
        self.joystick_status.setMinimumHeight(260)

        joystick_layout.addLayout(btn_row)
        joystick_layout.addWidget(self.joystick_status)

        layout.addWidget(mapping_group, 0)
        layout.addWidget(joystick_group, 1)

    def _build_appearance_tab(self) -> None:
        layout = QHBoxLayout(self.tab_appearance)

        left_col = QVBoxLayout()
        right_col = QVBoxLayout()

        size_group = QGroupBox("Geometry")
        size_form = QFormLayout(size_group)
        size_form.addRow("Gimbal size [px]:", self.gui_gimbal_size_spin)
        size_form.addRow("Target zone radius:", self.gui_stick_zone_spin)
        size_form.addRow("Stick radius:", self.gui_stick_radius_spin)
        size_form.addRow("Stick outline width:", self.gui_stick_outline_width_spin)
        size_form.addRow("Zone outline width:", self.gui_zone_outline_width_spin)
        size_form.addRow("Gimbal border width:", self.gui_gimbal_border_width_spin)
        size_form.addRow("Cross width:", self.gui_gimbal_cross_width_spin)

        color_group = QGroupBox("Colors")
        color_grid = QGridLayout(color_group)

        labels = [
            ("screen_background", "Screen background"),
            ("gimbal_background", "Gimbal background"),
            ("stick_outline", "Stick outline"),
            ("stick_fill", "Stick fill"),
            ("zone_idle_outline", "Zone idle outline"),
            ("zone_idle_fill", "Zone idle fill"),
            ("zone_ok_outline", "Zone OK outline"),
            ("zone_ok_fill", "Zone OK fill"),
            ("grid_color", "Grid color"),
            ("label_color", "Label color"),
            ("prompt_color", "Prompt color"),
        ]

        for row, (key, label) in enumerate(labels):
            btn = QPushButton()
            btn.setMinimumWidth(130)
            btn.clicked.connect(lambda _, k=key: self._pick_color(k))
            self.color_buttons[key] = btn
            color_grid.addWidget(QLabel(label), row, 0)
            color_grid.addWidget(btn, row, 1)

        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)
        self.preview_status = QLabel("Live embedded preview will be added in the next step.")
        self.preview_status.setWordWrap(True)
        self.refresh_preview_btn = QPushButton("Refresh preview")
        self.refresh_preview_btn.clicked.connect(self._update_preview)
        preview_layout.addWidget(self.preview_status)
        preview_layout.addWidget(self.refresh_preview_btn)
        preview_layout.addStretch()

        left_col.addWidget(size_group)
        left_col.addStretch()

        right_col.addWidget(color_group)
        right_col.addWidget(preview_group)
        right_col.addStretch()

        layout.addLayout(left_col, 0)
        layout.addLayout(right_col, 1)

    def _pick_color(self, key: str) -> None:
        color = QColorDialog.getColor()
        if color.isValid():
            self.colors[key] = color.name()
            self._refresh_color_buttons()
            self._update_preview()

    def _refresh_color_buttons(self) -> None:
        for key, btn in self.color_buttons.items():
            hex_color = self.colors[key]
            btn.setText(hex_color)
            btn.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: {hex_color};
                    color: {self._ideal_text_color(hex_color)};
                    border: 1px solid #666;
                    border-radius: 6px;
                    padding: 6px 10px;
                    font-weight: 600;
                }}
                """
            )

    def _ideal_text_color(self, hex_color: str) -> str:
        hex_color = hex_color.lstrip("#")
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        brightness = (r * 299 + g * 587 + b * 114) / 1000
        return "#000000" if brightness > 150 else "#ffffff"

    def _parse_deadzone(self) -> list[int]:
        parts = [p.strip() for p in self.deadzone_edit.text().replace(";", ",").split(",") if p.strip()]
        if len(parts) != 4:
            raise ValueError("Deadzone must contain 4 comma-separated integers.")
        return [int(v) for v in parts]

    def build_scope_config(self, common) -> ScopeConfig:
        seed_text = self.seed_edit.text().strip()

        return ScopeConfig(
            user=common.user_edit.text().strip() or "Pilot",
            difficulty=self.difficulty_edit.text().strip().lower() or "hard",
            action_timeout_s=self.timeout_spin.value(),
            hold_time_s=self.hold_time_spin.value(),
            fps=common.fps_spin.value(),
            stick_max=self.stick_max_spin.value(),
            deadzone=self._parse_deadzone(),
            max_completed_actions=self.max_actions_spin.value(),
            countdown_s=self.countdown_spin.value(),
            seed=int(seed_text) if seed_text else None,
            fullscreen=common.fullscreen_check.isChecked(),
            topmost=common.topmost_check.isChecked(),
            debug_output=common.debug_output_check.isChecked(),
            joystick_index=common.joystick_index_spin.value(),
            break_axis=common.break_axis_spin.value(),
            axis_map={
                "AILE": self.aile_axis_spin.value(),
                "ELEV": self.elev_axis_spin.value(),
                "THRO": self.thro_axis_spin.value(),
                "RUDD": self.rudd_axis_spin.value(),
            },
            output_root=common.output_root_edit.text().strip(),
            profile_name=common.profile_name_edit.text().strip() or "default",
            use_dated_subfolders=common.use_dated_subfolders_check.isChecked(),
            save_raw_log=common.save_raw_log_check.isChecked(),
            save_action_log=common.save_action_log_check.isChecked(),
            save_step_file=common.save_step_file_check.isChecked(),
            save_graph_pdf=common.save_graph_pdf_check.isChecked(),
            auto_open_graph=common.auto_open_graph_check.isChecked(),
            run_evaluation=common.run_evaluation_check.isChecked(),
            show_graph=common.show_graph_check.isChecked(),
            expert_mode=self.expert_mode_check.isChecked(),
            gui_gimbal_size=self.gui_gimbal_size_spin.value(),
            gui_stick_zone=self.gui_stick_zone_spin.value(),
            gui_stick_radius=self.gui_stick_radius_spin.value(),
            gui_stick_outline_width=self.gui_stick_outline_width_spin.value(),
            gui_zone_outline_width=self.gui_zone_outline_width_spin.value(),
            gui_gimbal_border_width=self.gui_gimbal_border_width_spin.value(),
            gui_gimbal_cross_width=self.gui_gimbal_cross_width_spin.value(),
            screen_background=self.colors["screen_background"],
            gimbal_background=self.colors["gimbal_background"],
            stick_outline=self.colors["stick_outline"],
            stick_fill=self.colors["stick_fill"],
            zone_idle_outline=self.colors["zone_idle_outline"],
            zone_idle_fill=self.colors["zone_idle_fill"],
            zone_ok_outline=self.colors["zone_ok_outline"],
            zone_ok_fill=self.colors["zone_ok_fill"],
            grid_color=self.colors["grid_color"],
            label_color=self.colors["label_color"],
            prompt_color=self.colors["prompt_color"],
        )

    def load_scope_config(self, cfg: ScopeConfig) -> None:
        self.difficulty_edit.setText(cfg.difficulty)
        self.timeout_spin.setValue(cfg.action_timeout_s)
        self.hold_time_spin.setValue(cfg.hold_time_s)
        self.stick_max_spin.setValue(cfg.stick_max)
        self.deadzone_edit.setText(",".join(str(v) for v in cfg.deadzone))
        self.max_actions_spin.setValue(cfg.max_completed_actions)
        self.countdown_spin.setValue(cfg.countdown_s)
        self.seed_edit.setText("" if cfg.seed is None else str(cfg.seed))
        self.expert_mode_check.setChecked(cfg.expert_mode)

        self.aile_axis_spin.setValue(cfg.axis_map["AILE"])
        self.elev_axis_spin.setValue(cfg.axis_map["ELEV"])
        self.thro_axis_spin.setValue(cfg.axis_map["THRO"])
        self.rudd_axis_spin.setValue(cfg.axis_map["RUDD"])

        self.gui_gimbal_size_spin.setValue(cfg.gui_gimbal_size)
        self.gui_stick_zone_spin.setValue(cfg.gui_stick_zone)
        self.gui_stick_radius_spin.setValue(cfg.gui_stick_radius)
        self.gui_stick_outline_width_spin.setValue(cfg.gui_stick_outline_width)
        self.gui_zone_outline_width_spin.setValue(cfg.gui_zone_outline_width)
        self.gui_gimbal_border_width_spin.setValue(cfg.gui_gimbal_border_width)
        self.gui_gimbal_cross_width_spin.setValue(cfg.gui_gimbal_cross_width)

        self.colors = {
            "screen_background": cfg.screen_background,
            "gimbal_background": cfg.gimbal_background,
            "stick_outline": cfg.stick_outline,
            "stick_fill": cfg.stick_fill,
            "zone_idle_outline": cfg.zone_idle_outline,
            "zone_idle_fill": cfg.zone_idle_fill,
            "zone_ok_outline": cfg.zone_ok_outline,
            "zone_ok_fill": cfg.zone_ok_fill,
            "grid_color": cfg.grid_color,
            "label_color": cfg.label_color,
            "prompt_color": cfg.prompt_color,
        }
        self._refresh_color_buttons()

    def _append_joystick_text(self, text: str) -> None:
        self.joystick_status.setPlainText(text)

    def _start_joystick_test(self) -> None:
        self._stop_joystick_test(clear_text=False)
        try:
            if not pygame.get_init():
                pygame.init()
            if not pygame.joystick.get_init():
                pygame.joystick.init()

            count = pygame.joystick.get_count()
            if count <= 0:
                self._append_joystick_text("No joystick detected.")
                return

            self.joystick = pygame.joystick.Joystick(0)
            self.joystick.init()
            self.joystick_active = True
            self.timer.start(50)
        except Exception as exc:
            self._append_joystick_text(f"Joystick start failed: {exc}")

    def _poll_joystick(self) -> None:
        if not self.joystick_active or self.joystick is None:
            return

        try:
            pygame.event.pump()

            lines = [
                f"Joystick name: {self.joystick.get_name()}",
                f"Axes: {self.joystick.get_numaxes()}",
                f"Buttons: {self.joystick.get_numbuttons()}",
                "",
            ]

            for i in range(self.joystick.get_numaxes()):
                value = self.joystick.get_axis(i)
                lines.append(f"Axis {i}: {value:+.4f}")

            self._append_joystick_text("\n".join(lines))
        except Exception as exc:
            self._append_joystick_text(f"Joystick polling failed: {exc}")
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
        except Exception:
            pass

        try:
            pygame.quit()
        except Exception:
            pass

        if clear_text:
            self._append_joystick_text("Joystick test stopped.")

    def _update_preview(self) -> None:
        self.preview_status.setText("Preview refresh requested. Embedded live preview will be added next.")
        
    def apply_scope_config(self, cfg: ScopeConfig, common_page) -> None:
        common_page.load_common_dict(
            {
                "user": cfg.user,
                "fullscreen": cfg.fullscreen,
                "topmost": cfg.topmost,
                "debug_output": getattr(cfg, "debug_output", False),
                "fps": cfg.fps,
                "joystick_index": cfg.joystick_index,
                "break_axis": cfg.break_axis,
                "output_root": cfg.output_root,
                "profile_name": cfg.profile_name,
                "use_dated_subfolders": cfg.use_dated_subfolders,
                "save_raw_log": cfg.save_raw_log,
                "save_action_log": cfg.save_action_log,
                "save_step_file": cfg.save_step_file,
                "save_graph_pdf": cfg.save_graph_pdf,
                "auto_open_graph": cfg.auto_open_graph,
                "run_evaluation": cfg.run_evaluation,
                "show_graph": cfg.show_graph,
            }
        )
        self.load_scope_config(cfg)