# -*- coding: utf-8 -*-
"""
core/data_manager.py
---------------------
مدیریت متمرکز داده‌های نرم‌افزار: اطلاعات مأموریت، اطلاعات راکت/موتور/نازل،
وضعیت اتصال، و داده‌های پرواز (DataFrame). این ماژول به صورت Singleton
در کل برنامه استفاده می‌شود تا همه صفحات به یک منبع داده واحد دسترسی داشته باشند.

قابل توسعه برای: تله‌متری زنده، ESP32/LoRa، هوش مصنوعی تحلیل پرواز.
"""
from __future__ import annotations
import csv as csv_module
import datetime
import os
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

import pandas as pd

from PySide6.QtCore import QObject, Signal, QTimer

from core.paths import get_data_dir, get_raw_flights_dir

ARCHIVE_DIR = get_data_dir("flight_archive")

# ---------------------------------------------------------------------------
# فازهای پرواز (ماشین وضعیت) -- با ارتباط دائم لورا، وضعیت راکت از روی
# تله‌متری زنده به‌صورت خودکار تشخیص داده و در مرکز کنترل پرواز نمایش داده می‌شود.
#   idle       : متصل نیست / پیش از ورود به جریان پرتاب
#   on_pad     : آماده روی سکو (وارد مرکز کنترل پرواز شده و ضبط شروع شده، هنوز پرتاب نشده)
#   ascent     : در حال پرواز (پرتاب از روی داده تشخیص داده شد)
#   descent    : در حال فرود (چتر باز شد -- سرعت سقوط در محدودهٔ ایمن)
#   chute_fail : چتر باز نشد -- در حال سقوط (سرعت سقوط بحرانی)
#   landed     : فرود آمد
FLIGHT_PHASE_INFO = {
    "idle":       ("متصل نیست", "#7c8aa5"),
    "installing": ("🔧 در حال نصب راکت", "#7c8aa5"),
    "on_pad":     ("✅ آماده روی سکو", "#35d07f"),
    "countdown":  ("⏳ در حال شمارش معکوس…", "#ffaa00"),
    "launched":   ("🚀 راکت پرتاب شد", "#ff2a6d"),
    "burnout":    ("🔥 پایان رانش", "#ff9f43"),
    "ascent":     ("⬆️ در حال صعود", "#ff2a6d"),
    "apogee":     ("🏔 حداکثر ارتفاع", "#a970ff"),
    "descent":    ("🪂 در حال فرود", "#35d07f"),
    "chute_fail": ("خطر خطر\nچتر باز نشده\nراکت در حال سقوط است", "#ef5350"),
    "landed":     ("🛬 فرود آمد", "#4fa3f7"),
}

# آستانه‌های تشخیص فاز از تله‌متری زنده (m/s و g)
LAUNCH_VV_THRESHOLD = 3.0        # سرعت عمودی برای تشخیص لحظهٔ پرتاب
LAUNCH_ACCEL_G_THRESHOLD = 2.0   # شتاب کل برای تشخیص لحظهٔ پرتاب
BURNOUT_ACCEL_G_THRESHOLD = 1.0  # شتاب کل زیر این مقدار پس از پرتاب -> پایان رانش موتور (همان آستانهٔ تحلیل CSV)
DESCENT_VV_THRESHOLD = -1.0      # سرعت عمودی منفی -> عبور از اوج و شروع فرود
APOGEE_VV_BAND = 1.0             # سرعت عمودی نزدیک صفر -> رسیدن به اوج
CHUTE_FAIL_SPEED = 25.0          # سرعت سقوط بحرانی (چتر باز نشده) بر حسب m/s
CHUTE_OK_SPEED = 15.0            # سرعت سقوط ایمن زیر چتر
LANDED_ALT = 3.0                 # نزدیکی به زمین برای تشخیص فرود (m)
LANDED_VV = 1.0                  # سکون عمودی برای تشخیص فرود (m/s)
APOGEE_HOLD_SEC = 2.0            # حداقل مدت نمایش «حداکثر ارتفاع» پیش از «در حال فرود»
LANDED_STILL_SEC = 10.0          # سکون کامل راکت پس از فرود پیش از توقف ثبت و ذخیرهٔ خودکار داده


@dataclass
class MissionInfo:
    flight_number: str = ""
    project_number: str = ""           # شماره پروژه (فیلد جدید گزارش)
    project_name: str = ""
    rocket_name: str = ""              # نام راکت
    motor_number: str = ""             # شماره موتور
    firmware_version: str = ""         # نسخه Firmware کامپیوتر پرواز
    launch_site: str = ""
    date: str = field(default_factory=lambda: datetime.date.today().isoformat())
    jalali_date: str = ""              # تاریخ شمسی معادل (YYYY/MM/DD)
    time: str = field(default_factory=lambda: datetime.datetime.now().strftime("%H:%M:%S"))
    altitude_msl: float = 0.0          # ارتفاع محل پرتاب از سطح دریا (m)
    total_mass: float = 0.0            # وزن کل راکت (kg)
    motor_mass: float = 0.0            # وزن موتور (گرم)
    propellant_mass: float = 0.0       # وزن سوخت (گرم)
    body_diameter: float = 0.0         # قطر بدنه (m)
    body_length: float = 0.0           # طول کامل راکت (m)
    body_section_length: float = 0.0   # طول بخش استوانه‌ای (m)، از طراح
    nose_length: float = 0.0           # طول مخروط سر (m)، از طراح
    nose_cone: str = "اویو"            # شکل مخروط سر: اویو/مخروطی/نیم‌کره/تخت
    # هندسهٔ باله‌ها (در ورود دستی صفر است؛ در حالت طراحی از طراح می‌آید)
    fin_shape: str = "ذوزنقه‌ای"
    fin_count: int = 0
    fin_root_chord: float = 0.0        # m
    fin_tip_chord: float = 0.0         # m
    fin_span: float = 0.0              # m
    fin_sweep: float = 0.0             # m
    # نقاط آیرودینامیکی از نوک دماغه (m). None یعنی ورود دستی و استفاده از
    # مقدار نرمال خودکار در build_preflight_payload.
    cg_from_nose: Optional[float] = None
    cp_from_nose: Optional[float] = None
    stability_margin_calibers: Optional[float] = None
    design_source: str = "manual"      # manual | designer
    design_transfer_id: str = ""
    launch_angle: float = 90.0         # زاویه پرتاب (deg)
    chute_diameter_m: float = 0.0      # قطر چتر بازیابی (m) -- ۰ = بدون چتر


@dataclass
class SensorStatus:
    """وضعیت تفصیلی یک سنسور: فاقد سنسور / خطا / سالم و آماده کار."""
    state: str = "unknown"   # "missing" | "error" | "ok" | "unknown"
    message: str = ""        # متن خطا در صورت state == "error"


@dataclass
class MotorInfo:
    motor_type: str = ""
    total_impulse: float = 0.0     # N.s
    burn_time: float = 0.0         # s
    average_thrust: float = 0.0    # N
    throat_diameter: float = 0.0   # mm
    exit_diameter: float = 0.0     # mm
    convergent_angle: float = 0.0  # deg
    divergent_angle: float = 0.0   # deg
    nozzle_length: float = 0.0     # طول نازل (سانتی‌متر)
    chamber_pressure_bar: float = 40.0   # فشار محفظهٔ احتراق (تقریبی) -- bar، پیش‌فرض رایج موتورهای شکری


class DataManager(QObject):
    """منبع واحد حقیقت (Single Source of Truth) برای کل برنامه."""

    mission_changed = Signal()
    motor_changed = Signal()
    connection_changed = Signal(bool)
    telemetry_updated = Signal(dict)
    analysis_ready = Signal(dict)
    sensor_model_changed = Signal(str, str)
    demo_mode_changed = Signal(bool)      # وقتی کاربر از صفحهٔ ارتباط، «پورت فرضی» را انتخاب/رها می‌کند
    navigate_requested = Signal(str)      # برای دکمه‌های «برو به صفحهٔ ...» داخل دیالوگ‌ها (نام صفحه در NAV_ITEMS)
    flight_phase_changed = Signal(str)    # فاز پرواز (کلید FLIGHT_PHASE_INFO) -- تشخیص خودکار از تله‌متری لورا
    telemetry_saved = Signal(str)         # مسیر فایل خام تله‌متری لورا که پس از فرود خودکار ذخیره شد
    design_imported = Signal(dict)        # طرح کامل دریافت‌شده از RocketDesigner

    def __init__(self):
        super().__init__()
        self.mission = MissionInfo()
        self.motor = MotorInfo()

        # حالت آموزشی/نمایشی -- هر زمان کاربر از صفحهٔ «ارتباط با کامپیوتر
        # پرواز» گزینهٔ «پورت فرضی» را انتخاب و متصل شود فعال می‌شود
        # (data_manager.set_demo_mode). صفحاتی مثل داشبورد این مقدار را در
        # لحظهٔ اجرای هر مرحله می‌خوانند تا زمان‌بندی‌ها را کوتاه کنند.
        self.demo_mode: bool = False

        self.connected: bool = False
        self.active_link = None  # نمونهٔ FlightComputerLink فعال (تنظیم‌شده در صفحهٔ ارتباط)

        # آیا اطلاعات مأموریت/نازلِ *فعلی* با تاییدیهٔ واقعی (ACK:MISSION_OK)
        # به کامپیوتر پرواز منتقل شده؟ با هر تغییر بعدی در اطلاعات مأموریت/نازل
        # یا قطع اتصال، خودکار False می‌شود (چون دیگر بیانگر آخرین داده نیست).
        self.preflight_transferred: bool = False
        self.connection_type: str = "USB"
        self.sd_total_mb: float = 0.0
        self.sd_free_mb: float = 0.0
        self.uptime_seconds: Optional[int] = None
        # GPS فعلاً به صورت سخت‌افزاری روی برد نصب نیست (قابلیت آینده)
        self.sensors_status: Dict[str, SensorStatus] = {
            "BMP280": SensorStatus("unknown"),
            "MPU6050": SensorStatus("unknown"),
            "AHT21": SensorStatus("unknown"),     # سنسور دما و رطوبت AHT21B
            "UV": SensorStatus("unknown"),        # سنسور شدت اشعهٔ UV خورشید GUVA-S12SD
            "CAMERA": SensorStatus("unknown"),    # دوربین رنگی OV7670 (ضبط روی SD)
            "SD": SensorStatus("unknown"),
            "GPS": SensorStatus("missing", "ماژول GPS نصب نشده (قابلیت آینده)"),
        }
        # آماده برای آینده: وقتی GPS نصب و متصل شد، این مقدار به‌جای ورودی
        # دستی «ارتفاع از سطح دریا» در همه‌جای برنامه استفاده می‌شود
        # (نگاه کنید به data_manager.get_launch_altitude)
        self.gps_altitude_m: Optional[float] = None
        self.gps_lat: Optional[float] = None
        self.gps_lon: Optional[float] = None
        self.gps_sats: Optional[int] = None
        self.gps_hdop: Optional[float] = None

        # آماده برای آینده: سنسورها/ماژول‌های سخت‌افزاری برنامه‌ریزی‌شده که هنوز
        # در پروتکل تله‌متری فعلی ارسال نمی‌شوند (دقیقاً مشابه GPS بالا) --
        # صفحهٔ «مرکز کنترل پرواز» این مقادیر را می‌خواند و تا رسیدن دادهٔ واقعی
        # «--» نمایش می‌دهد، نه دادهٔ ساختگی.
        self.humidity_percent: Optional[float] = None      # AHT21B
        self.temperature_aht_c: Optional[float] = None      # دمای محیط -- سنسور AHT21B (مستقل از BMP280)
        self.uv_index: Optional[float] = None               # GUVA-S12SD
        self.lora_rssi_dbm: Optional[float] = None          # LoRa SX1278
        self.lora_snr_db: Optional[float] = None
        self.lora_packet_rate_hz: Optional[float] = None

        # مدل انتخابی ماژول هر سنسور (فقط برچسب نمایشی -- مورد ۱۰ لیست اصلاحات).
        # طبق تصمیم نهایی: در ابتدا همهٔ ماژول‌ها روی «انتخاب نشده» هستند تا کاربر
        # خودش از صفحهٔ «انتخاب سنسور» مدل واقعی هرکدام را انتخاب کند؛
        # ماژولی که هنوز «انتخاب نشده» (یا برای GPS: «نصب نشده») باشد، در تست
        # سلامت مرحلهٔ ۱ داشبورد نادیده گرفته می‌شود (core/analysis این مقدار را
        # نمی‌بیند -- فقط برچسب نمایشی و کلید تصمیم‌گیری برای چک‌لیست است).
        self.sensor_models: Dict[str, str] = {
            "BMP280": "نصب نشده", "MPU6050": "نصب نشده",
            "AHT21": "نصب نشده", "UV": "نصب نشده", "CAMERA": "نصب نشده",
            "SD": "نصب نشده", "GPS": "نصب نشده",
        }

        # ---- ماشین وضعیت فاز پرواز (تشخیص خودکار از تله‌متری زنده لورا) ----
        self.flight_phase: str = "idle"
        self._burnout_timer: Optional[QTimer] = None   # نمایش ۱ ثانیه‌ای «پایان رانش»
        self._apogee_timer: Optional[QTimer] = None    # نمایش «حداکثر ارتفاع» پیش از فرود
        self._apogee_hold_done: bool = False
        self._landed_save_timer: Optional[QTimer] = None  # ذخیرهٔ خودکار پس از ۱۰ ثانیه سکون

        # ---- بافر داده‌های خام تله‌متری لورا (برای ذخیرهٔ خودکار پس از فرود) ----
        # از لحظهٔ ورود به مرکز کنترل پرواز (شمارش معکوس) شروع و پس از فرود در یک
        # فایل خام با نام «تاریخ‌شمسی_شماره‌پرواز_زنده.csv» ذخیره می‌شود.
        self._lora_telemetry_log: list = []
        self._lora_logging_active: bool = False

        self.flight_df: Optional[pd.DataFrame] = None
        self._last_flight_csv_path: Optional[str] = None
        self.events: Dict[str, Optional[float]] = {
            "launch": None, "burnout": None, "apogee": None,
            "parachute": None, "landing": None,
        }
        # اسنپ‌شات «پیش‌بینی در لحظهٔ پرتاب» -- مبنای گزارش «پیش‌بینی در برابر
        # واقعیت»: با شروع شمارش معکوسِ پرواز بعدی پاک می‌شود و در لحظهٔ پرتاب
        # (فاز launched) با همان پارامترهایی که کاربر دیده ثبت می‌گردد.
        self.prediction_snapshot: Optional[dict] = None
        self.analysis_results: Dict[str, Any] = {}

        # با هر تغییر در اطلاعات مأموریت/نازل یا انتخاب مدل ماژول‌ها، انتقال
        # قبلی به کامپیوتر پرواز دیگر معتبر نیست (چک‌لیست دوباره باید ارسال
        # شود) -- شبیه‌ساز آموزشی هم انتخاب ماژول را فقط از SET_MISSION می‌فهمد.
        self.mission_changed.connect(self._invalidate_preflight)
        self.motor_changed.connect(self._invalidate_preflight)
        self.sensor_model_changed.connect(lambda *_: self._invalidate_preflight())

    def _invalidate_preflight(self):
        self.preflight_transferred = False
        if self.flight_phase == "countdown":
            # پارامترها عوض شدند → اسنپ‌شات قدیمی بی‌اعتبار؛ نسخهٔ جدید با
            # همان پارامترهای تازه (چک‌لیست باید دوباره ارسال شود)
            self.prediction_snapshot = None
            QTimer.singleShot(300, self._capture_prediction_snapshot)

    def effective_design_parameters(self) -> dict:
        """هندسهٔ آیرودینامیکی مؤثر برای هر دو مسیر ورود اطلاعات.

        در مسیر دستی CP/CG فیلد مستقیمی در فرم وجود ندارد. برای جلوگیری از
        ورود صفر یا رفتار نامعلوم، یک مدل «نرمالِ ۱٫۵ کالیبر» ساخته می‌شود:
        CP حدود ۶۷٪ طول از نوک و CG به‌اندازهٔ ۱٫۵ قطر جلوتر از آن. این
        مقدار صریحاً در payload و پیش‌بینی ثبت می‌شود و با انتقال طرح، نقاط
        واقعی طراح جایگزین آن می‌شوند.
        """
        m = self.mission
        diameter = float(m.body_diameter or 0.08)
        length = float(m.body_length or 0.0)
        if length <= 0:
            length = max(0.6, diameter * 8.0)
        cp = m.cp_from_nose if m.cp_from_nose is not None and m.cp_from_nose > 0 else length * 0.67
        normal_margin = 1.5
        cg_default = max(0.0, cp - normal_margin * diameter)
        cg = m.cg_from_nose if m.cg_from_nose is not None and m.cg_from_nose > 0 else cg_default
        margin = (cp - cg) / diameter if diameter > 0 else normal_margin
        return {
            "body_diameter_m": diameter,
            "body_length_m": length,
            "body_section_length_m": float(m.body_section_length or 0.0),
            "nose_length_m": float(m.nose_length or 0.0),
            "fin_shape": m.fin_shape or "ذوزنقه‌ای",
            "fin_count": int(m.fin_count or 0),
            "fin_root_chord_m": float(m.fin_root_chord or 0.0),
            "fin_tip_chord_m": float(m.fin_tip_chord or 0.0),
            "fin_span_m": float(m.fin_span or 0.0),
            "fin_sweep_m": float(m.fin_sweep or 0.0),
            "cp_from_nose_m": cp,
            "cg_from_nose_m": cg,
            "stability_margin_calibers": margin,
            "aero_defaulted": (m.cp_from_nose is None or m.cp_from_nose <= 0
                               or m.cg_from_nose is None or m.cg_from_nose <= 0),
            "design_source": m.design_source or "manual",
        }

    def build_preflight_payload(self) -> dict:
        """محتوای یکسانِ دستور SET_MISSION برای ارتباط، پایش و شبیه‌ساز.

        هندسهٔ کامل طراح (باله‌ها، طول، CP و CG) در همین payload می‌رود.
        اگر مسیر دستی انتخاب شده باشد، CP/CG نرمال خودکار نیز عمداً ارسال
        می‌شود تا کامپیوتر پرواز هیچ پارامتر بی‌تعریفی نداشته باشد.
        """
        m, mo = self.mission, self.motor
        design = self.effective_design_parameters()
        return {
            "flight_number": m.flight_number,
            "altitude_msl": m.altitude_msl,
            "launch_angle": m.launch_angle,
            "total_mass": m.total_mass,
            "body_diameter": design["body_diameter_m"],
            "body_length": design["body_length_m"],
            "body_section_length": design["body_section_length_m"],
            "nose_length": design["nose_length_m"],
            "nose_cone": m.nose_cone or "اویو",
            "fin_shape": design["fin_shape"],
            "propellant_mass": m.propellant_mass,
            "motor_mass": m.motor_mass,
            "chute_diameter": m.chute_diameter_m,
            "burn_time": mo.burn_time,
            "average_thrust": mo.average_thrust,
            "throat_diameter": mo.throat_diameter,
            "exit_diameter": mo.exit_diameter,
            "convergent_angle": mo.convergent_angle,
            "divergence_angle": mo.divergent_angle if mo.divergent_angle > 0 else 15.0,
            "nozzle_length": mo.nozzle_length,
            "chamber_pressure_bar": mo.chamber_pressure_bar,
            "fin_count": design["fin_count"],
            "fin_root_chord": design["fin_root_chord_m"],
            "fin_tip_chord": design["fin_tip_chord_m"],
            "fin_span": design["fin_span_m"],
            "fin_sweep": design["fin_sweep_m"],
            "cp_from_nose": design["cp_from_nose_m"],
            "cg_from_nose": design["cg_from_nose_m"],
            "stability_margin_calibers": design["stability_margin_calibers"],
            "aero_defaulted": design["aero_defaulted"],
            "design_source": design["design_source"],
            "sensor_models": dict(self.sensor_models),
        }

    def import_design_payload(self, payload: dict, transfer_id: str = "") -> bool:
        """اعمال قرارداد RocketDesigner در مدل مرکزی ایستگاه.

        این متد مستقل از UI است تا انتقال واقعی و تست خودکار هر دو از یک مسیر
        استفاده کنند. مقادیر دستیِ پرتاب مثل محل/زاویه/قطر چتر حفظ می‌شوند؛
        مواردی که طراح دارد (بدنه، باله، جرم و CG/CP) جایگزین می‌شوند؛
        موتور و نازل از صفحهٔ مأموریت ایستگاه مدیریت می‌شوند.
        """
        if not isinstance(payload, dict):
            return False
        geo = payload.get("geometry") or {}
        fins = geo.get("fins") or {}
        mass = payload.get("mass") or {}
        stability = payload.get("stability") or {}
        # مشخصات موتور/نازل از صفحهٔ مأموریت ایستگاه می‌آید؛ طراح راکت
        # نباید در صورت نبودن این بخش، مقادیر فعلی ایستگاه را صفر کند.
        nozzle = payload.get("nozzle")

        def num(value, default=0.0):
            try:
                if value is None or value == "":
                    return float(default)
                return float(value)
            except (TypeError, ValueError):
                return float(default)

        diameter_mm = num(geo.get("body_diameter_mm"))
        total_length_mm = num(geo.get("total_length_mm"))
        body_length_mm = num(geo.get("body_length_mm"))
        nose_length_mm = num(geo.get("nose_length_mm"))
        total_g = num(mass.get("total_g"))
        if diameter_mm <= 0 or total_length_mm <= 0 or total_g <= 0:
            return False

        m, mo = self.mission, self.motor
        m.body_diameter = diameter_mm / 1000.0
        m.body_length = total_length_mm / 1000.0
        m.body_section_length = body_length_mm / 1000.0
        m.nose_length = nose_length_mm / 1000.0
        m.nose_cone = str(geo.get("nose_shape") or "اویو")
        m.fin_shape = str(fins.get("shape") or "ذوزنقه‌ای")
        m.fin_count = max(0, int(num(fins.get("count"))))
        m.fin_root_chord = num(fins.get("root_chord_mm")) / 1000.0
        m.fin_tip_chord = num(fins.get("tip_chord_mm")) / 1000.0
        m.fin_span = num(fins.get("span_mm")) / 1000.0
        m.fin_sweep = num(fins.get("sweep_mm")) / 1000.0
        imported_cp = num(stability.get("cp_from_nose_mm")) / 1000.0
        imported_cg = num(stability.get("cg_from_nose_mm")) / 1000.0
        m.cp_from_nose = imported_cp if imported_cp > 0 else None
        m.cg_from_nose = imported_cg if imported_cg > 0 else None
        imported_margin = num(stability.get("margin_calibers"))
        m.stability_margin_calibers = imported_margin if imported_margin else None
        m.design_source = "designer"
        m.design_transfer_id = transfer_id
        m.total_mass = total_g / 1000.0
        m.motor_mass = num(mass.get("engine_g"))
        imported_propellant = num(mass.get("propellant_g"))
        if imported_propellant > 0:
            m.propellant_mass = min(imported_propellant, max(0.0, total_g - 1.0))
        if "chute_diameter_m" in mass:
            m.chute_diameter_m = max(0.0, num(mass.get("chute_diameter_m")))

        if isinstance(nozzle, dict):
            mo.throat_diameter = num(nozzle.get("throat_diameter_mm"))
            mo.exit_diameter = num(nozzle.get("exit_diameter_mm"))
            mo.convergent_angle = num(nozzle.get("convergent_angle_deg"))
            mo.divergent_angle = num(nozzle.get("divergent_angle_deg"))
            mo.nozzle_length = num(nozzle.get("length_cm"))
            mo.chamber_pressure_bar = num(nozzle.get("chamber_pressure_bar"), 40.0) or 40.0

        self.refresh_motor_performance()
        self.mission_changed.emit()
        self.motor_changed.emit()
        self.design_imported.emit(dict(payload))
        return True

    def mission_info_complete(self) -> bool:
        """آیا حداقل فیلدهای ضروری اطلاعات مأموریت وارد شده؟ (چک‌لیست
        کالیبراسیون ناوبری، مورد ۱).

        ارتفاع صفر متر (تراز دریا) مقداری معتبر است و کامل بودن را رد
        نمی‌کند (ممیزی 1405-06-11)."""
        m = self.mission
        return bool(m.rocket_name.strip() and m.launch_site.strip()
                    and m.total_mass > 0
                    and m.propellant_mass > 0)   # بدون سوخت، موتور کار نمی‌کند و ARM رد می‌شود

    def refresh_motor_performance(self) -> bool:
        """پر کردن ضربه/زمان سوزش/رانش میانگین MotorInfo از design_motor.

        قبلاً این سه فیلد همیشه ۰ می‌ماندند مگر دستی در آرشیو؛ در نتیجه مشاور
        بازدهی سوزش و منحنی تئوری آیرودینامیک هرگز اجرا نمی‌شدند.
        True اگر مقادیر عوض شده باشند.
        """
        m, mo = self.mission, self.motor
        try:
            from core.rocket_physics import design_motor, isa_pressure
            d = design_motor(
                float(m.propellant_mass or 0.0),
                float(mo.chamber_pressure_bar or 0.0),
                float(mo.throat_diameter or 0.0),
                float(mo.exit_diameter or 0.0),
                float(m.total_mass or 0.0),
                isa_pressure(float(m.altitude_msl or 0.0)),
                divergence_half_angle_deg=float(mo.divergent_angle or 15.0),
            )
        except Exception:
            return False
        if not d.valid:
            return False
        changed = False
        for attr, val in (("total_impulse", d.total_impulse_n_s),
                          ("burn_time", d.burn_time_s),
                          ("average_thrust", d.thrust_avg_n)):
            if abs(float(getattr(mo, attr) or 0.0) - val) > 1e-6:
                setattr(mo, attr, val)
                changed = True
        return changed

    def nozzle_info_complete(self) -> bool:
        """آیا حداقل فیلدهای ضروری اطلاعات نازل وارد شده؟ (چک‌لیست
        کالیبراسیون ناوبری، مورد ۲)."""
        mo = self.motor
        return bool(mo.throat_diameter > 0 and mo.exit_diameter > 0 and mo.chamber_pressure_bar > 0)

    def update_sensor_status(self, name: str, state: str, message: str = ""):
        """state: 'missing' | 'error' | 'ok'"""
        self.sensors_status[name] = SensorStatus(state, message)
        self.telemetry_updated.emit({"sensor_status_changed": name})

    def set_connection(self, connected: bool, conn_type: str = "USB"):
        self.connected = connected
        self.connection_type = conn_type
        if not connected:
            # با قطع اتصال، هر انتقال قبلی به کامپیوتر پرواز دیگر معتبر
            # نیست -- برای اتصال بعدی باید دوباره ارسال شود.
            self.preflight_transferred = False
            # قطع ارتباط لورا در میانهٔ پرواز، فاز را صفر نمی‌کند تا آخرین
            # وضعیت شناخته‌شده حفظ شود؛ اما پیش از پرتاب (installing/on_pad/
            # countdown) به حالت اولیه برمی‌گردیم.
            if self.flight_phase in ("idle", "installing", "on_pad", "countdown"):
                self.set_flight_phase("idle")
        self.connection_changed.emit(connected)

    def mark_preflight_transferred(self, ok: bool):
        """صدا زده می‌شود از صفحهٔ ارتباط پس از تلاش برای ارسال اطلاعات
        مأموریت/نازل به کامپیوتر پرواز (SET_MISSION). فقط با تاییدیهٔ واقعی
        (ACK:MISSION_OK) مقدار True می‌گیرد؛ چک‌لیست کالیبراسیون ناوبری
        (مرحلهٔ ۲ داشبورد) از همین پرچم برای شرط سوم استفاده می‌کند."""
        self.preflight_transferred = ok

    def set_demo_mode(self, active: bool):
        """فعال/غیرفعال‌کردن حالت آموزشی در حین اجرا (وقتی کاربر از صفحهٔ
        ارتباط، «پورت فرضی» را متصل/قطع می‌کند) -- فقط در صورت تغییر واقعی
        سیگنال می‌فرستد تا صفحات مشترک (نوار بالا و غیره) بی‌مورد رفرش نشوند."""
        if self.demo_mode == active:
            return
        self.demo_mode = active
        self.demo_mode_changed.emit(active)

    # ------------------------------------------------------------------
    # ماشین وضعیت فاز پرواز
    # ------------------------------------------------------------------
    def set_flight_phase(self, phase: str):
        """تنظیم دستی فاز پرواز (مثلاً installing/on_pad هنگام نصب و کالیبراسیون،
        countdown هنگام ورود به مرکز کنترل پرواز). فقط در صورت تغییر واقعی سیگنال
        می‌فرستد."""
        if phase == self.flight_phase:
            return
        self.flight_phase = phase
        if phase in ("idle", "installing", "on_pad"):
            self._apogee_hold_done = False
            self._apogee_timer = None
        if phase in ("idle", "installing", "on_pad", "countdown"):
            # چرخهٔ جدید: اسنپ‌شات پرواز قبلی دیگر معتبر نیست
            self.prediction_snapshot = None
        if phase == "countdown":
            # ثبت اسنپ‌شات در «شروع شمارش معکوس» -- پارامترها با انتقال چک‌لیست
            # قفل‌شده‌اند و محاسبهٔ ~۱.۵ ثانیه‌ایِ مونت‌کارلو اینجا انجام می‌شود
            # تا در لحظهٔ حساس پرتاب، جریان تله‌متری هیچ وقفه‌ای نخورد.
            QTimer.singleShot(300, self._capture_prediction_snapshot)
        elif phase == "launched" and self.prediction_snapshot is None:
            # مسیر پشتیبان (بدون شمارش معکوس): همین‌جا ثبت شود؛ خطا هرگز
            # پرواز را متوقف نمی‌کند.
            self._capture_prediction_snapshot()
        self.flight_phase_changed.emit(phase)

    def prediction_snapshot_or_rebuild(self) -> Optional[dict]:
        """اسنپ‌شات «پیش‌بینی لحظهٔ پرتاب» برای گزارش‌ها و تب تحلیل.

        اگر اسنپ‌شات در حافظه نباشد (مثلاً برنامه بین پرواز و گزارش باز شده
        باشد)، همان محاسبه با پارامترهای ثبت‌شدهٔ مأموریت -- که منبعِ همان
        SET_MISSION موقع پرتاب بود -- بازسازی می‌شود تا بخش «پیش‌بینی در
        برابر واقعیت» هرگز حذف نشود. نسخهٔ بازسازی‌شده با کلید
        fallback=True علامت می‌خورد تا صادقانه توضیح داده شود."""
        if self.prediction_snapshot is not None:
            return self.prediction_snapshot
        try:
            from core.prediction_compare import capture_snapshot
            fresh = capture_snapshot(self.mission, self.motor, self.sensor_models)
            if fresh is not None:
                return dict(fresh, fallback=True)
        except Exception:
            pass
        return None

    def _capture_prediction_snapshot(self):
        """ثبت پیش‌بینیِ «لحظهٔ پرتاب» (عدد مرکزی + بازهٔ محتمل + پارامترها).
        فقط در پنجرهٔ شمارش معکوس تا اوج معتبر است؛ بعد از آن پارامترها ممکن
        است تغییر کند و مقایسه باید با همین نسخهٔ ثبت‌شده انجام شود."""
        if self.prediction_snapshot is not None:
            return
        if self.flight_phase not in ("countdown", "launched"):
            return
        try:
            from core.prediction_compare import capture_snapshot
            self.prediction_snapshot = capture_snapshot(
                self.mission, self.motor, self.sensor_models)
        except Exception:
            self.prediction_snapshot = None

    # ------------------------------------------------------------------
    # ثبت و ذخیرهٔ خام تله‌متری لورا
    # ------------------------------------------------------------------
    def start_lora_logging(self):
        """آغاز ثبت خام هر بستهٔ تله‌متری لورا در حافظه -- از لحظهٔ ورود به
        مرکز کنترل پرواز (شمارش معکوس). پس از فرود و ۱۰ ثانیه سکون کامل،
        ثبت متوقف و این بافر به‌صورت خودکار در یک فایل CSV خام ذخیره می‌شود
        (پایش زندهٔ گیج‌ها پس از آن همچنان ادامه دارد)."""
        self._lora_telemetry_log = []
        self._lora_logging_active = True

    def log_lora_packet(self, packet: dict):
        """ثبت یک بستهٔ تله‌متری خام لورا (اگر ثبت فعال باشد)."""
        if self._lora_logging_active and isinstance(packet, dict):
            self._lora_telemetry_log.append(dict(packet))

    def _telemetry_filename(self) -> str:
        """نام فایل «داده‌های زنده»: دادهٔ لحظه‌ای لورا در حین پرواز -- متمایز
        از فایل «دانلود دادهٔ خام» که بعداً از کارت SD راکت دانلود می‌شود.
        الگو: <تاریخ‌شمسی>_<شماره‌پرواز>_زنده.csv
        مثال: 1405-06-12_F-014_زنده.csv"""
        from core.paths import build_report_filename
        number = (self.mission.flight_number or "").strip() or "بدون‌شماره"
        return build_report_filename(self.mission.jalali_date or self.mission.date,
                                     number, "csv", suffix="زنده")

    def save_lora_telemetry(self) -> Optional[str]:
        """ذخیرهٔ بافر خام تله‌متری لورا در پوشهٔ دادهٔ برنامه. مسیر فایل را
        برمی‌گرداند (یا None اگر داده‌ای نبود)."""
        if not self._lora_telemetry_log:
            self._lora_logging_active = False
            return None
        # اجتماع همهٔ کلیدهای دیده‌شده برای سرستون کامل CSV
        fieldnames: list = []
        for row in self._lora_telemetry_log:
            for k in row.keys():
                if k not in fieldnames:
                    fieldnames.append(k)
        path = os.path.join(get_data_dir("telemetry"), self._telemetry_filename())
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv_module.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(self._lora_telemetry_log)
        except OSError:
            self._lora_logging_active = False
            return None
        self._lora_logging_active = False
        self.telemetry_saved.emit(path)
        return path

    def _on_landed_still_elapsed(self):
        """پس از ۱۰ ثانیه سکون کامل راکت پس از فرود: ثبت متوقف و فایل
        «داده‌های زنده» ذخیره می‌شود (پایش زندهٔ گیج‌ها قطع نمی‌شود)."""
        if self._landed_save_timer:
            self._landed_save_timer.stop()
        self.save_lora_telemetry()

    def update_flight_phase_from_telemetry(self, altitude=None, vertical_velocity=None,
                                            accel_total_g=None):
        """تشخیص خودکار فاز پرواز از روی دادهٔ زندهٔ لورا. پس از ورود به
        مرکز کنترل پرواز (countdown) فعال است. زنجیرهٔ گذارها:

            countdown → launched : سرعت عمودی یا شتاب از آستانهٔ پرتاب بگذرد
            launched  → burnout  : پس از پرتاب، افت شتاب کل (پایان رانش موتور)
            burnout   → ascent   : یک ثانیه پس از نمایش «پایان رانش» (تایمر)
            ascent    → apogee   : سرعت عمودی نزدیک صفر (رسیدن به اوج)
            apogee    → descent  : شروع سقوط با سرعت ایمن (چتر باز)
            apogee    → chute_fail: سقوط با سرعت بحرانی (چتر باز نشده)
            descent/chute_fail → landed : ارتفاع و سرعت نزدیک صفر
        """
        active = ("countdown", "launched", "burnout", "ascent",
                  "apogee", "descent", "chute_fail")
        if self.flight_phase not in active:
            return

        vv = vertical_velocity

        # countdown -> launched (لحظهٔ پرتاب توسط کیف پرتاب، بیرون از برنامه)
        if self.flight_phase == "countdown":
            launched = False
            if vv is not None and vv > LAUNCH_VV_THRESHOLD:
                launched = True
            if accel_total_g is not None and accel_total_g > LAUNCH_ACCEL_G_THRESHOLD:
                launched = True
            if launched:
                self.set_flight_phase("launched")
            return

        # launched -> burnout (افت شتاب کل = خاموش شدن موتور)
        if self.flight_phase == "launched":
            if accel_total_g is not None and accel_total_g < BURNOUT_ACCEL_G_THRESHOLD:
                self.set_flight_phase("burnout")
                # نمایش «پایان رانش» فقط ۱ ثانیه، سپس «در حال صعود»
                self._burnout_timer = QTimer()
                self._burnout_timer.setSingleShot(True)
                self._burnout_timer.timeout.connect(self._finish_burnout_display)
                self._burnout_timer.start(1000)
            return

        # burnout: منتظر تایمر ۱ ثانیه‌ای می‌مانیم؛ اما اگر زودتر شروع به سقوط
        # کرد (سرعت عمودی نزدیک صفر یا منفی)، بلافاصله وارد صعود/اوج می‌شویم
        if self.flight_phase == "burnout":
            return

        # ascent -> apogee (سرعت عمودی نزدیک صفر = رسیدن به اوج)
        if self.flight_phase == "ascent":
            if vv is not None and vv <= APOGEE_VV_BAND:
                self.set_flight_phase("apogee")
            return

        # apogee -> descent / chute_fail (شروع سقوط)
        if self.flight_phase == "apogee":
            fall_speed = abs(vv) if vv is not None else 0.0
            # سقوط بحرانی (چتر باز نشده) بلافاصله هشدار می‌دهد -- ایمنی مقدم است
            if vv is not None and vv < DESCENT_VV_THRESHOLD and fall_speed >= CHUTE_FAIL_SPEED:
                self.set_flight_phase("chute_fail")
                return
            # فرود ایمن (چتر باز): «حداکثر ارتفاع» حداقل مدتی نمایش داده شود تا
            # خوانا باشد، سپس «در حال فرود».
            if vv is not None and vv < DESCENT_VV_THRESHOLD:
                if self._apogee_hold_done:
                    self.set_flight_phase("descent")
                elif self._apogee_timer is None:
                    self._apogee_timer = QTimer()
                    self._apogee_timer.setSingleShot(True)
                    self._apogee_timer.timeout.connect(self._finish_apogee_display)
                    self._apogee_timer.start(int(APOGEE_HOLD_SEC * 1000))
            return

        # descent <-> chute_fail + تشخیص فرود
        if self.flight_phase in ("descent", "chute_fail"):
            near_ground = (altitude is not None and altitude <= LANDED_ALT)
            still = (vv is None or abs(vv) <= LANDED_VV)
            if near_ground and still:
                self.set_flight_phase("landed")
                # فرود: آغاز شمارش ۱۰ ثانیه سکون کامل؛ پس از آن ثبت متوقف و
                # فایل «داده‌های زنده» ذخیره می‌شود. پایش زندهٔ تله‌متری/
                # جی‌پی‌اس/باتری قطع نمی‌شود -- در حالت واقعی هنگام یافتن
                # راکت همچنان به سیگنال‌ها نیاز است.
                self._landed_save_timer = QTimer()
                self._landed_save_timer.setSingleShot(True)
                self._landed_save_timer.timeout.connect(self._on_landed_still_elapsed)
                self._landed_save_timer.start(int(LANDED_STILL_SEC * 1000))
                return
            if vv is not None:
                fall_speed = abs(vv)
                if self.flight_phase == "descent" and fall_speed >= CHUTE_FAIL_SPEED:
                    self.set_flight_phase("chute_fail")
                elif self.flight_phase == "chute_fail" and fall_speed < CHUTE_OK_SPEED:
                    # چتر با تأخیر باز شد -- بازگشت به فرود ایمن
                    self.set_flight_phase("descent")

    def _finish_burnout_display(self):
        """پس از ۱ ثانیه نمایش «پایان رانش»، وضعیت به «در حال صعود» می‌رود."""
        if self.flight_phase == "burnout":
            self.set_flight_phase("ascent")

    def _finish_apogee_display(self):
        """پس از مدت نمایش «حداکثر ارتفاع»، اجازهٔ گذار به «در حال فرود» صادر
        می‌شود (گذار واقعی در به‌روزرسانی بعدی تله‌متری با سرعت سقوط انجام می‌شود)."""
        self._apogee_hold_done = True
        if self.flight_phase == "apogee":
            self.set_flight_phase("descent")

    def load_flight_csv(self, path: str, *, archive: bool = True) -> bool:
        """بارگذاری فایل CSV دانلودشده از کامپیوتر پرواز و اجرای تحلیل خودکار.

        پس از تحلیل موفق، بستهٔ خام (CSV + مشخصات مأموریت) در پوشهٔ
        «گزارش‌های خام» ذخیره می‌شود تا بعداً بتوان همان پرواز را بازتحلیل کرد.
        ``archive=False`` هنگام باز کردن از خودِ آرشیو خام است تا کپی تکراری ساخته نشود.
        """
        if not os.path.exists(path):
            return False
        df = pd.read_csv(path)
        df.columns = [c.strip() for c in df.columns]
        self._last_flight_csv_path = os.path.abspath(path)
        self.flight_df = df
        if archive:
            try:
                self.save_raw_flight(source_csv=path)
            except Exception:
                pass
        self._apply_analyzed_df(df)
        return True

    def _apply_analyzed_df(self, df: pd.DataFrame):
        """تحلیل تازه از روی DataFrame خام با فرمول‌های فعلی برنامه."""
        self.flight_df = df
        from core.analysis import FlightAnalyzer
        analyzer = FlightAnalyzer(df, self.mission, self.motor)
        self.events = analyzer.detect_events()
        self.analysis_results = analyzer.full_analysis(self.events)
        self.analysis_ready.emit(self.analysis_results)

    def get_launch_altitude(self) -> float:
        """ارتفاع محل پرتاب از سطح دریا.

        اولویت با مقدار خوانده‌شده از GPS است (وقتی ماژول GPS در آینده نصب و
        متصل شود)؛ در غیر این صورت مقدار دستی ثبت‌شده در اطلاعات مأموریت
        استفاده می‌شود. این تابع مرکز واحدی است تا هر بخش از برنامه که به
        ارتفاع محل پرتاب نیاز دارد (مثلاً محاسبهٔ نسبت انبساط بهینهٔ نازل)
        بعداً بدون تغییر در آن بخش‌ها به‌صورت خودکار از GPS بهره‌مند شود.
        """
        if self.gps_altitude_m is not None:
            return self.gps_altitude_m
        return self.mission.altitude_msl

    # ------------------------------------------------------------------
    # آرشیو دادهٔ خام پروازها (پوشهٔ «گزارش‌های خام»)
    # ------------------------------------------------------------------
    def save_raw_flight(self, source_csv: Optional[str] = None, label: str = "") -> str:
        """ذخیره/به‌روزرسانی بستهٔ خام پرواز فعلی در پوشهٔ «گزارش‌های خام»."""
        if self.flight_df is None:
            return ""
        from core.raw_archive import save_raw_flight as _save
        src = source_csv or getattr(self, "_last_flight_csv_path", None)
        return _save(
            dest_root=get_raw_flights_dir(),
            df=self.flight_df,
            mission=self.mission,
            motor=self.motor,
            sensor_models=self.sensor_models,
            prediction=self.prediction_snapshot,
            source_csv=src,
            label=label,
        )

    def save_to_archive(self, label: str = "") -> str:
        """سازگاری با نام قدیمی -- همان save_raw_flight."""
        return self.save_raw_flight(label=label)

    def list_archive(self) -> list:
        """لیست پروازهای خام (پوشهٔ گزارش‌های خام + آرشیو قدیمی)."""
        from core.raw_archive import list_raw_flights
        return list_raw_flights()

    def load_from_archive(self, name_or_path: str) -> bool:
        """بازکردن یک پرواز خام و اجرای دوبارهٔ تحلیل با فرمول‌های فعلی."""
        from core.raw_archive import (
            dataclass_from_dict, load_raw_flight, resolve_raw_flight,
        )
        path = resolve_raw_flight(name_or_path)
        if not path:
            return False
        try:
            bundle = load_raw_flight(path)
        except Exception:
            return False
        if not bundle or bundle.get("df") is None:
            return False

        mission = dataclass_from_dict(MissionInfo, bundle.get("mission"))
        if mission is not None:
            self.mission = mission
            self.mission_changed.emit()
        motor = dataclass_from_dict(MotorInfo, bundle.get("motor"))
        if motor is not None:
            self.motor = motor
            self.motor_changed.emit()
        models = bundle.get("sensor_models")
        if isinstance(models, dict) and models:
            self.sensor_models.update(models)
        if bundle.get("has_manifest"):
            self.prediction_snapshot = bundle.get("prediction")

        csv_path = bundle.get("csv_path")
        if csv_path:
            self._last_flight_csv_path = csv_path
        self._apply_analyzed_df(bundle["df"])
        return True


data_manager = DataManager()
