# -*- coding: utf-8 -*-
"""
core/nozzle.py
-----------------
محاسبهٔ نسبت انبساط بهینهٔ نازل با رابطهٔ ایزنتروپیک جریان، بر اساس فشار
محفظهٔ احتراق (تقریبی) و فشار محیط در ارتفاع محل پرتاب (مدل جو استاندارد
بین‌المللی ISA، معتبر تا حدود ۱۱ کیلومتر -- کافی برای پروژه‌های آماتور).

فرضیات:
    - k (نسبت گرمای ویژه گازهای احتراق) پیش‌فرض ۱.۱۵ -- مقدار رایج برای
      سوخت شکری (KNSU/KNDX). در صورت نیاز قابل تغییر است.
    - فشار محفظه یک مقدار تقریبی ورودی از کاربر است، نه دادهٔ اندازه‌گیری‌شده.
"""
from __future__ import annotations

P0_SEA_LEVEL_PA = 101325.0  # فشار استاندارد سطح دریا (Pa)
DEFAULT_K = 1.15


def ambient_pressure(altitude_m: float) -> float:
    """فشار جو در ارتفاع داده‌شده، طبق مدل ISA (تروپوسفر، تا ۱۱ کیلومتر)."""
    h = max(0.0, altitude_m)
    h = min(h, 11000.0)
    return P0_SEA_LEVEL_PA * (1 - 2.25577e-5 * h) ** 5.25588


def _mach_from_pressure_ratio(pe_over_pc: float, k: float = DEFAULT_K) -> float:
    """حل عددی (دوبخشی) معادلهٔ ایزنتروپیک برای یافتن عدد ماخ خروجی از روی
    نسبت فشار خروجی به فشار محفظه (Pe/Pc)."""
    def f(m):
        return (1 + (k - 1) / 2 * m ** 2) ** (-k / (k - 1)) - pe_over_pc

    lo, hi = 1.0, 10.0
    if f(lo) * f(hi) > 0:
        return 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if f(lo) * f(mid) <= 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def optimal_expansion_ratio(chamber_pressure_pa: float, altitude_m: float,
                             k: float = DEFAULT_K) -> float:
    """نسبت انبساط بهینه (Ae/At) برای اینکه فشار خروجی نازل با فشار محیط
    در ارتفاع پرتاب برابر شود (Pe = Pa، حالت Perfectly Expanded)."""
    pa = ambient_pressure(altitude_m)
    if chamber_pressure_pa <= 0:
        return 0.0
    pe_over_pc = pa / chamber_pressure_pa
    me = _mach_from_pressure_ratio(pe_over_pc, k)
    ratio = (1 / me) * ((2 / (k + 1)) * (1 + (k - 1) / 2 * me ** 2)) ** ((k + 1) / (2 * (k - 1)))
    return ratio


def classify_expansion(actual_ratio: float, optimal_ratio: float, tolerance: float = 0.15) -> str:
    """مقایسهٔ نسبت انبساط هندسی فعلی نازل با نسبت بهینه.
    خروجی یکی از: 'under' (کم‌انبساط), 'optimal' (بهینه), 'over' (پرانبساط)."""
    if optimal_ratio <= 0 or actual_ratio <= 0:
        return "unknown"
    diff = (actual_ratio - optimal_ratio) / optimal_ratio
    if diff < -tolerance:
        return "under"
    if diff > tolerance:
        return "over"
    return "optimal"
