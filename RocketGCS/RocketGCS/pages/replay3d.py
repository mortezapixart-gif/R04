# -*- coding: utf-8 -*-
"""صفحهٔ بازپخش پرواز (نمای ایزومتریک تخت)

طراحی قبلی (سه‌بعدی واقعی با OpenGL) به مشکلاتی برخورد:
    - جابه‌جایی راکت هنگام حرکت موس دچار لگ می‌شد (محاسبهٔ ماتریس
      دوربین روی هر رویداد mouseMove سنگین بود)
    - برچسب‌های عددی روی هم می‌افتادند
    - مسیر پرواز شلوغ و ناخوانا به نظر می‌رسید

این نسخه یک طراحی کاملاً متفاوت است: به‌جای OpenGL واقعی، صحنه با
QPainter و یک تصویرسازی «ایزومتریک تخت» (Flat Isometric -- سبک رایج در
داشبوردهای HUD/مانیتورینگ) رسم می‌شود:
    - عملکرد بسیار سریع‌تر (فقط یک ضرب برداری numpy برای تشخیص نزدیک‌ترین
      نقطهٔ مسیر به موس، بدون هیچ محاسبهٔ ماتریسی سه‌بعدی روی هر فریم)
    - برچسب‌ها هرکدام پس‌زمینهٔ «چیپ»ی مخصوص به خود دارند و با فاصلهٔ ثابت
      از نقطهٔ مربوطه جاگذاری می‌شوند تا هرگز روی هم نیفتند
    - زوم با قلتک موس دقیقاً به‌سمت نقطهٔ زیر نشانگر (ریاضی دقیق در فضای
      دوبعدی، نه تقریب)
    - پن با درگ‌کردن دکمهٔ چپ موس

این صفحه فقط از data_manager.flight_df می‌خواند، پس چه دادهٔ پرواز واقعی
باشد چه دادهٔ پروازِ فرضیِ «حالت آموزشی»، دقیقاً همین‌طور کار می‌کند.
"""
import math
import numpy as np
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QSlider, QLabel
from PySide6.QtCore import Qt, QTimer, QPointF, QRectF, Signal
from PySide6.QtGui import (QPainter, QColor, QLinearGradient, QPen, QBrush, QPainterPath,
                            QFont, QPolygonF)
from ui.widgets import make_card
from ui.style import APP_FONT_FAMILY
from core.data_manager import data_manager
from core.report_text import protect_latin_quantities

COS30 = math.cos(math.radians(30))
SIN30 = math.sin(math.radians(30))

COLOR_ASCENT = QColor(250, 181, 51)
COLOR_FREEFALL = QColor(240, 84, 79)
COLOR_CHUTE = QColor(79, 209, 197)
COLOR_GROUND = QColor(140, 153, 173, 130)
COLOR_START = QColor(89, 209, 128)
COLOR_APOGEE = QColor(250, 181, 51)
COLOR_LANDING = QColor(240, 84, 79)


class IsoFlightCanvas(QWidget):
    """بوم رسم مسیر پرواز به سبک ایزومتریک تخت."""

    azimuth_changed = Signal(float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(480)
        self.setMouseTracking(True)
        self.setCursor(Qt.OpenHandCursor)

        self._wx = self._wy = self._wz = None
        self.iso_x = self.iso_y_flight = self.iso_y_ground = None
        self.t = self.alt = self.vel = None
        self.launch_idx = self.apogee_idx = self.parachute_idx = self.landing_idx = None
        self.current_idx = 0
        self.has_data = False

        self.azimuth_deg = 0.0   # چرخش صحنه حول محور عمودی (Roll) -- ۰ = نمای پیش‌فرض ایزومتریک
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.view_scale = 1.0

        self._dragging = False
        self._drag_start = QPointF()
        self._drag_pan_start = (0.0, 0.0)
        self._rotating = False
        self._rotate_start_x = 0.0
        self._rotate_start_az = 0.0
        self._hover_idx = None
        self._hover_screen = None
        self._landing_label_text = None
        self._fitted_with_real_size = False

    # ------------------------------------------------------------------
    def _recompute_projection(self):
        """اعمال چرخش افقی (Azimuth) روی مختصات جهانی و سپس تصویر ایزومتریک
        ثابت (زاویهٔ ۳۰ درجه) -- در azimuth=0 دقیقاً همان فرمول قبلی است،
        پس نمای پیش‌فرض هیچ تغییری نمی‌کند."""
        if self._wx is None:
            return
        az = math.radians(self.azimuth_deg)
        cos_a, sin_a = math.cos(az), math.sin(az)
        xr = self._wx * cos_a - self._wy * sin_a
        yr = self._wx * sin_a + self._wy * cos_a
        self.iso_x = (xr - yr) * COS30
        self.iso_y_flight = (xr + yr) * SIN30 + self._wz
        self.iso_y_ground = (xr + yr) * SIN30

    def set_azimuth(self, deg: float, refit: bool = False):
        self.azimuth_deg = deg % 360.0
        self._recompute_projection()
        if refit:
            self._auto_fit()
        self.update()
        self.azimuth_changed.emit(self.azimuth_deg)

    # ------------------------------------------------------------------
    def set_flight(self, x, y, z, t, alt, vel, launch_idx, apogee_idx, parachute_idx, landing_idx):
        self._wx, self._wy, self._wz = x, y, z
        self._recompute_projection()
        self.t = t
        self.alt = alt
        self.vel = vel
        self.launch_idx = launch_idx or 0
        self.apogee_idx = apogee_idx
        self.parachute_idx = parachute_idx
        self.landing_idx = landing_idx
        self.current_idx = 0
        self.has_data = True
        self._auto_fit()
        if self.width() > 50 and self.height() > 50:
            self._fitted_with_real_size = True
        self.update()

    def clear_flight(self):
        self.has_data = False
        self.update()

    def _auto_fit(self):
        if self.iso_x is None or len(self.iso_x) == 0:
            return
        all_x = self.iso_x
        all_y = np.concatenate([self.iso_y_flight, self.iso_y_ground])
        span_x = max(float(np.max(all_x) - np.min(all_x)), 1.0)
        span_y = max(float(np.max(all_y) - np.min(all_y)), 1.0)
        w, h = max(self.width(), 200), max(self.height(), 200)
        margin = 0.72
        self.view_scale = min((w * margin) / span_x, (h * margin) / span_y)
        self.pan_x = float(np.min(all_x) + np.max(all_x)) / 2.0
        self.pan_y = float(np.min(all_y) + np.max(all_y)) / 2.0

    # ------------------------------------------------------------------
    def _origin(self):
        return self.width() / 2.0, self.height() * 0.66

    def world_to_screen(self, ix, iy):
        cx, cy = self._origin()
        return cx + (ix - self.pan_x) * self.view_scale, cy - (iy - self.pan_y) * self.view_scale

    def screen_to_world(self, px, py):
        cx, cy = self._origin()
        return (px - cx) / self.view_scale + self.pan_x, -(py - cy) / self.view_scale + self.pan_y

    def set_playhead(self, idx: int):
        if self.t is None:
            return
        self.current_idx = int(np.clip(idx, 0, len(self.t) - 1))
        self.update()

    # ------------------------------------------------------------------
    def wheelEvent(self, ev):
        delta = ev.angleDelta().y()
        if delta == 0 or not self.has_data:
            return
        old_scale = self.view_scale
        factor = 1.0015 ** delta
        new_scale = float(np.clip(old_scale * factor, 0.02, 200.0))

        pos = ev.position() if hasattr(ev, "position") else ev.pos()
        wx, wy = self.screen_to_world(pos.x(), pos.y())
        self.view_scale = new_scale
        sx, sy = self.world_to_screen(wx, wy)
        # جبران جابه‌جایی: pan را طوری اصلاح کن که نقطهٔ زیر موس دقیقاً همان‌جا بماند
        self.pan_x += (pos.x() - sx) / self.view_scale
        self.pan_y -= (pos.y() - sy) / self.view_scale
        self.update()

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            self._dragging = True
            self._drag_start = ev.position() if hasattr(ev, "position") else ev.pos()
            self._drag_pan_start = (self.pan_x, self.pan_y)
            self.setCursor(Qt.ClosedHandCursor)
        elif ev.button() == Qt.RightButton:
            self._rotating = True
            pos = ev.position() if hasattr(ev, "position") else ev.pos()
            self._rotate_start_x = pos.x()
            self._rotate_start_az = self.azimuth_deg
            self.setCursor(Qt.SizeHorCursor)

    def mouseReleaseEvent(self, ev):
        if ev.button() == Qt.LeftButton:
            self._dragging = False
            self.setCursor(Qt.OpenHandCursor)
        elif ev.button() == Qt.RightButton:
            self._rotating = False
            self.setCursor(Qt.OpenHandCursor)

    def mouseMoveEvent(self, ev):
        pos = ev.position() if hasattr(ev, "position") else ev.pos()
        if self._rotating:
            dx = pos.x() - self._rotate_start_x
            self.set_azimuth(self._rotate_start_az + dx * 0.4)
            return
        if self._dragging:
            dx = (pos.x() - self._drag_start.x()) / self.view_scale
            dy = (pos.y() - self._drag_start.y()) / self.view_scale
            self.pan_x = self._drag_pan_start[0] - dx
            self.pan_y = self._drag_pan_start[1] + dy
            self.update()
            return

        if not self.has_data or self.iso_x is None:
            self._hover_idx = None
            self.update()
            return

        # جست‌وجوی نزدیک‌ترین نقطه با یک عملیات برداری numpy (سریع، بدون لگ)
        sx = (self.iso_x - self.pan_x) * self.view_scale + self.width() / 2.0
        sy = self._origin()[1] - (self.iso_y_flight - self.pan_y) * self.view_scale
        dists = np.hypot(sx - pos.x(), sy - pos.y())
        j = int(np.argmin(dists))
        if dists[j] <= 30:
            self._hover_idx = j
            self._hover_screen = (float(sx[j]), float(sy[j]))
        else:
            self._hover_idx = None
        self.update()

    def leaveEvent(self, ev):
        self._hover_idx = None
        self.update()

    # ------------------------------------------------------------------
    def _draw_chip_label(self, painter, anchor, text, color, offset=(14, -14), font_size=10, bold=True):
        painter.save()
        font = QFont(APP_FONT_FAMILY, font_size, QFont.Bold if bold else QFont.Normal)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        tw = metrics.horizontalAdvance(text) + 14
        th = metrics.height() + 8
        x = anchor[0] + offset[0]
        y = anchor[1] + offset[1] - th
        rect = QRectF(x, y, tw, th)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(15, 19, 26, 225)))
        painter.drawRoundedRect(rect, 6, 6)
        painter.setPen(QPen(color, 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect, 6, 6)
        painter.setPen(QPen(color))
        painter.drawText(rect, Qt.AlignCenter, text)
        # خط رابط کوچک از چیپ به نقطهٔ اصلی
        painter.setPen(QPen(color, 1, Qt.DashLine))
        painter.drawLine(QPointF(anchor[0], anchor[1]), QPointF(x + tw / 2, y + th))
        painter.restore()

    def _draw_marker(self, painter, screen_pos, color, radius=6):
        painter.save()
        painter.setPen(QPen(QColor(10, 12, 16), 1.5))
        painter.setBrush(QBrush(color))
        painter.drawEllipse(QPointF(*screen_pos), radius, radius)
        painter.restore()

    def paintEvent(self, ev):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        bg = QLinearGradient(0, 0, 0, h)
        bg.setColorAt(0.0, QColor(15, 20, 28))
        bg.setColorAt(1.0, QColor(9, 12, 17))
        painter.fillRect(self.rect(), bg)

        if not self.has_data or self.iso_x is None or len(self.iso_x) < 2:
            painter.setPen(QColor(120, 132, 150))
            painter.setFont(QFont(APP_FONT_FAMILY, 12))
            painter.drawText(self.rect(), Qt.AlignCenter, "داده‌ای برای نمایش وجود ندارد")
            return

        # (شبکهٔ پس‌زمینه عمداً حذف شد -- نسخهٔ قبلی فقط بخش کوچکی از صحنه را
        # می‌پوشاند و در حالت‌های مختلف زوم/پن به‌صورت یک «جعبهٔ شطرنجی شناور»
        # نامرتب دیده می‌شد؛ پس‌زمینهٔ گرادیانی ساده تمیزتر است)

        # ---- ردپای مسیر روی زمین ----
        ground_path = QPainterPath()
        gx, gy = self.world_to_screen(self.iso_x[0], self.iso_y_ground[0])
        ground_path.moveTo(gx, gy)
        for i in range(1, len(self.iso_x)):
            gx, gy = self.world_to_screen(self.iso_x[i], self.iso_y_ground[i])
            ground_path.lineTo(gx, gy)
        painter.save()
        pen_ground = QPen(COLOR_GROUND, 1.6, Qt.DashLine)
        painter.setPen(pen_ground)
        painter.drawPath(ground_path)
        painter.restore()

        # ---- مسیر پرواز رنگ‌بندی‌شده بر اساس مرحله (با افکت درخشش ساده) ----
        n = len(self.iso_x)
        seg_end_ascent = self.apogee_idx if self.apogee_idx is not None else n - 1
        seg_end_freefall = self.parachute_idx if self.parachute_idx is not None else seg_end_ascent

        def build_path(i0, i1):
            path = QPainterPath()
            sx0, sy0 = self.world_to_screen(self.iso_x[i0], self.iso_y_flight[i0])
            path.moveTo(sx0, sy0)
            for i in range(i0 + 1, i1 + 1):
                sx, sy = self.world_to_screen(self.iso_x[i], self.iso_y_flight[i])
                path.lineTo(sx, sy)
            return path

        segments = []
        if seg_end_ascent > self.launch_idx:
            segments.append((build_path(self.launch_idx, seg_end_ascent), COLOR_ASCENT))
        if seg_end_freefall > seg_end_ascent:
            segments.append((build_path(seg_end_ascent, seg_end_freefall), COLOR_FREEFALL))
        if n - 1 > seg_end_freefall:
            segments.append((build_path(seg_end_freefall, n - 1), COLOR_CHUTE))

        for path, color in segments:
            painter.save()
            glow = QColor(color); glow.setAlpha(70)
            painter.setPen(QPen(glow, 7, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.drawPath(path)
            painter.setPen(QPen(color, 2.4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            painter.drawPath(path)
            painter.restore()

        # ---- نشانگرها + برچسب‌ها ----
        launch_screen = self.world_to_screen(self.iso_x[self.launch_idx], self.iso_y_ground[self.launch_idx])
        self._draw_marker(painter, launch_screen, COLOR_START, 7)
        self._draw_chip_label(painter, launch_screen, "🚀 نقطهٔ پرتاب", COLOR_START, offset=(16, -10))

        if self.apogee_idx is not None:
            ap_screen = self.world_to_screen(self.iso_x[self.apogee_idx], self.iso_y_flight[self.apogee_idx])
            self._draw_marker(painter, ap_screen, COLOR_APOGEE, 6)
            self._draw_chip_label(painter, ap_screen, f"اوج: {float(self.alt[self.apogee_idx]):.0f} m",
                                   COLOR_APOGEE, offset=(18, -34))

        if self.landing_idx is not None:
            land_screen = self.world_to_screen(self.iso_x[self.landing_idx], self.iso_y_ground[self.landing_idx])
            self._draw_marker(painter, land_screen, COLOR_LANDING, 7)
            self._draw_chip_label(painter, land_screen, self._landing_label_text or "🛬 فرود",
                                   COLOR_LANDING, offset=(-16, -10))

        # ---- راکت متحرک ----
        idx = self.current_idx
        rx, ry = self.world_to_screen(self.iso_x[idx], self.iso_y_flight[idx])
        heading = 0.0
        if idx > 0:
            dx = self.iso_x[idx] - self.iso_x[idx - 1]
            dy = self.iso_y_flight[idx] - self.iso_y_flight[idx - 1]
            if abs(dx) > 1e-6 or abs(dy) > 1e-6:
                heading = math.degrees(math.atan2(-dy, dx)) + 90

        painter.save()
        painter.translate(rx, ry)
        painter.rotate(heading)
        rocket_poly = QPolygonF([QPointF(0, -14), QPointF(6, 8), QPointF(0, 4), QPointF(-6, 8)])
        painter.setPen(QPen(QColor(10, 12, 16), 1))
        painter.setBrush(QBrush(QColor(79, 173, 240)))
        painter.drawPolygon(rocket_poly)
        painter.restore()

        if self.parachute_idx is not None and idx >= self.parachute_idx:
            painter.save()
            painter.translate(rx, ry - 24)
            painter.setPen(QPen(QColor(230, 230, 240, 220), 1.6))
            painter.setBrush(QBrush(QColor(235, 235, 245, 90)))
            painter.drawChord(QRectF(-16, -10, 32, 22), 0, 180 * 16)
            painter.restore()

        # ---- پنل اطلاعات لحظه‌ای (گوشهٔ بالا-راست، همیشه ثابت -- بدون همپوشانی) ----
        if self.t is not None:
            t_v = float(self.t[idx]); alt_v = float(self.alt[idx]) if self.alt is not None else 0.0
            vel_v = float(self.vel[idx]) if self.vel is not None else None
            lines = [f"زمان: {t_v:.1f} s", f"ارتفاع: {alt_v:.0f} m"]
            if vel_v is not None:
                lines.append(protect_latin_quantities(f"سرعت: {vel_v:.1f} m/s"))
            self._draw_info_panel(painter, w - 195, 14, lines, QColor(79, 173, 240))

        # ---- پنل هاور موس (اگر روی مسیر باشد) ----
        if self._hover_idx is not None:
            i = self._hover_idx
            t_v = float(self.t[i]); alt_v = float(self.alt[i]) if self.alt is not None else 0.0
            vel_v = float(self.vel[i]) if self.vel is not None else None
            lines = [f"زمان: {t_v:.1f} s", f"ارتفاع: {alt_v:.0f} m"]
            if vel_v is not None:
                lines.append(protect_latin_quantities(f"سرعت: {vel_v:.1f} m/s"))
            hx, hy = self._hover_screen
            self._draw_marker(painter, (hx, hy), QColor(255, 255, 255), 4)
            self._draw_info_panel(painter, min(hx + 16, w - 195), max(hy - 70, 8), lines, QColor(255, 255, 255))

    def _draw_info_panel(self, painter, x, y, lines, accent: QColor):
        painter.save()
        font = QFont(APP_FONT_FAMILY, 13, QFont.Bold)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        tw = max(metrics.horizontalAdvance(line) for line in lines) + 20
        th = metrics.height() * len(lines) + 14
        rect = QRectF(x, y, tw, th)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(15, 19, 26, 235)))
        painter.drawRoundedRect(rect, 8, 8)
        painter.setPen(QPen(accent, 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect, 8, 8)
        painter.setPen(QColor(230, 235, 241))
        for i, line in enumerate(lines):
            line_rect = QRectF(x, y + 6 + i * metrics.height(), tw, metrics.height())
            painter.drawText(line_rect, Qt.AlignCenter, line)
        painter.restore()

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        if self.has_data and not self._fitted_with_real_size and self.width() > 50 and self.height() > 50:
            self._auto_fit()
            self._fitted_with_real_size = True
        self.update()


class Replay3DPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setLayoutDirection(Qt.RightToLeft)
        root = QVBoxLayout(self)

        self.canvas = IsoFlightCanvas()
        root.addWidget(make_card(self.canvas))

        legend = QLabel(
            "🟡 صعود با موتور &nbsp;&nbsp; 🔴 سقوط آزاد &nbsp;&nbsp; 🟢 نزول با چتر باز &nbsp;&nbsp; "
            "⚪ ردپای زمین &nbsp;&nbsp; | &nbsp;&nbsp; قلتک موس: زوم &nbsp; | &nbsp; درگ چپ: جابه‌جایی صحنه "
            "&nbsp; | &nbsp; درگ راست: چرخش صحنه (Roll)"
        )
        legend.setAlignment(Qt.AlignCenter)
        legend.setTextFormat(Qt.RichText)
        root.addWidget(legend)

        controls = QHBoxLayout()
        controls.setSpacing(12)
        self.play_btn = QPushButton("⏵\nپخش")
        self.pause_btn = QPushButton("⏸\nتوقف")
        self.slow_btn = QPushButton("🐢\nآهسته")
        self.slow_btn.setCheckable(True)

        self.time_label = QLabel("۰۰:۰۰.۰۰")
        self.time_label.setObjectName("TimeReadout")
        self.time_label.setAlignment(Qt.AlignCenter)
        self.time_label.setFixedHeight(48)

        controls.addStretch()
        for b in (self.play_btn, self.pause_btn, self.slow_btn):
            b.setObjectName("MediaButton")
            b.setFixedSize(64, 48)
            controls.addWidget(b)
        controls.addSpacing(16)
        controls.addWidget(self.time_label)
        controls.addStretch()

        # سه دکمهٔ زاویهٔ دید (Roll حول محور عمودی) -- در همین لایوت RTL، آخرین
        # آیتم‌های اضافه‌شده در گوشهٔ سمت چپ می‌نشینند (طبق خواستهٔ کاربر)
        for label, deg in (("ایزومتریک", 0), ("روبه‌رو", 90), ("از بغل", 180)):
            btn = QPushButton(label)
            btn.setObjectName("MediaButton")
            btn.setFixedSize(64, 48)
            btn.clicked.connect(lambda _=False, d=deg: self._set_view(d))
            controls.addWidget(btn)

        root.addWidget(make_card(self._wrap(controls)))

        self.time_slider = QSlider(Qt.Horizontal)
        root.addWidget(self.time_slider)

        self.play_btn.clicked.connect(self.play)
        self.pause_btn.clicked.connect(self.pause)
        self.time_slider.valueChanged.connect(self.on_slider)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)

        self.t = None
        self.avg_dt = 0.03
        data_manager.analysis_ready.connect(self.load_data)

    def _wrap(self, layout):
        w = QWidget(); w.setLayout(layout); return w

    def _set_view(self, deg: float):
        self.canvas.set_azimuth(float(deg) % 360, refit=True)

    # ------------------------------------------------------------------
    def _local_xy(self, df):
        lat = lon = None
        for cand in ("Latitude", "lat"):
            if cand in df.columns:
                lat = df[cand].astype(float).to_numpy(); break
        for cand in ("Longitude", "lon"):
            if cand in df.columns:
                lon = df[cand].astype(float).to_numpy(); break
        if lat is None or lon is None:
            n = len(df)
            return np.zeros(n), np.zeros(n)
        R = 6371000
        x = np.radians(lon - lon[0]) * R * np.cos(np.radians(lat[0]))
        y = np.radians(lat - lat[0]) * R
        return x, y

    def load_data(self, _results: dict):
        df = data_manager.flight_df
        if df is None:
            return
        from core.analysis import FlightAnalyzer
        an = FlightAnalyzer(df, data_manager.mission)
        an.detect_events()
        idx = getattr(an, "_idx", {})
        self.t = an.t
        if self.t is None or an.alt is None or len(self.t) < 2:
            self.canvas.clear_flight()
            return

        self.avg_dt = float(np.mean(np.diff(self.t))) or 0.03

        x_m, y_m = self._local_xy(df)
        z_m = np.clip(an.alt - an.alt[0], 0, None)

        launch_idx = idx.get("launch") or 0
        apogee_idx = idx.get("apogee")
        parachute_idx = idx.get("parachute")
        landing_idx = idx.get("landing")

        if landing_idx is not None:
            dist_m = float(np.hypot(x_m[landing_idx] - x_m[launch_idx], y_m[landing_idx] - y_m[launch_idx]))
            self.canvas._landing_label_text = f"🛬 فرود -- {dist_m:.0f} m از پرتاب"

        self.canvas.set_flight(x_m, y_m, z_m, self.t, an.alt, an.vel,
                                launch_idx, apogee_idx, parachute_idx, landing_idx)

        self.time_slider.setRange(0, len(self.t) - 1)
        self.time_slider.setValue(0)
        self.on_slider(0)

    # ------------------------------------------------------------------
    def play(self):
        if self.t is not None:
            self._tick_setup_interval()
            self.timer.start()

    def pause(self):
        self.timer.stop()

    def _tick_setup_interval(self):
        speed = 0.25 if self.slow_btn.isChecked() else 1.0
        interval = max(10, int(1000 * self.avg_dt / speed))
        self.timer.setInterval(interval)

    def _tick(self):
        self._tick_setup_interval()
        v = self.time_slider.value() + 1
        if self.t is not None and v >= len(self.t):
            self.timer.stop()
            return
        self.time_slider.setValue(v)

    def on_slider(self, idx: int):
        if self.t is None or idx >= len(self.t):
            return
        t = self.t[idx]
        minutes, seconds = divmod(max(0.0, t), 60)
        self.time_label.setText(f"{int(minutes):02d}:{seconds:05.2f}")
        self.canvas.set_playhead(idx)
