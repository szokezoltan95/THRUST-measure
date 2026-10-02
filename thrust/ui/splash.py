"""Small startup image shared by the Qt and PyInstaller splash screens."""

from PyQt6.QtCore import QRectF
from PyQt6.QtGui import QColor, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer

from thrust.paths import PROJECT_ROOT


def make_splash_pixmap() -> QPixmap:
    pixmap = QPixmap(640, 210)
    pixmap.fill(QColor("#101a28"))
    painter = QPainter(pixmap)
    try:
        logo = QSvgRenderer(str(PROJECT_ROOT / "thrust" / "ui" / "THRUST_LOGO.svg"))
        if logo.isValid():
            logo.render(painter, QRectF(67, 25, 506, 153))
    finally:
        painter.end()
    return pixmap
