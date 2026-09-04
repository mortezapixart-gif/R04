# -*- coding: utf-8 -*-
"""صفحهٔ «تحلیل پرواز» -- ظرف تب‌دار برای هر ۹ صفحهٔ تحلیلِ پس از پرواز.

ساختار سایدبار (درخواست کاربر): صفحاتِ «قبل از پرتاب» مستقیم در سایدبار
می‌مانند و هر ۹ صفحهٔ تحلیل، تب‌های همین یک صفحهٔ کلی‌اند؛ آخرین تب «بازپخش»
است و «تهیه گزارش» صفحهٔ مستقلِ سایدبار (زیر همین صفحه) شده است.

تب‌ها به‌جای QTabWidget، نوار دکمه‌های قابل‌انتخاب‌اند تا هر تب بتواند
«رنگ مخصوص خودش» را داشته باشد؛ اما مثل نوار تب کلاسیک راست‌چین‌اند
(تب اول از راست) و تبِ فعال کاملاً از تب‌های خاموش جدا می‌شود:
  - تب خاموش: بدنهٔ تیرهٔ ساده + «ستون هویت» باریکِ رنگ کدر در لبهٔ راست؛
  - تب فعال: بدنهٔ پُر با گرادیان عمودی رنگ خودش، متن سفید درشت و
    خط زیرینِ ضخیم که به خط پایهٔ نوار می‌نشیند.

تم رنگی «مهندسی» از چرخهٔ رنگ ایتن: هر تب از یک قطاع ۱۲گانهٔ چرخهٔ ایتن
می‌گیرد و تب‌های مجاور از قطاع‌های دور (کنتراست مکمل) تا با هم اشتباه
نشوند؛ اشباع/روشنایی هر رنگ برای زمینهٔ تیرهٔ برنامه تنظیم شده است.
"""
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                                QButtonGroup, QStackedWidget, QScrollArea)
from PySide6.QtCore import Qt

from pages.flight_indices import FlightIndicesPage
from pages.prediction_actual import PredictionActualPage
from pages.flight_analysis import FlightAnalysisPage
from pages.altitude_velocity import AltitudeVelocityPage
from pages.altitude_temperature import AltitudeTemperaturePage
from pages.aerodynamics import AerodynamicsPage
from pages.parachute import ParachutePage
from pages.gps_map import GpsMapPage
from pages.replay3d import Replay3DPage

_BG = "#1a2029"        # زمینهٔ کارت‌ها -- برای کم‌رنگ‌کردن تب‌های انتخاب‌نشده
_TAB_FACE = "#1f2735"  # بدنهٔ تب خاموش
_TAB_EDGE = "#2b3446"  # حاشیهٔ تب خاموش
_TAB_TEXT = "#96a2b5"  # متن تب خاموش
_BASELINE = "#2a3447"  # خط پایهٔ زیر نوار تب


def _mix(c1: str, c2: str, t: float) -> str:
    """ترکیب دو رنگ hex (t=۰ → c1، t=۱ → c2)."""
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(a, b))


def _tab_qss(col: str) -> str:
    """استایل یک تب با رنگ هویتِ خودش (فرم نوار تب کلاسیک).

    خاموش: تیرهٔ مسطح + ستون رنگیِ کدر در لبهٔ راست (لبهٔ آغاز در RTL)؛
    فعال: بدنهٔ پُرِ گرادیان عمودی رنگ + متن سفید درشت + خط زیرین ضخیم.
    هندسه (padding/فونت) در هر سه حالت یکسان است تا تب‌ها نپرند."""
    spine = _mix(col, _BG, 0.45)          # ستون هویتِ تب خاموش
    hover_bg = _mix(col, _BG, 0.86)       # ته‌رنگ ملایم در هاور
    hover_edge = _mix(col, _BG, 0.50)
    hover_spine = _mix(col, _BG, 0.20)
    top = _mix(col, "#ffffff", 0.20)      # گرادیان فعال: روشن ↑
    bottom = _mix(col, "#000000", 0.16)   #                        ↓ تیره
    edge_on = _mix(col, "#ffffff", 0.42)
    underline = _mix(col, "#000000", 0.34)
    geo = ("border-top-left-radius: 8px; border-top-right-radius: 8px;"
           " border-bottom-left-radius: 3px; border-bottom-right-radius: 3px;"
           " padding: 8px 16px 6px 16px; min-height: 22px;"
           " font-weight: bold; font-size: 12.5px;")
    return f"""
        QPushButton {{
            background-color: {_TAB_FACE};
            color: {_TAB_TEXT};
            border: 1px solid {_TAB_EDGE};
            border-right: 3px solid {spine};
            {geo}
        }}
        QPushButton:hover {{
            background-color: {hover_bg};
            color: #dbe3ee;
            border: 1px solid {hover_edge};
            border-right: 3px solid {hover_spine};
        }}
        QPushButton:checked {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {top}, stop:0.55 {col}, stop:1 {bottom});
            color: #ffffff;
            border: 1px solid {edge_on};
            border-right: 3px solid {edge_on};
            border-bottom: 3px solid {underline};
        }}
        QPushButton:checked:hover {{
            background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                stop:0 {_mix(col, "#ffffff", 0.26)}, stop:0.55 {col}, stop:1 {bottom});
        }}
    """


# (نام تب، کلاس صفحه، رنگ هویت از چرخهٔ رنگ ایتن -- تنظیم‌شده برای تم تیره)
# تب‌های مجاور از قطاع‌های دورِ چرخه‌اند (نارنجی↔آبی مکمل ایتن و ...)
ANALYSIS_TABS = [
    ("شاخص‌های پرواز", FlightIndicesPage, "#5eb3d4"),      # سبزآبیِ مکمل نارنجی: جدول‌های نتایج
    ("پیش‌بینی و واقعیت", PredictionActualPage, "#e0b13e"),  # طلایی: مقایسهٔ شبیه‌سازی با پرواز
    ("شتاب / سرعت", FlightAnalysisPage, "#e97449"),        # قرمز-نارنجی: انرژی/شتاب
    ("ارتفاع / سرعت", AltitudeVelocityPage, "#5a99d8"),    # آبی: مکمل نارنجی، آسمان
    ("ارتفاع / دما / رطوبت", AltitudeTemperaturePage, "#3bcea9"),  # سبزآبی: محیط
    ("آیرودینامیک", AerodynamicsPage, "#7c73de"),          # آبی-بنفش
    ("چتر", ParachutePage, "#41c858"),                      # سبز: فرود موفق
    ("مسیر GPS", GpsMapPage, "#b079d8"),                    # بنفش: ناوبری
    ("بازپخش", Replay3DPage, "#e160ab"),                    # قرمز-بنفش: پخش
]
# «گزارش نهایی» به درخواست کاربر از تب‌ها خارج شد و به‌عنوان صفحهٔ مستقل
# «تهیه گزارش» در سایدبار (زیر «تحلیل پرواز») نشسته است.

# نام‌های قدیمی صفحات → تب جدید؛ برای اینکه ناوبری/متن‌های قدیمی هم کار کنند
TAB_ALIASES = {
    "تحلیل پرواز و شتاب": "شتاب / سرعت",
    "ارتفاع و سرعت": "ارتفاع / سرعت",
    "ارتفاع، دما و رطوبت": "ارتفاع / دما / رطوبت",
    "تحلیل آیرودینامیک": "آیرودینامیک",
    "تحلیل چتر": "چتر",
    "بازپخش سه‌بعدی": "بازپخش",
}


class AnalysisHubPage(QWidget):
    """یک صفحهٔ کلی با ۹ تب تحلیل؛ صفحات خودشان دست‌نخورده‌اند."""

    def __init__(self):
        super().__init__()
        self.setLayoutDirection(Qt.RightToLeft)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # ---- نوار تب‌ها (راست‌چین: تب اول از راست؛ در تنگی پیمایش‌پذیر)
        strip = QWidget()
        strip.setObjectName("AnalysisTabStrip")
        strip_lay = QHBoxLayout(strip)
        strip_lay.setContentsMargins(8, 6, 8, 4)
        strip_lay.setSpacing(6)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._names = []
        self.stack = QStackedWidget()
        for i, (name, cls, col) in enumerate(ANALYSIS_TABS):
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(_tab_qss(col))
            self._group.addButton(btn, i)
            strip_lay.addWidget(btn)
            self._names.append(name)

            page_wrap = QScrollArea()
            page_wrap.setWidgetResizable(True)
            page_wrap.setFrameShape(QScrollArea.NoFrame)
            page_wrap.setWidget(cls())
            self.stack.addWidget(page_wrap)
        # در چیدمان RTL آیتمِ بعد از دکمه‌ها به لبهٔ چپ می‌رود → تب‌ها به راست می‌چسبند
        strip_lay.addStretch(1)
        self._group.idClicked.connect(self.stack.setCurrentIndex)
        self._group.button(0).setChecked(True)

        strip_scroll = QScrollArea()
        strip_scroll.setWidgetResizable(True)
        strip_scroll.setFrameShape(QScrollArea.NoFrame)
        strip_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        strip_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        strip_scroll.setFixedHeight(54)
        strip_scroll.setWidget(strip)
        # مرجع پایتونی صریح: در برخی نسخه‌های PySide (مثل 6.11) setWidget مالکیت
        # پایتونی را منتقل نمی‌کند و strip بعد از خروج از __init__ حذف می‌شد
        self._strip = strip
        lay.addWidget(strip_scroll)

        # ---- خط پایهٔ نوار تب: تب فعال با خط زیرینِ خودش روی آن می‌نشیند
        self._baseline = QWidget()
        self._baseline.setFixedHeight(2)
        self._baseline.setStyleSheet(f"background-color: {_BASELINE};")
        lay.addWidget(self._baseline)
        lay.addWidget(self.stack, stretch=1)

    # ---------------- API سازگار با تب ----------------
    def count(self) -> int:
        return self.stack.count()

    def tabText(self, i: int) -> str:
        return self._names[i]

    def currentIndex(self) -> int:
        return self.stack.currentIndex()

    def open_tab(self, name: str) -> bool:
        """رفتن به تب موردنظر (نام جدید یا نام قدیمی صفحه). اگر نبود False."""
        name = TAB_ALIASES.get(name, name)
        for i, n in enumerate(self._names):
            if n == name:
                self._group.button(i).setChecked(True)
                self.stack.setCurrentIndex(i)
                return True
        return False
