# -*- coding: utf-8 -*-
"""صفحهٔ «مرکز کنترل پرواز» (Live HUD Dashboard) -- سبک داشبورد فضایی مدرن.

طبق درخواست کاربر:
  - نوار سرتاسری بالای صفحه: «خط زمانی مراحل پرواز» (سکو/رانش/صعود/اوج/چتر/
    فرود) به‌جای برچسبِ وضعیت قبلی، با ترتیبِ **راست‌به‌چپ**؛ با هر تیکِ
    مرحله صدای «دینگ» پخش می‌شود (assets/phase_ding.wav، مکانیزم QSoundEffect
    مثل صدای فرود). هیچ نوشتهٔ وضعیتی بالای پرده‌ها نیست؛ فضای آزاد شده به
    پرده‌ها می‌رسد ولی ارتفاعِ کل نوار ثابت مانده است. دکمهٔ دانلود خام آبی
    و هم‌اندازهٔ باکس زمان پرواز (MET) است و هر دو با پالت پرده‌های خط
    زمانی هم‌خانواده‌اند (زمینهٔ تیره + حاشیه/متن رنگی).
  - جای خالیِ قبلیِ خط زمانی (ستون کنار نردبان): «خط زمانی رویدادهای مأموریت»
    به سبک کنسول Flight Dynamics ناسا -- اوج/چتر/فرود با زمان MET و رنگ رویداد.
  - باکس پارامترهای لحظه‌ای: واحد انگلیسی (m، km/h، g، °C…) همیشه سمت راستِ
    عدد و نام فارسی پارامتر زیر آن؛ سرعت بر حسب km/h.
  - نردبان ارتفاع: فشرده و وسط‌چین (ارتفاع نوار مقیاس محدود); عدد ارتفاع از
    بالای نردبان برداشته و کنار آن (بالای نشانگرهای اوج/چتر) نشسته، واحد m
    سمت راستِ عدد؛ سرعت عمودی + m/s در ردیف بالا.
  - باکس «لینک تله‌متری»: بدون نام ماژول و بدون آیکون اخطار؛ RSSI/SNR با
    رنگ‌بندی سبز/نارنجی/قرمز بر اساس کیفیت سیگنال.
  - ستون راست باریک‌تر شد و رادار تا لبه‌های باکسش بزرگ‌تر؛ باکس ژیروسکوپ
    بزرگ‌تر.
  - باکس «ژیروسکوپ» (نام تغییر یافته از جهت‌گیری) مثل ژیروسکوپ واقعی هواپیما،
    محدب و با اعداد و درجه.
  - باکس UV فقط عدد رنگی + نمودار (بدون نوشتهٔ سطح).
  - روند لحظه‌ای ارتفاع/سرعت دیگر «نمودار» نیست (بعد از فرود خطِ الکی از شروع به
    انتها رسم می‌کرد و برای نمایش لحظه‌ای جالب نبود): به‌جایش «نردبان ارتفاع»
    به سبک نمایشگرهای هوانوردی/مرکز کنترل ناسا (عدد درشت + نوار عمودی مدرج +
    نشانگرهای اوج/چتر) و «خط زمانی مراحل پرواز» (سکو ← رانش ← صعود ← اوج ← چتر
    ← فرود) آمده است.

صداقت داده: GPS، رطوبت، UV و آمار لینک لورا تا رسیدن دادهٔ واقعی «--» می‌مانند.
"""
import math
import os


from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
                                QPushButton, QMessageBox, QDialogButtonBox, QApplication)
from PySide6.QtCore import Qt, QTimer, QElapsedTimer, QUrl

from ui.widgets import WarningIcon
from ui.hud_widgets import (HudFrame, RadialGauge, AttitudeRadar, RocketAttitude, UvMeter,
                            PhaseTimeline, NeedleGauge)
from core import palette as colors
from core.data_manager import data_manager
from core.analysis import G0
from core.paths import get_data_dir, asset_path
from core.report_text import protect_latin_quantities

FLIGHT_PHASES = ("launched", "burnout", "ascent", "apogee",
               "descent", "chute_fail")  # فازهای «در پرواز» برای تایمر پرواز
EARTH_RADIUS_M = 6371000.0

# آستانه‌های کیفیت لینک لورا برای رنگ‌بندی (مقادیر مرسوم SX1278):
#   RSSI (dBm): بهتر از -90 خوب، -90..-110 ضعیف، بدتر از -110 خیلی ضعیف
#   SNR  (dB) : بالاتر از 5 خوب، 0..5 ضعیف، کمتر از 0 خیلی ضعیف
GOOD = colors.COLOR_OK
WEAK = colors.COLOR_WARN
BAD = colors.COLOR_ERROR


def _persian_num(text: str) -> str:
    table = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
    return text.translate(table)


def _rssi_color(v: float) -> str:
    if v >= -90:
        return GOOD
    if v >= -110:
        return WEAK
    return BAD


def _snr_color(v: float) -> str:
    if v >= 5:
        return GOOD
    if v >= 0:
        return WEAK
    return BAD


class HudDashboardPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setLayoutDirection(Qt.RightToLeft)

        self.setObjectName("HudPage")
        self.setStyleSheet(
            "#HudPage { background-color: qradialgradient("
            "cx:0.5, cy:0.18, radius:1.15, fx:0.5, fy:0.12, "
            "stop:0 #101d38, stop:0.5 #0a1120, stop:1 #05070d); }"
        )

        # ---- تایمر پرواز (از پرتاب تا فرود؛ مبنای اصلی: ساعت کامپیوتر پرواز) ----
        self._flight_t0 = None          # t لحظهٔ پرتاب
        self._flight_t_end = None       # t لحظهٔ فرود
        self._flight_last_t = None      # t آخرین بستهٔ دریافتی
        self._flight_last_wall = QElapsedTimer()  # زمان واقعی از آخرین بسته
        self._flight_shown_ms = -1      # ضدر برگشت زمان نمایش‌داده‌شده


        self._home_lat = None
        self._home_lon = None
        self._last_vv = None

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 8, 10, 10)

        # ============================================ نوار سرتاسری وضعیت پرواز
        # دکمهٔ دانلود دادهٔ خام -- از همان ابتدا در نوار دیده می‌شود ولی تا فرودِ
        # راکت غیرفعال و خاکستری است؛ کاربر از قبل می‌داند این دکمه کجاست و پس
        # از فرود بر اساس کیفیت لینک لورا (نزدیکی به راکت) خودش شروع می‌کند.
        phase_row = QHBoxLayout()
        phase_row.setSpacing(8)
        self.download_btn = QPushButton("⬇️ دانلود داده‌های خام از راکت")
        self.download_btn.setToolTip(
            "دریافت فایل دادهٔ خام از کارت حافظهٔ کامپیوتر پرواز\n"
            "پس از فرود راکت فعال می‌شود؛ با توجه به کیفیت سیگنال لورا "
            "(نزدیکی به راکت) خودتان شروع کنید")
        self.download_btn.setEnabled(False)
        # آبی (هم‌خانوادهٔ باکس زمان پرواز)؛ هم‌اندازهٔ همان باکس
        self.download_btn.setFixedHeight(40)
        self.download_btn.setMinimumWidth(200)
        # در هر دو حالت آبی است؛ حالت غیرفعال کمی تیره‌تر تا «آمادهٔ بعد از
        # فرود» حس شود و با ترکیب رنگی نوار بالا هم‌خوان بماند.
        self.download_btn.setStyleSheet(
            "QPushButton { background-color:#4fa3f7; color:#08131f; font-weight:800;"
            " font-size:13px; border:1px solid #4fa3f7; border-radius:8px; padding:0px 14px; }"
            "QPushButton:disabled { background-color:#2b4a6e; color:#c3daf5;"
            " border:1px solid #4a7bb5; font-weight:600; }"
            "QPushButton:hover:enabled { background-color:#63b0f8; border:1px solid #7cbcf9; }")
        self.download_btn.clicked.connect(self._download_raw_data)
        phase_row.addWidget(self.download_btn)

        # نوار بالای صفحه: خط زمانی مراحل پرواز (سکو ← رانش ← صعود ← اوج ←
        # چتر ← فرود) به‌جای برچسبِ وضعیت قبلی؛ ترتیب چیدمان راست‌به‌چپ است و
        # با هر تیکِ مرحله صدای «دینگ» پخش می‌شود (QSoundEffect، همان مکانیزم
        # صدای فرود؛ بدون QtMultimedia هم برنامه کار می‌کند).
        self.phase_timeline = PhaseTimeline()
        self.phase_timeline.setToolTip(
            "مراحل پرواز راست‌به‌چپ: سکو - رانش - صعود - اوج - چتر - فرود\n"
            "با هر تغییر مرحله صدای «دینگ» پخش می‌شود")
        phase_row.addWidget(self.phase_timeline, stretch=1)

        # قرینهٔ دکمهٔ دانلود در سمت دیگر نوار: باکس «زمان پرواز» (MET) -- از
        # لحظهٔ پرتاب تا فرود با دقت میلی‌ثانیه (دقیقه:ثانیه.میلی‌ثانیه) بر
        # اساس ساعت کامپیوتر پرواز؛ حین پرواز زنده می‌چرخد و پس از فرود ثابت
        # می‌ماند.
        self.flight_timer_lbl = QLabel("زمان پرواز  ۰۰:۰۰.۰۰۰")
        self.flight_timer_lbl.setAlignment(Qt.AlignCenter)
        # هم‌اندازهٔ دکمهٔ دانلود: ارتفاع و حداقل عرض یکسان
        self.flight_timer_lbl.setFixedHeight(40)
        self.flight_timer_lbl.setMinimumWidth(200)
        self.flight_timer_lbl.setToolTip(
            "زمان پرواز (MET): از لحظهٔ پرتاب تا لحظهٔ فرود\n"
            "دقت میلی‌ثانیه (دقیقه:ثانیه.میلی‌ثانیه) بر اساس ساعت کامپیوتر پرواز\n"
            "حین پرواز زنده به‌روز می‌شود و پس از فرود روی زمان نهایی ثابت می‌ماند")
        phase_row.addWidget(self.flight_timer_lbl)
        self._apply_flight_timer_style("idle")

        # صدای «دینگ» هر تیکِ مرحله (فایل کوتاه مخصوص؛ بدون QtMultimedia ← beep)
        self._ding = None
        try:
            from PySide6.QtMultimedia import QSoundEffect
            snd = QSoundEffect(self)
            snd.setSource(QUrl.fromLocalFile(asset_path("phase_ding.wav")))
            snd.setVolume(0.55)
            self._ding = snd
        except Exception:
            self._ding = None

        root.addLayout(phase_row)
        data_manager.flight_phase_changed.connect(self._on_flight_phase)

        # ============================================================ ردیف اصلی
        main_row = QGridLayout()
        main_row.setSpacing(10)
        root.addLayout(main_row, stretch=3)

        # ------------------------------------------------ ستون گیج‌ها (۲×۳)
        gauges_panel = HudFrame(title="پارامترهای لحظه‌ای -- آرایهٔ سنسور اصلی", accent=colors.ALTITUDE)
        gauges_lay = QGridLayout(gauges_panel)
        gauges_lay.setSpacing(2)
        gauges_lay.setContentsMargins(2, 2, 2, 2)

        self.gauge_alt = RadialGauge(unit="ارتفاع (m)", min_val=0, max_val=1500,
                                      accent=colors.ALTITUDE, decimals=0)
        self.gauge_vel = RadialGauge(unit="سرعت (km/h)", min_val=-150, max_val=950,
                                      accent=colors.VELOCITY, decimals=0)
        self.gauge_accel = RadialGauge(unit="شتاب کل (g)", min_val=0, max_val=8,
                                        accent=colors.ACCEL_TOTAL, decimals=2)
        self.gauge_temp = RadialGauge(unit="دما (°C)", min_val=-20, max_val=60,
                                       accent=colors.TEMPERATURE, decimals=1)
        self.gauge_pressure = RadialGauge(unit="فشار (hPa)", min_val=550, max_val=1030,
                                           accent=colors.PRESSURE, decimals=0)
        self.gauge_humidity = RadialGauge(unit="رطوبت (%RH)", min_val=0, max_val=100,
                                           accent=colors.HUMIDITY, decimals=0)

        # آیکون اخطار رطوبت -- روی سلول گیج رطوبت (بدون نوشتهٔ زیرین)
        self.humidity_warning = WarningIcon(
            "سنسور رطوبت AHT21B هنوز روی سخت‌افزار نصب نشده، برای همین این گیج «--» نشان "
            "می‌دهد. این یک ویژگی آمادهٔ آینده است."
        )
        humid_cell = QVBoxLayout()
        humid_cell.setContentsMargins(0, 0, 0, 0)
        hw_row = QHBoxLayout()
        hw_row.setContentsMargins(0, 0, 0, 0)
        hw_row.addStretch()
        hw_row.addWidget(self.humidity_warning)
        humid_cell.addLayout(hw_row)
        humid_cell.addWidget(self.gauge_humidity, stretch=1)

        gauge_defs = [
            (self.gauge_alt, 0, 0), (self.gauge_vel, 0, 1), (self.gauge_accel, 0, 2),
            (self.gauge_temp, 1, 0), (self.gauge_pressure, 1, 1),
        ]
        for g, row, col in gauge_defs:
            gauges_lay.addWidget(g, row, col)
        gauges_lay.addLayout(humid_cell, 1, 2)
        main_row.addWidget(gauges_panel, 0, 0, 2, 1)

        # ------------------------------------------------ ستون میانی: رادار GPS
        radar_panel = HudFrame(title="رادار GPS", accent=colors.COLOR_INFO)
        radar_lay = QVBoxLayout(radar_panel)
        radar_lay.setContentsMargins(2, 2, 2, 2)
        radar_lay.setSpacing(2)
        self.radar = AttitudeRadar(accent=colors.COLOR_INFO)
        # رادار تا لبه‌های باکس بزرگ می‌شود (بدون سقف اندازه). چرخش «بالای صفحه»
        # با درگ موس روی خود رادار انجام می‌شود؛ درجهٔ چرخش در ردیف پایین نمایش
        # داده می‌شود و اعداد «سمت» همیشه نسبت به شمال واقعی باقی می‌مانند.
        radar_lay.addWidget(self.radar, stretch=1)

        pos_grid = QGridLayout()
        pos_grid.setContentsMargins(4, 0, 4, 0)
        pos_grid.setVerticalSpacing(1)     # دو ردیف نوشته به هم نزدیک
        pos_grid.setHorizontalSpacing(10)
        self.lbl_gps_sats = QLabel("ماهواره: --")
        self.lbl_gps_hdop = QLabel("HDOP: --")
        self.lbl_pos_diag = QLabel("فاصله: --")
        self.lbl_pos_az = QLabel("سمت: --")
        self.lbl_heading = QLabel("بالا: ۰°")
        for lbl in (self.lbl_gps_sats, self.lbl_gps_hdop, self.lbl_pos_diag,
                    self.lbl_pos_az, self.lbl_heading):
            lbl.setProperty("class", "CardTitleCompact")
            lbl.setAlignment(Qt.AlignCenter)
        # ردیف اول: ماهواره | HDOP    ردیف دوم: فاصله | سمت | جهتِ بالا
        pos_grid.addWidget(self.lbl_gps_sats, 0, 0)
        pos_grid.addWidget(self.lbl_gps_hdop, 0, 1)
        pos_grid.addWidget(self.lbl_pos_diag, 1, 0)
        pos_grid.addWidget(self.lbl_pos_az, 1, 1)
        pos_grid.addWidget(self.lbl_heading, 1, 2)
        self.radar.heading_changed.connect(self._on_heading_changed)
        radar_lay.addLayout(pos_grid)
        gps_warn_row = QHBoxLayout()
        self.gps_warning = WarningIcon(
            "ماژول GPS هنوز روی سخت‌افزار نصب نشده، برای همین موقعیت/فاصله/سمت راکت «--» نشان داده "
            "می‌شود. این یک ویژگی آمادهٔ آینده است."
        )
        self.gps_warning_lbl = QLabel("داده GPS در دسترس نیست")
        self.gps_warning_lbl.setProperty("class", "CardTitleCompact")
        self.gps_warning_lbl.setStyleSheet("color:#ef5350;")
        gps_warn_row.addStretch()
        gps_warn_row.addWidget(self.gps_warning)
        gps_warn_row.addWidget(self.gps_warning_lbl)
        gps_warn_row.addStretch()
        radar_lay.addLayout(gps_warn_row)
        main_row.addWidget(radar_panel, 0, 1, 2, 1)

        # ------------------------- ستون راست (باریک): لینک تله‌متری + ژیروسکوپ + UV
        right_col = QVBoxLayout()
        right_col.setContentsMargins(0, 0, 0, 0)
        right_col.setSpacing(8)

        # -- باکس لینک تله‌متری (فقط اعداد رنگی، بدون نام ماژول/اخطار) --
        # ارتفاعش فشرده و ثابت است تا کل فضای عمودیِ ستون به ژیروسکوپ برسد و
        # ژیروسکوپ (که مربعی رسم می‌شود) عرض ستون را پر کند و کنارش خالی نماند.
        link_panel = HudFrame(title="لینک تله‌متری", accent=colors.COLOR_INFO)
        link_panel.setFixedHeight(58)
        link_lay = QVBoxLayout(link_panel)
        link_lay.setContentsMargins(6, 4, 6, 4)
        link_row = QHBoxLayout()
        self.lbl_rssi = QLabel("RSSI: --")
        self.lbl_snr = QLabel("SNR: --")
        self.lbl_pktrate = QLabel("نرخ: --")
        for lbl in (self.lbl_rssi, self.lbl_snr, self.lbl_pktrate):
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet("font-size:12px; font-weight:bold; color:#8fa3b8;")
            link_row.addWidget(lbl)
        link_lay.addLayout(link_row)
        right_col.addWidget(link_panel)

        # -- باکس زاویهٔ راکت (سیلوئت مرجع + انحراف از عمود) -- بزرگ‌تر --
        att_panel = HudFrame(title="زاویهٔ راکت", accent=colors.COLOR_INFO)
        att_lay = QVBoxLayout(att_panel)
        att_lay.setContentsMargins(4, 4, 4, 4)
        self.attitude = RocketAttitude()
        att_lay.addWidget(self.attitude, stretch=1)
        right_col.addWidget(att_panel, stretch=1)

        # -- باکس تشعشع UV (فقط عدد رنگی + نمودار، بدون نوشتهٔ سطح) --
        # ارتفاع فشرده و ثابت -- مثل باکس لینک، تا فضای عمودی به ژیروسکوپ برسد.
        uv_panel = HudFrame(title="تشعشع UV", accent=colors.UV_INDEX)
        uv_panel.setFixedHeight(70)
        uv_lay = QVBoxLayout(uv_panel)
        uv_lay.setContentsMargins(6, 4, 6, 4)
        uv_row = QHBoxLayout()
        self.lbl_uv_val = QLabel("--")
        self.lbl_uv_val.setStyleSheet(f"font-size:20px; font-weight:800; color:{colors.UV_INDEX};")
        self.lbl_uv_val.setFixedWidth(48)
        self.uv_meter = UvMeter()
        self.uv_warning = WarningIcon(
            "سنسور GUVA-S12SD هنوز روی سخت‌افزار نصب نشده، برای همین این مقدار «--» نشان می‌دهد."
        )
        uv_row.addWidget(self.lbl_uv_val)
        uv_row.addWidget(self.uv_meter, stretch=1)
        uv_row.addWidget(self.uv_warning)
        uv_lay.addLayout(uv_row)
        right_col.addWidget(uv_panel)

        right_wrap = QWidget()
        right_wrap.setLayout(right_col)
        main_row.addWidget(right_wrap, 0, 2, 2, 1)

        # تعادل نهایی: هیچ فضای زائدی کنار رادار یا ژیروسکوپ نماند. چون هر دو
        # مربعی رسم می‌شوند، عرض ستونشان طوری تنظیم شده که با ارتفاع مفیدشان
        # بخواند. رادار کمی بزرگ‌تر از ژیروسکوپ است.
        main_row.setColumnStretch(0, 6)   # گیج‌ها
        main_row.setColumnStretch(1, 5)   # رادار (کمی بزرگ‌تر از ژیروسکوپ)
        main_row.setColumnStretch(2, 4)   # لینک/ژیروسکوپ/UV

        # ============== ردیف پایین: گیج‌های دایره‌کامل «بدون تکرار» (بدون اسکرول) ==============
        # شتاب، سرعت، فشار محیط و دما بالای صفحه نمایش داده می‌شوند؛ پس اینجا
        # فقط اطلاعاتی می‌آید که جای دیگری نیست: سلامت انرژی (ولتاژ/جریان/توان
        # لحظه‌ای + پیوستگی چاشنی) و سلامت لینک/GPS (SNR و HDOP) -- تا وقتی
        # دادهٔ واقعی لینک یا GPS نرسیده، صادقانه «--» نشان می‌دهند.
        # بدون عنوانِ پنل (طبق درخواست کاربر: فقط قاب و خود گیج‌ها)
        live_panel = HudFrame(title="", accent=colors.ALTITUDE)
        live_row = QHBoxLayout(live_panel)
        live_row.setContentsMargins(10, 8, 10, 6)
        live_row.setSpacing(10)
        self.g_vbat = NeedleGauge("ولتاژ باتری", "V", 6.0, 8.4, colors.COLOR_OK,
                                  zones=[("#ef5350", 0.0), ("#f2c14e", 0.3),
                                         ("#35d07f", 0.55)],
                                  decimals=2)
        self.g_cur = NeedleGauge("جریان مصرفی", "A", 0.0, 5.0, colors.COLOR_INFO,
                                 zones=[("#35d07f", 0.0), ("#f2c14e", 0.55),
                                        ("#ef5350", 0.85)],
                                 decimals=2)
        self.g_power = NeedleGauge("توان لحظه‌ای", "W", 0.0, 3.0, "#c084fc",
                                   zones=[("#35d07f", 0.0), ("#f2c14e", 0.55),
                                          ("#ef5350", 0.85)],
                                   decimals=2)
        self.g_snr = NeedleGauge("قدرت لینک (SNR)", "dB", -20.0, 15.0, "#4fd1c5",
                                 zones=[("#ef5350", 0.0), ("#f2c14e", 0.5),
                                        ("#35d07f", 0.8)],
                                 decimals=1)
        self.g_hdop = NeedleGauge("کیفیت GPS (HDOP)", "", 0.0, 10.0, "#7cbcf9",
                                  zones=[("#35d07f", 0.0), ("#f2c14e", 0.2),
                                         ("#ef5350", 0.5)],
                                  decimals=1)
        for g in (self.g_vbat, self.g_cur, self.g_power, self.g_snr, self.g_hdop):
            live_row.addWidget(g, 1)
        root.addWidget(live_panel, stretch=1)

        # ============================================================ تایمرها/سیگنال‌ها
        self._sweep_timer = QTimer(self)
        self._sweep_timer.setInterval(40)
        self._sweep_timer.timeout.connect(self._tick_sweep)
        self._sweep_timer.start()
        self._sweep_angle = 0.0

        # به‌روزرسانی روانِ میلی‌ثانیه‌های «زمان پرواز» بین بسته‌های تله‌متری
        self._flight_ui_timer = QTimer(self)
        self._flight_ui_timer.setInterval(47)
        self._flight_ui_timer.timeout.connect(self._tick_flight_timer)
        self._flight_ui_timer.start()

        # ---- بافر-محور: پکت‌ها فقط push می‌شوند؛ بازرسم ~۱۵Hz (بدون افت فریم) ----
        self._hud_refresh_timer = QTimer(self)
        self._hud_refresh_timer.setInterval(66)
        self._hud_refresh_timer.timeout.connect(self._refresh_live_hud)
        self._hud_refresh_timer.start()

        # ---- ولتاژ/جریان/چاشنی: نظرسنجی یک‌ثانیه‌ای GET_STATUS ----
        self._power_poll_timer = QTimer(self)
        self._power_poll_timer.setInterval(1000)
        self._power_poll_timer.timeout.connect(self._poll_onboard_status)
        self._power_poll_timer.start()

        data_manager.telemetry_updated.connect(self._on_telemetry)
        data_manager.connection_changed.connect(self._on_connection_changed)
        self.phase_timeline.set_phase(data_manager.flight_phase)

    # ------------------------------------------------------------------
    def _tick_sweep(self):
        self._sweep_angle = (self._sweep_angle + 3) % 360
        self.radar.set_sweep_angle(self._sweep_angle)

    def _on_heading_changed(self, deg: float):
        """درجهٔ چرخشِ «بالای رادار» را در ردیف پایین نمایش می‌دهد."""
        self.lbl_heading.setText(
            "بالا: " + "\u202a" + _persian_num(f"{deg:.0f}°") + "\u202c")

    # ------------------------ نوار بالای صفحه: صدای دینگ
    def _play_ding(self):
        """صدای «دینگ» کوتاه برای هر تیکِ مرحله (بدون QtMultimedia ← beep)."""
        if self._ding is not None:
            self._ding.play()
        else:
            QApplication.beep()

    def _on_connection_changed(self, _connected: bool):
        self._home_lat = None
        self._home_lon = None
        self.radar.reset_range()
        self._reset_live_hud()
        # بعد از پاک‌سازی، فاز فعلی را دوباره روی خط زمانی بنشان (ترتیب سیگنال‌ها
        # بین صفحه‌ها تضمینی نیست) -- این «بازنشانی» صدا ندارد.
        self.phase_timeline.set_phase(data_manager.flight_phase)

    def _reset_live_hud(self):
        """پاک‌سازی گیج‌های عقربه‌ای برای پرواز جدید (یا قطع اتصال)."""
        self.g_vbat.reset()
        self.g_cur.reset()
        self.g_power.reset()
        self.g_snr.reset()
        self.g_hdop.reset()
        self.phase_timeline.reset()
        self._last_vv = None

    # ------------------------ گیج‌های زنده: بازرسم میرایی‌شده
    def _refresh_live_hud(self):
        """حرکت نرم عقربه‌ها (~۱۵Hz)؛ اگر داده‌ای نرسیده باشد چیزی رسم نمی‌شود."""
        self.g_vbat.refresh()
        self.g_cur.refresh()
        self.g_power.refresh()
        self.g_snr.refresh()
        self.g_hdop.refresh()

    def _poll_onboard_status(self):
        """GET_STATUS دوره‌ای: ولتاژ باتری + جریان + مقاومت چاشنی‌ها.

        فیلدهای جریان/چاشنی اختیاری‌اند (پاسخ فریمور قدیمی فقط تا دوربین
        است) -- نبودشان با «--» صادقانه نشان داده می‌شود، بدون عددسازی.
        """
        link = data_manager.active_link
        if not link or not data_manager.connected:
            return
        try:
            response = (link.send_command("GET_STATUS") or "").strip()
        except Exception:
            return
        if not response.startswith("STATUS,"):
            return
        parts = response.split(",")

        def fnum(i: int):
            try:
                if len(parts) > i and parts[i].strip() != "":
                    return float(parts[i])
            except ValueError:
                pass
            return None

        v = fnum(1)
        if v is not None:
            self.g_vbat.set_value(v)
        curr = fnum(6)          # میلی‌آمپر از فریمور
        if curr is not None:
            self.g_cur.set_value(curr / 1000.0)             # گیج جریان: ۰..۵ آمپر
            if v is not None:
                self.g_power.set_value(v * curr / 1000.0)   # V × A → W
        # پیوستگی چاشنی‌ها: مقاومت کمتر از ~۱۰Ω یعنی سیم پیوسته/وصل است
        p1, p2 = fnum(7), fnum(8)
        def pyro_txt(ohm):
            if ohm is None:
                return "--"
            return "وصل" if ohm < 10.0 else "قطع"
        self.g_cur.set_status("چاشنی ۱: " + pyro_txt(p1) + "  ·  چاشنی ۲: " + pyro_txt(p2))

    # -------------------------------- تله‌متری زنده
    @staticmethod
    def _expand_gauge(gauge, value: float, headroom: float = 1.2):
        """بزرگ‌کردن خودکار دامنهٔ گیج وقتی مقدار به سقف آن نزدیک می‌شود --
        چون با فیزیک واقعی (سوخت/نازل/وزن دلخواه کاربر) ممکن است اوج، سرعت
        یا شتاب از محدودهٔ پیش‌فرض گیج بیشتر شود."""
        if value is None:
            return
        if value > gauge._max * 0.92:
            gauge._max = value * headroom
            gauge.update()
        elif gauge._min < 0 and value < gauge._min * 0.92:
            gauge._min = value * headroom
            gauge.update()

    # ==================================================================
    # باکس «زمان پرواز» (قرینهٔ دانلود خام) + فعال‌شدن دانلود پس از فرود
    # ==================================================================
    def _on_flight_phase(self, phase: str):
        # دکمهٔ دانلود خام از اول دیده می‌شود ولی فقط پس از فرود فعال است
        self.download_btn.setEnabled(phase == "landed")
        if phase == "idle":
            # چرخهٔ کاملاً جدید (یا قطع اتصال): همه‌چیز از صفر
            self._reset_flight_timer()
            self._reset_live_hud()
        elif phase == "installing":
            # مأموریت تازه (پس از فرودِ قبلی یا اولین نصب): تله‌سنجی قبلی پاک
            # می‌شود؛ خط زمانی هم چرخهٔ جدید را از «سکو» شروع می‌کند.
            self._reset_flight_timer()
            if self.phase_timeline._current in (None, "landed"):
                self._reset_live_hud()
        elif phase in ("on_pad", "countdown"):
            # پیش از پرتاب: فقط زمان پرواز صفر می‌شود؛ خط زمانی «سکو» روشن
            # می‌ماند و هر بار دوباره دینگ نمی‌زند (فقط اولین تیکِ مرحله).
            self._reset_flight_timer()
        elif phase == "landed" and self._flight_t0 is not None and self._flight_t_end is None:
            # سیگنال فاز داخل همان بستهٔ فرود می‌آید و t آن قبلاً ثبت شده؛
            # اگر به هر دلیلی بسته‌اش نبود، از آخرین t معتبر استفاده می‌کنیم.
            self._flight_t_end = self._flight_last_t if self._flight_last_t is not None else self._flight_t0
            self._show_flight_time(self._flight_t_end - self._flight_t0)
            self._apply_flight_timer_style("landed")
        # خط زمانی مراحل: هر تیکِ مرحله = تغییر پرده + صدای «دینگ». چتر باز
        # نشدن (chute_fail) هم اگر پرده عوض نشود هشدار دینگ می‌گیرد. بازگشت
        # به «idle» (قطع اتصال/بازنشانی) بی‌صدا است؛ فقط مراحل پرواز دینگ
        # می‌زنند وگرنه هر قطع/وصل دوباره صدا می‌داد.
        changed = self.phase_timeline.set_phase(phase)
        if phase == "idle":
            return
        if changed:
            self._play_ding()
        elif phase == "chute_fail":
            self._play_ding()

    def _apply_flight_timer_style(self, state: str):
        """سبکِ هم‌خانوادهٔ پرده‌های خط زمانی: زمینهٔ تیره + خط/متن رنگی.

        رنگ وضعیت فقط در متن و حاشیه است تا ترکیب‌بندی نوار بالا با بقیهٔ
        باکس‌ها هماهنگ بماند (نه یک پلاک سبز/فیروزه‌ای جدا).
        """
        if state == "running":
            style = ("font-size:13px; font-weight:800; color:#4fd1c5;"
                     " background-color:rgba(79,209,197,30); border:1px solid #4fd1c5;"
                     " border-radius:8px; padding:0px 14px;")
        elif state == "landed":
            style = ("font-size:13px; font-weight:800; color:#7cbcf9;"
                     " background-color:rgba(79,163,247,34); border:1px solid #4fa3f7;"
                     " border-radius:8px; padding:0px 14px;")
        else:  # idle: پیش از پرتاب
            style = ("font-size:13px; font-weight:600; color:#a9bcd1;"
                     " background-color:rgba(255,255,255,16); border:1px solid rgba(255,255,255,45);"
                     " border-radius:8px; padding:0px 14px;")
        self.flight_timer_lbl.setStyleSheet(style)

    @staticmethod
    def _fmt_flight_time(seconds: float) -> str:
        ms = max(0, int(round(seconds * 1000.0)))
        minutes, rem = divmod(ms, 60000)
        secs, msec = divmod(rem, 1000)
        return _persian_num(f"{minutes:02d}:{secs:02d}.{msec:03d}")

    def _show_flight_time(self, seconds: float):
        ms = int(round(seconds * 1000.0))
        if ms <= self._flight_shown_ms:   # زمان نمایش‌داده‌شده همیشه پیش‌رونده است
            return
        self._flight_shown_ms = ms
        self.flight_timer_lbl.setText(f"زمان پرواز  {self._fmt_flight_time(seconds)}")

    def _tick_flight_timer(self):
        if self._flight_t0 is None or self._flight_t_end is not None:
            return
        if self._flight_last_t is None:
            return
        # بسته‌های تله‌متری حدوداً هر نیم‌ثانیه می‌رسند؛ بین آن‌ها با ساعت واقعی
        # درون‌یابی می‌کنیم تا میلی‌ثانیه‌ها روان بچرخند. مبنای اصلی همچنان
        # «t» کامپیوتر پرواز است و روی بستهٔ فرود دقیقاً ثابت می‌شود.
        elapsed = (self._flight_last_t - self._flight_t0) + self._flight_last_wall.elapsed() / 1000.0
        self._show_flight_time(elapsed)

    def _reset_flight_timer(self):
        self._flight_t0 = None
        self._flight_t_end = None
        self._flight_shown_ms = -1
        self.flight_timer_lbl.setText("زمان پرواز  ۰۰:۰۰.۰۰۰")
        self._apply_flight_timer_style("idle")

    def _download_raw_data(self):
        """دریافت فایل دادهٔ خام از کامپیوتر پرواز. کیفیت لینک روی خودِ HUD
        دیده می‌شود؛ اینجا فقط تأیید سادهٔ کاربر است.
        ویدیوهای دوربین از این مسیر نیستند و فقط با کابل USB منتقل می‌شوند."""
        link = data_manager.active_link
        if not link or not data_manager.connected:
            QMessageBox.warning(self, "بدون اتصال", "اتصال به کامپیوتر پرواز برقرار نیست.")
            return

        box = QMessageBox(self)
        box.setWindowTitle("دانلود داده‌های خام")
        box.setIcon(QMessageBox.NoIcon)
        box.setText("آیا سیگنال قوی است؟")
        yes_btn = box.addButton("بله — شروع دانلود", QMessageBox.AcceptRole)
        no_btn = box.addButton("نه — نزدیک‌تر می‌شوم", QMessageBox.RejectRole)
        box.setDefaultButton(yes_btn)
        _center_msg_buttons(box)
        box.exec()
        if box.clickedButton() is not yes_btn:
            return

        # ---- شروع دریافت فایل خام ----
        response = (link.send_command("DOWNLOAD") or "").strip()
        if response.startswith("ERR:NO_SD"):
            QMessageBox.warning(self, "بدون کارت حافظه",
                                "ماژول کارت SD روی راکت انتخاب/نصب نشده -- دادهٔ خام روی راکت "
                                "ذخیره نشده است.\nفایل «داده‌های زنده» (تله‌متری لورا) به‌صورت "
                                "خودکار ذخیره شده و همان مبنای تحلیل است.")
            return
        if not response.startswith("ACK:DOWNLOAD_START"):
            QMessageBox.warning(
                self, "دانلود ممکن نشد",
                "کامپیوتر پرواز آمادهٔ ارسال داده نیست (هنوز پروازی ثبت نشده یا پرواز "
                "به پایان نرسیده است).\nدر حالت واقعی، انتقال فایل از طریق همین دکمه و "
                "پروتکل فریمور انجام می‌شود.")
            return

        from core.jalali import jalali_date_for_filename
        from core.paths import build_report_filename
        m = data_manager.mission
        stamp = build_report_filename(
            jalali_date_for_filename(m.jalali_date or m.date),
            m.flight_number or "بدون‌شماره",
            "csv",
            suffix="خام",
        )
        if data_manager.demo_mode and hasattr(link, "write_csv"):
            path = os.path.join(get_data_dir("telemetry"), stamp)
            if not link.write_csv(path) or not os.path.exists(path):
                QMessageBox.warning(self, "خطا در دریافت", "دریافت/ذخیرهٔ فایل خام ناموفق بود.")
                return
            data_manager.load_flight_csv(path)
            done = QMessageBox(self)
            done.setWindowTitle("دانلود کامل شد")
            done.setIcon(QMessageBox.NoIcon)
            done.setText("دانلود کامل شد")
            done.setInformativeText(
                "یادآوری: ویدیوهای دوربین جداگانه و از طریق کابل USB منتقل می‌شوند.")
            ok_btn = done.addButton("Ok", QMessageBox.AcceptRole)
            done.setDefaultButton(ok_btn)
            _center_msg_buttons(done)
            done.exec()
            # دانلود خام کامل و درست انجام شد → خودکار به تحلیل، تب «شاخص‌های پرواز»
            data_manager.navigate_requested.emit("شاخص‌های پرواز")
        else:
            QMessageBox.information(
                self, "شروع دریافت",
                "دستور دریافت دادهٔ خام به کامپیوتر پرواز ارسال شد. پس از اتمام انتقال، "
                "فایل از صفحهٔ «ارتباط با کامپیوتر پرواز» ذخیره و تحلیل می‌شود.\n"
                "ویدیوهای دوربین فقط از طریق کابل USB منتقل می‌شوند.")

    def _on_telemetry(self, packet: dict):
        if "sensor_status_changed" in packet:
            return

        if "pressure" in packet:
            self.gauge_pressure.set_value(packet["pressure"])
        if "temperature" in packet:
            self.gauge_temp.set_value(packet["temperature"])

        if "humidity" in packet:
            data_manager.humidity_percent = packet["humidity"]
        if "temperature_aht" in packet:
            data_manager.temperature_aht_c = packet["temperature_aht"]
        if "uv_index" in packet:
            data_manager.uv_index = packet["uv_index"]

        if data_manager.humidity_percent is not None:
            self.gauge_humidity.set_value(data_manager.humidity_percent)
            self.humidity_warning.hide()

        total_g = None
        if all(k in packet for k in ("accel_x", "accel_y", "accel_z")):
            ax, ay, az = packet["accel_x"], packet["accel_y"], packet["accel_z"]
            total_g = math.sqrt(ax * ax + ay * ay + az * az) / G0
            self.gauge_accel.set_value(total_g)
            self._expand_gauge(self.gauge_accel, total_g)
            roll = math.degrees(math.atan2(ay, az))
            # انحراف محور طولی راکت از خط قائم (۰ = کاملاً عمود) -- نه زاویهٔ
            # پرتاب! رابطهٔ دو زاویه روی سکو: انحراف = ۹۰ − زاویهٔ پرتاب
            # (پرتاب ۸۵° ← انحراف ۵°؛ پرتاب ۹۰° ← انحراف ۰°). پس از پرتاب،
            # همین فرمول انحراف واقعی لحظه‌ای راکت را از دادهٔ شتاب‌سنجِ
            # کامپیوتر پرواز می‌دهد.
            dev = math.degrees(math.atan2(-ax, math.hypot(ay, az)))
            self.attitude.set_attitude(dev, roll)

        if "altitude" in packet:
            self.gauge_alt.set_value(packet["altitude"])
            self._expand_gauge(self.gauge_alt, packet["altitude"])
        if "vertical_velocity" in packet:
            vel = packet["vertical_velocity"]
            self.gauge_vel.set_value(vel * 3.6)   # km/h
            self._expand_gauge(self.gauge_vel, vel * 3.6)
            self._last_vv = vel

        if data_manager.uv_index is not None:
            self.lbl_uv_val.setText(f"{data_manager.uv_index:.1f}")
            self.uv_meter.set_value(data_manager.uv_index)
            self.uv_warning.hide()

        # آمار لینک لورا با رنگ‌بندی کیفیت
        if data_manager.lora_rssi_dbm is not None:
            v = data_manager.lora_rssi_dbm
            self.lbl_rssi.setText(f"RSSI: {v:.0f}")
            self.lbl_rssi.setStyleSheet(f"font-size:12px; font-weight:bold; color:{_rssi_color(v)};")
        if data_manager.lora_snr_db is not None:
            v = data_manager.lora_snr_db
            self.lbl_snr.setText(f"SNR: {v:.1f}")
            self.lbl_snr.setStyleSheet(f"font-size:12px; font-weight:bold; color:{_snr_color(v)};")
        if data_manager.lora_packet_rate_hz is not None:
            self.lbl_pktrate.setText(
                protect_latin_quantities(f"نرخ: {data_manager.lora_packet_rate_hz:.1f}Hz"))

        if data_manager.gps_sats is not None:
            self.lbl_gps_sats.setText(_persian_num(f"ماهواره: {data_manager.gps_sats}"))
        if data_manager.gps_hdop is not None:
            self.lbl_gps_hdop.setText(f"HDOP: {data_manager.gps_hdop:.1f}")

        # ---- سلامت لینک و GPS (تا رسیدن دادهٔ واقعی صادقانه «--» می‌مانند) ----
        if data_manager.lora_snr_db is not None:
            self.g_snr.set_value(data_manager.lora_snr_db)
        if data_manager.gps_hdop is not None:
            self.g_hdop.set_value(data_manager.gps_hdop)
        # t همین بسته را «قبل» از به‌روزرسانی فاز ثبت می‌کنیم تا مهرهای
        # پرتاب/فرودِ تایمر دقیقاً از بستهٔ همان لحظه گرفته شوند.
        if "t" in packet:
            self._flight_last_t = packet["t"]
            self._flight_last_wall.restart()

        alt_v = packet.get("altitude")
        vv_v = packet.get("vertical_velocity", self._last_vv)
        data_manager.update_flight_phase_from_telemetry(
            altitude=alt_v, vertical_velocity=vv_v, accel_total_g=total_g)

        # تایمر پرواز: شروع از بستهٔ لحظهٔ پرتاب، توقف روی بستهٔ لحظهٔ فرود
        phase = data_manager.flight_phase
        if phase in FLIGHT_PHASES and self._flight_t0 is None:
            self._flight_t0 = self._flight_last_t
            self._apply_flight_timer_style("running")
        elif phase == "landed" and self._flight_t0 is not None and self._flight_t_end is None:
            self._flight_t_end = self._flight_last_t
            self._show_flight_time(self._flight_t_end - self._flight_t0)
            self._apply_flight_timer_style("landed")

        self._update_position()

    def _update_position(self):
        lat, lon = data_manager.gps_lat, data_manager.gps_lon
        if lat is None or lon is None:
            self.radar.set_position(None, None)
            self.lbl_pos_diag.setText("فاصله: --")
            self.lbl_pos_az.setText("سمت: --")
            self.gps_warning.show()
            self.gps_warning_lbl.show()
            return

        self.gps_warning.hide()
        self.gps_warning_lbl.hide()
        if self._home_lat is None:
            self._home_lat, self._home_lon = lat, lon

        dlat = math.radians(lat - self._home_lat)
        dlon = math.radians(lon - self._home_lon)
        north = dlat * EARTH_RADIUS_M
        east = dlon * EARTH_RADIUS_M * math.cos(math.radians(self._home_lat))
        diag = math.hypot(east, north)
        azimuth = (math.degrees(math.atan2(east, north)) + 360) % 360

        self.radar.set_position(east, north)
        self.lbl_pos_diag.setText(protect_latin_quantities(_persian_num(f"فاصله: {diag:.0f} m")))
        self.lbl_pos_az.setText(
            "سمت: " + "\u202a" + _persian_num(f"{azimuth:.0f}°") + "\u202c")


def _center_msg_buttons(box: QMessageBox) -> None:
    """دکمه‌های QMessageBox را وسط‌چین می‌کند (بدون آیکون استاندارد)."""
    btn_box = box.findChild(QDialogButtonBox)
    if btn_box:
        btn_box.setCenterButtons(True)
