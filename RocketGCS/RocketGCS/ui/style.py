# -*- coding: utf-8 -*-
"""
ui/style.py
------------
پوستهٔ بصری (Theme) مدرن مهندسی، تیره، مناسب برای نرم‌افزارهای تحلیل داده.
"""
import os
import tempfile
import base64

# خانوادهٔ فونت اصلی کل برنامه -- هم در QSS (پایین همین فایل) و هم در
# جاهایی که صریحاً QFont(...) ساخته می‌شود (مثل صفحهٔ ری‌پلی سه‌بعدی) از
# همین ثابت استفاده کنید تا تغییر فونت در کل برنامه یکدست بماند.
APP_FONT_FAMILY = "Shabnam"


def _create_temp_arrow_icons():
    """ایجاد آیکون‌های PNG فلش برای ورودی‌های عددی در پوشهٔ موقت سیستم."""
    temp_dir = tempfile.gettempdir()
    up_path = os.path.join(temp_dir, "spin_up_teal_v2.png").replace("\\", "/")
    down_path = os.path.join(temp_dir, "spin_down_teal_v2.png").replace("\\", "/")
    # مثلث فیروزه‌ای رو به بالا (▲) -- ضدلک‌لک، ۱۶×۱۰ پیکسل
    up_b64 = (
        "iVBORw0KGgoAAAANSUhEUgAAABAAAAAKCAYAAAC9vt6cAAABgklEQVR4nHVRwUobURQ99743MzqgiYJm7w+01YVdaIOLiJspdPH8BD9DZ9E/yW6yTBVEJDQuFBoGVER3LXTTTaFJauO8zHu3C2lBE8/ycDj3nnOAaRAQRGiv1wt2Lo7mHzmhaVKeRtbRUSCSH3r0MYqrhwBgXtBOwEimACDJzxofbr+I+X4j7/PuAQDUpaOf65++JQcMpJJcXywrpksiWvauLHU0E9j7P9vt1c0TI5lq0a6bGsEgJTALi2/qeLbm7NjDQ3nnRIVBM7k6r7Vg/OOhZwZ16egWkUvybhpWK43xYFgSkwKBXWG9jmdrLL4JZjFI6YmByTL1mbbKJD9rBHG8X/QHDiD1PyeTGg+GZVitNJK8m7aI3L8+CCIMIr+Td5dmwvASzDVvrdBE6yRQ5FQYKfv7fvvT2rtTI6LIZJkaraxEKrTH0UJ1w/7qg7QGIJN9ew+OQriHou9KvGm/Wv9GAGB6vUo5hw1XjAomYpQvbKwBPxYfLC0G9ufwrv367de/vSmjkBESt7MAAAAASUVORK5CYII="
    )
    # مثلث فیروزه‌ای رو به پایین (▼) -- ضدلک‌لک، ۱۶×۱۰ پیکسل
    down_b64 = (
        "iVBORw0KGgoAAAANSUhEUgAAABAAAAAKCAYAAAC9vt6cAAABiUlEQVR4nI1RQWsTYRB975vdbS7Z0krxX0htLwohpQdLL6142GPw5m/w1ogn/8ruSVJEKKW0AREMqQqiNw+egogJqQn5dr8ZDyGllhZ8MJfhvTfzZggAWa+3XNXRCLPpzJEOFW5GBGhpGq+txv7X+Ftn/cH3KMtzmQKlzPzz2sqdhh+OwFoEwK6pCagiThOE0XgE4D7MSJg5kLrbP1urJcknOHdXvTcC7pqBQRgkWRJ/8WfncLN5nJmJA6lZnsvbjebP4MunToRwbj6R5GXBNEnTuJxMXh5uNo+37CQqyMCF/5adRKfcrvbOu+3a6sqB/z2sQEYAYGohWa5LOb44er3e2MlUpSADcGXNU25XmZl0NpptPxwdxWk9MrUAg8pS4qrJdKB0LaiyQPvyQP/kLNA2qFLpWtVkOpAkdnAIToTBl63OvYeDDIUDX+gtfwIyywUA9vrdR0++frDsxxfb758dLGLeKryKBXH/Y/fV48/vunNjk/8SAwAMhBmf9Xrx7vs36bxnvIn6F5XFry2KfiAPAAAAAElFTkSuQmCC"
    )

    with open(up_path, "wb") as f:
        f.write(base64.b64decode(up_b64))
    with open(down_path, "wb") as f:
        f.write(base64.b64decode(down_b64))

    return up_path, down_path

_UP_PATH, _DOWN_PATH = _create_temp_arrow_icons()

# استایل باکس توضیح (tooltip) -- تنها منبع حقیقت؛ هم در QSS سراسری نشسته
# و هم فیلتر رویداد main.py خودِ پنجرهٔ tooltip را با آن می‌پوشاند تا در
# «همهٔ» برنامه (حتی ویجت‌های دارای استایل خطی) یکسان بماند.
TOOLTIP_QSS = """
QToolTip {
    background-color: #232b38;
    color: #e6ebf1;
    border: 1px solid #3d4a5c;
    padding: 6px 10px;
    font-size: 13px;
}
"""

# همان رنگ‌ها به‌صورت اعلان‌های لخت (بدون سلکتور) -- برای ست‌کردن مستقیم روی
# خودِ شیء پنجرهٔ tooltip. کلاس واقعی آن در Qt «QToolTipLabel» است (نه
# QToolTip که یک کلاس ایستای مدیریت‌گر است و ویجت نیست)؛ اعلان لخت مستقل از
# نام کلاس کار می‌کند.
TOOLTIP_LABEL_QSS = (
    "background-color: #232b38;"
    "color: #e6ebf1;"
    "border: 1px solid #3d4a5c;"
    "padding: 6px 10px;"
    "font-size: 13px;"
)

APP_QSS = f"""
* {{
    font-family: "Shabnam", "B Yekan", "Vazirmatn", "Tahoma", "Segoe UI";
    font-size: 14px;
}}

QMainWindow, QWidget {{
    background-color: #12161c;
    color: #e6ebf1;
}}

/* ردیف کمبو و wrapperهای داخلی نباید زمینهٔ مشکی جدا از باکس داشته باشند */
QWidget#CommunicationPortRow, QWidget#TransparentContainer {{
    background-color: transparent;
}}

#TopBar {{
    background-color: #171c24;
    border-bottom: 1px solid #262d38;
}}

QLabel {{
    background-color: transparent;
    qproperty-alignment: AlignCenter;
}}
QLineEdit, QDoubleSpinBox {{
    qproperty-alignment: AlignCenter;
}}

QLabel#TopBarItem {{
    color: #b8c2cf;
    font-size: 13px;
}}
QLabel#TopBarItemOk {{
    color: #35d07f;
    font-size: 13px;
    font-weight: bold;
}}
QLabel#TopBarItemError {{
    color: #ef5350;
    font-size: 13px;
    font-weight: bold;
}}

{TOOLTIP_QSS}

#Sidebar {{
    background-color: #171c24;
    border-left: 1px solid #262d38;
}}

#SidebarTitle {{
    color: #4fd1c5;
    font-size: 17px;
    font-weight: bold;
    padding: 18px 16px 12px 16px;
    qproperty-alignment: AlignCenter;
}}

/* سربرگ گروه «تحلیل‌ها» در سایدبار -- کمی بولد و بزرگ‌تر از دکمه‌ها */
QLabel#NavGroupHeader {{
    color: #dfe7f1;
    background: transparent;
    font-size: 13.5px;
    font-weight: bold;
    padding: 12px 16px 4px 16px;
}}

QPushButton#NavButton {{
    border: none;
    border-radius: 8px;
    background-color: transparent;
}}

QPushButton#NavButton QLabel {{
    color: #b8c2cf;
    font-size: 14px;
    background-color: transparent;
    qproperty-alignment: \'AlignRight | AlignVCenter\';
}}

QPushButton#NavButton:hover {{
    background-color: #202836;
}}

QPushButton#NavButton:hover QLabel {{
    color: #ffffff;
}}

QPushButton#NavButton:checked {{
    background-color: #24405c;
    border-right: 4px solid #4fd1c5;
}}

QPushButton#NavButton:checked QLabel {{
    color: #4fd1c5;
    font-weight: bold;
}}

/* دکمهٔ اجرای برنامهٔ خواهر «طراح راکت» (پروسهٔ جدا) */
QPushButton#DesignerButton {{
    border: 1px solid #7a5210;
    border-radius: 8px;
    background-color: #2b2313;
    margin-top: 8px;
}}
QPushButton#DesignerButton QLabel {{
    color: #ffb020;
    font-size: 14px;
    font-weight: bold;
    background-color: transparent;
    qproperty-alignment: \'AlignCenter\';
}}
QPushButton#DesignerButton:hover {{
    background-color: #3a2e18;
    border-color: #ff9f1c;
}}
QPushButton#DesignerButton:hover QLabel {{
    color: #ffffff;
}}

QLabel#SectionTitle {{
    color: #8fa3b8;
    font-size: 14px;
    font-weight: bold;
    padding: 10px 2px 4px 2px;
}}

QLabel#PageTitle {{
    font-size: 20px;
    font-weight: bold;
    color: #ffffff;
    padding: 6px 2px 14px 2px;
}}

QFrame.Card {{
    background-color: #1a2029;
    border: 1px solid #262d38;
    border-radius: 12px;
}}

QFrame#BigCard {{
    background-color: #1a2029;
    border: 1px solid #2f6fed;
    border-radius: 14px;
}}

QLabel.CardTitle {{
    color: #a3b6c9;
    background: transparent;
    font-size: 13px;
}}

QLabel.CardTitleBig {{
    color: #b3c6d9;
    background: transparent;
    font-size: 14px;
    font-weight: bold;
}}

QLabel.CardValue {{
    color: #ffffff;
    background: transparent;
    font-size: 22px;
    font-weight: bold;
}}

QLabel.CardValueBig {{
    color: #ffffff;
    background: transparent;
    font-size: 26px;
    font-weight: bold;
}}

QLabel.CardExtra {{
    color: #c3d2e3;
    background: transparent;
    font-size: 13px;
    font-weight: 500;
    padding-top: 4px;
}}

/* کارت فشردهٔ تک‌خطی (عنوان + مقدار کنار هم) -- صفحات ارتفاع/سرعت و تحلیل چتر */
QFrame#CompactStatCard {{
    background-color: #1a2029;
    border: 1px solid #262d38;
    border-radius: 10px;
}}
QLabel.CardTitleCompact {{
    color: #a3b6c9;
    background: transparent;
    font-size: 12px;
}}
QLabel.CardValueCompact {{
    color: #ffffff;
    background: transparent;
    font-size: 15px;
    font-weight: bold;
}}
QLabel.CardExtraCompact {{
    color: #8fa3b8;
    background: transparent;
    font-size: 11px;
}}

/* کارت جدول شاخص‌ها -- تب «شاخص‌های پرواز» (دو جدول گزارش PDF) */
QFrame#IndicesPanel {{
    background-color: #1a2029;
    border: 1px solid #262d38;
    border-radius: 10px;
}}
QLabel#IndicesHeader {{
    color: #dfe7f1;
    background: transparent;
    font-size: 13.5px;
    font-weight: bold;
    padding: 2px 2px 6px 2px;
    border-bottom: 1px solid #2b3446;
}}

/* ردیف‌های زبرای جدول شاخص‌ها -- زمینهٔ یک‌درمیان (مشابه گزارش PDF) */
QFrame#IndicesRow {{
    border: none;
    border-radius: 4px;
}}
QFrame#IndicesRow[odd="false"] {{
    background-color: #1a2029;
}}
QFrame#IndicesRow[odd="true"] {{
    background-color: #212a38;
}}

QLabel#TopBarDemoMode {{
    color: #c084fc;
    font-size: 13px;
    font-weight: bold;
    background-color: rgba(192, 132, 252, 0.14);
    border: 1px solid #c084fc;
    border-radius: 8px;
    padding: 3px 10px;
}}

QLabel.StatusOk    {{ color: #3fe08f; background: transparent; font-weight: bold; }}
QLabel.StatusWarn  {{ color: #f5cc5f; background: transparent; font-weight: bold; }}
QLabel.StatusError {{ color: #f2635f; background: transparent; font-weight: bold; }}
QLabel.StatusInfo  {{ color: #63b0f9; background: transparent; font-weight: bold; }}
QLabel.StatusMissing {{ color: #7488a0; background: transparent; font-weight: bold; }}

QLabel#InfoIcon {{
    color: #4fa3f7;
    background: transparent;
    font-size: 14px;
    font-weight: bold;
    padding: 0 4px;
}}

QLabel#WarningIcon {{
    color: #ef5350;
    background: transparent;
    font-size: 13px;
    font-weight: bold;
    padding: 0 4px;
}}

/* فیلدهای ورود و انتخاب -- روشن‌تر از پنل تا محدودهٔ قابل ویرایش واضح باشد */
QLineEdit, QTextEdit, QPlainTextEdit {{
    background-color: #303844;
    border: 1px solid #566273;
    border-radius: 8px;
    padding: 7px 10px;
    color: #f3f6fa;
    selection-background-color: #2f80ed;
    selection-color: #ffffff;
}}
QLineEdit:read-only {{
    background-color: #29313c;
    color: #cbd5e1;
}}

/* باکس‌های متنی گزارش نهایی (پیش‌نمایش + پیشنهادهای اصلاحی): بدون زمینه و
   قاب -- متن مستقیم روی کارت اصلی (قانون: هیچ کانتینری داخل کارت‌ها
   پس‌زمینه نکشد) */
QTextEdit#ReportPreview, QTextEdit#AdvisorBox, QTextEdit#CommunicationLog {{
    background-color: transparent;
    border: none;
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
    background-color: #36404e;
    border: 1px solid #62c8ff;
}}

QDoubleSpinBox {{
    background-color: #303844;
    border: 1px solid #566273;
    border-radius: 8px;
    padding: 6px 38px 6px 10px;
    color: #f3f6fa;
    min-height: 22px;
}}
QDoubleSpinBox:focus {{
    background-color: #36404e;
    border: 1px solid #62c8ff;
}}

QComboBox {{
    background-color: #303844;
    border: 1px solid #566273;
    border-radius: 8px;
    padding: 6px 10px 6px 38px;
    color: #f3f6fa;
    min-height: 22px;
}}
QComboBox:focus {{
    background-color: #36404e;
    border: 1px solid #62c8ff;
}}

/* فهرست بازشوندهٔ کشویی: همان تم تیرهٔ #303844 که در صفحهٔ ارتباط کار
   می‌کند (COMBO_POPUP_QSS) -- بدون این، پاپ‌آپ سفید پیش‌فرض ویجت‌ها
   باز می‌شود و متن روشن روی سفید خوانا نیست */
QComboBox QAbstractItemView {{
    background-color: #303844;
    border: none;
    outline: none;
    color: #f3f6fa;
    padding: 0;
    selection-background-color: #2f80ed;
    selection-color: #ffffff;
}}
QComboBox QLineEdit {{
    background: transparent;
    border: none;
    padding: 0;
    color: #f3f6fa;
    qproperty-alignment: AlignCenter;
}}
QComboBox QLineEdit:read-only {{
    background: transparent;
    border: none;
    color: #f3f6fa;
}}
QComboBox QAbstractItemView::item {{
    background-color: #303844;
    border: none;
    padding: 7px 10px;
    min-height: 24px;
}}
QComboBox QAbstractItemView::item:hover {{
    background-color: #3d4755;
}}
QComboBox:disabled, QDoubleSpinBox:disabled, QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled {{
    background-color: #252c35;
    color: #7c8795;
    border-color: #3b4552;
}}

/* فلش کشویی داخل محدودهٔ خود فیلد نگه داشته می‌شود؛ بدون margin منفی یا بیرون‌زدگی */
QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top left;
    width: 28px;
    margin: 2px;
    border: 1px solid #566273;
    border-radius: 6px;
    background-color: #3d4755;
}}
QComboBox::drop-down:hover {{
    background-color: #4b596a;
    border-color: #75d7ff;
}}
QComboBox:disabled::drop-down {{
    background-color: #303844;
    border-color: #3b4552;
}}
QComboBox::down-arrow {{
    image: url("{_DOWN_PATH}");
    width: 12px;
    height: 8px;
}}
QComboBox QAbstractItemView, QAbstractItemView#CommunicationComboPopup {{
    background-color: #303844;
    border: none;
    color: #f3f6fa;
    outline: 0;
    padding: 0;
    selection-background-color: #2f80ed;
    selection-color: #ffffff;
}}
QAbstractItemView#CommunicationComboPopup::item {{
    background-color: #303844;
    border: none;
    padding: 7px 10px;
    min-height: 24px;
}}
QAbstractItemView#CommunicationComboPopup::item:hover {{
    background-color: #3d4755;
}}
QAbstractItemView#CommunicationComboPopup::item:selected {{
    background-color: #2f80ed;
    color: #ffffff;
    border: none;
}}
QFrame#CommunicationComboPopupFrame {{
    background-color: #303844;
    border: none;
}}

/* ============================================================
   دکمه‌های کم و زیاد (▲ و ▼) ورودی‌های عددی -- شکل مثلثی واضح
   ============================================================ */
QDoubleSpinBox {{
    padding-right: 32px;
}}

/* دکمه بالا (▲) -- کاملاً داخل کادر ورودی */
QDoubleSpinBox::up-button {{
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 20px;
    height: 13px;
    margin: 5px 6px 0px 0px;
    border: 1px solid #566273;
    border-radius: 4px;
    background-color: #3d4755;
}}
QDoubleSpinBox::up-button:hover {{
    background-color: #4b596a;
}}
QDoubleSpinBox::up-button:pressed {{
    background-color: #2f80ed;
}}
QDoubleSpinBox::up-arrow {{
    image: url("{_UP_PATH}");
    width: 12px;
    height: 8px;
}}

/* دکمه پایین (▼) -- کاملاً داخل کادر ورودی */
QDoubleSpinBox::down-button {{
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 20px;
    height: 13px;
    margin: 0px 6px 5px 0px;
    border: 1px solid #566273;
    border-radius: 4px;
    background-color: #3d4755;
}}
QDoubleSpinBox::down-button:hover {{
    background-color: #4b596a;
}}
QDoubleSpinBox::down-button:pressed {{
    background-color: #2f80ed;
}}
QDoubleSpinBox::down-arrow {{
    image: url("{_DOWN_PATH}");
    width: 12px;
    height: 8px;
}}

/* دکمه‌ها -- رنگ، حاشیه و سایهٔ پایین برای تشخیص سریع حالت فشردن */
QPushButton {{
    background-color: #3f78c5;
    color: #ffffff;
    border: 1px solid #76b5ff;
    border-bottom: 3px solid #1d4e92;
    border-radius: 8px;
    padding: 8px 16px;
    min-height: 24px;
    font-weight: bold;
}}
QPushButton:hover:enabled {{
    background-color: #4c8de0;
    border-color: #9bcbff;
}}
QPushButton:pressed {{
    background-color: #2e62a8;
    border-bottom-width: 1px;
    padding-top: 10px;
}}
QPushButton:disabled {{
    background-color: #303844;
    color: #8793a2;
    border-color: #465365;
    border-bottom-color: #3a4554;
}}

QPushButton.Primary {{
    background-color: #2f80ed;
    color: #ffffff;
    border: 1px solid #7bb8ff;
    border-bottom: 3px solid #1b4f9d;
}}
QPushButton.Primary:hover:enabled {{ background-color: #4894f4; }}
QPushButton.Primary:pressed {{
    background-color: #2569c7;
    border-bottom-width: 1px;
    padding-top: 10px;
}}
QPushButton.Primary:disabled {{
    background-color: #344354;
    color: #8f9baa;
    border-color: #4b5a6c;
    border-bottom-color: #3d4a5a;
}}

QPushButton.Success {{
    background-color: #239b61;
    color: #ffffff;
    border: 1px solid #6ee7a8;
    border-bottom: 3px solid #12603c;
}}
QPushButton.Success:hover:enabled {{ background-color: #2bbd75; }}
QPushButton.Success:pressed {{
    background-color: #1b7b4e;
    border-bottom-width: 1px;
    padding-top: 10px;
}}
QPushButton.Success:disabled {{
    background-color: #30463d;
    color: #94aa9e;
    border-color: #4b6d5b;
    border-bottom-color: #3a5547;
}}

QPushButton.Danger {{
    background-color: #c83f4a;
    color: #ffffff;
    border: 1px solid #ff9aa1;
    border-bottom: 3px solid #76212a;
}}
QPushButton.Danger:hover:enabled {{ background-color: #e0525d; }}
QPushButton.Danger:pressed {{
    background-color: #a8323c;
    border-bottom-width: 1px;
    padding-top: 10px;
}}
QPushButton.Danger:disabled {{
    background-color: #4a3539;
    color: #b89da1;
    border-color: #76585e;
    border-bottom-color: #5b454a;
}}

QPushButton.Secondary {{
    background-color: #4b596a;
    color: #f3f6fa;
    border: 1px solid #8190a3;
    border-bottom: 3px solid #283441;
}}
QPushButton.Secondary:hover:enabled {{ background-color: #607188; }}
QPushButton.Secondary:pressed {{
    background-color: #3d4a59;
    border-bottom-width: 1px;
    padding-top: 10px;
}}
QPushButton.Secondary:disabled {{
    background-color: #303844;
    color: #8793a2;
    border-color: #465365;
    border-bottom-color: #3a4554;
}}

/* دکمهٔ تازه‌سازی پورت -- نماد خوانا و بدون padding عمودی اضافی */
QPushButton#RefreshButton {{
    padding: 0;
    min-width: 0;
    min-height: 0;
    color: #f3f6fa;
    font-family: "Segoe UI Symbol", "DejaVu Sans", "Tahoma", sans-serif;
    font-size: 22px;
    font-weight: bold;
}}
QPushButton#RefreshButton:pressed {{
    padding: 0;
}}

/* ============================================================
   چک‌لیست ترتیبی ایمنی پرتاب -- سه دکمهٔ مرحله
   لبه‌های گردتر + حالت غیرفعال = نسخهٔ کم‌رنگِ همان رنگ
   ============================================================ */
/* مرحله ۱ -- تست سلامت (فیروزه‌ای) */
QPushButton#Step1Button {{
    background-color: #1f8f85;
    border: 1px solid #4fd1c5;
    border-top: 1px solid #7ee8de;
    border-bottom: 2px solid #146058;
}}
QPushButton#Step1Button:hover:enabled {{ background-color: #24a89c; }}
QPushButton#Step1Button:pressed {{ background-color: #17685f; }}
QPushButton#Step1Button:disabled {{
    background-color: rgba(31, 143, 133, 0.22);
    color: rgba(255, 255, 255, 0.45);
    border: 1px solid rgba(79, 209, 197, 0.35);
}}

/* مرحله ۲ -- کالیبراسیون ناوبری (کهربایی) */
QPushButton#Step2Button {{
    background-color: #b9891f;
    border: 1px solid #f2c14e;
    border-top: 1px solid #ffd876;
    border-bottom: 2px solid #7d5c14;
}}
QPushButton#Step2Button:hover:enabled {{ background-color: #d19c26; }}
QPushButton#Step2Button:pressed {{ background-color: #93701a; }}
QPushButton#Step2Button:disabled {{
    background-color: rgba(185, 137, 31, 0.22);
    color: rgba(255, 255, 255, 0.45);
    border: 1px solid rgba(242, 193, 78, 0.35);
}}

/* مرحله ۳ -- آماده‌سازی نهایی و ورود به پرتاب (قرمز) */
QPushButton#Step3Button {{
    background-color: #b3352f;
    border: 1px solid #ef5350;
    border-top: 1px solid #ff8a80;
    border-bottom: 2px solid #7a221e;
}}
QPushButton#Step3Button:hover:enabled {{ background-color: #cc3d37; }}
QPushButton#Step3Button:pressed {{ background-color: #932b26; }}
QPushButton#Step3Button:disabled {{
    background-color: rgba(179, 53, 47, 0.22);
    color: rgba(255, 255, 255, 0.45);
    border: 1px solid rgba(239, 83, 80, 0.35);
}}

QLabel#CalibWarning {{
    color: #f2c14e;
    font-size: 14px;
    font-weight: bold;
    padding: 6px 2px;
}}

QProgressBar {{
    background-color: #0e1319;
    border: 1px solid #2b3442;
    border-radius: 8px;
    text-align: center;
    color: #e6ebf1;
    height: 20px;
}}
QProgressBar::chunk {{
    background-color: #4fd1c5;
    border-radius: 7px;
}}
QProgressBar#CalibProgress::chunk {{
    background-color: #f2c14e;
}}

QPushButton#MediaButton {{
    background-color: #1a2029;
    border: 1px solid #2b3442;
    border-radius: 10px;
    color: #c3cddb;
    font-size: 11px;
    padding: 2px;
}}
QPushButton#MediaButton:hover {{
    background-color: #22293a;
    border-color: #4fd1c5;
}}
QPushButton#MediaButton:checked {{
    background-color: #2f6fed;
    border-color: #4183ff;
    color: #ffffff;
}}

/* دکمهٔ خروجی KML -- رنگ‌آمیزی به سبک گوگل ارث (سبز/آبی) */
QPushButton#KmlExportButton {{
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #1a8f5c, stop:0.55 #1f9d69, stop:1 #2f9df0);
    border: 1px solid #34a853;
    border-radius: 12px;
    color: #ffffff;
    font-size: 14px;
    font-weight: bold;
    padding: 6px 22px;
}}
QPushButton#KmlExportButton:hover:enabled {{
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #1fa56a, stop:0.55 #24b378, stop:1 #43aef8);
}}
QPushButton#KmlExportButton:pressed {{
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #157548, stop:0.55 #198256, stop:1 #2685c4);
}}
QPushButton#KmlExportButton:disabled {{
    background-color: #1a2029;
    border: 1px solid #262d38;
    color: #4a5568;
}}

QLabel#TimeReadout {{
    background-color: #0e1319;
    border: 1px solid #2b3442;
    border-radius: 10px;
    color: #4fd1c5;
    font-size: 18px;
    font-weight: bold;
    font-family: "Consolas", "Courier New", monospace;
    padding: 0 18px;
    qproperty-alignment: AlignCenter;
}}

QPushButton#NavArrowButton {{
    background-color: #1a2029;
    color: #4fd1c5;
    border: 1px solid #2b3442;
    border-radius: 8px;
    padding: 8px 18px;
    font-weight: bold;
}}
QPushButton#NavArrowButton:hover:enabled {{
    background-color: #24405c;
    color: #ffffff;
}}
QPushButton#NavArrowButton:disabled {{
    color: #4a5568;
    border-color: #232a35;
}}

QLabel#PageIndicator {{
    color: #8fa3b8;
    font-size: 13px;
}}

QScrollBar:vertical {{
    background: #12161c;
    width: 10px;
}}
QScrollBar::handle:vertical {{
    background: #2b3442;
    border-radius: 5px;
}}
"""


# استایل داخلی popup کشویی‌ها؛ قاب و پس‌زمینهٔ پیش‌فرض Fusion را حذف می‌کند.
# (قبلاً فقط در pages/communication.py بود؛ به‌عنوان منبع مشترک به ui/style
# آمد تا فرم‌های دیگر -- مثل «مخروط سر» صفحهٔ مأموریت -- هم‌رنگ شوند.)
COMBO_POPUP_QSS = """
QAbstractItemView {
    background-color: #303844;
    border: none;
    outline: none;
    color: #f3f6fa;
    padding: 0;
    selection-background-color: #2f80ed;
    selection-color: #ffffff;
}
QAbstractItemView::item {
    background-color: #303844;
    border: none;
    padding: 7px 10px;
    min-height: 24px;
}
QAbstractItemView::item:hover {
    background-color: #3d4755;
}
QAbstractItemView::item:selected {
    background-color: #2f80ed;
    color: #ffffff;
    border: none;
}
"""


COMBO_POPUP_BG = "#303844"


def darken_combo_popup(combo) -> None:
    """پاپ‌آپ کشویی را به‌طور کامل تیره (#303844) می‌کند.

    سه لایه را رنگ می‌زند:
      1) خودِ ویوی فهرست (QSS آیتم‌ها/هاور/انتخاب)
      2) viewport ویو
      3) «ظرف» والددِ ویو (QComboBoxPrivateContainer) -- بدون این، روی
         ویندوز یک نوار سفید در بالا و پایین پاپ‌آپ دیده می‌شود (بازخورد
         کاربر: باکس کشویی مخروط سر).

    مصرف: ui/widgets.form_grid، pages/communication و هر کشویی سفارشی.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QFrame

    popup = combo.view()
    popup.setObjectName("DarkComboPopup")
    popup.setFrameShape(QFrame.NoFrame)
    popup.setLineWidth(0)
    popup.setMidLineWidth(0)
    try:
        popup.setViewportMargins(0, 0, 0, 0)
    except AttributeError:
        pass
    popup.setContentsMargins(0, 0, 0, 0)
    popup.setStyleSheet(COMBO_POPUP_QSS)

    viewport = popup.viewport()
    viewport.setAutoFillBackground(True)
    viewport.setStyleSheet(f"background-color: {COMBO_POPUP_BG}; border: none;")

    # نوار سفید بالا/پایین از قاب/زمینهٔ ظرفِ پاپ‌آپ می‌آید، نه از آیتم‌ها
    parent = popup.parentWidget()
    while parent is not None and parent is not combo:
        if isinstance(parent, QFrame):
            parent.setObjectName("DarkComboPopupHost")
            parent.setFrameShape(QFrame.NoFrame)
            parent.setLineWidth(0)
            parent.setMidLineWidth(0)
            parent.setStyleSheet(
                f"QFrame#DarkComboPopupHost {{ background-color: {COMBO_POPUP_BG};"
                f" border: none; }}")
            # بعد از استایل‌شیت (تا بازنویسی نشود): پرکردن زمینهٔ ظرف
            parent.setAutoFillBackground(True)
            parent.setAttribute(Qt.WA_StyledBackground, True)
            break
        parent = parent.parentWidget()
