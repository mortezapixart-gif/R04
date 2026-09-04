# -*- coding: utf-8 -*-
"""
ui/hud_widgets.py
-------------------
ویجت‌های ترسیم‌شدهٔ سفارشی (QPainter) با ظاهر HUD علمی‌تخیلی/فضایی، برای
صفحهٔ «مرکز کنترل پرواز» (pages/hud_dashboard.py). این ویجت‌ها عمداً از ui/widgets.py
جدا نگه داشته شده‌اند چون منطق ترسیم‌شان (QPainter) کاملاً متفاوت از
کارت‌های استاندارد QSS-محور بقیهٔ برنامه است.

قانون رنگ: هر ویجت یک رنگ اصلی (accent) از ui/colors.py می‌گیرد و کاملاً با
همان رنگ (پس‌زمینه‌ی گرم/سرد، درخشش و غیره) ترسیم می‌شود -- هیچ رنگ ثابتی
اینجا هاردکد نشده مگر رنگ خنثی زمینه/خط‌چین که با بقیهٔ برنامه هم‌خوان است.
"""
import math

from PySide6.QtWidgets import QWidget, QFrame, QSizePolicy, QVBoxLayout, QHBoxLayout, QLabel
from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import (QPainter, QPen, QColor, QFont, QConicalGradient, QRadialGradient,
                            QLinearGradient, QPainterPath, QFontMetrics)
from core import palette as colors

# رنگ‌های خنثی مشترک همهٔ ویجت‌های این فایل
RING_DIM = QColor(255, 255, 255, 28)
TEXT_DIM = QColor("#8fa3b8")
TEXT_BRIGHT = QColor("#eaf2fa")


def _glow_pen(color: QColor, width: int, alpha: int = 70) -> QPen:
    """قلمِ کم‌رنگ و پهن برای شبیه‌سازی درخشش (glow) زیر خط اصلی روشن."""
    glow = QColor(color)
    glow.setAlpha(alpha)
    pen = QPen(glow, width)
    pen.setCapStyle(Qt.RoundCap)
    return pen


class HudFrame(QFrame):
    """قاب پنلی با گوشه‌های براکت‌مانند (سبک HUD فضایی) به‌جای حاشیهٔ ساده.

    فرزندان با layout معمولی داخلش چیده می‌شوند؛ این کلاس فقط بعد از رسم
    عادی، براکت‌های گوشه و یک برچسب عنوان کوچک بالا-راست اضافه می‌کند.
    """
    def __init__(self, title: str = "", accent: str = "#4fa3f7", parent=None):
        super().__init__(parent)
        self._title = title
        self._accent = QColor(accent)
        self.setObjectName("HudPanel")
        self.setStyleSheet(
            "QFrame#HudPanel { background-color: rgba(19, 24, 32, 0.92); "
            "border: 1px solid rgba(255,255,255,18); border-radius: 6px; }"
        )
        self.setContentsMargins(14, 22 if title else 14, 14, 14)

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.rect().adjusted(1, 1, -2, -2)
        L = 14  # طول هر بازوی براکت

        pen = QPen(self._accent, 2)
        pen.setCapStyle(Qt.FlatCap)
        p.setPen(pen)
        corners = [
            ((r.left(), r.top()), (1, 0), (0, 1)),
            ((r.right(), r.top()), (-1, 0), (0, 1)),
            ((r.left(), r.bottom()), (1, 0), (0, -1)),
            ((r.right(), r.bottom()), (-1, 0), (0, -1)),
        ]
        for (x, y), (dx, _), (_, dy) in corners:
            p.drawLine(x, y, x + dx * L, y)
            p.drawLine(x, y, x, y + dy * L)

        if self._title:
            p.setPen(QPen(self._accent))
            f = QFont()
            f.setPointSize(9)
            f.setBold(True)
            f.setLetterSpacing(QFont.PercentageSpacing, 110)
            p.setFont(f)
            # نکتهٔ مهم: به‌جای تکیه بر پرچم‌های Qt.AlignRight/AlignAbsolute
            # (که رفتارشان با متن راست‌چین در QPainter::drawText بسته به
            # نسخهٔ Qt/سیستم‌عامل کاربر متفاوت بود و باعث می‌شد گاهی عنوان
            # پنل‌ها روی برخی سیستم‌ها چپ‌چین دیده شوند)، موقعیت دقیق پیکسلی
            # لبهٔ راست متن را خودمان محاسبه و مستقیماً در همان‌جا رسم
            # می‌کنیم -- این روش کاملاً مستقل از پلتفرم/نسخهٔ Qt است.
            fm = QFontMetrics(f)
            text_w = fm.horizontalAdvance(self._title)
            x = r.right() - 18 - text_w
            y = r.top() + 4 + fm.ascent()
            p.drawText(QPointF(x, y), self._title)
        p.end()


class RadialGauge(QWidget):
    """گیج دایره‌ای (کمان ۲۷۰ درجه) با تیک، کمان‌مقدار درخشان و عدد مرکزی.

    «عدد + واحد لاتین» با مختصات پیکسلی جدا رسم می‌شوند، پس واحد (m، km/h،
    g، °C، hPa، %RH) همیشه **سمت راستِ عدد** است حتی در زمینهٔ RTL؛ نام
    فارسی پارامتر زیر عدد می‌آید. string ورودی unit مثل «ارتفاع (m)» است.
    """
    def __init__(self, unit: str = "", min_val: float = 0.0, max_val: float = 100.0,
                 accent: str = "#4fd1c5", decimals: int = 1, parent=None):
        super().__init__(parent)
        self._fa_label, self._latin_unit = self._split_unit(unit)
        self._min = min_val
        self._max = max_val
        self._accent = QColor(accent)
        self._decimals = decimals
        self._value = None  # None یعنی هنوز دادهٔ زنده‌ای نرسیده -- نمایش «--»
        self.setMinimumSize(150, 150)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    @staticmethod
    def _split_unit(unit: str):
        """«ارتفاع (m)» → («ارتفاع», «m») ؛ «دما (°C)» → («دما», «°C»)."""
        if "(" in unit and unit.rstrip().endswith(")"):
            latin = unit[unit.index("(") + 1:unit.rindex(")")].strip()
            label = unit[:unit.index("(")].strip(" -–\t")
            return label, latin
        return "", unit

    def set_value(self, value):
        self._value = value
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        side = min(self.width(), self.height()) - 16
        rect = QRectF((self.width() - side) / 2, (self.height() - side) / 2, side, side)

        start_angle = 225 * 16
        full_span = -270 * 16

        # کمان زمینه (خاکستری کم‌رنگ)
        pen_bg = QPen(RING_DIM, max(6, side // 16))
        pen_bg.setCapStyle(Qt.RoundCap)
        p.setPen(pen_bg)
        p.drawArc(rect, start_angle, full_span)

        # تیک‌های درجه‌بندی
        p.setPen(QPen(TEXT_DIM, 1))
        cx, cy, radius = rect.center().x(), rect.center().y(), side / 2
        for i in range(11):
            ang = math.radians(225 - i * 27)
            r1, r2 = radius - 2, radius - 9
            x1, y1 = cx + r1 * math.cos(ang), cy - r1 * math.sin(ang)
            x2, y2 = cx + r2 * math.cos(ang), cy - r2 * math.sin(ang)
            p.drawLine(QPointF(x1, y1), QPointF(x2, y2))

        # کمان مقدار (با افکت درخشش: یک لایهٔ کم‌رنگِ پهن‌تر زیر خط روشن)
        if self._value is not None:
            frac = max(0.0, min(1.0, (self._value - self._min) / (self._max - self._min or 1)))
            value_span = full_span * frac
            width_glow = max(10, side // 11)
            p.setPen(_glow_pen(self._accent, width_glow, alpha=60))
            p.drawArc(rect, start_angle, value_span)
            pen_val = QPen(self._accent, max(5, side // 20))
            pen_val.setCapStyle(Qt.RoundCap)
            p.setPen(pen_val)
            p.drawArc(rect, start_angle, value_span)

        # نوشتهٔ مرکزی: عدد + واحدِ لاتین سمتِ راستِ آن (جای‌گذاری پیکسلی جدا)
        f = QFont()
        f.setBold(True)
        f.setPointSize(max(11, side // 8))
        p.setFont(f)
        # ارقام فارسی (مثل گیج‌های پایین)؛ واحد لاتین همچنان سمت راستِ عدد
        text = _fa(f"{self._value:.{self._decimals}f}") if self._value is not None else "--"
        if self._value is not None:
            # در زمینهٔ راست‌به‌چپ، علامت منفیِ ابتدای عدد سمت راستِ رقم‌ها می‌افتد؛
            # جاسازی LRE/PDF (نامرئی) جهت عدد را چپ‌به‌راست قفل می‌کند تا منفی
            # سمت چپِ عدد بماند (با آزمون پیکسلی QPainter تأیید شده).
            text = "\u202a" + text + "\u202c"
        f_unit = QFont()
        f_unit.setBold(True)
        f_unit.setPointSize(max(8, min(11, side // 17)))
        fm_v = QFontMetrics(f)
        fm_u = QFontMetrics(f_unit)
        w_v = fm_v.horizontalAdvance(text)
        w_u = fm_u.horizontalAdvance(self._latin_unit) if self._latin_unit else 0
        gap = max(3.0, side / 38.0)
        total = w_v + (gap + w_u if self._latin_unit else 0)
        h_txt = max(fm_v.height(), fm_u.height())
        y0 = rect.center().y() - side * 0.06 - h_txt / 2.0
        x0 = rect.center().x() - total / 2.0
        p.setPen(TEXT_BRIGHT)
        p.setFont(f)
        p.drawText(QRectF(x0, y0, w_v, h_txt), Qt.AlignCenter, text)
        if self._latin_unit:
            p.setPen(TEXT_DIM)
            p.setFont(f_unit)
            p.drawText(QRectF(x0 + w_v + gap, y0, w_u, h_txt),
                       Qt.AlignCenter, self._latin_unit)

        # نام فارسی پارامتر زیر عدد
        if self._fa_label:
            f2 = QFont()
            f2.setPointSize(max(8, side // 16))
            p.setFont(f2)
            p.setPen(TEXT_DIM)
            p.drawText(rect.adjusted(0, side * 0.26, 0, side * 0.26),
                       Qt.AlignCenter, self._fa_label)
        p.end()


class AttitudeRadar(QWidget):
    """رادار موقعیت (GPS/لورا): حلقه‌های هم‌مرکز + حلقهٔ درجه‌بندی ۰/۴۵/۹۰...
    + برچسب قطب‌نما (شمال/جنوب/شرق/غرب) + بازوی چرخان تزئینی + نشانگر «محل
    پرتاب» در مرکز + نقطهٔ متحرک معرف موقعیت لحظه‌ای راکت.

    قابلیت چرخش نمایش (Head-Up) با درگ موس روی رادار انجام می‌شود؛ کل نمایش
    (حلقهٔ درجه، برچسب‌ها و نقطهٔ راکت) با هم می‌چرخند اما اعداد واقعیِ سمت
    (azimuth) که در صفحهٔ داشبورد نمایش داده می‌شوند همیشه نسبت به شمال واقعی
    باقی می‌مانند.

    چرخش با موس: کاربر با درگ روی رادار جهتِ «بالای صفحه» را دستی تنظیم می‌کند
    (سیگنال heading_changed با درجهٔ جدید ارسال می‌شود).
    """
    heading_changed = Signal(float)

    def __init__(self, accent: str = "#4fa3f7", parent=None):
        super().__init__(parent)
        self._accent = QColor(accent)
        self._sweep_deg = 0.0
        self._pos = None       # (east_m, north_m) نسبت به محل پرتاب یا None
        self._range_m = 250.0  # شعاع فعلی رادار (خودکار بزرگ می‌شود)
        self._heading_up = 0.0 # جهت جغرافیاییِ «بالای صفحه» (درجه، نسبت به شمال)
        self._drag_last = None # زاویهٔ آخرین موقعیت موس هنگام درگ (درجه)
        self.setMinimumSize(150, 150)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setCursor(Qt.OpenHandCursor)

    # -- چرخش دستی با درگ موس --
    def _angle_from_center(self, pos) -> float:
        cx, cy = self.width() / 2, self.height() / 2
        return math.degrees(math.atan2(-(pos.y() - cy), pos.x() - cx))

    def mousePressEvent(self, event):
        self._drag_last = self._angle_from_center(event.position())
        self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if self._drag_last is None:
            return
        cur = self._angle_from_center(event.position())
        delta = cur - self._drag_last
        self._drag_last = cur
        # حرکت موس در جهت بالا، نمایش را هم در همان جهت می‌چرخاند
        self._heading_up = (self._heading_up + delta) % 360
        self.heading_changed.emit(self._heading_up)
        self.update()

    def mouseReleaseEvent(self, event):
        self._drag_last = None
        self.setCursor(Qt.OpenHandCursor)

    def set_sweep_angle(self, deg: float):
        self._sweep_deg = deg % 360
        self.update()

    def set_position(self, east_m, north_m):
        """east_m/north_m: فاصلهٔ شرقی/شمالی راکت نسبت به محل پرتاب (متر).
        None/None یعنی هنوز داده‌ای (GPS/لورا) در دسترس نیست."""
        if east_m is None or north_m is None:
            self._pos = None
        else:
            self._pos = (east_m, north_m)
            dist = math.hypot(east_m, north_m)
            while dist > self._range_m and self._range_m < 20000:
                self._range_m *= 1.5
        self.update()

    def reset_range(self):
        self._range_m = 250.0

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        side = min(self.width(), self.height()) - 12
        rect = QRectF((self.width() - side) / 2, (self.height() - side) / 2, side, side)
        cx, cy, radius = rect.center().x(), rect.center().y(), side / 2

        # زاویهٔ چرخش نمایش: مقدار مثبت heading_up یعنی صفحه به‌اندازهٔ همان
        # درجه (در جهت عقربه) چرخیده تا آن سمت رو به بالا بیاید.
        rot = self._heading_up

        for frac in (1.0, 0.72, 0.44):
            p.setPen(QPen(RING_DIM, 1))
            r = radius * frac
            p.drawEllipse(QPointF(cx, cy), r, r)

        # -- حلقهٔ درجه‌بندی ۰/۴۵/۹۰/... (با چرخش نمایش هماهنگ) --
        # جهتِ جغرافیایی deg روی صفحه در زاویهٔ (deg - rot) از شمالِ صفحه قرار
        # می‌گیرد؛ شمالِ صفحه بالا است. تیک هر ۱۵ درجه، عدد هر ۴۵ درجه.
        f_deg = QFont(); f_deg.setPointSize(6)
        for deg in range(0, 360, 15):
            screen_ang = math.radians(90 - deg + rot)  # 90=بالا، خلاف عقربه مثبت
            major = deg % 45 == 0
            r1 = radius
            r2 = radius - (9 if major else 5)
            x1, y1 = cx + r1 * math.cos(screen_ang), cy - r1 * math.sin(screen_ang)
            x2, y2 = cx + r2 * math.cos(screen_ang), cy - r2 * math.sin(screen_ang)
            p.setPen(QPen(RING_DIM if not major else TEXT_DIM, 1))
            p.drawLine(QPointF(x1, y1), QPointF(x2, y2))
            if major:
                p.setFont(f_deg)
                p.setPen(TEXT_DIM)
                rt = radius - 20
                tx, ty = cx + rt * math.cos(screen_ang), cy - rt * math.sin(screen_ang)
                p.drawText(QRectF(tx - 12, ty - 8, 24, 16), Qt.AlignCenter, str(deg))

        # خطوط صلیبی نمایش (ثابت روی صفحه)
        p.setPen(QPen(RING_DIM, 1))
        p.drawLine(QPointF(cx - radius, cy), QPointF(cx + radius, cy))
        p.drawLine(QPointF(cx, cy - radius), QPointF(cx, cy + radius))

        # بازوی چرخان تزئینی (دنبالهٔ محوشونده مثل رادار)
        grad = QConicalGradient(cx, cy, -self._sweep_deg)
        c0 = QColor(self._accent); c0.setAlpha(0)
        c1 = QColor(self._accent); c1.setAlpha(130)
        grad.setColorAt(0.0, c1)
        grad.setColorAt(0.12, c0)
        grad.setColorAt(1.0, c0)
        p.setPen(Qt.NoPen)
        p.setBrush(grad)
        p.drawEllipse(QPointF(cx, cy), radius, radius)

        ang = math.radians(self._sweep_deg)
        p.setPen(QPen(self._accent, 2))
        p.drawLine(QPointF(cx, cy), QPointF(cx + radius * math.cos(ang), cy - radius * math.sin(ang)))

        # برچسب‌های قطب‌نما (با چرخش نمایش جابه‌جا می‌شوند)
        p.setPen(TEXT_BRIGHT)
        f_compass = QFont(); f_compass.setPointSize(8); f_compass.setBold(True); p.setFont(f_compass)
        compass = {"N": 0, "E": 90, "S": 180, "W": 270}
        for text, deg in compass.items():
            screen_ang = math.radians(90 - deg + rot)
            rr = radius - 34
            tx, ty = cx + rr * math.cos(screen_ang), cy - rr * math.sin(screen_ang)
            # شمال را برجسته‌تر (قرمز) نشان می‌دهیم مثل قطب‌نمای واقعی
            p.setPen(QColor("#ef5350") if text == "N" else TEXT_BRIGHT)
            p.drawText(QRectF(tx - 12, ty - 9, 24, 18), Qt.AlignCenter, text)

        # نشانگر «محل پرتاب» (مرکز رادار، همیشه ثابت)
        p.setPen(QPen(QColor("#f2c14e"), 2))
        p.setBrush(Qt.NoBrush)
        launch_r = 6
        p.drawLine(QPointF(cx - launch_r, cy), QPointF(cx + launch_r, cy))
        p.drawLine(QPointF(cx, cy - launch_r), QPointF(cx, cy + launch_r))
        p.drawEllipse(QPointF(cx, cy), launch_r, launch_r)

        # نشانگر موقعیت لحظه‌ای راکت نسبت به محل پرتاب (با چرخش نمایش می‌چرخد،
        # اما مختصات واقعیِ east/north دست‌نخورده می‌مانند)
        if self._pos is not None:
            east, north = self._pos
            scale = radius / self._range_m
            ex = east * scale
            ny = north * scale
            rot_rad = math.radians(rot)
            # چرخش نمایش: (east, north) را حول مرکز به‌اندازهٔ rot می‌چرخانیم
            rx = ex * math.cos(rot_rad) - ny * math.sin(rot_rad)
            ry = ex * math.sin(rot_rad) + ny * math.cos(rot_rad)
            mx = cx + max(-radius, min(radius, rx))
            my = cy - max(-radius, min(radius, ry))
            pen_line = QPen(QColor(255, 255, 255, 90), 1, Qt.DashLine)
            p.setPen(pen_line)
            p.drawLine(QPointF(cx, cy), QPointF(mx, my))
            marker_color = QColor("#35d07f")
            p.setPen(QPen(marker_color, 2))
            p.setBrush(marker_color)
            p.drawEllipse(QPointF(mx, my), 5, 5)
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(QPointF(mx, my), 9, 9)

        p.setPen(TEXT_DIM)
        f3 = QFont()
        f3.setPointSize(7)
        p.setFont(f3)
        p.drawText(rect.adjusted(0, side * 0.90, 0, side * 0.90), Qt.AlignHCenter | Qt.AlignTop,
                   f"برد رادار: {self._range_m:.0f} m")
        p.end()


def _fa(s) -> str:
    """ارقام لاتین را به فارسی تبدیل می‌کند."""
    return str(s).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))


class RocketCanvas(QWidget):
    """بومِ نمایشِ راکت بر اساس سیلوئتِ مرجعِ ارسالی کاربر.

    فرم راکت عمودیِ باریک، دماغهٔ نوک‌تیز، دو بالهٔ بزرگ و شعلهٔ پایین را
    بازسازی می‌کند تا در اندازه‌های مختلف واضح بماند. راکت با زاویهٔ واقعیِ
    لحظه‌ای می‌چرخد و رنگش از همان رنگ‌های وضعیتِ برنامه انتخاب می‌شود:
    سبز برای وضعیت مناسب، کهربایی برای هشدار، قرمز برای انحراف زیاد و آبی
    اطلاعاتی تا پیش از دریافت داده.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._dev = None        # انحراف محور طولی راکت از خط قائم (۰ = کاملاً عمود)
        self._roll = None       # غلت حولِ محورِ طولی
        self._rocket_color = QColor(colors.COLOR_INFO)
        self.setMinimumSize(140, 150)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    @staticmethod
    def _color_for_dev(dev_deg):
        """رنگ راکت را با همان آستانه‌های رنگیِ عدد «انحراف از عمود» تعیین می‌کند."""
        if dev_deg is None:
            return QColor(colors.COLOR_INFO)
        try:
            deviation = abs(float(dev_deg))
        except (TypeError, ValueError):
            return QColor(colors.COLOR_INFO)
        if deviation <= 5:
            return QColor(colors.COLOR_OK)
        if deviation <= 15:
            return QColor(colors.COLOR_WARN)
        return QColor(colors.COLOR_ERROR)

    def set_attitude(self, dev_deg, roll_deg):
        """dev_deg = انحراف محور طولی راکت از خط قائم (۰ = کاملاً عمود).
        (زبان مشترک با زاویهٔ پرتاب: روی سکو، انحراف = ۹۰ − زاویهٔ پرتاب)"""
        self._dev = dev_deg
        self._roll = roll_deg
        self._rocket_color = self._color_for_dev(dev_deg)
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        side = min(w, h) - 8
        rect = QRectF((w - side) / 2, (h - side) / 2, side, side)
        cx, cy, radius = rect.center().x(), rect.center().y(), side / 2

        # ---- زمینهٔ محدب (گنبدی شیشه‌ای، تیره در لبه و روشن در مرکز) ----
        dome = QRadialGradient(cx - radius * 0.25, cy - radius * 0.3, radius * 1.5)
        dome.setColorAt(0.0, QColor("#16324a"))
        dome.setColorAt(0.55, QColor("#0e2133"))
        dome.setColorAt(1.0, QColor("#070e18"))
        p.setBrush(dome)
        p.setPen(Qt.NoPen)
        p.drawEllipse(rect)

        # کلیپ به داخل کره برای همهٔ عناصرِ داخلی
        p.save()
        clip = QPainterPath()
        clip.addEllipse(rect.adjusted(3, 3, -3, -3))
        p.setClipPath(clip)

        # ---- خط عمودِ مرجع (نقطه‌چین) ----
        p.setPen(QPen(QColor(120, 150, 180, 120), 1.4, Qt.DashLine))
        p.drawLine(QPointF(cx, cy - radius), QPointF(cx, cy + radius))
        # خط افق ظریف
        p.setPen(QPen(QColor(120, 150, 180, 60), 1.0, Qt.DashLine))
        p.drawLine(QPointF(cx - radius, cy), QPointF(cx + radius, cy))

        dev = self._dev
        tilt = 0.0 if dev is None else float(dev)
        tilt = max(-90.0, min(90.0, tilt))

        # ---- قوسِ نمایشِ زاویهٔ انحراف بین عمود و محورِ راکت ----
        if dev is not None and abs(tilt) >= 1.0:
            arc_color = self._rocket_color
            arc_r = radius * 0.5
            arc_rect = QRectF(cx - arc_r, cy - arc_r, arc_r * 2, arc_r * 2)
            p.setPen(QPen(arc_color, 2.2))
            p.setBrush(Qt.NoBrush)
            # از عمود (۹۰° در مختصات Qt) به‌اندازهٔ tilt
            p.drawArc(arc_rect, int(90 * 16), int(-tilt * 16))

        # ---- خودِ راکت (حتی پیش از رسیدن داده، صاف و آبی نمایش داده می‌شود) ----
        p.save()
        p.translate(cx, cy)
        p.rotate(tilt)
        self._draw_rocket(p, radius, self._rocket_color)
        p.restore()

        p.restore()

        # ---- افکتِ محدب: درخششِ شیشه‌ایِ بالا-چپ ----
        glass = QRadialGradient(cx - radius * 0.35, cy - radius * 0.4, radius * 1.2)
        glass.setColorAt(0.0, QColor(255, 255, 255, 70))
        glass.setColorAt(0.4, QColor(255, 255, 255, 12))
        glass.setColorAt(1.0, QColor(0, 0, 0, 90))
        p.setBrush(glass)
        p.setPen(Qt.NoPen)
        p.drawEllipse(rect.adjusted(3, 3, -3, -3))

        # ---- بِزِلِ فلزی ----
        bez = QLinearGradient(0, rect.top(), 0, rect.bottom())
        bez.setColorAt(0.0, QColor("#3a4657"))
        bez.setColorAt(0.5, QColor("#141b26"))
        bez.setColorAt(1.0, QColor("#2a3444"))
        p.setPen(QPen(bez, 5))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(rect)
        p.setPen(QPen(QColor(255, 255, 255, 30), 1))
        p.drawEllipse(rect.adjusted(3, 3, -3, -3))

        # عدد «--» در مرکز دیگر روی خودِ راکت قرار نمی‌گیرد؛ readoutهای زیر
        # بوم همین وضعیتِ نبود داده را نشان می‌دهند. این‌جا فقط یک نشانگر
        # کوچک و غیرمزاحم در پایین گنبد باقی می‌ماند.
        if dev is None:
            p.setPen(TEXT_DIM)
            f = QFont()
            f.setPointSize(9)
            f.setBold(True)
            p.setFont(f)
            p.drawText(QRectF(cx - 18, cy + radius * 0.70, 36, 18), Qt.AlignCenter, "--")
        p.end()

    def _draw_rocket(self, p, radius, accent):
        """سیلوئتِ رنگیِ راکت مرجع: دماغه، بدنهٔ باریک، دو باله و شعله."""
        H = radius * 1.26
        top = -H / 2
        bottom = H / 2
        body_width = max(10.0, radius * 0.18)
        flame_height = H * 0.17
        body_top = top + H * 0.18
        body_bottom = bottom - flame_height
        fin_top = top + H * 0.53
        fin_outer_top = fin_top + H * 0.16
        fin_outer_bottom = fin_top + H * 0.31
        fin_inner_bottom = fin_top + H * 0.23
        fin_width = radius * 0.16
        outline = QPen(accent.darker(175), max(1.0, radius * 0.012))

        # درخشش ظریفِ پشت سیلوئت، هماهنگ با رنگ وضعیت
        glow = QColor(accent)
        glow.setAlpha(42)
        p.setPen(Qt.NoPen)
        p.setBrush(glow)
        p.drawEllipse(QRectF(-body_width * 1.15, body_top, body_width * 2.3,
                             body_bottom - body_top))

        # ---- شعلهٔ اصلی و شعلهٔ داخلی ----
        flame = QPainterPath()
        flame.moveTo(0, body_bottom - H * 0.015)
        flame.cubicTo(-body_width * 0.32, body_bottom + H * 0.06,
                      -body_width * 0.22, bottom - H * 0.035, 0, bottom)
        flame.cubicTo(body_width * 0.22, bottom - H * 0.035,
                      body_width * 0.32, body_bottom + H * 0.06,
                      0, body_bottom - H * 0.015)
        flame_grad = QLinearGradient(0, body_bottom, 0, bottom)
        flame_grad.setColorAt(0.0, accent.lighter(165))
        flame_grad.setColorAt(0.65, accent)
        flame_grad.setColorAt(1.0, accent.darker(145))
        p.setBrush(flame_grad)
        p.setPen(outline)
        p.drawPath(flame)

        inner_flame = QPainterPath()
        inner_flame.moveTo(0, body_bottom + H * 0.015)
        inner_flame.cubicTo(-body_width * 0.12, body_bottom + H * 0.08,
                            -body_width * 0.08, bottom - H * 0.07, 0, bottom - H * 0.035)
        inner_flame.cubicTo(body_width * 0.08, bottom - H * 0.07,
                            body_width * 0.12, body_bottom + H * 0.08,
                            0, body_bottom + H * 0.015)
        inner = QColor(255, 255, 255, 150)
        p.setBrush(inner)
        p.setPen(Qt.NoPen)
        p.drawPath(inner_flame)

        # ---- باله‌های پهنِ پایین (پشت بدنه) ----
        fin_grad = QLinearGradient(0, fin_top, 0, fin_outer_bottom)
        fin_grad.setColorAt(0.0, accent.lighter(120))
        fin_grad.setColorAt(1.0, accent.darker(155))
        p.setBrush(fin_grad)
        p.setPen(outline)

        left_fin = QPainterPath()
        left_fin.moveTo(-body_width / 2, fin_top)
        left_fin.lineTo(-body_width / 2 - fin_width, fin_outer_top)
        left_fin.lineTo(-body_width / 2 - fin_width, fin_outer_bottom)
        left_fin.lineTo(-body_width / 2, fin_inner_bottom)
        left_fin.closeSubpath()
        p.drawPath(left_fin)

        right_fin = QPainterPath()
        right_fin.moveTo(body_width / 2, fin_top)
        right_fin.lineTo(body_width / 2 + fin_width, fin_outer_top)
        right_fin.lineTo(body_width / 2 + fin_width, fin_outer_bottom)
        right_fin.lineTo(body_width / 2, fin_inner_bottom)
        right_fin.closeSubpath()
        p.drawPath(right_fin)

        # ---- بدنهٔ اصلی ----
        body_rect = QRectF(-body_width / 2, body_top, body_width,
                           body_bottom - body_top)
        body_grad = QLinearGradient(-body_width / 2, 0, body_width / 2, 0)
        body_grad.setColorAt(0.0, accent.darker(145))
        body_grad.setColorAt(0.48, accent.lighter(135))
        body_grad.setColorAt(1.0, accent.darker(120))
        p.setBrush(body_grad)
        p.setPen(outline)
        p.drawRoundedRect(body_rect, body_width * 0.22, body_width * 0.22)

        # ---- دماغهٔ نوک‌تیز ----
        nose = QPainterPath()
        nose.moveTo(0, top)
        nose.cubicTo(-body_width * 0.18, top + H * 0.035,
                     -body_width / 2, body_top - H * 0.045,
                     -body_width / 2, body_top)
        nose.lineTo(body_width / 2, body_top)
        nose.cubicTo(body_width / 2, body_top - H * 0.045,
                     body_width * 0.18, top + H * 0.035, 0, top)
        nose.closeSubpath()
        nose_grad = QLinearGradient(0, top, 0, body_top)
        nose_grad.setColorAt(0.0, accent.lighter(145))
        nose_grad.setColorAt(1.0, accent.darker(145))
        p.setBrush(nose_grad)
        p.setPen(outline)
        p.drawPath(nose)

        # نوار نور باریک روی بدنه برای خوانایی شکل در اندازهٔ کوچک
        highlight = QColor(255, 255, 255, 70)
        p.setPen(QPen(highlight, max(1.0, radius * 0.012)))
        p.drawLine(QPointF(-body_width * 0.16, body_top + H * 0.08),
                   QPointF(-body_width * 0.16, body_bottom - H * 0.08))


class RocketAttitude(QWidget):
    """نمایشِ «مدلِ راکت + زاویهٔ انحراف از عمود» به‌جای افقِ مصنوعیِ هواپیما.

    بالا: بومِ گرافیکیِ راکت (RocketCanvas) که به‌اندازهٔ انحرافِ لحظه‌ای از
    عمود کج می‌شود. پایین: چهار عددِ انحراف از عمود، چرخش (پیچ)، رول و یاو.

    انحراف از عمود = زاویهٔ محور طولی راکت با خط قائم (۰ = کاملاً عمود) و از
    شتاب‌سنجِ MPU6050ِ کامپیوتر پرواز می‌آید:  dev = atan2(-ax, hypot(ay,az))
    و roll = atan2(ay, az). رابطه با زاویهٔ پرتاب (نسبت به افق): روی سکو
    «انحراف = ۹۰ − زاویهٔ پرتاب» (پرتاب ۸۵° ← انحراف ۵°)؛ پس از پرتاب، همین
    فرمول انحرافِ واقعیِ لحظه‌ای راکت را از دادهٔ زنده می‌دهد. یاو با
    شتاب‌سنج قابل‌محاسبه نیست و تا افزودنِ مغناطوس‌سنج (یا ادغامِ ژیرو در
    فریمور) «--» می‌ماند.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._dev = None
        self._roll = None
        self._yaw = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        self.canvas = RocketCanvas()
        lay.addWidget(self.canvas, stretch=1)

        grid = QHBoxLayout()
        grid.setSpacing(6)
        self._readouts = {}
        for key, title in (("dev", "انحراف از عمود"), ("pitch", "چرخش"),
                           ("roll", "رول"), ("yaw", "یاو")):
            box = QVBoxLayout(); box.setSpacing(1)
            t = QLabel(title); t.setAlignment(Qt.AlignCenter)
            t.setStyleSheet("font-size:10px; color:#8fa3b8; background:transparent;")
            v = QLabel("--"); v.setAlignment(Qt.AlignCenter)
            v.setStyleSheet("font-size:15px; font-weight:800; color:#eaf2fa; background:transparent;")
            box.addWidget(t); box.addWidget(v)
            grid.addLayout(box)
            self._readouts[key] = v
        lay.addLayout(grid)

    def set_attitude(self, dev_deg, roll_deg, yaw_deg=None):
        """dev_deg = انحراف محور طولی راکت از خط قائم (۰ = کاملاً عمود)."""
        self._dev = dev_deg
        self._roll = roll_deg
        self._yaw = yaw_deg
        self.canvas.set_attitude(dev_deg, roll_deg)
        self._refresh_labels()

    def _refresh_labels(self):
        if self._dev is None:
            for v in self._readouts.values():
                v.setText("--")
            return
        dev = float(self._dev)
        ad = abs(dev)
        col = "#35d07f" if ad <= 5 else ("#f2c14e" if ad <= 15 else "#ef5350")
        # قفل LTR برای «عدد + درجه» تا نماد ° همیشه سمت راستِ عدد بماند
        self._readouts["dev"].setText("\u202a" + _fa(f"{dev:+.0f}").replace("-", "\u2212") + "°\u202c")
        self._readouts["dev"].setStyleSheet(
            f"font-size:16px; font-weight:800; color:{col}; background:transparent;")
        # «چرخش» = زاویهٔ محور راکت نسبت به افق (۹۰ − اندازهٔ انحراف)
        self._readouts["pitch"].setText("\u202a" + _fa(f"{90.0 - ad:.0f}") + "°\u202c")
        self._readouts["roll"].setText(
            "\u202a" + _fa(f"{self._roll:+.0f}").replace("-", "\u2212") + "°\u202c"
            if self._roll is not None else "--")
        self._readouts["yaw"].setText(
            "\u202a" + _fa(f"{self._yaw:.0f}") + "°\u202c"
            if self._yaw is not None else "--")


class UvMeter(QWidget):
    """نوار افقی طیف‌رنگی شاخص UV با نشانگر مقدار لحظه‌ای -- وقتی هنوز
    داده‌ای از سنسور GUVA-S12SD نرسیده باشد، نشانگر نمایش داده نمی‌شود."""
    STOPS = [
        (0.0, "#35d07f"), (0.27, "#d4ff00"), (0.5, "#f2c14e"),
        (0.65, "#ff9f43"), (0.80, "#ef5350"), (1.0, "#b026ff"),
    ]
    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = None
        self.setMinimumHeight(14)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_value(self, value):
        self._value = value
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(0, 0, self.width(), self.height())
        grad = pg_gradient(self.STOPS, rect.width())
        p.setPen(Qt.NoPen)
        p.setBrush(grad)
        p.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)
        if self._value is not None:
            frac = max(0.0, min(1.0, self._value / 11.0))
            x = frac * rect.width()
            p.setPen(QPen(TEXT_BRIGHT, 2))
            p.drawLine(QPointF(x, -2), QPointF(x, rect.height() + 2))
        p.end()


def pg_gradient(stops, width):
    from PySide6.QtGui import QLinearGradient
    grad = QLinearGradient(0, 0, width, 0)
    for frac, color in stops:
        grad.setColorAt(frac, QColor(color))
    return grad


class PhaseTimeline(QWidget):
    """خط زمانی افقی مراحل پرواز -- سبک نوار بالای مرکز کنترل مأموریت.

    شش پرده: سکو ← رانش ← صعود ← اوج ← چتر ← فرود. مرحلهٔ جاری پرنور،
    مراحل گذشته با «✓» و آینده خاکستری است. اگر چتر باز نشود، پردهٔ چتر
    قرمز با «✕» می‌شود.

    چیدمان **راست‌به‌چپ**: «سکو» سمت راست و «فرود» سمت چپ (ترتیبِ خواندن
    در رابط فارسی). هیچ نوشتهٔ وضعیت بالای پرده‌ها نیست (به درخواست کاربر
    حذف شد) و همین فضای خالی صرف بزرگ‌ترشدن خود پرده‌ها می‌شود؛ ارتفاع کل
    نوار بالا ثابت می‌ماند.
    """
    STEPS = [
        ("pad", "سکو", colors.COLOR_MISSING, "●"),
        ("launched", "رانش", colors.COLOR_ERROR, "▲"),
        ("ascent", "صعود", colors.COLOR_WARN, "⬆"),
        ("apogee", "اوج", colors.ALTITUDE, "◆"),
        ("descent", "چتر", colors.COLOR_OK, "◆"),
        ("landed", "فرود", colors.COLOR_INFO, "■"),
    ]
    _MAP = {
        "idle": "pad", "installing": "pad", "on_pad": "pad", "countdown": "pad",
        "launched": "launched", "burnout": "ascent", "ascent": "ascent",
        "apogee": "apogee", "descent": "descent", "chute_fail": "descent",
        "landed": "landed",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current = None    # کلید مرحلهٔ نمایشی جاری
        self._failed = False    # چتر باز نشد (خطر)
        self.setMinimumSize(560, 62)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(66)

    def set_phase(self, phase_key: str) -> bool:
        """فاز پرواز را روی خط زمانی نشان می‌دهد.

        خروجی: True اگر مرحلهٔ *نمایشی* عوض شده باشد (برای پخش صدای «دینگ»
        هنگام هر تیکِ مرحله در مرکز کنترل).
        """
        new_stage = self._MAP.get(phase_key, self._current)
        changed = new_stage != self._current
        self._failed = phase_key == "chute_fail"
        self._current = new_stage
        self.update()
        return changed

    def reset(self):
        self._current = None
        self._failed = False
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        margin = 6
        gap = 5
        n = len(self.STEPS)

        lab_h = 12
        seg_h = max(30.0, h - margin * 2 - lab_h - 4)
        y_seg = margin
        y_lab = y_seg + seg_h + 2

        f_icon = QFont(); f_icon.setPointSize(12)
        f_lab = QFont(); f_lab.setPointSize(8); f_lab.setBold(True)

        cur_idx = None
        if self._current is not None:
            for i, (key, *_r) in enumerate(self.STEPS):
                if key == self._current:
                    cur_idx = i
                    break

        seg_w = (w - margin * 2 - gap * (n - 1)) / n
        for i, (key, label, hexcol, icon) in enumerate(self.STEPS):
            # راست‌به‌چپ: شاخص ۰ («سکو») سمت راست، آخرین («فرود») سمت چپ
            x0 = w - margin - (i + 1) * seg_w - i * gap
            rect = QRectF(x0, y_seg, seg_w, seg_h)
            col = QColor(hexcol)
            is_done = cur_idx is not None and i < cur_idx
            is_cur = i == cur_idx
            failed_here = self._failed and key == "descent"

            if failed_here:
                fill = QColor(colors.COLOR_ERROR); fill.setAlpha(215)
                border = QColor(colors.COLOR_ERROR)
            elif is_cur:
                fill = QColor(col); fill.setAlpha(205)
                border = QColor(255, 255, 255, 195)
            elif is_done:
                fill = QColor(col); fill.setAlpha(60)
                border = QColor(col); border.setAlpha(170)
            else:
                fill = QColor(255, 255, 255, 16)
                border = QColor(255, 255, 255, 45)
            p.setPen(QPen(border, 2 if is_cur else 1))
            p.setBrush(fill)
            p.drawRoundedRect(rect, 5, 5)

            # آیکون/علامت داخل پرده
            if failed_here:
                icon_txt, icon_col = "✕", QColor("#ffffff")
            elif is_cur:
                icon_txt, icon_col = icon, QColor("#ffffff")
            elif is_done:
                icon_txt, icon_col = "✓", QColor(col).lighter(140)
            else:
                icon_txt, icon_col = icon, QColor(255, 255, 255, 90)
            p.setPen(icon_col)
            p.setFont(f_icon)
            p.drawText(rect, Qt.AlignCenter, icon_txt)

            # برچسب
            p.setFont(f_lab)
            p.setPen(TEXT_BRIGHT if (is_cur or is_done or failed_here) else TEXT_DIM)
            lab_text = "چتر باز نشد" if failed_here else label
            fm = QFontMetrics(f_lab)
            if fm.horizontalAdvance(lab_text) > seg_w - 2:
                lab_text = fm.elidedText(lab_text, Qt.ElideRight, int(seg_w) - 2)
            p.drawText(QRectF(x0, y_lab, seg_w, lab_h),
                       Qt.AlignCenter, lab_text)
        p.end()


# ============================================================================
# تله‌سنجی زندهٔ HUD (به‌جای نردبان/رویدادهای قبلی) -- چهار پنل:
#   ۱) شتاب زنده و پروفایل موتور   ۲) مسیر واقعی در برابر پیش‌بینی
#   ۳) سلامت توان و ولتاژ آنبرد    ۴) فشار دینامیکی و Max-Q
# همهٔ پنل‌ها «بافر-محور» هستند: بسته‌های تله‌متری فقط O(1) در بافر اضافه
# می‌شوند (`push_*`) و بازرسم فقط با `refresh()` و حداکثر ~۱۵ فریم در ثانیه
# انجام می‌شود -- هیچ رندر سنگینی روی مسیر دریافت پکت انجام نمی‌شود تا
# افت فریم (مخصوصاً با GPS/لورا) پیش نیاید. واحدهای انگلیسی همیشه سمت
# راستِ عدد می‌نشینند (بلوک LTR) و استایل دارک/نئونی با پالت یکپارچه است.
# ============================================================================

_LTR_QTY = "\u202a"   # قفل چپ‌به‌راست برای «عدد + واحد»


def _ltr(text: str) -> str:
    """قفل LTR تا واحد انگلیسی سمت راستِ عدد بماند (در RTL جابه‌جا نشود)."""
    return _LTR_QTY + text + "\u202c"


def _panel_header(p, rect: QRectF, title: str, accent: str, right_text: str = ""):
    """هدر کوچک هر پنل: عنوان سمت راست (خواندن فارسی) + مقدار سمت چپ."""
    f = QFont(); f.setBold(True); f.setPointSize(9)
    p.setFont(f)
    fm = QFontMetrics(f)
    p.setPen(QColor(accent))
    tw = fm.horizontalAdvance(title)
    p.drawText(QRectF(rect.right() - 4 - tw, rect.top() + 2, tw, 18),
               Qt.AlignLeft | Qt.AlignVCenter, title)
    if right_text:
        p.setPen(TEXT_DIM)
        p.drawText(QRectF(rect.left() + 4, rect.top() + 2, rect.width() - tw - 16, 18),
                   Qt.AlignRight | Qt.AlignVCenter, right_text)



class NeedleGauge(QWidget):
    """گیج عقربه‌ای با بدنهٔ دایرهٔ کامل + کمانِ پارامتر ۲۵۲° (۳۰٪ پایین خالی).

    - بدنه/حلقهٔ بیرونی دایرهٔ کامل است؛ اما کمانِ ۰٪..۱۰۰٪ از «پایین-چپ»
      از روی بالا تا «پایین-راست» می‌چرخد و ۳۰٪ پایینی دایره خالی می‌ماند
      (شبیه گیج‌های بالای HUD، ولی با بدنهٔ دایرهٔ کامل).
    - عددِ مقدار، بزرگ‌تر از قبل، در همان ناحیهٔ خالیِ پایینِ داخل دایره
      رسم می‌شود؛ وضعیت (پیوستگی چاشنی و...) زیر دایره می‌آید.
    - درجه‌بندی: تیک‌های بیشتر (هر ۶٫۲۵٪، تیکِ درشت هر ۱۲٫۵٪) و عددهای
      بیشتر (۱۲٫۵٪..۸۷٫۵٪) با فونت بزرگ‌تر؛ دو سرِ کمان به عددِ بزرگِ
      پایین اختصاص دارد تا با آن برخورد نکند.
    - عقربه با میرایی نرم (~۱۵Hz) حرکت می‌کند و فقط در صورت تغییر بازرسم
      دارد (برای جلوگیری از افت فریم).
    """

    # کمانِ مقدار و درجه‌بندی: از ۲۱۶° (پایین-چپ) به‌اندازهٔ ۲۵۲° در جهت
    # عقربه‌ها تا −۳۶° (پایین-راست)؛ خالی ماندن ۱۰۸° پایین = ۳۰٪ دایره.
    _ARC_START_DEG = 216.0
    _ARC_SWEEP_DEG = 252.0

    def __init__(self, title: str, unit: str, vmin: float, vmax: float,
                 accent: str, zones=None, decimals: int = 1, parent=None):
        super().__init__(parent)
        self._title = title
        self._unit = unit
        self._vmin = float(vmin)
        self._vmax = float(vmax)
        self._accent = accent
        # zones: لیست (رنگ، کسرِ شروع) به‌ترتیب صعودی؛ پیش‌فرض: سبز←کهربایی←قرمز
        self._zones = zones or [("#35d07f", 0.0), ("#f2c14e", 0.55), ("#ef5350", 0.8)]
        self._decimals = decimals
        self._target: float | None = None
        self._disp = 0.0
        self._status = ""            # زیرنویس وضعیت (پیوستگی چاشنی و...)
        self._dirty = False
        self.setMinimumSize(150, 180)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    # ------------------------------------------------------------------
    def set_value(self, v: float | None):
        if v is None:
            return
        self._target = float(v)
        self._dirty = True

    def set_status(self, text: str = ""):
        self._status = text
        self._dirty = True

    def reset(self):
        self._target = None
        self._disp = 0.0
        self._status = ""
        self._dirty = True

    def refresh(self):
        """حرکت میرایی‌شدهٔ عقربه؛ فقط وقتی مقدار/وضعیت تغییر کرده بازرسم می‌کند."""
        if self._target is None:
            if self._dirty:
                self._dirty = False
                self.update()
            return
        target = self._target
        if self._dirty or abs(self._disp - target) > 1e-4:
            self._disp += (target - self._disp) * 0.28
            if abs(self._disp - target) < max(1e-4, abs(target) * 0.004):
                self._disp = target
            self._dirty = False
            self.update()

    # ------------------------------------------------------------------
    @staticmethod
    def _fmt(v, decimals: int) -> str:
        return _fa(f"{v:.{decimals}f}")

    def _frac_of(self, v: float) -> float:
        return max(0.0, min(1.0, (v - self._vmin) / max(1e-9, self._vmax - self._vmin)))

    @staticmethod
    def _arc_angle(frac: float) -> float:
        """زاویهٔ ریاضی (خلاف عقربه، ۰°=راست) برای کسرِ ۰..۱ روی کمان.""" 
        return math.radians(NeedleGauge._ARC_START_DEG - frac * NeedleGauge._ARC_SWEEP_DEG)

    def paintEvent(self, _event):
        p = QPainter(self)
        try:
            self._paint(p)
        except Exception:
            pass
        finally:
            p.end()

    def _paint(self, p: QPainter):
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(1, 1, self.width() - 2, self.height() - 2)
        p.setPen(QPen(QColor(255, 255, 255, 22), 1))
        p.setBrush(QColor(19, 24, 32, 200))
        p.drawRoundedRect(rect, 6, 6)

        live = self._target is not None
        _panel_header(p, rect, self._title, self._accent)

        # چیدمان: هدر بالا + دایرهٔ وسط + نوار وضعیت پایین
        hdr, bottom = 24.0, 20.0
        avail_h = rect.height() - hdr - bottom
        cx = rect.center().x()
        cy = rect.top() + hdr + avail_h / 2.0
        radius = min(rect.width() / 2.0 - 12.0, avail_h / 2.0 - 4.0)

        # ---- بدنهٔ دایرهٔ کامل (حلقهٔ بیرونی همیشه بسته است)
        p.setPen(QPen(RING_DIM, max(5, int(radius / 7))))
        p.drawArc(QRectF(cx - radius, cy - radius, radius * 2, radius * 2), 0, 360 * 16)

        # ---- سگمنت‌های رنگی فقط روی کمانِ ۲۵۲° (پایین خالی می‌ماند)
        seg_w = max(4, int(radius / 9))
        for i, (col, f0) in enumerate(self._zones):
            f1 = self._zones[i + 1][1] if i + 1 < len(self._zones) else 1.0
            p.setPen(QPen(QColor(col), seg_w))
            p.drawArc(QRectF(cx - radius + 4, cy - radius + 4,
                             (radius - 4) * 2, (radius - 4) * 2),
                      int((self._ARC_START_DEG - f1 * self._ARC_SWEEP_DEG) * 16),
                      int((f1 - f0) * self._ARC_SWEEP_DEG * 16))

        # ---- درجه‌بندی: ۱۷ تیک (تیکِ درشت هر ۱۲٫۵٪) + ۷ عدد (۱۲٫۵٪..۸۷٫۵٪)
        f_tick = QFont(); f_tick.setPointSize(9); f_tick.setBold(True)
        p.setFont(f_tick)
        for i in range(17):
            frac = i / 16.0
            ang = self._arc_angle(frac)
            major = (i % 2 == 0)
            r1 = radius - 1
            r2 = radius - (12 if major else 7)
            p.setPen(QPen(TEXT_DIM if major else QColor(140, 150, 165, 120), 1))
            p.drawLine(QPointF(cx + r1 * math.cos(ang), cy - r1 * math.sin(ang)),
                       QPointF(cx + r2 * math.cos(ang), cy - r2 * math.sin(ang)))

        span = abs(self._vmax - self._vmin)
        label_dec = 0 if span > 20.0 else 1
        for i in range(1, 8):
            frac = i / 8.0
            v = self._vmin + span * frac
            ang = self._arc_angle(frac)
            lx, ly = cx + (radius - 23) * math.cos(ang), cy - (radius - 23) * math.sin(ang)
            p.setPen(TEXT_DIM)
            p.drawText(QRectF(lx - 22, ly - 9, 44, 18), Qt.AlignCenter,
                       self._fmt(v, label_dec))

        # ---- عقربه (میرا)
        frac = self._frac_of(self._disp)
        ang = self._arc_angle(frac)
        nx, ny = cx + radius * 0.62 * math.cos(ang), cy - radius * 0.62 * math.sin(ang)
        p.setPen(_glow_pen(QColor(self._accent), 6, alpha=60))
        p.drawLine(QPointF(cx, cy), QPointF(nx, ny))
        p.setPen(QPen(QColor(self._accent), 2.4))
        p.drawLine(QPointF(cx, cy), QPointF(nx, ny))
        p.setPen(Qt.NoPen); p.setBrush(QColor("#eaf2fa"))
        p.drawEllipse(QPointF(cx, cy), 3.5, 3.5)

        # ---- عدد مقدار (بزرگ‌تر): در ناحیهٔ خالیِ پایینِ داخل دایره
        val_txt = ("--" if not live
                   else _ltr(self._fmt(self._target, self._decimals)
                             + (" " + self._unit if self._unit else "")))
        num_cy = cy + radius * 0.5
        box = QRectF(cx - radius * 0.95, num_cy - 13, radius * 1.9, 26)
        f_big = QFont(); f_big.setBold(True)
        f_big.setPointSize(max(12, min(18, int(radius * 0.23))))
        p.setFont(f_big)
        p.setPen(QColor(self._accent) if live else TEXT_DIM)
        p.drawText(box, Qt.AlignCenter, val_txt)

        # ---- وضعیت (چاشنی و...) زیر دایره
        if self._status:
            f_s = QFont(); f_s.setPointSize(7); p.setFont(f_s)
            p.setPen(TEXT_DIM)
            p.drawText(QRectF(rect.left() + 4, rect.bottom() - 18,
                              rect.width() - 8, 14), Qt.AlignCenter, self._status)
