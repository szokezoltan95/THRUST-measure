import ctypes
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon
from PyQt6.QtWidgets import QApplication, QSplashScreen

from thrust.paths import PROJECT_ROOT, ensure_app_directories
from thrust.ui.splash import make_splash_pixmap


def main() -> int:
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

    # PyInstaller's bootloader shows its splash before Python starts on Windows.
    # Source runs, Linux and macOS use a Qt splash during GUI initialization.
    boot_splash = None
    if getattr(sys, "frozen", False) and sys.platform == "win32":
        try:
            import pyi_splash

            if pyi_splash.is_alive():
                boot_splash = pyi_splash
        except ImportError:
            pass

    qt_splash = None
    if boot_splash is None:
        qt_splash = QSplashScreen(make_splash_pixmap())
        qt_splash.showMessage(
            "Starting THRUST-measure...", Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
            QColor("#c7d7e4"),
        )
        qt_splash.show()
        app.processEvents()

    try:
        ensure_app_directories()
        # Delay the large UI and analysis import until the splash is visible.
        from thrust.ui.main_window import MainWindow

        window = MainWindow()
        if not icon.isNull():
            window.setWindowIcon(icon)
        window.show()
        app.processEvents()
    finally:
        if qt_splash is not None:
            qt_splash.finish(window) if "window" in locals() else qt_splash.close()
        if boot_splash is not None:
            boot_splash.close()

    return app.exec()
