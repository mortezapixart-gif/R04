# -*- coding: utf-8 -*-
"""
RocketDesigner/main.py
----------------------
نقطهٔ ورود مستقل برنامهٔ «طراح راکت» -- خواهرِ ایستگاه زمینی (RocketGCS).
فیزیک و **پوستهٔ بصری** هر دو از برنامهٔ اصلی می‌آید (core/ + ui/style) تا
ظاهر طراح -- فونت شبنم، کارت‌ها، فیلدها و دکمه‌ها -- کاملاً یکسان با
ایستگاه زمینی باشد.

اجرا:  python RocketDesigner/main.py   (یا run_designer.bat)
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "RocketGCS"))   # فیزیک + پوستهٔ مشترک
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # blueprint/window

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QPalette  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from ui.style import APP_FONT_FAMILY  # noqa: E402  (فونت مشترک: شبنم)
from window import DesignerWindow  # noqa: E402


def main() -> int:
    app = QApplication(sys.argv)
    app.setLayoutDirection(Qt.RightToLeft)
    # Fusion + شبنم؛ پوستهٔ شاد اختصاصی طراح در window.py اعمال می‌شود
    app.setStyle("Fusion")
    # فونت سراسری: سری شبنم
    font = QFont("Shabnam", 10)
    font.setStyleHint(QFont.SansSerif)
    app.setFont(font)
    # پالت سراسری تیره: هیچ سطح سفیدی (لیست کشویی، دیالوگ‌ها و…) دیده نشود
    pal = QPalette()
    pal.setColor(QPalette.Window, QColor("#0c1226"))
    pal.setColor(QPalette.Base, QColor("#10182e"))
    pal.setColor(QPalette.Button, QColor("#16203c"))
    pal.setColor(QPalette.ButtonText, QColor("#9fb0dd"))
    pal.setColor(QPalette.Text, QColor("#e8ecff"))
    pal.setColor(QPalette.WindowText, QColor("#e8ecff"))
    pal.setColor(QPalette.PlaceholderText, QColor("#93a0c4"))
    pal.setColor(QPalette.Highlight, QColor("#5eead4"))
    pal.setColor(QPalette.HighlightedText, QColor("#06251f"))
    pal.setColor(QPalette.ToolTipBase, QColor("#131c36"))
    pal.setColor(QPalette.ToolTipText, QColor("#e8ecff"))
    app.setPalette(pal)
    _ = APP_FONT_FAMILY  # پوستهٔ مشترک همچنان قابل استفاده است
    win = DesignerWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
