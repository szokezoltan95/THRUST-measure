"""Render the startup image for PyInstaller's early bootloader splash."""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtGui import QGuiApplication

from thrust.ui.splash import make_splash_pixmap


def main() -> int:
    app = QGuiApplication([])
    target = Path(sys.argv[1])
    target.parent.mkdir(parents=True, exist_ok=True)
    if not make_splash_pixmap().save(str(target), "PNG"):
        raise RuntimeError(f"Could not render splash image: {target}")
    app.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
