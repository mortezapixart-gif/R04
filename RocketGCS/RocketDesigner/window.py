# -*- coding: utf-8 -*-
"""
RocketDesigner/window.py
------------------------
پنجرهٔ اصلی طراح راکت -- بازنسیسی کامل با زبان بصری «فضاییِ مینی‌مال»:

  • پس‌زمینهٔ فضای عمیق (گرادیان شعاعیِ مه‌آلود) و پنل‌های شیشه‌ایِ نرم
    (شعاع‌های بزرگ، مرزهای نورِ کم‌رنگ، بدون هیچ گوشهٔ تیز)
  • دکمه‌ها قرص‌مانند (pill) با گرادیان نرم؛ فیلدها شیشه‌ای با فوکوسِ فیروزه‌ای
  • کنترل تب به‌صورت دکمهٔ قطعه‌ای (segmented) نرم
  • کارت‌های پارامتر: شیشه + خطِ نورِ هویت + نقطهٔ درخشان
  • بوم نقشه (blueprint.py) با راکتِ وسط‌چین + گیج نرم (gauge.py)
  • اتصال زنده: تغییر هر عدد → به‌روزرسانی آنی بوم + پالس نورِ نرم
"""
from __future__ import annotations

import json
import os
import sys

from PySide6.QtCore import QPointF, QRectF, Qt, Signal, QTimer
from PySide6.QtGui import (QBrush, QColor, QFont, QLinearGradient, QPainter,
                           QPainterPath, QPalette, QPen, QPixmap)
from PySide6.QtWidgets import (QAbstractSpinBox, QButtonGroup, QCheckBox, QComboBox,
                               QDoubleSpinBox, QFileDialog, QFrame, QHBoxLayout,
                               QLabel,
                               QPushButton, QScrollArea, QSizePolicy,
                               QSpinBox, QStackedWidget, QVBoxLayout, QWidget)

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "RocketGCS"))
from core.barrowman import (  # noqa: E402
    MARGIN_MIN, RocketGeometry, MassItem, analyze,
    fin_set_cg_mm, nose_cg_mm, suggest_fin_span_mm, suggest_nose_mass_g,
    center_of_gravity_mm,
)
from core.design_transfer import write_design_transfer  # noqa: E402

from blueprint import Blueprint, THEME, fa, verdict_color  # noqa: E402
from gauge import MarginGauge  # noqa: E402
from guide import build_guide_page  # noqa: E402

FIELD_W = 92
FONT_FAMILY = "Shabnam"          # سری فونت سراسری برنامه
LOGO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

C_VERDICT = {"ok": ("#4ade80", "پایدار"),
             "warn": ("#ffd166", "در مرز -- اصلاح بهتر است"),
             "danger": ("#fb7185", "ناپایدار -- پرواز ممنوع"),
             "unstable": ("#fb7185", "ناپایدار -- پرواز ممنوع"),
             "over": ("#fdba74", "بیش‌پایدار"),
             "unknown": ("#93a0c4", "در انتظار ورود جرم‌ها")}

# مرزهای نورِ مشترک همهٔ سطوح شیشه‌ای
EDGE = "rgba(148, 163, 255, 0.13)"
EDGE_HI = "rgba(148, 163, 255, 0.22)"


def _rgba(hexcol: str, alpha: int) -> str:
    """رنگ شفاف برای QSS (آلفای ۰..۲۵۵ → ۰..۱)."""
    c = QColor(hexcol)
    return f"rgba({c.red()}, {c.green()}, {c.blue()}, {round(alpha / 255.0, 3)})"


def _glass(top: int = 12, bottom: int = 5) -> str:
    """پس‌زمینهٔ شیشه‌ای: برقِ ملایم بالا + بدنهٔ نیمه‌شفاف."""
    return (f"qlineargradient(x1:0, y1:0, x2:0, y2:1, "
            f"stop:0 rgba(255,255,255,{top}), "
            f"stop:0.35 rgba(255,255,255,{(top + bottom) // 2}), "
            f"stop:1 rgba(255,255,255,{bottom}))")


# پوستهٔ دارک‌مدرن با «خطِ تخت»: هیچ border-radius وجود ندارد (گوشه‌ها
# چهارگوش و خطوط مستقیم‌اند) و تنها تأکید بصری، خطِ نئونیِ ملایم است
# (سبز یشمی / آبی سایبر / کهربایی).
DESIGNER_QSS = f"""
QWidget {{ background: transparent; color: {THEME["text"]};
  font-family: 'Shabnam'; font-size: 14px; }}

/* ---- فیلدها: شیشهٔ تیرهٔ نرم ---- */
QSpinBox, QDoubleSpinBox, QComboBox {{
  background: rgba(9, 14, 30, 0.62);
  border: 1px solid {EDGE};
  border-radius: 10px; padding: 4px 30px 4px 10px; color: {THEME["text"]};
  min-width: {FIELD_W}px; min-height: 18px; max-height: 18px;
  selection-background-color: {_rgba(THEME["neon_jade"], 80)};
  selection-color: #eafffa; }}
QSpinBox:focus, QDoubleSpinBox:focus {{
  border: 1px solid {_rgba(THEME["neon_jade"], 150)};
  background: rgba(12, 19, 40, 0.80); }}
QSpinBox:disabled, QDoubleSpinBox:disabled {{
  color: {THEME["sub"]}; border: 1px solid rgba(148, 163, 255, 0.07);
  background: rgba(9, 14, 30, 0.40); }}
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {{
  width: 0; height: 0; background: transparent; border: none; }}
QComboBox::drop-down {{
  subcontrol-origin: border; width: 20px;
  background: transparent; border: none; }}
QComboBox:focus {{ border: 1px solid {_rgba(THEME["neon_cyber"], 150)}; }}
QComboBox QAbstractItemView {{
  background: #10182e; color: {THEME["text"]};
  border: 1px solid {EDGE_HI}; border-radius: 12px; padding: 6px;
  selection-background-color: {_rgba(THEME["neon_cyber"], 60)};
  selection-color: #eaf4ff; outline: none; }}
QComboBox QAbstractItemView QWidget {{ background: #10182e; }}
QCheckBox {{ color: {THEME["text"]}; spacing: 8px; }}
QCheckBox::indicator {{
  width: 18px; height: 18px; border-radius: 6px;
  border: 1px solid {EDGE_HI}; background: rgba(9, 14, 30, 0.62); }}
QCheckBox::indicator:hover {{ border: 1px solid {_rgba(THEME["neon_jade"], 130)}; }}
QCheckBox::indicator:checked {{
  background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
      stop:0 {_rgba(THEME["neon_jade"], 230)}, stop:1 {_rgba(THEME["neon_cyber"], 210)});
  border: 1px solid {_rgba(THEME["neon_jade"], 200)}; }}

/* ---- دکمه‌ها: قرصِ نرم ---- */
QPushButton#ActionBtn {{
  background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
      stop:0 #86f3dd, stop:1 #5cc9f2);
  color: #05262b; font-weight: bold; border: none;
  border-radius: 12px; padding: 9px 20px; }}
QPushButton#ActionBtn:hover {{
  background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
      stop:0 #a7f8e9, stop:1 #7dd8f8); }}
QPushButton#ActionBtn:pressed {{ background: #38b6a0; }}
QPushButton#GhostBtn {{
  background: rgba(255, 255, 255, 0.05); color: {THEME["text"]};
  border: 1px solid {EDGE_HI}; border-radius: 12px; padding: 9px 20px; }}
QPushButton#GhostBtn:hover {{
  background: rgba(255, 255, 255, 0.09); color: #d9fff6;
  border: 1px solid {_rgba(THEME["neon_jade"], 110)}; }}
QPushButton#GhostBtn:pressed {{ background: rgba(255, 255, 255, 0.03); }}

/* ---- اسکرول: نوار نورِ باریک ---- */
QScrollArea {{ border: none; }}
QScrollBar:vertical {{ background: transparent; width: 10px; border: none; }}
QScrollBar::handle:vertical {{ background: rgba(148, 163, 255, 0.20);
  border-radius: 5px; min-height: 30px; margin: 2px; }}
QScrollBar::handle:vertical:hover {{ background: {_rgba(THEME["neon_jade"], 140)}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; border: none; }}
QScrollBar::handle:horizontal {{ background: rgba(148, 163, 255, 0.20);
  border-radius: 5px; min-width: 30px; margin: 2px; }}
QScrollBar::handle:horizontal:hover {{ background: {_rgba(THEME["neon_jade"], 140)}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QToolTip {{ background: #131c36; color: {THEME["text"]};
  border: 1px solid {_rgba(THEME["neon_jade"], 90)};
  border-radius: 9px; padding: 5px 8px; }}
"""


def _tab_qss(col: str) -> str:
    """تبِ قطعه‌ای نرم: خاموش = شیشهٔ بی‌رنگ؛ فعال = شیشهٔ رنگیِ ملایم."""
    return f"""
    QPushButton {{
        background: rgba(255, 255, 255, 0.03); color: {THEME["sub"]};
        border: 1px solid rgba(148, 163, 255, 0.08); border-radius: 10px;
        padding: 6px 16px; font-weight: bold; font-size: 13px;
    }}
    QPushButton:hover {{ color: {THEME["text"]};
        background: rgba(255, 255, 255, 0.07); }}
    QPushButton:checked {{
        background: {_rgba(col, 40)}; color: {col};
        border: 1px solid {_rgba(col, 120)};
    }}
    """


def _advice_qss(accent: str) -> str:
    """کارت پیشنهاد: شیشهٔ نرم با نوار نور در سمت راست."""
    return (
        "QLabel#AdviceCard {"
        f" color: {THEME['text']}; background: {_glass(10, 4)};"
        f" border: 1px solid {EDGE}; border-radius: 14px;"
        f" border-right: 3px solid {_rgba(accent, 170)}; padding: 9px 14px;"
        " font-size: 13.5px; font-family: 'Shabnam'; }")


def _verdict_qss(color: str) -> str:
    """قرصِ حکم: شیشهٔ رنگیِ ملایم با حاشیهٔ نور."""
    c = QColor(color)
    lum = 0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()
    fg = "#08131f" if lum > 190 else "#ffffff"
    return (
        "QLabel#VerdictBadge {"
        f" color: {fg}; background: {_rgba(color, 70)}; font-size: 14px;"
        f" font-weight: bold; border: 1px solid {_rgba(color, 150)};"
        " border-radius: 12px; padding: 9px 20px; }")


def num(value, unit: str = "", decimals: int = 1) -> str:
    txt = fa(f"{value:.{decimals}f}")
    return f"\u202a{txt}{' ' + unit if unit else ''}\u202c"


TEAL_ARROW = "#35d0ba"          # رنگ پیکان‌ها مطابق مرجع


class _StepPad(QWidget):
    """پدِ پله‌ها مطابق مرجع: مربعِ گردِ خاکستری-آبی داخل فیلد با دو پیکان فیروزه‌ای."""

    up = Signal()
    down = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hover = False
        self._half = -1           # 0 = بالا، 1 = پایین (فشرده)، -1 = هیچ
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)

    def enterEvent(self, ev):
        self._hover = True
        self.update()

    def leaveEvent(self, ev):
        self._hover, self._half = False, -1
        self.update()

    def mousePressEvent(self, ev):
        self._half = 1 if ev.position().y() > self.height() / 2 else 0
        self.update()

    def mouseReleaseEvent(self, ev):
        half = 1 if ev.position().y() > self.height() / 2 else 0
        (self.down if half else self.up).emit()
        self._half = -1
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setBrush(QBrush(QColor(255, 255, 255, 40 if self._hover else 26)))
        p.setPen(QPen(QColor(255, 255, 255, 26), 1))
        p.drawRoundedRect(r, 7, 7)
        cx = r.center().x()
        cy_up = r.top() + r.height() * 0.28
        cy_dn = r.top() + r.height() * 0.72
        for cy, is_up in ((cy_up, True), (cy_dn, False)):
            pressed = self._half == (0 if is_up else 1)
            col = QColor("#eafffb" if pressed else TEAL_ARROW)
            path = QPainterPath()
            if is_up:
                path.moveTo(cx, cy - 3.0)
                path.lineTo(cx - 4.4, cy + 2.6)
                path.lineTo(cx + 4.4, cy + 2.6)
            else:
                path.moveTo(cx, cy + 3.0)
                path.lineTo(cx - 4.4, cy - 2.6)
                path.lineTo(cx + 4.4, cy - 2.6)
            path.closeSubpath()
            p.setBrush(QBrush(col))
            p.setPen(Qt.NoPen)
            p.drawPath(path)
        p.end()


class _ComboArrow(QWidget):
    """پدِ پیکانِ کشویی مطابق مرجع: مربع گرد با یک پیکان فیروزه‌ای."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setBrush(QBrush(QColor(255, 255, 255, 26)))
        p.setPen(QPen(QColor(255, 255, 255, 26), 1))
        p.drawRoundedRect(r, 7, 7)
        cx, cy = r.center().x(), r.center().y()
        path = QPainterPath()
        path.moveTo(cx - 4.6, cy - 2.4)
        path.lineTo(cx + 4.6, cy - 2.4)
        path.lineTo(cx, cy + 3.2)
        path.closeSubpath()
        p.setBrush(QBrush(QColor(TEAL_ARROW)))
        p.setPen(Qt.NoPen)
        p.drawPath(path)
        p.end()


class SoftComboBox(QComboBox):
    """باکس کشویی شیشه‌ای با پدِ پیکان داخلی (بدون هیچ سطح سفید)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._arrow = _ComboArrow(self)

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._arrow.setGeometry(self.width() - 25, 4, 21, self.height() - 8)


class SoftSpinBox(QSpinBox):
    """اسپین‌باکس شیشه‌ای با دکمه‌های پله *داخل* کادر (هرگز بیرون نمی‌زند)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._pad = _StepPad(self)
        self._pad.up.connect(self.stepUp)
        self._pad.down.connect(self.stepDown)

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._pad.setGeometry(self.width() - 25, 4, 21, self.height() - 8)


class SoftDoubleSpinBox(QDoubleSpinBox):
    """نسخهٔ اعشاری همان فیلد نرم."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self._pad = _StepPad(self)
        self._pad.up.connect(self.stepUp)
        self._pad.down.connect(self.stepDown)

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._pad.setGeometry(self.width() - 25, 4, 21, self.height() - 8)


def _dark_popup(cmb: QComboBox):
    """پالتِ تیره برای لیستِ بازشو -- تا هیچ سطحِ سفیدی پشت آن دیده نشود."""
    pal = cmb.palette()
    for role in (QPalette.Base, QPalette.Window, QPalette.Button):
        pal.setColor(role, QColor("#10182e"))
    for role in (QPalette.Text, QPalette.WindowText, QPalette.ButtonText):
        pal.setColor(role, QColor(THEME["text"]))
    pal.setColor(QPalette.Highlight, QColor(THEME["neon_cyber"]))
    pal.setColor(QPalette.HighlightedText, QColor("#08131f"))
    cmb.setPalette(pal)


def _spin(lo, hi, val, step=5):
    s = SoftSpinBox()
    s.setRange(int(lo), int(hi))
    s.setSingleStep(int(step))
    s.setValue(int(val))
    s.setAlignment(Qt.AlignCenter)          # اعداد وسط‌چین
    return s


# ---------------------------------------------------------------------------
class LogoBadge(QWidget):
    """لوگوی کافنا در سربرگ.

    اگر فایل لوگو در RocketDesigner/assets/kafna_logo.png (یا jpg) وجود داشته
    باشد همان نمایش داده می‌شود؛ در غیر این صورت یک نشان‌نوشتارِ نرمِ داخلی
    («کافنا» با فونت شبنم روی قرصِ گرادیانی) رسم می‌شود.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pix = None
        for name in ("kafna_logo.png", "kafna_logo.jpg", "kafna_logo.jpeg"):
            path = os.path.join(LOGO_DIR, name)
            if os.path.exists(path):
                pix = QPixmap(path)
                if not pix.isNull():
                    self._pix = pix
                break
        # نشانِ رسمی مربعِ تقریبی است؛ نشان‌نوشتارِ جایگزین عریض‌تر
        self.setFixedSize(52 if self._pix else 124, 44)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        if self._pix is not None:
            # برچسب سفیدِ گرد پشت نشان (لوگوی رسمی پس‌زمینهٔ سفید دارد)
            p.setBrush(QBrush(QColor("#f7fafc")))
            p.setPen(QPen(QColor(255, 255, 255, 120), 1))
            p.drawRoundedRect(rect, 11, 11)
            dpr = self.devicePixelRatioF()
            inner = rect.adjusted(3, 3, -3, -3)
            p.setClipRect(inner.toRect())
            scaled = self._pix.scaled(int(inner.width() * dpr),
                                      int(inner.height() * dpr),
                                      Qt.KeepAspectRatio, Qt.SmoothTransformation)
            scaled.setDevicePixelRatio(dpr)
            dw = scaled.deviceIndependentSize().width()
            dh = scaled.deviceIndependentSize().height()
            p.drawPixmap(int(inner.center().x() - dw / 2),
                         int(inner.center().y() - dh / 2), scaled)
            p.setClipping(False)
            return
        grad = QLinearGradient(rect.left(), rect.top(), rect.right(), rect.bottom())
        grad.setColorAt(0.0, QColor(THEME["teal"]))
        grad.setColorAt(1.0, QColor(THEME["purple"]))
        p.setBrush(QBrush(grad))
        p.setPen(QPen(QColor(255, 255, 255, 90), 1))
        p.drawRoundedRect(rect, 13, 13)
        p.setFont(QFont(FONT_FAMILY, 17, QFont.Bold))
        p.setPen(QColor("#08131f"))
        p.drawText(QRectF(rect.x() + 8, rect.y(), rect.width() - 8, rect.height()),
                   Qt.AlignCenter, "کافنا")
        p.end()


# ---------------------------------------------------------------------------
class ParamCard(QFrame):
    """کارت شیشه‌ای گروه پارامترها: خط نورِ هویت + نقطهٔ درخشان + ردیف‌ها."""

    def __init__(self, title: str, color: str):
        super().__init__()
        self.setObjectName("ParamCard")
        self.setStyleSheet(
            f"QFrame#ParamCard {{ background: qlineargradient(x1:0, y1:0,"
            f" x2:0, y2:1, stop:0 {_rgba(color, 22)}, stop:0.30 rgba(255,255,255,9),"
            f" stop:1 rgba(255,255,255,5));"
            f" border: 1px solid {EDGE}; border-radius: 18px; }}"
            "QFrame#ParamCard QLabel { background: transparent; border: none; }")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 11)
        lay.setSpacing(7)
        # خطِ نورِ هویت: باریک، محو در دو سر
        strip = QFrame()
        strip.setObjectName("CardStrip")
        strip.setFixedHeight(3)
        strip.setStyleSheet(
            "QFrame#CardStrip { border: none; background:"
            f" qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {_rgba(color, 0)},"
            f" stop:0.5 {_rgba(color, 210)}, stop:1 {_rgba(color, 0)}); }}")
        lay.addWidget(strip)
        head = QHBoxLayout()
        dot = QFrame()
        dot.setObjectName("CardDot")
        dot.setFixedSize(8, 8)
        dot.setStyleSheet(
            f"QFrame#CardDot {{ background: {color}; border: none;"
            f" border-radius: 4px; }}")
        t = QLabel(title)
        t.setStyleSheet(f"color: {color}; font-size: 13.5px; font-weight: bold;"
                        " background: transparent; border: none;")
        head.addWidget(dot)
        head.addWidget(t)
        head.addStretch(1)
        lay.addLayout(head)
        self.body = QVBoxLayout()
        self.body.setSpacing(6)
        lay.addLayout(self.body)

    def add_row(self, label_text: str, field: QWidget, tooltip: str = ""):
        row = QHBoxLayout()
        row.setSpacing(6)
        lab = QLabel(label_text)
        lab.setStyleSheet(f"color: {THEME['sub']}; background: transparent;"
                          " border: none; font-size: 12.5px;")
        lab.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        if tooltip:
            lab.setToolTip(tooltip)
        row.addWidget(lab)
        row.addStretch(1)
        row.addWidget(field)
        self.body.addLayout(row)


# ---------------------------------------------------------------------------
class StatChip(QFrame):
    """چیپ آماری شیشه‌ای: عنوان کم‌رنگ + مقدار رنگی + زیرخط نور."""

    def __init__(self, caption: str, color: str):
        super().__init__()
        self.setObjectName("StatChip")
        self.setStyleSheet(
            f"QFrame#StatChip {{ background: {_glass(10, 4)};"
            f" border: 1px solid {EDGE}; border-radius: 14px;"
            f" border-bottom: 2px solid {_rgba(color, 110)}; }}"
            "QFrame#StatChip QLabel { background: transparent; border: none; }")
        self.setFixedHeight(66)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(2)
        cap = QLabel(caption)
        cap.setStyleSheet(f"color: {THEME['sub']}; font-size: 11.5px;"
                          " background: transparent; border: none;")
        cap.setAlignment(Qt.AlignCenter)
        self.value = QLabel("--")
        self.value.setStyleSheet(f"color: {color}; font-size: 15px;"
                                 " font-weight: bold; background: transparent;"
                                 " border: none;")
        self.value.setAlignment(Qt.AlignCenter)
        lay.addWidget(cap)
        lay.addWidget(self.value)


# ---------------------------------------------------------------------------
class DesignerWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("طراح راکت -- استودیو طراحی پایداری")
        self.setLayoutDirection(Qt.RightToLeft)
        self.resize(1560, 980)
        self.setObjectName("DesignerRoot")
        self.setFont(QFont(FONT_FAMILY, 10))
        self.setStyleSheet(
            "QWidget#DesignerRoot { background: qradialgradient(cx:0.78,"
            " cy:0.08, radius:1.15, stop:0 #17224a, stop:0.45 #0c1226,"
            " stop:1 #070b18); }" + DESIGNER_QSS)
        # پالتِ دارک برای اجزایی که نقاشیِ سبک (Fusion) دارند (پیکان‌ها و…)
        pal = self.palette()
        pal.setColor(QPalette.Window, QColor("#0c1226"))
        pal.setColor(QPalette.Base, QColor("#0a0f1e"))
        pal.setColor(QPalette.Button, QColor("#16203c"))
        pal.setColor(QPalette.ButtonText, QColor("#9fb0dd"))
        pal.setColor(QPalette.Text, QColor(THEME["text"]))
        pal.setColor(QPalette.WindowText, QColor(THEME["text"]))
        pal.setColor(QPalette.Highlight, QColor(THEME["teal"]))
        pal.setColor(QPalette.HighlightedText, QColor("#06251f"))
        self.setPalette(pal)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(14)

        # ================= هدر =================
        header = QFrame()
        header.setObjectName("HeaderBar")
        header.setStyleSheet(
            f"QFrame#HeaderBar {{ background: {_glass(12, 4)};"
            f" border: 1px solid {EDGE}; border-radius: 18px; }}"
            "QFrame#HeaderBar QLabel { background: transparent; border: none; }")
        hl = QHBoxLayout(header)
        hl.setContentsMargins(18, 12, 18, 12)
        hl.setSpacing(14)
        logo = LogoBadge()
        title_box = QVBoxLayout()
        title_box.setSpacing(0)
        t1 = QLabel("طراح راکت")
        t1.setStyleSheet(f"color: {THEME['text']}; font-size: 19px;"
                         " font-weight: 900; background: transparent;"
                         " border: none;")
        t2 = QLabel("استودیو طراحی پارامتری و پایداری")
        t2.setStyleSheet(f"color: {THEME['sub']}; font-size: 11.5px;"
                         " background: transparent; border: none;")
        title_box.addWidget(t1)
        title_box.addWidget(t2)
        hl.addWidget(logo)
        hl.addLayout(title_box)
        hl.addSpacing(26)
        # سربرگِ تب‌ها داخل همان باکس بالایی (بدون باکس تودرتو)
        self.tab_group = QButtonGroup(self)
        self.tab_group.setExclusive(True)
        self.tab_stack = QStackedWidget()
        for i, (name, col) in enumerate((("نقشه و تحلیل", THEME["teal"]),
                                         ("راهنمای CG و ساخت", THEME["blue"]))):
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(_tab_qss(col))
            self.tab_group.addButton(btn, i)
            hl.addWidget(btn)
        self.tab_group.button(0).setChecked(True)
        self.tab_group.idClicked.connect(self.tab_stack.setCurrentIndex)
        hl.addStretch(1)
        self.lbl_verdict = QLabel("در انتظار ورود جرم‌ها")
        self.lbl_verdict.setObjectName("VerdictBadge")
        self.lbl_verdict.setAlignment(Qt.AlignCenter)
        self.lbl_verdict.setStyleSheet(_verdict_qss(THEME["sub"]))
        hl.addWidget(self.lbl_verdict)
        self.btn_save = QPushButton("ذخیرهٔ طرح")
        self.btn_open = QPushButton("بازکردن طرح")
        self.btn_transfer = QPushButton("ارسال به ایستگاه")
        self.btn_save.setObjectName("ActionBtn")
        self.btn_open.setObjectName("GhostBtn")
        self.btn_transfer.setObjectName("ActionBtn")
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_open.setCursor(Qt.PointingHandCursor)
        self.btn_transfer.setCursor(Qt.PointingHandCursor)
        self.btn_save.clicked.connect(self.save_json)
        self.btn_open.clicked.connect(self.open_json)
        self.btn_transfer.clicked.connect(self.transfer_to_station)
        self.btn_transfer.setToolTip(
            "تمام هندسه، جرم‌ها، نقاط CG/CP و مشخصات نازل را به ایستگاه بفرست "
            "و برای استفاده در پایش و پیش‌بینی آماده کن.")
        hl.addWidget(self.btn_save)
        hl.addWidget(self.btn_open)
        hl.addWidget(self.btn_transfer)
        root.addWidget(header)

        # ================= بدنه: پنل راست + محتوا =================
        body = QHBoxLayout()
        body.setSpacing(14)
        root.addLayout(body, 1)

        # ---- پنل پارامترها (راست) ----
        panel_scroll = QScrollArea()
        panel_scroll.setWidgetResizable(True)
        panel_scroll.setFixedWidth(340)
        panel = QWidget()
        pv = QVBoxLayout(panel)
        pv.setContentsMargins(2, 2, 6, 2)
        pv.setSpacing(10)

        # کارت بدنه و مخروط سر (فیروزه‌ای)
        card1 = ParamCard("بدنه و مخروط سر", THEME["teal"])
        self.sp_diameter = _spin(20, 300, 80)
        self.sp_body_len = _spin(10, 300, 60)
        self.cmb_shape = SoftComboBox()
        self.cmb_shape.addItems(["اویو", "مخروطی", "نیم‌کره", "تخت"])
        _dark_popup(self.cmb_shape)
        self.sp_nose_len = _spin(2, 60, 12, step=1)
        self.sp_nose_mass = _spin(0, 2000, 150)
        card1.add_row("قطر بدنه (mm)", self.sp_diameter)
        card1.add_row("طول بدنه (cm)", self.sp_body_len)
        card1.add_row("شکل مخروط سر", self.cmb_shape)
        card1.add_row("طول مخروط (cm)", self.sp_nose_len)
        card1.add_row("جرم مخروط (g)", self.sp_nose_mass)
        pv.addWidget(card1)

        # کارت باله‌ها (بنفش)
        card2 = ParamCard("باله‌ها", THEME["purple"])
        self.cmb_fin_n = SoftComboBox()
        self.cmb_fin_n.addItems(["3", "4", "6"])
        _dark_popup(self.cmb_fin_n)
        self.cmb_fin_shape = SoftComboBox()
        self.cmb_fin_shape.addItems(["ذوزنقه‌ای", "مثلثی", "مستطیلی"])
        _dark_popup(self.cmb_fin_shape)
        self.sp_root = _spin(20, 400, 100)
        self.sp_tip = _spin(0, 400, 60)
        self.sp_span = _spin(10, 300, 90)
        self.sp_sweep = _spin(0, 300, 20)
        self.sp_fin_mass = _spin(0, 300, 8, step=1)
        card2.add_row("تعداد باله", self.cmb_fin_n)
        card2.add_row("شکل باله", self.cmb_fin_shape)
        card2.add_row("وتر ریشه (mm)", self.sp_root)
        card2.add_row("وتر نوک (mm)", self.sp_tip)
        card2.add_row("دهانه -- بیرون‌زدگی (mm)", self.sp_span)
        card2.add_row("عقب‌رفتگی لبهٔ حمله (mm)", self.sp_sweep)
        card2.add_row("جرم هر باله (g)", self.sp_fin_mass)
        pv.addWidget(card2)

        # کارت جرم‌ها (نارنجی)
        card3 = ParamCard("جرم‌ها (برای CG)", THEME["orange"])
        self.sp_body_mass = _spin(0, 5000, 120)
        self.sp_body_pos = _spin(5, 290, 36, step=1)
        self.sp_engine_mass = _spin(0, 5000, 350)
        self.sp_engine_pos = _spin(0, 60, 4, step=1)
        self.sp_propellant_mass = _spin(0, 5000, 100)
        self.sp_chute_mass = _spin(0, 2000, 60)
        self.sp_chute_diameter = _spin(0, 800, 120)
        self.sp_chute_pos = _spin(5, 290, 20, step=1)
        card3.add_row("جرم بدنه/ساختار (g)", self.sp_body_mass)
        card3.add_row("موضع مرکز بدنه (cm از نوک)", self.sp_body_pos)
        card3.add_row("موتور + سوخت (g)", self.sp_engine_mass)
        card3.add_row("جرم سوخت (g)", self.sp_propellant_mass)
        card3.add_row("موضع مرکز موتور (cm از انتها)", self.sp_engine_pos)
        card3.add_row("چتر + آواتار (g)", self.sp_chute_mass)
        card3.add_row("قطر چتر (cm)", self.sp_chute_diameter)
        card3.add_row("موضع چتر (cm از نوک)", self.sp_chute_pos)
        pv.addWidget(card3)

        # کارت اندازه‌گیری (آبی)
        card4 = ParamCard("اندازه‌گیری CG", THEME["blue"])
        self.chk_meas = QCheckBox("CG اندازه‌گیری‌شده دارم")
        self.chk_meas.setToolTip("نتیجهٔ آزمون موازنه/رشته (تب راهنما) را جایگزین محاسبهٔ جرمی کن")
        self.sp_meas = SoftDoubleSpinBox()
        self.sp_meas.setRange(2, 300)
        self.sp_meas.setValue(40)
        self.sp_meas.setDecimals(1)
        self.sp_meas.setAlignment(Qt.AlignCenter)
        self.sp_meas.setEnabled(False)
        self.chk_meas.toggled.connect(self.sp_meas.setEnabled)
        card4.body.addWidget(self.chk_meas)
        card4.add_row("فاصلهٔ CG از نوک (cm)", self.sp_meas)
        pv.addWidget(card4)

        # کارت نازل: اختیاری است، اما اگر در طراحی پر شده باشد همراه هندسه و
        # جرم‌ها به ایستگاه می‌رود و دیگر لازم نیست همان اعداد دوباره تایپ شوند.
        card5 = ParamCard("موتور و نازل (برای انتقال)", THEME["yellow"])
        self.sp_throat = _spin(0, 500, 8)
        self.sp_exit = _spin(0, 1000, 20)
        self.sp_conv_angle = _spin(0, 90, 45)
        self.sp_div_angle = _spin(0, 90, 15)
        self.sp_nozzle_len = _spin(0, 100, 3, step=1)
        self.sp_chamber_p = _spin(1, 300, 40)
        card5.add_row("قطر گلوگاه (mm)", self.sp_throat)
        card5.add_row("قطر خروجی (mm)", self.sp_exit)
        card5.add_row("زاویه همگرا (درجه)", self.sp_conv_angle)
        card5.add_row("زاویه واگرا (درجه)", self.sp_div_angle)
        card5.add_row("طول نازل (cm)", self.sp_nozzle_len)
        card5.add_row("فشار محفظه (bar)", self.sp_chamber_p)
        pv.addWidget(card5)
        pv.addStretch(1)
        panel_scroll.setWidget(panel)
        body.addWidget(panel_scroll)

        # ---- محتوا: تب‌ها + صفحات ----
        content = QVBoxLayout()
        content.setSpacing(12)
        body.addLayout(content, 1)


        # --- صفحهٔ ۰: بوم + گیج + چیپ‌ها + پیشنهاد ---
        page0 = QWidget()
        p0 = QVBoxLayout(page0)
        p0.setContentsMargins(0, 0, 0, 0)
        p0.setSpacing(12)
        self.blueprint = Blueprint()
        self.blueprint.setFixedHeight(430)   # کاملاً قفل: با تغییر اعداد تکان نمی‌خورد
        p0.addWidget(self.blueprint)
        self.gauge = MarginGauge()
        self.gauge.setFixedHeight(84)
        p0.addWidget(self.gauge)
        chips = QHBoxLayout()
        chips.setSpacing(12)
        self.tbl = {}
        for key, cap, col in (("cp", "CP از نوک", THEME["blue"]),
                              ("cg", "CG از نوک", THEME["yellow"]),
                              ("dist", "فاصله CP تا CG", THEME["green"]),
                              ("cn", "CNα (1/rad)", THEME["pink"]),
                              ("mass", "جرم کل", THEME["orange"])):
            chip = StatChip(cap, col)
            self.tbl[key] = chip.value
            chips.addWidget(chip, 1)
        p0.addLayout(chips)
        self.lbl_advice = QLabel("...")
        self.lbl_advice.setObjectName("AdviceCard")
        self.lbl_advice.setWordWrap(True)
        self.lbl_advice.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.lbl_advice.setFixedHeight(96)
        self.lbl_advice.setAlignment(Qt.AlignRight | Qt.AlignTop)
        self.lbl_advice.setStyleSheet(_advice_qss(THEME["neon_jade"]))
        p0.addWidget(self.lbl_advice)
        p0.addStretch(1)

        guide_wrap = QScrollArea()
        guide_wrap.setWidgetResizable(True)
        guide_wrap.setWidget(build_guide_page())
        self.tab_stack.addWidget(page0)
        self.tab_stack.addWidget(guide_wrap)
        content.addWidget(self.tab_stack, 1)

        # ================= اتصال زندهٔ فیلدها =================
        self._live = [
            (self.sp_diameter, "sp_diameter"), (self.sp_body_len, "sp_body_len"),
            (self.cmb_shape, "cmb_shape"), (self.sp_nose_len, "sp_nose_len"),
            (self.sp_nose_mass, "sp_nose_mass"), (self.cmb_fin_n, "cmb_fin_n"),
            (self.cmb_fin_shape, "cmb_fin_shape"), (self.sp_root, "sp_root"), (self.sp_tip, "sp_tip"),
            (self.sp_span, "sp_span"), (self.sp_sweep, "sp_sweep"),
            (self.sp_fin_mass, "sp_fin_mass"), (self.sp_body_mass, "sp_body_mass"),
            (self.sp_body_pos, "sp_body_pos"), (self.sp_engine_mass, "sp_engine_mass"),
            (self.sp_propellant_mass, "sp_propellant_mass"),
            (self.sp_engine_pos, "sp_engine_pos"), (self.sp_chute_mass, "sp_chute_mass"),
            (self.sp_chute_diameter, "sp_chute_diameter"),
            (self.sp_chute_pos, "sp_chute_pos"), (self.sp_meas, "chk_meas"),
            (self.sp_throat, "sp_throat"), (self.sp_exit, "sp_exit"),
            (self.sp_conv_angle, "sp_conv_angle"), (self.sp_div_angle, "sp_div_angle"),
            (self.sp_nozzle_len, "sp_nozzle_len"), (self.sp_chamber_p, "sp_chamber_p"),
        ]
        for field, key in self._live:
            if isinstance(field, QComboBox):
                field.currentIndexChanged.connect(
                    lambda _i, k=key: self._on_live_change(k))
            else:
                field.valueChanged.connect(lambda _v, k=key: self._on_live_change(k))
        self.chk_meas.toggled.connect(lambda _on: self._on_live_change("chk_meas"))

        self.recompute()

    # ------------------------------------------------------------------
    def _on_live_change(self, key: str):
        """هر تغییر فیلد: بازمحاسبهٔ فوری + پالس نورِ نرم روی بوم."""
        self.recompute()
        self.blueprint.highlight(key)

    def geometry_inputs(self) -> RocketGeometry:
        fin_shape = self.cmb_fin_shape.currentText()
        fin_tip = self.sp_tip.value()
        if fin_shape == "مثلثی":
            fin_tip = 0.0
        elif fin_shape == "مستطیلی":
            fin_tip = self.sp_root.value()
        return RocketGeometry(
            body_diameter_mm=self.sp_diameter.value(),
            body_length_mm=self.sp_body_len.value() * 10.0,
            nose_length_mm=self.sp_nose_len.value() * 10.0,
            nose_shape=self.cmb_shape.currentText(),
            fin_count=int(self.cmb_fin_n.currentText()),
            fin_root_chord_mm=self.sp_root.value(),
            fin_tip_chord_mm=fin_tip,
            fin_span_mm=self.sp_span.value(),
            fin_sweep_mm=self.sp_sweep.value(),
        )

    def _mass_items(self, geo: RocketGeometry):
        total = geo.total_length_mm
        items = [
            MassItem("مخروط سر", self.sp_nose_mass.value(), nose_cg_mm(geo)),
            MassItem("بدنه", self.sp_body_mass.value(), self.sp_body_pos.value() * 10.0),
            MassItem("موتور", self.sp_engine_mass.value(),
                     max(total - self.sp_engine_pos.value() * 10.0, 0.0)),
            MassItem("چتر", self.sp_chute_mass.value(), self.sp_chute_pos.value() * 10.0),
        ]
        fm = self.sp_fin_mass.value()
        if fm > 0:
            items.append(MassItem("باله‌ها", geo.fin_count * fm, fin_set_cg_mm(geo)))
        return items

    # ------------------------------------------------------------------
    def recompute(self):
        geo = self.geometry_inputs()
        items = self._mass_items(geo)
        m_tot = sum(i.mass_g for i in items)

        cg = self.sp_meas.value() * 10.0 if self.chk_meas.isChecked() else None
        if cg is None:
            cg = center_of_gravity_mm(items)
        res = analyze(geo, cg)
        self.blueprint.set_data(geo, res, self.chk_meas.isChecked())

        color, verdict_txt = C_VERDICT[res.verdict]
        self.lbl_verdict.setStyleSheet(_verdict_qss(color))
        if res.verdict == "unknown":
            self.lbl_verdict.setText(verdict_txt)
        else:
            self.lbl_verdict.setText(
                f"حاشیهٔ پایداری {num(res.margin_calibers, 'کالیبر', 2)} -- {verdict_txt}")

        self.gauge.set_margin(
            res.margin_calibers, verdict_color(res.verdict),
            fa(f"{res.margin_calibers:.2f}"))

        d = geo.body_diameter_mm
        self.tbl["cp"].setText(num(res.x_cp_mm / 10.0, "cm"))
        self.tbl["cg"].setText(num(res.x_cg_mm / 10.0, "cm") if res.x_cg_mm else "--")
        self.tbl["dist"].setText(num((res.x_cp_mm - res.x_cg_mm) / d if res.x_cg_mm else 0,
                                     "کالیبر", 2))
        self.tbl["cn"].setText(num(res.cn_total, "", 1))
        self.tbl["mass"].setText(num(m_tot, "g", 0))

        from dataclasses import replace as _repl
        lines = []
        if res.verdict in ("unstable", "danger", "warn"):
            span = suggest_fin_span_mm(geo, res.x_cg_mm)
            if span is not None:
                lines.append(
                    f"دهانهٔ باله را از {num(self.sp_span.value(), 'mm', 0)} به "
                    f"{num(span, 'mm', 0)} ببرید تا حاشیه به ۱٫۵ کالیبر برسد "
                    "(وترها ثابت می‌مانند).")
            mn = suggest_nose_mass_g(geo, res.x_cg_mm, m_tot)
            if mn is not None:
                lines.append(
                    f"جایگزین/مکمل: حدود {num(mn, 'g', 0)} جرم به نوک دماغه "
                    "اضافه کنید (گلولهٔ فلزی با خمیر اپوکسی).")
            if not lines:
                lines.append("با جرم‌های فعلی، اصلاح با باله/دماغه به تنهایی کافی نیست؛ "
                             "جرم‌های عقب را کم یا دماغه را بلندتر کنید.")
        elif res.verdict == "over":
            base = _repl(geo, fin_span_mm=max(10.0, geo.fin_span_mm * 0.2))
            span = suggest_fin_span_mm(base, res.x_cg_mm, target=2.0)
            if span is not None:
                lines.append(
                    f"دهانهٔ باله را به {num(span, 'mm', 0)} کم کنید تا حاشیه "
                    "حدود ۲ کالیبر شود و هواروک در باد کمتر شود.")
            else:
                lines.append("باله‌ها را کوچک‌تر یا دماغه را سبک‌تر کنید.")
        else:
            lines.append("طراحی در بازهٔ ایمن است؛ برای پرواز آماده است.")
            if MARGIN_MIN <= res.margin_calibers < 1.2:
                lines.append("حاشیه نزدیک مرز پایین است؛ در باد زیاد پرواز نکنید.")
        lines.append("CG را با آزمون موازنه (تب راهنما) تأیید کنید.")
        # متن ساده + جهت RTL صریح: راست‌چینی در همهٔ نسخه‌های Qt قطعی است
        self.lbl_advice.setTextFormat(Qt.PlainText)
        self.lbl_advice.setLayoutDirection(Qt.RightToLeft)
        self.lbl_advice.setText("\n".join(lines))
        self.lbl_advice.setStyleSheet(_advice_qss(verdict_color(res.verdict)))

    # ------------------------------------------------------------------
    _FIELDS = ["sp_diameter", "sp_body_len", "sp_nose_len", "sp_nose_mass",
               "sp_root", "sp_tip", "sp_span", "sp_sweep", "sp_fin_mass",
               "sp_body_mass", "sp_body_pos", "sp_engine_mass", "sp_propellant_mass",
               "sp_engine_pos", "sp_chute_mass", "sp_chute_diameter", "sp_chute_pos",
               "sp_throat", "sp_exit",
               "sp_conv_angle", "sp_div_angle", "sp_nozzle_len", "sp_chamber_p"]

    def export_design_payload(self) -> dict:
        """ساخت قرارداد کامل انتقال به ایستگاه.

        علاوه بر مقادیر خام، خروجی بارومانِ همان لحظه هم ذخیره می‌شود تا
        ایستگاه دقیقاً همان CP/CG و حاشیه‌ای را ببیند که کاربر روی بوم دیده
        است؛ ایستگاه برای اجرای پیش‌بینی از همین داده‌ها و هندسهٔ باله‌ها
        استفاده می‌کند، نه از یک فرم ناقصِ جداگانه.
        """
        geo = self.geometry_inputs()
        items = self._mass_items(geo)
        cg_mm = self.sp_meas.value() * 10.0 if self.chk_meas.isChecked() else center_of_gravity_mm(items)
        res = analyze(geo, cg_mm)
        total_g = sum(item.mass_g for item in items)
        engine_g = self.sp_engine_mass.value()
        propellant_g = min(max(self.sp_propellant_mass.value(), 0.0), max(engine_g, 0.0))
        return {
            "schema_version": 1,
            "mode": "designer",
            "units": {"length": "mm", "mass": "g", "pressure": "bar"},
            "geometry": {
                "body_diameter_mm": geo.body_diameter_mm,
                "body_length_mm": geo.body_length_mm,
                "nose_length_mm": geo.nose_length_mm,
                "total_length_mm": geo.total_length_mm,
                "nose_shape": geo.nose_shape,
                "fins": {
                    "shape": self.cmb_fin_shape.currentText(),
                    "count": geo.fin_count,
                    "root_chord_mm": geo.fin_root_chord_mm,
                    "tip_chord_mm": geo.fin_tip_chord_mm,
                    "span_mm": geo.fin_span_mm,
                    "sweep_mm": geo.fin_sweep_mm,
                },
            },
            "mass": {
                "total_g": total_g,
                "body_g": self.sp_body_mass.value(),
                "engine_g": engine_g,
                "propellant_g": propellant_g,
                "nose_g": self.sp_nose_mass.value(),
                "chute_g": self.sp_chute_mass.value(),
                "chute_diameter_m": self.sp_chute_diameter.value() / 100.0,
                "fin_each_g": self.sp_fin_mass.value(),
                "items": [
                    {"name": item.name, "mass_g": item.mass_g,
                     "x_from_nose_mm": item.x_from_nose_mm}
                    for item in items
                ],
            },
            "stability": {
                "cg_from_nose_mm": res.x_cg_mm,
                "cp_from_nose_mm": res.x_cp_mm,
                "margin_calibers": res.margin_calibers,
                "cn_total": res.cn_total,
                "cn_nose": res.cn_nose,
                "cn_fins": res.cn_fins,
                "verdict": res.verdict,
                "measured_cg": self.chk_meas.isChecked(),
            },
            "nozzle": {
                "throat_diameter_mm": self.sp_throat.value(),
                "exit_diameter_mm": self.sp_exit.value(),
                "convergent_angle_deg": self.sp_conv_angle.value(),
                "divergent_angle_deg": self.sp_div_angle.value(),
                "length_cm": self.sp_nozzle_len.value(),
                "chamber_pressure_bar": self.sp_chamber_p.value(),
            },
        }

    def transfer_to_station(self):
        """ارسال اتمی طرح به ایستگاه و بازگشت از پنجرهٔ طراح."""
        try:
            path = write_design_transfer(self.export_design_payload())
        except (OSError, TypeError, ValueError) as exc:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "انتقال طرح", f"طرح به ایستگاه ارسال نشد:\n{exc}")
            return False
        self.btn_transfer.setText("✅ طرح به ایستگاه رسید")
        self.btn_transfer.setEnabled(False)
        # فایل در صورت بسته‌بودن ایستگاه هم باقی می‌ماند؛ در اجرای عادی،
        # تایمر ایستگاه در همین فاصله آن را می‌خواند و پنجرهٔ فعلی بسته می‌شود.
        QTimer.singleShot(450, self.close)
        return path

    def save_json(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "ذخیرهٔ طرح", "rocket_design.json", "JSON (*.json)")
        if not path:
            return
        data = {"shape": self.cmb_shape.currentText(),
                "fin_count": self.cmb_fin_n.currentText(),
                "fin_shape": self.cmb_fin_shape.currentText(),
                "measured": self.chk_meas.isChecked(),
                "meas_cg": self.sp_meas.value()}
        for f in self._FIELDS:
            data[f] = getattr(self, f).value()
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2)
        except OSError as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "خطا", f"ذخیره نشد: {e}")

    def open_json(self):
        path, _ = QFileDialog.getOpenFileName(self, "بازکردن طرح", "", "JSON (*.json)")
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError) as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "خطا", f"فایل خوانده نشد: {e}")
            return
        self.cmb_shape.setCurrentText(data.get("shape", "اویو"))
        self.cmb_fin_n.setCurrentText(str(data.get("fin_count", "4")))
        self.cmb_fin_shape.setCurrentText(data.get("fin_shape", "ذوزنقه‌ای"))
        self.chk_meas.setChecked(bool(data.get("measured", False)))
        self.sp_meas.setValue(float(data.get("meas_cg", 40)))
        for f in self._FIELDS:
            if f in data:
                getattr(self, f).setValue(data[f])
        self.recompute()
