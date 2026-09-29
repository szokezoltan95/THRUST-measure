from __future__ import annotations

from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QComboBox, QColorDialog, QDoubleSpinBox, QFormLayout, QGroupBox, QLabel,
    QPushButton, QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)

from simple.simple_config import SimpleConfig


RESOLUTIONS = [
    ("1920 × 1080 · 16:9", 1920, 1080), ("2560 × 1440 · 16:9", 2560, 1440),
    ("1280 × 720 · 16:9", 1280, 720), ("1920 × 1200 · 16:10", 1920, 1200),
    ("1280 × 800 · 16:10", 1280, 800), ("1280 × 1024 · 5:4", 1280, 1024),
    ("1024 × 768 · 4:3", 1024, 768),
]


class SimpleSettingsPage(QWidget):
    """Offline SimPLE test parameters; joystick and output remain local runtime settings."""

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
        control.setMaximumWidth(180)
        return control

    def _build_controls(self) -> None:
        self.timeout_s = self._spin(.1, 60, 5, 2, .1)
        self.hold_s = self._spin(.1, 30, 1, 2, .1)
        self.countdown_s = self._spin(0, 60, 3)
        self.completion_radius = self._spin(.01, 2, .1, 2, .01)
        self.x_limit = self._spin(.1, 20, 1.5, 2, .1)
        self.y_limit = self._spin(.1, 20, 2, 2, .1)
        self.resolution = QComboBox()
        for label, width, height in RESOLUTIONS:
            self.resolution.addItem(label, (width, height))
        self.world_width = self._spin(.5, 50, 4.5, 2, .1)
        self.world_height = QLabel("2.53 m")
        self.resolution.currentIndexChanged.connect(self._update_derived_height)
        self.world_width.valueChanged.connect(self._update_derived_height)
        self.mass = self._spin(.1, 10, .8, 2, .1)
        self.max_thrust = self._spin(1, 100, 16, 2, .5)
        self.drag = self._spin(0, 5, .3, 3, .05)
        self.zone_idle_fill = self._color_button("#ff3948")
        self.zone_idle_outline = self._color_button("#ff3948")
        self.zone_ok_fill = self._color_button("#00cc66")
        self.zone_ok_outline = self._color_button("#00ff80")

    def _color_button(self, color: str) -> QPushButton:
        button = QPushButton(color)
        button.setProperty("hex_color", color)
        button.setStyleSheet(f"background-color: {color}; color: {self._contrast_text(color)}; font-weight: 600; padding: 6px 12px;")
        button.clicked.connect(lambda _checked=False, control=button: self._choose_color(control))
        return button

    def _choose_color(self, button: QPushButton) -> None:
        current = QColor(str(button.property("hex_color")))
        selected = QColorDialog.getColor(
            current,
            self,
            "Vybrať farbu zóny",
            QColorDialog.ColorDialogOption.DontUseNativeDialog,
        )
        if selected.isValid():
            value = selected.name()
            button.setProperty("hex_color", value)
            button.setText(value)
            button.setStyleSheet(f"background-color: {value}; color: {self._contrast_text(value)}; font-weight: 600; padding: 6px 12px;")

    @staticmethod
    def _contrast_text(value: str) -> str:
        color = value.lstrip("#")
        brightness = (int(color[0:2], 16) * 299 + int(color[2:4], 16) * 587 + int(color[4:6], 16) * 114) / 1000
        return "#101820" if brightness > 150 else "#ffffff"

    def _update_derived_height(self, *_args) -> None:
        size = self.resolution.currentData()
        if size:
            self.world_height.setText(f"{self.world_width.value() * size[1] / size[0]:.2f} m")

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabWidget()
        root.addWidget(self.tabs)
        task = QWidget()
        task_layout = QVBoxLayout(task)
        task_group = QGroupBox("SimPLE task")
        task_form = QFormLayout(task_group)
        task_form.addRow("Target timeout [s]:", self.timeout_s)
        task_form.addRow("Hold in target [s]:", self.hold_s)
        task_form.addRow("Countdown [s]:", self.countdown_s)
        task_form.addRow("Target acceptance radius [m]:", self.completion_radius)
        task_form.addRow(QLabel("Target zone radius uses the same meter scale as the flight simulation."))
        task_layout.addWidget(task_group)
        task_layout.addStretch()
        self.tabs.addTab(task, "Task")
        world = QWidget()
        world_layout = QVBoxLayout(world)
        world_group = QGroupBox("2D world and dynamics")
        world_form = QFormLayout(world_group)
        world_form.addRow("Screen resolution / aspect ratio:", self.resolution)
        world_form.addRow("World width [m]:", self.world_width)
        world_form.addRow("Derived world height:", self.world_height)
        world_form.addRow("Horizontal target limit [m]:", self.x_limit)
        world_form.addRow("Maximum target height [m]:", self.y_limit)
        world_form.addRow("Copter mass [kg]:", self.mass)
        world_form.addRow("Maximum thrust [N]:", self.max_thrust)
        world_form.addRow("Quadratic drag coefficient:", self.drag)
        world_form.addRow("Zone fill:", self.zone_idle_fill)
        world_form.addRow("Zone outline:", self.zone_idle_outline)
        world_form.addRow("Success fill:", self.zone_ok_fill)
        world_form.addRow("Success outline:", self.zone_ok_outline)
        world_layout.addWidget(world_group)
        world_layout.addStretch()
        self.tabs.addTab(world, "World and physics")

    def load_simple_config(self, config: SimpleConfig) -> None:
        self.timeout_s.setValue(config.action_timeout_s)
        self.hold_s.setValue(config.hold_time_s)
        self.countdown_s.setValue(config.countdown_s)
        self.completion_radius.setValue(config.completion_radius_m)
        self.x_limit.setValue(config.target_x_limit_m)
        self.y_limit.setValue(config.target_y_max_m)
        self.world_width.setValue(config.world_width_m)
        selected = None
        for index in range(self.resolution.count()):
            if self.resolution.itemData(index) == (config.field_width_px, config.field_height_px):
                selected = index
                break
        if selected is None:
            size = (config.field_width_px, config.field_height_px)
            self.resolution.addItem(f"{size[0]} × {size[1]} · aktuálne", size)
            selected = self.resolution.count() - 1
        self.resolution.setCurrentIndex(selected)
        self.mass.setValue(config.mass_kg)
        self.max_thrust.setValue(config.max_thrust_n)
        self.drag.setValue(config.drag_coefficient)
        for control, color in ((self.zone_idle_fill, config.zone_idle_fill), (self.zone_idle_outline, config.zone_idle_outline), (self.zone_ok_fill, config.zone_ok_fill), (self.zone_ok_outline, config.zone_ok_outline)):
            control.setProperty("hex_color", color)
            control.setText(color)
            control.setStyleSheet(f"background-color: {color}; color: {self._contrast_text(color)}; font-weight: 600; padding: 6px 12px;")
        self._update_derived_height()

    def build_simple_config(self) -> SimpleConfig:
        width, height = self.resolution.currentData()
        config = SimpleConfig(
            action_timeout_s=self.timeout_s.value(), hold_time_s=self.hold_s.value(),
            countdown_s=self.countdown_s.value(), completion_radius_m=self.completion_radius.value(),
            target_x_limit_m=self.x_limit.value(), target_y_max_m=self.y_limit.value(),
            field_width_px=width, field_height_px=height, world_width_m=self.world_width.value(),
            mass_kg=self.mass.value(), max_thrust_n=self.max_thrust.value(), drag_coefficient=self.drag.value(),
            zone_idle_fill=str(self.zone_idle_fill.property("hex_color")),
            zone_idle_outline=str(self.zone_idle_outline.property("hex_color")),
            zone_ok_fill=str(self.zone_ok_fill.property("hex_color")),
            zone_ok_outline=str(self.zone_ok_outline.property("hex_color")),
        )
        config.validate()
        return config
