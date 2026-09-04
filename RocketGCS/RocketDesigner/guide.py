# -*- coding: utf-8 -*-
"""
RocketDesigner/guide.py
-----------------------
راهنمای گام‌به‌گام داخل طراح: اندازه‌گیری CG (موازنه و رشته)، قواعد پایداری،
و نکات ساخت باله -- متنی و روشن، بدون ایموجی.

نکتهٔ جهتِ متن: هیچ rich-text ای استفاده نمی‌شود؛ همهٔ برچسب‌ها متن ساده با
جهتِ راست‌به‌چپِ صریحِ ویجت هستند تا چیدمان پاراگراف در همهٔ نسخه‌های Qt و
همهٔ فونت‌ها قطعی راست‌چین بماند. شمارهٔ هر گام هم برچسب جداگانه در ستونِ
سمت راست است تا جای آن هرگز به حدسِ جهتِ متن وابسته نباشد.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QScrollArea,
                               QVBoxLayout, QWidget)

from blueprint import THEME, fa

C_DESC = "#b9c4e4"          # رنگ متنِ توضیحات (کم‌رنگ‌تر از تیترها)
C_TEXT = THEME["text"]      # رنگ متنِ اصلی
EDGE = "rgba(148, 163, 255, 0.13)"


def _rgba(hexcol: str, alpha: int) -> str:
    c = QColor(hexcol)
    return f"rgba({c.red()}, {c.green()}, {c.blue()}, {round(alpha / 255.0, 3)})"


BALANCE_STEPS = [
    ("راکت را «آمادهٔ پرواز» کنید.",
     "موتورِ پر (یا مدل هم‌وزنِ آن)، چتر، آواتار/حلقهٔ اتصال و هر چیزی که پرواز "
     "با همراه دارد را سر جایش بگذارید. CG فقط با راکتِ کامل معنا دارد؛ راکتِ خالی "
     "همیشه پایدارتر از واقعیت دیده می‌شود."),
    ("یک لبهٔ صاف افقی کنید.",
     "خط‌کش فلزی، لبهٔ میز یا یک تختهٔ باریک؛ هرچه لبهٔ تیزتر باشد اندازه‌گیری "
     "دقیق‌تر است. تراز بودش با ترازِ حباب چک کنید."),
    ("راکت را عمود بر لبه بخوابانید و بلغزانید.",
     "راکت را افقی و عمود بر لبه بگذارید و آرام جلو و عقب ببرید تا نقطه‌ای پیدا "
     "شود که دیگر به هیچ سمت نمی‌غلتد و بالانس می‌ماند."),
    ("نقطهٔ تعادل را علامت بزنید.",
     "همان نقطه، مرکز ثقل (CG) است. با ماژیک یک خط دور بدنه بکشید."),
    ("فاصلهٔ CG از نوک دماغه را اندازه بگیرید.",
     "با خط‌کش/متر، فاصلهٔ آن خط تا نوکِ دماغه را به میلی‌متر بخوانید (دقت حدود "
     "5 میلی‌متر کافی است) و در فرم طراح در قسمت «CG اندازه‌گیری‌شده» وارد کنید."),
]

STRING_STEPS = [
    ("راکت را از نزدیکِ انتها با نخ آویزان کنید.",
     "نخ را دور بدنه نزدیک دماغه ببندید و راکت را آزاد بگذارید تا آرام بگیرد؛ "
     "راکت طوری می‌چرخد که CG دقیقاً زیر نقطهٔ آویز قرار گیرد."),
    ("امتداد نخ را روی بدنه علامت بزنید.",
     "یک خط در امتداد آویز به سمت پایین بکشید."),
    ("از نقطهٔ دیگری تکرار کنید.",
     "نخ را به فاصلهٔ 10 تا 15 سانتی‌متر جلوتر ببندید و دوباره امتداد نخ را علامت "
     "بزنید. محل تقاطع دو خط، CG است."),
    ("فاصلهٔ تقاطع از نوک دماغه را اندازه بگیرید.",
     "این روش مستقل از لبه است و برای راکت‌های سبک و سنگین هر دو جواب می‌دهد؛ "
     "اختلاف با روش لبه نباید از چند میلی‌متر بیشتر باشد."),
]

RULES = [
    ("حاشیهٔ پایداری = فاصلهٔ CP تا CG تقسیم بر قطر بدنه. برای راکت آماتوری عدد بین "
     "1 و 2 کالیبر ایمن است: کمتر از 1 خطرناک و بیشتر از حدود 2.5 یعنی «بیش‌پایداری» و "
     "هوريگ شدن در باد جانبی."),
    ("CP با روش بارومن فقط برای سرعت زیرصوت و زاویهٔ حملهٔ کوچک معتبر است؛ همین برای "
     "راکت‌های آماتوری کافی است."),
    ("در طول سوزش موتور جامع، CG به سمت دماغه می‌رود و پایداری بهتر می‌شود؛ پس حساب "
     "سخت‌گیرانه، لحظهٔ پرتاب با موتور پر است."),
    ("باد جانبی در لحظهٔ جدا شدن از ریل، راکت را حول CP می‌چرخاند و CP با باد می‌سازد و "
     "بال زاویهٔ حمله می‌گیرد؛ با باد بیش از 5 تا 6 متر بر ثانیه پرتاب نکنید و ریل را "
     "بلند بگیرید تا سرعت جدا شدن از ریل بالا برود."),
]

BUILD_TIPS = [
    ("وتیر باله را از تختهٔ بالسا 2 تا 3 میلی‌متر یا فوم سبک ببرید؛ لبهٔ حمله را کمی "
     "گرد و سطح را صاف کنید تا مقاومت کم بماند."),
    ("باله‌ها را دقیقاً هم‌فاصله (برای 3 باله هر 120 درجه) و هم‌تراز با محور بدنه "
     "بچسبانید؛ حتی یک درجه انحراف، پرواز را مارپیچ می‌کند."),
    ("جای CG را پس از ساخت با افزودن وزن کوچک در دماغه (خمیر فلزی یا حلقهٔ سربی) تنظیم "
     "کنید؛ هرگز با افزودن وزن به انتها پایداری نسازید."),
]


def _lbl(text: str, size: float, color: str, bold: bool = False) -> QLabel:
    """برچسب متنِ ساده، راست‌چین، با جهت RTL صریح (بدون rich-text)."""
    w = QLabel(text)
    w.setTextFormat(Qt.PlainText)
    w.setWordWrap(True)
    w.setLayoutDirection(Qt.RightToLeft)
    w.setAlignment(Qt.AlignRight | Qt.AlignTop)
    w.setStyleSheet(f"color: {color}; font-size: {size}px; "
                    f"font-family: 'Shabnam'; background: transparent; border: none;"
                    + (" font-weight: 700;" if bold else ""))
    return w


def _step_row(idx: int, title: str, desc: str, numbered: bool,
              accent: str) -> QWidget:
    row = QWidget()
    row.setLayoutDirection(Qt.RightToLeft)
    h = QHBoxLayout(row)
    h.setContentsMargins(2, 0, 2, 0)
    h.setSpacing(9)
    if numbered:
        num = QLabel(fa(idx))
        num.setTextFormat(Qt.PlainText)
        num.setFixedWidth(22)
        num.setAlignment(Qt.AlignCenter)
        num.setStyleSheet(
            f"color: {accent}; font-size: 15px; font-weight: 800; "
            "font-family: 'Shabnam'; background: transparent; border: none;")
        h.addWidget(num, 0, Qt.AlignTop | Qt.AlignRight)
    col = QVBoxLayout()
    col.setContentsMargins(0, 0, 0, 0)
    col.setSpacing(3)
    if title:
        col.addWidget(_lbl(title, 14.5, C_TEXT, bold=True))
    col.addWidget(_lbl(desc, 13.5, C_DESC))
    col.addStretch(1)
    h.addLayout(col, 1)
    return row


def _card(title: str, steps, numbered: bool = True,
          accent: str = THEME["teal"]) -> QFrame:
    f = QFrame()
    f.setLayoutDirection(Qt.RightToLeft)
    f.setStyleSheet(
        "QFrame { background: rgba(13, 20, 40, 0.55); border: 1px solid "
        + _rgba(accent, 60) + "; border-radius: 16px; }")
    lay = QVBoxLayout(f)
    lay.setContentsMargins(18, 14, 18, 16)
    lay.setSpacing(10)
    head = QLabel(title)
    head.setTextFormat(Qt.PlainText)
    head.setLayoutDirection(Qt.RightToLeft)
    head.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    head.setStyleSheet(f"color: {accent}; font-size: 19px; font-weight: 800;"
                       " font-family: 'Shabnam'; background: transparent;"
                       " border: none;")
    lay.addWidget(head)
    line = QFrame()
    line.setFixedHeight(1)
    line.setStyleSheet(f"background: {_rgba(accent, 70)}; border: none;")
    lay.addWidget(line)
    for i, item in enumerate(steps, start=1):
        t, d = item if numbered else ("", item)
        lay.addWidget(_step_row(i, t, d, numbered, accent))
    return f


def build_guide_page() -> QWidget:
    page = QWidget()
    page.setLayoutDirection(Qt.RightToLeft)
    outer = QVBoxLayout(page)
    outer.setContentsMargins(20, 16, 20, 20)
    outer.setSpacing(14)

    title = QLabel("راهنمای اندازه‌گیری CG و ساخت")
    title.setTextFormat(Qt.PlainText)
    title.setLayoutDirection(Qt.RightToLeft)
    title.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    title.setStyleSheet(f"color: {THEME['text']}; font-size: 20px; "
                        "font-weight: 800; font-family: 'Shabnam';")
    outer.addWidget(title)

    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
    content = QWidget()
    content.setStyleSheet("background: transparent;")
    content.setLayoutDirection(Qt.RightToLeft)
    lay = QVBoxLayout(content)
    lay.setContentsMargins(2, 2, 2, 2)
    lay.setSpacing(14)

    lay.addWidget(_card("روش 1 -- موازنه روی لبه (ساده‌ترین روش)", BALANCE_STEPS,
                        accent=THEME["teal"]))
    lay.addWidget(_card("روش 2 -- آزمون رشته (دقیق‌تر)", STRING_STEPS,
                        accent=THEME["purple"]))
    lay.addWidget(_card("قواعد پایداری که باید بدانید", RULES, numbered=False,
                        accent=THEME["yellow"]))
    lay.addWidget(_card("نکات ساخت باله و وتیر", BUILD_TIPS, numbered=False,
                        accent=THEME["blue"]))
    lay.addStretch(1)

    scroll.setWidget(content)
    outer.addWidget(scroll, 1)
    return page
