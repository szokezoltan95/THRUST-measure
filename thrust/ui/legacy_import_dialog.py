from __future__ import annotations

import re
import sys
from pathlib import Path

from PyQt6.QtCore import QProcess, QProcessEnvironment
from PyQt6.QtWidgets import (
    QCheckBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton,
    QVBoxLayout, QWidget,
)


class LegacyImportDialog(QDialog):
    """Convert old measurement logs and optionally upload normalized results."""

    def __init__(self, webdb_url: str, username: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Legacy measurement files")
        self.resize(760, 600)
        self.process: QProcess | None = None

        self.source_edit = QLineEdit(str(Path.home() / "Documents" / "THRUST" / "import"))
        self.output_edit = QLineEdit(str(Path.home() / "Documents" / "THRUST" / "normalized"))
        self.webdb_edit = QLineEdit(webdb_url)
        self.username_edit = QLineEdit(username)
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.upload_check = QCheckBox("Upload converted files to WebDB after saving")
        self.upload_check.setChecked(False)
        self.upload_check.toggled.connect(self._set_upload_fields_enabled)

        form = QFormLayout()
        form.addRow("Source folder:", self._folder_row(self.source_edit))
        form.addRow("Output folder:", self._folder_row(self.output_edit))
        form.addRow("WebDB URL:", self.webdb_edit)
        form.addRow("Username:", self.username_edit)
        form.addRow("Password:", self.password_edit)
        form.addRow("", self.upload_check)

        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.status = QLabel("Ready")
        self.logger = QPlainTextEdit()
        self.logger.setReadOnly(True)
        self.logger.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.run_button = QPushButton("Convert and save")
        self.run_button.clicked.connect(self._run)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)
        buttons = QHBoxLayout()
        buttons.addWidget(self.run_button)
        buttons.addStretch()
        buttons.addWidget(close_button)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.status)
        layout.addWidget(self.progress)
        layout.addWidget(self.logger, 1)
        layout.addLayout(buttons)
        self._set_upload_fields_enabled(False)

    def _folder_row(self, edit: QLineEdit):
        row = QHBoxLayout()
        row.addWidget(edit, 1)
        button = QPushButton("Browse…")
        button.clicked.connect(lambda: self._browse(edit))
        row.addWidget(button)
        container = QWidget()
        container.setLayout(row)
        return container

    def _browse(self, edit: QLineEdit) -> None:
        selected = QFileDialog.getExistingDirectory(self, "Select folder", edit.text())
        if selected:
            edit.setText(selected)

    def _set_upload_fields_enabled(self, enabled: bool) -> None:
        for widget in (self.webdb_edit, self.username_edit, self.password_edit):
            widget.setEnabled(enabled)
        self.run_button.setText("Convert and upload" if enabled else "Convert and save")

    def _run(self) -> None:
        source, output = Path(self.source_edit.text()).expanduser(), Path(self.output_edit.text()).expanduser()
        if not source.is_dir():
            QMessageBox.warning(self, "Source folder missing", "Choose an existing folder containing measurement logs.")
            return
        if self.upload_check.isChecked() and (not self.username_edit.text().strip() or not self.password_edit.text()):
            QMessageBox.warning(self, "Credentials required", "Enter the WebDB username and password to upload.")
            return
        self.logger.clear()
        self.progress.setRange(0, 0)
        self.status.setText("Starting…")
        self.run_button.setEnabled(False)
        process = QProcess(self)
        self.process = process
        process.setProgram(sys.executable)
        repo_root = Path(__file__).resolve().parents[2]
        args = [str(repo_root / "scripts" / "import_measurements.py"), "--workspace", str(source), "--output", str(output)]
        if not self.upload_check.isChecked():
            args.append("--convert-only")
        else:
            args.extend(["--webdb", self.webdb_edit.text().strip(), "--username", self.username_edit.text().strip()])
        process.setArguments(args)
        env = QProcessEnvironment.systemEnvironment()
        if self.upload_check.isChecked():
            env.insert("THRUST_WEBDB_PASSWORD", self.password_edit.text())
        else:
            env.remove("THRUST_WEBDB_PASSWORD")
        process.setProcessEnvironment(env)
        process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        process.readyReadStandardOutput.connect(self._read_output)
        process.finished.connect(self._finished)
        process.errorOccurred.connect(lambda error: self._append(f"Process error: {error}"))
        process.start()

    def _read_output(self) -> None:
        if self.process is None:
            return
        text = bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace")
        for line in text.splitlines():
            self._append(line)
            match = re.search(r"PROGRESS\t(\d+)\t(\d+)\t(.*)$", line)
            if match:
                current, total = int(match.group(1)), int(match.group(2))
                self.progress.setRange(0, max(1, total))
                self.progress.setValue(current)
                self.status.setText(match.group(3))

    def _append(self, line: str) -> None:
        self.logger.appendPlainText(line)
        self.logger.verticalScrollBar().setValue(self.logger.verticalScrollBar().maximum())

    def _finished(self, exit_code: int, _exit_status: QProcess.ExitStatus) -> None:
        self._read_output()
        self.run_button.setEnabled(True)
        self.progress.setRange(0, 1)
        self.progress.setValue(1 if exit_code == 0 else 0)
        self.status.setText("Completed" if exit_code == 0 else f"Finished with errors (exit {exit_code})")
        self._append(f"Process exited with code {exit_code}.")
