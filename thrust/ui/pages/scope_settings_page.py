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

        self.points_per_axis_spin = QSpinBox()
        self.points_per_axis_spin.setRange(2, 101)
        self.points_per_axis_spin.setValue(9)
        self.min_changed_axes_spin = QSpinBox()
        self.min_changed_axes_spin.setRange(1, 4)
        self.min_changed_axes_spin.setValue(1)
        self.max_changed_axes_spin = QSpinBox()
        self.max_changed_axes_spin.setRange(1, 4)
        self.max_changed_axes_spin.setValue(2)
        self.single_gimbal_probability_spin = QDoubleSpinBox()
        self.single_gimbal_probability_spin.setRange(0, 100)
        self.single_gimbal_probability_spin.setSuffix(" %")
        self.single_gimbal_probability_spin.setValue(50)
        self.interval_spins: dict[str, tuple[QDoubleSpinBox, QDoubleSpinBox]] = {}
        for axis in ("LX", "LY", "RY", "RX"):
            low, high = QDoubleSpinBox(), QDoubleSpinBox()
            for spin in (low, high):
                spin.setRange(-1, 1)
                spin.setDecimals(2)
                spin.setSingleStep(0.05)
                spin.setMaximumWidth(110)
            low.setValue(-0.8)
            high.setValue(0.8)
            self.interval_spins[axis] = (low, high)

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

        basic = QWidget()
        basic_layout = QGridLayout(basic)
        task_group = QGroupBox("Test parameters")
        task_form = QFormLayout(task_group)
        task_form.addRow("Sampling frequency [Hz]:", self.fps_spin)
        task_form.addRow("Action timeout [s]:", self.timeout_spin)
        task_form.addRow("Hold time [s]:", self.hold_time_spin)
        task_form.addRow("Stick max:", self.stick_max_spin)
        task_form.addRow("Completed actions:", self.max_actions_spin)
        task_form.addRow("Countdown [s]:", self.countdown_spin)
        task_form.addRow("Random seed:", self.seed_edit)
        basic_layout.addWidget(task_group, 0, 0)
        geometry_group = QGroupBox("Geometry")
        geometry_form = QFormLayout(geometry_group)
        geometry_form.addRow("Gimbal size [px]:", self.gui_gimbal_size_spin)
        geometry_form.addRow("Target zone radius:", self.gui_stick_zone_spin)
        geometry_form.addRow("Stick radius:", self.gui_stick_radius_spin)
        geometry_form.addRow("Stick outline width:", self.gui_stick_outline_width_spin)
        geometry_form.addRow("Zone outline width:", self.gui_zone_outline_width_spin)
        geometry_form.addRow("Gimbal border width:", self.gui_gimbal_border_width_spin)
        geometry_form.addRow("Cross width:", self.gui_gimbal_cross_width_spin)

        basic_layout.addWidget(geometry_group, 0, 1)
        basic_layout.addWidget(QLabel("Joystick hardware, axis mapping and output paths are local runtime settings."), 1, 0, 1, 2)
        basic_layout.setRowStretch(2, 1)

        actions = QWidget()
        actions_layout = QGridLayout(actions)
        action_group = QGroupBox("Random target generation")
        action_form = QFormLayout(action_group)
        action_form.addRow("Possible points per axis:", self.points_per_axis_spin)
        interval_grid = QGridLayout()
        interval_grid.addWidget(QLabel("Axis"), 0, 0)
        interval_grid.addWidget(QLabel("Minimum"), 0, 1)
        interval_grid.addWidget(QLabel("Maximum"), 0, 2)
        for row, (axis, (low, high)) in enumerate(self.interval_spins.items(), start=1):
            interval_grid.addWidget(QLabel(axis), row, 0)
            interval_grid.addWidget(low, row, 1)
            interval_grid.addWidget(high, row, 2)
        action_form.addRow("Normalized intervals:", interval_grid)
        action_form.addRow("Minimum changed axes:", self.min_changed_axes_spin)
        action_form.addRow("Maximum changed axes:", self.max_changed_axes_spin)
        action_form.addRow("Only one gimbal changes:", self.single_gimbal_probability_spin)
        actions_layout.addWidget(action_group, 0, 0)
        actions_layout.addWidget(QLabel("A changed axis means its target differs from the previous target. Zero is a regular target value; no automatic return to centre is inserted."), 1, 0)
        actions_layout.setRowStretch(2, 1)

        colors = QWidget()
        colors_layout = QGridLayout(colors)
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

        colors_layout.addWidget(color_group, 0, 0)
        colors_layout.setColumnStretch(0, 1)

        self.tabs.addTab(basic, "Basic settings")
        self.tabs.addTab(actions, "Actions")
        self.tabs.addTab(colors, "Colors")

    def _pick_color(self, key: str) -> None:
        color = QColorDialog.getColor(options=QColorDialog.ColorDialogOption.DontUseNativeDialog)
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
            action_timeout_s=self.timeout_spin.value(),
            hold_time_s=self.hold_time_spin.value(),
            fps=self.fps_spin.value(),
            stick_max=self.stick_max_spin.value(),
            deadzone=common_data.get("deadzone", [100, 100, 100, 100]),
            max_completed_actions=self.max_actions_spin.value(),
            countdown_s=self.countdown_spin.value(),
            seed=int(seed_text) if seed_text else None,
            action_settings={
                "generator_version": 1,
                "intervals": {
                    axis: [bounds[0].value(), bounds[1].value()]
                    for axis, bounds in self.interval_spins.items()
                },
                "points_per_axis": self.points_per_axis_spin.value(),
                "min_changed_axes": self.min_changed_axes_spin.value(),
                "max_changed_axes": self.max_changed_axes_spin.value(),
                "single_gimbal_probability": self.single_gimbal_probability_spin.value() / 100,
            },
            fullscreen=common_data["fullscreen"],
            topmost=common_data["topmost"],
            debug_output=common_data["debug_output"],
            joystick_index=common_data["joystick_index"],
            break_axis=common_data["break_axis"],
            reset_axis=common_data["reset_axis"],
            axis_map=common_data["axis_map"],
            output_root=common_data["output_root"],
            profile_name=common_data.get("profile_name", "local"),
            use_dated_subfolders=common_data["use_dated_subfolders"],
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
        self.timeout_spin.setValue(cfg.action_timeout_s)
        self.fps_spin.setValue(cfg.fps)
        self.hold_time_spin.setValue(cfg.hold_time_s)
        self.stick_max_spin.setValue(cfg.stick_max)
        self.max_actions_spin.setValue(cfg.max_completed_actions)
        self.countdown_spin.setValue(cfg.countdown_s)
        self.seed_edit.setText("" if cfg.seed is None else str(cfg.seed))
        action_settings = cfg.action_settings
        for axis, bounds in self.interval_spins.items():
            low, high = action_settings["intervals"][axis]
            bounds[0].setValue(low)
            bounds[1].setValue(high)
        self.points_per_axis_spin.setValue(action_settings["points_per_axis"])
        self.min_changed_axes_spin.setValue(action_settings["min_changed_axes"])
        self.max_changed_axes_spin.setValue(action_settings["max_changed_axes"])
        self.single_gimbal_probability_spin.setValue(action_settings["single_gimbal_probability"] * 100)
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
