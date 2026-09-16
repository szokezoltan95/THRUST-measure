from __future__ import annotations

from PyQt6.QtWidgets import (
    QColorDialog,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from scope.scope_config import ScopeConfig


class ScopeSettingsPage(QWidget):
    """Offline test configuration: the same test-owned settings as WebDB."""

    def __init__(self) -> None:
        super().__init__()
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

        self.fps_spin = QSpinBox()
        self.fps_spin.setRange(10, 1000)
        self.fps_spin.setValue(100)
        self.fps_spin.setMaximumWidth(110)

        self.hold_time_spin = QDoubleSpinBox()
        self.hold_time_spin.setRange(0.1, 60.0)
        self.hold_time_spin.setDecimals(2)
        self.hold_time_spin.setValue(0.5)
        self.hold_time_spin.setMaximumWidth(110)

        self.stick_max_spin = QSpinBox()
        self.stick_max_spin.setRange(100, 5000)
        self.stick_max_spin.setValue(1000)
        self.stick_max_spin.setMaximumWidth(110)

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

        for name, value in {
            "gui_gimbal_size": (150, 2000, 500),
            "gui_stick_zone": (10, 1000, 200),
            "gui_stick_radius": (1, 100, 20),
            "gui_stick_outline_width": (1, 30, 6),
            "gui_zone_outline_width": (1, 30, 8),
            "gui_gimbal_border_width": (1, 40, 12),
            "gui_gimbal_cross_width": (1, 20, 6),
        }.items():
            spin = QSpinBox()
            spin.setRange(value[0], value[1])
            spin.setValue(value[2])
            spin.setMaximumWidth(110)
            setattr(self, f"{name}_spin", spin)

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
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabWidget()
        root.addWidget(self.tabs)

        experiment = QWidget()
        experiment_layout = QGridLayout(experiment)
        task_group = QGroupBox("Test parameters")
        task_form = QFormLayout(task_group)
        task_form.addRow("Difficulty:", self.difficulty_edit)
        task_form.addRow("Sampling frequency [Hz]:", self.fps_spin)
        task_form.addRow("Action timeout [s]:", self.timeout_spin)
        task_form.addRow("Hold time [s]:", self.hold_time_spin)
        task_form.addRow("Stick max:", self.stick_max_spin)
        task_form.addRow("Completed actions:", self.max_actions_spin)
        task_form.addRow("Countdown [s]:", self.countdown_spin)
        task_form.addRow("Random seed:", self.seed_edit)
        experiment_layout.addWidget(task_group, 0, 0)
        experiment_layout.addWidget(QLabel("Joystick hardware, axis mapping and output paths are local runtime settings."), 1, 0)
        experiment_layout.setRowStretch(2, 1)

        appearance = QWidget()
        appearance_layout = QGridLayout(appearance)
        geometry_group = QGroupBox("Geometry")
        geometry_form = QFormLayout(geometry_group)
        geometry_form.addRow("Gimbal size [px]:", self.gui_gimbal_size_spin)
        geometry_form.addRow("Target zone radius:", self.gui_stick_zone_spin)
        geometry_form.addRow("Stick radius:", self.gui_stick_radius_spin)
        geometry_form.addRow("Stick outline width:", self.gui_stick_outline_width_spin)
        geometry_form.addRow("Zone outline width:", self.gui_zone_outline_width_spin)
        geometry_form.addRow("Gimbal border width:", self.gui_gimbal_border_width_spin)
        geometry_form.addRow("Cross width:", self.gui_gimbal_cross_width_spin)

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
            button = QPushButton()
            button.clicked.connect(lambda _, selected=key: self._pick_color(selected))
            self.color_buttons[key] = button
            color_grid.addWidget(QLabel(label), row, 0)
            color_grid.addWidget(button, row, 1)

        appearance_layout.addWidget(geometry_group, 0, 0)
        appearance_layout.addWidget(color_group, 0, 1)
        appearance_layout.setColumnStretch(1, 1)

        self.tabs.addTab(experiment, "Test configuration")
        self.tabs.addTab(appearance, "Appearance")

    def _pick_color(self, key: str) -> None:
        color = QColorDialog.getColor()
        if color.isValid():
            self.colors[key] = color.name()
            self._refresh_color_buttons()

    def _refresh_color_buttons(self) -> None:
        for key, button in self.color_buttons.items():
            value = self.colors[key]
            button.setText(value)
            button.setStyleSheet(
                f"QPushButton {{ background-color: {value}; color: {'#000000' if self._brightness(value) > 150 else '#ffffff'}; padding: 6px 10px; }}"
            )

    @staticmethod
    def _brightness(value: str) -> float:
        value = value.lstrip("#")
        return (int(value[0:2], 16) * 299 + int(value[2:4], 16) * 587 + int(value[4:6], 16) * 114) / 1000

    def build_scope_config(self, common) -> ScopeConfig:
        seed_text = self.seed_edit.text().strip()
        common_data = common.export_common_dict()
        return ScopeConfig(
            user=common_data["user"],
            difficulty=self.difficulty_edit.text().strip().lower() or "hard",
            action_timeout_s=self.timeout_spin.value(),
            hold_time_s=self.hold_time_spin.value(),
            fps=self.fps_spin.value(),
            stick_max=self.stick_max_spin.value(),
            deadzone=common_data.get("deadzone", [100, 100, 100, 100]),
            max_completed_actions=self.max_actions_spin.value(),
            countdown_s=self.countdown_spin.value(),
            seed=int(seed_text) if seed_text else None,
            fullscreen=common_data["fullscreen"],
            topmost=common_data["topmost"],
            debug_output=common_data["debug_output"],
            joystick_index=common_data["joystick_index"],
            break_axis=common_data["break_axis"],
            axis_map=common_data["axis_map"],
            output_root=common_data["output_root"],
            profile_name=common_data.get("profile_name", "local"),
            use_dated_subfolders=common_data["use_dated_subfolders"],
            save_raw_log=common_data["save_raw_log"],
            save_action_log=common_data["save_action_log"],
            save_step_file=common_data["save_step_file"],
            save_graph_pdf=common_data["save_graph_pdf"],
            auto_open_graph=common_data["auto_open_graph"],
            run_evaluation=common_data["run_evaluation"],
            show_graph=common_data["show_graph"],
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
        self.fps_spin.setValue(cfg.fps)
        self.hold_time_spin.setValue(cfg.hold_time_s)
        self.stick_max_spin.setValue(cfg.stick_max)
        self.max_actions_spin.setValue(cfg.max_completed_actions)
        self.countdown_spin.setValue(cfg.countdown_s)
        self.seed_edit.setText("" if cfg.seed is None else str(cfg.seed))
        self.gui_gimbal_size_spin.setValue(cfg.gui_gimbal_size)
        self.gui_stick_zone_spin.setValue(cfg.gui_stick_zone)
        self.gui_stick_radius_spin.setValue(cfg.gui_stick_radius)
        self.gui_stick_outline_width_spin.setValue(cfg.gui_stick_outline_width)
        self.gui_zone_outline_width_spin.setValue(cfg.gui_zone_outline_width)
        self.gui_gimbal_border_width_spin.setValue(cfg.gui_gimbal_border_width)
        self.gui_gimbal_cross_width_spin.setValue(cfg.gui_gimbal_cross_width)
        self.colors = {key: getattr(cfg, key) for key in self.colors}
        self._refresh_color_buttons()

    def apply_scope_config(self, cfg: ScopeConfig, common_page) -> None:
        # WebDB owns test parameters only. Local runtime/joystick/output controls stay untouched.
        self.load_scope_config(cfg)
