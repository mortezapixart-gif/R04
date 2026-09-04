# -*- coding: utf-8 -*-
"""صفحهٔ ارتباط با کامپیوتر پرواز (آخرین صفحهٔ منو).

معماری اتصال دو مرحله‌ای -- مطابق سخت‌افزار واقعی:

  • باکس سمت راست «اتصال به ایستگاه زمینی»: ایستگاه زمینی یک برد کمکی است
    (ماژول لورا RA-02 + آردوینو + ماژول WiFi). از یک سو رادیویی به لورای
    داخل راکت وصل می‌شود و از سوی دیگر با USB یا WiFi به این سیستم. کاربر
    ابتدا باید از این باکس به ایستگاه وصل شود.

  • باکس سمت چپ «اتصال به راکت»: سه حالت دارد --
        ۱) ایستگاه زمینی (لورا): نیازمند اتصال قبلی به ایستگاه؛ برنامه به
           ایستگاه دستور می‌دهد لینک رادیویی با راکت را برقرار و یک PING
           موفق بگیرد.
        ۲) USB مستقیم به برد راکت: برای تخلیهٔ کارت SD/فیلم‌ها یا به‌روزرسانی
           فریم‌ور.
        ۳) پورت آموزشی (شبیه‌ساز).

پس از موفقیت هر باکس، پس‌زمینهٔ آن سبز کم‌رنگ و در صورت شکست، قرمز کم‌رنگ
می‌شود تا کاربر وضعیت را در یک نگاه ببیند.
"""
import json
import os
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QPushButton,
                                QLabel, QTextEdit, QFileDialog, QFrame,
                                QLineEdit, QMessageBox, QSizePolicy)
from PySide6.QtCore import Qt, QTimer
from ui.widgets import page_title
from core.data_manager import data_manager
from core.serial_comm import FlightComputerLink
from core.demo_flight_sim import SimulatedFlightComputerLink

# رنگ پس‌زمینهٔ باکس‌ها بر اساس وضعیت اتصال
BOX_NEUTRAL = "QFrame#CommunicationBox { background-color:#202833; border:1px solid #3d4a5c; border-radius:12px; }"
BOX_OK = "QFrame#CommunicationBox { background-color:#183524; border:1px solid #35d07f; border-radius:12px; }"
BOX_FAIL = "QFrame#CommunicationBox { background-color:#3a2025; border:1px solid #ef5350; border-radius:12px; }"

# گزینه‌های فیلد کشویی «اتصال به راکت»
ROCKET_VIA_STATION = "ایستگاه زمینی (لورا)"
ROCKET_VIA_USB = "USB مستقیم به برد راکت"
ROCKET_VIA_DEMO = "پورت آموزشی (شبیه‌ساز)"

# ارتفاع فشردهٔ ردیف سه باکس اصلی؛ محتوا در این ارتفاع هم‌تراز می‌ماند.
COMMUNICATION_BOX_HEIGHT = 240

# استایل داخلی popup کمبوها؛ قاب و پس‌زمینهٔ پیش‌فرض Fusion را حذف می‌کند.


class CommunicationComboBox(QComboBox):
    """کمبوباکس صفحهٔ ارتباط با popup بدون قاب سفید پیش‌فرض."""

    def showPopup(self):
        super().showPopup()
        # Qt در بعضی styleها view را هنگام بازشدن به container خصوصی منتقل می‌کند؛
        # دوباره‌سازی استایل بعد از show شدن، قاب والد را هم قطعی پوشش می‌دهد.
        CommunicationPage._prepare_combo(self)


class CommunicationPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setLayoutDirection(Qt.RightToLeft)

        # لینک ایستگاه زمینی (حاملِ فیزیکی USB/WiFi) و لینک فعال به راکت
        self.station_link: FlightComputerLink | None = None
        self.rocket_link = None            # ممکن است همان station_link (لورا) یا لینک USB/شبیه‌ساز باشد
        self._station_connected = False

        self.telemetry_timer = QTimer(self)
        self.telemetry_timer.setInterval(500)  # پایش تله‌متری زنده هر ۵۰۰ میلی‌ثانیه
        self.telemetry_timer.timeout.connect(self.poll_telemetry)

        # پس از فرود و ۱۰ ثانیه سکون کامل: ثبت داده متوقف و فایل «داده‌های
        # زنده» ذخیره می‌شود؛ اما پایش زندهٔ تله‌متری ادامه دارد -- در حالت
        # واقعی تا یافتن راکت، به سیگنال تله‌متری/جی‌پی‌اس/ولتاژ باتری نیاز
        # است (به‌روز نگه‌داشتن گیج‌های مرکز کنترل).
        data_manager.telemetry_saved.connect(self._on_live_data_saved)
        data_manager.flight_phase_changed.connect(self._on_phase_for_telemetry)
        self._success_sound = None
        try:
            from PySide6.QtMultimedia import QSoundEffect
            from PySide6.QtCore import QUrl
            from core.paths import asset_path
            snd = QSoundEffect(self)
            snd.setSource(QUrl.fromLocalFile(asset_path("success_landing.wav")))
            snd.setVolume(0.7)
            self._success_sound = snd
        except Exception:
            self._success_sound = None   # بدون QtMultimedia هم برنامه کار می‌کند

        root = QVBoxLayout(self)
        root.addWidget(page_title("ارتباط با کامپیوتر پرواز"))

        self.demo_note = QLabel(
            "🎓 حالت آموزشی فعال است -- شبیه‌ساز به‌جای سخت‌افزار واقعی پاسخ می‌دهد؛ "
            "پرواز کاملاً از اطلاعات مأموریت/نازل و ماژول‌های انتخابیِ شما ساخته می‌شود."
        )
        self.demo_note.setWordWrap(True)
        self.demo_note.setAlignment(Qt.AlignCenter)
        self.demo_note.setObjectName("TopBarDemoMode")
        self.demo_note.setVisible(data_manager.demo_mode)
        root.addWidget(self.demo_note)
        data_manager.demo_mode_changed.connect(self.demo_note.setVisible)

        # ---------------- سه باکس اصلی در یک ردیف ----------------
        # هر سه باکس سهم برابر دارند تا فرم فشرده و هم‌تراز بماند.
        boxes_row = QHBoxLayout()
        boxes_row.setContentsMargins(0, 0, 0, 0)
        boxes_row.setSpacing(12)
        ops_box = self._build_ops_box()
        rocket_box = self._build_rocket_box()
        station_box = self._build_station_box()
        for box in (ops_box, rocket_box, station_box):
            box.setFixedHeight(COMMUNICATION_BOX_HEIGHT)
            box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            boxes_row.addWidget(box, 1)
        root.addLayout(boxes_row)

        # ---------------- باکس به‌روزرسانی فریم‌ور ----------------
        root.addWidget(self._build_firmware_box())

        self.log = QTextEdit(); self.log.setReadOnly(True)
        self.log.setObjectName("CommunicationLog")   # شفاف -- متن مستقیم روی باکس اصلی
        self.log.setLayoutDirection(Qt.LeftToRight)
        # بدون سقف ارتفاع: لاگ تمام فضای باکس اصلی را پر می‌کند (قبلاً سقفِ
        # ۱۳۰ پیکسل متن را در نوارِ وسطِ باکس حبس می‌کرد و بالا/پایین خالی
        # می‌ماند).
        log_frame = QFrame()
        log_frame.setObjectName("CommunicationBox")
        log_frame.setStyleSheet(BOX_NEUTRAL)
        log_lay = QVBoxLayout(log_frame)
        log_lay.setContentsMargins(12, 12, 12, 12)
        log_lay.addWidget(self.log)
        root.addWidget(log_frame)

        self._update_ops_enabled()
        self._on_rocket_mode_changed()

    # ==================================================================
    # ساخت باکس‌ها
    # ==================================================================
    def _build_station_box(self) -> QFrame:
        """باکس سمت راست: اتصال به ایستگاه زمینی (USB یا WiFi)."""
        self.station_box = QFrame()
        self.station_box.setObjectName("CommunicationBox")
        self.station_box.setStyleSheet(BOX_NEUTRAL)
        lay = QVBoxLayout(self.station_box)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        title = QLabel("📡 اتصال به ایستگاه زمینی")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-weight:bold; font-size:15px;")
        title.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        lay.addWidget(title)

        # فیلد کشویی نوع اتصال ایستگاه: USB / WiFi
        self.station_mode_combo = CommunicationComboBox()
        self.station_mode_combo.addItems(["USB", "WiFi"])
        self._prepare_combo(self.station_mode_combo)
        self.station_mode_combo.currentTextChanged.connect(self._on_station_mode_changed)
        lay.addWidget(self.station_mode_combo)

        # فیلد پورت (برای USB) -- ترکیبی از کمبو و دکمهٔ رفرش
        self.station_port_row = QWidget()
        self.station_port_row.setObjectName("CommunicationPortRow")
        self.station_port_row.setFixedHeight(36)
        port_row = QHBoxLayout(self.station_port_row)
        port_row.setContentsMargins(0, 0, 0, 0)
        port_row.setSpacing(8)
        self.station_port_combo = CommunicationComboBox()
        self._prepare_combo(self.station_port_combo)
        self.station_refresh_btn = QPushButton("↻")
        self.station_refresh_btn.setObjectName("RefreshButton")
        self.station_refresh_btn.setProperty("class", "Secondary")
        self.station_refresh_btn.setFixedSize(40, 36)
        self.station_refresh_btn.setToolTip("بروزرسانی لیست پورت‌های USB")
        self.station_refresh_btn.clicked.connect(self._refresh_station_ports)
        port_row.addWidget(self.station_port_combo, 1, Qt.AlignVCenter)
        port_row.addWidget(self.station_refresh_btn, 0, Qt.AlignVCenter)
        lay.addWidget(self.station_port_row)

        # فیلد IP (برای WiFi)
        self.station_ip_edit = QLineEdit()
        self.station_ip_edit.setFixedHeight(36)
        self.station_ip_edit.setPlaceholderText("مثلاً 192.168.4.1 یا 192.168.4.1:8080")
        self.station_ip_edit.setAlignment(Qt.AlignCenter)
        lay.addWidget(self.station_ip_edit)

        self.station_connect_btn = QPushButton("اتصال به ایستگاه")
        self.station_connect_btn.setProperty("class", "Primary")
        self.station_connect_btn.setMinimumHeight(42)
        self.station_connect_btn.clicked.connect(self.toggle_station_connect)
        lay.addWidget(self.station_connect_btn)

        self.station_status = QLabel("وضعیت: قطع")
        self.station_status.setAlignment(Qt.AlignCenter)
        self.station_status.setWordWrap(True)
        self.station_status.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        lay.addWidget(self.station_status)

        self._refresh_station_ports()
        self._on_station_mode_changed("USB")
        return self.station_box

    def _build_rocket_box(self) -> QFrame:
        """باکس سمت چپ: اتصال به راکت (ایستگاه/لورا، USB مستقیم، یا شبیه‌ساز)."""
        self.rocket_box = QFrame()
        self.rocket_box.setObjectName("CommunicationBox")
        self.rocket_box.setStyleSheet(BOX_NEUTRAL)
        lay = QVBoxLayout(self.rocket_box)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        title = QLabel("🚀 اتصال به راکت")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-weight:bold; font-size:15px;")
        title.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        lay.addWidget(title)

        self.rocket_mode_combo = CommunicationComboBox()
        self.rocket_mode_combo.addItems([ROCKET_VIA_STATION, ROCKET_VIA_USB, ROCKET_VIA_DEMO])
        self._prepare_combo(self.rocket_mode_combo)
        self.rocket_mode_combo.currentTextChanged.connect(self._on_rocket_mode_changed)
        lay.addWidget(self.rocket_mode_combo)

        # فیلد انتخاب پورت USB (فقط در حالت USB مستقیم به راکت)
        self.rocket_port_row = QWidget()
        self.rocket_port_row.setObjectName("CommunicationPortRow")
        self.rocket_port_row.setFixedHeight(36)
        rp = QHBoxLayout(self.rocket_port_row)
        rp.setContentsMargins(0, 0, 0, 0)
        rp.setSpacing(8)
        self.rocket_port_combo = CommunicationComboBox()
        self._prepare_combo(self.rocket_port_combo)
        self.rocket_refresh_btn = QPushButton("↻")
        self.rocket_refresh_btn.setObjectName("RefreshButton")
        self.rocket_refresh_btn.setProperty("class", "Secondary")
        self.rocket_refresh_btn.setFixedSize(40, 36)
        self.rocket_refresh_btn.setToolTip("بروزرسانی لیست پورت‌های USB")
        self.rocket_refresh_btn.clicked.connect(self._refresh_rocket_ports)
        rp.addWidget(self.rocket_port_combo, 1, Qt.AlignVCenter)
        rp.addWidget(self.rocket_refresh_btn, 0, Qt.AlignVCenter)
        lay.addWidget(self.rocket_port_row)

        self.rocket_connect_btn = QPushButton("اتصال به راکت")
        self.rocket_connect_btn.setProperty("class", "Primary")
        self.rocket_connect_btn.setMinimumHeight(42)
        self.rocket_connect_btn.clicked.connect(self.toggle_rocket_connect)
        lay.addWidget(self.rocket_connect_btn)

        self.rocket_status = QLabel("وضعیت: قطع")
        self.rocket_status.setAlignment(Qt.AlignCenter)
        self.rocket_status.setWordWrap(True)
        self.rocket_status.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        lay.addWidget(self.rocket_status)

        self._refresh_rocket_ports()
        return self.rocket_box

    def _build_ops_box(self) -> QFrame:
        box = QFrame()
        box.setObjectName("CommunicationBox")
        box.setStyleSheet(BOX_NEUTRAL)
        lay = QVBoxLayout(box)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)
        title = QLabel("🗂 عملیات کارت حافظه و مأموریت")
        title.setStyleSheet("font-weight:bold; font-size:15px;")
        title.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        lay.addWidget(title)

        ops_row = QVBoxLayout()
        ops_row.setContentsMargins(0, 0, 0, 0)
        ops_row.setSpacing(8)
        # دکمهٔ اول (سبز): دانلود فایل پرواز
        self.download_btn = QPushButton("⬇️ دانلود فایل پرواز")
        self.download_btn.setProperty("class", "Success")
        # دکمهٔ دوم (آبی): ارسال اطلاعات قبل از پرواز
        self.send_btn = QPushButton("📤 ارسال اطلاعات قبل از پرواز")
        self.send_btn.setProperty("class", "Primary")
        # دکمهٔ سوم (قرمز): پاک کردن حافظه
        self.erase_btn = QPushButton("🗑 پاک کردن حافظه (فرمت SD)")
        self.erase_btn.setProperty("class", "Danger")

        for b in (self.download_btn, self.send_btn, self.erase_btn):
            b.setMinimumHeight(42)
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            b.setEnabled(False)
        ops_row.addWidget(self.download_btn)
        ops_row.addWidget(self.send_btn)
        ops_row.addWidget(self.erase_btn)
        lay.addLayout(ops_row, 1)

        self.download_btn.clicked.connect(self.download_flight)
        self.send_btn.clicked.connect(self.send_preflight)
        self.erase_btn.clicked.connect(self.erase_memory)
        return box

    def _build_firmware_box(self) -> QFrame:
        box = QFrame()
        box.setObjectName("CommunicationBox")
        box.setStyleSheet(BOX_NEUTRAL)
        lay = QVBoxLayout(box); lay.setContentsMargins(16, 12, 16, 12)
        title = QLabel("🔧 به‌روزرسانی فریم‌ور کامپیوتر پرواز")
        title.setStyleSheet("font-weight:bold;")
        lay.addWidget(title)

        note = QLabel(
            "به‌روزرسانی فریم‌ور فقط از طریق «اتصال USB مستقیم به برد راکت» ممکن است "
            "(bootloader داخلی STM32/آردوینو). از طریق لورا/WiFi امکان‌پذیر نیست. "
            "فایل .bin/.hex فریم‌ور را انتخاب کنید."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color:#7c8aa5; font-size:11px;")
        lay.addWidget(note)

        fw_row = QHBoxLayout()
        self.fw_path_edit = QLineEdit()
        self.fw_path_edit.setMinimumHeight(36)
        self.fw_path_edit.setPlaceholderText("مسیر فایل فریم‌ور (.bin یا .hex)")
        self.fw_path_edit.setReadOnly(True)
        self.fw_browse_btn = QPushButton("انتخاب فایل")
        self.fw_browse_btn.setProperty("class", "Secondary")
        self.fw_browse_btn.setMinimumHeight(40)
        self.fw_browse_btn.clicked.connect(self._browse_firmware)
        self.fw_flash_btn = QPushButton("شروع به‌روزرسانی")
        self.fw_flash_btn.setProperty("class", "Primary")
        self.fw_flash_btn.setMinimumHeight(40)
        self.fw_flash_btn.setEnabled(False)
        self.fw_flash_btn.clicked.connect(self.flash_firmware)
        fw_row.addWidget(self.fw_flash_btn)
        fw_row.addWidget(self.fw_browse_btn)
        fw_row.addWidget(self.fw_path_edit, 1)
        lay.addLayout(fw_row)
        return box

    # ==================================================================
    # کمکی‌ها
    # ==================================================================
    def _append_log(self, text: str):
        self.log.append(text)

    def _refresh_station_ports(self):
        current = self.station_port_combo.currentText()
        self.station_port_combo.blockSignals(True)
        self.station_port_combo.clear()
        real_ports = FlightComputerLink.list_usb_ports() or []
        self.station_port_combo.addItems(real_ports)
        idx = self.station_port_combo.findText(current)
        self.station_port_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.station_port_combo.blockSignals(False)

    def _refresh_rocket_ports(self):
        current = self.rocket_port_combo.currentText()
        self.rocket_port_combo.blockSignals(True)
        self.rocket_port_combo.clear()
        real_ports = FlightComputerLink.list_usb_ports() or []
        self.rocket_port_combo.addItems(real_ports)
        idx = self.rocket_port_combo.findText(current)
        self.rocket_port_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.rocket_port_combo.blockSignals(False)

    def _on_station_mode_changed(self, mode: str = ""):
        mode = mode or self.station_mode_combo.currentText()
        is_usb = mode == "USB"
        self.station_port_row.setVisible(is_usb)
        self.station_ip_edit.setVisible(not is_usb)
        if is_usb:
            self._refresh_station_ports()

    def _on_rocket_mode_changed(self, mode: str = ""):
        mode = mode or self.rocket_mode_combo.currentText()
        # فیلد پورت USB فقط برای «USB مستقیم به برد راکت» دیده می‌شود
        self.rocket_port_row.setVisible(mode == ROCKET_VIA_USB)
        if mode == ROCKET_VIA_USB:
            self._refresh_rocket_ports()

    @staticmethod
    def _prepare_combo(combo: QComboBox):
        """یکنواخت‌سازی ارتفاع کمبو و حذف کامل قاب/پس‌زمینهٔ پیش‌فرض popup."""
        combo.setFixedHeight(36)
        # ویو + viewport + ظرفِ پاپ‌آپ (نوار سفید بالا/پایین) -- منبع مشترک
        from ui.style import darken_combo_popup
        darken_combo_popup(combo)

    def _set_box_style(self, box: QFrame, style: str):
        box.setStyleSheet(style)

    @staticmethod
    def _set_button_tone(button: QPushButton, tone: str):
        """اعمال رنگ وضعیت دکمه و تازه‌سازی استایل آن پس از تغییر property."""
        button.setProperty("class", tone)
        button.style().unpolish(button)
        button.style().polish(button)
        button.update()

    # ==================================================================
    # اتصال به ایستگاه زمینی (باکس راست)
    # ==================================================================
    def toggle_station_connect(self):
        if self._station_connected:
            # قطع ایستگاه -> قطع راکت لورا هم (اگر از راه ایستگاه بود)
            if self.rocket_link is self.station_link:
                self._disconnect_rocket(silent=True)
            if self.station_link:
                self.station_link.stop()
            self.station_link = None
            self._station_connected = False
            self.station_connect_btn.setText("اتصال به ایستگاه")
            self._set_button_tone(self.station_connect_btn, "Primary")
            self.station_status.setText("وضعیت: قطع")
            self._set_box_style(self.station_box, BOX_NEUTRAL)
            self._append_log("اتصال ایستگاه زمینی قطع شد.")
            return

        mode = self.station_mode_combo.currentText()
        if mode == "USB":
            port = self.station_port_combo.currentText().strip()
            if not port:
                self._station_result(False, "هیچ پورت USB برای ایستگاه انتخاب نشده است.")
                return
            self.station_link = FlightComputerLink(mode="USB", port=port)
        else:  # WiFi
            ip = self.station_ip_edit.text().strip()
            if not ip:
                self._station_result(False, "آدرس IP ایستگاه زمینی را وارد کنید.")
                return
            self.station_link = FlightComputerLink(mode="WiFi", host=ip)

        self.station_status.setText("در حال اتصال به ایستگاه ...")
        self.station_link.connected_signal.connect(self._on_station_connected)
        self.station_link.log_message.connect(self._append_log)
        self.station_link.start()

    def _on_station_connected(self, ok: bool):
        if not ok:
            self._station_result(False, "اتصال به ایستگاه زمینی برقرار نشد -- اتصالات و درایور را بررسی کنید.")
            self.station_link = None
            return
        # تأیید اینکه واقعاً برد ایستگاه زمینی پاسخ می‌دهد
        resp = ""
        try:
            resp = self.station_link.send_command("STATION_PING")
        except Exception:
            resp = ""
        if resp.startswith("PONG,STATION") or resp.startswith("PONG"):
            self._station_connected = True
            self.station_connect_btn.setText("قطع ایستگاه")
            self._station_result(True, "✅ ایستگاه زمینی با موفقیت متصل شد.")
        else:
            # اتصال فیزیکی برقرار شد اما پاسخ معتبری نیامد
            self._station_connected = True
            self.station_connect_btn.setText("قطع ایستگاه")
            self._station_result(True, "اتصال برقرار شد (پاسخ شناسایی ایستگاه دریافت نشد).")

    def _station_result(self, ok: bool, message: str):
        self.station_status.setText(message)
        self._set_button_tone(self.station_connect_btn, "Success" if ok else "Danger")
        self._set_box_style(self.station_box, BOX_OK if ok else BOX_FAIL)
        self._append_log(message)

    # ==================================================================
    # اتصال به راکت (باکس چپ)
    # ==================================================================
    def toggle_rocket_connect(self):
        if data_manager.connected:
            self._disconnect_rocket()
            return

        mode = self.rocket_mode_combo.currentText()
        if mode == ROCKET_VIA_STATION:
            self._connect_rocket_via_station()
        elif mode == ROCKET_VIA_USB:
            self._connect_rocket_via_usb()
        else:
            self._connect_rocket_demo()

    def _connect_rocket_via_station(self):
        if not self._station_connected or not self.station_link:
            self._rocket_result(False, "ابتدا ایستگاه زمینی را به سیستم متصل کنید (باکس سمت راست).")
            QMessageBox.warning(self, "ایستگاه زمینی متصل نیست",
                                "ابتدا از باکس «اتصال به ایستگاه زمینی» به ایستگاه وصل شوید.")
            return
        self.rocket_status.setText("در حال برقراری لینک رادیویی لورا با راکت ...")
        # به ایستگاه دستور می‌دهیم لینک لورا با راکت را برقرار کند
        link_resp = ""
        try:
            link_resp = self.station_link.send_command("LORA_LINK")
        except Exception:
            link_resp = ""
        if not link_resp.startswith("ACK:LORA_LINKED"):
            self._rocket_result(False, "❌ برقراری لینک لورا با راکت ناموفق بود -- راکت/آنتن را بررسی کنید.")
            return
        # تست PING موفق از خود راکت
        ping = ""
        try:
            ping = self.station_link.send_command("PING")
        except Exception:
            ping = ""
        if not ping.startswith("PONG"):
            self._rocket_result(False, "❌ لینک لورا برقرار شد اما راکت به PING پاسخ نداد.")
            return
        # موفق: راکت از طریق ایستگاه (لورا) متصل است
        self.rocket_link = self.station_link
        data_manager.active_link = self.rocket_link
        data_manager.set_connection(True, "LORA")
        data_manager.set_demo_mode(False)
        self._rocket_connected_ui(True, "✅ راکت از طریق لورا (ایستگاه زمینی) متصل شد.")

    def _connect_rocket_via_usb(self):
        port = self.rocket_port_combo.currentText().strip()
        if not port:
            self._rocket_result(False, "هیچ پورت USB برای اتصال مستقیم به راکت انتخاب نشده است.")
            return
        self.rocket_status.setText("در حال اتصال USB مستقیم به برد راکت ...")
        self.rocket_link = FlightComputerLink(mode="USB", port=port)
        self.rocket_link.connected_signal.connect(self._on_rocket_usb_connected)
        self.rocket_link.log_message.connect(self._append_log)
        self.rocket_link.start()

    def _on_rocket_usb_connected(self, ok: bool):
        if not ok:
            self._rocket_result(False, "❌ اتصال USB به برد راکت برقرار نشد.")
            self.rocket_link = None
            return
        data_manager.active_link = self.rocket_link
        data_manager.set_connection(True, "USB")
        data_manager.set_demo_mode(False)
        self._rocket_connected_ui(True, "✅ اتصال USB مستقیم به برد راکت برقرار شد.")

    def _connect_rocket_demo(self):
        self.rocket_status.setText("در حال اتصال به پورت آموزشی ...")
        self.rocket_link = SimulatedFlightComputerLink(port=SimulatedFlightComputerLink.FAKE_PORT_NAME)
        self.rocket_link.connected_signal.connect(self._on_rocket_demo_connected)
        self.rocket_link.log_message.connect(self._append_log)
        self.rocket_link.start()

    def _on_rocket_demo_connected(self, ok: bool):
        if not ok:
            self._rocket_result(False, "❌ اتصال به پورت آموزشی برقرار نشد.")
            self.rocket_link = None
            return
        data_manager.active_link = self.rocket_link
        data_manager.set_connection(True, "DEMO")
        data_manager.set_demo_mode(True)
        # طبق تصمیم کاربر: اتصال آموزشی هیچ داده‌ای را خودکار پر/تغییر نمی‌دهد.
        # کاربر خودش ماژول‌ها را انتخاب و اطلاعات مأموریت را وارد می‌کند و با
        # «ارسال اطلاعات قبل از پرواز» به کامپیوتر پرواز (شبیه‌ساز) می‌فرستد.
        self._rocket_connected_ui(True, "✅ اتصال به پورت آموزشی (شبیه‌ساز) برقرار شد.")

    def _rocket_connected_ui(self, ok: bool, message: str):
        self._rocket_result(ok, message)
        self.rocket_connect_btn.setText("قطع اتصال راکت")
        self._update_ops_enabled()
        if ok:
            self.query_firmware()
            self.query_status()
            self.telemetry_timer.start()

    def _disconnect_rocket(self, silent: bool = False):
        self.telemetry_timer.stop()
        # اگر لینک راکت همان لینک ایستگاه بود (لورا)، ایستگاه را قطع نمی‌کنیم
        if self.rocket_link is not None and self.rocket_link is not self.station_link:
            self.rocket_link.stop()
        self.rocket_link = None
        data_manager.active_link = None
        data_manager.set_connection(False)
        data_manager.mission.firmware_version = ""
        data_manager.mission_changed.emit()
        self.rocket_connect_btn.setText("اتصال به راکت")
        self._set_button_tone(self.rocket_connect_btn, "Primary")
        self.rocket_status.setText("وضعیت: قطع")
        self._set_box_style(self.rocket_box, BOX_NEUTRAL)
        self._update_ops_enabled()
        if not silent:
            self._append_log("اتصال راکت قطع شد.")

    def _rocket_result(self, ok: bool, message: str):
        self.rocket_status.setText(message)
        self._set_button_tone(self.rocket_connect_btn, "Success" if ok else "Danger")
        self._set_box_style(self.rocket_box, BOX_OK if ok else BOX_FAIL)
        self._append_log(message)

    def _update_ops_enabled(self):
        ok = data_manager.connected
        for b in (self.download_btn, self.send_btn, self.erase_btn):
            b.setEnabled(ok)
        # به‌روزرسانی فریم‌ور فقط با اتصال USB مستقیم به راکت
        is_usb_direct = (ok and data_manager.connection_type.upper() == "USB")
        self.fw_flash_btn.setEnabled(is_usb_direct and bool(self.fw_path_edit.text().strip()))

    # ==================================================================
    # ==================================================================
    # پایش تله‌متری و کوئری‌ها (بدون تغییر منطقی نسبت به نسخهٔ قبل)
    # ==================================================================
    def _active_link(self):
        return data_manager.active_link

    def _on_phase_for_telemetry(self, phase: str):
        """شمارش معکوس پروازِ جدید → پایش تله‌متری زنده دوباره فعال شود.
        (پس از پرواز قبلی، تایمر برای «توقف ورود داده» خاموش شده بود؛ بدون
        این ری‌استارت، پرواز بعدی روی شمارش معکوس گیر می‌کرد.)"""
        if phase == "countdown" and data_manager.connected and self._active_link():
            self.telemetry_timer.start()

    def _on_live_data_saved(self, path: str):
        """پایان پرواز: پس از ۱۰ ثانیه سکون، فایل «داده‌های زنده» ذخیره شد و
        **ثبت داده متوقف شد**؛ اما پایش زندهٔ تله‌متری ادامه دارد تا در حالت
        واقعی هنگام یافتن راکت، گیج‌های مرکز کنترل (تله‌متری/جی‌پی‌اس/
        ولتاژ باتری) زنده بمانند. صدای موفقیت پخش و دکمهٔ دانلود دادهٔ خام
        هم در داشبورد فعال است (دانلود بر اساس کیفیت لینک با خودِ کاربر)."""
        if self._success_sound is not None:
            self._success_sound.play()
        self._append_log(
            f"🪂 فرود موفق! پس از ۱۰ ثانیه سکون، فایل «داده‌های زنده» ذخیره شد: {os.path.basename(path)}\n"
            "   ثبت داده متوقف شد؛ پایش زندهٔ تله‌متری/جی‌پی‌اس/باتری همچنان فعال است "
            "(برای یافتن راکت). برای دادهٔ کامل کارت SD، در مرکز کنترل پرواز دکمهٔ "
            "«دانلود داده‌های خام» را بزنید (بر اساس کیفیت لینک لورا).")
        # درخواست کاربر: پس از فرود و ذخیرهٔ خودکار، برنامه روی همین صفحهٔ زنده
        # می‌ماند؛ فقط وقتی دانلود دادهٔ خام کامل و درست شد، به «تحلیل پرواز»
        # (تب «شاخص‌های پرواز») می‌رود.

    def poll_telemetry(self):
        link = self._active_link()
        if not link or not data_manager.connected:
            return
        response = link.send_command("GET_TELEMETRY")
        if not response.startswith("TELEM,"):
            return
        parts = response.split(",")

        def f(i):
            """پارس مقاوم: فیلد خالی (ماژول نصب نیست) یا خراب → None."""
            try:
                if len(parts) > i and parts[i].strip() != "":
                    return float(parts[i])
            except ValueError:
                pass
            return None

        packet = {}
        for key, idx in (("t", 1), ("altitude", 2), ("vertical_velocity", 3),
                         ("pressure", 4), ("temperature", 5),
                         ("accel_x", 6), ("accel_y", 7), ("accel_z", 8),
                         ("humidity", 9), ("temperature_aht", 10), ("uv_index", 11)):
            v = f(idx)
            if v is not None:
                packet[key] = v
        if packet.get("humidity") is not None:
            data_manager.humidity_percent = packet["humidity"]
        if packet.get("temperature_aht") is not None:
            data_manager.temperature_aht_c = packet["temperature_aht"]
        if packet.get("uv_index") is not None:
            data_manager.uv_index = packet["uv_index"]

        # فیلدهای GPS اختیاری انتهای بسته: <lat>,<lon>,<sats>
        lat, lon, sats = f(12), f(13), f(14)
        if lat is not None and lon is not None:
            data_manager.gps_lat, data_manager.gps_lon = lat, lon
            data_manager.gps_hdop = 1.2
            if sats is not None:
                data_manager.gps_sats = int(sats)

        # حالت آموزشی: شبیه‌سازی آمار لینک لورا -- کاربر بر اساس RSSI/SNR/نرخ
        # بسته تصمیم می‌گیرد کِی دادهٔ خام را دانلود کند (بعد از نزدیک‌شدن به
        # راکتِ فرودآمده سیگنال بهتر می‌شود)
        if data_manager.demo_mode:
            import random as _rnd
            data_manager.lora_rssi_dbm = round(_rnd.gauss(-72, 3), 1)
            data_manager.lora_snr_db = round(_rnd.gauss(8.5, 1.2), 1)
            data_manager.lora_packet_rate_hz = round(_rnd.gauss(2.0, 0.2), 2)

        data_manager.log_lora_packet(packet)
        data_manager.telemetry_updated.emit(packet)

    def query_firmware(self):
        link = self._active_link()
        if not link:
            return
        response = link.send_command("PING")
        if not response.startswith("PONG"):
            self._append_log("پاسخی از PING دریافت نشد؛ نسخهٔ Firmware نامشخص باقی ماند.")
            return
        parts = response.split(",")
        fw_version = parts[1].strip() if len(parts) > 1 else ""
        data_manager.mission.firmware_version = fw_version
        data_manager.mission_changed.emit()
        self._append_log(f"نسخهٔ Firmware دریافت شد: {fw_version or 'نامشخص'}")

    def query_status(self):
        link = self._active_link()
        if not link:
            return
        response = link.send_command("GET_STATUS")
        if not response.startswith("STATUS,"):
            self._append_log("پاسخی از GET_STATUS دریافت نشد (اتصال شبیه‌سازی‌شده یا سخت‌افزار در دسترس نیست).")
            return
        parts = response.split(",")
        try:
            battery = float(parts[1])
            data_manager.telemetry_updated.emit({"battery": battery})
            for name, idx in (("BMP280", 2), ("MPU6050", 3), ("SD", 4), ("CAMERA", 5)):
                if idx < len(parts) and parts[idx].strip():
                    data_manager.update_sensor_status(name, parts[idx].strip())
        except (ValueError, IndexError):
            self._append_log("پاسخ GET_STATUS قابل تفسیر نبود.")

    # ==================================================================
    # عملیات کارت حافظه/مأموریت
    # ==================================================================
    def send_preflight(self):
        link = self._active_link()
        if not link or not data_manager.connected:
            self._append_log("ابتدا به راکت متصل شوید.")
            return
        payload = json.dumps(data_manager.build_preflight_payload(), ensure_ascii=False)
        self._append_log("در حال ارسال اطلاعات مأموریت/راکت/موتور به کامپیوتر پرواز ...")
        response = link.send_command(f"SET_MISSION,{payload}")
        if response.strip().startswith("ACK:MISSION_OK"):
            self._append_log("✅ اطلاعات با موفقیت ارسال و توسط کامپیوتر پرواز تایید شد.")
            data_manager.mark_preflight_transferred(True)
        else:
            self._append_log("❌ تاییدیه‌ای از کامپیوتر پرواز دریافت نشد -- ارسال ممکن است ناموفق بوده باشد.")
            data_manager.mark_preflight_transferred(False)

    def download_flight(self):
        link = self._active_link()
        if not link or not data_manager.connected:
            self._append_log("ابتدا به راکت متصل شوید.")
            return
        self._append_log("در حال دانلود فایل پرواز از حافظه SD ...")
        link.send_command("DOWNLOAD")
        from core.jalali import jalali_date_for_filename
        from core.paths import build_report_filename
        m = data_manager.mission
        suggested = build_report_filename(
            jalali_date_for_filename(m.jalali_date or m.date),
            m.flight_number or "بدون‌شماره",
            "csv",
            suffix="خام",
        )
        path, _ = QFileDialog.getSaveFileName(self, "ذخیره فایل پرواز", suggested, "CSV Files (*.csv)")
        if path:
            ok = False
            if data_manager.demo_mode and hasattr(link, "write_csv"):
                ok = link.write_csv(path)
                if not ok:
                    if data_manager.flight_phase != "landed":
                        self._append_log(
                            "❌ هنوز پروازی ثبت نشده است -- ابتدا مراحل پرتاب (داشبورد) را کامل کنید.")
                    else:
                        self._append_log(
                            "❌ کارت SD روی راکت نصب نیست -- دادهٔ خام روی راکت ذخیره نشده. "
                            "(فایل خام تله‌متری لورا پس از فرود خودکار ذخیره شده است)")
            if ok:
                loaded = data_manager.load_flight_csv(path) if os.path.exists(path) else False
                self._append_log("فایل دانلود و تحلیل شد." if loaded else f"فایل در {path} ذخیره شد.")
            elif not data_manager.demo_mode:
                self._append_log("دانلود از سخت‌افزار واقعی هنوز پیاده‌سازی نشده است.")

    def erase_memory(self):
        link = self._active_link()
        if not link or not data_manager.connected:
            self._append_log("ابتدا به راکت متصل شوید.")
            return
        # اخطار اول
        c1 = QMessageBox.warning(
            self, "پاک کردن حافظه SD",
            "⚠️ هشدار: با این کار تمام داده‌ها و فیلم‌های روی کارت SD کامپیوتر پرواز "
            "برای همیشه پاک می‌شوند.\n\nآیا مطمئن هستید؟",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if c1 != QMessageBox.Yes:
            return
        # اخطار دوم (تایید نهایی)
        c2 = QMessageBox.critical(
            self, "تایید نهایی فرمت",
            "این عملیات غیرقابل بازگشت است.\nآیا واقعاً می‌خواهید کارت SD فرمت شود؟",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if c2 != QMessageBox.Yes:
            return
        self._append_log("در حال ارسال دستور فرمت کارت SD به کامپیوتر پرواز ...")
        response = link.send_command("FORMAT_SD")
        if not response.strip().startswith("ACK:"):
            # سازگاری با فریمورهایی که دستور قدیمی ERASE را می‌شناسند
            response = link.send_command("ERASE")
        if response.strip().startswith("ACK:"):
            self._append_log("✅ کارت SD با موفقیت فرمت شد.")
        else:
            self._append_log("❌ تاییدیه‌ای از کامپیوتر پرواز دریافت نشد -- فرمت تایید نشد.")

    # ==================================================================
    # به‌روزرسانی فریم‌ور (فقط USB مستقیم)
    # ==================================================================
    def _browse_firmware(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "انتخاب فایل فریم‌ور", "", "Firmware (*.bin *.hex);;All Files (*)")
        if path:
            self.fw_path_edit.setText(path)
            self._update_ops_enabled()

    def flash_firmware(self):
        link = self._active_link()
        if not link or not data_manager.connected:
            self._append_log("برای به‌روزرسانی فریم‌ور باید مستقیماً با USB به راکت متصل باشید.")
            return
        if data_manager.connection_type.upper() != "USB":
            QMessageBox.warning(
                self, "اتصال نامناسب",
                "به‌روزرسانی فریم‌ور فقط از طریق اتصال USB مستقیم به برد راکت ممکن است، "
                "نه از راه لورا/WiFi.")
            return
        path = self.fw_path_edit.text().strip()
        if not path or not os.path.exists(path):
            self._append_log("فایل فریم‌ور معتبر انتخاب نشده است.")
            return
        confirm = QMessageBox.question(
            self, "به‌روزرسانی فریم‌ور",
            "برد به حالت bootloader می‌رود و فریم‌ور جدید نوشته می‌شود.\n"
            "طی این فرایند برد را جدا یا خاموش نکنید.\n\nادامه می‌دهید؟",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if confirm != QMessageBox.Yes:
            return
        self._append_log("در حال ورود برد به حالت bootloader ...")
        resp = link.send_command("ENTER_BOOTLOADER")
        if not resp.strip().startswith("ACK:BOOTLOADER"):
            self._append_log("❌ برد وارد حالت bootloader نشد -- به‌روزرسانی لغو شد.")
            return
        # TODO: پیاده‌سازی واقعی پروتکل bootloader (STM32 AN3155 یا آردوینو STK500)
        # برای نوشتن فایل .bin/.hex قطعه‌به‌قطعه.
        # این بخش به سخت‌افزار واقعی نیاز دارد تا تست و تکمیل شود.
        self._append_log(
            "ℹ️ ورود به bootloader موفق بود. نوشتن فایل فریم‌ور نیازمند سخت‌افزار واقعی است "
            "و در این نسخه هنوز تکمیل نشده (اسکلت پروتکل آماده است).")
