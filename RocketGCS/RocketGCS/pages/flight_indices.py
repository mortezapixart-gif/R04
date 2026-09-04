# -*- coding: utf-8 -*-
"""صفحهٔ «شاخص‌های پرواز» -- تب اول تحلیل: هر دو جدول کامل نتایج
(«شاخص‌های پروازی و صعود» و «شاخص‌های محیطی و فرود») دقیقاً همان ردیف‌هایی
که گزارش PDF می‌آید، از منبع مشترک core/report_text.py.

چیدمان: دو کارت کنار هم (پروازی راست، محیطی چپ)؛ هر ردیف یک خط --
عنوان راست، مقدار چپ. توضیح هر پارامتر با hover روی عنوان."""
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                               QFrame, QLabel)
from PySide6.QtCore import Qt

from core.report_text import results_table_rows_with_keys
from core.data_manager import data_manager

# توضیح پارامترها (hover روی عنوان) -- همان سبک صفحات تحلیل دیگر
PARAM_DESCRIPTIONS = {
    "max_altitude": "بیشینهٔ ارتفاع رسیدگی راکت نسبت به نقطهٔ پرتاب (اوج پرواز).",
    "max_velocity": "بیشترین سرعت لحظه‌ای در کل پرواز؛ معمولاً درست پیش از خاموشی موتور.",
    "velocity_at_burnout": "سرعت راکت در لحظهٔ پایان سوختن موتور.",
    "max_g": "بیشینهٔ شتاب وارد بر سازه بر حسب g؛ ملاک استحکام سازه و اجزای الکترونیک.",
    "accel_at_landing": "شتاب ثبت‌شده در لحظهٔ برخورد به زمین (معیار شدت فرود).",
    "landing_velocity": "سرعت راکت هنگام برخورد به زمین؛ عدد کوچک‌تر یعنی کارایی بهتر چتر.",
    "dynamic_pressure_max": "بیشینهٔ فشار دینامیکی هوا (Max Q)؛ سنگین‌ترین لحظهٔ بار هوایی روی سازه.",
    "max_q_time": "زمان وقوع بیشینهٔ فشار دینامیکی از لحظهٔ پرتاب.",
    "max_q_velocity": "سرعت راکت در لحظهٔ وقوع Max Q.",
    "estimated_Cd": "ضریب پسای راکت که از خود دادهٔ پرواز برآورد شده است.",
    "ground_temperature_c": "دمای هوا در سطح زمین در لحظهٔ پرتاب.",
    "apogee_temperature_c": "دمای محیط در ارتفاع اوج پرواز.",
    "temperature_lapse_rate_c_per_km": "نرخ افت دمای هوا با ارتفاع، از دادهٔ همین پرواز (مدل استاندارد атмосفر ≈ ۶٫۵ درجه بر کیلومتر).",
    "mpu_self_heating_offset_c": "اختلاف دمای ثابت سنسورها به‌خاطر گرمای خودِ تراشهٔ ژیروسکوپ.",
    "parachute_deploy_altitude": "ارتفاعی که چتر نجات در آن باز شده است.",
    "parachute_deploy_time": "زمان باز شدن چتر از لحظهٔ پرتاب.",
    "velocity_before_chute": "سرعت راکت درست پیش از باز شدن چتر.",
    "velocity_after_chute": "سرعت تثبیت‌شدهٔ نزول پس از باز شدن چتر.",
    "impact_energy_j": "انرژی جنبشی راکت هنگام برخورد به زمین.",
    "ground_humidity_percent": "رطوبت نسبی هوا در سطح زمین در لحظهٔ پرتاب (سنسور ماژول دما و رطوبت).",
    "apogee_humidity_percent": "رطوبت نسبی هوا در ارتفاع اوج پرواز.",
    "ground_uv_index": "شاخص تشعشع فرابنفش خورشید در سطح زمین در لحظهٔ پرتاب.",
    "apogee_uv_index": "شاخص تشعشع فرابنفش خورشید در ارتفاع اوج پرواز.",
    "aht_bmp_temp_diff_c": "اختلاف دمای خوانده‌شدهٔ ماژول رطوبت (AHT21B) و ماژول فشار (BMP280)؛ معیاری برای سلامت کالیبراسیون سنسورها.",
    "estimated_Cd": "ضریب پسا (دراگ) برآوردی از دادهٔ همین پرواز.",
}


class _IndicesPanel(QFrame):
    """یک کارت جدول شاخص‌ها: سربرگ + ردیف‌های زبرای «عنوان — مقدار» تک‌خطی.

    مشابه گزارش PDF: زمینهٔ ردیف‌ها یک‌درمیان فرق می‌کند تا چشم سطر را گم
    نکند و رنگ مقدارها همان رنگ گزارش رنگی است (پروازی: نارنجی، محیطی: کهربایی)."""

    _ROW_EVEN = "#1a2029"   # زمینهٔ کارت
    _ROW_ODD = "#212a38"    # یک درمیان روشن‌تر

    def __init__(self, title: str, value_color: str = "#ff9f1c", parent=None):
        super().__init__(parent)
        self.setObjectName("IndicesPanel")
        self.setLayoutDirection(Qt.RightToLeft)
        self._value_color = value_color
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 12)
        lay.setSpacing(0)

        self.header = QLabel(title)
        self.header.setObjectName("IndicesHeader")
        lay.addWidget(self.header)

        self.rows_box = QVBoxLayout()
        self.rows_box.setSpacing(1)
        self.rows_box.setContentsMargins(0, 6, 0, 0)
        lay.addLayout(self.rows_box)
        lay.addStretch(1)

    def set_rows(self, rows):
        """rows = فهرست (کلید، عنوان فارسی، مقدار) — پاک و بازسازی."""
        while self.rows_box.count():
            item = self.rows_box.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        for r, (key, label, value) in enumerate(rows):
            row = QFrame()
            row.setObjectName("IndicesRow")
            row.setProperty("odd", bool(r % 2))
            row.setLayoutDirection(Qt.RightToLeft)
            row_lay = QHBoxLayout(row)
            row_lay.setContentsMargins(10, 3, 10, 3)
            row_lay.setSpacing(8)

            title = QLabel(label)
            title.setProperty("class", "CardTitleCompact")
            title.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            title.setToolTip(PARAM_DESCRIPTIONS.get(key, label))
            val = QLabel(value)
            val.setProperty("class", "CardValueCompact")
            val.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            val.setStyleSheet(f"color: {self._value_color};")

            row_lay.addWidget(title, stretch=1)
            row_lay.addWidget(val, stretch=1)
            self.rows_box.addWidget(row)


class FlightIndicesPage(QWidget):
    """تب اول «تحلیل پرواز»: هر دو جدول شاخص‌های گزارش PDF."""

    def __init__(self):
        super().__init__()
        self.setLayoutDirection(Qt.RightToLeft)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        row = QHBoxLayout()
        row.setSpacing(10)
        # رنگ مقدارها مثل گزارش رنگی PDF: جدول پروازی نارنجی، جدول محیطی کهربایی
        self.panel_flight = _IndicesPanel("شاخص‌های پروازی و صعود", "#ff9f1c")
        self.panel_env = _IndicesPanel("شاخص‌های محیطی و فرود", "#ffb020")
        row.addWidget(self.panel_flight, stretch=1)   # در RTL اولین = راست
        row.addWidget(self.panel_env, stretch=1)
        root.addLayout(row, stretch=1)

        self.refresh({})
        data_manager.analysis_ready.connect(self.refresh)

    def refresh(self, results: dict):
        rows_right, rows_left = results_table_rows_with_keys(results or {},
                                                             placeholders=True)
        self.panel_flight.set_rows(rows_right)
        self.panel_env.set_rows(rows_left)
