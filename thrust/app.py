import sys

from PyQt6.QtWidgets import QApplication

from thrust.paths import ensure_app_directories
from thrust.ui.main_window import MainWindow


def main() -> int:
    ensure_app_directories()

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()

    return app.exec()