from __future__ import annotations

import csv
import json
import os
import sys
from dataclasses import fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PyQt6.QtCore import QSettings, QTimer, Qt
from PyQt6.QtGui import QActionGroup, QColor, QGuiApplication, QPalette
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QAbstractItemView,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from scope.scope_config import ScopeConfig
from simple.simple_config import SimpleConfig
from thrust.analysis.scope_log import analyze_scope_log
from thrust.analysis.simple_log import analyze_simple_log, save_step_graph, write_step_response
from thrust.runners.simple_runner import run_simple
from thrust.ui.pages.common_settings_page import CommonSettingsPage
from thrust.ui.pages.scope_settings_page import ScopeSettingsPage
from thrust.ui.pages.simple_settings_page import SimpleSettingsPage
from thrust.webdb_client import DEFAULT_WEBDB_URL, WebDbClient, WebDbError


class LoginDialog(QDialog):
    def __init__(self, server: str, username: str, password: str, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("Connect to THRUST WebDB")
        self.setMinimumWidth(390)

        self.server_edit = QLineEdit(server)
        self.username_edit = QLineEdit(username)
        self.password_edit = QLineEdit(password)
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)

        form = QFormLayout()
        form.addRow("WebDB address:", self.server_edit)
        form.addRow("E-mail / Participant ID / username:", self.username_edit)
        form.addRow("Password:", self.password_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def values(self) -> tuple[str, str, str]:
        return (
            self.server_edit.text().strip(),
            self.username_edit.text(),
            self.password_edit.text(),
        )


class AdvancedSettingsDialog(QDialog):
    """State-aware settings dialog for runtime and, when offline, test settings."""

    def __init__(self, common_page: CommonSettingsPage, scope_page: ScopeSettingsPage, simple_page: SimpleSettingsPage, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("THRUST settings")
        self.resize(820, 720)

        self.tabs = QTabWidget()
        self.runtime_tab_index = self.tabs.addTab(common_page, "Joystick and runtime")
        self.scope_tab_index = self.tabs.addTab(scope_page, "Offline SCoPE")
        self.simple_tab_index = self.tabs.addTab(simple_page, "Offline SimPLE")

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)
        layout.addWidget(buttons)

    def set_offline_visible(self, visible: bool) -> None:
        self.tabs.setTabVisible(self.scope_tab_index, visible)
        self.tabs.setTabVisible(self.simple_tab_index, visible)

    def set_measurement_mode(self, is_simple: bool) -> None:
        self.tabs.setCurrentIndex(self.simple_tab_index if is_simple else self.scope_tab_index)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("THRUST · measurement client")
        self.resize(760, 900)
        self.setMinimumSize(640, 600)
        self.settings = QSettings("THRUST", "THRUST-measure")
        self.theme_mode = str(self.settings.value("appearance/theme", "system"))
        if self.theme_mode not in {"system", "dark", "light"}:
            self.theme_mode = "system"
        self._system_palette = QApplication.palette()

        self.client: WebDbClient | None = None
        self.current_manifest: dict[str, Any] | None = None
        self.available_tests: list[dict[str, Any]] = []
        self.offline_mode = True

        self.common_page = CommonSettingsPage()
        self.scope_page = ScopeSettingsPage()
        self.simple_page = SimpleSettingsPage()
        self.advanced_dialog: AdvancedSettingsDialog | None = None
        self.common_page.joystick_status_changed.connect(self._set_joystick_status)
        self.common_page.joystick_values_changed.connect(self._update_joystick_feedback)
        self.joystick_bars: dict[str, QProgressBar] = {}
        self.joystick_device_names: list[str] = []

        self.server_edit = QLineEdit(DEFAULT_WEBDB_URL)
        self.username_edit = QLineEdit()
        self.password_edit = QLineEdit()
        self.config_source_combo = QComboBox()
        self.config_source_combo.addItems(["WebDB", "Local offline"])
        self.config_source_combo.setVisible(False)

        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(self._open_login)
        self.disconnect_button = QPushButton("Disconnect")
        self.disconnect_button.clicked.connect(self._disconnect_webdb)
        self.disconnect_button.setVisible(False)

        self.connection_status = QLabel("● WebDB DISCONNECTED · Offline mode")
        self.connection_status.setObjectName("connectionStatus")
        self.connection_status.setProperty("connectionState", "disconnected")

        self.program_selector = QComboBox()
        self.program_selector.addItem("SCoPE", "SCOPE")
        self.program_selector.addItem("SimPLE", "SIMPLE")
        self.program_selector.setVisible(False)
        self.mode_button_group = QButtonGroup(self)
        self.mode_button_group.setExclusive(True)
        mode_switch = QWidget()
        mode_switch_layout = QHBoxLayout(mode_switch)
        mode_switch_layout.setContentsMargins(0, 0, 0, 0)
        mode_switch_layout.setSpacing(5)
        self.mode_buttons: dict[str, QPushButton] = {}
        for label, mode in (("SCoPE", "SCOPE"), ("SimPLE", "SIMPLE")):
            button = QPushButton(label)
            button.setCheckable(True)
            button.setObjectName("modeSwitchOption")
            button.setMinimumHeight(36)
            self.mode_button_group.addButton(button)
            self.mode_buttons[mode] = button
            button.clicked.connect(lambda _checked=False, index=0 if mode == "SCOPE" else 1: self.program_selector.setCurrentIndex(index))
            mode_switch_layout.addWidget(button, 1)

        self.participant_combo = QComboBox()
        self.participant_combo.setEditable(True)
        self.participant_combo.setPlaceholderText("Participant ID")
        self.participant_combo.setEnabled(False)
        self.participant_combo.currentIndexChanged.connect(lambda _: self._update_run_availability())
        self.participant_combo.editTextChanged.connect(lambda _: self._update_run_availability())
        self.participant_combo.currentIndexChanged.connect(lambda _: self._sync_selection_labels())
        self.participant_combo.editTextChanged.connect(lambda _: self._sync_selection_labels())
        self.participant_button = QPushButton("Select participant")
        self.participant_button.setObjectName("selectionPicker")
        self.participant_button.clicked.connect(self._choose_participant)
        self.participant_combo.setVisible(False)

        self.test_combo = QComboBox()
        self.test_combo.setPlaceholderText("Connect to load test versions")
        self.test_combo.setEnabled(False)
        self.test_combo.currentIndexChanged.connect(self._load_selected_test)
        self.test_combo.currentIndexChanged.connect(lambda _: self._sync_selection_labels())
        self.test_button = QPushButton("Select test version")
        self.test_button.setObjectName("selectionPicker")
        self.test_button.clicked.connect(self._choose_test)
        self.test_combo.setVisible(False)
        self.program_selector.currentIndexChanged.connect(self._refresh_test_choices)

        selection_group = QGroupBox("Measurement session")
        selection_group_layout = QVBoxLayout(selection_group)
        selection_group_layout.addWidget(mode_switch)
        selection_form = QFormLayout()
        selection_form.addRow("Participant ID:", self.participant_button)
        selection_form.addRow("Test version:", self.test_button)
        selection_group_layout.addLayout(selection_form)

        joystick_group = QGroupBox("Joystick link")
        joystick_layout = QVBoxLayout(joystick_group)
        joystick_row = QHBoxLayout()
        self.joystick_selector = QComboBox()
        self.joystick_selector.setPlaceholderText("Select joystick")
        self.joystick_selector.currentIndexChanged.connect(self._select_joystick)
        self.joystick_selector.setVisible(False)
        self.joystick_button = QPushButton("SELECT JOYSTICK · DISCONNECTED")
        self.joystick_button.setObjectName("joystickButton")
        self.joystick_button.setFixedHeight(36)
        self.joystick_button.setProperty("state", "disconnected")
        self.joystick_button.clicked.connect(self._choose_joystick)
        self.joystick_button.setText("Select Joystick")
        self.joystick_state_label = QLabel("DISCONNECTED")
        self.joystick_state_label.setObjectName("joystickState")
        self.joystick_state_label.setProperty("state", "disconnected")
        self.joystick_state_label.setFixedWidth(112)
        self.joystick_state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        joystick_row.addWidget(self.joystick_button, 1)
        joystick_row.addWidget(self.joystick_state_label)
        joystick_layout.addLayout(joystick_row)

        feedback_grid = QGridLayout()
        self.joystick_bars = {}
        self.axis_bar_stacks: dict[str, QStackedWidget] = {}
        self.axis_placeholders: dict[str, QLabel] = {}
        self.axis_rows: dict[str, QWidget] = {}
        self._axis_spins = {
            "LX": self.common_page.lx_axis_spin,
            "LY": self.common_page.ly_axis_spin,
            "RY": self.common_page.ry_axis_spin,
            "RX": self.common_page.rx_axis_spin,
            "BREAK": self.common_page.break_axis_spin,
            "RESET": self.common_page.reset_axis_spin,
        }
        for row, name in enumerate(("LX", "LY", "RY", "RX", "BREAK", "RESET")):
            axis_row = QWidget()
            axis_row_layout = QHBoxLayout(axis_row)
            axis_row_layout.setContentsMargins(0, 0, 0, 0)
            axis_row_layout.setSpacing(7)
            label = QLabel(name)
            label.setMinimumWidth(48)
            bar = QProgressBar()
            bar.setRange(-100, 100)
            bar.setValue(0)
            bar.setTextVisible(False)
            bar.setFixedHeight(8)
            bar.setObjectName("miniAxis")
            self.joystick_bars[name] = bar
            axis_row_layout.addWidget(label)
            if name == "BREAK":
                stack = QStackedWidget()
                stack.setFixedHeight(14)
                placeholder = QLabel("—")
                placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
                placeholder.setObjectName("axisPlaceholder")
                placeholder.setToolTip("BREAK axis is not active")
                stack.addWidget(bar)
                stack.addWidget(placeholder)
                stack.setCurrentWidget(placeholder)
                self.axis_bar_stacks[name] = stack
                self.axis_placeholders[name] = placeholder
                axis_row_layout.addWidget(stack, 1)
            else:
                axis_row_layout.addWidget(bar, 1)
            feedback_grid.addWidget(axis_row, row, 0)
            self.axis_rows[name] = axis_row
            self._axis_spins[name].valueChanged.connect(lambda _value: self._update_joystick_feedback(self.common_page.latest_axis_values))
        joystick_layout.addLayout(feedback_grid)

        self.axis_selector_buttons: dict[str, QPushButton] = {}
        self.axis_selector_rows: dict[str, QWidget] = {}
        mapping_group = QGroupBox("Axis assignment")
        mapping_grid = QGridLayout(mapping_group)
        mapping_grid.setContentsMargins(8, 8, 8, 8)
        mapping_grid.setHorizontalSpacing(14)
        mapping_grid.setVerticalSpacing(6)
        for index, name in enumerate(("LX", "LY", "RY", "RX", "BREAK", "RESET")):
            row, column = divmod(index, 2)
            mapping_cell = QWidget()
            cell_layout = QHBoxLayout(mapping_cell)
            cell_layout.setContentsMargins(0, 0, 0, 0)
            cell_layout.setSpacing(6)
            cell_layout.addWidget(QLabel(name))
            selector = QPushButton(f"Axis {self._axis_spins[name].value()}")
            selector.setObjectName("axisAssignButton")
            selector.setFixedWidth(84)
            self.axis_selector_buttons[name] = selector
            cell_layout.addWidget(selector)
            mapping_grid.addWidget(mapping_cell, row, column)
            self.axis_selector_rows[name] = mapping_cell
            selector.clicked.connect(lambda _checked=False, role=name: self._show_axis_choices(role))
            self._axis_spins[name].valueChanged.connect(lambda value, role=name: self._axis_spin_changed(role, value))
        self._refresh_axis_selectors()
        joystick_layout.addWidget(mapping_group)

        self.run_button = QPushButton("Start measurement")
        self.run_button.setObjectName("startMeasurement")
        self.run_button.setMinimumHeight(62)
        self.run_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.run_button.clicked.connect(self._run_selected_measurement)

        self.measurement_status = {}
        status_row = QHBoxLayout()
        status_row.setContentsMargins(0, 0, 0, 0)
        status_row.setSpacing(8)
        for key in ("participant", "test", "joystick"):
            indicator = QLabel()
            indicator.setObjectName("measurementStatus")
            indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
            indicator.setFixedHeight(28)
            indicator.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            self.measurement_status[key] = indicator
            status_row.addWidget(indicator, 1)

        self.advanced_button = QPushButton("Settings")
        self.advanced_button.clicked.connect(self._open_advanced)

        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setObjectName("sessionLog")
        self.log_output.setMinimumHeight(0)
        self.log_output.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(10)

        title = QLabel("THRUST")
        title.setObjectName("appTitle")
        title_row = QHBoxLayout()
        title_row.addWidget(title)
        title_row.addStretch()
        self.appearance_button = QToolButton()
        self.appearance_button.setObjectName("appearanceButton")
        self.appearance_button.setText("◐")
        self.appearance_button.setToolTip("Choose system, dark or light colors")
        self.appearance_button.setAccessibleName("Appearance")
        self.appearance_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.theme_menu = QMenu(self.appearance_button)
        self.theme_actions: dict[str, Any] = {}
        self.theme_action_group = QActionGroup(self.theme_menu)
        self.theme_action_group.setExclusive(True)
        for label, value in (("System", "system"), ("Dark", "dark"), ("Light", "light")):
            action = self.theme_menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(value == self.theme_mode)
            self.theme_action_group.addAction(action)
            action.triggered.connect(lambda _checked=False, selected=value: self._set_theme_mode(selected))
            self.theme_actions[value] = action
        self.appearance_button.setMenu(self.theme_menu)
        title_row.addWidget(self.appearance_button)
        session_actions = QWidget()
        session_actions_layout = QHBoxLayout(session_actions)
        session_actions_layout.setContentsMargins(0, 0, 0, 0)
        session_actions_layout.addWidget(self.connection_status)
        session_actions_layout.addStretch()
        session_actions_layout.addWidget(self.connect_button)
        session_actions_layout.addWidget(self.disconnect_button)
        session_actions_layout.addWidget(self.advanced_button)

        session_ribbon = QGroupBox("Measurement session")
        session_ribbon_layout = QHBoxLayout(session_ribbon)
        session_ribbon_layout.setContentsMargins(10, 4, 10, 4)
        session_ribbon_layout.addWidget(session_actions)

        controls_panel = QWidget()
        controls_layout = QVBoxLayout(controls_panel)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(8)
        controls_layout.addWidget(selection_group)
        controls_layout.addWidget(joystick_group)
        controls_layout.addStretch(1)
        controls_panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        log_panel = QGroupBox("Session log")
        log_panel.setObjectName("sessionLogPanel")
        log_layout = QVBoxLayout(log_panel)
        log_layout.setContentsMargins(8, 12, 8, 8)
        log_layout.setSpacing(0)
        log_layout.addWidget(self.log_output, 1)

        self.content_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.content_splitter.setChildrenCollapsible(False)
        self.content_splitter.addWidget(controls_panel)
        self.content_splitter.addWidget(log_panel)
        self.content_splitter.setStretchFactor(0, 1)
        self.content_splitter.setStretchFactor(1, 1)
        self.content_splitter.setSizes([360, 360])

        root.addLayout(title_row)
        root.addWidget(session_ribbon)
        root.addWidget(self.content_splitter, 1)
        root.addWidget(self.run_button)
        root.addLayout(status_row)

        self.setCentralWidget(central)
        self._apply_theme()
        style_hints = QGuiApplication.styleHints()
        if hasattr(style_hints, "colorSchemeChanged"):
            style_hints.colorSchemeChanged.connect(self._system_theme_changed)
        self._activate_offline_mode(show_dialog=False)
        self._refresh_joystick_selector()
        self.joystick_scan_timer = QTimer(self)
        self.joystick_scan_timer.timeout.connect(self._poll_joystick_devices)
        self.joystick_scan_timer.start(1000)
        QTimer.singleShot(0, self._auto_connect_joystick)

    def _refresh_joystick_selector(self) -> None:
        devices = self.common_page.available_joysticks()
        previous = self.joystick_selector.currentData()
        changed = devices != self.joystick_device_names
        if changed:
            self.joystick_selector.blockSignals(True)
            self.joystick_selector.clear()
            for index, name in enumerate(devices):
                self.joystick_selector.addItem(f"{index}: {name}", index)
            if not devices:
                self.joystick_selector.addItem("No joystick detected", -1)
            elif isinstance(previous, int) and 0 <= previous < len(devices):
                self.joystick_selector.setCurrentIndex(previous)
            else:
                self.joystick_selector.setCurrentIndex(0)
            self.joystick_selector.blockSignals(False)
            self.joystick_device_names = devices

        self._update_run_availability(self.common_page.joystick_active)
        if not devices:
            if self.common_page.joystick_active:
                self.common_page.stop_joystick()
            self._set_joystick_status(False, "No joystick detected")
        elif len(devices) == 1 and not self.common_page.joystick_active:
            self._select_joystick(self.joystick_selector.currentIndex())

    def _selected_theme_is_dark(self) -> bool:
        if self.theme_mode == "dark":
            return True
        if self.theme_mode == "light":
            return False
        scheme = QGuiApplication.styleHints().colorScheme()
        if scheme == Qt.ColorScheme.Dark:
            return True
        if scheme == Qt.ColorScheme.Light:
            return False
        return self._system_palette.color(QPalette.ColorRole.Window).lightness() < 128

    def _set_theme_mode(self, theme_mode: str) -> None:
        self.theme_mode = theme_mode if theme_mode in {"system", "dark", "light"} else "system"
        self.settings.setValue("appearance/theme", self.theme_mode)
        for key, action in self.theme_actions.items():
            action.setChecked(key == self.theme_mode)
        self._apply_theme()

    def _axis_count(self) -> int:
        joystick = self.common_page.joystick
        if self.common_page.joystick_active and joystick is not None:
            try:
                return max(1, int(joystick.get_numaxes()))
            except Exception:
                pass
        return 17

    def _refresh_axis_selectors(self) -> None:
        if not hasattr(self, "axis_selectors"):
            return
        for role, selector in self.axis_selector_buttons.items():
            selected_axis = self._axis_spins[role].value()
            selector.setText(f"Axis {selected_axis}")
            selector.setToolTip(f"{role} uses joystick axis {selected_axis}. Click to change.")

    def _show_axis_choices(self, role: str) -> None:
        menu = QMenu(self.axis_selector_buttons[role])
        selected_axis = self._axis_spins[role].value()
        count = self._axis_count()
        for axis_index in range(count):
            action = menu.addAction(f"Axis {axis_index}")
            action.setCheckable(True)
            action.setChecked(axis_index == selected_axis)
            action.triggered.connect(lambda _checked=False, chosen=axis_index, axis_role=role: self._axis_selection_changed(axis_role, chosen))
        if selected_axis >= count:
            menu.addAction(f"Axis {selected_axis} (currently unavailable)").setEnabled(False)
        button = self.axis_selector_buttons[role]
        menu.exec(button.mapToGlobal(button.rect().bottomLeft()))

    def _axis_selection_changed(self, role: str, axis_index: int) -> None:
        self._axis_spins[role].setValue(axis_index)
        self._update_joystick_feedback(self.common_page.latest_axis_values)

    def _axis_spin_changed(self, role: str, value: int) -> None:
        selector = self.axis_selector_buttons.get(role)
        if selector is not None:
            selector.setText(f"Axis {value}")
            selector.setToolTip(f"{role} uses joystick axis {value}. Click to change.")

    def _sync_selection_labels(self) -> None:
        participant = self.participant_combo.currentText().strip()
        self.participant_button.setText(participant or "Select participant")
        test = self.test_combo.currentData()
        self.test_button.setText(self.test_combo.currentText() if test else "Select test version")

    def _choose_from_table(self, title: str, combo: QComboBox, columns: tuple[str, ...]) -> None:
        if combo.count() == 0:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.resize(560, min(520, 130 + combo.count() * 38))
        table = QTableWidget(combo.count(), len(columns), dialog)
        table.setHorizontalHeaderLabels(columns)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        for row in range(combo.count()):
            value = combo.itemData(row)
            if columns == ("Participant",):
                values = (combo.itemText(row),)
            elif isinstance(value, dict):
                values = (str(value.get("name", "")), str(value.get("version", "")))
            else:
                values = (combo.itemText(row), "")
            for column, text in enumerate(values):
                table.setItem(row, column, QTableWidgetItem(text))
        table.resizeColumnsToContents()
        table.horizontalHeader().setStretchLastSection(True)
        if combo.currentIndex() >= 0:
            table.selectRow(combo.currentIndex())
        layout = QVBoxLayout(dialog)
        layout.addWidget(table)
        table.cellClicked.connect(lambda row, _column: (combo.setCurrentIndex(row), dialog.accept()))
        dialog.exec()

    def _choose_participant(self) -> None:
        self._choose_from_table("Choose participant", self.participant_combo, ("Participant",))

    def _choose_test(self) -> None:
        self._choose_from_table("Choose test version", self.test_combo, ("Test", "Version"))

    def _system_theme_changed(self, *_args: object) -> None:
        if self.theme_mode == "system":
            self._apply_theme()

    def _apply_theme(self) -> None:
        dark = self._selected_theme_is_dark()
        colors = (
            {
                "window": "#111820", "surface": "#18232d", "surface_alt": "#202e39",
                "input": "#0d151c", "text": "#edf3f7", "muted": "#a5b5c1",
                "border": "#405563", "accent": "#55c7df", "selection": "#175269",
                "button": "#243b49", "button_hover": "#315568", "disabled": "#26313a",
                "disabled_text": "#aab3ba", "log": "#0b1218", "scroll": "#314552",
            }
            if dark else
            {
                "window": "#eef2f5", "surface": "#ffffff", "surface_alt": "#e6edf2",
                "input": "#ffffff", "text": "#17232c", "muted": "#526574",
                "border": "#aabac5", "accent": "#087d9b", "selection": "#b9e4ee",
                "button": "#e0e9ee", "button_hover": "#cadce5", "disabled": "#71262b",
                "disabled_text": "#ffffff", "log": "#f8fafb", "scroll": "#9aacb8",
            }
        )
        palette = QPalette()
        role_colors = {
            QPalette.ColorRole.Window: colors["window"],
            QPalette.ColorRole.WindowText: colors["text"],
            QPalette.ColorRole.Base: colors["input"],
            QPalette.ColorRole.AlternateBase: colors["surface_alt"],
            QPalette.ColorRole.ToolTipBase: colors["surface"],
            QPalette.ColorRole.ToolTipText: colors["text"],
            QPalette.ColorRole.Text: colors["text"],
            QPalette.ColorRole.Button: colors["button"],
            QPalette.ColorRole.ButtonText: colors["text"],
            QPalette.ColorRole.BrightText: "#ffffff" if dark else "#111820",
            QPalette.ColorRole.Highlight: colors["selection"],
            QPalette.ColorRole.HighlightedText: colors["text"] if dark else "#10212a",
            QPalette.ColorRole.Link: colors["accent"],
            QPalette.ColorRole.PlaceholderText: colors["muted"],
        }
        for role, value in role_colors.items():
            palette.setColor(role, QColor(value))
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(colors["disabled_text"]))
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(colors["disabled_text"]))
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor(colors["disabled_text"]))
        app = QApplication.instance()
        if app is not None:
            app.setPalette(palette)
            app.setStyleSheet(f"""
                QWidget {{ color: {colors['text']}; font-size: 13px; }}
                QMainWindow, QDialog, QWidget#centralWidget {{ background: {colors['window']}; }}
                QGroupBox {{ color: {colors['text']}; background: {colors['surface']}; border: 1px solid {colors['border']}; border-radius: 8px; margin-top: 10px; padding: 12px 10px 10px; font-weight: 600; }}
                QGroupBox::title {{ subcontrol-origin: margin; left: 12px; padding: 0 5px; color: {colors['accent']}; }}
                QLabel {{ color: {colors['text']}; background: transparent; }}
                QLabel#appTitle {{ color: {colors['text']}; font-size: 30px; font-weight: 800; }}
                QToolButton#appearanceButton {{ color: {colors['text']}; background: {colors['surface']}; border: 1px solid {colors['border']}; border-radius: 7px; min-width: 38px; min-height: 38px; font-size: 22px; padding: 0; }}
                QToolButton#appearanceButton:hover {{ color: {colors['accent']}; border-color: {colors['accent']}; background: {colors['surface_alt']}; }}
                QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit, QTimeEdit, QDateTimeEdit, QPlainTextEdit, QTextEdit {{ color: {colors['text']}; background: {colors['input']}; border: 1px solid {colors['border']}; border-radius: 4px; padding: 6px 8px; selection-background-color: {colors['selection']}; selection-color: {colors['text']}; }}
                QPlainTextEdit#sessionLog {{ background: {colors['log']}; border: none; font-family: monospace; font-size: 12px; }}
                QGroupBox#sessionLogPanel {{ background: {colors['log']}; border: 1px solid {colors['log']}; }}
                QComboBox::drop-down {{ background: {colors['button']}; border: 0; width: 24px; }}
                QComboBox QAbstractItemView {{ color: {colors['text']}; background: {colors['surface']}; selection-background-color: {colors['selection']}; selection-color: {colors['text']}; border: 1px solid {colors['border']}; outline: 0; }}
                QPushButton {{ color: {colors['text']}; background: {colors['button']}; border: 1px solid {colors['border']}; border-radius: 5px; padding: 7px 12px; }}
                QPushButton:hover {{ background: {colors['button_hover']}; border-color: {colors['accent']}; }}
                QPushButton:pressed {{ background: {colors['selection']}; }}
                QPushButton:disabled {{ color: {colors['disabled_text']}; background: {colors['disabled']}; border-color: {colors['disabled']}; }}
                QPushButton#modeSwitchOption {{ color: {colors['muted']}; background: {colors['surface_alt']}; font-size: 14px; font-weight: 700; padding: 7px 16px; }}
                QPushButton#modeSwitchOption:checked {{ color: {colors['text']}; background: {colors['selection']}; border-color: {colors['accent']}; }}
                QPushButton#selectionPicker {{ text-align: left; min-height: 30px; font-weight: 600; }}
                QPushButton#joystickButton {{ text-align: left; min-height: 30px; font-weight: 600; }}
                QPushButton#joystickButton:hover {{ border-color: {colors['accent']}; }}
                QLabel#joystickState[state="connected"] {{ color: #20b865; font-weight: 800; }}
                QLabel#joystickState[state="disconnected"] {{ color: #ef5962; font-weight: 800; }}
                QPushButton#axisAssignButton {{ text-align: left; min-height: 30px; padding-left: 9px; }}
                QLabel#axisPlaceholder {{ color: {colors['muted']}; background: {colors['surface_alt']}; border: 1px dashed {colors['border']}; border-radius: 3px; }}
                QLabel#measurementStatus {{ background: transparent; border: none; font-size: 11px; font-weight: 700; letter-spacing: .3px; }}
                QLabel#measurementStatus[state="ready"] {{ color: #20b865; }}
                QLabel#measurementStatus[state="error"] {{ color: #ef5962; }}
                QPushButton#startMeasurement {{ color: #ffffff; background: #16804b; border: 1px solid #27a967; border-radius: 8px; padding: 13px 16px; font-size: 17px; font-weight: 800; letter-spacing: .4px; }}
                QPushButton#startMeasurement:hover:enabled {{ background: #1b9959; }}
                QPushButton#startMeasurement:disabled {{ color: #f7eeee; background: #76252c; border-color: #9e343c; }}
                QCheckBox {{ color: {colors['text']}; spacing: 8px; }}
                QCheckBox::indicator {{ width: 17px; height: 17px; border: 1px solid {colors['border']}; border-radius: 3px; background: {colors['input']}; }}
                QCheckBox::indicator:checked {{ background: {colors['accent']}; border-color: {colors['accent']}; }}
                QProgressBar#miniAxis {{ color: {colors['text']}; background: {colors['surface_alt']}; border: 1px solid {colors['border']}; border-radius: 3px; }}
                QProgressBar#miniAxis::chunk {{ background: {colors['accent']}; border-radius: 2px; }}
                QLabel#joystickLed[connectionState="connected"], QLabel#connectionStatus[connectionState="connected"] {{ color: #159653; font-weight: 700; }}
                QLabel#joystickLed[connectionState="disconnected"], QLabel#connectionStatus[connectionState="disconnected"] {{ color: #d34852; font-weight: 700; }}
                QLabel#connectionStatus[connectionState="warning"] {{ color: #b97911; font-weight: 700; }}
                QTabWidget::pane {{ border: 1px solid {colors['border']}; background: {colors['surface']}; }}
                QTabBar::tab {{ color: {colors['text']}; background: {colors['surface_alt']}; border: 1px solid {colors['border']}; padding: 8px 12px; }}
                QTabBar::tab:selected {{ color: {colors['text']}; background: {colors['surface']}; border-bottom-color: {colors['accent']}; }}
                QScrollBar:vertical, QScrollBar:horizontal {{ background: {colors['surface']}; border: 0; margin: 0; }}
                QScrollBar:vertical {{ width: 12px; }} QScrollBar:horizontal {{ height: 12px; }}
                QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{ background: {colors['scroll']}; border-radius: 5px; min-height: 24px; min-width: 24px; }}
                QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
                QSplitter::handle {{ background: {colors['window']}; }}
                QToolTip {{ color: {colors['text']}; background: {colors['surface']}; border: 1px solid {colors['border']}; }}
                QMenu {{ color: {colors['text']}; background: {colors['surface']}; border: 1px solid {colors['border']}; }}
                QMenu::item:selected {{ color: {colors['text']}; background: {colors['selection']}; }}
            """)

    def resizeEvent(self, event: object) -> None:
        super().resizeEvent(event)
        if not hasattr(self, "content_splitter"):
            return
        desired = Qt.Orientation.Vertical if self.width() < 700 else Qt.Orientation.Horizontal
        if self.content_splitter.orientation() != desired:
            self.content_splitter.setOrientation(desired)
            if desired == Qt.Orientation.Vertical:
                self.content_splitter.setSizes([340, 460])
            else:
                width = max(1, self.content_splitter.width())
                half = width // 2
                self.content_splitter.setSizes([half, width - half])

    def _update_run_availability(self, joystick_present: bool | None = None) -> None:
        connected = self.common_page.joystick_active if joystick_present is None else joystick_present
        participant_ready = bool(
            self.participant_combo.currentText().strip()
            if self.offline_mode
            else self.participant_combo.currentData()
        )
        test_ready = bool(self.current_manifest and self.test_combo.currentIndex() >= 0)
        self.run_button.setEnabled(connected and test_ready and participant_ready)
        self._set_status_indicator("participant", participant_ready, "PARTICIPANT · OK", "SELECT PARTICIPANT")
        self._set_status_indicator("test", test_ready, "TEST · OK", "SELECT TEST")
        self._set_status_indicator("joystick", connected, "JOYSTICK · OK", "JOYSTICK DISCONNECTED")

    def _set_status_indicator(self, key: str, ready: bool, good_text: str, error_text: str) -> None:
        indicator = self.measurement_status.get(key)
        if indicator is None:
            return
        indicator.setText(good_text if ready else error_text)
        indicator.setProperty("state", "ready" if ready else "error")
        indicator.style().unpolish(indicator)
        indicator.style().polish(indicator)

    def _poll_joystick_devices(self) -> None:
        self._refresh_joystick_selector()

    def _auto_connect_joystick(self) -> None:
        self._refresh_joystick_selector()

    def _choose_joystick(self) -> None:
        self._choose_from_table("Choose joystick", self.joystick_selector, ("Device",))

    def _select_joystick(self, index: int) -> None:
        device_index = self.joystick_selector.itemData(index)
        if device_index is None or int(device_index) < 0:
            self._set_joystick_status(False, "No joystick detected")
            return
        self.common_page.select_joystick(int(device_index), connect=True)

    def _set_joystick_status(self, connected: bool, status: str) -> None:
        if connected:
            device_index = self.joystick_selector.currentData()
            device_name = (
                self.joystick_device_names[int(device_index)]
                if isinstance(device_index, int) and 0 <= device_index < len(self.joystick_device_names)
                else "Joystick"
            )
            self.joystick_button.setText(device_name)
        else:
            self.joystick_button.setText("Select Joystick")
        self.joystick_state_label.setText("CONNECTED" if connected else "DISCONNECTED")
        self.joystick_state_label.setProperty("state", "connected" if connected else "disconnected")
        self.joystick_state_label.style().unpolish(self.joystick_state_label)
        self.joystick_state_label.style().polish(self.joystick_state_label)
        self._refresh_axis_selectors()
        self._update_joystick_feedback(self.common_page.latest_axis_values)
        if hasattr(self, "run_button"):
            self._update_run_availability(connected)

    def _update_joystick_feedback(self, values: object) -> None:
        if not isinstance(values, list):
            return
        for role, bar in self.joystick_bars.items():
            axis_index = self._axis_spins[role].value()
            available = self.common_page.joystick_active and 0 <= axis_index < len(values)
            if role == "BREAK":
                self.axis_bar_stacks[role].setCurrentWidget(bar if available else self.axis_placeholders[role])
            if available:
                value = float(values[axis_index])
                bar.setValue(int(max(-1.0, min(1.0, value)) * 100))

    def _open_login(self) -> None:
        dialog = LoginDialog(
            self.server_edit.text().strip() or DEFAULT_WEBDB_URL,
            self.username_edit.text(),
            self.password_edit.text(),
            self,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            server, username, password = dialog.values()
            self.server_edit.setText(server)
            self.username_edit.setText(username)
            self.password_edit.setText(password)
            self._connect_webdb()

    def _connect_webdb(self) -> None:
        try:
            self.client = WebDbClient(self.server_edit.text().strip() or DEFAULT_WEBDB_URL)
            account = self.client.login(self.username_edit.text(), self.password_edit.text())
            tests = self.client.list_tests()
            role = str(account.get("role", ""))

            self.participant_combo.clear()
            if role == "student":
                participant_id = account.get("participant_id")
                participant_code = account.get("participant_code") or participant_id or "STUDENT"
                self.participant_combo.addItem(str(participant_code), participant_id)
                self.participant_combo.setCurrentIndex(0)
                self.participant_combo.setEditable(False)
                self.participant_combo.setEnabled(False)
            else:
                participants = self.client.list_participants()
                for participant in participants:
                    self.participant_combo.addItem(participant["participant_code"], participant["id"])
                self.participant_combo.setEditable(True)
                self.participant_combo.setEnabled(bool(participants))

            self.available_tests = [test for test in tests if test.get("is_active", False)]
            self.offline_mode = False
            self.config_source_combo.setCurrentIndex(0)
            self._refresh_test_choices()
            self._sync_selection_labels()
            identity = account.get("participant_code") if role == "student" else account.get("username", "")
            self.connection_status.setText(f"● WebDB CONNECTED · {identity}")
            self._set_connection_state("connected")
            self.connect_button.setVisible(False)
            self.disconnect_button.setVisible(True)
            self.advanced_button.setVisible(True)
            if self.advanced_dialog is not None:
                self.advanced_dialog.set_offline_visible(False)
            self.append_log(f"Loaded {len(tests)} active tests for {role or 'user'}.")
            self._load_selected_test()

        except (WebDbError, KeyError, ValueError) as exc:
            self.append_log(f"WebDB connection failed: {exc}")
            self._activate_offline_mode(show_dialog=True, error=str(exc))

    def _disconnect_webdb(self) -> None:
        self._activate_offline_mode(show_dialog=False)
        self.append_log("WebDB disconnected. Offline mode is active.")

    def _offline_manifest(self, mode: str = "SCOPE") -> dict[str, Any]:
        is_simple = mode.upper() == "SIMPLE"
        return {
            "test": {
                "id": "",
                "test_code": "LOCAL_SIMPLE" if is_simple else "LOCAL_SCOPE",
                "name": "Local offline SimPLE test" if is_simple else "Local offline SCoPE test",
                "version": "local",
                "analysis_profile": "SIMPLE_FLIGHT_V1" if is_simple else "SCOPE_STEP_RESPONSE_V1",
                "configuration": SimpleConfig().to_dict() if is_simple else {},
            }
        }

    def _activate_offline_mode(self, show_dialog: bool, error: str = "") -> None:
        self.offline_mode = True
        self.client = None
        self.current_manifest = None
        self.config_source_combo.setCurrentIndex(1)

        self.participant_combo.clear()
        self.participant_combo.addItem("LOCAL")
        self.participant_combo.setCurrentText("LOCAL")
        self.participant_combo.setEnabled(True)
        self._sync_selection_labels()

        self.available_tests = [
            self._offline_manifest("SCOPE")["test"],
            self._offline_manifest("SIMPLE")["test"],
        ]
        self._refresh_test_choices()

        self.connection_status.setText("● WebDB DISCONNECTED · Offline mode")
        self._set_connection_state("warning")
        self.connect_button.setVisible(True)
        self.disconnect_button.setVisible(False)
        self.advanced_button.setVisible(True)
        if self.advanced_dialog is not None:
            self.advanced_dialog.set_offline_visible(True)
        self._update_run_availability()
        if show_dialog:
            QMessageBox.warning(
                self,
                "WebDB unavailable",
                f"THRUST switched to offline mode automatically.\n\n{error}",
            )
            self._open_advanced()

    def _refresh_test_choices(self, _index: int = -1) -> None:
        mode = str(self.program_selector.currentData() or "SCOPE")
        previous = self.test_combo.currentData()
        previous_id = previous.get("id") if isinstance(previous, dict) else None
        matching = [
            test for test in self.available_tests
            if str(test.get("analysis_profile", "")).upper().startswith(mode)
        ]
        self.test_combo.blockSignals(True)
        self.test_combo.clear()
        for test in matching:
            self.test_combo.addItem(f'{test["name"]} · v{test["version"]}', test)
        saved_index = next(
            (i for i, test in enumerate(matching) if test.get("id") == previous_id),
            0,
        )
        self.test_combo.setCurrentIndex(saved_index if matching else -1)
        self.test_combo.setPlaceholderText("No available versions for this mode")
        self.test_combo.setEnabled(bool(matching))
        self.test_combo.blockSignals(False)
        self._sync_selection_labels()
        for button_mode, button in self.mode_buttons.items():
            button.setChecked(button_mode == mode)
        self.axis_rows["RESET"].setVisible(mode == "SIMPLE")
        self.axis_selector_rows["RESET"].setVisible(mode == "SIMPLE")
        self.current_manifest = None
        if matching:
            self._load_selected_test()
        else:
            self.append_log(f"No active {mode} test version is available.")
        self._update_run_availability()

    def _set_connection_state(self, state: str) -> None:
        self.connection_status.setProperty("connectionState", state)
        self.connection_status.style().unpolish(self.connection_status)
        self.connection_status.style().polish(self.connection_status)

    def _load_selected_test(self, _index: int = -1) -> None:
        if self.test_combo.currentIndex() < 0:
            return
        if self.offline_mode:
            selected = self.test_combo.currentData()
            if not isinstance(selected, dict):
                self.current_manifest = None
                self.run_button.setEnabled(False)
                return
            self.current_manifest = {"test": selected}
            is_simple = str(selected.get("analysis_profile", "")).upper().startswith("SIMPLE")
            if is_simple:
                self.simple_page.load_simple_config(SimpleConfig.from_dict(selected.get("configuration")))
            else:
                self.scope_page.load_scope_config(ScopeConfig())
            if self.advanced_dialog is not None:
                self.advanced_dialog.set_measurement_mode(is_simple)
            self._update_run_availability()
            return
        if self.client is None:
            return

        selected = self.test_combo.currentData()
        if not isinstance(selected, dict):
            self.run_button.setEnabled(False)
            return

        try:
            self.current_manifest = self.client.get_test_configuration(selected["id"])
            test = self.current_manifest["test"]
            self._apply_web_configuration(test)
            self._update_run_availability()
            self.append_log(f'Loaded test manifest: {test["test_code"]} v{test["version"]}')
        except (WebDbError, KeyError, TypeError, ValueError) as exc:
            self.current_manifest = None
            self.run_button.setEnabled(False)
            self.append_log(f"Test configuration failed: {exc}")

    def _configuration_from_web_test(self, test: dict[str, Any]) -> ScopeConfig:
        source = test.get("configuration")
        if not isinstance(source, dict):
            raise ValueError("Test configuration must be a JSON object.")

        config_data = dict(source)
        for obsolete_key in (
            "user", "profile_name", "expert_mode", "output_root", "use_dated_subfolders",
            "joystick_index", "break_axis", "reset_axis", "axis_map", "deadzone",
        ):
            config_data.pop(obsolete_key, None)

        legacy_mapping = {"sampling_hz": "fps", "timeout_s": "action_timeout_s"}
        for source_key, target_key in legacy_mapping.items():
            if source_key in config_data and target_key not in config_data:
                config_data[target_key] = config_data[source_key]

        visual = config_data.pop("visual", None)
        if isinstance(visual, dict):
            visual_mapping = {
                "screen_bg": "screen_background",
                "gimbal_bg": "gimbal_background",
                "grid": "grid_color",
                "label": "label_color",
                "prompt": "prompt_color",
            }
            for source_key, target_key in visual_mapping.items():
                if source_key in visual and target_key not in config_data:
                    config_data[target_key] = visual[source_key]
            for key in (
                "stick_outline", "stick_fill", "zone_idle_outline", "zone_idle_fill",
                "zone_ok_outline", "zone_ok_fill",
            ):
                if key in visual and key not in config_data:
                    config_data[key] = visual[key]

        known_fields = {item.name for item in fields(ScopeConfig)}
        config_data = {key: value for key, value in config_data.items() if key in known_fields}
        config = ScopeConfig.from_dict(config_data)
        config.validate()
        return config

    def _simple_configuration_from_web_test(self, test: dict[str, Any]) -> SimpleConfig:
        source = test.get("configuration")
        if not isinstance(source, dict):
            raise ValueError("SimPLE configuration must be a JSON object.")
        return SimpleConfig.from_dict(source)

    def _apply_web_configuration(self, test: dict[str, Any]) -> None:
        is_simple = str(test.get("analysis_profile", "")).upper().startswith("SIMPLE")
        if is_simple:
            self.simple_page.load_simple_config(self._simple_configuration_from_web_test(test))
        else:
            config = self._configuration_from_web_test(test)
            self.scope_page.apply_scope_config(config, self.common_page)
        if self.advanced_dialog is not None:
            self.advanced_dialog.set_measurement_mode(is_simple)

    def _open_advanced(self) -> None:
        if self.advanced_dialog is None:
            self.advanced_dialog = AdvancedSettingsDialog(self.common_page, self.scope_page, self.simple_page, self)
        self.advanced_dialog.set_offline_visible(self.offline_mode)
        if self.current_manifest:
            self.advanced_dialog.set_measurement_mode(str(self.current_manifest["test"].get("analysis_profile", "")).upper().startswith("SIMPLE"))
        self.advanced_dialog.show()
        self.advanced_dialog.raise_()
        self.advanced_dialog.activateWindow()

    def _run_selected_measurement(self) -> None:
        if self.current_manifest is None:
            return

        participant_code = self.participant_combo.currentText().strip() or "LOCAL"
        test = self.current_manifest["test"]
        profile_name = f'{test["test_code"]}_v{test["version"]}'
        is_simple = (
            str(test.get("analysis_profile", "")).upper().startswith("SIMPLE")
            or str(test.get("test_code", "")).upper().startswith("SIMPLE")
        )

        try:
            if not self.common_page.joystick_active:
                message = "Cannot start measurement: no joystick is connected."
                self.append_log(message)
                QMessageBox.warning(self, "Joystick unavailable", message)
                return

            runtime = self.common_page.export_common_dict()
            selected_joystick = self.joystick_selector.currentData()
            runtime["joystick_index"] = int(selected_joystick) if isinstance(selected_joystick, int) and selected_joystick >= 0 else 0
            if is_simple:
                config = (
                    self.simple_page.build_simple_config()
                    if self.offline_mode
                    else self._simple_configuration_from_web_test(test)
                )
                if config.background_image_id:
                    if self.client is None:
                        raise RuntimeError("The selected WebDB background requires a connection.")
                    runtime["background_image_path"] = str(
                        self.client.download_background(config.background_image_id)
                    )
                    self.append_log(f"Loaded SimPLE background {config.background_image_id}.")
                self.append_log(f"Starting SimPLE {test['test_code']} v{test['version']} for participant {participant_code}.")
                session = run_simple(
                    config, runtime, participant=participant_code, profile_name=profile_name,
                    log_callback=self.append_log,
                )
                raw_path = session.logfile_path
                if not raw_path:
                    raise RuntimeError("SimPLE did not create a raw log.")
                analysis = analyze_simple_log(raw_path, started_at=session.started_at)
                base_dir = Path(raw_path).parent.parent
                raw_stem = Path(raw_path).name.removesuffix(".gz").removesuffix(".tsv")
                if runtime.get("save_step_file", True):
                    step_path = base_dir / "steps" / (raw_stem + "_step.tsv")
                    analysis.setdefault("artifacts", {})["step_response"] = Path(
                        write_step_response(step_path, analysis)
                    ).name
                if runtime.get("save_graph_pdf", True):
                    graph_path = base_dir / "graphs" / (raw_stem + "_response.pdf")
                    analysis.setdefault("artifacts", {})["step_response_graph"] = Path(
                        save_step_graph(graph_path, analysis)
                    ).name
                    if runtime.get("auto_open_graph", False):
                        self._open_local_file(graph_path)
                analysis_path = base_dir / "analysis" / (raw_stem + "_analysis.json")
                analysis_path.parent.mkdir(parents=True, exist_ok=True)
                analysis.setdefault("artifacts", {})["analysis_json"] = analysis_path.name
                analysis_path.write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")
                self.append_log(f"SimPLE analysis saved: {analysis_path}")
            else:
                from thrust.runners.scope_runner import run_scope
                config = (
                    self.scope_page.build_scope_config(self.common_page)
                    if self.offline_mode
                    else self._configuration_from_web_test(test)
                )
                # Joystick channel assignments and break/reset axes are local hardware settings,
                # so they must override the test definition for both online and offline runs.
                config.axis_map = dict(runtime["axis_map"])
                config.deadzone = list(runtime["deadzone"])
                config.break_axis = int(runtime["break_axis"])
                config.reset_axis = int(runtime["reset_axis"])
                config.user = participant_code
                config.profile_name = profile_name
                config.validate()
                self.append_log(
                    f"Starting {test['test_code']} v{test['version']} for participant {participant_code}."
                )
                session = run_scope(config, log_callback=self.append_log)
                raw_path = session.logfile_path
                step_path = session.step_path
                if not raw_path:
                    raise RuntimeError("Measurement did not create a raw log.")
                analysis = analyze_scope_log(raw_path)
                if step_path and Path(step_path).is_file() and "normalized_step_response" not in analysis:
                    with Path(step_path).open("r", encoding="utf-8", newline="") as handle:
                        reader = csv.DictReader(handle, delimiter="\\t")
                        curves = {
                            name: [] for name in (
                                "Time[s]", "AMEA", "AMED", "ASTD", "EMEA", "EMED", "ESTD",
                                "TMEA", "TMED", "TSTD", "RMEA", "RMED", "RSTD",
                            )
                        }
                        for row in reader:
                            for name in curves:
                                if row.get(name) not in (None, ""):
                                    curves[name].append(float(row[name]))
                        analysis["normalized_step_response"] = {
                            "schema_version": "scope-normalized-response-v1",
                            "columns": curves,
                        }

            if self.offline_mode:
                self.append_log(f"Offline measurement finished. Raw log: {raw_path}")
                return

            participant_id = self.participant_combo.currentData()
            if not participant_id:
                raise RuntimeError("Participant has no valid WebDB ID.")
            if self.client is None:
                raise RuntimeError("WebDB client is not connected.")

            uploaded = self.client.upload_measurement(
                participant_id=str(participant_id),
                test_definition_id=str(test["id"]),
                started_at=analysis.get("started_at") or datetime.now(timezone.utc).isoformat(),
                raw_log_path=raw_path,
                analysis_data=analysis,
            )
            self.append_log(
                f"Measurement uploaded: {uploaded.get('id', 'unknown')} "
                f"({uploaded.get('raw_size_bytes', 0)} bytes, SHA-256 {uploaded.get('raw_sha256', '')})."
            )
            self.append_log("Measurement finished and archived in WebDB.")
        except Exception as exc:
            self.append_log(f"Measurement failed: {type(exc).__name__}: {exc}")
            QMessageBox.critical(self, "Measurement failed", f"{type(exc).__name__}: {exc}")

    @staticmethod
    def _open_local_file(path: Path) -> None:
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(path))
            elif sys.platform == "darwin":
                os.system(f'open "{path}"')
            else:
                os.system(f'xdg-open "{path}"')
        except Exception:
            pass

    def append_log(self, message: str) -> None:
        self.log_output.appendPlainText(message)
