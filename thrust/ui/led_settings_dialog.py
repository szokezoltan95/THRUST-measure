"""Locally stored radio LED colors and brightness animations."""
from __future__ import annotations

from PyQt6.QtGui import QColor
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QColorDialog, QComboBox, QDialog, QDialogButtonBox,
                             QGridLayout, QHBoxLayout, QLabel, QPushButton,
                             QSlider, QVBoxLayout)

from thrust.tx16smk3_led import ANIMATIONS, MODE_STATIC, MODE_TARGET_TRACKING, LedStyle

LABELS = {
    "idle": "Idle / measurement not ready",
    "ready": "Measurement ready",
    "countdown": "Countdown",
    "out_of_zone": "Measuring · outside zone",
    "in_zone": "Measuring · inside zone",
}


class LedSettingsDialog(QDialog):
    def __init__(self, styles: dict[str, LedStyle], parent=None, *,
                 mode: str = MODE_STATIC, refresh_hz: int = 30) -> None:
        super().__init__(parent)
        self.setWindowTitle("TX16SMK3 lights")
        self.setMinimumWidth(480)
        self.colors = {state: QColor(style.color) for state, style in styles.items()}
        self.selectors = {}
        self.buttons = {}
        self.mode_selector = QComboBox()
        self.mode_selector.addItem("Static state colors", MODE_STATIC)
        self.mode_selector.addItem("Target tracking", MODE_TARGET_TRACKING)
        self.mode_selector.setCurrentIndex(max(0, self.mode_selector.findData(mode)))
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("LED behavior"))
        mode_row.addWidget(self.mode_selector, 1)
        layout = QVBoxLayout(self)
        layout.addLayout(mode_row)

        self.static_hint = QLabel("Static colors follow the measurement state below.")
        self.static_hint.setWordWrap(True)
        layout.addWidget(self.static_hint)
        self.tracking_hint = QLabel(
            "Target tracking maps target direction to each ring. The red → yellow → green "
            "fade expands as the stick approaches its target; inside the target zone, the ring is green. "
            "Button LEDs stay off while the full-ring tracking frame is active."
        )
        self.tracking_hint.setWordWrap(True)
        self.tracking_hint.hide()
        layout.addWidget(self.tracking_hint)
        self.static_widgets = []
        layout.addWidget(QLabel("Both rings use the same color in static mode; animations vary brightness."))
        grid = QGridLayout()
        grid.addWidget(QLabel("State"), 0, 0)
        grid.addWidget(QLabel("Color"), 0, 1)
        grid.addWidget(QLabel("Animation"), 0, 2)
        for row, (state, label) in enumerate(LABELS.items(), 1):
            button = QPushButton()
            button.clicked.connect(lambda _, key=state: self._pick_color(key))
            self.buttons[state] = button
            self.static_widgets.append(button)
            self._paint_button(state)
            selector = QComboBox()
            for animation in ANIMATIONS:
                selector.addItem(animation.capitalize(), animation)
            selector.setCurrentIndex(selector.findData(styles[state].animation))
            self.selectors[state] = selector
            self.static_widgets.append(selector)
            grid.addWidget(QLabel(label), row, 0)
            grid.addWidget(button, row, 1)
            grid.addWidget(selector, row, 2)
        layout.addLayout(grid)

        refresh_row = QHBoxLayout()
        refresh_row.addWidget(QLabel("LED refresh rate"))
        self.refresh_slider = QSlider(Qt.Orientation.Horizontal)
        self.refresh_slider.setRange(1, 200)
        self.refresh_slider.setValue(max(1, min(200, int(refresh_hz))))
        self.refresh_slider.setTickInterval(25)
        self.refresh_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.refresh_label = QLabel()
        self.refresh_label.setMinimumWidth(90)
        self.refresh_slider.valueChanged.connect(self._update_refresh_label)
        refresh_row.addWidget(self.refresh_slider, 1)
        refresh_row.addWidget(self.refresh_label)
        layout.addLayout(refresh_row)
        self.refresh_slider.setToolTip(
            "Maximum update rate for target-tracking frames (1–200 Hz). "
            "The actual rate depends on the radio and USB HID response."
        )
        self.mode_selector.currentIndexChanged.connect(self._update_mode_controls)
        self._update_refresh_label(self.refresh_slider.value())
        self._update_mode_controls()
        controls = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        controls.accepted.connect(self.accept)
        controls.rejected.connect(self.reject)
        layout.addWidget(controls)

    def _paint_button(self, state: str) -> None:
        color = self.colors[state]
        self.buttons[state].setText(color.name().upper())
        self.buttons[state].setStyleSheet(f"background: {color.name()}; color: {'black' if color.lightness() > 140 else 'white'};")

    def _pick_color(self, state: str) -> None:
        color = QColorDialog.getColor(self.colors[state], self, f"{LABELS[state]} color")
        if color.isValid():
            self.colors[state] = color
            self._paint_button(state)

    def values(self) -> dict[str, LedStyle]:
        return {state: LedStyle(color.name(), self.selectors[state].currentData())
                for state, color in self.colors.items()}

    def _update_refresh_label(self, value: int) -> None:
        self.refresh_label.setText(f"{value} Hz · {1000 / value:.1f} ms")

    def _update_mode_controls(self, _index: int = -1) -> None:
        static_mode = self.mode_selector.currentData() == MODE_STATIC
        for widget in self.static_widgets:
            widget.setEnabled(static_mode)
        self.static_hint.setVisible(static_mode)
        self.tracking_hint.setVisible(not static_mode)
