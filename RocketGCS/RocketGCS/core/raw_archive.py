# -*- coding: utf-8 -*-
"""
core/raw_archive.py
-------------------
بستهٔ دادهٔ خام یک پرواز: CSV تله‌متری + مشخصات مأموریت/نازل.

منبع نمودارها و گزارش‌ها همین دادهٔ خام است. نتایج تحلیل داخل بسته ذخیره
نمی‌شوند تا اگر فرمول‌ها یا قالب اکسل عوض شد، بازتحلیل از روی CSV ممکن باشد.

پوشهٔ پیش‌فرض: %APPDATA%/RocketGCS/گزارش‌های خام/
هر پرواز یک زیرپوشه است:
    flight.csv      تله‌متری خام
    manifest.json   مأموریت / نازل / سنسور / پیش‌بینی لحظهٔ پرتاب
    راهنما.txt      توضیح برای تیم دیگر
"""
from __future__ import annotations

import json
import os
import shutil
from dataclasses import asdict, fields, is_dataclass
from datetime import datetime
from typing import Any, Iterable, Optional

import pandas as pd

from core.paths import get_data_dir, get_raw_flights_dir, sanitize_filename_part

MANIFEST_NAME = "manifest.json"
CSV_NAME = "flight.csv"
README_NAME = "راهنما.txt"
BUNDLE_VERSION = 2

README_TEXT = (
    "این پوشه دادهٔ خام یک پرواز راکت است.\n"
    "\n"
    "  flight.csv      تله‌متری خام (منبع نمودارها و گزارش‌ها)\n"
    "  manifest.json   مشخصات مأموریت، نازل، سنسور و پیش‌بینی لحظهٔ پرتاب\n"
    "\n"
    "برای باز کردن در برنامه:\n"
    "۱) کل این پوشه را داخل «گزارش‌های خام» کپی کنید\n"
    "۲) در صفحهٔ «تهیه گزارش» دکمهٔ «بازخوانی لیست» را بزنید\n"
    "۳) پرواز را انتخاب و «فعال کردن پرواز انتخاب‌شده» را بزنید\n"
    "\n"
    "دادهٔ خام نگه داشته می‌شود تا اگر قالب اکسل یا فرمول‌های تحلیل عوض شد،\n"
    "بتوان دوباره از روی همین فایل تحلیل و گزارش گرفت.\n"
)


def get_legacy_archive_dir() -> str:
    """آرشیو قدیمی (flight_archive) -- هنوز در لیست خوانده می‌شود."""
    return get_data_dir("flight_archive")


def default_scan_roots() -> list[tuple[str, bool]]:
    """(مسیر ریشه، آیا آرشیو قدیمی است)."""
    return [
        (get_raw_flights_dir(), False),
        (get_legacy_archive_dir(), True),
    ]


def _json_safe(obj: Any):
    """تبدیل مقدار به چیزی که json.dump بپذیرد (numpy / inf / dataclass)."""
    if obj is None or isinstance(obj, (str, bool, int)):
        return obj
    if isinstance(obj, float):
        if obj != obj or obj in (float("inf"), float("-inf")):
            return None
        return obj
    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_json_safe(v) for v in obj]
    if is_dataclass(obj) and not isinstance(obj, type):
        return _json_safe(asdict(obj))
    try:
        import numpy as np
        if isinstance(obj, np.generic):
            return _json_safe(obj.item())
        if isinstance(obj, np.ndarray):
            return _json_safe(obj.tolist())
    except Exception:
        pass
    if hasattr(obj, "item"):
        try:
            return _json_safe(obj.item())
        except Exception:
            pass
    return str(obj)


def _to_dict(obj: Any) -> dict:
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return dict(obj)
    if is_dataclass(obj) and not isinstance(obj, type):
        return asdict(obj)
    out = {}
    cls = type(obj)
    for src in (getattr(cls, "__dict__", {}), getattr(obj, "__dict__", {})):
        for k, v in src.items():
            if str(k).startswith("_") or callable(v) or isinstance(v, (classmethod, staticmethod, property)):
                continue
            out[k] = v
    for k, v in list(out.items()):
        try:
            out[k] = getattr(obj, k)
        except Exception:
            pass
    return out


def dataclass_from_dict(cls, data: Any):
    """ساخت dataclass با نادیده‌گرفتن کلیدهای ناشناخته (سازگاری نسخه‌ها)."""
    if not isinstance(data, dict) or not data:
        return None
    known = {f.name: f for f in fields(cls)}
    kwargs = {}
    for k, v in data.items():
        if k not in known or v is None:
            continue
        kwargs[k] = v
    if not kwargs:
        return None
    try:
        return cls(**kwargs)
    except TypeError:
        return None


def bundle_folder_name(mission: Any, label: str = "") -> str:
    """نام پایدار پوشه: تاریخ‌شمسی_شماره‌پرواز_نام‌راکت."""
    from core.jalali import jalali_date_for_filename

    jalali = jalali_date_for_filename(
        getattr(mission, "jalali_date", None)
        or (mission.get("jalali_date") if isinstance(mission, dict) else None)
        or getattr(mission, "date", None)
        or (mission.get("date") if isinstance(mission, dict) else None)
        or ""
    )

    def _field(name: str) -> str:
        if isinstance(mission, dict):
            return str(mission.get(name) or "").strip()
        return str(getattr(mission, name, "") or "").strip()

    flight = sanitize_filename_part(_field("flight_number"))
    rocket = sanitize_filename_part(_field("rocket_name"))
    parts = [sanitize_filename_part(jalali)]
    if flight and flight != "نامشخص":
        parts.append(flight)
    if rocket and rocket != "نامشخص":
        parts.append(rocket)
    extra = sanitize_filename_part(label) if label else ""
    if extra and extra != "نامشخص":
        parts.append(extra)
    if len(parts) == 1 and (not flight or flight == "نامشخص"):
        parts.append(datetime.now().strftime("%H%M%S"))
    return "_".join(parts)


def save_raw_flight(
    *,
    dest_root: str,
    df: pd.DataFrame,
    mission: Any,
    motor: Any = None,
    sensor_models: Optional[dict] = None,
    prediction: Any = None,
    source_csv: Optional[str] = None,
    label: str = "",
) -> str:
    """نوشتن/به‌روزرسانی بستهٔ خام. نام پوشه را برمی‌گرداند."""
    os.makedirs(dest_root, exist_ok=True)
    name = bundle_folder_name(mission, label)
    folder = os.path.join(dest_root, name)
    os.makedirs(folder, exist_ok=True)

    dest_csv = os.path.join(folder, CSV_NAME)
    copied = False
    if source_csv and os.path.isfile(source_csv):
        if os.path.abspath(source_csv) != os.path.abspath(dest_csv):
            shutil.copy2(source_csv, dest_csv)
        copied = True
    if not copied:
        df.to_csv(dest_csv, index=False, encoding="utf-8-sig")

    mission_d = _to_dict(mission)
    payload = {
        "version": BUNDLE_VERSION,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "source_csv": os.path.basename(source_csv) if source_csv else CSV_NAME,
        "row_count": int(len(df)),
        "columns": [str(c) for c in df.columns],
        "mission": mission_d,
        "motor": _to_dict(motor),
        "sensor_models": dict(sensor_models) if sensor_models else {},
        "prediction": prediction,
    }
    with open(os.path.join(folder, MANIFEST_NAME), "w", encoding="utf-8") as f:
        json.dump(_json_safe(payload), f, ensure_ascii=False, indent=2)

    readme_path = os.path.join(folder, README_NAME)
    if not os.path.isfile(readme_path):
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(README_TEXT)
    return name


def _csv_row_count(path: str) -> int:
    try:
        with open(path, "r", encoding="utf-8-sig", errors="replace") as f:
            n = sum(1 for _ in f)
        return max(0, n - 1)
    except OSError:
        return 0


def _read_manifest(path: str) -> Optional[dict]:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _folder_csv(folder: str) -> Optional[str]:
    preferred = os.path.join(folder, CSV_NAME)
    if os.path.isfile(preferred):
        return preferred
    try:
        names = os.listdir(folder)
    except OSError:
        return None
    csvs = [
        os.path.join(folder, n)
        for n in names
        if n.lower().endswith(".csv") and os.path.isfile(os.path.join(folder, n))
    ]
    return csvs[0] if csvs else None


def _item_from_folder(folder: str, *, legacy: bool) -> Optional[dict]:
    csv_path = _folder_csv(folder)
    if not csv_path:
        return None
    manifest_path = os.path.join(folder, MANIFEST_NAME)
    data = _read_manifest(manifest_path) if os.path.isfile(manifest_path) else None
    mi = (data or {}).get("mission") or {}
    jalali = (mi.get("jalali_date") or "").strip()
    date = (mi.get("date") or "").strip()
    rows = (data or {}).get("row_count")
    if not rows:
        rows = _csv_row_count(csv_path)
    try:
        mtime = os.path.getmtime(csv_path)
    except OSError:
        mtime = 0.0
    return {
        "name": os.path.basename(folder),
        "path": os.path.abspath(folder),
        "csv_path": os.path.abspath(csv_path),
        "kind": "folder",
        "has_manifest": bool(data),
        "legacy": legacy,
        "flight_number": mi.get("flight_number") or "",
        "rocket_name": mi.get("rocket_name") or "",
        "date": date,
        "jalali_date": jalali,
        "rows": int(rows or 0),
        "mtime": mtime,
    }


def _item_from_csv(path: str, *, legacy: bool) -> Optional[dict]:
    if not os.path.isfile(path):
        return None
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        mtime = 0.0
    return {
        "name": os.path.basename(path),
        "path": os.path.abspath(path),
        "csv_path": os.path.abspath(path),
        "kind": "csv",
        "has_manifest": False,
        "legacy": legacy,
        "flight_number": "",
        "rocket_name": "",
        "date": "",
        "jalali_date": "",
        "rows": _csv_row_count(path),
        "mtime": mtime,
    }


def list_raw_flights(
    roots: Optional[Iterable[tuple[str, bool]]] = None,
) -> list[dict]:
    """لیست پروازهای خام (جدیدترین اول). پوشه یا CSV تکی را می‌پذیرد."""
    items: list[dict] = []
    seen: set[str] = set()
    for root, legacy in (roots if roots is not None else default_scan_roots()):
        if not root or not os.path.isdir(root):
            continue
        try:
            names = os.listdir(root)
        except OSError:
            continue
        for name in names:
            if name.startswith("."):
                continue
            path = os.path.join(root, name)
            key = os.path.abspath(path)
            if key in seen:
                continue
            item = None
            if os.path.isdir(path):
                item = _item_from_folder(path, legacy=legacy)
            elif name.lower().endswith(".csv"):
                item = _item_from_csv(path, legacy=legacy)
            if item:
                seen.add(key)
                items.append(item)
    items.sort(key=lambda x: x.get("mtime") or 0, reverse=True)
    return items


def format_list_label(item: dict) -> str:
    """برچسب یک ردیف لیست برای صفحهٔ تهیه گزارش."""
    from core.report_text import to_jalali_date

    raw_date = item.get("jalali_date") or item.get("date") or ""
    date = to_jalali_date(raw_date) if raw_date else "--"
    if date in ("--", ""):
        date = "--"
    flight = item.get("flight_number") or "--"
    rocket = item.get("rocket_name") or "--"
    parts = [str(date), f"پرواز {flight}", str(rocket)]
    rows = item.get("rows")
    if rows:
        parts.append(f"{int(rows)} ردیف")
    if not item.get("has_manifest"):
        parts.append("بدون مشخصات مأموریت")
    if item.get("legacy"):
        parts.append("آرشیو قدیمی")
    if item.get("kind") == "csv":
        parts.append(item.get("name") or "CSV")
    return "   |   ".join(parts)


def resolve_raw_flight(
    name_or_path: str,
    roots: Optional[Iterable[tuple[str, bool]]] = None,
) -> Optional[str]:
    """مسیر پوشه یا CSV را از مسیر کامل یا نام پوشه پیدا می‌کند."""
    if not name_or_path:
        return None
    if os.path.exists(name_or_path):
        return os.path.abspath(name_or_path)
    for root, _legacy in (roots if roots is not None else default_scan_roots()):
        cand = os.path.join(root, name_or_path)
        if os.path.exists(cand):
            return os.path.abspath(cand)
    return None


def load_raw_flight(path: str) -> Optional[dict]:
    """خواندن بستهٔ خام. تحلیل را اجرا نمی‌کند -- فقط CSV و manifest."""
    if not path or not os.path.exists(path):
        return None
    folder = path if os.path.isdir(path) else os.path.dirname(path)
    csv_path = None
    data = None
    if os.path.isdir(path):
        csv_path = _folder_csv(path)
        manifest_path = os.path.join(path, MANIFEST_NAME)
        if os.path.isfile(manifest_path):
            data = _read_manifest(manifest_path)
    else:
        csv_path = path
        sibling = os.path.join(folder, MANIFEST_NAME)
        if os.path.isfile(sibling):
            data = _read_manifest(sibling)

    if not csv_path or not os.path.isfile(csv_path):
        return None
    try:
        df = pd.read_csv(csv_path)
    except (OSError, pd.errors.ParserError, UnicodeDecodeError):
        return None
    df.columns = [str(c).strip() for c in df.columns]
    return {
        "df": df,
        "mission": (data or {}).get("mission"),
        "motor": (data or {}).get("motor"),
        "sensor_models": (data or {}).get("sensor_models"),
        "prediction": (data or {}).get("prediction") if data else None,
        "has_manifest": bool(data),
        "csv_path": os.path.abspath(csv_path),
        "folder": os.path.abspath(folder) if os.path.isdir(path) else None,
    }
