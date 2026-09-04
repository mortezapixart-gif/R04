# -*- coding: utf-8 -*-
"""صفحهٔ پایش پرتاب (مراحل تست سلامت تا شمارش معکوس و پرتاب)

نسخهٔ ۲.۰.۰ -- بازطراحی بر اساس استانداردهای ناوبری فضایی (INS/IMU
Alignment) و چک‌لیست ترتیبی ایمنی پرتاب (Sequential Launch Checklist):

    اکنون ۳ دکمهٔ مرحله‌ای وجود دارد که هرکدام رنگ اختصاصی خودش را دارد
    (مرحلهٔ ۳ قرمز). برای جلوگیری از خطای انسانی، دکمه‌های مراحل در ابتدا
    غیرفعال هستند و فقط پس از اتمام موفقیت‌آمیز هر مرحله، دکمهٔ مرحلهٔ بعد
    فعال می‌شود:

        ۱) تست سلامت سنسورها (حداقل ۳۰ ثانیه، تیک زنده کنار هر ماژول)
        ۲) کالیبراسیون و ترازبندی ناوبری (INS/IMU Static Alignment، ۶۰ ثانیه)
        ۳) آماده‌سازی نهایی و ورود به پرتاب: دیالوگ «آیا آماده پرتاب هستید؟»
           → شروع ضبط روی SD → ورود به «مرکز کنترل پرواز». دکمهٔ خودِ پرتاب اکنون
           در مرکز کنترل پرواز است (ارسال ARM + تغییر وضعیت به «آماده پرتاب» و
           سپس تشخیص خودکار فاز پرواز از دادهٔ لورا). ارتباط لورا برخلاف
           وای‌فای قبلی طی کل پرواز برقرار می‌ماند، پس دیگر نیازی به قطع
           رادیو و اتصال مجدد پس از فرود نیست.

توجه: مقادیر ثابت زیر (به‌ویژه HEALTH_CHECK_DURATION_SEC و
CALIB_DURATION_SEC) عمداً به‌صورت ثابت‌های سرتاسری این فایل نگه
داشته شده‌اند تا در آینده به‌سادگی از تنظیمات برنامه قابل تغییر باشند.
"""
import json
import math
import time

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QGridLayout, QHBoxLayout, QPushButton,
                                QLabel, QMessageBox, QProgressBar,
                                QGraphicsDropShadowEffect, QDialog, QFrame)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont

from ui.widgets import StatCard, SensorStatusCard, page_title, section_title, make_card
from core.data_manager import data_manager
from core.analysis import G0
from core.demo_flight_sim import DEMO_HEALTH_CHECK_DURATION_SEC, DEMO_CALIB_DURATION_SEC
from core.rocket_physics import SimParams, predict_summary

SENSOR_META = {
    "BMP280": ("سنسور فشار/دما", "🌡"),
    "MPU6050": ("شتاب‌سنج/ژیروسکوپ", "🧭"),
    "AHT21": ("دما و رطوبت", "💧"),
    "UV": ("شدت اشعه UV", "☀️"),
    "CAMERA": ("دوربین", "📷"),
    "SD": ("کارت حافظه SD", "💾"),
    "GPS": ("ماژول GPS", "📡"),
}

# محدوده‌های مجاز تست سلامت ماژول‌های جدید (مرحلهٔ ۱)
HUMIDITY_MIN = 0.0
HUMIDITY_MAX = 100.0
AHT_TEMP_MIN = -40.0
AHT_TEMP_MAX = 85.0
UV_INDEX_MIN = 0.0
UV_INDEX_MAX = 20.0

# مقادیری که یعنی «هنوز مدل این ماژول انتخاب نشده» -- طبق تصمیم نهایی، این
# ماژول‌ها در تست سلامت مرحلهٔ ۱ نادیده گرفته می‌شوند (پیش‌فرض همهٔ لیست‌ها
# در pages/sensor_modules.py با همین مقدار شروع می‌شود)
UNSELECTED_VALUES = {"انتخاب نشده", "نصب نشده"}

# ---- محدوده‌های مجاز تست سلامت (مرحلهٔ ۱) ----
PRESSURE_MIN_HPA = 800.0
PRESSURE_MAX_HPA = 1100.0
ACCEL_G_MIN = 0.7      # حدود ۱g با کمی رواداری برای حالت ساکن روی سکو
ACCEL_G_MAX = 1.3
HEALTH_CHECK_DURATION_SEC = 30     # حداقل مدت تست سلامت -- قابل تنظیم
HEALTH_CHECK_TICK_MS = 1000

# ---- تایمر کالیبراسیون ناوبری (مرحلهٔ ۲) ----
CALIB_DURATION_SEC = 60

# مدت مکث منطقی پیش از فعال‌شدن دوبارهٔ دکمهٔ یک مرحلهٔ موفق، برای امکان
# «تکرار» بدون نیاز به بستن/بازکردن برنامه (طبق تصمیم کاربر).
RETRY_COOLDOWN_MS = 4000


def _add_shadow(widget, color: QColor, blur: int = 26, y_offset: int = 5):
    """سایهٔ نرم زیر دکمه‌ها برای ظاهر گرافیکی و برجسته‌تر."""
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setOffset(0, y_offset)
    effect.setColor(color)
    widget.setGraphicsEffect(effect)


class CalibrationChecklistDialog(QDialog):
    """چک‌لیست پیش‌نیاز پیش از شروع کالیبراسیون ناوبری (مرحلهٔ ۲):

        ۱) اطلاعات مأموریت وارد و ذخیره شده؟
        ۲) اطلاعات نازل وارد و ذخیره شده؟
        ۳) اطلاعات ذخیره‌شده به کامپیوتر پرواز منتقل شده؟

    هر سه شرط به‌صورت خودکار توسط برنامه بررسی می‌شوند (نه با تیک دستی
    کاربر روی چیزی که خودش تضمین نمی‌کند) -- دکمهٔ «شروع کالیبراسیون» فقط
    وقتی هر سه سبز باشند فعال می‌شود. کاربر می‌تواند بدون بستن این پنجره،
    از دکمه‌های «برو به ...» برای رفع مشکل و بعد «بررسی مجدد» استفاده کند.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("بررسی پیش‌نیازهای کالیبراسیون ناوبری")
        self.setLayoutDirection(Qt.RightToLeft)
        self.setMinimumWidth(600)

        layout = QVBoxLayout(self)
        intro = QLabel(
            "پیش از شروع کالیبراسیون ناوبری (که ۶۰ ثانیه طول می‌کشد و باید راکت "
            "کاملاً ساکن بماند)، این سه شرط باید برقرار باشند:"
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.row1 = self._make_row()
        self.row2 = self._make_row()
        self.row3 = self._make_row()
        for row in (self.row1, self.row2, self.row3):
            layout.addWidget(row["frame"])

        helper_row = QHBoxLayout()
        self.recheck_btn = QPushButton("🔄 بررسی مجدد")
        self.recheck_btn.clicked.connect(self.recheck)
        self.goto_mission_btn = QPushButton("برو به اطلاعات مأموریت/نازل")
        self.goto_mission_btn.clicked.connect(self._goto_mission)
        # به‌جای «برو به صفحهٔ ارتباط»، اطلاعات مستقیم از همین‌جا به کامپیوتر
        # پرواز ارسال می‌شود تا کاربر مجبور نباشد صفحه را ترک کند.
        self.send_preflight_btn = QPushButton("📤 ارسال اطلاعات قبل از پرواز")
        self.send_preflight_btn.setProperty("class", "Primary")
        self.send_preflight_btn.clicked.connect(self._send_preflight)
        helper_row.addWidget(self.recheck_btn)
        helper_row.addWidget(self.goto_mission_btn)
        helper_row.addWidget(self.send_preflight_btn)
        helper_row.addStretch()
        layout.addLayout(helper_row)

        self.send_result_label = QLabel("")
        self.send_result_label.setWordWrap(True)
        self.send_result_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.send_result_label)

        action_row = QHBoxLayout()
        self.cancel_btn = QPushButton("انصراف")
        self.cancel_btn.clicked.connect(self.reject)
        self.start_btn = QPushButton("✅ شروع کالیبراسیون")
        self.start_btn.setProperty("class", "Primary")
        self.start_btn.setMinimumWidth(170)
        self.start_btn.setEnabled(False)
        self.start_btn.clicked.connect(self.accept)
        action_row.addStretch()
        action_row.addWidget(self.cancel_btn)
        action_row.addWidget(self.start_btn)
        layout.addLayout(action_row)

        self.recheck()

    def _make_row(self):
        frame = QFrame()
        frame.setProperty("class", "Card")
        lay = QHBoxLayout(frame)
        icon = QLabel("❔")
        icon.setFixedWidth(30)
        f = QFont()
        f.setPointSize(15)
        icon.setFont(f)
        text_col = QVBoxLayout()
        title = QLabel("")
        title.setProperty("class", "CardTitle")
        detail = QLabel("")
        detail.setWordWrap(True)
        detail.setProperty("class", "CardTitleCompact")
        text_col.addWidget(title)
        text_col.addWidget(detail)
        lay.addWidget(icon)
        lay.addLayout(text_col, 1)
        return {"frame": frame, "icon": icon, "title": title, "detail": detail}

    def _set_row(self, row, label, ok, detail):
        row["title"].setText(label)
        row["icon"].setText("✅" if ok else "❌")
        row["icon"].setStyleSheet(f"color:{'#35d07f' if ok else '#ef5350'};")
        row["detail"].setText(detail)
        row["detail"].setStyleSheet(f"color:{'#7c8aa5' if ok else '#ef5350'};")

    def recheck(self):
        mission_ok = data_manager.mission_info_complete()
        nozzle_ok = data_manager.nozzle_info_complete()
        connected = data_manager.connected
        transferred_ok = connected and data_manager.preflight_transferred

        self._set_row(
            self.row1, "۱. اطلاعات مأموریت وارد و ذخیره شده", mission_ok,
            "تایید شد." if mission_ok else
            "نام راکت، محل پرتاب، ارتفاع از سطح دریا، وزن کل راکت و وزن سوخت باید وارد و ذخیره شود."
        )
        self._set_row(
            self.row2, "۲. اطلاعات نازل وارد و ذخیره شده", nozzle_ok,
            "تایید شد." if nozzle_ok else
            "قطر گلوگاه، قطر خروجی و فشار محفظه باید وارد و ذخیره شود."
        )
        if not connected:
            detail3 = "ابتدا در صفحهٔ ارتباط، به کامپیوتر پرواز متصل شوید."
        elif not transferred_ok:
            detail3 = "در صفحهٔ ارتباط، دکمهٔ «ارسال اطلاعات قبل از پرواز» را بزنید و تاییدیه بگیرید."
        else:
            detail3 = "تایید شد."
        self._set_row(self.row3, "۳. اطلاعات ذخیره‌شده به کامپیوتر پرواز منتقل شده", transferred_ok, detail3)

        all_ok = mission_ok and nozzle_ok and transferred_ok
        self.start_btn.setEnabled(all_ok)
        self.goto_mission_btn.setVisible(not (mission_ok and nozzle_ok))
        # دکمهٔ ارسال فقط وقتی معنا دارد که اطلاعات مأموریت/نازل کامل باشد ولی
        # هنوز به کامپیوتر پرواز منتقل نشده باشد.
        self.send_preflight_btn.setVisible(mission_ok and nozzle_ok and not transferred_ok)

    def _goto_mission(self):
        data_manager.navigate_requested.emit("اطلاعات مأموریت و نازل")

    def _send_preflight(self):
        """ارسال مستقیم اطلاعات مأموریت/راکت/موتور به کامپیوتر پرواز از داخل
        همین دیالوگ -- تا کاربر مجبور نباشد به صفحهٔ ارتباط برود."""
        if not data_manager.connected or not data_manager.active_link:
            self.send_result_label.setText("❌ ابتدا در صفحهٔ ارتباط به کامپیوتر پرواز متصل شوید.")
            self.send_result_label.setStyleSheet("color:#ef5350;")
            return
        payload = json.dumps(data_manager.build_preflight_payload(), ensure_ascii=False)
        self.send_result_label.setText("در حال ارسال اطلاعات به کامپیوتر پرواز ...")
        self.send_result_label.setStyleSheet("color:#7c8aa5;")
        response = data_manager.active_link.send_command(f"SET_MISSION,{payload}")
        if response.strip().startswith("ACK:MISSION_OK"):
            data_manager.mark_preflight_transferred(True)
            self.send_result_label.setText("✅ اطلاعات با موفقیت ارسال و تایید شد.")
            self.send_result_label.setStyleSheet("color:#35d07f;")
        else:
            data_manager.mark_preflight_transferred(False)
            self.send_result_label.setText("❌ تاییدیه‌ای از کامپیوتر پرواز دریافت نشد — دوباره تلاش کنید.")
            self.send_result_label.setStyleSheet("color:#ef5350;")
        self.recheck()


class DashboardPage(QWidget):
    # حالت آموزشی: زمان‌بندی‌های چک‌لیست کوتاه می‌شوند (بدون نیاز به ۶۰ ثانیهٔ
    # کالیبراسیون یا ۵ دقیقهٔ انتظار پرتاب واقعی) -- core/demo_flight_sim.py.
    # این‌ها Property هستند (نه مقدار ثابتِ محاسبه‌شده در __init__) چون کاربر
    # می‌تواند در حین اجرای برنامهٔ اصلی هم از صفحهٔ ارتباط وارد حالت آموزشی
    # بشود -- پس باید همیشه data_manager.demo_mode زنده خوانده شود.
    @property
    def health_check_duration(self):
        return DEMO_HEALTH_CHECK_DURATION_SEC if data_manager.demo_mode else HEALTH_CHECK_DURATION_SEC

    @property
    def calib_duration(self):
        return DEMO_CALIB_DURATION_SEC if data_manager.demo_mode else CALIB_DURATION_SEC

    def __init__(self):
        super().__init__()
        self.setLayoutDirection(Qt.RightToLeft)
        self._start_time = time.time()

        # ---- وضعیت داخلی چک‌لیست ترتیبی ----
        self._health_active_keys = []
        # آیا قبلاً برای این تلاشِ پرتاب، «راکت قابلیت پرتاب ندارد» نشان داده
        # شده؟ (بار اول: سد + هدایت به صفحهٔ مأموریت؛ بار دوم پس از اصلاح
        # اطلاعات و ادامهٔ بی‌تغکیر پیش‌بینی: گرفتن تاییدیهٔ صریح کاربر)
        self._launch_warned = False
        self._health_pending = set()
        self._health_elapsed = 0
        self._calib_seconds_left = self.calib_duration
        self._calib_acked = False

        # قابلیت تکرار مراحل ۱ تا ۳ بدون نیاز به بستن/بازکردن برنامه.
        # دکمهٔ مرحلهٔ ۳ ضبط را آغاز کرده و کاربر را به «مرکز کنترل پرواز» می‌برد.
        self._step_completed = {1: False, 2: False, 3: False}
        self._step_names = {1: "تست سلامت سنسورها", 2: "کالیبراسیون ناوبری",
                            3: "آماده‌سازی نهایی و ورود به پرتاب"}

        root = QVBoxLayout(self)
        root.addWidget(page_title("پایش پرتاب"))

        # ---------------------------------------------------------------
        # ردیف اول: خلاصهٔ پرواز + فشار هوا/دما (طبق تصمیم کاربر، برای
        # خلوت‌تر شدن صفحه و حذف نیاز به اسکرول -- ارتفاع لحظه‌ای و سرعت
        # عمودی از این صفحه حذف شدند، چون در صفحهٔ «ارتفاع و سرعت» هستند)
        # ---------------------------------------------------------------
        top_grid = QGridLayout()
        top_grid.setSpacing(14)
        root.addLayout(top_grid)

        self.card_flight_no = StatCard("🚀 شماره پرواز", "--")
        self.card_uptime = StatCard("⏱ زمان از روشن شدن سیستم", "--")
        self.card_pressure = StatCard("🌫 فشار هوا", "--", icon="")
        self.card_temp = StatCard("🌡 دمای سنسور", "--", icon="")
        # زاویهٔ لحظه‌ایِ راکت نسبت به افق (از شتاب‌سنجِ MPU6050، پیش از هر
        # کالیبراسیون). روی سکو باید تقریباً با زاویه‌ای که دستی تنظیم/اندازه
        # گرفته‌ایم یکی باشد؛ برای همین اینجا کنارِ دما نشان داده می‌شود تا
        # صحتِ حسگر پیش از پرتاب راستی‌آزمایی شود.
        self.card_angle = StatCard(
            "📐 زاویهٔ راکت (افق)", "--", icon="",
            tooltip=(
                "زاویهٔ محورِ طولیِ راکت نسبت به افق، مستقیماً از شتاب‌سنج "
                "MPU6050 و بدون کالیبراسیون (۹۰°=کاملاً عمود). روی سکو این عدد "
                "باید با زاویه‌ای که دستی تنظیم/اندازه گرفته‌اید یکی باشد."))
        cards_top = [self.card_flight_no, self.card_uptime, self.card_pressure,
                     self.card_temp, self.card_angle]
        for i, c in enumerate(cards_top):
            top_grid.addWidget(c, 0, i)
            top_grid.setColumnStretch(i, 1)

        # ---------------------------------------------------------------
        # ردیف دوم: وضعیت سنسورها (کارت‌های رنگی -- عنوان متنی حذف شد؛
        # خود کارت‌ها گویا هستند)
        # ---------------------------------------------------------------
        self.sensor_grid = QGridLayout()
        self.sensor_grid.setSpacing(14)
        root.addLayout(self.sensor_grid)

        self.sensor_cards = {}
        for i, key in enumerate(SENSOR_META):
            label, icon = SENSOR_META[key]
            model = data_manager.sensor_models.get(key, label)
            c = SensorStatusCard(f"{label} ({model})", icon=icon)
            self.sensor_cards[key] = c
            self.sensor_grid.addWidget(c, i // 4, i % 4)

        # ---------------------------------------------------------------
        # ردیف چک‌لیست ترتیبی ایمنی پرتاب (سه دکمهٔ مرحله‌ای)
        # ---------------------------------------------------------------
        root.addWidget(section_title("چک‌لیست ترتیبی ایمنی پرتاب"), alignment=Qt.AlignCenter)

        steps_row = QHBoxLayout()
        steps_row.setSpacing(14)

        self.step1_btn = QPushButton("1️⃣ مرحله یک\nتست سلامت سنسورها")
        self.step1_btn.setObjectName("Step1Button")
        self.step2_btn = QPushButton("2️⃣ مرحله دو\nکالیبراسیون ناوبری")
        self.step2_btn.setObjectName("Step2Button")
        # این مرحله ضبط روی SD را آغاز می‌کند و کاربر را به مرکز کنترل پرواز می‌برد؛
        # پرتاب واقعی توسط کیف پرتاب انجام می‌شود، نه این دکمه.
        self.step3_btn = QPushButton("3️⃣ مرحله سه\nآماده‌سازی نهایی و ورود به پرتاب")
        self.step3_btn.setObjectName("Step3Button")

        # رنگ سایهٔ هر دکمه هماهنگ با رنگ خودش (ظاهر گرافیکی‌تر و نرم‌تر)
        shadow_colors = [
            QColor(79, 209, 197, 90),    # فیروزه‌ای -- مرحله ۱
            QColor(242, 193, 78, 90),    # کهربایی -- مرحله ۲
            QColor(239, 83, 80, 100),    # قرمز -- مرحله ۳ (پرتاب)
        ]

        self.step_buttons = [self.step1_btn, self.step2_btn, self.step3_btn]
        for b, shadow_color in zip(self.step_buttons, shadow_colors):
            b.setMinimumHeight(80)
            b.setCursor(Qt.PointingHandCursor)
            _add_shadow(b, shadow_color)
            steps_row.addWidget(b)

        # طبق الزام: در ابتدا فقط مرحلهٔ ۱ فعال است، بقیه خاموش/کم‌رنگ
        self.step2_btn.setEnabled(False)
        self.step3_btn.setEnabled(False)

        self.step1_btn.clicked.connect(self.run_step1_health_check)
        self.step2_btn.clicked.connect(self.run_step2_calibration)
        self.step3_btn.clicked.connect(self.run_step3_prepare_and_enter_launch)

        root.addWidget(make_card(self._wrap(steps_row)))

        # ---- وضعیت لحظه‌ای چک‌لیست + نوار پیشرفت کالیبراسیون ----
        status_col = QVBoxLayout()

        self.flight_state_label = QLabel("متصل نیست")
        self.flight_state_label.setAlignment(Qt.AlignCenter)
        self.flight_state_label.setProperty("class", "CardValue")
        self.flight_state_label.setWordWrap(True)
        status_col.addWidget(self.flight_state_label)

        self.calib_warning_label = QLabel(
            "⚠️ راکت کاملاً ساکن باشد! در حال محاسبهٔ Static Gyro Bias و ترازبندی جاذبه..."
        )
        self.calib_warning_label.setObjectName("CalibWarning")
        self.calib_warning_label.setAlignment(Qt.AlignCenter)
        self.calib_warning_label.setWordWrap(True)
        self.calib_warning_label.hide()
        status_col.addWidget(self.calib_warning_label)

        self.calib_countdown_label = QLabel("")
        self.calib_countdown_label.setAlignment(Qt.AlignCenter)
        self.calib_countdown_label.setProperty("class", "CardTitleBig")
        self.calib_countdown_label.hide()
        status_col.addWidget(self.calib_countdown_label)

        self.calib_progress = QProgressBar()
        self.calib_progress.setObjectName("CalibProgress")
        self.calib_progress.setRange(0, self.calib_duration)
        self.calib_progress.setValue(0)
        self.calib_progress.setFormat(f"%v / {self.calib_duration} ثانیه")
        self.calib_progress.hide()
        status_col.addWidget(self.calib_progress)

        root.addWidget(make_card(self._wrap(status_col)))

        root.addStretch()

        # ---- تایمرهای داخلی ----
        self.health_check_timer = QTimer(self)
        self.health_check_timer.setInterval(HEALTH_CHECK_TICK_MS)
        self.health_check_timer.timeout.connect(self._health_check_tick)

        self.calib_timer = QTimer(self)
        self.calib_timer.setInterval(1000)
        self.calib_timer.timeout.connect(self._calibration_tick)

        # تایمرهای بازفعال‌سازی دکمهٔ مراحل ۱ و ۲ پس از موفقیت، برای امکان
        # تکرار بدون نیاز به بستن/بازکردن برنامه
        self.step1_retry_timer = QTimer(self); self.step1_retry_timer.setSingleShot(True)
        self.step2_retry_timer = QTimer(self); self.step2_retry_timer.setSingleShot(True)
        self.step1_retry_timer.timeout.connect(lambda: self.step1_btn.setEnabled(True))
        self.step2_retry_timer.timeout.connect(lambda: self.step2_btn.setEnabled(True))

        data_manager.connection_changed.connect(self.on_connection_changed)
        data_manager.telemetry_updated.connect(self.on_telemetry)
        data_manager.mission_changed.connect(self.refresh_static)
        data_manager.sensor_model_changed.connect(self._on_sensor_model_changed)
        data_manager.analysis_ready.connect(self._on_analysis_ready)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._tick_uptime)
        self.refresh_timer.start(1000)

        self.refresh_static()
        self.refresh_all_sensors()

    def _wrap(self, layout):
        w = QWidget()
        w.setObjectName("TransparentContainer")
        w.setLayout(layout)
        return w

    def _on_sensor_model_changed(self, key: str, model_name: str):
        if key in self.sensor_cards:
            label = SENSOR_META[key][0]
            self.sensor_cards[key].set_title(f"{label} ({model_name})")

    def _connection_protocol_fa(self) -> str:
        ct = data_manager.connection_type.upper()
        if ct == "DEMO":
            return "پورت فرضی (آموزشی)"
        return "لورا" if ct == "LORA" else "USB"

    def _lock_all_steps(self):
        """قفل همهٔ دکمه‌های مرحله حین شمارش معکوس کالیبراسیون -- طبق تصمیم
        کاربر، فقط دکمه‌های همین صفحه قفل می‌شوند (نه کل رابط کاربری) و
        کاربر همچنان می‌تواند بین صفحات دیگر جابه‌جا شود. بازکردن دکمه‌ها پس
        از پایان شمارش معکوس در _finish_step2 به‌صورت دقیق (طبق نتیجهٔ
        کالیبراسیون) انجام می‌شود، نه اینجا."""
        for b in self.step_buttons:
            b.setEnabled(False)

    def _confirm_repeat_if_needed(self, step_num: int) -> bool:
        """اگر این مرحله قبلاً با موفقیت انجام شده، پیش از اجرای دوباره‌اش
        تاییدیه بگیر. برمی‌گرداند: آیا اجرا ادامه پیدا کند یا نه."""
        if not self._step_completed.get(step_num):
            return True
        resp = QMessageBox.question(
            self, "تکرار مرحله",
            f"شما قبلاً «{self._step_names[step_num]}» را با موفقیت انجام داده‌اید.\n"
            "مطمئنید می‌خواهید دوباره انجامش دهید؟",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        return resp == QMessageBox.Yes

    def _relock_steps_after(self, step_num: int):
        """وقتی کاربر یکی از مراحل ۱ تا ۳ را دوباره با موفقیت انجام می‌دهد،
        برای ایمنی، همهٔ مراحل بعدی باید دوباره طی شوند (چون شرایط ممکن است
        از آخرین بار عوض شده باشد)."""
        for n in (2, 3):
            if n > step_num:
                self._step_completed[n] = False
        if step_num < 2:
            self.step2_retry_timer.stop()
        for i in range(step_num, len(self.step_buttons)):
            self.step_buttons[i].setEnabled(False)

    # ==================================================================
    # مرحلهٔ ۱: تست سلامت سیستم (System Health Check & BIST)
    # ==================================================================
    def run_step1_health_check(self):
        if not data_manager.connected or not data_manager.active_link:
            self.flight_state_label.setText("ابتدا به کامپیوتر پرواز متصل شوید")
            return

        # دو ماژول اول (بارومتر فشار/دما + شتاب‌سنج) برای تشخیص اوج و باز
        # شدن چتر الزامی‌اند -- بدون آن‌ها کامپیوتر پرواز نمی‌داند کی اوج
        # رسیده و کی چتر را باز کند.
        MANDATORY_MODULES = ("BMP280", "MPU6050")
        missing_mandatory = [k for k in MANDATORY_MODULES
                             if data_manager.sensor_models.get(k) in UNSELECTED_VALUES]
        if missing_mandatory:
            names = " و ".join(SENSOR_META[k][0] for k in missing_mandatory)
            self.flight_state_label.setText(
                "انتخاب ماژول فشار/دما و شتاب‌سنج برای تشخیص اوج و باز شدن چتر الزامی است"
            )
            QMessageBox.warning(
                self, "ماژول الزامی انتخاب نشده",
                f"انتخاب {names} برای تشخیص اوج و باز شدن چتر الزامی است.\n\n"
                "ابتدا از صفحهٔ «انتخاب سنسور» مدل این دو ماژول را انتخاب کنید "
                "(مدل خاصی مهم نیست)، سپس تست سلامت را اجرا کنید.\n"
                "سایر ماژول‌ها اختیاری‌اند: هر چه انتخاب نشود، در تست، مرکز کنترل پرواز و "
                "گزارش هم نخواهد آمد."
            )
            return

        if not self._confirm_repeat_if_needed(1):
            return
        self.step1_retry_timer.stop()

        active_keys = [k for k in SENSOR_META if data_manager.sensor_models.get(k) not in UNSELECTED_VALUES]
        if not active_keys:
            QMessageBox.warning(
                self, "هیچ ماژولی انتخاب نشده",
                "هیچ‌کدام از ماژول‌های سنسور انتخاب نشده‌اند.\n"
                "ابتدا از صفحهٔ «انتخاب سنسور» مدل واقعی سنسورهای نصب‌شده را انتخاب کنید."
            )
            return

        self.step1_btn.setEnabled(False)
        self._health_active_keys = active_keys
        self._health_pending = set(active_keys)
        self._health_elapsed = 0

        # علامت‌گذاری ماژول‌های نادیده‌گرفته‌شده (بدون مدل انتخابی)
        for key in SENSOR_META:
            if key not in active_keys:
                self.sensor_cards[key].set_status("missing", "رد شد از تست (مدل انتخاب نشده)")

        proto = self._connection_protocol_fa()
        self.flight_state_label.setText(
            f"اتصال با پروتکل {proto} برقرار شد\nآغاز تست سلامت..."
        )
        data_manager.active_link.send_command("STEP1_TEST")
        for key in active_keys:
            self.sensor_cards[key].set_status("pending", "در حال تست...")

        self.health_check_timer.start()

    def _health_check_tick(self):
        self._health_elapsed += 1

        need_telemetry = bool({"BMP280", "MPU6050", "AHT21", "UV"} & self._health_pending)
        if need_telemetry and data_manager.active_link:
            response = data_manager.active_link.send_command("GET_TELEMETRY")
            self._evaluate_telemetry_sample(response)

        # وضعیت SD و دوربین هر دو در پاسخ GET_STATUS گزارش می‌شوند
        if {"SD", "CAMERA"} & self._health_pending and data_manager.active_link:
            response = data_manager.active_link.send_command("GET_STATUS")
            self._evaluate_status_sample(response)

        if "GPS" in self._health_pending:
            self._evaluate_gps_sample()

        self.flight_state_label.setText(
            f"در حال تست سلامت سنسورها... ({self._health_elapsed}/{self.health_check_duration} ثانیه)"
        )

        if self._health_elapsed >= self.health_check_duration:
            self.health_check_timer.stop()
            self._finish_step1()

    def _evaluate_telemetry_sample(self, response: str):
        if not response or not response.startswith("TELEM,"):
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
        if packet:
            data_manager.telemetry_updated.emit(packet)

        pressure = packet.get("pressure")
        if "BMP280" in self._health_pending and pressure is not None:
            if PRESSURE_MIN_HPA <= pressure <= PRESSURE_MAX_HPA:
                self._mark_sensor_passed("BMP280", f"✅ تایید شد ({pressure:.0f} hPa)")

        if "MPU6050" in self._health_pending and all(
                k in packet for k in ("accel_x", "accel_y", "accel_z")):
            ax, ay, az = packet["accel_x"], packet["accel_y"], packet["accel_z"]
            accel_total_g = math.sqrt(ax * ax + ay * ay + az * az) / G0
            if ACCEL_G_MIN <= accel_total_g <= ACCEL_G_MAX:
                self._mark_sensor_passed("MPU6050", f"✅ تایید شد ({accel_total_g:.2f}g)")

        if ("AHT21" in self._health_pending and "humidity" in packet
                and "temperature_aht" in packet):
            humidity, temp_aht = packet["humidity"], packet["temperature_aht"]
            if (HUMIDITY_MIN <= humidity <= HUMIDITY_MAX
                    and AHT_TEMP_MIN <= temp_aht <= AHT_TEMP_MAX):
                self._mark_sensor_passed("AHT21", f"✅ تایید شد ({temp_aht:.1f}°C / {humidity:.0f}%)")

        if "UV" in self._health_pending and "uv_index" in packet:
            uv = packet["uv_index"]
            if UV_INDEX_MIN <= uv <= UV_INDEX_MAX:
                self._mark_sensor_passed("UV", f"✅ تایید شد (شاخص {uv:.1f})")

    def _evaluate_status_sample(self, response: str):
        """پاسخ GET_STATUS: STATUS,<battery>,<bmp>,<mpu>,<sd>,<camera>
        (فیلد دوربین اختیاری است -- فریمورهای قدیمی‌تر آن را ندارند)."""
        if not response or not response.startswith("STATUS,"):
            return
        parts = response.split(",")
        if "SD" in self._health_pending and len(parts) > 4 and parts[4].strip() == "ok":
            self._mark_sensor_passed("SD", "✅ تایید شد")
        # وضعیت دوربین OV7670 (راه‌اندازی موفق -- init OK)
        if "CAMERA" in self._health_pending and len(parts) > 5 and parts[5].strip() == "ok":
            self._mark_sensor_passed("CAMERA", "✅ تایید شد (راه‌اندازی موفق)")

    def _evaluate_gps_sample(self):
        # حالت آموزشی: شبیه‌ساز یک Fix واقعی نزدیک سمنان تولید می‌کند، پس
        # ماژول GPS مثل بقیهٔ سنسورها تایید می‌شود.
        if data_manager.demo_mode:
            self._mark_sensor_passed("GPS", "✅ تایید شد (Fix GPS دریافت شد)")
            return

        # حالت واقعی: فریمور فعلی هیچ فیلد وضعیتی برای GPS گزارش نمی‌کند
        # (قابلیت آینده -- نگاه کنید به core/data_manager.py). بنابراین حتی
        # اگر کاربر مدل واقعی GPS را انتخاب کرده باشد، امکان تایید/رد واقعی
        # وجود ندارد؛ برای جلوگیری از مسدود شدن ناعادلانهٔ کاربرانی که فعلاً
        # GPS متصل ندارند، GPS را از معیار قبولی/ردی مرحلهٔ ۱ کنار می‌گذاریم
        # و فقط اطلاع‌رسانی می‌کنیم.
        self._health_pending.discard("GPS")
        self.sensor_cards["GPS"].set_status(
            "pending", "ماژول انتخاب شد -- بررسی وضعیت هنوز در فریمور پیاده‌سازی نشده"
        )

    def _mark_sensor_passed(self, key: str, text: str):
        if key not in self._health_pending:
            return
        self._health_pending.discard(key)
        self.sensor_cards[key].set_status("ok", text)

    def _finish_step1(self):
        failed_keys = list(self._health_pending)  # هرچه تا انتهای ۳۰ ثانیه تایید نشد، مردود است
        for key in failed_keys:
            self.sensor_cards[key].set_status("error", "❌ تایید نشد (خارج از محدودهٔ مجاز یا بدون پاسخ)")

        skipped_count = len(SENSOR_META) - len(self._health_active_keys)
        passed_count = len(self._health_active_keys) - len(failed_keys)

        if not failed_keys:
            self.flight_state_label.setText(
                f"✅ تست سلامت با موفقیت انجام شد — {passed_count} ماژول سالم، {skipped_count} ماژول نصب‌نشده/رد شده"
            )
            self._step_completed[1] = True
            self._relock_steps_after(1)
            self.step2_btn.setEnabled(True)
            self.step1_retry_timer.start(RETRY_COOLDOWN_MS)
        else:
            failed_names = "، ".join(SENSOR_META[k][0] for k in failed_keys)
            self.flight_state_label.setText(
                "❌ تست سلامت ناموفق — یک یا چند ماژول در محدودهٔ مجاز تایید نشدند"
            )
            QMessageBox.warning(
                self, "تست سلامت ناموفق",
                f"ماژول(های) زیر در طول ۳۰ ثانیهٔ تست تایید نشدند:\n{failed_names}\n\n"
                "لطفاً اتصال و سلامت سنسورها را بررسی کرده و دوباره تلاش کنید."
            )
            self.step1_btn.setEnabled(True)

    # ==================================================================
    # مرحلهٔ ۲: کالیبراسیون و ترازبندی ناوبری (INS/IMU Static Alignment)
    # ==================================================================
    def run_step2_calibration(self):
        # چک‌لیست پیش‌نیاز: اطلاعات مأموریت/نازل وارد و ذخیره شده، و به
        # کامپیوتر پرواز منتقل شده باشند -- طبق درخواست کاربر، این سه شرط
        # (همراه با خودِ وضعیت اتصال) خودکار توسط برنامه در همین یک دیالوگ
        # بررسی می‌شوند و کالیبراسیون فقط با تایید هر سه (و کلیک صریح کاربر
        # روی «شروع کالیبراسیون») آغاز می‌شود.
        dialog = CalibrationChecklistDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return

        if not data_manager.connected or not data_manager.active_link:
            # احتیاط: اتصال دقیقاً همین حین باز بودن دیالوگ قطع شده باشد
            self.flight_state_label.setText("اتصال قطع شد -- دوباره تلاش کنید")
            return

        asl = data_manager.mission.altitude_msl
        pitch = data_manager.mission.launch_angle

        if not self._confirm_repeat_if_needed(2):
            return
        self.step2_retry_timer.stop()

        # طبق تصمیم کاربر: در طول شمارش معکوس، هر سه دکمهٔ همین صفحه قفل
        # می‌شود (نه کل نرم‌افزار) تا کاربر بتواند صفحات دیگر را مشاهده کند
        self._lock_all_steps()

        self.flight_state_label.setText("در حال کالیبره ناوبری...")
        data_manager.active_link.send_command(f"CALIB:{asl},{pitch}")

        self._calib_seconds_left = self.calib_duration
        self._calib_acked = False
        self.calib_progress.setRange(0, self.calib_duration)
        self.calib_progress.setFormat(f"%v / {self.calib_duration} ثانیه")
        self.calib_progress.setValue(0)
        self.calib_progress.show()
        self.calib_warning_label.show()
        self.calib_countdown_label.setText(f"⏳ {self._calib_seconds_left} ثانیه باقی‌مانده")
        self.calib_countdown_label.show()
        self.calib_timer.start()

    def _calibration_tick(self):
        self._calib_seconds_left -= 1
        elapsed = self.calib_duration - self._calib_seconds_left
        self.calib_progress.setValue(elapsed)
        self.calib_countdown_label.setText(f"⏳ {max(self._calib_seconds_left, 0)} ثانیه باقی‌مانده")

        # بررسی دوره‌ای ACK از STM32 بدون قطع کردن شمارش معکوس
        if not self._calib_acked and data_manager.active_link:
            ack = data_manager.active_link.send_command("CALIB_STATUS")
            if ack.strip().startswith("ACK:CALIB_OK"):
                self._calib_acked = True

        if self._calib_seconds_left <= 0:
            self.calib_timer.stop()
            self._finish_step2()

    def _finish_step2(self):
        self.calib_warning_label.hide()
        self.calib_progress.hide()
        self.calib_countdown_label.hide()

        # دکمه‌ها را دوباره باز می‌کنیم؛ وضعیت دقیق هرکدام را زیر تعیین می‌کنیم
        self.step1_btn.setEnabled(False)   # مرحلهٔ ۱ قبلاً با موفقیت انجام شده
        self._relock_steps_after(2)   # مرحلهٔ ۳ را قفل کن، بعد طبق نتیجه باز می‌کنیم

        if self._calib_acked:
            self.flight_state_label.setText("✅ کالیبراسیون ناوبری با موفقیت انجام شد")
            self._step_completed[2] = True
            self.step3_btn.setEnabled(True)
            self.step2_retry_timer.start(RETRY_COOLDOWN_MS)
            # پس از کالیبراسیون موفق، وضعیت پرواز به «آماده روی سکو» می‌رود
            data_manager.set_flight_phase("on_pad")
        else:
            self.step2_btn.setEnabled(True)
            self.flight_state_label.setText("❌ کالیبراسیون ناموفق — تاییدیه از کامپیوتر پرواز دریافت نشد")
            QMessageBox.warning(
                self, "کالیبراسیون ناموفق",
                "پس از پایان ۶۰ ثانیه، تاییدیهٔ کالیبراسیون از کامپیوتر پرواز دریافت نشد.\n"
                "لطفاً از سکون کامل راکت و برقراری ارتباط اطمینان حاصل کرده و دوباره تلاش کنید."
            )

    # ==================================================================
    # مرحلهٔ ۳: آماده‌سازی نهایی، شروع ضبط روی SD و ورود به مرکز کنترل پرواز
    # ==================================================================
    def _launch_capability(self):
        """پیش‌بینی فیزیکی پرواز با اطلاعات فعلی فرم‌ها (همان کارت پیش‌بینی
        صفحهٔ مأموریت). خروجی: (قابلیت پرتاب، پیام‌های هشدار).

        قابلیت پرتاب = پیش‌بینی معتبر + هیچ هشدار نارنجی‌ای (همان‌هایی که در
        باکس «پیش‌بینی عملکرد پرواز» دیده می‌شوند). هم در حالت واقعی و هم
        آموزشی یکسان است -- فیزیک از اطلاعات ورودی می‌آید."""
        try:
            pl = data_manager.build_preflight_payload()
            preds = predict_summary(SimParams(
                total_mass_kg=float(pl.get("total_mass") or 0.0),
                propellant_mass_g=float(pl.get("propellant_mass") or 0.0),
                body_diameter_m=float(pl.get("body_diameter") or 0.08),
                body_length_m=float(pl.get("body_length") or 0.0),
                body_section_length_m=float(pl.get("body_section_length") or 0.0),
                nose_length_m=float(pl.get("nose_length") or 0.0),
                nose_cone=str(pl.get("nose_cone") or "اویو"),
                fin_shape=str(pl.get("fin_shape") or "ذوزنقه‌ای"),
                fin_count=int(pl.get("fin_count") or 0),
                fin_root_chord_m=float(pl.get("fin_root_chord") or 0.0),
                fin_tip_chord_m=float(pl.get("fin_tip_chord") or 0.0),
                fin_span_m=float(pl.get("fin_span") or 0.0),
                fin_sweep_m=float(pl.get("fin_sweep") or 0.0),
                cp_from_nose_m=pl.get("cp_from_nose"),
                cg_from_nose_m=pl.get("cg_from_nose"),
                stability_margin_calibers=pl.get("stability_margin_calibers"),
                aero_defaulted=bool(pl.get("aero_defaulted", False)),
                design_source=str(pl.get("design_source") or "manual"),
                launch_angle_deg=float(pl.get("launch_angle") or 90.0),
                altitude_msl_m=float(pl.get("altitude_msl") or 1130.0),
                throat_diameter_mm=float(pl.get("throat_diameter") or 0.0),
                exit_diameter_mm=float(pl.get("exit_diameter") or 0.0),
                chamber_pressure_bar=float(pl.get("chamber_pressure_bar") or 40.0),
                chute_diameter_m=float(pl.get("chute_diameter") or 0.0),
                sensor_models=dict(pl.get("sensor_models") or {}),
            ))
        except Exception:
            return True, []   # بدون شبیه‌سازی مانع نمی‌شویم (حالت واقعی بدون داده)
        warns = [w for w in (preds.get("warnings") or [])]
        ok = bool(preds.get("valid")) and not warns
        return ok, warns

    def run_step3_prepare_and_enter_launch(self):
        if not data_manager.connected or not data_manager.active_link:
            self.flight_state_label.setText("ابتدا به کامپیوتر پرواز متصل شوید")
            return

        # ---- گیت قابلیت پرتاب (هم آموزشی، هم واقعی) ----
        capable, warns = self._launch_capability()
        if not capable:
            warn_lines = "\n".join(f"• {w}" for w in warns[:6]) or "• پیش‌بینی پرواز نامعتبر است."
            if not self._launch_warned:
                # بار اول: سد کامل + هدایت به صفحهٔ مأموریت برای اصلاح اطلاعات
                self._launch_warned = True
                self.flight_state_label.setText("❌ راکت قابلیت پرتاب ندارد — اطلاعات مأموریت/نازل را اصلاح کنید")
                QMessageBox.warning(
                    self, "راکت قابلیت پرتاب ندارد",
                    "بر اساس پیش‌بینی عملکرد پرواز (باکس پیش‌بینی در صفحهٔ اطلاعات مأموریت)، "
                    "این راکت با اطلاعات فعلی قابلیت پرتاب ندارد:\n\n"
                    f"{warn_lines}\n\n"
                    "به صفحهٔ «اطلاعات مأموریت و نازل» می‌روید؛ باکس «پیش‌بینی عملکرد پرواز» "
                    "را نگاه کنید و اطلاعات را درست کنید (هشدارهای نارنجی باید سبز شوند)، "
                    "ذخیره و ارسال مجدد کنید، سپس دوباره مرحلهٔ ۳ را بزنید."
                )
                data_manager.navigate_requested.emit("اطلاعات مأموریت و نازل")
                return
            # بار دوم پس از اصلاح: اگر هنوز قابل پرتاب نیست، تاییدیهٔ صریح بگیر
            box = QMessageBox(self)
            box.setWindowTitle("ادامه با پرتاب ناموفق؟")
            box.setIcon(QMessageBox.Warning)
            box.setText("طبق پیش‌بینی، بر اساس اطلاعات ورودی، پرتاب انجام نخواهد شد.")
            box.setInformativeText(
                "هنوز این هشدارها برقرارند:\n\n" + warn_lines +
                "\n\nآیا مطمئنید می‌خواهید ادامه دهید؟"
            )
            yes_btn = box.addButton("بله، ادامه بده", QMessageBox.AcceptRole)
            no_btn = box.addButton("نه، برگرد و اصلاح کن", QMessageBox.RejectRole)
            box.setDefaultButton(no_btn)
            box.exec()
            if box.clickedButton() is not yes_btn:
                data_manager.navigate_requested.emit("اطلاعات مأموریت و نازل")
                return
        else:
            self._launch_warned = False

        # دیالوگ تایید پرتاب با دو دکمهٔ فارسی مطابق درخواست کاربر
        box = QMessageBox(self)
        box.setWindowTitle("آماده پرتاب؟")
        box.setIcon(QMessageBox.Question)
        box.setText("آیا آماده پرتاب هستید؟")
        box.setInformativeText(
            "با زدن «آره، بزن بریم» وارد مرکز کنترل پرواز می‌شوید و ضبط داده‌ها "
            "روی کارت حافظه (SD) آغاز می‌گردد.\n"
            "پرتاب توسط کیف پرتاب انجام می‌شود و برنامه به‌صورت خودکار از روی "
            "دادهٔ لورا مراحل پرواز را تشخیص می‌دهد."
        )
        yes_btn = box.addButton("آره، بزن بریم", QMessageBox.AcceptRole)
        no_btn = box.addButton("نه، صبر کن", QMessageBox.RejectRole)
        box.setDefaultButton(no_btn)
        box.exec()
        if box.clickedButton() is not yes_btn:
            return

        self.step3_btn.setEnabled(False)
        self.flight_state_label.setText("در حال شروع ضبط روی کارت SD...")
        response = data_manager.active_link.send_command("STEP2_START_REC")

        if not response.strip().startswith("ACK:STEP2_REC_OK"):
            self.flight_state_label.setText("❌ شروع ضبط ناموفق بود — کارت SD یا اتصال را بررسی کنید")
            QMessageBox.warning(
                self, "شروع ضبط ناموفق",
                "کامپیوتر پرواز تاییدیهٔ شروع ضبط روی SD را ارسال نکرد.\nکارت SD و اتصال را بررسی کنید."
            )
            self.step3_btn.setEnabled(True)
            return

        data_manager.update_sensor_status("SD", "ok", "در حال ضبط (LOGGING)")

        # بررسی اینکه ماژول‌های انتخاب‌شده واقعاً در حال ذخیرهٔ داده هستند یا نه
        _, not_recording = self._check_modules_recording()
        if not_recording:
            names = "، ".join(SENSOR_META[k][0] for k in not_recording)
            QMessageBox.warning(
                self, "هشدار ذخیرهٔ داده",
                "ضبط روی کارت SD آغاز شد، اما ماژول(های) زیر که انتخاب کرده‌اید "
                f"در حال ذخیرهٔ داده نیستند:\n{names}\n\n"
                "اتصال و سلامت این ماژول‌ها را بررسی کنید یا اگر عمداً نصب نکرده‌اید، "
                "مدل آن‌ها را در صفحهٔ «انتخاب سنسور» روی «نصب نشده» بگذارید."
            )

        self._step_completed[3] = True

        # ارسال دستور مسلح‌سازی/آماده‌سازی نهایی به کامپیوتر پرواز (یک‌بار،
        # همین‌جا). پرتاب واقعی توسط کیف پرتاب و بیرون از برنامه است.
        # پاسخ بررسی می‌شود: اگر مأموریت نامعتبر باشد (مثلاً وزن سوخت صفر یا
        # بیشتر از وزن کل)، کامپیوتر پرواز مسلح نمی‌شود و پرتابی رخ نخواهد
        # داد -- قبلاً این خطا نادیده گرفته می‌شد و برنامه بی‌خبر وارد شمارش
        # معکوس می‌شد و برای همیشه روی سکو می‌ماند!
        try:
            arm_response = (data_manager.active_link.send_command("STEP3_ARM_LAUNCH") or "").strip()
        except Exception:
            arm_response = ""
        if not arm_response.startswith("ACK"):
            detail = ""
            try:
                pl = data_manager.build_preflight_payload()
                preds = predict_summary(SimParams(
                    total_mass_kg=float(pl.get("total_mass") or 0.0),
                    propellant_mass_g=float(pl.get("propellant_mass") or 0.0),
                    body_diameter_m=float(pl.get("body_diameter") or 0.08),
                    body_length_m=float(pl.get("body_length") or 0.0),
                    body_section_length_m=float(pl.get("body_section_length") or 0.0),
                    nose_length_m=float(pl.get("nose_length") or 0.0),
                    nose_cone=str(pl.get("nose_cone") or "اویو"),
                    fin_shape=str(pl.get("fin_shape") or "ذوزنقه‌ای"),
                    fin_count=int(pl.get("fin_count") or 0),
                    fin_root_chord_m=float(pl.get("fin_root_chord") or 0.0),
                    fin_tip_chord_m=float(pl.get("fin_tip_chord") or 0.0),
                    fin_span_m=float(pl.get("fin_span") or 0.0),
                    fin_sweep_m=float(pl.get("fin_sweep") or 0.0),
                    cp_from_nose_m=pl.get("cp_from_nose"),
                    cg_from_nose_m=pl.get("cg_from_nose"),
                    stability_margin_calibers=pl.get("stability_margin_calibers"),
                    aero_defaulted=bool(pl.get("aero_defaulted", False)),
                    design_source=str(pl.get("design_source") or "manual"),
                    launch_angle_deg=float(pl.get("launch_angle") or 90.0),
                    altitude_msl_m=float(pl.get("altitude_msl") or 1130.0),
                    throat_diameter_mm=float(pl.get("throat_diameter") or 0.0),
                    exit_diameter_mm=float(pl.get("exit_diameter") or 0.0),
                    chamber_pressure_bar=float(pl.get("chamber_pressure_bar") or 40.0),
                    chute_diameter_m=float(pl.get("chute_diameter") or 0.0),
                    sensor_models=dict(pl.get("sensor_models") or {}),
                ))
                if preds.get("warnings"):
                    detail = "\n\nهشدارهای پیش‌بینی پرواز:\n• " + "\n• ".join(preds["warnings"][:5])
            except Exception:
                pass
            self._step_completed[3] = False
            self.step3_btn.setEnabled(True)
            self.flight_state_label.setText("❌ کامپیوتر پرواز مسلح نشد — اطلاعات مأموریت/موتور را بررسی کنید")
            QMessageBox.warning(
                self, "مسلح‌سازی ناموفق",
                "کامپیوتر پرواز دستور مسلح‌سازی را تایید نکرد (پاسخ: "
                f"{arm_response or 'بدون پاسخ'}).\n"
                "معمولاً دلیلش نامعتبربودن پارامترهای پرواز است: وزن سوخت صفر، سوخت بیشتر از وزن کل، "
                "یا مشخصات ناقص نازل." + detail + "\n\n"
                "این موارد را در صفحهٔ «اطلاعات مأموریت و نازل» اصلاح، ذخیره و دوباره ارسال کنید، "
                "سپس مرحلهٔ ۳ را تکرار کنید."
            )
            return

        # آغاز ثبت خام تله‌متری لورا (برای ذخیرهٔ خودکار پس از فرود) و ورود به
        # فاز «شمارش معکوس» + انتقال به مرکز کنترل پرواز. مرکز کنترل پرواز هیچ دکمه‌ای
        # ندارد و فقط وضعیت را اطلاع می‌دهد.
        data_manager.start_lora_logging()
        data_manager.set_flight_phase("countdown")
        self._launch_warned = False   # پرواز بعدی دوباره از سد سخت شروع می‌شود
        self.flight_state_label.setText("✅ ضبط آغاز شد — ورود به مرکز کنترل پرواز و شمارش معکوس")
        data_manager.navigate_requested.emit("مرکز کنترل پرواز")

    def _check_modules_recording(self):
        """بررسی اینکه کدام‌یک از ماژول‌های انتخاب‌شده واقعاً در حال ذخیرهٔ
        داده روی SD هستند. پاسخ مورد انتظار از فریمور:
            REC_STATUS,BMP280=1,MPU6050=1,AHT21=1,UV=1,CAMERA=1
        (۱ = در حال ذخیره، ۰ = ذخیره نمی‌کند). فیلدهای غائب به‌معنی «نامشخص»
        در نظر گرفته می‌شوند و برای جلوگیری از هشدار نادرست، ذخیره‌شونده
        فرض می‌شوند."""
        active_keys = [k for k in SENSOR_META
                       if data_manager.sensor_models.get(k) not in UNSELECTED_VALUES]
        recording, not_recording = [], []

        response = ""
        if data_manager.active_link:
            try:
                response = data_manager.active_link.send_command("GET_REC_STATUS") or ""
            except Exception:
                response = ""

        rec_map = {}
        if response.strip().startswith("REC_STATUS"):
            for token in response.strip().split(",")[1:]:
                if "=" in token:
                    k, _, v = token.partition("=")
                    rec_map[k.strip()] = v.strip() == "1"

        for key in active_keys:
            # اگر فریمور وضعیت این ماژول را گزارش نکرده، «در حال ذخیره» فرض می‌شود
            is_rec = rec_map.get(key, True)
            if is_rec:
                recording.append(key)
                data_manager.update_sensor_status(key, "ok", "در حال ذخیرهٔ داده")
            else:
                not_recording.append(key)
                data_manager.update_sensor_status(key, "error", "داده ذخیره نمی‌شود")
        return recording, not_recording

    def _on_analysis_ready(self, results: dict):
        # کارت‌های خلاصه (اوج/سرعت/مدت) به درخواست کاربر از این صفحه حذف شدند؛
        # این مقادیر در تب‌های «شاخص‌های پرواز» و «ارتفاع / سرعت» کامل موجودند.
        pass

    def refresh_static(self):
        self.card_flight_no.set_value(data_manager.mission.flight_number or "--")

    def _tick_uptime(self):
        if data_manager.uptime_seconds is not None:
            secs = data_manager.uptime_seconds
        elif data_manager.connected:
            secs = int(time.time() - self._start_time)
        else:
            self.card_uptime.set_value("--")
            return
        h, rem = divmod(int(secs), 3600)
        m, s = divmod(rem, 60)
        self.card_uptime.set_value(f"{h:02d}:{m:02d}:{s:02d}")

    def refresh_all_sensors(self):
        for key, card in self.sensor_cards.items():
            status = data_manager.sensors_status.get(key)
            self._apply_sensor_status(key, card, status)

    def _apply_sensor_status(self, key: str, card: SensorStatusCard, status):
        if status is None or status.state == "unknown":
            card.set_status("pending", "در حال بررسی...")
        elif status.state == "missing":
            text = "غیرفعال / نصب نشده" if key == "GPS" else "نصب نشده"
            card.set_status("missing", text)
        elif status.state == "error":
            card.set_status("error", f"خطا: {status.message or 'ارتباط برقرار نشد'}")
        elif status.state == "ok":
            card.set_status("ok", status.message or "OK")
        else:
            card.set_status("pending", "در حال بررسی...")

        if key == "SD":
            if data_manager.sd_total_mb:
                free_gb = data_manager.sd_free_mb / 1024
                total_gb = data_manager.sd_total_mb / 1024
                writing = "آماده" if status and status.state == "ok" else "نامشخص"
                card.set_extra(f"ظرفیت: {total_gb:.1f}GB   |   آزاد: {free_gb:.1f}GB   |   نوشتن: {writing}")
            else:
                card.set_extra("")

    def on_connection_changed(self, connected: bool):
        if connected:
            self._start_time = time.time()
            # با اتصال تازه و پیش از کالیبراسیون، وضعیت «در حال نصب راکت» است
            if data_manager.flight_phase == "idle":
                data_manager.set_flight_phase("installing")

    def on_telemetry(self, packet: dict):
        if "sensor_status_changed" in packet:
            key = packet["sensor_status_changed"]
            if key in self.sensor_cards:
                self._apply_sensor_status(key, self.sensor_cards[key], data_manager.sensors_status.get(key))

        if "pressure" in packet:
            p = packet["pressure"]
            self.card_pressure.set_value(f"{p:.1f}")
            self.card_pressure.set_unit("hPa")
            self.card_pressure.set_status("info")

        if "temperature" in packet:
            temp = packet["temperature"]
            self.card_temp.set_value(f"{temp:.1f}")
            self.card_temp.set_unit("°C")
            self.card_temp.set_status("info")

        # زاویهٔ محورِ طولی راکت نسبت به «افق» از شتاب‌سنج MPU6050.
        # بردار شتاب ساکن: ax = -a·cos(θ)، az = a·sin(θ) (θ از افق) → θ = atan2(az, -ax)
        # بنابراین روی سکو دقیقاً «زاویهٔ پرتاب» نشان داده می‌شود (۹۰° = عمود).
        # (فرمول قبلی atan2(-ax, …) انحراف از عمود می‌داد = ۹۰ − زاویهٔ پرتاب.)
        if all(k in packet for k in ("accel_x", "accel_y", "accel_z")):
            ax = packet["accel_x"]
            az = packet["accel_z"]
            angle = math.degrees(math.atan2(az, -ax))
            self.card_angle.set_value(f"{angle:.1f}")
            self.card_angle.set_unit("°")
            self.card_angle.set_status("info")

        if "sd_total_mb" in packet or "sd_free_mb" in packet:
            self._apply_sensor_status("SD", self.sensor_cards["SD"], data_manager.sensors_status.get("SD"))
