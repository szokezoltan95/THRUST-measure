"""Live joystick axis preview and local channel assignment."""
from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QPainter, QPalette, QPen
from PyQt6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget,
)


CHANNELS = ("LX", "LY", "RY", "RX", "BREAK", "RESET")


class AxisMeter(QWidget):
    """A centered gauge: negative movement fills left, positive fills right."""

    def __init__(self) -> None:
        super().__init__()
        self.value = 0.0
        self.setMinimumSize(150, 28)

    def set_value(self, value: float) -> None:
        self.value = max(-1.0, min(1.0, value))
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        track = QRectF(self.rect()).adjusted(2, 5, -2, -5)
        palette = self.palette()
        painter.setPen(QPen(palette.color(QPalette.ColorRole.Mid), 1))
        painter.setBrush(palette.color(QPalette.ColorRole.Base))
        painter.drawRoundedRect(track, 5, 5)
        center = track.center().x()
        end = center + self.value * (track.width() / 2 - 3)
        if abs(end - center) > 1:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(palette.color(QPalette.ColorRole.Highlight))
            painter.drawRoundedRect(QRectF(min(center, end), track.top() + 2,
                                           abs(end - center), track.height() - 4), 2, 2)
        painter.setPen(QPen(palette.color(QPalette.ColorRole.WindowText), 1))
        painter.drawLine(round(center), round(track.top()), round(center), round(track.bottom()))
        painter.end()


class AxisAssignmentDialog(QDialog):
    def __init__(self, common_page, mapping: dict[str, int], parent: QWidget) -> None:
        super().__init__(parent)
        self.common_page = common_page
        self.mapping = dict(mapping)
        self.axis_count = -1
        self.meters: list[AxisMeter] = []
        self.value_labels: list[QLabel] = []
        self.setWindowTitle("Joystick axis assignment")
        self.resize(700, 670)
        self.setMinimumWidth(560)

        root = QVBoxLayout(self)
        self.device_label = QLabel()
        root.addWidget(self.device_label)

        preview = QGroupBox("Available axes · move a control to identify its axis")
        preview_layout = QVBoxLayout(preview)
        self.axis_scroll = QScrollArea()
        self.axis_scroll.setWidgetResizable(True)
        self.axis_scroll.setMinimumHeight(180)
        self.axis_scroll.setMaximumHeight(340)
        self.axis_container = QWidget()
        self.axis_grid = QGridLayout(self.axis_container)
        self.axis_grid.setSpacing(10)
        self.axis_scroll.setWidget(self.axis_container)
        preview_layout.addWidget(self.axis_scroll)
        root.addWidget(preview, 1)

        assignment = QGroupBox("Channel assignment")
        assignment_grid = QGridLayout(assignment)
        self.selectors: dict[str, QComboBox] = {}
        for index, role in enumerate(CHANNELS):
            row, column = divmod(index, 2)
            label = QLabel(f"{role}:")
            selector = QComboBox()
            selector.setMinimumWidth(175)
            selector.currentIndexChanged.connect(self._validate)
            self.selectors[role] = selector
            assignment_grid.addWidget(label, row, column * 2)
            assignment_grid.addWidget(selector, row, column * 2 + 1)
        root.addWidget(assignment)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)

        self._update_values(common_page.latest_axis_values)
        common_page.joystick_values_changed.connect(self._update_values)

    def _update_values(self, values: object) -> None:
        joystick = self.common_page.joystick
        connected = self.common_page.joystick_active and joystick is not None
        try:
            count = max(0, int(joystick.get_numaxes())) if connected else 0
            name = joystick.get_name() if connected else "No joystick connected"
        except Exception:
            count, name = 0, "No joystick connected"
        if count != self.axis_count:
            self._rebuild_axes(count)
        self.device_label.setText(f"{name} · {count} axes" if count else "Connect a joystick to view and assign axes.")
        values = values if isinstance(values, list) else []
        for index, (meter, label) in enumerate(zip(self.meters, self.value_labels)):
            value = float(values[index]) if index < len(values) else 0.0
            meter.set_value(value)
            label.setText(f"{value:+.3f}")

    def _rebuild_axes(self, count: int) -> None:
        self.axis_count = count
        while self.axis_grid.count():
            item = self.axis_grid.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        self.meters.clear()
        self.value_labels.clear()
        if not count:
            self.axis_grid.addWidget(QLabel("No axes available."), 0, 0)
        for index in range(count):
            card = QWidget()
            row = QHBoxLayout(card)
            row.setContentsMargins(4, 4, 4, 4)
            label = QLabel(f"Axis {index}")
            label.setMinimumWidth(58)
            meter = AxisMeter()
            value_label = QLabel("+0.000")
            value_label.setMinimumWidth(56)
            row.addWidget(label)
            row.addWidget(meter, 1)
            row.addWidget(value_label)
            self.axis_grid.addWidget(card, index // 2, index % 2)
            self.meters.append(meter)
            self.value_labels.append(value_label)

        for role, selector in self.selectors.items():
            selected = selector.currentData()
            if selected is None:
                selected = self.mapping[role]
            selector.blockSignals(True)
            selector.clear()
            for index in range(count):
                selector.addItem(f"Axis {index}", index)
            if count and selected >= count:
                selector.addItem(f"Axis {selected} (unavailable)", selected)
            selector.setCurrentIndex(selector.findData(selected))
            selector.setEnabled(bool(count))
            selector.blockSignals(False)
        self._validate()

    def _validate(self, _index: int = -1) -> None:
        valid = self.axis_count > 0 and all(
            isinstance(selector.currentData(), int) and 0 <= selector.currentData() < self.axis_count
            for selector in self.selectors.values()
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(valid)

    def values(self) -> dict[str, int]:
        return {role: int(selector.currentData()) for role, selector in self.selectors.items()}

    def stop(self) -> None:
        try:
            self.common_page.joystick_values_changed.disconnect(self._update_values)
        except TypeError:
            pass

    def closeEvent(self, event) -> None:
        self.stop()
        super().closeEvent(event)
