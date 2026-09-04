# -*- coding: utf-8 -*-
"""
ui/main_window.py
-------------------
پنجره اصلی برنامه: منوی کناری راست‌چین + نوار پایین با فلش چپ/راست
براى جابه‌جایی بین صفحات با QStackedWidget.
"""
import datetime
import os
import sys
from PySide6.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
                                QPushButton, QStackedWidget, QLabel, QButtonGroup,
                                QScrollArea, QMessageBox)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication

from ui.widgets import PageNavBar, TopStatusBar
from core.data_manager import data_manager
from core.version import APP_VERSION, APP_NAME
from core.jalali import gregorian_date_to_jalali_str
from core.design_transfer import read_design_transfer, remove_design_transfer
from pages.dashboard import DashboardPage
from pages.hud_dashboard import HudDashboardPage
from pages.mission import MissionPage
from pages.communication import CommunicationPage
from pages.sensor_modules import SensorModulesPage
from ui.analysis_hub import AnalysisHubPage
from pages.report import ReportPage

# ساختار (درخواست کاربر): صفحاتِ آماده‌سازی/پرواز به‌ترتیب زیر؛ سپس سربرگ
# «تحلیل‌ها» و صفحهٔ «تحلیل پرواز» با هر ۹ تب تحلیلِ پس از پرواز.
NAV_ITEMS = [
    ("ارتباط با کامپیوتر پرواز", CommunicationPage),   # صفحهٔ اول برنامه
    ("انتخاب سنسور", SensorModulesPage),
    ("اطلاعات مأموریت و نازل", MissionPage),
    ("پایش پرتاب", DashboardPage),
    ("مرکز کنترل پرواز", HudDashboardPage),
    ("تحلیل پرواز", AnalysisHubPage),
    ("تهیه گزارش", ReportPage),          # صفحهٔ مستقل، زیر «تحلیل پرواز»
]

# نام‌های قدیمی ناوبری → نام صفحهٔ جدید («مرکز کنترل پرواز» قبلاً «داشبورد زنده» بود)
NAV_ALIASES = {
    "گزارش نهایی": "تهیه گزارش",
    "داشبورد زنده": "مرکز کنترل پرواز",
}


class SidebarNavButton(QPushButton):
    """دکمه اختصاصی سایدبار که متن را به سمت راست هدایت می‌کند"""
    def __init__(self, text, parent=None):
        super().__init__("", parent)
        self.setLayoutDirection(Qt.LeftToRight)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 16, 0)
        layout.setSpacing(0)

        # هل دادن متن به سمت راست
        layout.addStretch()

        self.label = QLabel(text)
        self.label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.label.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout.addWidget(self.label)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._update_window_title()
        self.setLayoutDirection(Qt.RightToLeft)
        self.setMinimumSize(1000, 650)
        self._apply_startup_geometry()

        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ---- نوار وضعیت بالای صفحه ----
        self.top_bar = TopStatusBar()
        self.top_bar.set_app_version(APP_VERSION)
        self.top_bar.set_demo_mode(data_manager.demo_mode)
        data_manager.demo_mode_changed.connect(self._on_demo_mode_changed)
        outer.addWidget(self.top_bar)

        content_row = QWidget()
        content_row.setLayoutDirection(Qt.RightToLeft)
        root_layout = QHBoxLayout(content_row)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ---- منوی کناری ----
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(240)
        sidebar.setLayoutDirection(Qt.RightToLeft)

        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(8, 0, 8, 12)
        side_layout.setSpacing(4)

        title = QLabel("کامپیوتر پرواز راکت")
        title.setObjectName("SidebarTitle")
        title.setAlignment(Qt.AlignCenter)
        side_layout.addWidget(title)

        self.stack = QStackedWidget()
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)

        self._pages = []
        for i, (name, page_cls) in enumerate(NAV_ITEMS):
            if name == "تحلیل پرواز":
                # سربرگ گروه تحلیل‌ها (درخواست کاربر: کمی بولد و بزرگ‌تر)
                header = QLabel("تحلیل‌ها")
                header.setObjectName("NavGroupHeader")
                side_layout.addWidget(header)
            btn = SidebarNavButton(name)
            btn.setObjectName("NavButton")
            btn.setCheckable(True)
            btn.setFixedHeight(42)
            self.nav_group.addButton(btn, i)
            side_layout.addWidget(btn)

            page = page_cls()
            self._pages.append(page)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QScrollArea.NoFrame)
            scroll.setWidget(page)
            self.stack.addWidget(scroll)

        side_layout.addStretch()
        self.nav_group.idClicked.connect(self._on_nav_clicked)

        # ---- دکمهٔ اجرای برنامهٔ خواهر: طراح راکت (پروسهٔ جدا) ----
        self.btn_designer = SidebarNavButton("طراح راکت")
        self.btn_designer.setObjectName("DesignerButton")
        self.btn_designer.setFixedHeight(42)
        # متن این دکمه -- برخلاف دکمه‌های ناوبری -- وسط‌چین باشد (درخواست کاربر)
        d_lay = self.btn_designer.layout()
        d_lay.setContentsMargins(8, 0, 8, 0)
        d_lay.addStretch()                       # استرچ قرینه در سمت چپ
        self.btn_designer.label.setAlignment(Qt.AlignCenter)
        # رنگ کهربایی مستقیم روی لیبل؛ قانون QSSِ «:hover QLabel» رنگ پایه را در
        # palette لغو می‌کند (رفتار شناخته‌شدهٔ Qt در قواعد فرزندیِ کشویی)
        self.btn_designer.label.setStyleSheet(
            "color:#ffb020; background:transparent; font-size:14px; font-weight:bold;")
        self.btn_designer.setToolTip(
            "برنامهٔ طراح راکت را در پنجرهٔ جدا باز می‌کند: نقشهٔ به مقیاس، "
            "مرکز ثقل و مرکز فشار، حاشیهٔ پایداری و راهنمای ساخت")
        self.btn_designer.clicked.connect(self._launch_designer)
        side_layout.addWidget(self.btn_designer)

        root_layout.addWidget(sidebar)
        root_layout.addWidget(self.stack, stretch=1)

        outer.addWidget(content_row, stretch=1)

        # ---- نوار پایین: فلش چپ/راست براى پیمایش بین صفحات ----
        self.nav_bar = PageNavBar()
        outer.addWidget(self.nav_bar)

        self.nav_bar.prev_requested.connect(self._go_prev)
        self.nav_bar.next_requested.connect(self._go_next)

        self.nav_group.button(0).setChecked(True)
        self._set_current_index(0)

        # ---- به‌روزرسانی نوار وضعیت بالای صفحه ----
        data_manager.connection_changed.connect(self._on_connection_changed)
        data_manager.telemetry_updated.connect(self._on_telemetry_for_topbar)
        data_manager.navigate_requested.connect(self._on_navigate_requested)
        data_manager.telemetry_saved.connect(self._on_telemetry_saved)

        # RocketDesigner در یک پردازش جدا اجرا می‌شود. صف JSON مشترک را
        # مرتب بررسی می‌کنیم تا دکمهٔ «ارسال به ایستگاه» نیاز به اتصال شبکه یا
        # اجرای دوبارهٔ ایستگاه نداشته باشد.
        self._last_design_transfer_id = ""
        self._design_transfer_timer = QTimer(self)
        self._design_transfer_timer.setInterval(350)
        self._design_transfer_timer.timeout.connect(self._poll_design_transfer)
        self._design_transfer_timer.start()
        self._poll_design_transfer()

        self._clock_timer = QTimer(self)
        self._clock_timer.timeout.connect(self._tick_clock)
        self._clock_timer.start(1000)
        self._tick_clock()

    def _launch_designer(self):
        """اجرای طراح راکت به‌صورت پروسهٔ مستقل (بدون قفل‌کردن ایستگاه)."""
        import subprocess
        designer_main = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "..", "RocketDesigner", "main.py")
        designer_main = os.path.normpath(designer_main)
        if not os.path.exists(designer_main):
            QMessageBox.warning(
                self, "طراح راکت",
                "پوشهٔ RocketDesigner کنار برنامه پیدا نشد.")
            return
        try:
            subprocess.Popen([sys.executable, designer_main],
                             cwd=os.path.dirname(designer_main),
                             env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        except OSError as e:
            QMessageBox.warning(self, "طراح راکت",
                                f"اجرای برنامه ممکن نشد:\n{e}")

    def _apply_startup_geometry(self):
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            self.resize(1280, 820)
            return
        avail = screen.availableGeometry()
        margin = 60
        w = max(self.minimumWidth(), min(1280, avail.width() - margin))
        h = max(self.minimumHeight(), min(820, avail.height() - margin))
        self.resize(w, h)
        x = avail.x() + (avail.width() - w) // 2
        y = avail.y() + (avail.height() - h) // 2
        self.move(x, y)

    def _poll_design_transfer(self):
        """دریافت طرح کامل طراح، اعمال در مدل مرکزی و رفتن به فرم مأموریت."""
        transfer = read_design_transfer()
        if not transfer:
            return
        transfer_id, payload = transfer
        if transfer_id == self._last_design_transfer_id:
            return
        if not data_manager.import_design_payload(payload, transfer_id=transfer_id):
            # فایل خراب را حذف نمی‌کنیم تا کاربر فرصت اصلاح/ارسال دوباره داشته
            # باشد؛ در poll بعدی همان شناسه دوباره بررسی می‌شود.
            return
        self._last_design_transfer_id = transfer_id
        remove_design_transfer()
        self._set_current_index(2)
        self.raise_()
        self.activateWindow()
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Information)
        box.setWindowTitle("انتقال طرح راکت")
        box.setText(
            "✅ طرح با موفقیت از نرم‌افزار طراحی دریافت شد.\n\n"
            "هندسهٔ بدنه و باله، جرم‌ها، نقاط CG/CP و مشخصات نازل در "
            "اطلاعات مأموریت و پیش‌بینی عملکرد اعمال شد.")
        box.setStandardButtons(QMessageBox.Ok)
        self._design_import_box = box
        box.finished.connect(lambda _code: setattr(self, "_design_import_box", None))
        box.show()

    def _on_connection_changed(self, connected: bool):
        self.top_bar.set_connection(connected, data_manager.connection_type)

    def _tick_clock(self):
        now = datetime.datetime.now()
        self.top_bar.set_time(now.strftime("%H:%M:%S"))
        self.top_bar.set_date(gregorian_date_to_jalali_str(now.date()))

    def _on_telemetry_for_topbar(self, packet: dict):
        if "battery" in packet:
            self.top_bar.set_battery(packet["battery"])

    def _on_telemetry_saved(self, _path: str):
        """پس از ذخیرهٔ خودکار داده‌های تله‌متری، یک پیام سراسری روی کل برنامه
        نمایش داده می‌شود (بدون نیاز به نام یا محل فایل)."""
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Information)
        box.setWindowTitle("ذخیرهٔ داده‌ها")
        box.setText("✅ داده‌ها ذخیره شد.")
        box.setStandardButtons(QMessageBox.Ok)
        box.exec()

    def _on_demo_mode_changed(self, active: bool):
        self.top_bar.set_demo_mode(active)
        self._update_window_title()

    def _update_window_title(self):
        self.setWindowTitle(
            f"{APP_NAME}  —  نسخه {APP_VERSION}" + ("  —  حالت آموزشی" if data_manager.demo_mode else "")
        )

    def _on_nav_clicked(self, index: int):
        self._set_current_index(index)

    def _on_navigate_requested(self, page_name: str):
        page_name = NAV_ALIASES.get(page_name, page_name)
        for i, (name, _) in enumerate(NAV_ITEMS):
            if name == page_name:
                self._set_current_index(i)
                return
        # نام یکی از تب‌های تحلیل (جدید یا قدیمی)؟ → صفحهٔ «تحلیل پرواز» + تب درست
        for page in self._pages:
            if isinstance(page, AnalysisHubPage) and page.open_tab(page_name):
                self._set_current_index(self._pages.index(page))
                return

    def _go_prev(self):
        idx = self.stack.currentIndex()
        if idx > 0:
            self._set_current_index(idx - 1)

    def _go_next(self):
        idx = self.stack.currentIndex()
        if idx < len(NAV_ITEMS) - 1:
            self._set_current_index(idx + 1)

    def _set_current_index(self, index: int):
        self.stack.setCurrentIndex(index)
        self.nav_group.button(index).setChecked(True)
        name, _ = NAV_ITEMS[index]
        self.nav_bar.set_indicator(index + 1, len(NAV_ITEMS), name)
