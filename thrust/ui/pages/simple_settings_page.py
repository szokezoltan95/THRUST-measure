from __future__ import annotations

from PyQt6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from simple.simple_config import SimpleConfig


class SimpleSettingsPage(QWidget):
    """Offline SimPLE test parameters; local joystick and output remain in Runtime settings."""

    def __init__(self) -> None:
        super().__init__()
        self._build_controls()
        self._build_ui()
        self.load_simple_config(SimpleConfig())

    def _spin(self, low: float, high: float, value: float, decimals: int = 0, step: float = 1.0):
        control = QDoubleSpinBox() if decimals else QSpinBox()
        control.setRange(int(low) if not decimals else low, int(high) if not decimals else high)
        if decimals:
            control.setDecimals(decimals)
            control.setSingleStep(step)
        control.setValue(value)
        control.setMaximumWidth(150)
        return control

    def _build_controls(self) -> None:
        self.sampling_hz = self._spin(20, 500, 100)
        self.timeout_s = self._spin(0.1, 60, 5.0, 2, 0.1)
        self.hold_s = self._spin(0.1, 30, 1.0, 2, 0.1)
        self.countdown_s = self._spin(0, 60, 3)
        self.zoom = self._spin(50, 2000, 500, 1, 10)
        self.target_radius = self._spin(10, 1000, 100, 1, 5)
        self.completion_radius = self._spin(0.01, 2.0, 0.1, 2, 0.01)
        self.x_limit = self._spin(0.1, 20, 1.5, 2, 0.1)
        self.y_limit = self._spin(0.1, 20, 2.0, 2, 0.1)
        self.field_width = self._spin(600, 4000, 1500)
        self.field_height = self._spin(400, 3000, 1000)
        self.mass = self._spin(0.1, 10, 0.8, 2, 0.1)
        self.max_thrust = self._spin(1, 100, 16.0, 2, 0.5)
        self.drag = self._spin(0, 5, 0.3, 3, 0.05)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabWidget()
        root.addWidget(self.tabs)

        task = QWidget()
        task_layout = QVBoxLayout(task)
        task_group = QGroupBox("SimPLE task")
        task_form = QFormLayout(task_group)
        task_form.addRow("Sampling frequency [Hz]:", self.sampling_hz)
        task_form.addRow("Target timeout [s]:", self.timeout_s)
        task_form.addRow("Hold in target [s]:", self.hold_s)
        task_form.addRow("Countdown [s]:", self.countdown_s)
        task_form.addRow("Target acceptance radius [m]:", self.completion_radius)
        task_layout.addWidget(task_group)
        task_layout.addStretch()
        self.tabs.addTab(task, "Task")

        world = QWidget()
        world_layout = QVBoxLayout(world)
        world_group = QGroupBox("2D world and dynamics")
        world_form = QFormLayout(world_group)
        world_form.addRow("Zoom [px/m]:", self.zoom)
        world_form.addRow("Target zone radius [px]:", self.target_radius)
        world_form.addRow("Horizontal target limit [m]:", self.x_limit)
        world_form.addRow("Maximum target height [m]:", self.y_limit)
        world_form.addRow("World width [px]:", self.field_width)
        world_form.addRow("World height [px]:", self.field_height)
        world_form.addRow("Copter mass [kg]:", self.mass)
        world_form.addRow("Maximum thrust [N]:", self.max_thrust)
        world_form.addRow("Quadratic drag coefficient:", self.drag)
        world_layout.addWidget(world_group)
        world_layout.addStretch()
        self.tabs.addTab(world, "World and physics")

    def load_simple_config(self, config: SimpleConfig) -> None:
        self.sampling_hz.setValue(config.sampling_hz)
        self.timeout_s.setValue(config.action_timeout_s)
        self.hold_s.setValue(config.hold_time_s)
        self.countdown_s.setValue(config.countdown_s)
        self.zoom.setValue(config.zoom_px_per_m)
        self.target_radius.setValue(config.target_zone_radius_px)
        self.completion_radius.setValue(config.completion_radius_m)
        self.x_limit.setValue(config.target_x_limit_m)
        self.y_limit.setValue(config.target_y_max_m)
        self.field_width.setValue(config.field_width_px)
        self.field_height.setValue(config.field_height_px)
        self.mass.setValue(config.mass_kg)
        self.max_thrust.setValue(config.max_thrust_n)
        self.drag.setValue(config.drag_coefficient)

    def build_simple_config(self) -> SimpleConfig:
        config = SimpleConfig(
            sampling_hz=self.sampling_hz.value(),
            action_timeout_s=self.timeout_s.value(),
            hold_time_s=self.hold_s.value(),
            countdown_s=self.countdown_s.value(),
            zoom_px_per_m=self.zoom.value(),
            target_zone_radius_px=self.target_radius.value(),
            completion_radius_m=self.completion_radius.value(),
            target_x_limit_m=self.x_limit.value(),
            target_y_max_m=self.y_limit.value(),
            field_width_px=self.field_width.value(),
            field_height_px=self.field_height.value(),
            mass_kg=self.mass.value(),
            max_thrust_n=self.max_thrust.value(),
            drag_coefficient=self.drag.value(),
        )
        config.validate()
        return config
