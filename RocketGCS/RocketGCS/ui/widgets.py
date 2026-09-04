# -*- coding: utf-8 -*-
"""
ui/widgets.py
--------------
ویجت‌های کمکی مشترک بین صفحات.

قانون چیدمان کل برنامه (طبق تصمیم نهایی کاربر):
    - همه‌جا وسط‌چین (StatCard، SensorStatusCard، عنوان‌ها و ...)
    - فقط دو صفحهٔ «اطلاعات مأموریت» و «اطلاعات نازل» که از two_column_form
      استفاده می‌کنن، راست‌چین می‌مونن
    - فقط منوی کناری (سایدبار) هم همیشه راست‌چین می‌مونه (کلاس SidebarNavButton
      در ui/main_window.py و استایل‌های اختصاصی #SidebarTitle /
      QPushButton#NavButton QLabel در ui/style.py این‌ها رو مدیریت می‌کنن)
"""
from PySide6.QtWidgets import (QFrame, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
                                QWidget, QPushButton, QAbstractSpinBox, QLineEdit, QComboBox)
from PySide6.QtCore import Qt, Signal

from core.report_text import protect_latin_quantities

# رنگ‌ها بر اساس نوع وضعیت
STATUS_CLASS = {"ok": "StatusOk", "warn": "StatusWarn", "pending": "StatusWarn",
                 "error": "StatusError", "info": "StatusInfo", "missing": "StatusMissing"}
STATUS_DOT = {"ok": "🟢", "warn": "🟡", "pending": "🟡", "error": "🔴",
              "info": "🔵", "missing": "⚪", None: "⚪"}


class InfoIcon(QLabel):
    """آیکون کوچک ⓘ با تولتیپ توضیحی -- برای اصطلاحات علمی/تخصصی، تا کاربر
    مبتدی (مثلاً دانش‌آموز) بدون نیاز به جست‌وجوی بیرونی، همان‌جا توضیح را
    ببیند."""
    def __init__(self, tooltip_text: str, parent=None):
        super().__init__("ⓘ", parent)
        self.setObjectName("InfoIcon")
        self.setToolTip(tooltip_text)
        self.setCursor(Qt.WhatsThisCursor)


class WarningIcon(QLabel):
    """آیکون کوچک قرمز ⚠ با تولتیپ توضیحی -- برای پارامترهایی که فعلاً کار
    نمی‌کنند (مثلاً چون ماژول سخت‌افزاری‌شان نصب نشده)، تا کاربر با دیدن یک
    عدد «--» گیج نشود و علتِ دقیقش را با نگه‌داشتن موس روی آیکون ببیند."""
    def __init__(self, tooltip_text: str, parent=None):
        super().__init__("⚠", parent)
        self.setObjectName("WarningIcon")
        self.setToolTip(tooltip_text)
        self.setCursor(Qt.WhatsThisCursor)


class StatCard(QFrame):
    """کارت نمایش یک مقدار یا وضعیت به همراه عنوان و واحد اختیاری (وسط‌چین)."""
    def __init__(self, title: str, value: str = "--", status: str | None = None,
                 unit: str = "", icon: str = "", big: bool = False, tooltip: str | None = None, parent=None):
        super().__init__(parent)
        self.setProperty("class", "Card")
        self.setObjectName("BigCard" if big else "StatCard")
        self.setMinimumHeight(104 if big else 90)
        self._unit = unit
        self._icon = icon
        layout = QVBoxLayout(self)
        if big:
            layout.setContentsMargins(18, 14, 18, 16)
        else:
            layout.setContentsMargins(16, 12, 16, 14)
        layout.setSpacing(8 if big else 6)

        self.title_label = QLabel(protect_latin_quantities(self._with_icon(title)))
        self.title_label.setProperty("class", "CardTitleBig" if big else "CardTitle")
        self.title_label.setAlignment(Qt.AlignCenter)
        self.value_label = QLabel(self._with_unit(value))
        self._raw_value = value
        self.value_label.setProperty("class", "CardValueBig" if big else "CardValue")
        self.value_label.setAlignment(Qt.AlignCenter)

        # طبق درخواست کاربر: آیکون آبی حذف شد؛ توضیح با بردن موس روی کارت
        # (tooltip) نمایش داده می‌شود -- همه‌جا یکسان، بدون شلوغی تصویر.
        if tooltip:
            self.setToolTip(tooltip)
        layout.addWidget(self.title_label, alignment=Qt.AlignCenter)
        layout.addWidget(self.value_label, alignment=Qt.AlignCenter)
        self.setLayoutDirection(Qt.RightToLeft)

        self.extra_label = QLabel("")
        self.extra_label.setProperty("class", "CardExtra")
        self.extra_label.setStyleSheet("background: transparent; color: #dbe4f0; font-size: 13px;")
        self.extra_label.setWordWrap(True)
        self.extra_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.extra_label, alignment=Qt.AlignCenter)
        self.extra_label.hide()

        if status:
            self.set_status(status)

    def _with_icon(self, title: str) -> str:
        return f"{self._icon}  {title}" if self._icon else title

    def _with_unit(self, value: str) -> str:
        if self._unit and value not in ("--", ""):
            out = f"{value} {self._unit}"
        else:
            out = value
        return protect_latin_quantities(out)

    def set_unit(self, unit: str):
        self._unit = unit
        if hasattr(self, "_raw_value"):
            self.value_label.setText(self._with_unit(self._raw_value))

    def set_value(self, value: str):
        self._raw_value = value
        self.value_label.setText(self._with_unit(value))

    def set_extra(self, text: str):
        self.extra_label.setText(protect_latin_quantities(text) if text else text)
        self.extra_label.setVisible(bool(text))

    def set_status(self, status: str | None):
        cls = STATUS_CLASS.get(status, "")
        default_cls = "CardValueBig" if self.objectName() == "BigCard" else "CardValue"
        self.value_label.setProperty("class", cls or default_cls)
        self.value_label.style().unpolish(self.value_label)
        self.value_label.style().polish(self.value_label)


class CompactStatCard(QFrame):
    """نسخهٔ فشردهٔ StatCard: عنوان و مقدار در یک خط افقی کنار هم (به‌جای دو
    خط جدا) -- برای صفحاتی با تعداد زیاد پارامتر (ارتفاع/سرعت، تحلیل چتر)
    که فضای بیشتری برای نمودارها لازم دارند."""
    def __init__(self, title: str, value: str = "--", unit: str = "", tooltip: str | None = None, parent=None):
        super().__init__(parent)
        self.setProperty("class", "Card")
        self.setObjectName("CompactStatCard")
        self._collapsed_height = 52
        self._expanded_height = 72
        self.setMinimumHeight(48)
        self.setMaximumHeight(self._collapsed_height)
        self._unit = unit
        self.setLayoutDirection(Qt.RightToLeft)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 4, 12, 4)
        outer.setSpacing(2)

        row = QHBoxLayout()
        row.setSpacing(8)

        self.value_label = QLabel(self._with_unit(value))
        self._raw_value = value
        self.value_label.setProperty("class", "CardValueCompact")
        self.title_label = QLabel(protect_latin_quantities(title))
        self.title_label.setProperty("class", "CardTitleCompact")

        row.addStretch()
        if tooltip:
            self.setToolTip(tooltip)   # توضیح با hover (به‌جای آیکون آبی)
        row.addWidget(self.title_label)
        row.addWidget(self.value_label)
        row.addStretch()
        outer.addLayout(row)

        # خط توضیح اضافه (مثلاً مقایسه با استاندارد ISA) -- به‌طور پیش‌فرض
        # مخفی است و فقط با فراخوانی set_extra نمایش داده می‌شود.
        self.extra_label = QLabel("")
        self.extra_label.setProperty("class", "CardExtraCompact")
        self.extra_label.setAlignment(Qt.AlignCenter)
        self.extra_label.setWordWrap(True)
        outer.addWidget(self.extra_label)
        self.extra_label.hide()

    def _with_unit(self, value: str) -> str:
        if self._unit and value not in ("--", ""):
            out = f"{value} {self._unit}"
        else:
            out = value
        return protect_latin_quantities(out)

    def set_unit(self, unit: str):
        self._unit = unit
        self.value_label.setText(self._with_unit(self._raw_value))

    def set_value(self, value: str):
        self._raw_value = value
        self.value_label.setText(self._with_unit(value))

    def set_extra(self, text: str):
        """نمایش یک خط توضیح کوچک زیر عنوان/مقدار (مثلاً مقایسه با مقدار مرجع)."""
        self.extra_label.setText(protect_latin_quantities(text) if text else (text or ""))
        has_text = bool(text)
        self.extra_label.setVisible(has_text)
        self.setMaximumHeight(self._expanded_height if has_text else self._collapsed_height)

    def set_status(self, status: str | None):
        cls = STATUS_CLASS.get(status, "") or "CardValueCompact"
        self.value_label.setProperty("class", cls)
        self.value_label.style().unpolish(self.value_label)
        self.value_label.style().polish(self.value_label)


class SensorStatusCard(QFrame):
    """کارت وضعیت یک سنسور با آیکون و نقطهٔ رنگی وضعیت (🟢/🟡/🔴/⚪) -- وسط‌چین."""
    def __init__(self, title: str, icon: str = "", parent=None):
        super().__init__(parent)
        self.setProperty("class", "Card")
        self.setObjectName("StatCard")
        self.setMinimumHeight(72)
        self._icon = icon
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)
        self.setLayoutDirection(Qt.RightToLeft)

        self.title_label = QLabel(f"{icon}  {title}" if icon else title)
        self.title_label.setProperty("class", "CardTitle")
        self.title_label.setAlignment(Qt.AlignCenter)
        # وسط‌چین واقعیِ گروه «نقطهٔ رنگی + متن وضعیت»: کشسانی هم قبل هم بعد
        row = QHBoxLayout()
        row.setSpacing(6)
        self.dot_label = QLabel(STATUS_DOT[None])
        self.value_label = QLabel("نامشخص")
        self.value_label.setProperty("class", "CardValue")
        row.addStretch()
        row.addWidget(self.value_label, alignment=Qt.AlignVCenter)
        row.addWidget(self.dot_label, alignment=Qt.AlignVCenter)
        row.addStretch()

        layout.addWidget(self.title_label, alignment=Qt.AlignCenter)
        layout.addLayout(row)

        self.extra_label = QLabel("")
        self.extra_label.setProperty("class", "CardExtra")
        self.extra_label.setStyleSheet("background: transparent; color: #dbe4f0; font-size: 13px;")
        self.extra_label.setWordWrap(True)
        self.extra_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.extra_label, alignment=Qt.AlignCenter)
        self.extra_label.hide()

    def set_status(self, status: str | None, text: str):
        self.dot_label.setText(STATUS_DOT.get(status, STATUS_DOT[None]))
        # واحد انگلیسی (hPa، g، °C…) همیشه سمت راستِ عدد بماند
        self.value_label.setText(protect_latin_quantities(text) if text else text)
        cls = STATUS_CLASS.get(status, "CardValue")
        self.value_label.setProperty("class", cls)
        self.value_label.style().unpolish(self.value_label)
        self.value_label.style().polish(self.value_label)

    def set_extra(self, text: str):
        self.extra_label.setText(protect_latin_quantities(text) if text else text)
        self.extra_label.setVisible(bool(text))

    def set_title(self, title: str):
        self.title_label.setText(f"{self._icon}  {title}" if self._icon else title)


class TopStatusBar(QWidget):
    """نوار وضعیت بالای صفحه"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TopBar")
        self.setLayoutDirection(Qt.RightToLeft)
        self.setFixedHeight(44)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 0, 16, 0)
        lay.setSpacing(22)

        def make_item(icon_text: str):
            lbl = QLabel(icon_text)
            lbl.setObjectName("TopBarItem")
            return lbl

        self.lbl_app_version = make_item("📦 نسخه برنامه: --")
        self.lbl_conn = make_item("🔌 کامپیوتر پرواز: قطع")
        self.lbl_battery = make_item("🔋 باتری: -- ولت")
        self.lbl_time = make_item("🕒 --:--:--")
        self.lbl_date = make_item("📅 --")

        # نشانگر همیشگی «حالت آموزشی» -- طبق درخواست کاربر با رنگ متفاوت،
        # در همهٔ صفحات (چون این ویجت سراسری است) تا کاربر هیچ‌وقت فراموش
        # نکند دارد با پرتاب فرضی کار می‌کند، نه سخت‌افزار واقعی
        self.lbl_demo_mode = make_item("🎓 حالت آموزشی")
        self.lbl_demo_mode.setObjectName("TopBarDemoMode")
        self.lbl_demo_mode.hide()

        for w in (self.lbl_demo_mode, self.lbl_app_version, self.lbl_conn,
                  self.lbl_battery, self.lbl_date, self.lbl_time):
            lay.addWidget(w)
        lay.addStretch()

    def set_app_version(self, version: str):
        self.lbl_app_version.setText(f"📦 نسخه برنامه: {version}")

    def set_connection(self, connected: bool, conn_type: str = ""):
        if not connected:
            text = "قطع"
        elif conn_type.upper() == "LORA":
            text = "متصل با لورا"
        elif conn_type.upper() == "USB":
            text = "متصل با USB"
        elif conn_type.upper() == "DEMO":
            text = "متصل با پورت فرضی"
        else:
            text = "متصل"
        self.lbl_conn.setObjectName("TopBarItemOk" if connected else "TopBarItemError")
        self.lbl_conn.setText(f"🔌 کامپیوتر پرواز: {text}")
        self.lbl_conn.style().unpolish(self.lbl_conn)
        self.lbl_conn.style().polish(self.lbl_conn)

    def set_battery(self, voltage: float | None):
        self.lbl_battery.setText(f"🔋 باتری: {voltage:.2f} ولت" if voltage else "🔋 باتری: -- ولت")

    def set_time(self, text: str):
        self.lbl_time.setText(f"🕒 {text}")

    def set_date(self, jalali_text: str):
        self.lbl_date.setText(f"📅 {jalali_text}")

    def set_demo_mode(self, active: bool):
        self.lbl_demo_mode.setVisible(active)


def page_title(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("PageTitle")
    lbl.setAlignment(Qt.AlignCenter)
    return lbl


def form_grid(rows: list, field_width: int = 150) -> QWidget:
    """فرم راست‌چین با دو پارامتر در هر ردیف (برای صفحاتی مثل «اطلاعات
    مأموریت و نازل» -- تا فضای خالی کنار فیلدها از بین برود و صفحه بدون
    نیاز به اسکرول جا شود).

    rows: لیستی از ردیف‌ها؛ هر ردیف خودش لیستی از یک یا دو تاپل
    (عنوان, فیلد[, تولتیپ]) است. اولین تاپل هر ردیف سمت راست‌تر قرار
    می‌گیرد. همهٔ فیلدها عرض ثابت و یکسان دارند (field_width) تا ردیف‌ها
    مرتب و هم‌اندازه به‌نظر برسند."""
    w = QWidget()
    w.setLayoutDirection(Qt.RightToLeft)
    # بدون این، قانون سراسری QWidget {background:#12161c} یک مستطیل
    # نزدیک‌به‌سیاه پشت همهٔ فیلدها می‌کشد -- داخل کارت باید شفاف باشد.
    # قاعدهٔ QToolTip هم همین‌جا تکرار می‌شود: ویجتِ دارای استایلِ خودش،
    # محدودهٔ استایل جدا می‌سازد و tooltip فرزندانش از قاعدهٔ سراسری جا
    # می‌ماند و سیاه می‌شود (کمربند دوم در کنار فیلتر رویداد main.py).
    from ui.style import TOOLTIP_QSS
    w.setStyleSheet("background:transparent;" + TOOLTIP_QSS)
    grid = QGridLayout(w)
    grid.setHorizontalSpacing(8)
    grid.setVerticalSpacing(12)
    grid.setContentsMargins(6, 8, 6, 8)
    grid.setColumnStretch(4, 1)  # فضای خالیِ باقی‌مانده (اگر بود) اینجا جمع می‌شود

    for row, row_items in enumerate(rows):
        for i, item in enumerate(row_items):
            label_text, field = item[0], item[1]
            tooltip = item[2] if len(item) > 2 else None
            base_col = i * 2  # جفت اول: ستون ۰-۱ (راست‌ترین) -- جفت دوم: ستون ۲-۳

            label = QLabel(protect_latin_quantities(label_text))
            label.setProperty("class", "CardTitle")
            label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            grid.addWidget(label, row, base_col, alignment=Qt.AlignRight | Qt.AlignVCenter)

            if isinstance(field, QLineEdit):
                field.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                field.setFixedWidth(field_width)
            elif isinstance(field, QAbstractSpinBox):
                field.setLayoutDirection(Qt.LeftToRight)
                field.lineEdit().setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                field.setFixedWidth(field_width)
            elif isinstance(field, QComboBox):
                # کشویی هم‌اندازهٔ بقیهٔ فیلدهای فرم + پاپ‌آپ تیرهٔ #303844
                # (بدون این، فهرستِ بازشونده روی ویندوز سفید و ناخواناست؛
                # darken_combo_popup علاوه بر آیتم‌ها، نوار سفیدِ بالا و
                # پایین پاپ‌آپ -- زمینهٔ ظرف -- را هم می‌پوشاند)
                field.setFixedWidth(field_width)
                # editable+read-only تنها راه مطمئن وسط‌چین کردن متنِ فیلدِ بسته
                # در Fusion/ویندوز است؛ بدون آن QComboBox متن را چپ‌چین می‌کشد.
                field.setEditable(True)
                field.setInsertPolicy(QComboBox.NoInsert)
                le = field.lineEdit()
                le.setReadOnly(True)
                le.setAlignment(Qt.AlignCenter)
                le.setFocusPolicy(Qt.NoFocus)
                le.setCursor(Qt.PointingHandCursor)
                def _open_popup(_event, combo=field):
                    combo.showPopup()
                le.mousePressEvent = _open_popup
                from ui.style import darken_combo_popup
                darken_combo_popup(field)

            if tooltip:
                # توضیح پارامتر فقط با بردن موس روی «عنوان» پارامتر (قانون کلی)
                label.setToolTip(protect_latin_quantities(tooltip))
            grid.addWidget(field, row, base_col + 1, alignment=Qt.AlignRight | Qt.AlignVCenter)
    return w


def section_title(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setObjectName("SectionTitle")
    lbl.setAlignment(Qt.AlignCenter)
    return lbl


def make_card(child: QWidget) -> QFrame:
    frame = QFrame()
    frame.setProperty("class", "Card")
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(16, 16, 16, 16)
    lay.addWidget(child)
    return frame


class PageNavBar(QWidget):
    """نوار پایین صفحه با فلش چپ/راست"""
    prev_requested = Signal()
    next_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setLayoutDirection(Qt.RightToLeft)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 8, 0, 0)

        self.prev_btn = QPushButton("\u2190 صفحه قبل")   # ←
        self.next_btn = QPushButton("صفحه بعد \u2192")   # →
        self.prev_btn.setObjectName("NavArrowButton")
        self.next_btn.setObjectName("NavArrowButton")
        self.prev_btn.setCursor(Qt.PointingHandCursor)
        self.next_btn.setCursor(Qt.PointingHandCursor)

        self.page_label = QLabel("")
        self.page_label.setAlignment(Qt.AlignCenter)
        self.page_label.setObjectName("PageIndicator")

        lay.addWidget(self.prev_btn)
        lay.addStretch()
        lay.addWidget(self.page_label)
        lay.addStretch()
        lay.addWidget(self.next_btn)

        self.prev_btn.clicked.connect(self.prev_requested)
        self.next_btn.clicked.connect(self.next_requested)

    def set_indicator(self, current: int, total: int, name: str):
        self.page_label.setText(f"{name}   ({current} / {total})")
        self.prev_btn.setEnabled(current > 1)
        self.next_btn.setEnabled(current < total)
