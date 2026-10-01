import ctypes
import sys

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from thrust.paths import PROJECT_ROOT, ensure_app_directories
from thrust.ui.main_window import MainWindow


def main() -> int:
    ensure_app_directories()

    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("TUKE.THRUST.Measure")
        except (AttributeError, OSError):
            pass

    app = QApplication(sys.argv)
    icon_path = PROJECT_ROOT / "THRUST.ico"
    icon = QIcon(str(icon_path)) if icon_path.is_file() else QIcon()
    if not icon.isNull():
        app.setWindowIcon(icon)
    window = MainWindow()
    if not icon.isNull():
        window.setWindowIcon(icon)
    window.show()

    return app.exec()