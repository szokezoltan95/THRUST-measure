"""Small startup image shared by the Qt and PyInstaller splash screens."""

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer

from thrust.paths import PROJECT_ROOT


def make_splash_pixmap() -> QPixmap:
    pixmap = QPixmap(640, 260)
    pixmap.fill(QColor("#101a28"))
    painter = QPainter(pixmap)
    try:
        logo = QSvgRenderer(str(PROJECT_ROOT / "thrust" / "ui" / "THRUST_LOGO.svg"))
        if logo.isValid():
            logo.render(painter, QRectF(67, 33, 506, 153))
        painter.setPen(QColor("#c7d7e4"))
        font = QFont()
        font.setPixelSize(17)
        painter.setFont(font)
        painter.drawText(0, 190, 640, 32, Qt.AlignmentFlag.AlignCenter, "Measurement client")
    finally:
        painter.end()
    return pixmap
