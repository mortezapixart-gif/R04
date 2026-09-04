# -*- coding: utf-8 -*-
"""
core/barrowman.py
------------------
محاسبهٔ مرکز فشار (CP)، مرکز ثقل (CG) و حاشیهٔ پایداری راکت به روش
بارومان (James S. Barrowman 1967) -- استاندارد راکت‌های آماتور در سرعت
زیرصوت و زاویهٔ حملهٔ کوچک.

این ماژول «مغز مشترک» دو برنامه است: ایستگاه زمینی (RocketGCS) و برنامهٔ
طراح (RocketDesigner) -- فقط ریاضی خالص و بدون Qt، تا در تست خودکار هم
قابل اجرا باشد.

معادلات (برگرفته از متن اصلی بارومان، بازنویسی ASPIRE Space eq.3.7-3.13):

  مخروط سر:   (CNα)N = 2 بر رادیان
              X_N = 0.466·L_N (اویو) | 0.666·L_N (مخروطی) | 0.5·L_N (بیضوی/تخت)

  بدنهٔ استوانه‌ای: (CNα)B = 0  (در زاویهٔ حملهٔ ~صفر)

  مجموعهٔ باله (n بالهٔ ذوزنقه‌ای، دهانهٔ s، وتر ریشه Cr، وتر نوک Ct،
  جاروب لبهٔ حملهٔ نوک نسبت به ریشه XR):
              (CNα)F = [1 + r/(s+r)] · 4n(s/d)² / (1 + √(1 + (2L_F/(Cr+Ct))²))
              L_F = √(s² + (XR + (Ct−Cr)/2)²)          (طول خط میان‌وتر)
              X_F = X_B + (XR/3)·(Cr+2Ct)/(Cr+Ct)
                        + (1/6)·(Cr + Ct − Cr·Ct/(Cr+Ct))
              (آزمون صحت: بالهٔ مستطیلی XR=0 → X_F − X_B = Cr/4 یعنی
               «ربع‌وتر» نظریهٔ ایرفویل نازک ✓)

  CP کل:      X̄ = Σ(CNαᵢ·Xᵢ) / Σ(CNαᵢ)

  پایداری:    حاشیه (کالیبر) = (X_CP − X_CG)/d   -- مثبت یعنی CP عقب‌تر از CG
              و راکت پایدار است؛ توصیهٔ رایج آماتوری: ۱ تا ۲ کالیبر
              (بیش از ~۲٫۵ = بیش‌پایدار/هواروک در باد).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# ثابت‌ها و نگاشت شکل مخروط سر → ضریب مکان CP (سهمِ طول مخروط)
# نیم‌کره/بیضوی: ۰٫۵ (نتیجهٔ مخروط سهمی، Cambridge eq.28)؛
# «تخت» به‌صورت تقریب همان ۰٫۵ روی طول کوتاهش (محافظه‌کارانه رو به جلو).
NOSE_CP_FACTOR: Dict[str, float] = {
    "اویو": 0.466,
    "مخروطی": 0.666,
    "نیم‌کره": 0.5,
    "تخت": 0.5,
}

# مکان CG مخروط سر (سهم طول از نوک) برای جسم توپر با چگالی یکنواخت:
# مخروط توپر 0.75 LN، اویو ~0.437، نیم‌کره 0.625، تخت 0.5.
NOSE_CG_FACTOR: Dict[str, float] = {
    "اویو": 0.437,
    "مخروطی": 0.750,
    "نیم‌کره": 0.625,
    "تخت": 0.500,
}

# آستانه‌های حاشیهٔ پایداری (کالیبر) برای رنگ/پیام
MARGIN_DANGER = 0.5      # کمتر از این: ناپایدار/خطرناک
MARGIN_MIN = 1.0         # حداقل قابل‌قبول
MARGIN_MAX = 2.5         # بیش از این: بیش‌پایدار (هواروک در باد)
MARGIN_TARGET = 1.5      # هدف پیشنهادی برای وارون‌سازی اندازهٔ باله


# ---------------------------------------------------------------------------
@dataclass
class RocketGeometry:
    """هندسهٔ راکت به میلی‌متر (مبدأ: نوک مخروط سر)."""
    body_diameter_mm: float = 80.0
    body_length_mm: float = 600.0          # بخش استوانه‌ای (بدون مخروط)
    nose_length_mm: float = 120.0
    nose_shape: str = "اویو"               # کلیدهای NOSE_CP_FACTOR
    fin_count: int = 4
    fin_root_chord_mm: float = 100.0       # Cr
    fin_tip_chord_mm: float = 60.0         # Ct
    fin_span_mm: float = 50.0              # s -- دهانهٔ بیرون‌زده از بدنه
    fin_sweep_mm: float = 0.0              # XR -- عقب‌رفتگی لبهٔ حملهٔ نوک
    fin_root_le_offset_mm: Optional[float] = None
    # فاصلهٔ لبهٔ حملهٔ ریشه از «انتهای بدنه» (مثبت = باله جلوتر).
    # None یعنی لبهٔ فرودِ باله هم‌تراز انتهای بدنه (رایج‌ترین ساخت).

    @property
    def total_length_mm(self) -> float:
        return self.nose_length_mm + self.body_length_mm

    @property
    def fin_root_le_from_nose_mm(self) -> float:
        """X_B -- فاصلهٔ لبهٔ حملهٔ ریشهٔ باله از نوک مخروط."""
        if self.fin_root_le_offset_mm is None:
            # لبهٔ فرود هم‌تراز انتها → لبهٔ حمله به‌اندازهٔ وتر ریشه جلوتر
            return self.total_length_mm - self.fin_root_chord_mm
        return self.total_length_mm - self.fin_root_le_offset_mm - self.fin_root_chord_mm


@dataclass
class MassItem:
    """یک جرم نقطه‌ای/قطعه برای محاسبهٔ CG (مبدأ: نوک مخروط)."""
    name: str
    mass_g: float
    x_from_nose_mm: float


@dataclass
class StabilityResult:
    x_cp_mm: float = 0.0                   # مرکز فشار از نوک
    x_cg_mm: float = 0.0                   # مرکز ثقل از نوک
    margin_calibers: float = 0.0           # (CP−CG)/d -- مثبت = پایدار
    cn_total: float = 0.0                  # (CNα) کل بر رادیان
    cn_nose: float = 0.0
    cn_fins: float = 0.0
    verdict: str = "unknown"               # danger | ok | over | unstable
    messages: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# اجزای بارومان
# ---------------------------------------------------------------------------
def nose_cn_alpha() -> float:
    """(CNα) مخروط سر بر رادیان -- ۲ برای همهٔ شکل‌های معمول (eq.3.7)."""
    return 2.0


def nose_cp_mm(geo: RocketGeometry) -> float:
    """مکان CP مخروط سر از نوک بر حسب شکل (eq.3.12 و همتایانش)."""
    factor = NOSE_CP_FACTOR.get(geo.nose_shape, 0.466)
    return factor * geo.nose_length_mm


def nose_cg_mm(geo: RocketGeometry) -> float:
    """مرکز جرم مخروط سر از نوک -- شکل‌وابسته (نه LN/2 برای همه)."""
    factor = NOSE_CG_FACTOR.get(geo.nose_shape, 0.437)
    return factor * geo.nose_length_mm


def fin_mid_chord_len_mm(geo: RocketGeometry) -> float:
    """L_F -- طول خط میان‌وتر باله (وتر ریشه و نوک را در وسط وصل می‌کند)."""
    delta = geo.fin_sweep_mm + (geo.fin_tip_chord_mm - geo.fin_root_chord_mm) / 2.0
    return math.hypot(geo.fin_span_mm, delta)


def fin_set_cn_alpha(geo: RocketGeometry) -> float:
    """(CNα) مجموعهٔ باله بر رادیان با ضریب تداخل بدنه (eq.3.8 × eq.3.9)."""
    d = geo.body_diameter_mm
    r = d / 2.0
    s = geo.fin_span_mm
    cr, ct = geo.fin_root_chord_mm, geo.fin_tip_chord_mm
    if s <= 0 or cr + ct <= 0 or d <= 0:
        return 0.0
    lf = fin_mid_chord_len_mm(geo)
    aspect_term = 2.0 * lf / (cr + ct)
    denom = 1.0 + math.sqrt(1.0 + aspect_term * aspect_term)
    interference = 1.0 + r / (s + r)
    return interference * 4.0 * geo.fin_count * (s / d) ** 2 / denom


def fin_set_cp_mm(geo: RocketGeometry) -> float:
    """مکان CP مجموعهٔ باله از نوک (eq.3.13) -- در mm."""
    cr, ct = geo.fin_root_chord_mm, geo.fin_tip_chord_mm
    if cr + ct <= 0:
        return geo.fin_root_le_from_nose_mm
    xr = geo.fin_sweep_mm
    xb = geo.fin_root_le_from_nose_mm
    return (xb
            + (xr / 3.0) * ((cr + 2.0 * ct) / (cr + ct))
            + (1.0 / 6.0) * (cr + ct - cr * ct / (cr + ct)))


def fin_set_cg_mm(geo: RocketGeometry) -> float:
    """مرکز جرم هندسی مجموعهٔ باله از نوک (سانتروئید ذوزنقهٔ یکنواخت).

    برای صفحهٔ مستطیلی Cr/2، برای مثلثی Cr/3 -- نه CP آیرودینامیکی (ربع‌وتر).
    """
    cr, ct = geo.fin_root_chord_mm, geo.fin_tip_chord_mm
    xb = geo.fin_root_le_from_nose_mm
    if cr + ct <= 0:
        return xb
    xr = geo.fin_sweep_mm
    # سانتروئید ذوزنقه از لبهٔ حملهٔ ریشه در راستای وتر
    x_le = (xr * (cr + 2.0 * ct) + cr * cr + cr * ct + ct * ct) / (3.0 * (cr + ct))
    return xb + x_le


# ---------------------------------------------------------------------------
# CG و CP کل
# ---------------------------------------------------------------------------
def center_of_gravity_mm(items: List[MassItem]) -> Optional[float]:
    """مرکز ثقل وزنی اجزا (mm از نوک)؛ بدون جرم → None."""
    m_tot = sum(it.mass_g for it in items)
    if m_tot <= 0:
        return None
    return sum(it.mass_g * it.x_from_nose_mm for it in items) / m_tot


def center_of_pressure_mm(geo: RocketGeometry) -> Dict[str, float]:
    """CP کل و اجزا؛ خروجی: dict(x_cp, cn_total, cn_nose, cn_fins, x_nose, x_fins)."""
    cn_n = nose_cn_alpha()
    x_n = nose_cp_mm(geo)
    cn_f = fin_set_cn_alpha(geo)
    x_f = fin_set_cp_mm(geo)
    cn_tot = cn_n + cn_f
    if cn_tot <= 0:
        return {"x_cp": 0.0, "cn_total": 0.0, "cn_nose": cn_n, "cn_fins": cn_f,
                "x_nose": x_n, "x_fins": x_f}
    x_cp = (cn_n * x_n + cn_f * x_f) / cn_tot
    return {"x_cp": x_cp, "cn_total": cn_tot, "cn_nose": cn_n, "cn_fins": cn_f,
            "x_nose": x_n, "x_fins": x_f}


# ---------------------------------------------------------------------------
# حاشیهٔ پایداری + پیشنهاد اصلاح
# ---------------------------------------------------------------------------
def classify_margin(margin: float) -> str:
    if margin < 0:
        return "unstable"
    if margin < MARGIN_DANGER:
        return "danger"
    if margin < MARGIN_MIN:
        return "warn"
    if margin <= MARGIN_MAX:
        return "ok"
    return "over"


def analyze(geo: RocketGeometry, cg_mm: Optional[float]) -> StabilityResult:
    """تحلیل کامل: CP، حاشیه و پیام‌ها. cg_mm از اجزا یا اندازه‌گیری."""
    cp = center_of_pressure_mm(geo)
    res = StabilityResult(
        x_cp_mm=cp["x_cp"], cn_total=cp["cn_total"],
        cn_nose=cp["cn_nose"], cn_fins=cp["cn_fins"],
    )
    if cg_mm is None:
        res.verdict = "unknown"
        res.messages.append("جرم‌ها را وارد کنید یا CG اندازه‌گیری‌شده بدهید.")
        return res
    res.x_cg_mm = cg_mm
    res.margin_calibers = (res.x_cp_mm - cg_mm) / geo.body_diameter_mm
    res.verdict = classify_margin(res.margin_calibers)
    m = res.margin_calibers
    if res.verdict == "unstable":
        res.messages.append(
            f"ناپایدار ({m:.2f} کالیبر): CP جلوی CG است -- این راکت بدون اصلاح "
            "پرواز نکند؛ بزرگ‌تر کردن باله‌ها یا افزودن جرم به دماغه لازم است.")
    elif res.verdict == "danger":
        res.messages.append(
            f"حاشیهٔ {m:.2f} کالیبر بسیار کم است؛ تلاطم باد یا باد جانبی می‌تواند "
            "راکت غلت بزند. باله بزرگ‌تر یا دماغهٔ سنگین‌تر لازم است.")
    elif res.verdict == "warn":
        res.messages.append(
            f"حاشیهٔ {m:.2f} کالیبر زیر حد توصیه‌شده (۱٫۰) است؛ برای پرواز بادزی "
            "بهتر است باله‌ها را کمی بزرگ‌تر کنید.")
    elif res.verdict == "ok":
        res.messages.append(
            f"حاشیهٔ {m:.2f} کالیبر در بازهٔ ایمن (۱ تا ۲٫۵) است -- طراحی سالم.")
    else:
        res.messages.append(
            f"حاشیهٔ {m:.2f} کالیبر بیش‌ازحد زیاد است؛ راکت در باد زیاد هواروک "
            "می‌شود (Weathercock). باله کوچک‌تر یا دماغهٔ سبک‌تر بهتر است.")
    return res


def suggest_fin_span_mm(geo: RocketGeometry, cg_mm: float,
                        target: float = MARGIN_TARGET) -> Optional[float]:
    """وارون‌سازی: کوچک‌ترین دهانهٔ باله که حاشیهٔ هدف (پیش‌فرض ۱٫۵ کالیبر)
    را می‌دهد؛ وترها و جاروب ثابت می‌مانند. اگر با دهانهٔ حداکثری (۴ برابر
    فعلی) هم به هدف نرسیدیم → None (باید جرم دماغه اضافه شود)."""
    from dataclasses import replace

    def margin_for(span: float) -> float:
        g2 = replace(geo, fin_span_mm=span)
        return (center_of_pressure_mm(g2)["x_cp"] - cg_mm) / g2.body_diameter_mm

    lo, hi = geo.fin_span_mm, 4.0 * max(geo.fin_span_mm, 1.0)
    if margin_for(lo) >= target:
        return None            # همین حالا کافی است -- پیشنهادی لازم نیست
    if margin_for(hi) < target:
        return None            # با باله هم نمی‌رسد → جرم دماغه
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if margin_for(mid) >= target:
            hi = mid
        else:
            lo = mid
    return round(hi, 1)


def suggest_nose_mass_g(geo: RocketGeometry, cg_mm: float, total_mass_g: float,
                        target: float = MARGIN_TARGET) -> Optional[float]:
    """جرمی که باید به «نوک دماغه» اضافه شود تا حاشیه به هدف برسد
    (بدون تغییر باله‌ها). CG هدف: به‌اندازهٔ target کالیبر جلوتر از CP:
        x_t = X_CP − target·d ؛  x_new = (M·cg)/(M+m) = x_t
        →  m = M·(cg − x_t)/x_t
    اگر CG همین حالا جلوتر از x_t است (حاشیهٔ بیش‌ازحد) → None."""
    cp = center_of_pressure_mm(geo)["x_cp"]
    x_target = cp - target * geo.body_diameter_mm
    if x_target <= 0 or cg_mm <= x_target:
        return None
    return total_mass_g * (cg_mm - x_target) / x_target
