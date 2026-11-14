"""앱 아이콘(금색 다이아몬드 안에 Δ)을 코드로 그린다."""
from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QIcon, QLinearGradient, QPainter, QPen, QPixmap, QPolygonF


def _diamond(cx: float, cy: float, r: float) -> QPolygonF:
    return QPolygonF([QPointF(cx, cy - r), QPointF(cx + r, cy), QPointF(cx, cy + r), QPointF(cx - r, cy)])


def make_pixmap(size: int) -> QPixmap:
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = float(size)
    c = s / 2
    pen_w = max(1.0, s * 0.07)
    p.setPen(QPen(QColor("#e8cf94"), pen_w))
    p.setBrush(QColor("#17120c"))
    p.drawPolygon(_diamond(c, c, c - pen_w))
    g = QLinearGradient(0, s * 0.25, 0, s * 0.75)
    g.setColorAt(0, QColor("#f4dea6"))
    g.setColorAt(1, QColor("#9a7438"))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(g)
    # 가운데 Δ (델타 = 변화량)
    r = s * 0.25
    p.drawPolygon(QPolygonF([QPointF(c, c - r * 0.95), QPointF(c + r * 0.95, c + r * 0.62),
                             QPointF(c - r * 0.95, c + r * 0.62)]))
    p.end()
    return pm


def app_icon() -> QIcon:
    icon = QIcon()
    for s in (16, 20, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(make_pixmap(s))
    return icon
