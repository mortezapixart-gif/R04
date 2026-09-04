# -*- coding: utf-8 -*-
"""
core/rocket_physics.py
------------------------
موتور فیزیکی «حالت آموزشی»: شبیه‌سازی واقعیِ پرتاب یک راکت شکری (KNSU/KNDX)
از لحظهٔ پرتاب تا فرود، بر اساس پارامترهایی که کاربر خودش وارد می‌کند.

هدف آموزشی: کاربر با جابه‌جا کردن پارامترها (میزان سوخت، وزن، زاویهٔ پرتاب،
مشخصات نازل، قطر چتر) باید *واقعاً* نتیجهٔ پرواز را تغییر ببیند -- اوج،
سرعت، شتاب، مسیر و گزارش نهایی. انتخاب ماژول‌ها هم نتیجه را در «داده‌ها»
عوض می‌کند (ستون‌های CSV، تله‌متری زنده، رادار GPS، گزارش)؛ اما وزن راکت
دوباره محاسبه نمی‌شود چون وزن کل واردشده از قبل کامل است.

مدل موتور جامد سوختی (روابط استاندارد موشک‌سازی آماتور):
    ṁ (دبی جرمی)  = Pc·At / c*      فشار محفظه × سطح گلوگاه / سرعت صوت مؤثر
    t_سوزش         = m_p / ṁ         گلوگاه بزرگ‌تر → سوختن سریع‌تر/رانش بیشتر
    Cf (ضریب رانش) = رابطهٔ ایزنتروپیک بر اساس Ae/At و فشار محیط محل پرتاب
    I کل           = m_p · c* · Cf   سوخت بیشتر → ضربهٔ بیشتر؛ نازل بد → ضربهٔ کمتر
    T میانگین      = Cf · Pc · At

مدل پرواز (2-DOF نقطه‌ای + گرانش‌چرخش):
    - رانش در جهت محور راکت (روی ریل: زاویهٔ پرتاب؛ پس از خروج از ریل:
      مماس بر مسیر -- Gravity Turn)، درگ جو در خلاف جهت سرعت
    - جو استاندارد ISA (چگالی/فشار/دما بر اساس ارتفاع محل پرتاب)
    - کاهش جرم در حین سوزش سوخت
    - باز شدن چتر ۲ ثانیه پس از اوج؛ نرخ نزول از تعادل درگِ چتر
    - اگر چتر نباشد: سقوط آزاد تا سرعت حد (بسته به وزن/قطر/Cd، معمولاً
      حدود ۸۰ تا ۱۵۰ m/s برای راکت ۸۰mm کلاس ۳ kg) -- بنر «چتر باز نشده»

این ماژول **هیچ وابستگی‌ای به Qt ندارد** (فقط stdlib) تا در تست
خودکار بدون نمایشگر هم قابل اجرا باشد. کلاس RocketFlightSimulator (پاسخ‌دهندهٔ
پروتکل متنی فریمور) هم همین‌جاست و داده‌های خود را فقط از payload دستور
SET_MISSION می‌گیرد، نه مستقیماً از data_manager.
"""
from __future__ import annotations

import csv
import json
import math
import random
import time
from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional

# ============================================================================
# ثابت‌های فیزیکی
# ============================================================================
G0 = 9.80665                 # شتاب گرانش (m/s²)
K_GAS = 1.15                 # نسبت گرمای ویژهٔ گازهای احتراق سوخت شکری
C_STAR = 890.0               # سرعت صوت مؤثر g* سوخت شکری KNSU/KNDX (m/s)
NOZZLE_EFFICIENCY = 0.95     # افت راندمان نازل (اصطکاک/واگرایی/خنکایش)
BODY_CD = 0.6                # ضریب درگ بدنهٔ راکت معمول آماتور (بدون چتر) -- مرجع: مخروط اویو
# ضریب اصلاح Cd بدنه بر حسب شکل مخروط سر (نسبت به اویو = ۱٫۰).
# مقادیر آموزشی بر پایهٔ جداول درگ مخروط (NASA-TR-R411 / Barrowman) برای
# پرواز زیرصوت؛ اویو بهترین مصالحه، تخت بدترین.
NOSE_CD_FACTOR = {
    "اویو": 1.00,      # Ogive -- مرجع (رایج‌ترین در راکت‌های آماتور)
    "مخروطی": 1.12,    # Cone -- موج ضربه‌ای تیزتر روی نوک
    "نیم‌کره": 0.85,   # Rounded/Elliptical -- کم‌درگ‌ترین در سرعت پایین
    "تخت": 1.45,       # Blunt -- درگ بسیار زیاد (مثل لولهٔ بریده)
}
CHUTE_CD = 1.5               # ضریب درگ چتر تخت (Flat/Annular)
SEA_LEVEL_PRESSURE = 101325.0   # Pa
SEA_LEVEL_TEMP_K = 288.15       # K
LAPSE_RATE = 0.0065             # K/m (تروپوسفر ISA)
AIR_GAS_CONSTANT = 287.05        # J/(kg·K)
CHUTE_DEPLOY_DELAY_SEC = 2.0     # چتر ۲ ثانیه پس از اوج باز می‌شود
CHUTE_INFLATE_SEC = 0.3          # زمان پُر شدن چتر -- درگ طی آن خطی از صفر به کامل می‌رسد
WIND_SPEED_MS = 3.0             # باد افقی فرضی محل پرتاب (سمتْ تصادفی)
MAX_FLIGHT_SEC = 600.0           # محافظ حلقهٔ انتگرال‌گیری

# زمان‌بندی‌های کوتاه‌شدهٔ حالت آموزشی (چک‌لیست داشبورد)
DEMO_HEALTH_CHECK_DURATION_SEC = 6
DEMO_CALIB_DURATION_SEC = 8

# زمان‌بندی تله‌متری زندهٔ فشرده
DEMO_PAD_HOLD_SEC = 10.0        # مکث روی سکو پس از ARM -- ۱۰ ثانیه بعد از مرحلهٔ ۳، پرتاب فرضی خودکار
LIVE_TARGET_SEC = 32.0          # کل پرواز در حدود این ثانیه‌های واقعی پخش می‌شود
LIVE_SPEED_MIN, LIVE_SPEED_MAX = 1.0, 15.0

# محل پرتاب فرضیِ پیش‌فرض: سمنان (کانون علوم و فناوری‌های نوین ایران)
SEMNAN_LAT = 35.5769
SEMNAN_LON = 53.3961
SEMNAN_ELEVATION_M = 1130.0

# ============================================================================
# معنای «انتخاب ماژول» در فرم سنسورها: فقط تعیین می‌کند کدام داده‌ها ساخته
# می‌شوند (ستون CSV/تله‌متری/رادار/گزارش). وزن ماژول‌ها دوباره به راکت اضافه
# نمی‌شود -- «وزن کل» واردشده در فرم مأموریت از قبل وزن کامل راکت با همهٔ
# تجهیزات است (هم در حالت آزمایشی، هم واقعی).
# ============================================================================
UNSELECTED_VALUES = {"انتخاب نشده", "نصب نشده"}


def is_selected(model_name: str) -> bool:
    """آیا این مدل ماژول به‌معنی «نصب‌شده روی راکت» است؟"""
    return bool(model_name) and model_name.strip() not in UNSELECTED_VALUES


# ============================================================================
# جو استاندارد ISA
# ============================================================================
def isa_pressure(altitude_m: float) -> float:
    """فشار جو (Pa) در ارتفاع داده‌شده از سطح دریا."""
    h = max(0.0, min(altitude_m, 11000.0))
    return SEA_LEVEL_PRESSURE * (1 - LAPSE_RATE * h / SEA_LEVEL_TEMP_K) ** 5.25588


def isa_temperature_k(altitude_m: float) -> float:
    h = max(0.0, min(altitude_m, 11000.0))
    return SEA_LEVEL_TEMP_K - LAPSE_RATE * h


def isa_density(altitude_m: float) -> float:
    """چگالی هوا (kg/m³) از معادلهٔ حالت گاز کامل."""
    return isa_pressure(altitude_m) / (AIR_GAS_CONSTANT * isa_temperature_k(altitude_m))


# ============================================================================
# طراحی موتور (از مشخصات نازل + سوخت)
# ============================================================================
def _gamma_func(k: float) -> float:
    """تابع Γ (Vandenkerckhove) -- ضریب جریان ایزنتروپیک دهانهٔ بحرانی."""
    return math.sqrt(k) * (2.0 / (k + 1.0)) ** ((k + 1.0) / (2.0 * (k - 1.0)))


def _mach_from_area_ratio(area_ratio: float, k: float = K_GAS) -> float:
    """یافتن عدد ماخ خروجی از نسبت انبساط Ae/At (حل عددی دوبخشی فرا-صوت)."""
    def area_ratio_of(m: float) -> float:
        return (1.0 / m) * ((2.0 / (k + 1.0)) * (1.0 + (k - 1.0) / 2.0 * m * m)) ** ((k + 1.0) / (2.0 * (k - 1.0)))

    lo, hi = 1.0001, 12.0
    if area_ratio_of(lo) > area_ratio > 0:
        return 1.0
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if area_ratio_of(mid) < area_ratio:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def thrust_coefficient(area_ratio: float, chamber_pressure_pa: float,
                       ambient_pressure_pa: float, k: float = K_GAS) -> float:
    """ضریب رانش Cf برای نسبت انبساط داده‌شده در فشار محیط داده‌شده.

    Cf = Γ·√(2k/(k-1)·(1-(Pe/Pc)^((k-1)/k))) + (Pe-Pa)/(Pc)·Ae/At
    """
    if area_ratio <= 1.0:
        # دهانهٔ واگرا ندارد (نازل همگرا) -- گاز بدون انبساط کافی به محیط
        # می‌ریزد؛ همان مقدار آموزشی که design_motor برای De≤Dt می‌گذارد.
        return 0.62
    me = _mach_from_area_ratio(area_ratio, k)
    pe = chamber_pressure_pa * (1.0 + (k - 1.0) / 2.0 * me * me) ** (-k / (k - 1.0))
    term1 = _gamma_func(k) * math.sqrt(
        (2.0 * k / (k - 1.0)) * (1.0 - (pe / chamber_pressure_pa) ** ((k - 1.0) / k)))
    term2 = (pe - ambient_pressure_pa) / chamber_pressure_pa * area_ratio
    return max(0.5, term1 + term2)


@dataclass
class MotorDesign:
    """نتیجهٔ طراحی موتور از مشخصات سوخت/نازل کاربر."""
    valid: bool = False
    warnings: List[str] = field(default_factory=list)
    throat_area_m2: float = 0.0
    exit_area_m2: float = 0.0
    area_ratio: float = 0.0            # Ae/At هندسی
    mdot_kg_s: float = 0.0             # دبی جرمی سوخت
    burn_time_s: float = 0.0           # مدت سوزش = m_p/ṁ
    thrust_avg_n: float = 0.0          # رانش میانگین
    total_impulse_n_s: float = 0.0     # ضربهٔ کل = m_p·c*·Cf
    thrust_coefficient: float = 0.0    # Cf مؤثر
    initial_twr: float = 0.0           # نسبت رانش به وزن در لحظهٔ پرتاب

    def thrust_at(self, t: float) -> float:
        """منحنی رانش نرمال‌شده: خیز سریع (~۱۲٪ اول سوزش)، سکو، دنبالهٔ کوتاه."""
        if not self.valid or t <= 0.0:
            return 0.0
        tau = min(t / self.burn_time_s, 1.0) if self.burn_time_s > 0 else 1.0
        # میانگین دقیقِ شکل روی [0,1] با انتگرال‌گیری ذره‌ای (_BURN_SHAPE_MEAN)
        return _burn_shape(tau) / _BURN_SHAPE_MEAN * self.thrust_avg_n


def _burn_shape(tau: float) -> float:
    """شکل واحد منحنی رانش موتور شکری بر حسب کسر مدت سوزش (tau در [0,1]).

    خیز اولیهٔ فشار محفظه، سکوی اصلی سوزش با افت ملایم و دنبالهٔ Tail-off."""
    if tau >= 1.0:
        return 0.0
    if tau < 0.12:                       # خیز فشار محفظه
        return 1.30 * (tau / 0.12)
    if tau < 0.80:                       # سکوی اصلی سوزش
        return 1.30 - 0.22 * (tau - 0.12) / 0.68
    return max(0.0, 1.08 * (1.0 - (tau - 0.80) / 0.20))  # دنباله (Tail-off)


def _shape_mean(f, n: int = 200_001) -> float:
    """میانگین دقیق تابع شکل روی [0,1] با قانون ذوزنقه (انتگرال/طول بازه)."""
    step = 1.0 / (n - 1)
    total = 0.5 * (f(0.0) + f(1.0))
    for i in range(1, n - 1):
        total += f(i * step)
    return total * step


# نرمال‌ساز منحنی رانش: تقسیم بر میانگینِ دقیق شکل تضمین می‌کند
# ∫T dt دقیقاً برابر total_impulse طراحی بماند (قبلاً ثابت تجربی 1.02 بود که
# ضربهٔ تحویلی را ~۲٫۴٪ کم می‌کرد؛ ممیزی 1405-06-11).
_BURN_SHAPE_MEAN = _shape_mean(_burn_shape)


def design_motor(propellant_mass_g: float, chamber_pressure_bar: float,
                 throat_diameter_mm: float, exit_diameter_mm: float,
                 liftoff_mass_kg: float, ambient_pressure_pa: float,
                 divergence_half_angle_deg: float = 15.0) -> MotorDesign:
    """طراحی موتور شکری از ورودی‌های کاربر (همان فیلدهای صفحهٔ مأموریت/نازل).

    divergence_half_angle_deg: زاویهٔ نیم‌رخ دیوارهٔ واگرای نازل (فیلد
    «زاویهٔ واگرا» فرم). تلفات واگرایی نازل مخروطی با ضریب کلاسیک
    λ = (1+cos α)/2 مدل می‌شود؛ چون NOZZLE_EFFICIENCY از قبل تلفاتِ
    نازلِ ۱۵ درجه (استاندارد رایج) را در خود دارد، اینجا فقط انحراف
    «نسبی» از ۱۵ درجه اعمال می‌شود تا دوبار‌شمول نشود: زاویهٔ ۱۵° یعنی
    همان راندمان قبلی، ۳۰° حدود ۵٪ رانش کمتر، ۸° حدود ۱٪ بیشتر."""
    d = MotorDesign()
    mp = max(0.0, propellant_mass_g) / 1000.0
    pc_pa = max(0.0, chamber_pressure_bar) * 1e5
    dt_m = max(0.0, throat_diameter_mm) / 1000.0
    de_m = max(0.0, exit_diameter_mm) / 1000.0

    if mp <= 0:
        d.warnings.append("وزن سوخت صفر است -- موتور کار نمی‌کند.")
    if dt_m <= 0:
        d.warnings.append("قطر گلوگاه نازل صفر است.")
    if de_m <= 0:
        d.warnings.append("قطر خروجی نازل صفر است.")
    if pc_pa <= 0:
        d.warnings.append("فشار محفظه صفر است.")
    if mp > 0 and dt_m > 0 and de_m <= dt_m:
        d.warnings.append("قطر خروجی باید بزرگ‌تر از قطر گلوگاه باشد (نازل دوپهلوی لاول).")
    # (هشدار «وزن کل صفر» را simulate_flight با پیام کامل‌تر می‌دهد)
    if d.warnings and (mp <= 0 or dt_m <= 0 or pc_pa <= 0 or liftoff_mass_kg <= 0):
        return d

    at = math.pi / 4.0 * dt_m * dt_m
    ae = math.pi / 4.0 * de_m * de_m
    d.throat_area_m2 = at
    d.exit_area_m2 = ae
    d.area_ratio = ae / at if at > 0 else 0.0

    # نازل همگرا (خروجی ≤ گلوگاه): بدون بخش واگرا فقط ~۴۰٪ راندمان یک
    # نازل لاوال درست (گاز بدون انبساط کافی به محیط می‌ریزد) -- عمداً ضعیف
    if de_m <= dt_m:
        cf = 0.62
        d.warnings.append("نازل بدون بخش واگرا: راندمان رانش به‌شدت افت کرده است.")
    else:
        alpha = math.radians(min(max(divergence_half_angle_deg, 5.0), 45.0))
        div_loss = (1.0 + math.cos(alpha)) / 2.0           # λ(α)
        div_ref = (1.0 + math.cos(math.radians(15.0))) / 2.0  # λ(15°) -- مرجعِ 0.95
        cf = NOZZLE_EFFICIENCY * (div_loss / div_ref) * thrust_coefficient(d.area_ratio, pc_pa, ambient_pressure_pa)
    d.thrust_coefficient = cf

    d.mdot_kg_s = pc_pa * at / C_STAR
    d.burn_time_s = mp / d.mdot_kg_s if d.mdot_kg_s > 0 else 0.0
    d.total_impulse_n_s = mp * C_STAR * cf
    d.thrust_avg_n = d.total_impulse_n_s / d.burn_time_s if d.burn_time_s > 0 else 0.0
    d.initial_twr = d.thrust_avg_n / (liftoff_mass_kg * G0) if liftoff_mass_kg > 0 else 0.0
    d.valid = d.thrust_avg_n > 0 and d.burn_time_s > 0

    if d.valid:
        if d.initial_twr < 3.0:
            d.warnings.append(
                f"نسبت رانش به وزن پایین است ({d.initial_twr:.1f}) -- راکت ممکن است "
                "با این سرعت اولیه روی ریل پایداری نداشته باشد و هواروک (Weathercock) شود."
            )
        elif d.initial_twr > 15:
            d.warnings.append(
                f"نسبت رانش به وزن بسیار بالاست ({d.initial_twr:.1f}) -- شتاب و فشار "
                "دینامیکی برای بدنه/ماژول‌ها خطرناک است."
            )
        if d.burn_time_s > 8:
            d.warnings.append("مدت سوزش طولانی است (گلوگاه کوچک) — زمان پرواز بیشتر می‌شود و راکت مدت طولانی‌تری در معرض باد قرار می‌گیرد؛ احتمال انحراف از مسیر عمودی بالاتر می‌رود.")
    return d


# ============================================================================
# شبیه‌سازی کامل پرواز
# ============================================================================
@dataclass
class SimParams:
    """همهٔ ورودی‌های شبیه‌سازی -- دقیقاً همان فیلدهایی که کاربر وارد می‌کند."""
    total_mass_kg: float = 3.2          # وزن کامل پرتاب (بدنه+موتور+سوخت+تجهیزات)
    propellant_mass_g: float = 350.0
    body_diameter_m: float = 0.08
    body_length_m: float = 0.0          # طول کامل راکت از نوک تا انتها
    body_section_length_m: float = 0.0  # بخش استوانه‌ای، از طراحی
    nose_length_m: float = 0.0
    nose_cone: str = "اویو"             # شکل مخروط سر -- ضریب Cd در NOSE_CD_FACTOR
    # هندسهٔ باله و نقاط آیرودینامیکی؛ صفر/None یعنی مدل دستی با پیش‌فرض نرمال
    fin_shape: str = "ذوزنقه‌ای"
    fin_count: int = 0
    fin_root_chord_m: float = 0.0
    fin_tip_chord_m: float = 0.0
    fin_span_m: float = 0.0
    fin_sweep_m: float = 0.0
    cp_from_nose_m: Optional[float] = None
    cg_from_nose_m: Optional[float] = None
    stability_margin_calibers: Optional[float] = None
    aero_defaulted: bool = True
    design_source: str = "manual"
    launch_angle_deg: float = 90.0
    launch_azimuth_deg: float = 0.0   # سمت پرتاب (۰ = شمال، ۹۰ = شرق) -- فقط مسیر GPS/بازپخش
    altitude_msl_m: float = SEMNAN_ELEVATION_M
    throat_diameter_mm: float = 8.0
    exit_diameter_mm: float = 20.0
    chamber_pressure_bar: float = 40.0
    divergence_angle_deg: float = 15.0  # زاویهٔ واگرای نازل -- تلفات λ=(1+cosα)/2
    chute_diameter_m: float = 1.2       # ۰ = بدون چتر (سقوط آزاد!)
    sensor_models: Dict[str, str] = field(default_factory=dict)
    wind_speed_ms: float = WIND_SPEED_MS   # ۰ = بدون باد (برد افقیِ خالص)
    seed: int = 42

    @property
    def liftoff_mass_kg(self) -> float:
        """وزن پرتاب = همان «وزن کل» واردشدهٔ کاربر. وزن ماژول‌های سنسور
        دوباره اضافه نمی‌شود (عدد فرم از قبل وزن کامل راکت با تجهیزات است)."""
        return self.total_mass_kg


@dataclass
class FlightResult:
    """خروجی شبیه‌سازی: ردیف‌های CSV + رویدادها + خلاصه + هشدارها."""
    rows: List[Dict] = field(default_factory=list)
    # مسیر خام برای درون‌یابی تله‌متری زنده (مستقل از اینکه کدام سنسورها نصب‌اند)
    track_t: List[float] = field(default_factory=list)
    track_alt: List[float] = field(default_factory=list)
    track_vv: List[float] = field(default_factory=list)
    track_acc: List[float] = field(default_factory=list)
    track_pitch: List[float] = field(default_factory=list)  # زاویهٔ مسیر (درجه از افق)
    summary: Dict = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    @property
    def duration(self) -> float:
        return self.summary.get("flight_time_s", 0.0)


def _thrust_dir(vx: float, vy: float, angle_rad: float) -> tuple:
    """جهت محور راکت: روی ریل (سرعت ~۰) زاویهٔ پرتاب؛ سپس مماس بر مسیر."""
    speed = math.hypot(vx, vy)
    if speed < 2.0:
        return math.cos(angle_rad), math.sin(angle_rad)
    return vx / speed, vy / speed


def simulate_flight(params: SimParams) -> FlightResult:
    """انتگرال‌گیری عددی کل پرواز (رانش ← اوج ← چتر ← فرود) + دادهٔ سنسورها."""
    res = FlightResult()
    rng = random.Random(params.seed)
    has_bmp = is_selected(params.sensor_models.get("BMP280", ""))
    has_mpu = is_selected(params.sensor_models.get("MPU6050", ""))
    has_aht = is_selected(params.sensor_models.get("AHT21", ""))
    has_uv = is_selected(params.sensor_models.get("UV", ""))
    has_gps = is_selected(params.sensor_models.get("GPS", ""))

    pa_launch = isa_pressure(params.altitude_msl_m)
    motor = design_motor(params.propellant_mass_g, params.chamber_pressure_bar,
                         params.throat_diameter_mm, params.exit_diameter_mm,
                         params.liftoff_mass_kg, pa_launch,
                         divergence_half_angle_deg=getattr(params, "divergence_angle_deg", 15.0))
    res.warnings.extend(motor.warnings)
    if params.chute_diameter_m <= 0:
        res.warnings.append("قطر چتر صفر است -- راکت بدون سیستم بازیابی سقوط می‌کند!")
    if not has_bmp:
        res.warnings.append("بارومتر (BMP280) انتخاب نشده -- ارتفاع/فشار ثبت نخواهد شد.")
    if not is_selected(params.sensor_models.get("SD", "")):
        res.warnings.append("کارت حافظه (SD) انتخاب نشده -- دادهٔ پرواز روی راکت ذخیره نمی‌شود.")

    # ---------------- گارد ورودی نامعتبر (جلوگیری از تقسیم بر جرم صفر) ----------------
    # در نصب تازهٔ برنامه ممکن است «وزن کل» هنوز وارد نشده باشد (صفر) یا سوخت
    # از وزن کل راکت بیشتر شده باشد -- به‌جای کرش، نتیجهٔ نامعتبر + هشدار
    # برمی‌گردانیم (کارت پیش‌بینی صفحهٔ مأموریت همان هشدار را زرد نشان می‌دهد).
    bad_mass = params.liftoff_mass_kg <= 0.0
    bad_fuel = params.propellant_mass_g / 1000.0 >= params.liftoff_mass_kg > 0.0
    if bad_mass:
        res.warnings.append("وزن کل راکت صفر است -- وزن کامل پرتابه را در صفحهٔ مأموریت وارد کنید.")
    if bad_fuel:
        res.warnings.append("وزن سوخت نباید از وزن کل راکت بیشتر یا مساوی آن باشد!")
    if bad_mass or bad_fuel:
        res.summary = {
            "valid": False,
            "apogee_m": 0.0,
            "apogee_time_s": None,
            "burn_time_s": motor.burn_time_s,
            "thrust_avg_n": motor.thrust_avg_n,
            "total_impulse_n_s": motor.total_impulse_n_s,
            "thrust_coefficient": motor.thrust_coefficient,
            "area_ratio": motor.area_ratio,
            "initial_twr": motor.initial_twr,
            "max_speed_ms": 0.0,
            "max_accel_g": 0.0,
            "chute_deploy_t": None,
            "flight_time_s": 0.0,
            "landing_speed_ms": 0.0,
            "has_chute": params.chute_diameter_m > 0,
            "range_m": 0.0,
            "liftoff_mass_kg": params.liftoff_mass_kg,
            "body_length_m": params.body_length_m,
            "fin_planform_m2": 0.0,
            "effective_drag_area_m2": 0.0,
            "cp_from_nose_m": getattr(params, "cp_from_nose_m", None),
            "cg_from_nose_m": getattr(params, "cg_from_nose_m", None),
            "stability_margin_calibers": getattr(params, "stability_margin_calibers", None),
            "motor": motor,
        }
        return res

    m0 = params.liftoff_mass_kg
    mp = max(0.0, params.propellant_mass_g) / 1000.0
    body_area = math.pi / 4.0 * max(params.body_diameter_m, 0.01) ** 2
    # سطح مؤثر باله‌ها از همان هندسهٔ منتقل‌شده محاسبه می‌شود. در مسیر
    # دستی صفر است و مدل قدیمیِ فقط-بدنه حفظ می‌شود.
    fin_shape = str(getattr(params, "fin_shape", "ذوزنقه‌ای") or "ذوزنقه‌ای")
    root_chord = max(0.0, getattr(params, "fin_root_chord_m", 0.0))
    tip_chord = max(0.0, getattr(params, "fin_tip_chord_m", 0.0))
    if fin_shape == "مثلثی":
        tip_chord = 0.0
    elif fin_shape == "مستطیلی":
        tip_chord = root_chord
    fin_planform = (max(0, int(getattr(params, "fin_count", 0)))
                    * max(0.0, (root_chord + tip_chord) / 2.0)
                    * max(0.0, getattr(params, "fin_span_m", 0.0)))
    rocket_length = max(0.0, getattr(params, "body_length_m", 0.0))
    if rocket_length <= 0:
        rocket_length = max(0.0, getattr(params, "body_section_length_m", 0.0)) + max(0.0, getattr(params, "nose_length_m", 0.0))
    slenderness = rocket_length / max(params.body_diameter_m, 0.01)
    # طول و عقب‌رفتگی باله فقط اطلاعات نمایشی نیستند: سطح خیس‌شدهٔ تقریبی
    # بدنه و درگ پایهٔ باله را کمی اصلاح می‌کنند.
    body_length_factor = 1.0 + 0.012 * min(18.0, max(0.0, slenderness - 8.0))
    sweep_ratio = max(0.0, getattr(params, "fin_sweep_m", 0.0)) / max(root_chord, 0.001)
    fin_drag_factor = 1.0 + 0.06 * min(2.0, sweep_ratio)
    aero_area = body_area * body_length_factor + 0.70 * fin_planform * fin_drag_factor
    chute_area = math.pi / 4.0 * max(params.chute_diameter_m, 0.0) ** 2
    angle_rad = math.radians(max(0.0, min(params.launch_angle_deg, 90.0)))

    stability_margin = getattr(params, "stability_margin_calibers", None)
    if stability_margin is None:
        cp = getattr(params, "cp_from_nose_m", None)
        cg = getattr(params, "cg_from_nose_m", None)
        stability_margin = ((cp - cg) / params.body_diameter_m
                            if cp is not None and cg is not None and params.body_diameter_m > 0
                            else 1.5)
    if stability_margin < 0:
        res.warnings.append(
            f"هشدار پایداری: حاشیه {stability_margin:.2f} کالیبر و CP جلوتر از CG است؛ "
            "پیش‌بینی مسیر برای پرواز پایدار معتبر نیست.")
    elif stability_margin < 1.0:
        res.warnings.append(
            f"حاشیهٔ پایداری فقط {stability_margin:.2f} کالیبر است؛ باد و تلاطم می‌تواند مسیر را منحرف کند.")
    elif stability_margin > 2.5:
        res.warnings.append(
            f"حاشیهٔ پایداری {stability_margin:.2f} کالیبر است؛ راکت بیش‌پایدار و در باد حساس‌تر است.")
    # ناپایداری/حاشیهٔ خیلی کم، افزایش کوچکی در درگ ناشی از انحراف بدنه
    # دارد؛ این تنها اصلاح مسیر مدل ساده است و مقدار هندسی CP/CG نیز در
    # هشدار و خلاصهٔ پیش‌بینی ثبت می‌شود.
    stability_drag_factor = 1.0 + max(0.0, 0.6 - stability_margin) * 0.08

    # باد افقی ثابت: در درگ به‌صورت سرعت نسبی هوا وارد می‌شود
    # (v_rel = v − v_wind) تا راکت زیر چتر به سرعت باد میل کند.
    # جهت باد نسبت به «سمت پرتاب» در بازهٔ ±۶۰ درجه و قطعی (از seed) انتخاب
    # می‌شود تا در حالت آموزشی باد همیشه راکت را به همین سمتِ پرتاب می‌برد
    # (برگشتِ ناگهانی به پشتِ پرتابگاه غیرطبیعی بود؛ ممیزی 1405-06-13).
    wind_rel = rng.uniform(-math.pi / 3.0, math.pi / 3.0)
    wind_x = params.wind_speed_ms * math.cos(wind_rel)

    dt = 0.02
    t = 0.0
    x = y = 0.0
    vx = vy = 0.0
    m = m0
    # بایاس GPS: درفتِ چندمتریِ سینوسی و بسیار آهسته (نویز سفیدِ نمونه‌به‌نمونه
    # مسیر و بازپخش را زیکزاکی می‌کرد -- ممیزی 1405-06-13)
    gps_phase_e = rng.uniform(0.0, 2 * math.pi)
    gps_phase_n = rng.uniform(0.0, 2 * math.pi)
    gps_period_e = rng.uniform(40.0, 70.0)
    gps_period_n = rng.uniform(45.0, 80.0)
    climbed = False                # راکت باید واقعاً بالا رفته باشد (اوایل سوزش، رانش لحظه‌ای از وزن کمتر است و vy چند صدم ثانیه منفی می‌شود -- نباید همان‌جا «اوج» تشخیص داده شود!)
    apogee_alt = apogee_t = None
    chute_t = None
    landed_t = None
    landing_speed = 0.0
    max_speed = 0.0
    max_accel_g = 0.0
    impulse_delivered = 0.0  # برای کاهش جرم متناسب با رانش تحویلی (نه خطی با زمان)
    rows_rate = 0.1          # CSV با ۱۰ هرتز
    next_row_t = 0.0

    def ambient(alt_agl: float) -> float:
        return isa_density(params.altitude_msl_m + alt_agl)

    while t < MAX_FLIGHT_SEC:
        # ---------------- محاسبهٔ نیروها ----------------
        speed = math.hypot(vx, vy)
        thrust = motor.thrust_at(t) if motor.valid else 0.0
        rho = ambient(max(y, 0.0))

        chute_open = chute_t is not None and t >= chute_t
        nose_factor = NOSE_CD_FACTOR.get(getattr(params, "nose_cone", "اویو"), 1.0)
        if chute_open:
            # پُر شدن تدریجی چتر (Snatch → Inflate): درگ طی CHUTE_INFLATE_SEC
            # خطی از صفر به سطح کامل می‌رسد -- پرشِ لحظه‌ایِ درگ در یک گاپ
            # انتگرال‌گیری، ضربهٔ غیرواقعی ده‌ها g می‌ساخت که سنسور واقعی
            # (نمونه‌برداری ۱۰ هرتز) هرگز نمی‌بیند (ممیزی 1405-06-12).
            inflate = min(1.0, (t - chute_t) / CHUTE_INFLATE_SEC)
            drag_area = aero_area + inflate * chute_area
            drag_cd = CHUTE_CD
        else:
            drag_area, drag_cd = aero_area, BODY_CD * nose_factor * stability_drag_factor
        # درگ روی سرعت نسبی نسبت به هوا (باد افقی). بدون این، باد به‌صورت
        # شتاب ثابت سرعت افقی را بی‌کران زیاد می‌کرد.
        vrx, vry = vx - wind_x, vy
        speed_rel = math.hypot(vrx, vry)
        drag = 0.5 * rho * speed_rel * speed_rel * drag_cd * drag_area
        rdx = (vrx / speed_rel) if speed_rel > 0 else 0.0
        rdy = (vry / speed_rel) if speed_rel > 0 else 0.0

        dirx, diry = _thrust_dir(vx, vy, angle_rad)
        # شتاب سینماتی جهان: رانش + درگ (خلاف v_rel) + گرانش
        ax = (thrust * dirx - drag * rdx) / m
        ay = (thrust * diry - drag * rdy) / m - G0

        # روی ریل/زمین: تا وقتی مؤلفهٔ عمودی رانش از وزن کمتر است، نیروی
        # واکنش ریل راکت را نگه می‌دارد -- شتاب سینماتی صفر و نیروی ویژهٔ
        # سنسور +1g رو به بالا (مثل شتاب‌سنج واقعی روی زمین).
        if y <= 0.0 and vy <= 0.0 and thrust * diry <= m * G0:
            ax = ay = 0.0
            vx = vy = 0.0

        # نیروی ویژهٔ سنسور (Specific force = a - g) در چارچوب جهان
        fx, fy = ax, ay + G0
        accel_total = math.hypot(fx, fy)

        # ---------------- ثبت ردیف سنسور ----------------
        if t >= next_row_t - 1e-9:
            # مسیر خام برای تله‌متری زنده (مستقل از ماژول‌های نصب‌شده)
            res.track_t.append(round(t, 2))
            res.track_alt.append(max(y, 0.0))
            res.track_vv.append(vy)
            res.track_acc.append(accel_total)
            res.track_pitch.append(math.degrees(math.atan2(diry, dirx)) if (thrust > 0 or speed > 2)
                                   else math.degrees(angle_rad))
            # بیشینهٔ شتاب بر اساس «همان نمونه‌هایی که سنسور ثبت می‌کند» --
            # تا پیش‌بینی با تحلیل دادهٔ واقعی (۱۰ هرتز) سیب‌به‌سیب قابل
            # مقایسه باشد؛ قلهٔ بین دو نمونه تعریف رسمی ندارد.
            max_accel_g = max(max_accel_g, accel_total / G0)
            pitch = math.degrees(math.atan2(diry, dirx)) if (thrust > 0 or speed > 2) else \
                math.degrees(angle_rad)
            row: Dict = {"Time": round(t, 2)}
            if has_bmp:
                row["Altitude"] = round(max(y, 0.0), 1)
                row["Pressure"] = round(isa_pressure(params.altitude_msl_m + max(y, 0.0)) / 100.0
                                        + rng.uniform(-0.2, 0.2), 1)
                row["Temperature"] = round(isa_temperature_k(params.altitude_msl_m + max(y, 0.0)) - 273.15
                                           + rng.uniform(-0.3, 0.3), 1)
            if has_mpu:
                pr = math.radians(pitch)
                a_mag = accel_total
                row["AccelX"] = round(-a_mag * math.cos(pr) + rng.uniform(-0.06, 0.06), 2)
                row["AccelY"] = round(rng.uniform(-0.06, 0.06), 2)
                row["AccelZ"] = round(a_mag * math.sin(pr) + rng.uniform(-0.06, 0.06), 2)
                # نوسان Pitch/Yaw حین سوزش -- پرتاب غیرعمودی هواروک بدتر می‌کند
                base_osc = 8.0 + max(0.0, (90.0 - params.launch_angle_deg)) * 0.9
                if thrust > 0:
                    gx = rng.gauss(0, base_osc)
                    gy = rng.gauss(0, base_osc)
                    gz = rng.gauss(0, base_osc * 2.0)
                elif chute_open:
                    gx, gy = rng.gauss(0, 4), rng.gauss(0, 4)
                    gz = rng.gauss(0, 6)
                else:
                    gx, gy, gz = rng.gauss(0, 1.5), rng.gauss(0, 1.5), rng.gauss(0, 3)
                row["GyroX"], row["GyroY"], row["GyroZ"] = (round(gx, 1), round(gy, 1), round(gz, 1))
                row["Temperature_MPU"] = round(
                    (isa_temperature_k(params.altitude_msl_m + max(y, 0.0)) - 273.15)
                    + 8.0 * (1 - math.exp(-t / 40.0)) + rng.uniform(-0.3, 0.3), 1)
            if has_aht:
                bmp_t = isa_temperature_k(params.altitude_msl_m + max(y, 0.0)) - 273.15
                row["Temperature_AHT"] = round(bmp_t + 0.3 + rng.uniform(-0.4, 0.4), 1)
                row["Humidity"] = round(max(0.0, min(100.0,
                    22.0 - max(y, 0.0) * 0.006 + rng.uniform(-0.8, 0.8))), 1)
            if has_uv:
                row["UV_Index"] = round(max(0.0, 6.5 + max(y, 0.0) * 0.0009
                                            + rng.uniform(-0.3, 0.3)), 1)
            if has_gps:
                # مسیر بر اساس «منطق پرتاب»: x جابه‌جایی در صفحهٔ پرتاب است و
                # با زاویهٔ سمت (launch_azimuth) روی شرق/شمال تصویر می‌شود؛
                # y هم فقط ارتفاع است (نه شمال).
                az = math.radians(params.launch_azimuth_deg)
                east_m = x * math.sin(az)
                north_m = x * math.cos(az)
                lat, lon = _xy_to_latlon(east_m, north_m, params.altitude_msl_m)
                # بایاس GPS: درفت سینوسی نرم (±۲ متر) -- بدون پرش بین نمونه‌ها
                gps_err_e = 2.0 * math.sin(2 * math.pi * t / gps_period_e + gps_phase_e)
                gps_err_n = 2.0 * math.sin(2 * math.pi * t / gps_period_n + gps_phase_n)
                row["Latitude"] = round(lat + gps_err_n / 111320.0, 6)
                row["Longitude"] = round(lon + gps_err_e / (111320.0 * math.cos(math.radians(SEMNAN_LAT))), 6)
                row["GPS_Altitude"] = round(params.altitude_msl_m + max(y, 0.0), 1)
            frac = min(t / 60.0, 1.0)
            sag = 0.05 + 0.25 * frac + (0.08 if is_selected(params.sensor_models.get("CAMERA", "")) else 0.0)
            row["Voltage"] = round(7.6 - sag, 2)
            res.rows.append(row)
            next_row_t += rows_rate

        # ---------------- انتگرال‌گیری ----------------
        x += vx * dt
        y += vy * dt
        vx += ax * dt
        vy += ay * dt
        if motor.valid and motor.total_impulse_n_s > 0:
            impulse_delivered += thrust * dt
            m = m0 - mp * min(impulse_delivered / motor.total_impulse_n_s, 1.0)
        elif motor.valid and motor.burn_time_s > 0:
            m = m0 - mp * min(t / motor.burn_time_s, 1.0)
        max_speed = max(max_speed, math.hypot(vx, vy))
        t += dt

        if vy > 2.0:
            climbed = True
        if climbed and apogee_t is None and vy < 0:
            apogee_t, apogee_alt = t, max(y, 0.0)
        if (apogee_t is not None and chute_t is None
                and params.chute_diameter_m > 0
                and t - apogee_t >= CHUTE_DEPLOY_DELAY_SEC):
            chute_t = t
        if y <= 0.0 and t > 1.0:
            landed_t = t
            landing_speed = math.hypot(vx, vy)
            break
        if not motor.valid and y <= 0.0 and t > 2.0:
            # موتور معتبر نیست: راکت هرگز پرتاب نمی‌شود
            break

    # راکتی که عملاً از لانچر بیرون نمی‌آید (اوج و برد هر دو < ۱۰ متر) --
    # مثلاً سوخت خیلی کم (۱ گرم): موتور چند میلی‌ثانیه می‌سوزد و TWR میانگین
    # بالا درمی‌آید، ولی ضربهٔ کل آن‌قدر کم است که راکت جابه‌جا نمی‌شود.
    if motor.valid:
        peak = max(apogee_alt or 0.0, abs(x))
        if peak < 10.0:
            res.warnings.append(
                f"پیش‌بینی: راکت حداکثر به {peak:.1f} متر می‌رسد (کمتر از ۱۰ متر) -- "
                "با این نیروی موتور، راکت عملاً از روی لانچر بیرون نمی‌آید!")

    res.summary = {
        "valid": motor.valid,
        "apogee_m": apogee_alt or 0.0,
        "apogee_time_s": apogee_t,
        "burn_time_s": motor.burn_time_s,
        "thrust_avg_n": motor.thrust_avg_n,
        "total_impulse_n_s": motor.total_impulse_n_s,
        "thrust_coefficient": motor.thrust_coefficient,
        "area_ratio": motor.area_ratio,
        "initial_twr": motor.initial_twr,
        "max_speed_ms": max_speed,
        "max_accel_g": max_accel_g,
        "chute_deploy_t": chute_t,
        "flight_time_s": landed_t or t,
        "landing_speed_ms": landing_speed,
        "has_chute": params.chute_diameter_m > 0,
        "range_m": abs(x),
        "liftoff_mass_kg": params.liftoff_mass_kg,
        "body_length_m": params.body_length_m,
        "fin_planform_m2": fin_planform,
        "effective_drag_area_m2": aero_area,
        "cp_from_nose_m": getattr(params, "cp_from_nose_m", None),
        "cg_from_nose_m": getattr(params, "cg_from_nose_m", None),
        "stability_margin_calibers": stability_margin,
        "motor": motor,
    }
    return res


def _xy_to_latlon(x_m: float, y_m: float, _alt: float,
                  lat0: float = SEMNAN_LAT, lon0: float = SEMNAN_LON) -> tuple:
    """تبدیل جابه‌جایی شرقی/شمالی (متر) به عرض/طول جغرافیایی."""
    R = 6371000.0
    # x = شرقی، y = شمالی (در این شبیه‌سازی مسیر در صفحهٔ عمودی است؛
    # جابه‌جایی افقی مسیر + رانش باد چتر را روی محور شرقی می‌گذاریم)
    lon = lon0 + math.degrees(x_m / (R * math.cos(math.radians(lat0))))
    lat = lat0 + math.degrees(y_m / R)
    return lat, lon


def predict_summary(params: SimParams) -> Dict:
    """پیش‌بینی سریع عملکرد برای نمایش زنده در صفحهٔ مأموریت.

    «برد افقی» دو عدد دارد:
      range_m         -- با بادِ تقریبی (جهت باد تصادفی؛ فقط برای تله‌متری زنده)
      range_no_wind_m -- بدون باد: عددِ قطعی و قابل‌توجه کاربر که فقط از
                         زاویهٔ پرتاب + درگ هوا + وزن + رانش موتور می‌آید.
    برد واقعی به باد روز پرتاب (به‌ویژه زیر چتر)، وزن، شکل/اندازهٔ باله‌ها
    و چتر بستگی دارد -- این حدود در tooltip کارت توضیح داده می‌شود."""
    r = simulate_flight(params)
    s = dict(r.summary)
    if params.wind_speed_ms > 0.0:
        nw = simulate_flight(replace(params, wind_speed_ms=0.0))
        s["range_no_wind_m"] = nw.summary.get("range_m", 0.0)
    else:
        s["range_no_wind_m"] = s.get("range_m", 0.0)
    s["warnings"] = list(r.warnings)
    s.pop("motor", None)
    return s


# ============================================================================
# شبیه‌ساز فریمور (پاسخ‌گویی به پروتکل متنی) -- بدون Qt، قابل تست خودکار
# ============================================================================
class RocketFlightSimulator:
    """موتور شبیه‌سازی + پاسخ‌دهندهٔ پروتکل متنی فریمور کامپیوتر پرواز.

    پارامترهای پرواز فقط از طریق دستور SET_MISSION (همان فلوی واقعی) وارد
    می‌شوند تا این کلاس به data_manager/Qt وابسته نباشد.
    """

    def __init__(self):
        self.phase = "pad"                 # pad -> ascending -> landed
        self.launch_time: Optional[float] = None
        self.rng = random.Random(42)
        self._flight: Optional[FlightResult] = None
        self._params: Optional[SimParams] = None
        self._live_speed = 1.0
        self._wind_lat = None
        self._wind_lon = None
        self._landed_at: Optional[float] = None   # لحظهٔ رسیدن به زمین (زمان واقعی)

    def set_live_sensor_models(self, models: Dict[str, str]):
        """همگام‌سازی «انتخاب فعلی ماژول‌ها» با شبیه‌ساز در حالت سکو (pad).

        فلوی کاربر: تست سلامت سنسورها «قبل از» ارسال اطلاعات مأموریت انجام
        می‌شود؛ پس شبیه‌ساز باید بداند الان چه ماژول‌هایی انتخاب شده‌اند تا
        تله‌متری/وضعیت دقیقاً همان‌ها را گزارش کند. این روش فقط مدل ماژول‌ها
        را به‌روز می‌کند (پارامترهای فیزیکی پرواز همچنان فقط از SET_MISSION
        می‌آیند) و پس از مسلح‌سازی (ARM) دیگر اثری ندارد -- پرواز با همان
        چیزی شبیه‌سازی شده که موقع پرتاب روی راکت بوده."""
        if self.phase != "pad":
            return
        if self._params is None:
            self._params = SimParams()
        self._params.sensor_models = dict(models or {})

    # ------------------------------------------------------------------
    def handle_command(self, cmd: str) -> str:
        cmd = cmd.strip()
        if cmd == "STATION_PING":
            return "PONG,STATION,DEMO-2.0"
        if cmd == "LORA_LINK":
            return "ACK:LORA_LINKED"
        if cmd == "ENTER_BOOTLOADER":
            return "ACK:BOOTLOADER"
        if cmd == "STEP1_TEST":
            return "ACK:STEP1_TEST_OK"
        if cmd == "GET_TELEMETRY":
            return self._telemetry_response()
        if cmd == "GET_STATUS":
            return self._status_response()
        if cmd == "GET_REC_STATUS":
            return self._rec_status_response()
        if cmd.startswith("SET_MISSION,"):
            self._handle_set_mission(cmd[len("SET_MISSION,"):])
            return "ACK:MISSION_OK"
        if cmd == "ERASE" or cmd == "FORMAT_SD":
            return "ACK:ERASE_OK"
        if cmd.startswith("CALIB:"):
            return "ACK:CALIB_START"
        if cmd == "CALIB_STATUS":
            return "ACK:CALIB_OK"
        if cmd == "STEP2_START_REC":
            if self._sd_available():
                return "ACK:STEP2_REC_OK"
            return "ERR:NO_SD"
        if cmd == "STEP3_ARM_LAUNCH":
            return self._arm()
        if cmd == "PING":
            return "PONG,DEMO-2.0"
        if cmd in ("DOWNLOAD", "STEP4_DOWNLOAD"):
            if self._flight is not None and self.phase == "landed":
                return "ACK:DOWNLOAD_START"
            if not self._sd_available():
                return "ERR:NO_SD"
            return "ERR:NO_DATA"
        return ""

    # ------------------------------------------------------------------
    def _sd_available(self) -> bool:
        return is_selected((self._params.sensor_models if self._params else {}).get("SD", ""))

    def _handle_set_mission(self, payload_json: str):
        try:
            p = json.loads(payload_json)
        except (ValueError, TypeError):
            return

        def num(key: str, fallback: float) -> float:
            """مقدار عددی payload؛ فقط «نبودِ کلید» به پیش‌فرض برمی‌گردد.

            صفرِ معتبر (مثل ارتفاع ۰ = تراز دریا یا زاویهٔ ۹۰) حفظ می‌شود --
            الگوی «x or default» صفرِ آگاهانهٔ کاربر را می‌بلعد (ممیزی 1405-06-11)."""
            v = p.get(key)
            if v is None or v == "":
                return fallback
            try:
                return float(v)
            except (TypeError, ValueError):
                return fallback

        self._params = SimParams(
            total_mass_kg=num("total_mass", 0.0),
            propellant_mass_g=num("propellant_mass", 0.0),
            # قطر بدنهٔ صفر فیزیکی نیست (راکت بدون بدنه نداریم) و یعنی «فرم
            # پر نشده» -- برخلاف ارتفاع صفر (تراز دریا) که مقدار معتبری است.
            # با پیش‌فرض ۸۰mm همان عددی می‌شود که کارت «پیش‌بینی عملکرد» صفحهٔ
            # مأموریت نشان می‌دهد (m.body_diameter or 0.08) -- این دو مسیر
            # باید همیشه یک عدد بدهند (ممیزی 1405-06-12).
            body_diameter_m=num("body_diameter", 0.08) or 0.08,
            body_length_m=num("body_length", 0.0),
            body_section_length_m=num("body_section_length", 0.0),
            nose_length_m=num("nose_length", 0.0),
            nose_cone=str(p.get("nose_cone") or "اویو"),
            fin_shape=str(p.get("fin_shape") or "ذوزنقه‌ای"),
            fin_count=int(num("fin_count", 0)),
            fin_root_chord_m=num("fin_root_chord", 0.0),
            fin_tip_chord_m=num("fin_tip_chord", 0.0),
            fin_span_m=num("fin_span", 0.0),
            fin_sweep_m=num("fin_sweep", 0.0),
            cp_from_nose_m=num("cp_from_nose", 0.0) if p.get("cp_from_nose") not in (None, "") else None,
            cg_from_nose_m=num("cg_from_nose", 0.0) if p.get("cg_from_nose") not in (None, "") else None,
            stability_margin_calibers=num("stability_margin_calibers", 1.5),
            aero_defaulted=bool(p.get("aero_defaulted", False)),
            design_source=str(p.get("design_source") or "manual"),
            launch_angle_deg=num("launch_angle", 90.0),
            launch_azimuth_deg=num("launch_azimuth", 0.0),
            altitude_msl_m=num("altitude_msl", SEMNAN_ELEVATION_M),
            throat_diameter_mm=num("throat_diameter", 0.0),
            exit_diameter_mm=num("exit_diameter", 0.0),
            chamber_pressure_bar=num("chamber_pressure_bar", 40.0),
            divergence_angle_deg=num("divergence_angle", 15.0),
            chute_diameter_m=num("chute_diameter", 0.0),
            sensor_models=dict(p.get("sensor_models") or {}),
        )

    def _arm(self) -> str:
        """مسلح‌سازی: شبیه‌سازی کامل با پارامترهای دریافتی از SET_MISSION."""
        params = self._params or SimParams()
        self._flight = simulate_flight(params)
        self._params = params
        duration = self._flight.duration
        # فشرده‌سازی زمان برای تله‌متری زنده (کل پرواز در ~۳۰ ثانیهٔ واقعی)
        self._live_speed = min(LIVE_SPEED_MAX, max(LIVE_SPEED_MIN, duration / LIVE_TARGET_SEC))
        self.phase = "ascending"
        self.launch_time = time.time()
        self._landed_at = None
        if not self._flight.summary.get("valid"):
            return "ERR:BAD_MISSION"
        return "ACK:ARMED"

    # ------------------------------------------------------------------
    def _flight_state_at(self, t_sim: float):
        """درون\u200cیابی وضعیت (alt، vv، شتاب کل) در زمان پروازِ t_sim -- از
        مسیر خام شبیه\u200cسازی (نه ستون\u200cهای CSV که به ماژول\u200cهای نصب\u200cشده وابسته\u200cاند)."""
        f = self._flight
        if f is None or not f.track_t:
            return None
        if t_sim <= 0:
            return 0.0, 0.0, G0
        if t_sim >= f.duration:
            return 0.0, 0.0, G0
        n = len(f.track_t)
        pos = t_sim / 0.1
        i = min(int(pos), n - 2)
        frac = max(0.0, min(1.0, pos - i))
        alt = f.track_alt[i] + (f.track_alt[i + 1] - f.track_alt[i]) * frac
        vv = f.track_vv[i] + (f.track_vv[i + 1] - f.track_vv[i]) * frac
        acc = f.track_acc[i] + (f.track_acc[i + 1] - f.track_acc[i]) * frac
        return max(alt, 0.0), vv, acc

    def _telemetry_response(self) -> str:
        p = self._params or SimParams()
        models = p.sensor_models
        has_bmp = is_selected(models.get("BMP280", ""))
        has_mpu = is_selected(models.get("MPU6050", ""))
        has_aht = is_selected(models.get("AHT21", ""))
        has_uv = is_selected(models.get("UV", ""))
        has_gps = is_selected(models.get("GPS", ""))

        if self.phase == "landed" and self._flight is not None:
            # پس از فرود، «زمان پرواز» روی لحظهٔ فرود می‌ماند (تایمر HUD ثابت
            # می‌شود) اما تله‌متری همچنان *زنده* ارسال می‌شود -- در حالت واقعی
            # تا پیدا شدن راکت به سیگنال تله‌متری/GPS/ولتاژ باتری نیاز است.
            # قبلاً این بخش مقادیر را منجمد می‌کرد و مرکز کنترل از کار می‌افتاد.
            duration = max(float(self._flight.duration), 0.0)
            if self._landed_at is None:
                self._landed_at = time.time()
            t_flight = duration + max(0.0, time.time() - self._landed_at)
            s = self._flight_state_at(t_flight)
            state = s if s is not None else (0.0, 0.0, G0)
            # نوفهٔ واقعی سنسور پس از فرود: IMU و بارومتر کمی «نفس می‌کشند»
            state = (max(0.0, state[0] + self.rng.uniform(-0.08, 0.08)),
                     state[1] + self.rng.uniform(-0.06, 0.06),
                     state[2] + self.rng.uniform(-0.06, 0.06))
        elif self.phase != "ascending" or self.launch_time is None:
            state = (0.0, 0.0, G0)
            t_flight = 0.0
        else:
            elapsed = time.time() - self.launch_time
            if elapsed < DEMO_PAD_HOLD_SEC:
                state = (0.0, 0.0, G0)
                t_flight = 0.0
            else:
                t_flight = (elapsed - DEMO_PAD_HOLD_SEC) * self._live_speed
                s = self._flight_state_at(t_flight)
                state = s if s is not None else (0.0, 0.0, G0)
                if t_flight >= self._flight.duration:
                    self._landed_at = time.time()
                    self.phase = "landed"
        alt, vv, acc_total = state

        def bmp(v, fmt="{:.1f}"):
            return fmt.format(v) if has_bmp else ""
        def mpu(v, fmt="{:.2f}"):
            return fmt.format(v) if has_mpu else ""
        def aht(v, fmt="{:.1f}"):
            return fmt.format(v) if has_aht else ""
        def uv(v, fmt="{:.1f}"):
            return fmt.format(v) if has_uv else ""

        pressure = isa_pressure(p.altitude_msl_m + alt) / 100.0 + self.rng.uniform(-0.3, 0.3)
        temp = isa_temperature_k(p.altitude_msl_m + alt) - 273.15 + self.rng.uniform(-0.3, 0.3)
        humidity = max(0.0, min(100.0, 22.0 - alt * 0.006 + self.rng.uniform(-1.0, 1.0)))
        temp_aht = temp + self.rng.uniform(-0.4, 0.4)
        uv_index = max(0.0, 6.5 + alt * 0.0009 + self.rng.uniform(-0.4, 0.4))

        pitch_deg = self._current_pitch_deg(t_flight)
        pr = math.radians(pitch_deg)
        ax = -acc_total * math.cos(pr) + self.rng.uniform(-0.05, 0.05)
        ay = self.rng.uniform(-0.05, 0.05)
        az = acc_total * math.sin(pr) + self.rng.uniform(-0.05, 0.05)

        if has_gps and self._flight is not None and self._flight.rows:
            row = self._flight.rows[min(int(t_flight / 0.1), len(self._flight.rows) - 1)]
            lat, lon = row.get("Latitude", ""), row.get("Longitude", "")
            sats = "9"
            if self._landed_at is not None:
                # راکت روی زمین است؛ گیرنده فقط نویز/دررفتگی جزئی دارد
                try:
                    lat = float(lat) + self.rng.uniform(-0.000003, 0.000003)
                    lon = float(lon) + self.rng.uniform(-0.000003, 0.000003)
                except (TypeError, ValueError):
                    pass
        else:
            lat = lon = ""
            sats = ""

        return (f"TELEM,{t_flight:.2f},{bmp(alt)},{bmp(vv, '{:.2f}')},{bmp(pressure)},"
                f"{bmp(temp)},{mpu(ax)},{mpu(ay)},{mpu(az)},"
                f"{aht(humidity)},{aht(temp_aht)},{uv(uv_index)},"
                f"{lat},{lon},{sats}")

    def _status_response(self) -> str:
        """پاسخ GET_STATUS -- سه فیلد پایانی (جریان، چاشنی ۱، چاشنی ۲) برای
        پنل «سلامت توان آنبرد» HUD اضافه شدند. فریمورهای قدیمی (فقط ۵ فیلد)
        با همین پاسخ کار می‌کنند؛ HUD پارسِ اختیاری دارد و «--» نشان می‌دهد."""
        models = (self._params or SimParams()).sensor_models
        def ok(key):
            return "ok" if is_selected(models.get(key, "")) else "missing"
        battery = 7.6 - (0.3 if is_selected(models.get("CAMERA", "")) else 0.0)
        # مدل سادهٔ جریان: برد پایه + هر سنسور فعال + دوربین
        current_ma = 58.0
        current_ma += 12.0 if is_selected(models.get("BMP280", "")) else 0.0
        current_ma += 9.0 if is_selected(models.get("MPU6050", "")) else 0.0
        current_ma += 6.0 if is_selected(models.get("AHT21", "")) else 0.0
        current_ma += 4.0 if is_selected(models.get("UV", "")) else 0.0
        current_ma += 130.0 if is_selected(models.get("CAMERA", "")) else 0.0
        # مقاومت چاشنی‌ها (Ω): زیر ۱۰ = پیوسته/وصل؛ بالای ۱۰ = باز/قطع
        pyro1, pyro2 = 2.2, 2.4
        return (f"STATUS,{battery:.1f},{ok('BMP280')},{ok('MPU6050')},{ok('SD')},"
                f"{ok('CAMERA')},{current_ma:.0f},{pyro1:.1f},{pyro2:.1f}")

    def _rec_status_response(self) -> str:
        models = (self._params or SimParams()).sensor_models
        parts = []
        for key in ("BMP280", "MPU6050", "AHT21", "UV", "CAMERA", "SD"):
            parts.append(f"{key}={1 if is_selected(models.get(key, '')) else 0}")
        return "REC_STATUS," + ",".join(parts)

    def _current_pitch_deg(self, t_flight: float) -> float:
        """زاویهٔ لحظه‌ای راکت = همان زاویهٔ مسیرِ شبیه‌سازی (CSV و تله‌متری یکی)."""
        p = self._params or SimParams()
        base = p.launch_angle_deg
        f = self._flight
        if f is None or t_flight <= 0 or not f.track_pitch:
            return base
        n = len(f.track_pitch)
        if n == 1:
            return f.track_pitch[0]
        pos = t_flight / 0.1
        i = min(int(pos), n - 2)
        frac = max(0.0, min(1.0, pos - i))
        return f.track_pitch[i] + (f.track_pitch[i + 1] - f.track_pitch[i]) * frac

    # ------------------------------------------------------------------
    def write_csv(self, path: str) -> bool:
        """تولید فایل CSV پرواز -- فقط پس از فرود و فقط اگر SD نصب باشد."""
        if self._flight is None or self.phase != "landed":
            return False
        if not self._sd_available():
            return False
        rows = self._flight.rows
        if not rows:
            return False
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        return True
