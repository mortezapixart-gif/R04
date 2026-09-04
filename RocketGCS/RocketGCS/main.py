# -*- coding: utf-8 -*-
"""
main.py
---------
نقطه ورود نرم‌افزار مدیریت، دریافت و تحلیل اطلاعات کامپیوتر پرواز راکت.

اجرا:
    pip install -r requirements.txt
    python main.py
"""
import os
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase, QIcon, QFont
from PySide6.QtCore import Qt

from ui.main_window import MainWindow
from ui.splash_screen import SplashScreen
from ui.custom_tooltip import install as install_custom_tooltips
from ui.style import APP_QSS, APP_FONT_FAMILY


from core.paths import asset_path

# همهٔ وزن‌های فونت شبنم که باید همراه با برنامه بارگذاری شوند (بدون نیاز
# به نصب روی سیستم کاربر). Shabnam.ttf و Shabnam-Bold.ttf هر دو زیر
# خانوادهٔ "Shabnam" ثبت می‌شوند (bold با font-weight انتخاب می‌شود)؛
# Light/Medium/Thin خانواده‌های جدا (Shabnam Light و ...) هستند.
_SHABNAM_FILES = [
    "Shabnam.ttf",
    "Shabnam-Bold.ttf",
    "Shabnam-Light.ttf",
    "Shabnam-Medium.ttf",
    "Shabnam-Thin.ttf",
]


def load_fonts():
    """بارگذاری فونت شبنم (همهٔ وزن‌ها) همراه با برنامه، بدون نیاز به نصب روی سیستم."""
    loaded_any = False
    for filename in _SHABNAM_FILES:
        font_path = asset_path(filename)
        if os.path.exists(font_path):
            if QFontDatabase.addApplicationFont(font_path) != -1:
                loaded_any = True
    return loaded_any


def main():
    app = QApplication(sys.argv)
    icon_path = asset_path("rocketgcs.ico")
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    # سبک پایهٔ Fusion به‌جای استایل بومی ویندوز -- چون استایل بومی ویندوز
    # خیلی از خاصیت‌های QSS سفارشی ما (مثل text-align روی دکمه‌ها، geometry
    # دقیق دکمه‌های +/- در ورودی‌های عددی) رو نادیده می‌گیره یا ناقص اجرا
    # می‌کنه. Fusion یه استایل مستقل از پلتفرمه که کاملاً طبق QSS رفتار می‌کنه.
    app.setStyle("Fusion")
    app.setLayoutDirection(Qt.RightToLeft)
    shabnam_loaded = load_fonts()
    # فونت پیش‌فرض کل اپلیکیشن را هم صریحاً روی شبنم تنظیم می‌کنیم؛ چون QSS
    # فقط روی ویجت‌هایی اعمال می‌شه که selector مناسب داشته باشن (دیالوگ‌های
    # سیستمی، Tooltip، منوها و...) و setFont در سطح QApplication همه‌جا رو
    # پوشش می‌ده، حتی جاهایی که کد صریحاً QFont("B Yekan", ...) ست کرده.
    if shabnam_loaded:
        app.setFont(QFont(APP_FONT_FAMILY, 10))
    app.setStyleSheet(APP_QSS)

    # ---- باکس توضیح (tooltip) اختصاصی ----
    # مسیر استایل‌دادن به پنجرهٔ خصوصی QTipLabel ذاتاً ناپایدار بود (Qt در هر
    # نمایش استایلش را پاک می‌کند → گاهی سیاه/گاهی خاکستری). راه قطعی:
    # سیستم tooltip خودمان -- رویداد ToolTip مصرف و لیبلِ تحت‌کنترل برنامه
    # نشان داده می‌شود؛ یک پیاده‌گیری، یک رنگ، همه‌جا و همیشه.
    install_custom_tooltips(app)

    def show_main_window():
        window = MainWindow()
        window.show()
        show_main_window.window_ref = window   # جلوگیری از garbage-collect شدن پنجره

    splash = SplashScreen()
    splash.finished.connect(show_main_window)
    splash.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
