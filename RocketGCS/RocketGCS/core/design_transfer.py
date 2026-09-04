# -*- coding: utf-8 -*-
"""رابط انتقال طرح بین «طراح راکت» و «ایستگاه».

طراح و ایستگاه دو پردازش جدا هستند؛ بنابراین به‌جای import کردن وضعیت یک
پنجره از پنجرهٔ دیگر، یک پاکت JSON اتمی در پوشهٔ دادهٔ مشترک کاربر نوشته می‌شود.
ایستگاه آن را با تایمر کوتاه می‌خواند و پس از اعمال موفق حذف می‌کند. این روش
هم در اجرای پایتونی و هم در نسخهٔ نصب‌شده/فریزشده کار می‌کند و اگر ایستگاه
هنگام فشردن دکمه باز نباشد، طرح تا اجرای بعدی باقی می‌ماند.
"""
from __future__ import annotations

import datetime as _datetime
import json
import os
import uuid
from typing import Any, Dict, Optional, Tuple

from core.paths import get_data_dir

TRANSFER_FILENAME = "rocket_design_transfer.json"
TRANSFER_SCHEMA_VERSION = 1


def transfer_path() -> str:
    """مسیر فایل صف انتقال (قابل نوشتن برای هر دو برنامه)."""
    return os.path.join(get_data_dir("تبادل"), TRANSFER_FILENAME)


def _utc_now() -> str:
    return _datetime.datetime.now(_datetime.timezone.utc).isoformat()


def write_design_transfer(payload: Dict[str, Any]) -> str:
    """یک طرح را به‌صورت اتمی در صف انتقال بنویسد و مسیر فایل را برگرداند.

    ``os.replace`` باعث می‌شود ایستگاه هیچ‌وقت فایل نیمه‌نوشته را نخواند.
    ``payload`` همان قرارداد نسخه‌دار بین دو برنامه است و این تابع عمداً آن
    را تغییر نمی‌دهد.
    """
    if not isinstance(payload, dict):
        raise TypeError("طرح باید یک شیء JSON باشد")

    path = transfer_path()
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    envelope = {
        "schema_version": TRANSFER_SCHEMA_VERSION,
        "transfer_id": uuid.uuid4().hex,
        "created_at": _utc_now(),
        "source": "RocketDesigner",
        "payload": payload,
    }
    temp = f"{path}.{os.getpid()}.tmp"
    try:
        with open(temp, "w", encoding="utf-8") as fh:
            json.dump(envelope, fh, ensure_ascii=False, indent=2)
            fh.flush()
            try:
                os.fsync(fh.fileno())
            except OSError:
                # روی بعضی فایل‌سیستم‌ها fsync در پوشهٔ کاربر در دسترس نیست؛
                # اتمی‌بودن replace همچنان برقرار است.
                pass
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            try:
                os.remove(temp)
            except OSError:
                pass
    return path


def read_design_transfer(path: Optional[str] = None) -> Optional[Tuple[str, Dict[str, Any]]]:
    """پاکت معتبر را بخواند؛ خروجی ``(transfer_id, payload)`` یا ``None``.

    خطای JSON/نسخهٔ ناشناخته در اینجا استثنا نمی‌شود؛ ایستگاه در poll بعدی
    دوباره فرصت خواندن دارد و فایل خراب را خودکار از بین نمی‌برد.
    """
    path = path or transfer_path()
    try:
        with open(path, encoding="utf-8") as fh:
            envelope = json.load(fh)
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(envelope, dict):
        return None
    if envelope.get("schema_version") != TRANSFER_SCHEMA_VERSION:
        return None
    transfer_id = str(envelope.get("transfer_id") or "").strip()
    payload = envelope.get("payload")
    if not transfer_id or not isinstance(payload, dict):
        return None
    return transfer_id, payload


def remove_design_transfer(path: Optional[str] = None) -> None:
    """فایل صف را پس از اعمال موفق حذف کند (غیرفعال‌کردن خطا بی‌خطر است)."""
    try:
        os.remove(path or transfer_path())
    except OSError:
        pass
