# -*- coding: utf-8 -*-
"""
RocketDesigner/gauge.py
------------------------
گیج حاشیهٔ پایداری -- نسخهٔ نرم و فضایی:

  • نوارِ قرص‌مانند (pill) با گرادیانِ پیوستهٔ رنگِ نواحی
    (خطر → هشدار → ایمن → بیش‌پایدار) به‌جای بلوک‌های خشک
  • عقربه: خطِ نورِ نرم + قرصِ مقدارِ شیشه‌ای
  • لایهٔ ثابت (نوار + تیک‌ها + عنوان) کش می‌شود؛ با هر پکت تله‌متری فقط
    عقربه و قرصِ مقدار جابه‌جا می‌شوند (به‌روزرسانی سبک و بدون افت فریم)
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QFont, QFontMetricsF, QLinearGradient,
                           QPainter, QPen, QPixmap, QRadialGradient)
from PySide6.QtWidgets import QWidget

from blueprint import THEME, alpha_color, fa

# (شروع، پایان، رنگ) -- بر حسب کالیبر
ZONES = [(-0.3, 0.5, "#fb7185"), (0.5, 1.0, "#ffd166"),
         (1.0, 2.0, "#4ade80"), (2.0, 2.5, "#5eead4"), (2.5, 3.3, "#ffd166")]
VMIN, VMAX = -0.3, 3.3


class MarginGauge(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(84)
        self._margin = None
        self._color = THEME["sub"]
        self._txt = "--"
        self._static = QPixmap()
        self._buf_size = (0, 0)

    def set_margin(self, margin_calibers, hex_color, txt):
        self._margin = margin_calibers
        self._color = hex_color
        self._txt = txt
        self.update()

    # ------------------------------------------------------------------
    def paintEvent(self, ev):
        w, h = self.width(), self.height()
        if w < 2 or h < 2:
            return
        self._ensure_static(w, h)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if not self._static.isNull():
            p.drawPixmap(0, 0, self._static)

        x0, x1 = w * 0.06, w * 0.94
        bar_y, bar_h = h - 32, 12

        def vx(v):
            return x0 + (v - VMIN) / (VMAX - VMIN) * (x1 - x0)

        if self._margin is not None:
            v = max(VMIN, min(VMAX, self._margin))
            x = vx(v)
            c = QColor(self._color)
            rgb = (c.red(), c.green(), c.blue())
            # هالهٔ نور دور عقربه
            halo = QRadialGradient(QPointF(x, bar_y + bar_h / 2), 26)
            halo.setColorAt(0.0, QColor(rgb[0], rgb[1], rgb[2], 70))
            halo.setColorAt(1.0, QColor(rgb[0], rgb[1], rgb[2], 0))
            p.setBrush(QBrush(halo))
            p.setPen(Qt.NoPen)
            p.drawEllipse(QPointF(x, bar_y + bar_h / 2), 26, 26)
            # خط نورِ عقربه
            pen = QPen(QColor(rgb[0], rgb[1], rgb[2], 230), 2.5)
            pen.setCapStyle(Qt.RoundCap)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawLine(QPointF(x, bar_y - 6), QPointF(x, bar_y + bar_h + 5))
            # قرصِ مقدار
            f = QFont("Shabnam", 10)
            f.setBold(True)
            p.setFont(f)
            fm = QFontMetricsF(f)
            txt = self._txt
            rect = QRectF(x - fm.horizontalAdvance(txt) / 2 - 9, bar_y - 38,
                          fm.horizontalAdvance(txt) + 18, 22)
            p.setBrush(QColor(rgb[0], rgb[1], rgb[2], 70))
            p.setPen(QPen(QColor(rgb[0], rgb[1], rgb[2], 190), 1))
            p.drawRoundedRect(rect, 11, 11)
            p.setPen(QColor("#ffffff"))
            p.drawText(rect, Qt.AlignCenter, txt)
        p.end()

    # ------------------------------------------------------------------
    def _ensure_static(self, w: int, h: int):
        if (w, h) == self._buf_size and not self._static.isNull():
            return
        dpr = self.devicePixelRatioF()
        pm = QPixmap(max(1, int(round(w * dpr))), max(1, int(round(h * dpr))))
        pm.setDevicePixelRatio(dpr)
        pm.fill(Qt.transparent)
        q = QPainter(pm)
        q.setRenderHint(QPainter.Antialiasing)
        self._render_static(q, w, h)
        q.end()
        self._static = pm
        self._buf_size = (w, h)

    def _render_static(self, p: QPainter, w: int, h: int):
        x0, x1 = w * 0.06, w * 0.94
        bar_y, bar_h = h - 32, 12
        track = QRectF(QPointF(x0, bar_y), QPointF(x1, bar_y + bar_h))

        def vx(v):
            return x0 + (v - VMIN) / (VMAX - VMIN) * (x1 - x0)

        # نوارِ پیوسته: گرادیان نرم بین رنگِ میانهٔ نواحی
        grad = QLinearGradient(x0, 0, x1, 0)
        for a, b, col in ZONES:
            t = ((a + b) / 2 - VMIN) / (VMAX - VMIN)
            grad.setColorAt(max(0.0, min(1.0, t)), QColor(col))
        grad.setColorAt(0.0, QColor(ZONES[0][2]))
        grad.setColorAt(1.0, QColor(ZONES[-1][2]))
        p.setBrush(QBrush(grad))
        p.setPen(Qt.NoPen)
        p.setOpacity(0.85)
        p.drawRoundedRect(track, bar_h / 2, bar_h / 2)
        p.setOpacity(1.0)
        # حاشیهٔ نورِ ملایم دور نوار
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor(255, 255, 255, 26), 1))
        p.drawRoundedRect(track.adjusted(-0.5, -0.5, 0.5, 0.5),
                          bar_h / 2, bar_h / 2)
        # تیک‌ها + اعداد فارسی
        p.setFont(QFont("Shabnam", 9))
        for v in (0, 1, 2, 3):
            x = vx(v)
            p.setPen(QPen(QColor(8, 13, 26, 160), 2))
            p.drawLine(QPointF(x, bar_y + 2), QPointF(x, bar_y + bar_h - 2))
            p.setPen(alpha_color(THEME["sub"], 200))
            p.drawText(QRectF(x - 14, bar_y + bar_h + 5, 28, 14),
                       Qt.AlignHCenter, fa(v))
        # عنوان و برچسبِ سمتِ ناپایدار
        p.setPen(alpha_color(THEME["sub"], 210))
        p.setFont(QFont("Shabnam", 9.5))
        p.drawText(QRectF(x0, 2, x1 - x0, 16), Qt.AlignRight |
                   Qt.AlignVCenter, "حاشیهٔ پایداری (کالیبر) -- سبز یعنی ایمن")
        p.drawText(QRectF(max(0.0, x0 - 60), bar_y + bar_h + 5, 58, 14),
                   Qt.AlignLeft | Qt.AlignVCenter, "ناپایدار")
