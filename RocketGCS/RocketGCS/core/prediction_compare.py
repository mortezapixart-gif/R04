# -*- coding: utf-8 -*-
"""«پیش‌بینی در برابر واقعیت» -- مقایسهٔ شبیه‌سازی پیش از پرواز با تله‌متری واقعی.

چرا این ماژول؟ پیش‌بینیِ صفحهٔ مأموریت از مدل فیزیکی ساده می‌آید (رانش موتور
از دیتاشیت/فشار محفظه، ضریب درگ تخمینی، جو استاندارد ISA و بدون بادِ واقعی).
واقعیت همیشه از آن فاصله دارد. این ماژول سه کار می‌کند:

۱) اسنپ‌شات (capture_snapshot): پیش‌بینی + بازهٔ عدم‌قطعیتِ آن دقیقاً در لحظهٔ
   پرتاب ثبت می‌شود تا بعد از پرواز، مقایسه با «همان چیزی که کاربر دیده بود»
   انجام شود نه با پارامترهای فعلیِ (شاید تغییرکردهٔ) فرم.
۲) بازهٔ محتمل (monte_carlo_bands): با تلرانس‌های واقع‌بینانهٔ راکت‌های آماتوری
   (فشار محفظه ±۱۵٪، وزن ±۵٪، سوخت ±۸٪، قطر/درگ ±۱۰٪) شبیه‌سازی تکرار
   می‌شود و بازهٔ ۱۰ تا ۹۰ درصد هر کمیت به‌دست می‌آید -- «پیش‌بینی یک عدد
   نیست، یک بازه است».
۳) مقایسه و علت‌یابی حدودی (compare_snapshot): جدول کمیت‌ها + ارزیابی + قواعد
   علت‌یابی (موتور ضعیف‌تر / درگ بیشتر / چتر ناقص / ...) -- همه با لحن
   «احتمالاً»، چون بدون بادسنج و تله‌متری موتور، قطعیت ممکن نیست.

این ماژول عمداً بدون Qt است تا در تست خودکار و اسکریپت‌های مستقل هم اجرا شود.
"""
import random
from dataclasses import asdict, replace
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from core.rocket_physics import (SimParams, simulate_flight, predict_summary,
                                 SEMNAN_ELEVATION_M)

# تلرانس‌های عدم‌قطعیت -- مبنا: تلرانس‌های متعارف موتورهای آماتوری سوخت جامد
# (رقابت‌پذیر: تلرانس ایمپالس کل در کلاس‌های NAR/Tracor ~±۱۰-۲۰٪) و خطای اندازه‌گیری وزن/قطر
MC_RUNS = 80
MC_TOLERANCES = {
    "mass": 0.05,        # وزن پرتاب ±۵٪ (ترازوی دستی + رنگ/چسب/رطوبت)
    "pressure": 0.15,    # فشار محفظه ±۱۵٪ → رانش ~خطی با آن
    "propellant": 0.08,  # وزن سوخت ±۸٪ (ریزش/تراکم دانه‌ها)
    "diameter": 0.10,    # قطر مؤثر/درگ ±۱۰٪ (فین‌ها، زبری، Cd تخمینی)
}


def build_sim_params(mission, motor, sensor_models: Optional[Dict[str, str]] = None) -> SimParams:
    """ساخت SimParams از اطلاعات ذخیره‌شدهٔ مأموریت/موتور (همان ورودی‌های فرم).

    جرم/سوخت صفر یعنی فرم خالی است و به پیش‌فرض آموزشی ۳٫۲ kg برنمی‌گردد
    (همان رفتار کارت پیش‌بینی صفحهٔ مأموریت: پرواز نامعتبر). دو استثنا:
      * ارتفاع ۰ متر (تراز دریا) مقداری معتبر و آگاهانه است و دست نمی‌خورد؛
        فقط نبودِ صفت/فرم خالی به پیش‌فرض سمنان برمی‌گردد.
      * قطر چتر صفر یعنی «بدون چتر» و انتخاب آگاهانهٔ کاربر است.
      * زاویهٔ پرتاب ۰ درجه هم معتبر است (افقی) و به ۹۰ تبدیل نمی‌شود."""
    alt = getattr(mission, "altitude_msl", None)
    ang = getattr(mission, "launch_angle", None)
    if ang is None or ang == "":
        launch_angle = 90.0
    else:
        try:
            launch_angle = float(ang)
        except (TypeError, ValueError):
            launch_angle = 90.0
    body_diameter = (getattr(mission, "body_diameter", 0.0) or 0.0) or SimParams.body_diameter_m
    cp = getattr(mission, "cp_from_nose", None)
    cg = getattr(mission, "cg_from_nose", None)
    if cp is None or cg is None:
        length = (getattr(mission, "body_length", 0.0) or 0.0) or max(0.6, body_diameter * 8.0)
        cp = length * 0.67 if cp is None else cp
        cg = max(0.0, cp - 1.5 * body_diameter) if cg is None else cg
    return SimParams(
        total_mass_kg=float(getattr(mission, "total_mass", 0.0) or 0.0),
        propellant_mass_g=float(getattr(mission, "propellant_mass", 0.0) or 0.0),
        body_diameter_m=body_diameter,
        body_length_m=(getattr(mission, "body_length", 0.0) or 0.0),
        body_section_length_m=(getattr(mission, "body_section_length", 0.0) or 0.0),
        nose_length_m=(getattr(mission, "nose_length", 0.0) or 0.0),
        nose_cone=str(getattr(mission, "nose_cone", None) or "اویو"),
        fin_shape=str(getattr(mission, "fin_shape", "ذوزنقه‌ای") or "ذوزنقه‌ای"),
        fin_count=int(getattr(mission, "fin_count", 0) or 0),
        fin_root_chord_m=float(getattr(mission, "fin_root_chord", 0.0) or 0.0),
        fin_tip_chord_m=float(getattr(mission, "fin_tip_chord", 0.0) or 0.0),
        fin_span_m=float(getattr(mission, "fin_span", 0.0) or 0.0),
        fin_sweep_m=float(getattr(mission, "fin_sweep", 0.0) or 0.0),
        cp_from_nose_m=cp,
        cg_from_nose_m=cg,
        stability_margin_calibers=getattr(mission, "stability_margin_calibers", None),
        design_source=str(getattr(mission, "design_source", "manual") or "manual"),
        launch_angle_deg=launch_angle,
        altitude_msl_m=(alt if alt is not None else SEMNAN_ELEVATION_M) if alt != "" else 0.0,
        throat_diameter_mm=(getattr(motor, "throat_diameter", 0.0) or 0.0) or SimParams.throat_diameter_mm,
        exit_diameter_mm=(getattr(motor, "exit_diameter", 0.0) or 0.0) or SimParams.exit_diameter_mm,
        chamber_pressure_bar=(getattr(motor, "chamber_pressure_bar", 0.0) or 0.0) or SimParams.chamber_pressure_bar,
        divergence_angle_deg=(getattr(motor, "divergent_angle", 0.0) or 0.0) or 15.0,
        chute_diameter_m=(getattr(mission, "chute_diameter_m", 0.0) or 0.0),
        sensor_models=dict(sensor_models or {}),
    )


def monte_carlo_bands(params: SimParams, runs: int = MC_RUNS,
                      seed: int = 7) -> Dict[str, Optional[Tuple[float, float, float]]]:
    """بازهٔ محتمل (۱۰٪-۹۰٪) خروجی‌های اصلی با پخش تلرانس‌ها -- مونت‌کارلو.

    خروجی: {کلید کمیت: (p10, میانه, p90)} یا None برای کمیت‌های ناموجود."""
    rng = random.Random(seed)
    keys = ("apogee_m", "max_speed_ms", "max_accel_g", "landing_speed_ms",
            "flight_time_s", "burn_time_s")
    samples: Dict[str, List[float]] = {k: [] for k in keys}
    for _ in range(runs):
        p = replace(
            params,
            total_mass_kg=max(0.05, params.total_mass_kg * rng.uniform(1 - MC_TOLERANCES["mass"],
                                                                       1 + MC_TOLERANCES["mass"])),
            chamber_pressure_bar=max(1.0, params.chamber_pressure_bar * rng.uniform(1 - MC_TOLERANCES["pressure"],
                                                                                    1 + MC_TOLERANCES["pressure"])),
            propellant_mass_g=max(1.0, params.propellant_mass_g * rng.uniform(1 - MC_TOLERANCES["propellant"],
                                                                              1 + MC_TOLERANCES["propellant"])),
            body_diameter_m=max(0.01, params.body_diameter_m * rng.uniform(1 - MC_TOLERANCES["diameter"],
                                                                           1 + MC_TOLERANCES["diameter"])),
        )
        s = simulate_flight(p).summary
        for k in keys:
            v = s.get(k)
            if v:
                samples[k].append(float(v))
    bands: Dict[str, Optional[Tuple[float, float, float]]] = {}
    for k in keys:
        vals = sorted(samples[k])
        if len(vals) < max(5, runs // 4):
            bands[k] = None
            continue
        def pct(f: float) -> float:
            i = min(len(vals) - 1, max(0, int(round(f * (len(vals) - 1)))))
            return vals[i]
        bands[k] = (pct(0.10), pct(0.50), pct(0.90))
    return bands


def capture_snapshot(mission, motor, sensor_models: Optional[Dict[str, str]] = None) -> Optional[dict]:
    """ثبت پیش‌بینیِ لحظهٔ پرتاب (عدد مرکزی + بازهٔ محتمل + پارامترها).

    در خطای محاسبه None برمی‌گردد تا پرواز هرگز به‌خاطر گزارش متوقف نشود."""
    try:
        params = build_sim_params(mission, motor, sensor_models)
        summary = predict_summary(params)
        bands = monte_carlo_bands(params)
        return {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "params": {k: v for k, v in asdict(params).items()},
            "summary": {k: v for k, v in summary.items() if k != "motor"},
            "bands": bands,
        }
    except Exception:
        return None


# ---------------------------------------------------------------------------
# مقایسه + علت‌یابی
# ---------------------------------------------------------------------------

# (کلید، برچسب فارسی، واحد، کلید پیش‌بینی، تابع استخراج واقعیت)
def _actual_from_results(results: dict) -> Dict[str, Optional[float]]:
    events = results.get("events") or {}
    t0 = events.get("launch")

    def dt(key: str) -> Optional[float]:
        t = events.get(key)
        return (t - t0) if (t is not None and t0 is not None) else None

    return {
        "apogee": results.get("max_altitude"),
        "vmax": results.get("max_velocity"),
        "gmax": results.get("max_g"),
        "vland": results.get("landing_velocity"),
        "burn": dt("burnout"),
        "tapogee": dt("apogee"),
        "tflight": dt("landing"),
    }


_METRICS = [
    ("apogee", "اوج پرواز", "m", "apogee_m"),
    ("vmax", "حداکثر سرعت", "m/s", "max_speed_ms"),
    ("gmax", "حداکثر شتاب", "g", "max_accel_g"),
    ("vland", "سرعت فرود", "m/s", "landing_speed_ms"),
    ("burn", "مدت سوزش موتور", "s", "burn_time_s"),
    ("tapogee", "زمان رسیدن به اوج", "s", "apogee_time_s"),
    ("tflight", "مدت کل پرواز", "s", "flight_time_s"),
]

# ردیف‌های مرجع (فقط پیش‌بینی؛ واقعیتِ مستقیمی برای مقایسه ندارند)
_REF_ROWS = [
    ("وزن برخاست", "kg", "liftoff_mass_kg"),
    ("رانش میانگین موتور", "N", "thrust_avg_n"),
    ("نسبت رانش به وزن (میانگین سوزش)", "g", "initial_twr"),
    ("برد افقی بدون باد", "m", "range_no_wind_m"),
]

METHOD_NOTE = (
    "روش: عدد «پیش‌بینی» از شبیه‌سازی فیزیکی با همین پارامترهای فرم در لحظهٔ پرتاب "
    "است (اسنپ‌شات؛ اگر بعد از پرواز پارامترها را عوض کنید، مقایسه همچنان با "
    "پیش‌بینیِ همان لحظهٔ پرتاب انجام می‌شود). ستون «بازهٔ محتمل» با اجرای ۸۰ بار "
    "شبیه‌سازی و پخش تلرانس‌های واقع‌بینانه به‌دست آمده: فشار محفظه/رانش ±۱۵٪ "
    "(تلرانس متعارف موتورهای آماتوری)، وزن ±۵٪، سوخت ±۸٪ و قطر مؤثر/درگ ±۱۰٪؛ "
    "بازهٔ ۱۰ تا ۹۰ درصد یعنی «اگر همه‌چیز طبق دیتاشیت و اندازه‌گیری‌ها باشد، "
    "واقعیت با احتمال ۸۰٪ داخل این بازه می‌افتد»."
)

_LIMITS_NOTE = (
    "محدودیت‌ها (صادقانه): بدون بادسنج و بدون تله‌متری فشار محفظه، علت‌یابی "
    "«حدودی» است نه قطعی. مدل، بادِ واقعی، زاویهٔ نصب روی ریل، تلرانس موتور و "
    "ضریب درگ واقعی را نمی‌داند؛ برای همین ابتدا بازهٔ محتمل ملاک است و متن "
    "علت‌یابی فقط «محتمل‌ترین توضیح» را می‌گوید. برد افقی عمداً در جدول مقایسه "
    "نیست چون بادِ روز پرتاب (که مدل نمی‌داند) عامل غالب آن است."
)


def compare_snapshot(snapshot: Optional[dict], results: Optional[dict]) -> dict:
    """جدول مقایسه + علت‌یابی حدودی. بدون اسنپ‌شات/تحلیل هم کرش نمی‌کند."""
    out = {"available": False, "rows": [], "ref_rows": [], "causes": [],
           "method": METHOD_NOTE, "limits": _LIMITS_NOTE, "meta": {}}
    if not snapshot or not isinstance(snapshot, dict):
        return out
    summary = snapshot.get("summary") or {}
    bands = snapshot.get("bands") or {}
    actuals = _actual_from_results(results or {})
    out["meta"] = {"created_at": snapshot.get("created_at", "--")}

    rows = []
    dev_of: Dict[str, Optional[float]] = {}
    for key, label, unit, pred_key in _METRICS:
        pred = summary.get(pred_key)
        actual = actuals.get(key)
        pred = float(pred) if pred is not None else None
        actual = float(actual) if actual is not None else None
        band = bands.get(pred_key) or bands.get(key)
        dev = ((actual - pred) / pred * 100.0) if (pred and actual is not None) else None
        dev_of[key] = dev
        # ارزیابی
        if pred is None or actual is None:
            verdict, kind = "بدون داده برای مقایسه", "nodata"
        elif band and band[0] <= actual <= band[2]:
            verdict, kind = "داخل بازهٔ محتمل (۱۰-۹۰٪)", "ok"
        elif key == "vland" and pred > 0 and actual >= max(6.0, pred * 1.5):
            verdict, kind = "خیلی سریع‌تر از طراحی -- بررسی چتر", "major"
        elif dev is not None and abs(dev) <= 15.0:
            verdict, kind = "نزدیک پیش‌بینی", "ok"
        elif dev is not None and abs(dev) <= 30.0:
            verdict, kind = "انحراف متوسط", "minor"
        else:
            verdict, kind = "انحراف زیاد", "major"
        rows.append({"key": key, "label": label, "unit": unit, "pred": pred,
                     "band": band, "actual": actual, "dev_pct": dev,
                     "verdict": verdict, "kind": kind})
    out["rows"] = rows

    ref = []
    for label, unit, pred_key in _REF_ROWS:
        v = summary.get(pred_key)
        ref.append({"label": label, "unit": unit,
                    "pred": float(v) if v is not None else None})
    out["ref_rows"] = ref
    out["available"] = any(r["actual"] is not None for r in rows)

    # ---------------- علت‌یابی حدودی (قاعده‌محور) ----------------
    causes = []

    def add(title, text, severity="info"):
        causes.append({"title": title, "text": text, "severity": severity})

    d_apo = dev_of.get("apogee")
    d_vmax = dev_of.get("vmax")
    d_burn = dev_of.get("burn")
    d_vland = dev_of.get("vland")
    d_tfl = dev_of.get("tflight")
    vland_pair = next((r for r in rows if r["key"] == "vland"), None)

    if not out["available"]:
        add("دادهٔ واقعی کافی نیست",
            "در فایل پرواز، نشانگرهای لازم (اوج/سرعت/فرود) پیدا نشد؛ برای همین فقط "
            "اعداد پیش‌بینی نمایش داده می‌شود. برای مقایسهٔ کامل، فایل پرواز باید "
            "ستون‌های ارتفاع/سرعت و رویدادهای پرتاب تا فرود را داشته باشد.")
    else:
        # چتر -- ایمنی مقدم است
        if vland_pair and vland_pair["kind"] == "major":
            add("سامانهٔ بازیابی: فرود خیلی سریع‌تر از طراحی",
                f"سرعت فرود واقعی {vland_pair['actual']:.1f} متر بر ثانیه اما پیش‌بینی "
                f"{vland_pair['pred']:.1f} بود. محتمل‌ترین علت‌ها: چتر ناقص/کج باز شده، "
                "قاطرگ شدن طناب‌ها، پارگی پارچه یا جدا شدن چتر. این مورد ایمنی است "
                "-- قبل از پرواز بعدی، سامانهٔ بازیابی کامل بازبینی شود (اندازهٔ چتر، "
                "تاود و مسیر خروج، اتصالات).", "danger")
        elif d_vland is not None and d_vland <= -30.0:
            add("فرود آرام‌تر از طراحی",
                f"سرعت فرود {abs(d_vland):.0f}٪ کمتر از پیش‌بینی بود؛ چتر مؤثرتر از "
                "مشخصات کار کرده (سطح مؤثر بیشتر) یا باد صعودی در نزول کمک کرده. "
                "چتر بزرگ‌تر از نیاز هم یعنی راکت بیشتر با باد جابه‌جا می‌شود -- "
                "فاصلهٔ فرود را در پرواز بعدی ببینید.", "info")
        # موتور / درگ
        if d_apo is not None and d_apo <= -15.0:
            if (d_vmax is not None and d_vmax <= -12.0) or (d_burn is not None and d_burn >= 10.0):
                add("موتور ضعیف‌تر از دیتاشیت/محاسبه",
                    f"اوج {abs(d_apo):.0f}٪ کمتر از پیش‌بینی "
                    + (f"و حداکثر سرعت {abs(d_vmax):.0f}٪ کمتر " if (d_vmax is not None and d_vmax <= -12.0) else "")
                    + "از انتظار بود. وقتی «سرعتِ پایان سوزش» پایین می‌آید ولی مسیر "
                    "بقیهٔ پرواز منطقی است، محتمل‌ترین توضیح رانش کمتر موتور است: "
                    "تلرانس ساخت موتورهای آماتوری (±۱۵ تا ۲۰٪ در ایمپالس کل) کاملاً "
                    "معمول است؛ فشار محفظهٔ واقعی کمتر از تقریب، سوخت کمتر/ناگنخته "
                    "یا نشتی نازل هم همین اثر را می‌گذارد.", "warn")
            else:
                add("مقاومت هوا یا وزن بیشتر از مدل",
                    f"اوج {abs(d_apo):.0f}٪ کمتر از پیش‌بینی اما سرعتِ حوالی پایان سوزش "
                    "نزدیک پیش‌بینی بود؛ یعنی راکت با سرعت درست راه افتاده ولی در "
                    "مسیر، سریع‌تر از مدل کم شده. محتمل‌ترین علت‌ها: ضریب درگ واقعی "
                    "بیشتر از تخمین (فین‌ها/زبری/لبه‌ها)، وزن واقعی بیشتر از اندازه‌گیری، "
                    "یا زاویهٔ واقعی نصب روی ریل از ۹۰ درجهٔ فرم فاصله داشته "
                    "(کمترین انحراف زاویه، بخشی از انرژی را به مسیر افقی می‌برد).", "warn")
        elif d_apo is not None and d_apo >= 15.0:
            add("عملکرد بهتر از مدل",
                f"اوج {d_apo:.0f}٪ بیشتر از پیش‌بینی بود؛ محتمل‌ترین توضیح‌ها: موتور "
                "قوی‌تر از تلرانس پایینِ دیتاشیت، وزن واقعی کمتر از ثبت، یا درگ کمتر "
                "از تخمین. برای پرواز بعدی همین تلرانس‌ها را در ذهن داشته باشید و "
                "به پیش‌بینیِ تک‌عددی اعتماد نکنید -- بازه را ببینید.", "info")
        # زمان‌بندی نزول
        if d_tfl is not None and d_tfl >= 25.0 and (d_apo is not None and abs(d_apo) <= 15.0):
            add("نزول طولانی‌تر از پیش‌بینی",
                f"مدت پرواز {d_tfl:.0f}٪ بیشتر از پیش‌بینی بود در حالی که اوج نزدیک "
                "پیش‌بینی بود؛ یعنی بخش نزول/چتر طولانی‌تر شده: چتر مؤثرتر، باد "
                "صعودی یا شروع نزول با تاخیر. روی فاصله و جهت فرود نسبت به لانچر "
                "اثر گذاشته است.", "info")
        # جمع‌بندی
        if all((r["kind"] in ("ok", "nodata")) for r in rows):
            add("هم‌خوانی خوب مدل و واقعیت",
                "همهٔ کمیت‌های قابل مقایسه داخل بازهٔ محتمل یا نزدیک پیش‌بینی "
                "بودند. این یعنی مدل فیزیکی برنامه برای این راکت/موتور کالیبره "
                "است و می‌توانید برای پروازهای بعدی هم به بازه‌های آن اعتماد کنید "
                "(همچنان با تلرانس‌ها، نه عدد تک‌نقطه‌ای).", "ok")
    out["causes"] = causes
    return out
