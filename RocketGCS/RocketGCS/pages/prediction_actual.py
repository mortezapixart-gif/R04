# -*- coding: utf-8 -*-
"""تب «پیش‌بینی و واقعیت» -- جدول مقایسهٔ پیش‌بینی لحظهٔ پرتاب با دادهٔ واقعی
پرواز (همان جدول گزارش PDF) + خلاصهٔ نتیجه‌گیری‌های علت‌یاب.

منبع داده: اسنپ‌شاتِ ثبت‌شده در شروع شمارش معکوس (یا بازسازی‌شده با
پارامترهای مأموریت) و نتایج تحلیل پرواز. علت‌یابی کامل، بازه‌های محتمل و
روش محاسبه در گزارش اکسل (شیت «پیش‌بینی و واقعیت») آمده است -- اینجا فقط
خلاصه نمایش داده می‌شود."""
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLabel,
                               QTableWidget, QTableWidgetItem, QHeaderView,
                               QScrollArea)
from PySide6.QtCore import Qt

from ui.widgets import section_title, CompactStatCard
from core.data_manager import data_manager
from core.prediction_compare import compare_snapshot
from core.report_text import protect_latin_quantities

# رنگ ارزیابی هر سطر -- همان نقشهٔ رنگی گزارش PDF
_KIND_COLOR = {
    "ok": "#35d07f",      # داخل بازهٔ محتمل / نزدیک پیش‌بینی
    "minor": "#ffb020",   # انحراف متوسط
    "major": "#ef5350",   # انحراف زیاد / ایمنی
    "nodata": "#96a2b5",  # بدون داده
}
_SEVERITY_COLOR = {
    "danger": "#ef5350",
    "warn": "#ffb020",
    "info": "#8fb6d9",
}

_ROW_EVEN = "#1a2029"   # زبرای هم‌سبک شاخص‌های پرواز
_ROW_ODD = "#212a38"


class PredictionActualPage(QWidget):
    """تب دوم تحلیل پرواز: پیش‌بینی در برابر واقعیت + خلاصهٔ نتیجه‌گیری."""

    def __init__(self):
        super().__init__()
        self.setLayoutDirection(Qt.RightToLeft)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        inner = QWidget()
        root = QVBoxLayout(inner)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(10)
        scroll.setWidget(inner)
        outer.addWidget(scroll)

        root.addWidget(section_title("پیش‌بینی و واقعیت -- مقایسهٔ شبیه‌سازی لحظهٔ پرتاب با پرواز واقعی"))

        # خط وضعیت اسنپ‌شات (زمان ثبت / بازسازی‌شده)
        self.meta_lbl = QLabel("")
        self.meta_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.meta_lbl.setStyleSheet("color:#96a2b5; font-size:12px;")
        root.addWidget(self.meta_lbl)

        # ---- جدول مقایسه (همان جدول PDF) -- دو ستون کنار هم تا سطرها نصف شوند ----
        tables_row = QHBoxLayout()
        tables_row.setSpacing(10)
        self.table = self._make_table()
        self.table_b = self._make_table()
        tables_row.addWidget(self.table, stretch=1)
        tables_row.addWidget(self.table_b, stretch=1)
        root.addLayout(tables_row)

        # ---- کارت‌های خلاصه (بیشینهٔ انحراف‌ها) ----
        cards_row = QHBoxLayout()
        cards_row.setSpacing(10)
        self.card_apogee = CompactStatCard("اختلاف اوج", "--")
        self.card_vmax = CompactStatCard("اختلاف بیشینهٔ سرعت", "--")
        self.card_vland = CompactStatCard("اختلاف سرعت فرود", "--")
        for c in (self.card_apogee, self.card_vmax, self.card_vland):
            cards_row.addWidget(c, stretch=1)
        root.addLayout(cards_row)

        # ---- باکس نتیجه‌گیری‌ها ----
        self.concl_title = QLabel("نتیجه‌گیری")
        self.concl_title.setStyleSheet(
            "color:#e6ebf1; font-size:15px; font-weight:bold; padding:2px 4px;")
        root.addWidget(self.concl_title)

        self.concl_box = QVBoxLayout()
        self.concl_box.setSpacing(6)
        root.addLayout(self.concl_box)
        root.addStretch(1)

        # ارجاع به گزارش اکسل برای توضیحات تکمیلی
        note = QLabel(
            "توضیحات تکمیلی -- علت‌یابی کامل، بازهٔ محتمل هر کمیت (مونت‌کارلو) و روش "
            "محاسبه -- در گزارش اکسل، شیت «پیش‌بینی و واقعیت» آمده است.")
        note.setWordWrap(True)
        note.setStyleSheet("color:#66748a; font-size:12px; padding:4px 6px;")
        note.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        root.addWidget(note)

        self.refresh({})
        data_manager.analysis_ready.connect(self.refresh)

    # ------------------------------------------------------------------
    def refresh(self, results: dict):
        results = results or {}
        snap = data_manager.prediction_snapshot_or_rebuild()
        # پاک‌سازی باکس نتیجه‌گیری برای بازسازی
        while self.concl_box.count():
            item = self.concl_box.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        if snap is None:
            self.meta_lbl.setText("")
            self._set_table_rows([])
            self._set_cards({})
            self._add_conclusion("بدون پیش‌بینی",
                                 "اطلاعات مأموریت/نازل هنوز کامل نیست؛ پس از پر کردن آن‌ها "
                                 "پیش‌بینی لحظهٔ پرتاب ثبت می‌شود و اینجا نمایش داده می‌شود.",
                                 "info")
            return
        if snap.get("fallback"):
            self.meta_lbl.setText(
                "اسنپ‌شات لحظهٔ پرتاب در دسترس نبود؛ پیش‌بینی با پارامترهای ثبت‌شدهٔ "
                "مأموریت بازسازی شده است.")
        else:
            created = (snap.get("created_at") or "").strip()
            self.meta_lbl.setText(f"اسنپ‌شات لحظهٔ پرتاب{(' -- ' + created) if created else ''}")

        comp = compare_snapshot(snap, results)
        rows = [r for r in comp.get("rows", []) if r.get("actual") is not None]
        self._set_table_rows(rows)
        self._set_cards({r["key"]: r for r in rows})
        for cause in comp.get("causes", []):
            self._add_conclusion(str(cause.get("title", "")),
                                 str(cause.get("text", "")),
                                 str(cause.get("severity", "info")))
        if not comp.get("causes"):
            self._add_conclusion("بدون تحلیل",
                                 "دادهٔ کافی برای نتیجه‌گیری وجود ندارد.", "info")

    # ------------------------------------------------------------------
    def _make_table(self) -> QTableWidget:
        """جدول مقایسه با استایل واحد (دو نمونه کنار هم ساخته می‌شود)."""
        table = QTableWidget(0, 4)
        table.setHorizontalHeaderLabels(["کمیت", "پیش‌بینی", "واقعیت", "اختلاف"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionMode(QTableWidget.NoSelection)
        table.setFocusPolicy(Qt.NoFocus)
        table.setShowGrid(False)
        table.setAlternatingRowColors(False)
        header = table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        for c in (1, 2, 3):
            header.setSectionResizeMode(c, QHeaderView.ResizeToContents)
        table.setStyleSheet("""
            QTableWidget {
                background-color: transparent;
                alternate-background-color: transparent;
                border: 1px solid #2b3446;
                border-radius: 8px;
            }
            QHeaderView::section {
                background-color: #1f2735;
                color: #96a2b5;
                border: none;
                border-bottom: 1px solid #2b3446;
                padding: 5px 8px;
                font-weight: bold;
                font-size: 12.5px;
            }
        """)
        return table

    @staticmethod
    def _fmt(v, unit, dec):
        if v is None:
            return "--"
        return protect_latin_quantities(f"{v:.{dec}f} {unit}")

    def _set_table_rows(self, rows):
        # دوستونه: نیمهٔ اول کمیت‌ها در جدول راست، نیمهٔ دوم در جدول چپ --
        # ارتفاع کل تقریباً نصف می‌شود (درخواست کاربر: نصف‌کردن سطرها)
        half = (len(rows) + 1) // 2
        self._fill_table(self.table, rows[:half])
        self._fill_table(self.table_b, rows[half:])

    def _fill_table(self, table: QTableWidget, rows):
        table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            dec = 1 if r["key"] in ("gmax", "vland", "burn", "tapogee") else 0
            dev = r.get("dev_pct")
            if dev is None:
                dev_txt, kind = "--", "nodata"
            else:
                dev_txt = ("\u202a+" if dev > 0 else "\u202a\u2212") + f"{abs(dev):.0f}٪\u202c"
                kind = r.get("kind", "nodata")
            color = _KIND_COLOR.get(kind, "#96a2b5")
            vals = (str(r.get("label", "--")),
                    self._fmt(r.get("pred"), r.get("unit", ""), dec),
                    self._fmt(r.get("actual"), r.get("unit", ""), dec),
                    dev_txt)
            for col, v in enumerate(vals):
                it = QTableWidgetItem(v)
                it.setTextAlignment(Qt.AlignCenter)
                if col == 0:
                    it.setForeground(_qt_color("#e6ebf1"))
                else:
                    it.setForeground(_qt_color(color))
                # زمینهٔ زبرا
                bg = _ROW_EVEN if i % 2 == 0 else _ROW_ODD
                it.setBackground(_qt_color(bg))
                table.setItem(i, col, it)
            table.setRowHeight(i, 30)

    def _set_cards(self, by_key):
        for key, card in (("apogee", self.card_apogee),
                          ("vmax", self.card_vmax),
                          ("vland", self.card_vland)):
            r = by_key.get(key)
            if r is None or r.get("dev_pct") is None:
                card.set_value("--")
            else:
                dev = r["dev_pct"]
                sign = "\u202a+" if dev > 0 else "\u202a\u2212"
                card.set_value(f"{sign}{abs(dev):.0f}٪\u202c")
                card.set_status("ok" if r.get("kind") == "ok"
                                else ("warn" if r.get("kind") == "minor" else "error"))

    def _add_conclusion(self, title, text, severity):
        frame = QFrame()
        frame.setStyleSheet(
            f"QFrame {{ background-color: {_ROW_ODD}; border: 1px solid #2b3446;"
            f" border-radius: 8px; }}")
        frame.setLayoutDirection(Qt.RightToLeft)
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(3)
        col = _SEVERITY_COLOR.get(severity, "#8fb6d9")
        t = QLabel(title)
        t.setStyleSheet(f"color:{col}; font-size:13.5px; font-weight:bold; border:none;")
        t.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        b = QLabel(text)
        b.setWordWrap(True)
        b.setStyleSheet("color:#c7d1de; font-size:12.5px; border:none;")
        b.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lay.addWidget(t)
        lay.addWidget(b)
        self.concl_box.addWidget(frame)


def _qt_color(hex_str: str):
    from PySide6.QtGui import QColor
    return QColor(hex_str)
