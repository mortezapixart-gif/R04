# -*- coding: utf-8 -*-
"""
core/jalali.py
-----------------
تبدیل تاریخ میلادی به شمسی (جلالی) بدون نیاز به کتابخانهٔ خارجی
(چون در محیط توسعه دسترسی به نصب پکیج جدید ممکن نیست).

پیاده‌سازی بر پایهٔ الگوریتم شناخته‌شده و رایج Kazimierz M. Borkowski برای
تبدیل تقویم جلالی (مورد استفاده در بسیاری از کتابخانه‌های متن‌باز تبدیل
تاریخ فارسی).
"""
from __future__ import annotations
import datetime

_G_DAYS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
_J_DAYS = [31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, 29]


def _is_gleap(gy: int) -> bool:
    return (gy % 4 == 0 and gy % 100 != 0) or (gy % 400 == 0)


def gregorian_to_jalali(gy: int, gm: int, gd: int) -> tuple[int, int, int]:
    gy2 = gy - 1600
    gm2 = gm - 1
    gd2 = gd - 1

    g_day_no = 365 * gy2 + (gy2 + 3) // 4 - (gy2 + 99) // 100 + (gy2 + 399) // 400
    for i in range(gm2):
        g_day_no += _G_DAYS[i]
    if gm2 > 1 and _is_gleap(gy):
        g_day_no += 1
    g_day_no += gd2

    j_day_no = g_day_no - 79

    j_np = j_day_no // 12053
    j_day_no %= 12053

    jy = 979 + 33 * j_np + 4 * (j_day_no // 1461)
    j_day_no %= 1461

    if j_day_no >= 366:
        jy += (j_day_no - 1) // 365
        j_day_no = (j_day_no - 1) % 365

    jm = 12
    for i in range(11):
        if j_day_no < _J_DAYS[i]:
            jm = i + 1
            break
        j_day_no -= _J_DAYS[i]
    jd = j_day_no + 1

    return jy, jm, jd


def gregorian_date_to_jalali_str(d: datetime.date) -> str:
    jy, jm, jd = gregorian_to_jalali(d.year, d.month, d.day)
    return f"{jy:04d}/{jm:02d}/{jd:02d}"


def jalali_today_filename() -> str:
    """تاریخ شمسی امروز برای نام فایل: 1405-06-12."""
    d = datetime.date.today()
    jy, jm, jd = gregorian_to_jalali(d.year, d.month, d.day)
    return f"{jy:04d}-{jm:02d}-{jd:02d}"


def jalali_date_for_filename(date_val=None) -> str:
    """تاریخ شمسی مناسب نام فایل (همیشه جلالی، هرگز میلادی).

    ورودی می‌تواند تاریخ شمسی («1405/06/12») یا میلادی («2026-09-03») باشد.
    اگر خالی یا نامعتبر باشد، امروز شمسی برمی‌گردد.
    """
    s = str(date_val or "").strip()
    if s.lower() in ("", "none", "null", "--"):
        return jalali_today_filename()

    token = s.split()[0]
    year_txt = "".join(ch for ch in token[:4] if ch.isdigit())
    if len(year_txt) == 4 and 1300 <= int(year_txt) <= 1599:
        cleaned = token.replace("/", "-").replace(".", "-").replace("_", "-")
        parts = [p for p in cleaned.split("-") if p]
        if len(parts) >= 3:
            try:
                return f"{int(parts[0]):04d}-{int(parts[1]):02d}-{int(parts[2][:2]):02d}"
            except ValueError:
                pass
        return jalali_today_filename()

    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d-%m-%Y", "%d/%m/%Y", "%Y%m%d"):
        try:
            dt = datetime.datetime.strptime(token, fmt).date()
        except ValueError:
            continue
        if dt.year >= 1600:
            jy, jm, jd = gregorian_to_jalali(dt.year, dt.month, dt.day)
            return f"{jy:04d}-{jm:02d}-{jd:02d}"
        if 1300 <= dt.year <= 1599:
            return f"{dt.year:04d}-{dt.month:02d}-{dt.day:02d}"

    try:
        dt = datetime.date.fromisoformat(token.replace("/", "-")[:10])
        if dt.year >= 1600:
            jy, jm, jd = gregorian_to_jalali(dt.year, dt.month, dt.day)
            return f"{jy:04d}-{jm:02d}-{jd:02d}"
    except ValueError:
        pass
    return jalali_today_filename()
