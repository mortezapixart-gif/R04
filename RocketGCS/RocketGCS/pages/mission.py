# -*- coding: utf-8 -*-
"""صفحهٔ اطلاعات مأموریت و نازل

طبق درخواست کاربر:
  - صفحهٔ «اطلاعات مأموریت» و «اطلاعات نازل» در یک صفحه ادغام شدند.
  - باکس ساعت/تاریخ (که قبلاً بالای صفحهٔ مأموریت بود) کاملاً حذف شد --
    تاریخ شمسی پرتاب دیگر این‌جا به‌صورت دستی وارد نمی‌شود، فقط در لحظهٔ
    ذخیره از ساعت سیستم گرفته می‌شود (همان مقداری که در گزارش‌ها/اکسل چاپ
    می‌شود -- تنها جایی که واقعاً لازم است).
  - اطلاعات وارد‌شده حتی بدون زدن دکمهٔ «ذخیره»، با خروج از این صفحه
    خودکار ذخیره می‌شود (hideEvent).
"""
import datetime
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QDoubleSpinBox, QComboBox,
                                QPushButton, QLabel, QFrame, QGridLayout, QSizePolicy)
from PySide6.QtCore import Qt
from ui.widgets import page_title, section_title, form_grid
from core.data_manager import data_manager
from core.jalali import gregorian_date_to_jalali_str
from core.nozzle import optimal_expansion_ratio, classify_expansion
from core.rocket_physics import SimParams, predict_summary


def _tight_card(child: QWidget) -> QFrame:
    """نسخهٔ کم‌حاشیهٔ make_card، فقط برای فرم‌های این صفحه -- تا با دو
    پارامتر در هر ردیف، عرض کافی برای جاشدن بدون اسکرول افقی باقی بماند."""
    frame = QFrame()
    frame.setProperty("class", "Card")
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(10, 12, 10, 12)
    lay.addWidget(child)
    return frame

EXPANSION_TOOLTIP = (
    "نسبت انبساط نازل (Ae/At): نسبت مساحت خروجی نازل به مساحت گلوگاه.\n"
    "هرچی این عدد بزرگ‌تر باشد، گاز خروجی بیشتر منبسط و سریع‌تر می‌شود؛\n"
    "ولی اگر خیلی بزرگ باشد (فشار خروجی کمتر از فشار محیط)، جریان گاز از\n"
    "دیوارهٔ نازل جدا می‌شود (Over-expanded) و راندمان افت می‌کند."
)

STATE_META = {
    "under": ("کم‌انبساط", "warn"),
    "optimal": ("بهینه", "ok"),
    "over": ("پرانبساط", "error"),
    "unknown": ("نامشخص", None),
}


def _ltr_spin(spin: QDoubleSpinBox) -> QDoubleSpinBox:
    # رفع باگ: فلش بالا (افزایش) در ورودی‌های عددی زیر حالت RTL کار
    # نمی‌کرد چون محل واقعی کلیک فلش‌ها با ظاهرشان جابه‌جا می‌شد.
    spin.setLayoutDirection(Qt.LeftToRight)
    spin.lineEdit().setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    return spin


class MissionPage(QWidget):
    """صفحهٔ ادغام‌شدهٔ اطلاعات مأموریت + اطلاعات نازل."""

    def __init__(self):
        super().__init__()
        self.setLayoutDirection(Qt.RightToLeft)
        root = QVBoxLayout(self)
        root.addWidget(page_title("اطلاعات مأموریت و نازل"))

        # ============================================================
        # اطلاعات مأموریت (راست) + اطلاعات نازل (چپ) -- کنار هم در یک ردیف
        # ============================================================
        columns_row = QHBoxLayout()
        columns_row.setSpacing(3)

        self.flight_number = QLineEdit()
        self.rocket_name = QLineEdit()
        self.motor_number = QLineEdit()
        self.launch_site = QLineEdit()

        self.altitude_msl = _ltr_spin(QDoubleSpinBox()); self.altitude_msl.setRange(-500, 9000); self.altitude_msl.setDecimals(0); self.altitude_msl.setSuffix(" m")
        self.total_mass = _ltr_spin(QDoubleSpinBox()); self.total_mass.setRange(0, 500); self.total_mass.setSuffix(" kg"); self.total_mass.setDecimals(1)
        self.propellant_mass = _ltr_spin(QDoubleSpinBox()); self.propellant_mass.setRange(0, 20000); self.propellant_mass.setSuffix(" g"); self.propellant_mass.setDecimals(1)
        self.body_diam = _ltr_spin(QDoubleSpinBox()); self.body_diam.setRange(20, 300); self.body_diam.setDecimals(0); self.body_diam.setSuffix(" mm"); self.body_diam.setValue(80)
        self.nose_cone = QComboBox(); self.nose_cone.addItems(["اویو", "مخروطی", "نیم‌کره", "تخت"])
        self.launch_angle = _ltr_spin(QDoubleSpinBox()); self.launch_angle.setRange(0, 90); self.launch_angle.setSuffix("°"); self.launch_angle.setValue(90)
        self.chute_d = _ltr_spin(QDoubleSpinBox()); self.chute_d.setRange(0, 8); self.chute_d.setSuffix(" m"); self.chute_d.setDecimals(2)

        mission_rows = [
            [("شماره پرواز:", self.flight_number,
              "شناسهٔ این پرواز (مثلاً F-001). در نام فایل‌های ذخیره‌شدهٔ داده و گزارش "
              "نهایی هم استفاده می‌شود."),
             ("نام راکت:", self.rocket_name,
              "نامی دلخواه برای این راکت -- در سربرگ گزارش و فایل‌های خروجی می‌آید.")],
            [("محل پرتاب:", self.launch_site,
              "نام سایت/محل پرتاب (مثلاً سمنان). در گزارش نهایی و تحلیل‌ها ثبت می‌شود."),
             ("شماره موتور:", self.motor_number,
              "شناسهٔ موتوری که روی این راکت نصب شده -- برای پیگیری تاریخچهٔ موتورها "
              "بین پرتاب‌های مختلف.")],
            [("وزن کل راکت:", self.total_mass,
              "وزن کامل راکت در لحظهٔ پرتاب: بدنه + موتور + سوخت + تجهیزات/ماژول‌ها.\n"
              "وزن ماژول‌های سنسور دوباره اضافه نمی‌شود -- همین عدد، جرم پرتاب شبیه‌ساز است."),
             ("ارتفاع از سطح دریا:", self.altitude_msl,
              "ارتفاع محل پرتاب نسبت به سطح آزاد دریا (MSL). برای محاسبهٔ دقیق فشار هوا و نسبت "
              "انبساط بهینهٔ نازل لازم است -- هرچه بالاتر باشد، هوا رقیق‌تر و فشار کمتر است.")],
            [("وزن سوخت:", self.propellant_mass,
              "وزن سوخت جامد (گرم). سوخت بیشتر = ضربهٔ کل بیشتر = اوج بالاتر؛\n"
              "ولی وزن بیشتر هم سرعت می‌گیرد -- نتیجهٔ خالص را در «پیش‌بینی عملکرد» ببینید.\n\n"
              "برای مسیر پرواز فقط همین وزن است که حین سوزش از وزن کل کم می‌شود؛\n"
              "وزن خالی موتور بخشی از «وزن کل» است و اثر جداگانه ندارد (به همین دلیل\n"
              "فیلد جداگانه‌ای برای آن نداریم."),
             ("مخروط سر:", self.nose_cone,
              "شکل دماغهٔ راکت. در سرعت‌های زیرصوت «نیم‌کره» کم‌درگ‌ترین و «تخت»\n"
              "پردرگ‌ترین است؛ «اویو» (Ogive) انتخاب متعادل و رایج راکت‌های آماتور است.\n"
              "ضریب اصلاح مقاومت هوا: نیم‌کره ×۰٫۸۵ / اویو ×۱٫۰ / مخروطی ×۱٫۱۲ / تخت ×۱٫۴۵")],
            [("قطر بدنه:", self.body_diam,
              "بیرونی‌ترین قطر بدنهٔ راکت (بدون باله) بر حسب میلی‌متر. قطر بزرگ‌تر یعنی\n"
              "مقاومت هوا (درگ) بیشتر، فشار دینامیکی بیشتر و اوج کمتر -- ولی جا برای\n"
              "ماژول‌ها و چتر بیشتر. این عدد مستقیماً در شبیه‌سازی و پیش‌بینی اثر می‌گذارد."),
             ("قطر چتر بازیابی:", self.chute_d,
              "قطر چتر بازیابی (متر). هرچه چتر بزرگ‌تر باشد سرعت فرود کمتر و فرود نرم‌تر است،\n"
              "ولی راکت بیشتر با باد جابه‌جا می‌شود. مقدار صفر یعنی بدون چتر (در شبیه‌ساز\n"
              "آموزشی، راکت با سرعت خیلی بالا سقوط می‌کند!)")],
            [("زاویه پرتاب:", self.launch_angle,
              "زاویهٔ پرتاب نسبت به افق: ۹۰ درجه یعنی کاملاً عمودی. راکت‌ها معمولاً کمی کمتر از ۹۰ "
              "درجه پرتاب می‌شوند تا در مسیر باد، بیش‌ازحد به سمت محل پرتاب برنگردند.")],
                ]

        mission_col = QVBoxLayout()
        mission_col.setSpacing(4)
        mission_col.addWidget(section_title("اطلاعات مأموریت"))
        mission_card = _tight_card(form_grid(mission_rows))
        mission_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        mission_col.addWidget(mission_card)
        mission_wrap = QWidget()
        mission_wrap.setLayout(mission_col)

        # ============================================================
        # بخش ۲: اطلاعات نازل
        # ============================================================
        self.throat_d = _ltr_spin(QDoubleSpinBox()); self.throat_d.setRange(0, 500); self.throat_d.setSuffix(" mm")
        self.exit_d = _ltr_spin(QDoubleSpinBox()); self.exit_d.setRange(0, 1000); self.exit_d.setSuffix(" mm")
        self.conv_angle = _ltr_spin(QDoubleSpinBox()); self.conv_angle.setRange(0, 90); self.conv_angle.setSuffix("°")
        self.div_angle = _ltr_spin(QDoubleSpinBox()); self.div_angle.setRange(0, 90); self.div_angle.setSuffix("°")
        self.nozzle_len = _ltr_spin(QDoubleSpinBox()); self.nozzle_len.setRange(0, 100); self.nozzle_len.setSuffix(" cm"); self.nozzle_len.setDecimals(2)
        self.chamber_p = _ltr_spin(QDoubleSpinBox()); self.chamber_p.setRange(1, 300); self.chamber_p.setSuffix(" bar"); self.chamber_p.setValue(40)

        # سه شاخص انبساط نازل -- قبلاً یک باکس جدا بودند؛ حالا داخل همان باکس
        # اطلاعات نازل، زیر «فشار محفظه» و «طول نازل» می‌آیند. «نسبت انبساط» و
        # «وضعیت» در یک خط، «نسبت پیشنهادی» در خط بعد. فونت هم‌اندازهٔ بقیهٔ
        # فیلدها (نه CardValue درشت) و بدون هیچ پس‌زمینه‌ای زیر نوشته.
        _val_style = "background:transparent; color:#f3f6fa; font-size:14px; font-weight:400;"
        self.ratio_value = QLabel("--")
        self.ratio_value.setAlignment(Qt.AlignCenter); self.ratio_value.setFixedWidth(150)
        self.ratio_value.setStyleSheet(_val_style)
        self.status_value = QLabel("--")
        self.status_value.setAlignment(Qt.AlignCenter); self.status_value.setFixedWidth(150)
        self.status_value.setStyleSheet(_val_style)
        self.optimal_value = QLabel("--")
        self.optimal_value.setAlignment(Qt.AlignCenter); self.optimal_value.setFixedWidth(150)
        self.optimal_value.setStyleSheet(_val_style)

        nozzle_rows = [
            [("قطر خروجی:", self.exit_d,
              "قطر خروجی (Exit): دهانهٔ انتهایی نازل که گاز از آن خارج می‌شود. نسبت این قطر به قطر "
              "گلوگاه، «نسبت انبساط» نازل را می‌سازد (پایین‌تر توضیح داده شده)."),
             ("قطر گلوگاه:", self.throat_d,
              "قطر گلوگاه (Throat): تنگ‌ترین نقطهٔ نازل، جایی که سرعت گاز خروجی به سرعت صوت می‌رسد. "
              "این عدد مستقیماً روی فشار محفظه و نیروی رانش موتور اثر می‌گذارد.")],
            [("زاویه واگرا:", self.div_angle,
              "زاویهٔ دیوارهٔ بخش واگرای نازل (بعد از گلوگاه تا خروجی). این زاویه هم‌اکنون\n"
              "در شبیه‌سازی اثر واقعی دارد: تلفات واگرایی با λ=(1+cosα)/2 مدل می‌شود؛\n"
              "۱۵ درجه مرجع است (بدون جریمه)؛ ۳۰ درجه حدود ۵٪ رانش کمتر و ۸ درجه\n"
              "حدود ۱٪ رانش بیشتر. زاویهٔ رایج ۱۲ تا ۱۸ درجه است؛ زاویهٔ بزرگ‌تر نازل\n"
              "کوتاه‌تر ولی پرتلفات‌تر می‌شود (جریان از دیواره جدا می‌شود)."),
             ("زاویه همگرا:", self.conv_angle,
              "زاویهٔ دیوارهٔ بخش همگرای نازل (از محفظه تا گلوگاه). معمولاً ۳۰ تا ۴۵ درجه "
              "انتخاب می‌شود؛ نقش اصلی آن هدایت یکنواخت جریان به گلوگاه است.")],
            [("فشار محفظه:", self.chamber_p,
              "فشار تقریبیِ داخل محفظهٔ احتراق حین سوزش موتور. این یک مقدار تقریبی ورودی شماست "
              "(نه دادهٔ اندازه‌گیری‌شده) و برای محاسبهٔ نسبت انبساط بهینهٔ نازل استفاده می‌شود."),
             ("طول نازل:", self.nozzle_len,
              "طول کامل محوری نازل: از لبهٔ بالایی (شروع زاویهٔ همگرا) تا انتهای زاویهٔ واگرا -- "
              "نه فقط طول گلوگاه (تنگ‌ترین نقطه).")],
            [("نسبت انبساط:", self.ratio_value, EXPANSION_TOOLTIP),
             ("وضعیت:", self.status_value)],
            [("پیشنهادی:", self.optimal_value,
              "نسبت انبساط بهینهٔ نازل برای «ارتفاع محل پرتاب» شما (همان ارتفاع از سطح "
              "دریا که در بخش اطلاعات مأموریت وارد کرده‌اید).\n\n"
              "چرا مهم است؟ فشار هوای محیط با ارتفاع کم می‌شود؛ نازل باید گاز را دقیقاً "
              "تا فشار همان ارتفاع باز کند تا رانش کامل به‌دست آید.\n"
              "• اگر نسبت فعلی (Ae/At) کمتر از این عدد باشد: «کم‌انبساط» -- فشار خروجی "
              "از فشار محیط بیشتر است؛ جت بیرون نازل به انبساط ادامه می‌دهد (جدایش دیواره ندارد).\n"
              "• اگر بیشتر باشد: «پرانبساط» -- فشار خروجی کمتر از محیط است و جریان ممکن است "
              "داخل نازل از دیواره جدا شود.\n\n"
              "پس قطر خروجی را طوری انتخاب کنید که نسبت انبساط به این عدد نزدیک شود.")],
        ]

        nozzle_col = QVBoxLayout()
        nozzle_col.setSpacing(4)
        nozzle_col.addWidget(section_title("اطلاعات نازل"))
        nozzle_card = _tight_card(form_grid(nozzle_rows))
        nozzle_card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        nozzle_col.addWidget(nozzle_card)

        # بازبینی هندسی طول نازل: طولِ بخش واگرا از قطرها + زاویهٔ واگرا
        # محاسبه می‌شود و با عدد واردشدهٔ کاربر مقایسه می‌گردد.
        self.nozzle_len_note = QLabel("")
        self.nozzle_len_note.setWordWrap(True)
        self.nozzle_len_note.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.nozzle_len_note.setStyleSheet("color:#96a2b5; font-size:12px; padding:2px 6px;")
        nozzle_col.addWidget(self.nozzle_len_note)
        nozzle_wrap = QWidget()
        nozzle_wrap.setLayout(nozzle_col)

        # راست‌چین: اولین ویجت اضافه‌شده سمت راست صفحه قرار می‌گیرد -- پس
        # مأموریت (راست) قبل از نازل (چپ) اضافه می‌شود.
        columns_row.addWidget(mission_wrap, stretch=1)
        columns_row.addWidget(nozzle_wrap, stretch=1)
        root.addLayout(columns_row)

        # ============================================================
        # پیش‌بینی زندهٔ عملکرد پرواز (شبیه‌سازی فیزیکی با همین اعداد)
        # -- قلب آموزشی: کاربر هر پارامتری را تغییر دهد، نتیجه را فوراً می‌بیند.
        # ============================================================
        pred_col = QVBoxLayout()
        pred_title = QLabel("پیش‌بینی عملکرد پرواز (با پارامترهای فعلی -- شبیه‌سازی فیزیکی)")
        pred_title.setProperty("class", "CardTitleBig")
        pred_title.setAlignment(Qt.AlignCenter)
        pred_col.addWidget(pred_title)

        pred_grid = QGridLayout()
        pred_grid.setSpacing(6)
        self._pred_labels = {}

        def pred_field(key, title, tooltip=None):
            box = QVBoxLayout()
            t = QLabel(title); t.setProperty("class", "CardTitle")
            t.setAlignment(Qt.AlignCenter)
            if tooltip:   # توضیح با hover (به‌جای آیکون آبی -- قانون کلی برنامه)
                t.setToolTip(tooltip)
            v = QLabel("--"); v.setProperty("class", "CardValue")
            v.setAlignment(Qt.AlignCenter)
            box.addWidget(t); box.addWidget(v)
            self._pred_labels[key] = v
            return box

        for i, (key, title, *extra) in enumerate((
                ("range", "برد افقی بدون باد (m)",
                 "فاصلهٔ افقی نقطهٔ فرود تا لانچر «بدون احتساب باد» -- فقط از زاویهٔ پرتاب، "
                 "درگ هوا، وزن راکت و رانش موتور محاسبه می‌شود (عدد قطعی و قابل مقایسه).\n\n"
                 "برد واقعی فرود به این‌ها هم بستگی دارد و می‌تواند بسیار متفاوت باشد:\n"
                 "• سرعت و جهت باد در روز پرتاب -- با چترِ باز، باد عامل اصلی دورشدن راکت است.\n"
                 "• وزن راکت (سنگین‌تر = کمتر جابه‌جا).\n"
                 "• شکل و اندازهٔ باله‌ها و پایداری آیرودینامیکی (در این مدل ساده وارد نشده).\n"
                 "• اندازهٔ چتر (چتر بزرگ‌تر = رانش بیشتر با باد در حین نزول).\n\n"
                 "تخمین با بادِ تقریبی ۳ m/s را با بردن موس روی عدد این فیلد ببینید."),
                ("mass0", "وزن برخاست (kg)",
                 "وزن کامل راکت در لحظهٔ پرتاب = وزن بدنه (خشک) + کل وزن سوخت.\n"
                 "با تغییر «وزن بدنه» یا «وزن سوخت» در فرم بالا، همین عدد عوض می‌شود.\n\n"
                 "• وزن بیشتر با همان موتور = شتاب کمتر، اوج کمتر و سرعت پایین‌تر.\n"
                 "• وزن کمتر = راکت سریع‌تر اما حساس‌تر به باد و ناپایداری."),
                ("thrust", "رانش میانگین موتور (N)",
                 "میانگین نیروی موتور در طول سوزش -- سوخت بیشتر در بدنه، رانش بیشتری "
                 "می‌سازد.\n\n"
                 "• رانش بالاتر = شتاب و سرعت بیشتر در پایان سوزش.\n"
                 "• برای بلندشدن راکت، رانش باید به‌طور قابل‌توجهی بیشتر از وزن او "
                 "باشد (نسبت رانش به وزن را ببینید)."),
                ("burn", "مدت سوزش (s)",
                 "مدت زمانی که موتور روشن است و راکت شتاب می‌گیرد؛ با مقدار سوخت "
                 "نسبت مستقیم دارد.\n\n"
                 "• سوزش طولانی‌تر = سرعت بیشتری در لحظهٔ خاموشی موتور.\n"
                 "• پس از پایان سوزش، راکت فقط با اینرسی‌اش بالا می‌رود و برخلاف درگ "
                 "و گرانش، دیگر سرعتش بیشتر نمی‌شود."),
                ("twr", "نسبت رانش به وزن",
                 "رانش میانگین موتور تقسیم بر وزن پرتاب (بر حسب g) -- نه رانش لحظهٔ صفر.\n\n"
                 "• بالای ۳ برای پایداری روی ریل مناسب است (هشدار موتور زیر ۳ یا بالای ۱۵).\n"
                 "• بالای ۱ حداقلِ بلندشدن است؛ خیلی بالا بار شتابی روی بدنه را زیاد می‌کند."),
                ("apogee", "اوج پرواز (m)",
                 "بیشترین ارتفاع راکت از سطح لانچر.\n\n"
                 "• با زاویهٔ پرتاب ۹۰ درجه (کاملاً عمودی) بیشترین اوج به دست می‌آید؛ "
                 "هرچه از عمود فاصله بگیرید، اوج کمتر و برد بیشتر می‌شود.\n"
                 "• وزن کمتر، سوخت بیشتر و درگ کمتر = اوج بالاتر.\n"
                 "• در لحظهٔ اوج سرعت عمودی تقریباً صفر است؛ چتر ۲ ثانیه بعد از اوج باز می‌شود."),
                ("vmax", "حداکثر سرعت (m/s)",
                 "بیشترین سرعت راکت در کل پرواز -- معمولاً درست پیش از خاموشی موتور "
                 "(پایان سوزش).\n\n"
                 "• سرعت را رانش و مدت سوزش بالا می‌برد و درگ هوا و گرانش پایین "
                 "می‌آورد.\n"
                 "• سرعت هوایی زیاد = فشار دینامیکی و بار بیشتر روی بدنه و باله‌ها."),
                ("gmax", "حداکثر شتاب (g)",
                 "بیشینهٔ نیروی ویژه در نمونه‌های ۱۰ Hz (معمولاً حین سوزش؛ ضربهٔ چتر هم شمرده می‌شود).\n\n"
                 "• مستقیم به «نسبت رانش به وزن» بستگی دارد: راکت سبک + موتور قوی = "
                 "شتاب زیاد.\n"
                 "• شتاب بالا روی بدنه، اتصالات و سنسورها بار می‌گذارد -- در طراحی "
                 "و انتخاب ماژول‌ها به یاد داشته باشید."),
                ("vland", "سرعت فرود (m/s)",
                 "سرعت برخورد راکت با زمین هنگام فرود با چترِ باز.\n\n"
                 "• مستقیم به قطر چتر بازیابی و وزن راکت بستگی دارد: چتر بزرگ‌تر = "
                 "فرود نرم‌تر.\n"
                 "• سرعت فرود در بازهٔ ۳ تا ۸ m/s برای جلوگیری از آسیب به بدنه و "
                 "الکترونیک مناسب است."),
        )):
            pred_grid.addLayout(pred_field(key, title, extra[0] if extra else None),
                                i // 5, i % 5)
        for col in range(5):
            pred_grid.setColumnStretch(col, 1)
        pred_col.addLayout(pred_grid)

        self.pred_warning_lbl = QLabel("")
        self.pred_warning_lbl.setWordWrap(True)
        self.pred_warning_lbl.setAlignment(Qt.AlignCenter)
        pred_col.addWidget(self.pred_warning_lbl)
        # کارت پیش‌بینی فشرده‌تر (حاشیهٔ کم از make_card) و هم‌عرض/هم‌لبهٔ
        # دو کارت بالایی -- هر سه فرزند مستقیم root با تمام‌عرض‌اند.
        pred_card = QFrame()
        pred_card.setProperty("class", "Card")
        pred_lay = QVBoxLayout(pred_card)
        pred_lay.setContentsMargins(8, 6, 8, 8)
        pred_lay.addWidget(self._wrap(pred_col))
        root.addWidget(pred_card)

        # ============================================================
        # ذخیرهٔ مشترک
        # ============================================================
        save_row = QHBoxLayout()
        self.save_status_lbl = QLabel("")
        self.save_status_lbl.setProperty("class", "CardTitle")
        save_btn = QPushButton("ذخیره اطلاعات مأموریت و نازل")
        save_btn.setProperty("class", "Primary")
        save_btn.clicked.connect(self.save_all)
        save_row.addWidget(self.save_status_lbl)
        save_row.addStretch()
        save_row.addWidget(save_btn)
        root.addLayout(save_row)
        root.addStretch()

        for w in (self.throat_d, self.exit_d, self.chamber_p):
            w.valueChanged.connect(self._update_expansion)
        for w in (self.throat_d, self.exit_d, self.div_angle, self.nozzle_len):
            w.valueChanged.connect(self._update_nozzle_length_note)
        # پیش‌بینی زندهٔ عملکرد: با تغییر هر پارامتر فیزیکی دوباره محاسبه می‌شود
        for w in (self.total_mass, self.propellant_mass, self.altitude_msl,
                  self.launch_angle, self.chute_d, self.body_diam,
                  self.throat_d, self.exit_d, self.chamber_p, self.div_angle):
            w.valueChanged.connect(self._update_prediction)
        self.nose_cone.currentIndexChanged.connect(self._update_prediction)
        data_manager.mission_changed.connect(self._update_expansion)
        data_manager.mission_changed.connect(self._on_external_data_changed)
        data_manager.motor_changed.connect(self._on_external_data_changed)
        data_manager.sensor_model_changed.connect(lambda *_: self._update_prediction())
        self._update_expansion()
        self._update_nozzle_length_note()
        self._load_from_data_manager()
        self._update_prediction()

    def _on_external_data_changed(self, *_):
        """هماهنگ‌سازی با تغییراتی که جای دیگر برنامه اعمال شده -- مثلاً پرشدن
        خودکار پیش‌فرض‌های حالت آموزشی هنگام اتصال به پورت فرضی."""
        self._load_from_data_manager()
        self._update_prediction()

    # ------------------------------------------------------------------
    def _wrap(self, layout):
        w = QWidget(); w.setLayout(layout)
        # شفاف (بدون مستطیل سیاه داخل کارت) + قاعدهٔ tooltip در همین محدوده
        # تا tooltip فرزندان (با استایل‌خطیِ این ویجت) خاکستری بماند.
        from ui.style import TOOLTIP_QSS
        w.setStyleSheet("background:transparent;" + TOOLTIP_QSS)
        return w


    def _load_from_data_manager(self):
        """پرکردن فیلدها از دادهٔ ذخیره‌شدهٔ فعلی -- برای وقتی صفحه دوباره
        باز می‌شود (مثلاً بعد از پرشدن خودکار در حالت آموزشی)."""
        m, mo = data_manager.mission, data_manager.motor
        self.flight_number.setText(m.flight_number)
        self.rocket_name.setText(m.rocket_name)
        self.motor_number.setText(m.motor_number)
        self.launch_site.setText(m.launch_site)
        self.altitude_msl.setValue(m.altitude_msl)
        self.total_mass.setValue(m.total_mass)
        self.propellant_mass.setValue(m.propellant_mass)
        self.body_diam.setValue(round((m.body_diameter or 0.08) * 1000))
        self.nose_cone.setCurrentText(m.nose_cone or "اویو")
        self.launch_angle.setValue(m.launch_angle or 90)
        self.chute_d.setValue(m.chute_diameter_m)
        self.throat_d.setValue(mo.throat_diameter)
        self.exit_d.setValue(mo.exit_diameter)
        self.conv_angle.setValue(mo.convergent_angle)
        self.div_angle.setValue(mo.divergent_angle)
        self.nozzle_len.setValue(mo.nozzle_length)
        self.chamber_p.setValue(mo.chamber_pressure_bar or 40)

    def _update_expansion(self):
        if self.throat_d.value() <= 0:
            return
        ratio = (self.exit_d.value() / self.throat_d.value()) ** 2
        self.ratio_value.setText(f"{ratio:.2f}")

        altitude = data_manager.get_launch_altitude()
        chamber_pa = self.chamber_p.value() * 1e5  # bar -> Pa
        optimal = optimal_expansion_ratio(chamber_pa, altitude)
        self.optimal_value.setText(f"{optimal:.2f}")   # ارتفاع در توضیح (آیکون آبی) آمده است

        state = classify_expansion(ratio, optimal)
        label, status = STATE_META[state]
        self.status_value.setText(label)
        # رنگ وضعیت بدون کلاس‌های بولد -- هم‌فونت/هم‌وزن بقیهٔ مقادیر فرم
        color = {"ok": "#3fe08f", "warn": "#f5cc5f", "error": "#f2635f"}.get(status, "#f3f6fa")
        self.status_value.setStyleSheet(
            f"background:transparent; color:{color}; font-size:14px; font-weight:400;")

    def save_all(self):
        """ذخیرهٔ هر دو بخش (مأموریت + نازل) در data_manager -- هم با کلیک
        دکمه صدا زده می‌شود، هم خودکار موقع خروج از صفحه (hideEvent).

        فقط وقتی واقعاً چیزی تغییر کرده باشد سیگنال ذخیره ساطع می‌شود؛ در
        غیر این صورت (مثلاً کاربر فقط صفحه را دید و بدون تغییر خارج شد)،
        هیچ اتفاقی نمی‌افتد -- که مهم است چون emit این سیگنال‌ها یعنی
        «اطلاعات ارسال‌شده به کامپیوتر پرواز دیگر معتبر نیست» (چک‌لیست
        کالیبراسیون)، و نباید بدون تغییر واقعی باطل شود."""
        m, mo = data_manager.mission, data_manager.motor

        new_mission = dict(
            flight_number=self.flight_number.text(),
            rocket_name=self.rocket_name.text(), motor_number=self.motor_number.text(),
            launch_site=self.launch_site.text(), altitude_msl=self.altitude_msl.value(),
            total_mass=self.total_mass.value(),
            propellant_mass=self.propellant_mass.value(), launch_angle=self.launch_angle.value(),
            body_diameter=self.body_diam.value() / 1000.0,
            nose_cone=self.nose_cone.currentText(),
            chute_diameter_m=self.chute_d.value(),
        )
        mission_dirty = any(getattr(m, k) != v for k, v in new_mission.items())

        new_motor = dict(
            throat_diameter=self.throat_d.value(), exit_diameter=self.exit_d.value(),
            convergent_angle=self.conv_angle.value(), divergent_angle=self.div_angle.value(),
            nozzle_length=self.nozzle_len.value(), chamber_pressure_bar=self.chamber_p.value(),
        )
        motor_dirty = any(getattr(mo, k) != v for k, v in new_motor.items())

        if mission_dirty:
            for k, v in new_mission.items():
                setattr(m, k, v)
            now = datetime.datetime.now()
            m.date = now.date().isoformat()
            m.jalali_date = gregorian_date_to_jalali_str(now.date())
            m.time = now.strftime("%H:%M:%S")
            data_manager.mission_changed.emit()

        if motor_dirty:
            for k, v in new_motor.items():
                setattr(mo, k, v)

        perf_dirty = data_manager.refresh_motor_performance()
        if motor_dirty or perf_dirty:
            data_manager.motor_changed.emit()

        if mission_dirty or motor_dirty or perf_dirty:
            self.save_status_lbl.setText(f"✅ ذخیره شد -- {datetime.datetime.now().strftime('%H:%M:%S')}")

    def hideEvent(self, event):
        """ذخیرهٔ خودکار وقتی کاربر بدون زدن دکمهٔ «ذخیره» از این صفحه خارج
        می‌شود (طبق درخواست صریح کاربر)."""
        self.save_all()
        super().hideEvent(event)

    # ------------------------------------------------------------------
    def _update_nozzle_length_note(self):
        """بازبینی هندسی «طول نازل»: بخش واگرای مخروطی با زاویهٔ واگرای α و
        قطرهای گلوگاه/خروجی، طول محوری مشخصی دارد: L = (De−Dt)/(2·tanα).
        بخش همگرا به قطر محفظه بستگی دارد که فیلدش وجود ندارد، پس فقط همان
        بخش واگرا بازبینی می‌شود (حداقلِ قابل‌دفاع)."""
        import math
        de, dt, alpha, ln = (self.exit_d.value(), self.throat_d.value(),
                             self.div_angle.value(), self.nozzle_len.value())
        if not (de > dt > 0 and alpha > 0):
            self.nozzle_len_note.setText("")
            return
        l_div_cm = (de - dt) / 2.0 / math.tan(math.radians(alpha)) / 10.0
        # عدد+واحد به‌صورت جزیرهٔ چپ‌به‌راست (LRE...PDF) تا «cm» همیشه سمت راستِ
        # عدد بماند و در متن راست‌به‌چپ جابه‌جا نشود (درخواست کاربر).
        def _cm(x: float) -> str:
            return "\u202a" + f"{x:.2f}" + " cm\u202c"

        if ln <= 0:
            self.nozzle_len_note.setText(
                f"طول هندسیِ بخش واگرا با این قطرها و زاویه: {_cm(l_div_cm)} "
                "-- برای بازبینی، طول نازل را هم وارد کنید.")
            self.nozzle_len_note.setStyleSheet("color:#96a2b5; font-size:12px; padding:2px 6px;")
        elif ln < 0.85 * l_div_cm:
            self.nozzle_len_note.setText(
                f"هشدار هندسه: طول واردشده ({_cm(ln)}) از طول بخش واگرا "
                f"({_cm(l_div_cm)} با این قطرها و زاویهٔ {alpha:.0f} درجه) کوتاه‌تر است؛ "
                "یا زاویهٔ واگرا در واقع بزرگ‌تر است یا قطر خروجی کوچک‌تر.")
            self.nozzle_len_note.setStyleSheet("color:#ef5350; font-size:12px; padding:2px 6px;")
        else:
            self.nozzle_len_note.setText(
                f"بازبینی هندسه: سازگار -- طول بخش واگرا {_cm(l_div_cm)} ≤ طول نازل {_cm(ln)}.")
            self.nozzle_len_note.setStyleSheet("color:#35d07f; font-size:12px; padding:2px 6px;")

    def _update_prediction(self):
        """شبیه‌سازی زندهٔ عملکرد با پارامترهای فعلی فرم -- آموزش فیزیک راکت:
        هر تغییری در سوخت/وزن/زاویه/نازل/چتر فوراً نتیجه می‌دهد."""
        m = data_manager.mission
        params = SimParams(
            total_mass_kg=self.total_mass.value() or m.total_mass,
            propellant_mass_g=self.propellant_mass.value(),
            body_diameter_m=self.body_diam.value() / 1000.0,
            nose_cone=self.nose_cone.currentText(),
            divergence_angle_deg=self.div_angle.value() or 15.0,
            launch_angle_deg=self.launch_angle.value(),
            altitude_msl_m=self.altitude_msl.value(),
            throat_diameter_mm=self.throat_d.value(),
            exit_diameter_mm=self.exit_d.value(),
            chamber_pressure_bar=self.chamber_p.value(),
            chute_diameter_m=self.chute_d.value(),
            sensor_models=dict(data_manager.sensor_models),
        )
        s = predict_summary(params)
        L = self._pred_labels

        def set_val(key, text):
            L[key].setText(text)

        set_val("mass0", f"{s.get('liftoff_mass_kg', 0):.2f}")
        if s.get("valid"):
            set_val("thrust", f"{s.get('thrust_avg_n', 0):.0f}")
            set_val("burn", f"{s.get('burn_time_s', 0):.2f}")
            set_val("twr", f"{s.get('initial_twr', 0):.1f}")
            set_val("apogee", f"{s.get('apogee_m', 0):.0f}")
            set_val("range", f"{s.get('range_no_wind_m', s.get('range_m', 0)):.0f}")
            self._pred_labels["range"].setToolTip(
                f"بدون باد: {s.get('range_no_wind_m', 0):.0f} متر\n"
                f"با باد تقریبی {3} m/s (جهت باد تصادفی): {s.get('range_m', 0):.0f} متر\n\n"
                "برد واقعی به باد روز پرتاب (زیر چتر عامل اصلی)، وزن راکت، باله‌ها و "
                "اندازهٔ چتر بستگی دارد.")
            set_val("vmax", f"{s.get('max_speed_ms', 0):.0f}")
            set_val("gmax", f"{s.get('max_accel_g', 0):.1f}")
            set_val("vland", f"{s.get('landing_speed_ms', 0):.1f}")
        else:
            for key in ("thrust", "burn", "twr", "apogee", "range", "vmax", "gmax", "vland"):
                set_val(key, "--")

        warnings = s.get("warnings") or []
        if warnings:
            self.pred_warning_lbl.setText("⚠️ " + "  |  ".join(warnings))
            self.pred_warning_lbl.setStyleSheet("color:#f2c14e;")
        else:
            self.pred_warning_lbl.setText("✅ همهٔ پارامترها در محدودهٔ سالم هستند.")
            self.pred_warning_lbl.setStyleSheet("color:#35d07f;")
