# -*- coding: utf-8 -*-
"""صفحهٔ انتخاب سنسور

این بخش قبلاً داخل صفحهٔ پایش پرتاب بود و باعث شلوغی و ناخوانا شدن صفحه شده بود؛
طبق بازخورد کاربر به یک صفحهٔ مستقل (قبل از «گزارش نهایی») منتقل شد.
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QGridLayout, QComboBox, QLabel
from PySide6.QtCore import Qt
from ui.widgets import page_title, make_card
from core.data_manager import data_manager

SENSOR_CATEGORY_LABEL = {
    "BMP280": "سنسور فشار/دما",
    "MPU6050": "شتاب‌سنج/ژیروسکوپ",
    "AHT21": "دما و رطوبت",
    "UV": "شدت اشعه UV",
    "CAMERA": "دوربین",
    "SD": "کارت حافظه",
    "GPS": "ماژول GPS",
}

SENSOR_ICON = {
    "BMP280": "🌡", "MPU6050": "🧭", "AHT21": "💧", "UV": "☀️",
    "CAMERA": "📷", "SD": "💾", "GPS": "📡",
}

# دو ماژول اول الزامی‌اند: تشخیص اوج (بارومتر) و لحظهٔ پرتاب/پایان رانش و
# باز شدن چتر (شتاب‌سنج) بدون آن‌ها ممکن نیست -- مدلِ دقیق مهم نیست.
MANDATORY_MODULES = ("BMP280", "MPU6050")

# اسامی شناخته‌شدهٔ ماژول‌های رایج -- قابل انتخاب توسط کاربر.
# هر لیست با «نصب نشده» شروع می‌شود (پیش‌فرض هیچ ماژولی انتخاب نیست)؛ گزینهٔ
# «انتخاب نشده» حذف شد (دو نام هم‌معنی، فضا اشغال می‌کرد). مقدار ذخیره‌شدهٔ
# قدیمی «انتخاب نشده» در load به «نصب نشده» ترجمه می‌شود.
NOT_INSTALLED = "نصب نشده"
LEGACY_UNSELECTED = "انتخاب نشده"
KNOWN_MODULES = {
    "BMP280": [NOT_INSTALLED, "BMP280", "BME280", "BMP388", "MS5611"],
    "MPU6050": [NOT_INSTALLED, "MPU6050", "MPU9250", "ICM-20948", "BNO055", "BNO085"],
    "AHT21": [NOT_INSTALLED, "AHT21B", "AHT20", "AHT10", "SHT31", "DHT22"],
    "UV": [NOT_INSTALLED, "GUVA-S12SD", "ML8511", "VEML6075", "SI1145"],
    "CAMERA": [NOT_INSTALLED, "OV7670", "OV2640", "OV5640"],
    "SD": [NOT_INSTALLED, "microSD (SPI)", "microSD (SDIO)"],
    "GPS": [NOT_INSTALLED, "NEO-6M", "NEO-M8N", "NEO-M9N"],
}


class SensorModulesPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setLayoutDirection(Qt.RightToLeft)
        root = QVBoxLayout(self)
        root.addWidget(page_title("انتخاب سنسور"))

        desc = QLabel("مدل ماژول‌هایی که می‌خواهید روی راکت نصب باشند را انتخاب کنید (مدلِ دقیق مهم "
                       "نیست -- هر مدلی همان اطلاعات آموزشی را می‌سازد).\n"
                       "سنسور فشار و شتاب‌سنج برای تشخیص اوج و باز شدن چتر الزامی‌اند. "
                       "بقیه اختیاری‌اند: هر ماژولی انتخاب نشود، در تست سلامت، مرکز کنترل پرواز، "
                       "رادار، دادهٔ خام و گزارش هم نمی‌آید.")
        desc.setWordWrap(True); desc.setAlignment(Qt.AlignCenter)
        root.addWidget(desc)

        # چیدمان شبکه‌ای (۴ ستون در هر ردیف) چون تعداد ماژول‌ها زیاد شده و
        # یک ردیف افقی باعث فشردگی/بریدگی می‌شد.
        module_grid = QGridLayout()
        module_grid.setSpacing(20)
        self.combos = {}
        COLS = 4
        for i, key in enumerate(SENSOR_CATEGORY_LABEL):
            box = QVBoxLayout()
            suffix = " (الزامی ⭐)" if key in MANDATORY_MODULES else ""
            lbl = QLabel(f"{SENSOR_ICON[key]} {SENSOR_CATEGORY_LABEL[key]}{suffix}")
            lbl.setProperty("class", "CardTitleBig")
            lbl.setAlignment(Qt.AlignCenter)
            combo = QComboBox()
            combo.addItems(KNOWN_MODULES[key])
            current = data_manager.sensor_models.get(key, KNOWN_MODULES[key][0])
            if current == LEGACY_UNSELECTED:   # دادهٔ ذخیره‌شدهٔ قدیمی
                current = NOT_INSTALLED
            if current in KNOWN_MODULES[key]:
                combo.setCurrentText(current)
            combo.currentTextChanged.connect(lambda text, k=key: self._on_changed(k, text))
            # پاپ‌آپ کاملاً تیره (#303844): آیتم‌ها + viewport + «ظرف» والد --
            # بدون ظرف، نوار سیاهِ بالا و پایین فهرستِ بازشونده دیده می‌شود
            from ui.style import darken_combo_popup
            darken_combo_popup(combo)
            box.addWidget(lbl); box.addWidget(combo)
            module_grid.addLayout(box, i // COLS, i % COLS)
            self.combos[key] = combo
        for col in range(COLS):
            module_grid.setColumnStretch(col, 1)

        root.addWidget(make_card(self._wrap(module_grid)))
        root.addStretch()

        data_manager.sensor_model_changed.connect(self._on_external_change)

    def _wrap(self, layout):
        # شفاف -- والگراند داخلی کارت نباید زمینهٔ جدا بکشد (قانون کلی برنامه؛
        # بدون این، قانون سراسری QWidget{background:#12161c} داخل کارت
        # مستطیل تیره می‌انداخت)
        w = QWidget(); w.setObjectName("TransparentContainer")
        w.setLayout(layout); return w

    def _on_changed(self, key: str, model_name: str):
        data_manager.sensor_models[key] = model_name
        data_manager.sensor_model_changed.emit(key, model_name)

    def _on_external_change(self, key: str, model_name: str):
        """هماهنگ‌نگه‌داشتن این صفحه با تغییراتی که جای دیگری از برنامه اعمال
        می‌شوند (مثلاً بارگذاری از فایل ذخیرهٔ مأموریت)."""
        combo = self.combos.get(key)
        if combo is None or combo.currentText() == model_name:
            return
        combo.blockSignals(True)
        combo.setCurrentText(model_name)
        combo.blockSignals(False)
