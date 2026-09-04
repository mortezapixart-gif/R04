# -*- coding: utf-8 -*-
"""
core/analysis.py
------------------
موتور تحلیل پرواز: تشخیص رویدادها (پرتاب، Burnout، Apogee، باز شدن چتر،
برخورد با زمین) و محاسبات آیرودینامیکی، ارتفاع/سرعت/شتاب و چتر.

روش تشخیص رویدادها بر پایه آستانه‌های شتاب و مشتق ارتفاع (سرعت عمودی)
است -- مشابه الگوریتم‌های متداول در آلتی‌مترهای آماتوری (مثل تشخیص
Burnout با افت ناگهانی شتاب به زیر ۱g و Apogee با تغییر علامت سرعت).
"""
from __future__ import annotations
from typing import Dict, Optional, Any
import math

import numpy as np
import pandas as pd

G0 = 9.80665


def _col(df: pd.DataFrame, *names):
    """پیدا کردن اولین ستون موجود از میان چند نام محتمل."""
    for n in names:
        if n in df.columns:
            return df[n].astype(float).to_numpy()
    return None


class FlightAnalyzer:
    def __init__(self, df: pd.DataFrame, mission=None, motor=None):
        self.mission = mission
        self.df = df  # دسترسی مستقیم به دیتافریم خام (مورد نیاز موتور گزارش جدید)

        self.t = _col(df, "Time", "time", "Timestamp")
        if self.t is not None and self.t[0] > 1e6:  # اگر epoch/ms باشد -> به ثانیه از شروع
            self.t = (self.t - self.t[0]) / 1000.0

        self.alt = _col(df, "Altitude", "altitude")
        self.pressure = _col(df, "Pressure", "pressure")
        self.temp = _col(df, "Temperature", "temperature")            # دمای محیط -- سنسور BMP280
        self.temp_mpu = _col(df, "Temperature_MPU", "temp_mpu", "MPU_Temperature")  # دمای داخلی تراشه -- MPU6050
        self.temp_aht = _col(df, "Temperature_AHT", "temp_aht", "AHT_Temperature")  # دمای محیط -- سنسور AHT21B
        self.humidity = _col(df, "Humidity", "humidity", "RH")        # رطوبت نسبی -- AHT21B
        self.uv = _col(df, "UV_Index", "uv_index", "UV", "uv")        # شاخص UV -- GUVA-S12SD
        self.ax = _col(df, "AccelX", "ax")
        self.ay = _col(df, "AccelY", "ay")
        self.az = _col(df, "AccelZ", "az")

        # شتاب کل (بردار) در صورت وجود سه محور
        if self.ax is not None and self.ay is not None and self.az is not None:
            self.a_total = np.sqrt(self.ax**2 + self.ay**2 + self.az**2)
        else:
            self.a_total = None

        # سرعت عمودی از مشتق ارتفاع (فیلتر ساده متحرک برای کاهش نویز)
        if self.alt is not None and self.t is not None and len(self.t) > 2:
            dt = np.gradient(self.t)
            dt[dt == 0] = 1e-3
            self.vel = np.gradient(self.alt) / dt
            self.vel = pd.Series(self.vel).rolling(5, min_periods=1, center=True).mean().to_numpy()
        else:
            self.vel = None

    def local_density(self):
        """چگالی هوا (kg/m³) در هر نمونه: ρ = p/(R·T) از سنسور، وگرنه ISA."""
        n = len(self.vel) if self.vel is not None else (len(self.t) if self.t is not None else 0)
        if n == 0:
            return np.array([], dtype=float)
        R = 287.05
        if self.pressure is not None and self.temp is not None:
            m = min(n, len(self.pressure), len(self.temp))
            p_pa = np.asarray(self.pressure[:m], dtype=float) * 100.0
            t_k = np.asarray(self.temp[:m], dtype=float) + 273.15
            with np.errstate(invalid="ignore", divide="ignore"):
                rho = p_pa / (R * np.maximum(t_k, 180.0))
            ok = np.isfinite(rho) & (rho > 0.05) & (rho < 3.0)
            if ok.mean() > 0.5:
                fill = float(np.nanmedian(np.where(ok, rho, np.nan)))
                rho = np.where(ok, rho, fill)
                if m < n:
                    rho = np.concatenate([rho, np.full(n - m, fill)])
                return rho
        try:
            from core.rocket_physics import isa_density
        except Exception:
            isa_density = None
        msl = 0.0
        if self.mission is not None:
            msl = float(getattr(self.mission, "altitude_msl", 0.0) or 0.0)
        if isa_density is not None and self.alt is not None:
            alt = np.asarray(self.alt, dtype=float)
            m = min(n, len(alt))
            rho = np.array([isa_density(msl + max(float(h), 0.0)) for h in alt[:m]], dtype=float)
            if m < n:
                rho = np.concatenate([rho, np.full(n - m, rho[-1] if m else 1.225)])
            return rho
        return np.full(n, 1.225)

    # ------------------------------------------------------------------
    def detect_events(self) -> Dict[str, Optional[float]]:
        events = {"launch": None, "burnout": None, "apogee": None,
                  "parachute": None, "landing": None}
        if self.t is None:
            return events

        n = len(self.t)

        # ۱) لحظه پرتاب: اولین نمونه‌ای که شتاب کل از آستانه (۲g) عبور کند
        if self.a_total is not None:
            launch_idx = np.argmax(self.a_total > 2.0 * G0) if np.any(self.a_total > 2.0 * G0) else 0
            events["launch"] = float(self.t[launch_idx])
        else:
            launch_idx = 0
            events["launch"] = float(self.t[0])

        # ۲) Burnout: پس از پرتاب، اولین لحظه‌ای که شتاب به زیر ۱g می‌افتد
        burnout_idx = launch_idx
        if self.a_total is not None:
            for i in range(launch_idx + 1, n):
                if self.a_total[i] < 1.0 * G0:
                    burnout_idx = i
                    break
            events["burnout"] = float(self.t[burnout_idx])

        # ۳) Apogee: بیشینه ارتفاع (یا لحظه تغییر علامت سرعت از + به -)
        if self.alt is not None:
            apogee_idx = int(np.argmax(self.alt))
            events["apogee"] = float(self.t[apogee_idx])
        elif self.vel is not None:
            apogee_idx = burnout_idx
            for i in range(burnout_idx + 1, n - 1):
                if self.vel[i] >= 0 and self.vel[i + 1] < 0:
                    apogee_idx = i
                    break
            events["apogee"] = float(self.t[apogee_idx])
        else:
            apogee_idx = burnout_idx

        # ۴) باز شدن چتر: بعد از اوج، افت ناگهانی سرعت سقوط (تغییر شیب سرعت)
        parachute_idx = apogee_idx
        if self.vel is not None:
            for i in range(apogee_idx + 2, n - 1):
                # جهش مثبت در سرعت (کند شدن سقوط) به معنی باز شدن چتر
                if self.vel[i] - self.vel[i - 2] > 3.0 and self.vel[i - 2] < -5:
                    parachute_idx = i
                    break
            events["parachute"] = float(self.t[parachute_idx])

        # ۵) برخورد با زمین: ارتفاع نزدیک صفر و سرعت نزدیک صفر پس از چتر
        landing_idx = n - 1
        if self.alt is not None:
            ground_ref = self.alt[0]
            for i in range(parachute_idx + 1, n):
                if abs(self.alt[i] - ground_ref) < 3.0:
                    landing_idx = i
                    break
        events["landing"] = float(self.t[landing_idx])

        self._idx = dict(launch=launch_idx, burnout=burnout_idx, apogee=apogee_idx,
                          parachute=parachute_idx, landing=landing_idx)
        return events

    # ------------------------------------------------------------------
    def full_analysis(self, events: Dict[str, Optional[float]]) -> Dict[str, Any]:
        res: Dict[str, Any] = {"events": events}
        idx = getattr(self, "_idx", {})

        # ---- ارتفاع و سرعت ----
        if self.alt is not None:
            res["max_altitude"] = float(np.max(self.alt))
        if self.vel is not None:
            res["max_velocity"] = float(np.max(np.abs(self.vel)))
            if "burnout" in idx:
                res["velocity_at_burnout"] = float(self.vel[idx["burnout"]])
            if "landing" in idx:
                res["landing_velocity"] = float(abs(self.vel[idx["landing"]]))

        # ---- شتاب ----
        if self.a_total is not None:
            res["max_g"] = float(np.max(self.a_total) / G0)
            if "landing" in idx:
                res["accel_at_landing"] = float(self.a_total[idx["landing"]] / G0)
            if "parachute" in idx:
                # شتاب کل در لحظهٔ باز شدن چتر: ضربهٔ باز شدن چتر روی سازه
                res["accel_at_parachute_g"] = float(self.a_total[idx["parachute"]] / G0)

        # ---- دما (BMP280 = محیط، MPU6050 = تراشه/Self-Heating) ----
        if self.temp is not None:
            launch_idx = idx.get("launch") or 0
            apogee_idx = idx.get("apogee")
            res["ground_temperature_c"] = float(self.temp[launch_idx])
            if apogee_idx is not None:
                res["apogee_temperature_c"] = float(self.temp[apogee_idx])
            if apogee_idx is not None and apogee_idx > launch_idx:
                alt_ascent = self.alt[launch_idx:apogee_idx + 1] if self.alt is not None else None
                temp_ascent = self.temp[launch_idx:apogee_idx + 1]
                if alt_ascent is not None and len(alt_ascent) > 3 and (np.max(alt_ascent) - np.min(alt_ascent)) > 10:
                    slope_c_per_m = float(np.polyfit(alt_ascent, temp_ascent, 1)[0])
                    res["temperature_lapse_rate_c_per_km"] = slope_c_per_m * 1000
            if self.temp_mpu is not None:
                res["mpu_self_heating_offset_c"] = float(np.mean(self.temp_mpu - self.temp))
            if self.temp_aht is not None:
                res["aht_bmp_temp_diff_c"] = float(np.mean(self.temp_aht - self.temp))

        # ---- رطوبت (AHT21B) ----
        if self.humidity is not None:
            launch_idx = idx.get("launch") or 0
            apogee_idx = idx.get("apogee")
            res["ground_humidity_percent"] = float(self.humidity[launch_idx])
            if apogee_idx is not None:
                res["apogee_humidity_percent"] = float(self.humidity[apogee_idx])
            res["humidity_min_percent"] = float(np.min(self.humidity))
            res["humidity_max_percent"] = float(np.max(self.humidity))

        # ---- شاخص UV (GUVA-S12SD) ----
        if self.uv is not None:
            launch_idx = idx.get("launch") or 0
            apogee_idx = idx.get("apogee")
            res["ground_uv_index"] = float(self.uv[launch_idx])
            if apogee_idx is not None:
                res["apogee_uv_index"] = float(self.uv[apogee_idx])
            res["uv_index_max"] = float(np.max(self.uv))

        # ---- آیرودینامیک ----
        # q = ½ρv² با چگالی *محلی* (نه ثابت سطح دریا). سرعت از مشتق ارتفاع
        # است (عمودی) چون CSV معمولاً مؤلفهٔ افقیِ تمیز ندارد.
        if self.vel is not None and self.t is not None:
            rho = self.local_density()
            q = 0.5 * rho * self.vel ** 2
            res["dynamic_pressure_max"] = float(np.nanmax(q))
            max_q_idx = int(np.nanargmax(q))
            res["max_q_time"] = float(self.t[max_q_idx])
            res["max_q_velocity"] = float(abs(self.vel[max_q_idx]))
            area = None
            if self.mission is not None and self.mission.body_diameter:
                area = np.pi * (self.mission.body_diameter / 2.0) ** 2
            if (area and self.mission is not None and self.mission.total_mass
                    and self.pressure is not None
                    and idx.get("burnout") and idx.get("apogee")):
                # برآورد Cd از سقوط آزاد بالستیک بعد از burnout:
                # h_coast = (m/(rho_bar·Cd·A))·ln(1 + rho_bar·Cd·A·v0²/(2mg))
                # Cd با دو بخشی (bisection) طوری حل می‌شود که ارتفاعِ سقوطِ
                # اندازه‌گیری‌شده بازتولید شود (ممیزی 1405-06-11).
                i_burn, i_apo = idx["burnout"], idx["apogee"]
                if i_apo > i_burn:
                    v0 = float(abs(self.vel[i_burn]))
                    h_coast = float(self.alt[i_apo] - self.alt[i_burn]) if self.alt is not None else 0.0
                    m_dry = self.mission.total_mass - \
                        max(0.0, getattr(self.mission, "propellant_mass", 0.0)) / 1000.0
                    m_dry = max(m_dry, 0.05 * self.mission.total_mass)
                    p_bar = float(np.mean(self.pressure[i_burn:i_apo + 1])) * 100.0  # hPa → Pa
                    t_bar_c = float(np.mean(self.temp[i_burn:i_apo + 1])) if self.temp is not None \
                        else 15.0 - 0.0065 * h_coast / 2.0
                    rho_bar = max(p_bar / (287.05 * (t_bar_c + 273.15)), 0.05)
                    k = rho_bar * area / (2.0 * m_dry * G0)

                    def coast_h(cd: float) -> float:
                        # انتگرال تحلیلی ارتفاع سقوط با درگ درجه۲ از سرعت v0:
                        # h = (m/(ρ·Cd·A))·ln(1 + ρ·Cd·A·v0²/(2mg))
                        z = k * cd * v0 * v0
                        if z < 1e-9:
                            return v0 * v0 / (2 * G0)
                        return math.log1p(z) / (2.0 * k * cd * G0)

                    if v0 > 20.0 and h_coast > 20.0 and coast_h(0.05) > h_coast > coast_h(2.0):
                        lo, hi = 0.05, 2.0
                        for _ in range(60):
                            mid = 0.5 * (lo + hi)
                            if coast_h(mid) > h_coast:
                                lo = mid
                            else:
                                hi = mid
                        cd_est = 0.5 * (lo + hi)
                        if 0.05 <= cd_est <= 2.0:
                            res["estimated_Cd"] = round(cd_est, 3)

        # ---- چتر ----
        if self.vel is not None and idx.get("parachute") is not None and idx.get("landing") is not None:
            v_before = float(abs(self.vel[idx["parachute"]]))
            v_after_idx = min(idx["parachute"] + 3, len(self.vel) - 1)
            v_after = float(abs(self.vel[v_after_idx]))
            res["parachute_deploy_altitude"] = float(self.alt[idx["parachute"]]) if self.alt is not None else None
            if self.t is not None:
                launch_t = self.t[idx["launch"]] if idx.get("launch") is not None else self.t[0]
                res["parachute_deploy_time"] = float(self.t[idx["parachute"]] - launch_t)
            res["velocity_before_chute"] = v_before
            res["velocity_after_chute"] = v_after
            # نسبت کاهش سرعت (بی‌بعد، مثلاً «۷٫۲ برابر»): واحد نمایش در همهٔ
            # مصرف‌کننده‌ها «x» است؛ m/s قبلاً با قالب‌های نمایش ناسازگار بود.
            res["descent_rate_reduction"] = (v_before / v_after) if v_after > 0.01 else None
            landing_v = res.get("landing_velocity", v_after)
            if self.mission and self.mission.total_mass:
                # انرژی برخورد با «جرم خشک» -- سوخت تا لحظهٔ فرود سوخته است
                m_dry = self.mission.total_mass - \
                    max(0.0, getattr(self.mission, "propellant_mass", 0.0)) / 1000.0
                res["impact_energy_j"] = 0.5 * max(m_dry, 0.05 * self.mission.total_mass) * landing_v ** 2

            # پیشنهاد ساده بر اساس سرعت فرود (آستانه‌های رایج در راکتری آماتور)
            if landing_v > 8:
                res["chute_suggestion"] = "سرعت فرود بالاست؛ افزایش سطح چتر پیشنهاد می‌شود."
            elif landing_v < 3:
                res["chute_suggestion"] = "سرعت فرود پایین است؛ کاهش سطح چتر برای کاهش رانش باد ممکن است مناسب باشد."
            else:
                res["chute_suggestion"] = "سرعت فرود در محدوده مناسب است."

        return res
