# -*- coding: utf-8 -*-
"""
core/advisor.py
------------------
بررسی هوشمند دادهٔ پرواز و ارائهٔ پیشنهاد اصلاحی -- یک سیستم کارشناس
(Expert System) مبتنی بر قواعد ساده و آستانه‌های مهندسی رایج در راکتری
آماتور، نه یک مدل یادگیری ماشین (که برای این حجم داده معنا/مزیتی ندارد).

سه محور بررسی می‌شود:
    1) پایداری (نوسانات Pitch/Yaw حین سوزش موتور)
    2) عملکرد موتور (بازدهی سوزش: ضربهٔ واقعی در برابر ضربهٔ نظری موتور)
    3) سیستم بازیابی (سرعت فرود در برابر بازهٔ ایمن)
"""
from __future__ import annotations
from typing import List

import numpy as np


def generate_suggestions(df, results: dict, mission, motor) -> List[str]:
    suggestions: List[str] = []
    if df is None or not results:
        return suggestions

    from core.analysis import FlightAnalyzer
    an = FlightAnalyzer(df, mission)
    an.detect_events()
    idx = getattr(an, "_idx", {})

    # ------------------------------------------------------------
    # ۱) پایداری: نوسانات Pitch/Yaw حین سوزش موتور
    # ------------------------------------------------------------
    launch_idx, burnout_idx = idx.get("launch"), idx.get("burnout")
    gx = df.get("GyroX"); gy = df.get("GyroY"); gz = df.get("GyroZ")
    if gx is not None and gy is not None and launch_idx is not None and burnout_idx is not None and burnout_idx > launch_idx:
        pitch_rate = gy.to_numpy()[launch_idx:burnout_idx + 1]
        yaw_rate = gz.to_numpy()[launch_idx:burnout_idx + 1] if gz is not None else np.zeros_like(pitch_rate)
        osc_amplitude = float(np.std(pitch_rate) + np.std(yaw_rate))  # deg/s (یا واحد خام سنسور)
        if osc_amplitude > 60:
            suggestions.append(
                "نوسانات Pitch/Yaw حین سوزش موتور بیشتر از حد معمول است؛ "
                "افزایش سطح بالچه‌ها (Fins) یا بررسی مجدد محل مرکز ثقل نسبت به مرکز فشار پیشنهاد می‌شود."
            )
        elif osc_amplitude > 30:
            suggestions.append(
                "نوسانات خفیفی حول محورهای Pitch/Yaw حین سوزش موتور مشاهده شد؛ "
                "توصیه می‌شود پایداری راکت (فاصلهٔ مرکز ثقل تا مرکز فشار) در پرواز بعدی بررسی شود."
            )
        else:
            suggestions.append("پایداری راکت حین سوزش موتور مطلوب بود؛ نوسانات Pitch/Yaw در محدودهٔ عادی است.")

    # ------------------------------------------------------------
    # ۲) عملکرد موتور: مقایسهٔ ضربهٔ واقعی با ضربهٔ نظری موتور
    # ------------------------------------------------------------
    if (an.a_total is not None and an.t is not None and mission and motor
            and launch_idx is not None and burnout_idx is not None and burnout_idx > launch_idx
            and motor.total_impulse > 0 and mission.total_mass > 0):
        t_burn = an.t[launch_idx:burnout_idx + 1]
        a_burn = an.a_total[launch_idx:burnout_idx + 1]
        # شتاب‌سنج «نیروی ویژه» می‌دهد: f = T/m (گرانش از قبل حذف شده)؛
        # پس رانش لحظه‌ای = جرم لحظه‌ای × f. گرانش دوباره کم نمی‌شود و
        # کاهش جرم حین سوزش هم خطی لحاظ می‌شود (ممیزی 1405-06-11).
        dur = max(t_burn[-1] - t_burn[0], 1e-6)
        prop_kg = max(0.0, getattr(mission, "propellant_mass", 0.0)) / 1000.0
        m0 = mission.total_mass
        m_t = np.maximum(m0 - prop_kg * (t_burn - t_burn[0]) / dur, 0.05 * m0)
        thrust_est = np.clip(m_t * a_burn, 0.0, None)
        # np.trapz در NumPy 2.x حذف و به np.trapezoid تغییر نام یافته است
        integrate = getattr(np, "trapezoid", None) or np.trapz
        actual_impulse = float(integrate(thrust_est, t_burn))
        efficiency = actual_impulse / motor.total_impulse if motor.total_impulse else 0

        if efficiency < 0.75:
            suggestions.append(
                f"بازدهی تخمینی سوزش موتور پایین است (حدود {efficiency*100:.0f}٪ از ضربهٔ نظری موتور). "
                "احتمال دارد قطر گلوگاه نازل نسبت به فشار محفظه بزرگ باشد یا سوخت به‌طور کامل نسوخته باشد؛ "
                "بررسی قطر گلوگاه یا فرمولاسیون سوخت پیشنهاد می‌شود."
            )
        elif efficiency > 1.25:
            suggestions.append(
                "ضربهٔ تخمینی از مقدار نظری موتور بیشتر است -- این می‌تواند نشانهٔ خطای اندازه‌گیری وزن راکت "
                "یا تخمین شتاب باشد؛ توصیه می‌شود دادهٔ خام شتاب و وزن واقعی راکت بازبینی شود."
            )
        else:
            suggestions.append(f"بازدهی تخمینی سوزش موتور مطلوب است (حدود {efficiency*100:.0f}٪ از ضربهٔ نظری موتور).")

    # ------------------------------------------------------------
    # ۳) سیستم بازیابی: سرعت فرود در برابر بازهٔ ایمن
    # ------------------------------------------------------------
    landing_v = results.get("landing_velocity")
    if landing_v is not None:
        if landing_v > 8:
            suggestions.append(
                f"سرعت فرود ({landing_v:.1f} m/s) بالاتر از بازهٔ ایمن معمول (۳ تا ۸ m/s) است؛ "
                "افزایش سطح چتر یا استفاده از چتر دوم (Drogue+Main) پیشنهاد می‌شود."
            )
        elif landing_v < 3:
            suggestions.append(
                f"سرعت فرود ({landing_v:.1f} m/s) کمتر از حد معمول است؛ راکت ممکن است در باد دچار "
                "رانش افقی زیاد شود -- کاهش سطح چتر یا استفاده از بند بلندتر برای کاهش رانش قابل بررسی است."
            )
        else:
            suggestions.append(f"سرعت فرود ({landing_v:.1f} m/s) در محدودهٔ ایمن قرار دارد.")

    return suggestions
