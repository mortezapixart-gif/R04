# -*- coding: utf-8 -*-
"""
core/paths.py
---------------
مسیر ریشهٔ پروژه را به‌شکلی برمی‌گرداند که هم موقع اجرای عادی
(``python main.py``) و هم موقع اجرا به‌صورت فایل اجرایی ساخته‌شده با
PyInstaller (خروجی onedir یا onefile) درست کار کند.

نکتهٔ مهم: برای ماژول‌های پایتونِ داخل بستهٔ PyInstaller، ``__file__`` به
یک مسیر واقعی روی دیسک اشاره نمی‌کند (چون این فایل‌ها داخل آرشیو فشرده‌شدهٔ
برنامه‌اند، نه پوشه‌های عادی) -- پس محاسبهٔ مسیر «assets» بر اساس
``__file__`` هر ماژول (مثل ``ui/splash_screen.py``) در نسخهٔ فریزشده خراب
می‌شود. راه‌حل درست: از ``sys.frozen`` و ``sys._MEIPASS`` (یا پوشهٔ کنار
فایل اجرایی) استفاده کنیم، نه ``__file__`` تک‌تک ماژول‌ها.
"""
import os
import sys


def get_base_dir() -> str:
    """پوشهٔ ریشهٔ پروژه (حاوی assets/, core/, pages/, ui/) -- در حالت توسعه
    همان پوشهٔ حاوی main.py است؛ در نسخهٔ فریزشده، پوشهٔ استخراج‌شدهٔ موقت
    (onefile) یا پوشهٔ کنار فایل exe (onedir)."""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    # core/paths.py -> بالا رفتن یک پله تا ریشهٔ پروژه
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def asset_path(*parts: str) -> str:
    """مسیر کامل یک فایل داخل پوشهٔ assets/ (مثلاً asset_path('kafna_logo.png'))."""
    return os.path.join(get_base_dir(), "assets", *parts)


def get_data_dir(*parts: str) -> str:
    """پوشهٔ قابل‌نوشتنِ داده‌های کاربر (آرشیو پروازها و مانند آن).

    برخلاف asset_path (فقط-خواندنی، کنار فایل اجرایی)، این پوشه باید همیشه
    قابل نوشتن باشد -- حتی وقتی برنامه داخل C:\\Program Files نصب شده و
    کاربر عادی (بدون دسترسی ادمین) اجرایش می‌کند. به همین دلیل از پوشهٔ
    دادهٔ کاربر سیستم‌عامل استفاده می‌شود (%APPDATA% در ویندوز، یا خانهٔ
    کاربر در سایر سیستم‌عامل‌ها)، نه پوشهٔ کنار فایل اجرایی."""
    base = os.getenv("APPDATA") or os.path.expanduser("~")
    path = os.path.join(base, "RocketGCS", *parts)
    os.makedirs(path, exist_ok=True)
    return path


def get_reports_dir() -> str:
    """پوشهٔ خروجی‌های گزارش (PDF رنگی/سیاه‌وسفید و Excel) -- زیرپوشهٔ
    «گزارش‌ها» داخل پوشهٔ دادهٔ کاربر برنامه."""
    return get_data_dir("گزارش‌ها")


def get_raw_flights_dir() -> str:
    """پوشهٔ دادهٔ خام پروازها (CSV تله‌متری + مشخصات مأموریت) برای بازتحلیل
    و اشتراک با تیم دیگر. جدا از خروجی PDF/Excel در «گزارش‌ها» است."""
    return get_data_dir("گزارش‌های خام")


def sanitize_filename_part(text: str) -> str:
    """حذف کاراکترهای غیرمجاز در نام فایل ویندوز (\\ / : * ? " < > |) و یکدست‌
    کردن فاصله‌ها -- چون مثلاً تاریخ شمسی با «/» جدا می‌شود که در نام فایل
    مجاز نیست."""
    text = str(text or "").strip()
    for ch in '\\/:*?"<>|':
        text = text.replace(ch, "-")
    text = "-".join(text.split())
    return text or "نامشخص"


def build_report_filename(jalali_date: str, flight_number: str, ext: str, suffix: str = "") -> str:
    """نام‌گذاری یکدست فایل‌های خروجی: <تاریخ‌شمسی>_<شماره‌پرواز>[_<پسوند>].<ext>

    تاریخ همیشه شمسی است (هرگز میلادی در نام فایل نمی‌آید).
    مثال‌ها:
        1405-06-12_F-014.pdf
        1405-06-12_F-014_bw.pdf
        1405-06-12_F-014.xlsx
        1405-06-12_F-014_خام.csv
    """
    from core.jalali import jalali_date_for_filename
    date_part = jalali_date_for_filename(jalali_date)
    flight_part = sanitize_filename_part(flight_number)
    name = f"{date_part}_{flight_part}"
    if suffix:
        name += f"_{sanitize_filename_part(suffix)}"
    return f"{name}.{ext.lstrip('.')}"

