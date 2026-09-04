# -*- coding: utf-8 -*-
"""
RocketDesigner/blueprint.py
---------------------------
بوم طراحی راکت -- بازنسیسی کامل با زبان بصری «فضاییِ مینی‌مال»:

  • پس‌زمینهٔ فضای عمیق: گرادیان شب + میدان ستارهٔ نرم + دو مه‌رنگ (نبولا)
    و وینیت ملایم -- بدون شلوغی، فقط عمق.
  • راکت با گرادیان‌های نرم و هالهٔ نورِ ملایم (نه خطِ خشک): بدنه نیلیِ شیشه‌ای،
    دماغه فیروزه‌ای، باله‌ها بنفشِ مه‌آلود؛ لبه‌ها با Round Join/Cap نرم‌اند.
  • هندسه صادق می‌ماند: دماغهٔ «تخت» چهارگوشِ واقعی است و فقط شکل‌های فیزیکی
    (نیم‌کره/اویو) منحنی دارند.
  • راکت همیشه وسط‌چین است: با بزرگ/کوچک‌شدن، از مرکز به دو طرف باز می‌شود.
  • نشانه‌های CG/CP و اندازه‌گذاری‌ها به‌صورت قرص/چیپِ شیشه‌ایِ نرم.
  • رندر Buffer-based (کشِ لایهٔ زمینه + لایهٔ صحنه) و پالسِ زندهٔ نرم با
    میرایی مبتنی بر زمان؛ پکت‌های پشت‌سرهم تله‌مری ادغام می‌شوند (~۶۰fps).

مختصات فیزیک: x از نوک دماغه به عقب (mm)؛ روی صفحه دماغه سمت راست است.
"""
from __future__ import annotations

import math
import random

from PySide6.QtCore import QElapsedTimer, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import (QBrush, QColor, QFont, QFontMetricsF, QLinearGradient,
                           QPainter, QPainterPath, QPen, QPixmap, QPolygonF,
                           QRadialGradient)
from PySide6.QtWidgets import QWidget

FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")

# ---------------------------------------------------------------------------
# پالتِ «فضاییِ مینی‌مال»: تیرهٔ عمیق + نورهای نرم
THEME = {
    "bg0": "#070b18", "bg1": "#0d1428", "bg2": "#131c36",
    "panel": "#10182e", "panel_hi": "#182242",
    "border": "#26314f",
    "text": "#e8ecff", "sub": "#93a0c4",
    "teal": "#5eead4", "purple": "#a78bfa", "orange": "#fdba74",
    "pink": "#f9a8d4", "yellow": "#ffd166", "blue": "#7cc4ff",
    "green": "#4ade80", "red": "#fb7185",
    "body": "#93a7e8",
    "neon_jade": "#5eead4", "neon_cyber": "#7cc4ff", "neon_amber": "#ffd166",
}

# کدام پارامتر → کدام عضو/اندازه روی نقشه بدرخشد
FIELD_HL = {
    "sp_diameter": {"body", "dim_diam"},
    "sp_body_len": {"body", "dim_total"},
    "cmb_shape": {"nose"},
    "sp_nose_len": {"nose", "dim_nose"},
    "sp_nose_mass": {"cg"},
    "cmb_fin_n": {"fins"},
    "sp_root": {"fins"},
    "sp_tip": {"fins"},
    "sp_span": {"fins", "dim_span"},
    "sp_sweep": {"fins"},
    "sp_fin_mass": {"cg"},
    "sp_body_mass": {"cg"},
    "sp_body_pos": {"cg"},
    "sp_engine_mass": {"cg"},
    "sp_engine_pos": {"cg"},
    "sp_chute_mass": {"cg"},
    "sp_chute_pos": {"cg"},
    "chk_meas": {"cg"},
}

# رنگِ هالهٔ پالس هر عضو (RGB)
PULSE_RGB = {
    "body": (124, 196, 255),
    "nose": (94, 234, 212),
    "fins": (167, 139, 250),
    "cg": (255, 209, 102),
    "cp": (124, 196, 255),
}

MARGIN = 52
RULER_H = 30


def fa(txt) -> str:
    """اعداد همیشه انگلیسی (LatIN) -- فقط محافظت از عبارات لاتین در متن فارسی."""
    s = str(txt)
    try:
        from core.report_text import protect_latin_quantities
        return protect_latin_quantities(s)
    except Exception:
        return s


def verdict_color(verdict: str) -> str:
    return {"ok": THEME["green"], "warn": THEME["yellow"],
            "danger": THEME["red"], "unstable": THEME["red"],
            "over": THEME["orange"]}.get(verdict, THEME["sub"])


def alpha_color(hexcol: str, alpha: int) -> QColor:
    """رنگِ شفاف از نامِ هگز -- QColor(name, alpha) در Qt معتبر نیست."""
    c = QColor(hexcol)
    c.setAlpha(max(0, min(255, int(alpha))))
    return c


def _rgb(hexcol: str):
    c = QColor(hexcol)
    return c.red(), c.green(), c.blue()


class Blueprint(QWidget):
    """بوم طراحی راکت: فضای عمیق، راکت وسط‌چین، بازخورد زندهٔ نرم."""

    FRAME_MS = 16            # سقف نرخ فریم (~60fps) برای ادغام به‌روزرسانی‌ها
    PULSE_MS = 700.0         # طولِ تپش (میلی‌ثانیه)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(520, 240)
        self._geo = None
        self._res = None
        self._cg_measured = False

        # میدان ستارهٔ ثابت (در مختصات نرمال) -- فقط یک‌بار ساخته می‌شود
        rnd = random.Random(20260904)
        self._stars = [(rnd.random(), rnd.random(),
                        rnd.choice((0.8, 1.0, 1.0, 1.4, 1.8)),
                        rnd.randint(26, 120)) for _ in range(150)]

        # ---- بافرهای رندر: لایهٔ زمینه و لایهٔ صحنه ----
        self._bg = QPixmap()
        self._scene = QPixmap()
        self._buf_size = (0, 0)
        self._scene_dirty = True
        self._fx = {}

        # ---- پالس زنده ----
        self._pulse_parts: set = set()
        self._pulse_alpha = 0.0
        self._pulse_t0 = 0.0
        self._clock = QElapsedTimer()
        self._clock.start()
        self._frame_timer = QTimer(self)
        self._frame_timer.setInterval(self.FRAME_MS)
        self._frame_timer.timeout.connect(self._tick)
        self._data_timer = QTimer(self)
        self._data_timer.setSingleShot(True)
        self._data_timer.setInterval(self.FRAME_MS)
        self._data_timer.timeout.connect(self._flush)

    # ------------------------------------------------------------------
    def set_data(self, geo, res, cg_measured=False):
        """دادهٔ تازه (هر پکت تله‌متری/تغییر پارامتر) -- ادغام‌شده در فریم بعد."""
        self._geo, self._res, self._cg_measured = geo, res, cg_measured
        self._scene_dirty = True
        if not self._data_timer.isActive():
            self._data_timer.start()

    def highlight(self, field_key: str):
        """پالس نورِ نرم روی عضوِ مرتبط با فیلدی که تغییر کرده."""
        parts = FIELD_HL.get(field_key)
        if not parts:
            return
        self._pulse_parts = set(parts)
        self._pulse_t0 = float(self._clock.elapsed())
        self._pulse_alpha = 1.0
        self._frame_timer.start()
        self.update()

    def _tick(self):
        dt = self._clock.elapsed() - self._pulse_t0
        a = 1.0 - dt / self.PULSE_MS
        if a <= 0.0:
            self._pulse_alpha = 0.0
            self._pulse_parts.clear()
            self._frame_timer.stop()
        else:
            self._pulse_alpha = a * a          # ease-out
        self.update()

    def _flush(self):
        self.update()

    def _pulse(self, part: str) -> float:
        return self._pulse_alpha if part in self._pulse_parts else 0.0

    # ------------------------------------------------------------------
    def paintEvent(self, ev):
        w, h = self.width(), self.height()
        if w < 2 or h < 2:
            return
        self._ensure_buffers(w, h)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        if not self._bg.isNull():
            p.drawPixmap(0, 0, self._bg)
        if not self._scene.isNull():
            p.drawPixmap(0, 0, self._scene)
        self._paint_pulse(p)
        p.end()

    # ------------------------------------------------------------------
    def _ensure_buffers(self, w: int, h: int):
        if (w, h) != self._buf_size or self._bg.isNull():
            dpr = self.devicePixelRatioF()
            self._bg = self._make_buffer(w, h, dpr)
            self._scene = self._make_buffer(w, h, dpr)
            self._buf_size = (w, h)
            self._scene_dirty = True
            q = QPainter(self._bg)
            q.setRenderHint(QPainter.Antialiasing)
            self._render_backdrop(q, w, h)
            q.end()
        if self._scene_dirty:
            self._scene_dirty = False
            w_px, h_px = self._scene.width(), self._scene.height()
            q = QPainter(self._scene)
            q.setRenderHint(QPainter.Antialiasing)
            q.setCompositionMode(QPainter.CompositionMode_Source)
            q.fillRect(0, 0, w_px, h_px, Qt.transparent)
            q.setCompositionMode(QPainter.CompositionMode_SourceOver)
            self._render_scene(q, w, h)
            q.end()

    @staticmethod
    def _make_buffer(w: int, h: int, dpr: float) -> QPixmap:
        pm = QPixmap(max(1, int(round(w * dpr))), max(1, int(round(h * dpr))))
        pm.setDevicePixelRatio(dpr)
        pm.fill(Qt.transparent)
        return pm

    # ------------------------------------------------------------------
    def _render_backdrop(self, p: QPainter, w: int, h: int):
        """فضای عمیق: گرادیان شب + نبولا + ستاره‌ها + وینیت."""
        # قابِ شیشه‌ایِ گرد: همهٔ لایه‌های زمینه داخل آن برش می‌خورند
        frame = QRectF(0.5, 0.5, w - 1, h - 1)
        clip = QPainterPath()
        clip.addRoundedRect(frame, 18, 18)
        p.setClipPath(clip)

        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0.0, QColor(THEME["bg0"]))
        grad.setColorAt(0.55, QColor(THEME["bg1"]))
        grad.setColorAt(1.0, QColor(THEME["bg2"]))
        p.fillRect(QRectF(0, 0, w, h), QBrush(grad))

        # دو مه‌رنگِ خیلی ملایم (عمقِ فضایی)
        for (ux, uy, col, alpha, rad) in (
                (0.80, 0.16, THEME["neon_cyber"], 20, 0.55),
                (0.14, 0.86, THEME["purple"], 16, 0.50),
                (0.50, 0.45, THEME["neon_jade"], 8, 0.70)):
            g = QRadialGradient(w * ux, h * uy, max(w, h) * rad)
            g.setColorAt(0.0, alpha_color(col, alpha))
            g.setColorAt(1.0, alpha_color(col, 0))
            p.fillRect(QRectF(0, 0, w, h), QBrush(g))

        # میدان ستاره
        p.setPen(Qt.NoPen)
        for (ux, uy, rr, aa) in self._stars:
            p.setBrush(QColor(214, 226, 255, aa))
            p.drawEllipse(QPointF(ux * w, uy * h), rr, rr)

        # وینیت نرم
        vg = QRadialGradient(w / 2, h / 2, max(w, h) * 0.75)
        vg.setColorAt(0.0, QColor(0, 0, 0, 0))
        vg.setColorAt(1.0, QColor(3, 5, 14, 120))
        p.fillRect(QRectF(0, 0, w, h), QBrush(vg))

        # بیرون از برش: حاشیهٔ نورِ قاب + امضای گوشهٔ بالا
        p.setClipping(False)
        self._soft_pen(p, (148, 163, 255), 30, 1)
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(frame, 18, 18)
        p.setPen(QColor(147, 160, 196, 60))
        p.setFont(self._f(9, bold=True))
        p.drawText(QRectF(18, 12, 220, 18), Qt.AlignLeft, "ROCKET DESIGNER")

    @staticmethod
    def _f(px, bold=False):
        f = QFont("Shabnam", px)
        f.setBold(bold)
        return f

    # ------------------------------------------------------------------
    @staticmethod
    def _soft_pen(p: QPainter, rgb, alpha: float, width: float):
        pen = QPen(QColor(int(rgb[0]), int(rgb[1]), int(rgb[2]),
                          max(0, min(255, int(alpha)))), width)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)

    @staticmethod
    def _halo(p: QPainter, rgb, alpha: float, draw):
        """هالهٔ نورِ نرم: سه پاسِ هم‌مرکز با آلفای نزولی."""
        if alpha <= 0.02:
            return
        p.setBrush(Qt.NoBrush)
        for width, mul in ((11.0, 0.10), (5.5, 0.22), (2.0, 0.55)):
            Blueprint._soft_pen(p, rgb, 255 * alpha * mul, width)
            draw(p)

    # ------------------------------------------------------------------
    def _render_scene(self, p: QPainter, w: int, h: int):
        self._fx = {}
        if self._geo is None:
            p.setPen(alpha_color(THEME["sub"], 200))
            p.setFont(self._f(13))
            p.drawText(QRectF(0, 0, w, h), Qt.AlignCenter, "پارامترها را وارد کنید")
            return

        geo, res = self._geo, self._res
        total = geo.total_length_mm
        r = geo.body_diameter_mm / 2.0
        s_fin = geo.fin_span_mm

        avail_w = w - 2 * MARGIN
        avail_h = h - 2 * MARGIN - RULER_H
        need_half = r + s_fin + 34.0
        sc = min(avail_w / total, avail_h / (2 * need_half))
        cy = MARGIN + avail_h / 2.0
        # ---- وسط‌چین: نوک دماغه و انتها به‌تناظر حولِ مرکز بوم ----
        cx = w / 2.0

        def sx(x): return cx + (total / 2.0 - x) * sc
        def sy(y): return cy + y * sc

        # نسخهٔ مهارشده برای نشانگرها/اندازه‌ها: اگر CG اندازه‌گیری‌شده بیرون از
        # بدنه وارد شود، برچسب‌ها از بوم بیرون نمی‌زنند
        def sxc(x): return min(max(sx(x), 10.0), float(w) - 10.0)

        self._cy, self._sc = cy, sc

        # خطِ محورِ خیلی ملایم (حسِ فضای HUD)
        self._soft_pen(p, _rgb(THEME["neon_cyber"]), 26, 1)
        p.setBrush(Qt.NoBrush)
        p.drawLine(QPointF(MARGIN, cy), QPointF(w - MARGIN, cy))

        self._paint_band(p, res, geo, sx, sy, r)
        self._paint_body(p, geo, sx, sy, r, total)
        self._paint_nose(p, geo, sx(0), sx(geo.nose_length_mm), cy, r * sc)
        self._paint_fins(p, geo, sx, sy, r)
        if res is not None:
            self._paint_markers(p, res, sxc, cy)
            self._paint_dims(p, geo, res, sxc, sy, r, s_fin, total, cy, sc)
        self._paint_ruler(p, w, h, sc, sx(0))

    # ------------------------------------------------------------------
    def _paint_band(self, p, res, geo, sx, sy, r):
        if res is None or geo.body_diameter_mm <= 0:
            return
        d = geo.body_diameter_mm
        x_a = min(max(res.x_cp_mm - 2 * d, 0.0), geo.total_length_mm)
        x_b = min(max(res.x_cp_mm - 1 * d, 0.0), geo.total_length_mm)
        rect = QRectF(QPointF(sx(x_a), sy(-r) - 5), QPointF(sx(x_b), sy(r) + 5))
        rgb = _rgb(THEME["green"])
        p.setBrush(QColor(rgb[0], rgb[1], rgb[2], 34))
        self._soft_pen(p, rgb, 90, 1)
        p.setPen(QPen(QColor(rgb[0], rgb[1], rgb[2], 90), 1, Qt.DashLine))
        p.drawRoundedRect(rect, 7, 7)
        p.setPen(alpha_color(THEME["green"], 200))
        p.setFont(self._f(9))
        lw = 180.0
        p.drawText(QRectF(rect.center().x() - lw / 2, rect.y() - 20, lw, 16),
                   Qt.AlignHCenter, "محدودهٔ مطلوب CG")

    # ------------------------------------------------------------------
    def _paint_body(self, p, geo, sx, sy, r, total):
        x0, x1 = sx(geo.nose_length_mm), sx(total)
        rect = QRectF(QPointF(x1, sy(-r)), QPointF(x0, sy(r)))
        rgb = _rgb(THEME["body"])
        self._halo(p, rgb, 0.35, lambda q: q.drawRect(rect))
        grad = QLinearGradient(0, rect.top(), 0, rect.bottom())
        grad.setColorAt(0.0, QColor("#3d4f8f"))
        grad.setColorAt(0.45, QColor("#2b3a6e"))
        grad.setColorAt(1.0, QColor("#1d2850"))
        p.setBrush(QBrush(grad))
        self._soft_pen(p, (158, 178, 240), 210, 1.2)
        p.drawRoundedRect(rect, 3, 3)
        # برقِ ملایم روی بدنه
        shine = QLinearGradient(0, rect.top(), 0, rect.bottom())
        shine.setColorAt(0.0, QColor(255, 255, 255, 26))
        shine.setColorAt(0.35, QColor(255, 255, 255, 0))
        p.setBrush(QBrush(shine))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(rect, 3, 3)
        # خط محورِ داخلی
        self._soft_pen(p, rgb, 50, 1)
        p.setPen(QPen(QColor(rgb[0], rgb[1], rgb[2], 50), 1, Qt.DotLine))
        p.drawLine(QPointF(x1 + 2, sy(0)), QPointF(x0 - 2, sy(0)))
        self._fx["body"] = rect

    # ------------------------------------------------------------------
    def _paint_nose(self, p, geo, x_tip, x_base, y_axis, rr):
        L = x_base - x_tip
        k = 0.5523
        shape = geo.nose_shape
        base_top, base_bot = QPointF(x_base, y_axis - rr), QPointF(x_base, y_axis + rr)
        tip = QPointF(x_tip, y_axis)
        tip_top = QPointF(x_tip, y_axis - rr)
        tip_bot = QPointF(x_tip, y_axis + rr)

        path = QPainterPath()
        if shape == "تخت":
            # دماغهٔ تخت: چهارگوشِ واقعی (هندسهٔ صادق)
            path.moveTo(base_top)
            path.lineTo(tip_top)
            path.lineTo(tip_bot)
            path.lineTo(base_bot)
            path.closeSubpath()
        else:
            path.moveTo(tip)
            if shape == "مخروطی":
                path.lineTo(base_top)
            elif shape == "نیم‌کره":
                path.cubicTo(QPointF(x_tip, y_axis - rr * k),
                             QPointF(x_tip + L * k, y_axis - rr), base_top)
            else:  # اویو
                path.cubicTo(QPointF(x_tip + L * 0.40, y_axis - rr * 0.10),
                             QPointF(x_tip + L * 0.82, y_axis - rr * 0.88), base_top)
            path.lineTo(base_bot)
            if shape == "مخروطی":
                path.lineTo(tip)
            elif shape == "نیم‌کره":
                path.cubicTo(QPointF(x_tip + L * k, y_axis + rr),
                             QPointF(x_tip, y_axis + rr * k), tip)
            else:
                path.cubicTo(QPointF(x_tip + L * 0.82, y_axis + rr * 0.88),
                             QPointF(x_tip + L * 0.40, y_axis + rr * 0.10), tip)
            path.closeSubpath()

        rgb = _rgb(THEME["teal"])
        self._halo(p, rgb, 0.4, lambda q: q.drawPath(path))
        grad = QLinearGradient(x_tip, 0, x_base, 0)
        grad.setColorAt(0.0, QColor("#7ff0dc"))
        grad.setColorAt(0.6, QColor("#39c9ae"))
        grad.setColorAt(1.0, QColor("#22998a"))
        p.setBrush(QBrush(grad))
        self._soft_pen(p, (178, 246, 232), 220, 1.2)
        p.drawPath(path)
        self._fx["nose"] = path

    # ------------------------------------------------------------------
    def _paint_fins(self, p, geo, sx, sy, r):
        xb = geo.fin_root_le_from_nose_mm
        cr, ct, xr_, sp = (geo.fin_root_chord_mm, geo.fin_tip_chord_mm,
                           geo.fin_sweep_mm, geo.fin_span_mm)
        top = [QPointF(sx(xb), sy(-r)), QPointF(sx(xb + cr), sy(-r)),
               QPointF(sx(xb + xr_ + ct), sy(-r - sp)), QPointF(sx(xb + xr_), sy(-r - sp))]
        bot = [QPointF(pt.x(), 2 * self._cy - pt.y()) for pt in top]

        rgb = _rgb(THEME["purple"])
        grad = QLinearGradient(0, self._cy - (r + sp) * self._sc, 0, self._cy)
        grad.setColorAt(0.0, QColor("#c9b8ff"))
        grad.setColorAt(1.0, QColor("#6d55d8"))
        self._halo(p, rgb, 0.3, lambda q: q.drawPolygon(QPolygonF(bot)))
        p.setBrush(QBrush(grad))
        self._soft_pen(p, (222, 210, 255), 200, 1.2)
        p.drawPolygon(QPolygonF(bot))
        p.setOpacity(0.5)
        p.drawPolygon(QPolygonF(top))
        p.setOpacity(1.0)
        self._fx["fins"] = (QPolygonF(top), QPolygonF(bot))

    # ------------------------------------------------------------------
    def _paint_markers(self, p, res, sx, cy):
        self._marker(p, sx(res.x_cp_mm), cy, THEME["blue"], "CP", "مرکز فشار",
                     above=True, fx_key="cp")
        lbl = "CG" + (" (اندازه‌گیری)" if self._cg_measured else "")
        self._marker(p, sx(res.x_cg_mm), cy, THEME["yellow"], lbl, "مرکز ثقل",
                     above=False, fx_key="cg")

    def _marker(self, p, x, cy, hexcol, tag, sub, above, fx_key=None):
        rad = 9
        # مهار نشانگر داخل بوم تا حلقه و چیپ‌ها هرگز بریده نشوند
        x = min(max(x, rad + 4.0), float(self.width()) - rad - 4.0)
        c = QColor(hexcol)
        rgb = (c.red(), c.green(), c.blue())
        # هالهٔ نور
        halo = QRadialGradient(QPointF(x, cy), rad * 2.6)
        halo.setColorAt(0.0, QColor(rgb[0], rgb[1], rgb[2], 90))
        halo.setColorAt(1.0, QColor(rgb[0], rgb[1], rgb[2], 0))
        p.setBrush(QBrush(halo))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(x, cy), rad * 2.6, rad * 2.6)
        # خط راهنمای نرم
        self._soft_pen(p, rgb, 130, 1)
        p.setPen(QPen(QColor(rgb[0], rgb[1], rgb[2], 130), 1, Qt.DashLine))
        p.drawLine(QPointF(x, cy - 52 if above else cy + 16),
                   QPointF(x, cy - 12 if above else cy + 52))
        # حلقه + پره‌ها
        rect = QRectF(x - rad, cy - rad, 2 * rad, 2 * rad)
        p.setBrush(QBrush(QColor(rgb[0], rgb[1], rgb[2], 235)))
        self._soft_pen(p, (242, 246, 255), 230, 1.4)
        p.drawPie(rect, 90 * 16, 90 * 16)
        p.drawPie(rect, 270 * 16, 90 * 16)
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(rect)
        # چیپ‌های شیشه‌ای
        ty = cy - rad - 46 if above else cy + rad + 30
        chip1 = self._chip(p, x, ty, tag, "#ffffff", hexcol, strong=True)
        chip2 = self._chip(p, x, ty + 21, sub, THEME["sub"], None)
        if fx_key:
            self._fx[fx_key] = (QPointF(x, cy), rad, chip1, chip2)

    # ------------------------------------------------------------------
    def _paint_dims(self, p, geo, res, sx, sy, r, s_fin, total, cy, sc):
        vc = verdict_color(res.verdict)
        self._dim(p, sx(total), sx(0), cy - r * sc - 34,
                  fa(f"طول کل {total / 10:.0f} cm"), THEME["sub"], "dim_total")
        self._dim_v(p, sx(total) - 18, sy(-r), sy(r),
                    fa(f"قطر {geo.body_diameter_mm:.0f}"), THEME["blue"],
                    "dim_diam")
        xb = geo.fin_root_le_from_nose_mm
        xr_ = geo.fin_sweep_mm
        ct = geo.fin_tip_chord_mm
        self._dim_v(p, sx(xb + xr_ + ct) - 22, sy(r), sy(r + s_fin),
                    fa(f"دهانه {s_fin:.0f}"), THEME["purple"], "dim_span")
        self._dim(p, sx(geo.nose_length_mm), sx(0), cy - r * sc - 58,
                  fa(f"مخروط {geo.nose_length_mm / 10:.0f} cm"), THEME["teal"],
                  "dim_nose")
        y_dim = cy + (r + s_fin) * sc + 34
        self._dim(p, sx(res.x_cg_mm), sx(res.x_cp_mm), y_dim,
                  fa(f"CG تا CP: {abs(res.x_cp_mm - res.x_cg_mm):.0f} mm"), vc,
                  "dim_cgcp")

    def _dim(self, p, x1, x2, y, label, hexcol, fx_key=None):
        c = QColor(hexcol)
        rgb = (c.red(), c.green(), c.blue())
        self._soft_pen(p, rgb, 150, 1)
        p.drawLine(QPointF(x1, y), QPointF(x2, y))
        for xx in (x1, x2):                      # سردرِ نرم به‌جای پیکان تیز
            p.drawLine(QPointF(xx, y - 4), QPointF(xx, y + 4))
        chip = self._chip(p, (x1 + x2) / 2, y - 11, label,
                          THEME["text"], hexcol)
        if fx_key:
            self._fx[fx_key] = {"line": (QPointF(x1, y), QPointF(x2, y)),
                                "chip": chip, "color": c}

    def _dim_v(self, p, x, y1, y2, label, hexcol, fx_key=None):
        c = QColor(hexcol)
        rgb = (c.red(), c.green(), c.blue())
        self._soft_pen(p, rgb, 150, 1)
        p.drawLine(QPointF(x, y1), QPointF(x, y2))
        for yy in (y1, y2):
            p.drawLine(QPointF(x - 4, yy), QPointF(x + 4, yy))
        cx = min(max(x - 44, 54.0), float(self.width()) - 54.0)
        chip = self._chip(p, cx, (y1 + y2) / 2, label, THEME["text"], hexcol)
        if fx_key:
            self._fx[fx_key] = {"line": (QPointF(x, y1), QPointF(x, y2)),
                                "chip": chip, "color": c}

    def _chip(self, p, cx, cy, text, fg, accent, strong=False):
        """قرصِ شیشه‌ایِ نرم برای برچسب‌ها."""
        f = self._f(9, bold=strong)
        fm = QFontMetricsF(f)
        tw = fm.horizontalAdvance(text)
        hgt = 18.0
        # مهار افقی چیپ داخل بوم
        cx = min(max(cx, tw / 2 + 10.0), float(self.width()) - tw / 2 - 10.0)
        rect = QRectF(cx - tw / 2 - 8, cy - hgt / 2, tw + 16, hgt)
        if accent:
            a = QColor(accent)
            p.setBrush(QColor(a.red(), a.green(), a.blue(), 60 if not strong else 200))
            edge = (a.red(), a.green(), a.blue())
            edge_a = 150 if not strong else 230
        else:
            p.setBrush(QColor(16, 24, 46, 200))
            edge = _rgb(THEME["sub"])
            edge_a = 70
        self._soft_pen(p, edge, edge_a, 1)
        p.drawRoundedRect(rect, hgt / 2, hgt / 2)
        p.setFont(f)
        p.setPen(QColor(fg))
        p.drawText(rect, Qt.AlignCenter, text)
        return rect

    # ------------------------------------------------------------------
    def _paint_ruler(self, p, w, h, sc, x_nose):
        y = h - 14
        p.setFont(self._f(9))
        step_cm = 1
        # نگهبان: با بدنهٔ خیلی بلند (sc کوچک) این حلقه باید تمام شود؛ حالت
        # sc<=0 هم هرگز باعث قفل شدن نمی‌شود (اشکال پیشین: else 10 به‌جای *10)
        if sc > 1e-6:
            while step_cm * 10.0 * sc < 34 and step_cm < 100000:
                step_cm = step_cm * 2 if step_cm < 5 else step_cm * 10
        else:
            step_cm = 100000
        step_px = step_cm * 10.0 * sc
        label_every = 5 if step_cm <= 2 else 2
        self._soft_pen(p, _rgb(THEME["border"]), 200, 1)
        p.drawLine(QPointF(MARGIN - 8, y), QPointF(w - MARGIN + 8, y))
        i = 0
        x = x_nose
        while x > MARGIN - 8 and i < 2000 and step_px > 0.5:
            big = (i % label_every == 0)
            col = THEME["teal"] if big else THEME["sub"]
            cc = QColor(col)
            self._soft_pen(p, (cc.red(), cc.green(), cc.blue()), 210 if big else 120, 1)
            p.drawLine(QPointF(x, y), QPointF(x, y - (9 if big else 5)))
            if big:
                p.setPen(alpha_color(THEME["sub"], 190))
                p.drawText(QPointF(x - 8, y - 12), fa(i * step_cm))
            x -= step_px
            i += 1
        p.setPen(alpha_color(THEME["sub"], 160))
        # برچسب محور از سمت راست (صفرِ خط‌کش در چیدمان راست‌به‌چپ سمت راست است)
        p.drawText(QRectF(MARGIN - 8, y + 2, w - 2 * (MARGIN - 8), 12),
                   Qt.AlignRight | Qt.AlignVCenter, "سانتی‌متر از نوک دماغه")

    # ------------------------------------------------------------------
    # لایهٔ انیمیشن: پالسِ نورِ نرم روی بافرهای آماده
    # ------------------------------------------------------------------
    def _paint_pulse(self, p: QPainter):
        if self._pulse_alpha <= 0.0 or not self._pulse_parts or not self._fx:
            return
        a = self._pulse_alpha

        rect = self._fx.get("body")
        if rect is not None and self._pulse("body"):
            glow = QRectF(rect).adjusted(-3, -3, 3, 3)
            self._halo(p, PULSE_RGB["body"], a, lambda q: q.drawRoundedRect(glow, 5, 5))

        path = self._fx.get("nose")
        if path is not None and self._pulse("nose"):
            self._halo(p, PULSE_RGB["nose"], a, lambda q: q.drawPath(path))

        fins = self._fx.get("fins")
        if fins is not None and self._pulse("fins"):
            self._halo(p, PULSE_RGB["fins"], a, lambda q: q.drawPolygon(fins[0]))
            self._halo(p, PULSE_RGB["fins"], a, lambda q: q.drawPolygon(fins[1]))

        for key in ("cg", "cp"):
            if not self._pulse(key):
                continue
            info = self._fx.get(key)
            if not info:
                continue
            centre, rad, chip1, chip2 = info
            rgb = PULSE_RGB[key]
            rr = rad + 7.0 * (1.0 - a)
            self._soft_pen(p, rgb, 210 * a, 2)
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(centre, rr, rr)
            for chip in (chip1, chip2):
                box = QRectF(chip).adjusted(-2.5, -2.5, 2.5, 2.5)
                self._halo(p, rgb, a * 0.9,
                           lambda q, b=box: q.drawRoundedRect(b, b.height() / 2, b.height() / 2))

        for key in ("dim_total", "dim_diam", "dim_span", "dim_nose", "dim_cgcp"):
            if not self._pulse(key):
                continue
            info = self._fx.get(key)
            if not info:
                continue
            (q1, q2), chip, base = info["line"], info["chip"], info["color"]
            rgb = (base.red(), base.green(), base.blue())
            self._soft_pen(p, (255, 255, 255), 200 * a, 1.8)
            p.setBrush(Qt.NoBrush)
            p.drawLine(q1, q2)
            box = QRectF(chip).adjusted(-2.5, -2.5, 2.5, 2.5)
            self._halo(p, rgb, a * 0.9,
                       lambda q, b=box: q.drawRoundedRect(b, b.height() / 2, b.height() / 2))
