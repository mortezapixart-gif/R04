# -*- coding: utf-8 -*-
"""
core/serial_comm.py
---------------------
لایهٔ ارتباط نرم‌افزار با سخت‌افزار.

معماری دو مرحله‌ای:

  الف) «ایستگاه زمینی» = یک برد کمکی شامل ماژول لورا RA-02 (تراشهٔ SX1278،
       باند ۴۳۳MHz) + آردوینو + ماژول WiFi. این ایستگاه از یک سو به لورای
       روی راکت و از سوی دیگر به لپ‌تاپ/سیستم وصل می‌شود. اتصال ایستگاه به
       سیستم به دو صورت ممکن است:
          - USB  : پورت سریال مستقیم به آردوینوی ایستگاه.
          - WiFi : سوکت TCP به ماژول WiFi ایستگاه (IP یا IP:port).

  ب) «راکت» = کامپیوتر پرواز داخل راکت. اتصال به راکت به سه صورت است:
          - از طریق ایستگاه زمینی (لورا): دستورها از همان لینک ایستگاه عبور
            کرده و ایستگاه آن‌ها را رادیویی به راکت می‌رساند.
          - USB مستقیم به برد کامپیوتر پرواز: مخصوص تخلیهٔ کارت SD/فیلم‌ها یا
            به‌روزرسانی فریم‌ور.
          - پورت آموزشی (شبیه‌ساز): core/demo_flight_sim.py

بنابراین یک کلاس عمومی FlightComputerLink هر دو حامل (سریال و سوکت WiFi) را
پیاده می‌کند؛ چون از دید نرم‌افزار هر دو صرفاً دستور متنی می‌فرستند و پاسخ
متنی می‌گیرند. هر لینک در یک QThread جدا باز می‌شود تا رابط کاربری قفل نشود.

پروتکل متنی (خط‌به‌خط، پایان‌دهنده \n):
        PING              -> PONG,<fw_version>            (راکت)
        STATION_PING      -> PONG,STATION,<fw_version>    (خودِ ایستگاه زمینی)
        LORA_LINK         -> ACK:LORA_LINKED یا ERR:LORA_FAIL
                             (به ایستگاه دستور می‌دهد لینک رادیویی با راکت را برقرار کند)
        SET_MISSION,<json> -> ACK:MISSION_OK
        GET_STATUS        -> STATUS,<battery>,<bmp>,<mpu>,<sd>,<camera>
                             [,<current_ma>,<pyro1_ohm>,<pyro2_ohm>]
                             (فیلدهای پایانی اختیاری: پنل «سلامت توان» HUD)
        GET_TELEMETRY     -> TELEM,<t>,<altitude>,<vv>,<pressure>,<temp>,<ax>,<ay>,<az>
                             [,<humidity>,<temp_aht>,<uv>]
        GET_REC_STATUS    -> REC_STATUS,BMP280=1,MPU6050=1,AHT21=1,UV=1,CAMERA=1,SD=1
        DOWNLOAD          -> شروع دریافت فایل CSV پرواز
        ERASE             -> ACK:ERASE_OK   (فرمت کارت SD)
        ENTER_BOOTLOADER  -> ACK:BOOTLOADER (پرش به bootloader برای فلش فریم‌ور -- فقط USB)
"""
from __future__ import annotations
import socket
import time
from typing import Optional

from PySide6.QtCore import QThread, Signal

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    serial = None

WIFI_DEFAULT_PORT = 8080   # پورت پیش‌فرض سوکت TCP ماژول WiFi ایستگاه زمینی


class FlightComputerLink(QThread):
    connected_signal = Signal(bool)
    log_message = Signal(str)

    def __init__(self, mode: str = "USB", port: Optional[str] = None,
                 host: Optional[str] = None, baudrate: int = 115200):
        super().__init__()
        # "USB"  = سریال مستقیم (به آردوینوی ایستگاه زمینی یا برد راکت)
        # "WiFi" = سوکت TCP به ماژول WiFi ایستگاه زمینی
        # "LoRa" = برچسب منطقی اتصال به راکت از طریق ایستگاه زمینی (حامل فیزیکی
        #          همان لینک ایستگاه است -- این کلاس مستقیم با mode=USB/WiFi باز می‌شود)
        self.mode = mode
        self.port = port
        self.host = host          # برای WiFi: "IP" یا "IP:port"
        self.baudrate = baudrate
        self._ser = None
        self._sock = None
        self._sock_file = None

    @staticmethod
    def list_usb_ports():
        if serial is None:
            return []
        return [p.device for p in serial.tools.list_ports.comports()]

    def run(self):
        try:
            if self.mode == "WiFi":
                self._connect_wifi()
            else:
                self._connect_serial()
        except Exception as e:
            self.log_message.emit(f"خطا در اتصال: {e}")
            self.connected_signal.emit(False)

    def _connect_serial(self):
        """اتصال سریال -- برای USB (آردوینوی ایستگاه زمینی یا برد راکت)."""
        if serial is None:
            self.log_message.emit("کتابخانه pyserial نصب نیست.")
            self.connected_signal.emit(False)
            return
        self._ser = serial.Serial(self.port, self.baudrate, timeout=1)
        self.connected_signal.emit(True)
        self.log_message.emit(f"اتصال USB روی {self.port} برقرار شد.")

    def _connect_wifi(self):
        """اتصال سوکت TCP به ماژول WiFi ایستگاه زمینی. مقدار host می‌تواند
        «IP» یا «IP:port» باشد؛ در نبود پورت، WIFI_DEFAULT_PORT استفاده می‌شود."""
        raw = (self.host or "").strip()
        if not raw:
            self.log_message.emit("آدرس IP ایستگاه زمینی وارد نشده است.")
            self.connected_signal.emit(False)
            return
        if ":" in raw:
            ip, _, port_str = raw.partition(":")
            try:
                port = int(port_str)
            except ValueError:
                port = WIFI_DEFAULT_PORT
        else:
            ip, port = raw, WIFI_DEFAULT_PORT
        self._sock = socket.create_connection((ip.strip(), port), timeout=5)
        self._sock.settimeout(1.0)
        self._sock_file = self._sock.makefile("rwb", buffering=0)
        self.connected_signal.emit(True)
        self.log_message.emit(f"اتصال WiFi به ایستگاه زمینی روی {ip}:{port} برقرار شد.")

    def send_command(self, cmd: str) -> str:
        """ارسال یک دستور و دریافت یک خط پاسخ (Blocking).

        برای اتصال به راکت از راه لورا، همین لینکِ ایستگاه زمینی دستور را
        رادیویی به راکت می‌رساند و پاسخ راکت را برمی‌گرداند -- از دید نرم‌افزار
        تفاوتی با سریال معمولی ندارد."""
        data = (cmd + "\n").encode("utf-8")
        if self._ser is not None:
            self._ser.write(data)
            time.sleep(0.05)
            return self._ser.readline().decode("utf-8", errors="ignore").strip()
        if self._sock_file is not None:
            try:
                self._sock_file.write(data)
                self._sock_file.flush()
                return self._sock_file.readline().decode("utf-8", errors="ignore").strip()
            except (socket.timeout, OSError):
                return ""
        return ""

    def stop(self):
        if self._ser is not None:
            try:
                self._ser.close()
            except Exception:
                pass
            self._ser = None
        if self._sock_file is not None:
            try:
                self._sock_file.close()
            except Exception:
                pass
            self._sock_file = None
        if self._sock is not None:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None
        self.connected_signal.emit(False)
