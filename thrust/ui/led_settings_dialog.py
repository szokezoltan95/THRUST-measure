"""Locally stored radio LED colors and brightness animations."""
from __future__ import annotations

from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (QColorDialog, QComboBox, QDialog, QDialogButtonBox,
                             QGridLayout, QLabel, QPushButton, QVBoxLayout)

from thrust.tx16smk3_led import ANIMATIONS, LedStyle

LABELS = {
    "idle": "Idle / measurement not ready",
    "ready": "Measurement ready",
    "countdown": "Countdown",
    "out_of_zone": "Measuring · outside zone",
    "in_zone": "Measuring · inside zone",
}


class LedSettingsDialog(QDialog):
    def __init__(self, styles: dict[str, LedStyle], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("TX16SMK3 lights")
        self.setMinimumWidth(480)
        self.colors = {state: QColor(style.color) for state, style in styles.items()}
        self.selectors = {}
        self.buttons = {}
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Both LED rings use the same color. Animations vary brightness."))
        grid = QGridLayout()
        grid.addWidget(QLabel("State"), 0, 0)
        grid.addWidget(QLabel("Color"), 0, 1)
        grid.addWidget(QLabel("Animation"), 0, 2)
        for row, (state, label) in enumerate(LABELS.items(), 1):
            button = QPushButton()
            button.clicked.connect(lambda _, key=state: self._pick_color(key))
            self.buttons[state] = button
            self._paint_button(state)
            selector = QComboBox()
            for animation in ANIMATIONS:
                selector.addItem(animation.capitalize(), animation)
            selector.setCurrentIndex(selector.findData(styles[state].animation))
            self.selectors[state] = selector
            grid.addWidget(QLabel(label), row, 0)
            grid.addWidget(button, row, 1)
            grid.addWidget(selector, row, 2)
        layout.addLayout(grid)
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
