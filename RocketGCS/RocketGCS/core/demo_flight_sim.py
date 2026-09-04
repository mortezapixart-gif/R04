# -*- coding: utf-8 -*-
"""
core/demo_flight_sim.py
--------------------------
پوستهٔ Qt برای شبیه‌ساز «حالت آموزشی».

تمام منطق فیزیکی و پروتکل در core/rocket_physics.py است (خالص و بدون Qt تا
در تست خودکار بدون نمایشگر هم قابل اجرا باشد). این فایل فقط کلاس
SimulatedFlightComputerLink را فراهم می‌کند که دقیقاً همان رابط عمومی
core.serial_comm.FlightComputerLink (متد send_command، سیگنال‌های
connected_signal/log_message، متد stop، صفت‌های mode/port/baudrate) را پیاده
می‌کند تا داشبورد و صفحات تحلیل بدون هیچ تغییری با آن کار کنند.

فیزیک واقعی: پرواز از پارامترهای واقعی کاربر (سوخت/وزن/زاویه/نازل/چتر/
ماژول‌ها) که با دستور SET_MISSION ارسال می‌شود ساخته می‌شود -- ببینید
build_demo_telemetry پیشنهادی در همان فایل rocket_physics.py.
"""
from __future__ import annotations
import time
from typing import Optional

from PySide6.QtCore import QThread, Signal

from core.rocket_physics import (          # noqa: F401 -- بازمهار برای سازگاری
    DEMO_HEALTH_CHECK_DURATION_SEC,
    DEMO_CALIB_DURATION_SEC,
    RocketFlightSimulator,
)

__all__ = [
    "SimulatedFlightComputerLink",
    "RocketFlightSimulator",
    "DEMO_HEALTH_CHECK_DURATION_SEC",
    "DEMO_CALIB_DURATION_SEC",
]


class SimulatedFlightComputerLink(QThread):
    """جایگزین core.serial_comm.FlightComputerLink برای «پورت فرضی» حالت آموزشی.

    همان رابط عمومی (send_command/connected_signal/log_message/stop) را دارد
    تا داشبورد و صفحهٔ ارتباط بدون تغییر با آن کار کنند."""
    connected_signal = Signal(bool)
    log_message = Signal(str)

    FAKE_PORT_NAME = "پورت فرضی (شبیه‌ساز آموزشی)"

    def __init__(self, mode: str = "DEMO", port: Optional[str] = None,
                 host: Optional[str] = None, baudrate: int = 115200):
        super().__init__()
        # host فقط برای سازگاری امضای سازنده با نسخهٔ قدیمی نگه داشته شده و
        # نادیده گرفته می‌شود (ماژول وای‌فای حذف و با لورا جایگزین شده است).
        self.mode = "DEMO"
        self.port = port or self.FAKE_PORT_NAME
        self.baudrate = baudrate
        self.sim = RocketFlightSimulator()

    def run(self):
        time.sleep(0.4)   # کمی تاخیر برای حس واقعی‌تر اتصال
        self.connected_signal.emit(True)
        self.log_message.emit("اتصال به پورت فرضی (حالت آموزشی) برقرار شد -- بدون سخت‌افزار واقعی.")

    def send_command(self, cmd: str) -> str:
        # همگام‌سازی زندهٔ «انتخاب فعلی ماژول‌ها» با شبیه‌ساز در حالت سکو --
        # فلوی کاربر: تست سلامت (مرحله ۱) «قبل از» ارسال اطلاعات مأموریت
        # (SET_MISSION) انجام می‌شود، پس شبیه‌ساز باید تله‌متری/وضعیت را
        # دقیقاً بر اساس همان چیزی که کاربر الان انتخاب کرده گزارش دهد.
        # پارامترهای فیزیکی پرواز همچنان فقط از SET_MISSION می‌آیند و پس از
        # ARM این همگام‌سازی دیگر اثری ندارد (پرواز منجمد است).
        if cmd.split(",")[0] in ("GET_TELEMETRY", "GET_STATUS", "GET_REC_STATUS"):
            try:
                from core.data_manager import data_manager
                self.sim.set_live_sensor_models(dict(data_manager.sensor_models))
            except Exception:
                pass
        return self.sim.handle_command(cmd)

    def write_csv(self, path: str) -> bool:
        """تولید و ذخیرهٔ CSV پرواز شبیه‌سازی‌شده -- فقط پس از فرود و فقط
        اگر ماژول کارت SD انتخاب شده باشد (دادهٔ خام روی راکت ذخیره می‌شود)."""
        return self.sim.write_csv(path)

    def stop(self):
        self.connected_signal.emit(False)
