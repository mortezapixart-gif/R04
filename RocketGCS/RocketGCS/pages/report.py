# -*- coding: utf-8 -*-
"""صفحهٔ گزارش نهایی (PDF / اکسل)"""
import os

# ابزارهای فارسی (شکل‌دهی متن، تاریخ شمسی، قالب اعداد، دیکشنری اصطلاحات) در
# core/report_text.py هستند تا موتورِ گزارش (core/hud_report.py و
# core/excel_export.py) بدون Qt قابل استفاده باشد.
from core.report_text import to_jalali_date, format_metric_value, fa_text_selftest, TERM_TRANSLATIONS, protect_latin_quantities

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                                QTextEdit, QListWidget, QListWidgetItem,
                                QMessageBox)
from PySide6.QtCore import Qt
from ui.widgets import make_card
from core.data_manager import data_manager


class ReportPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setLayoutDirection(Qt.RightToLeft)
        root = QVBoxLayout(self)

        self.preview = QTextEdit()
        self.preview.setObjectName("ReportPreview")   # بدون زمینه/قاب -- روی کارت اصلی
        self.preview.setReadOnly(True)
        self.preview.setLayoutDirection(Qt.RightToLeft)
        root.addWidget(make_card(self.preview))

        btn_row = QHBoxLayout()
        gen_btn = QPushButton("تولید گزارش رنگی")
        gen_btn.setProperty("class", "Primary")
        gen_btn.clicked.connect(self.generate_pdf)
        gen_btn_bw = QPushButton("تولید گزارش سیاه‌وسفید")
        gen_btn_bw.setProperty("class", "Secondary")
        gen_btn_bw.clicked.connect(self.generate_pdf_bw)
        excel_btn = QPushButton("تولید گزارش در اکسل")
        excel_btn.setProperty("class", "Primary")
        excel_btn.clicked.connect(self.generate_excel)
        open_folder_btn = QPushButton("باز کردن پوشهٔ گزارش‌ها")
        open_folder_btn.setProperty("class", "Secondary")
        open_folder_btn.clicked.connect(self.open_reports_folder)

        for b in (gen_btn, gen_btn_bw, excel_btn, open_folder_btn):
            b.setMinimumWidth(190)
            b.setMinimumHeight(38)

        btn_row.addStretch()
        btn_row.addWidget(gen_btn)
        btn_row.addWidget(gen_btn_bw)
        btn_row.addWidget(excel_btn)
        btn_row.addWidget(open_folder_btn)
        btn_row.addStretch()
        root.addLayout(btn_row)

        self.archive_list = QListWidget()
        self.archive_list.setLayoutDirection(Qt.RightToLeft)
        self.archive_list.setMinimumHeight(140)
        self.archive_list.itemDoubleClicked.connect(self.open_selected_archive)
        root.addWidget(make_card(self.archive_list))

        open_row = QHBoxLayout()
        open_archive_btn = QPushButton("فعال کردن پرواز انتخاب‌شده")
        open_archive_btn.setProperty("class", "Primary")
        open_archive_btn.clicked.connect(self.open_selected_archive)
        refresh_archive_btn = QPushButton("بازخوانی لیست")
        refresh_archive_btn.setProperty("class", "Secondary")
        refresh_archive_btn.clicked.connect(self.refresh_archive_list)
        open_raw_folder_btn = QPushButton("باز کردن پوشهٔ گزارش‌های خام")
        open_raw_folder_btn.setProperty("class", "Secondary")
        open_raw_folder_btn.clicked.connect(self.open_raw_flights_folder)
        for b in (open_archive_btn, refresh_archive_btn, open_raw_folder_btn):
            b.setMinimumHeight(38)
        open_row.addStretch()
        open_row.addWidget(open_archive_btn)
        open_row.addWidget(refresh_archive_btn)
        open_row.addWidget(open_raw_folder_btn)
        open_row.addStretch()
        root.addLayout(open_row)

        data_manager.analysis_ready.connect(self._on_analysis_ready)
        self.update_preview(data_manager.analysis_results)
        self.refresh_archive_list()

    def update_preview(self, results: dict):
        m = data_manager.mission
        mo = data_manager.motor
        jalali_date_str = to_jalali_date(m.jalali_date or m.date)
        lines = [
            f"پروژه: {m.project_number or '--'}   |   نام راکت: {m.rocket_name or '--'}   |   شماره پرواز: {m.flight_number or '--'}",
            f"محل پرتاب: {m.launch_site or '--'}   |   تاریخ: {jalali_date_str}  ساعت: {m.time}",
            f"وزن کل: {m.total_mass} کیلوگرم   |   زاویه پرتاب: {m.launch_angle} درجه",
            f"هندسه: قطر {m.body_diameter * 1000:.0f} mm، طول {m.body_length * 100:.1f} cm، "
            f"باله {m.fin_shape} / {m.fin_count or 'پیش‌فرض'} عدد",
            f"پایداری: CP {m.cp_from_nose * 100:.1f} cm، CG {m.cg_from_nose * 100:.1f} cm، "
            f"حاشیه {m.stability_margin_calibers:.2f} کالیبر" if m.cp_from_nose and m.cg_from_nose else
            "پایداری: CP/CG نرمال خودکار در حالت ورود دستی",
            f"نازل: گلوگاه {mo.throat_diameter} mm، خروجی {mo.exit_diameter} mm، طول {mo.nozzle_length} cm",
            "",
            "========== نتایج تحلیل پرواز ==========",
        ]
        for k, v in (results or {}).items():
            if k == "events":
                continue
            fa_title = TERM_TRANSLATIONS.get(k, k)
            formatted_v = format_metric_value(k, v)
            lines.append(f"• {fa_title}: {formatted_v}")
        self.preview.setPlainText("\n".join(protect_latin_quantities(ln) for ln in lines))


    def open_reports_folder(self):
        from core.paths import get_reports_dir
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        folder = get_reports_dir()
        QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    def _auto_report_path(self, ext: str, suffix: str = "") -> str:
        """مسیر خودکار فایل خروجی داخل پوشهٔ «گزارش‌ها» با نام‌گذاری یکدست
        (تاریخ شمسی + شمارهٔ پرواز [+ پسوند])."""
        from core.paths import get_reports_dir, build_report_filename
        m = data_manager.mission
        jalali = to_jalali_date(m.jalali_date or m.date)
        filename = build_report_filename(jalali, m.flight_number, ext, suffix)
        return os.path.join(get_reports_dir(), filename)

    def _prediction_for_report(self):
        """اسنپ‌شات «پیش‌بینی لحظهٔ پرتاب» برای گزارش‌ها (PDF و اکسل).

        اگر اسنپ‌شات در حافظه نباشد (مثلاً برنامه بین پرواز و گزارش باز
        شده باشد)، همان محاسبه با پارامترهای ثبت‌شدهٔ مأموریت -- که منبعِ
        همان SET_MISSION موقع پرتاب بود -- بازسازی می‌شود تا بخش
        «پیش‌بینی در برابر واقعیت» هرگز از گزارش حذف نشود. نسخهٔ
        بازسازی‌شده با کلید fallback=True علامت می‌خورد تا در PDF به‌صورت
        پانوشت صادقانه توضیح داده شود."""
        return data_manager.prediction_snapshot_or_rebuild()

    def generate_pdf(self):
        self._generate_pdf_impl(bw=False)

    def generate_pdf_bw(self):
        self._generate_pdf_impl(bw=True)

    def _generate_pdf_impl(self, bw: bool):
        path = self._auto_report_path("pdf", suffix=("bw" if bw else ""))
        fa_ok, fa_detail = fa_text_selftest()
        if not fa_ok:
            QMessageBox.warning(
                self, "مشکل در شکل‌دهی متن فارسی",
                "متن فارسی داخل گزارش PDF درست نمایش داده نخواهد شد (حروف "
                "جدا از هم و برعکس -- مثلاً «گزارش» به‌صورت «ش ر ا ز گ»).\n\n"
                f"جزئیات فنی: {fa_detail}\n\n"
                "اگر از سورس اجرا می‌کنید:\n"
                "pip install -r requirements.txt\n\n"
                "اگر از نسخهٔ exe استفاده می‌کنید، این نسخه باید دوباره از "
                "روی سورس به‌روز build شود. گزارش همچنان تولید می‌شود ولی "
                "متن فارسی آن نادرست خواهد بود -- در خودِ فایل PDF هم یک "
                "هشدار قرار داده شده است."
            )
        try:
            from core.hud_report import generate_hud_pdf
            try:
                from core.advisor import generate_suggestions
                suggestions = generate_suggestions(data_manager.flight_df, data_manager.analysis_results,
                                                    data_manager.mission, data_manager.motor)
            except Exception:
                suggestions = []
            generate_hud_pdf(
                path,
                mission=data_manager.mission,
                motor=data_manager.motor,
                results=data_manager.analysis_results or {},
                flight_df=data_manager.flight_df,
                suggestions=suggestions,
                bw=bw,
                prediction=self._prediction_for_report(),
            )
            kind_label = "سیاه‌وسفید (کم‌مصرف جوهر)" if bw else "گرافیک HUD"
            self.preview.append(f"\nگزارش PDF نهایی ({kind_label}) با موفقیت ذخیره شد.")
            QMessageBox.information(self, "گزارش تولید شد",
                                     f"گزارش PDF ({kind_label}) با موفقیت تولید و ذخیره شد.")
        except Exception as e:
            self.preview.append(f"\nخطا در تولید PDF: {e}")
            QMessageBox.critical(self, "خطا در تولید گزارش", f"تولید گزارش PDF ناموفق بود:\n{e}")

    def generate_excel(self):
        path = self._auto_report_path("xlsx")
        try:
            from core.excel_export import export_excel
            summary = export_excel(path, prediction=self._prediction_for_report()) or {}
            sheets = summary.get("sheets") or []
            charts = summary.get("charts") or 0
            rows = summary.get("rows_raw") or 0
            notes = summary.get("notes") or []
            self.preview.append(
                f"\nخروجی Excel ذخیره شد.\n"
                f"  شیت‌ها: {len(sheets)}   |   نمودار: {charts}   |   ردیف دادهٔ خام: {rows}")
            for n in notes:
                self.preview.append(f"  ⚠ {n}")
            detail = f"{len(sheets)} شیت، {charts} نمودار و {rows} ردیف دادهٔ خام در آن ساخته شد."
            if notes:
                # یادداشت‌ها یعنی بخشی از گزارش ناقص بوده (مثلاً ستون رطوبت در
                # فایل CSV نیست) -- باید به چشم بیاید، نه این‌که بی‌صدا بماند.
                QMessageBox.warning(
                    self, "گزارش اکسل با نکته تولید شد",
                    "فایل ساخته شد ولی این نکته‌ها را بررسی کنید:\n\n"
                    + "\n".join(f"• {n}" for n in notes[:4]) + "\n\n" + detail)
            else:
                QMessageBox.information(self, "گزارش تولید شد",
                                        f"داشبورد اکسل با موفقیت تولید و ذخیره شد.\n\n{detail}")
        except Exception as e:
            self.preview.append(f"\nخطا در تولید Excel: {e}")
            QMessageBox.critical(self, "خطا در تولید گزارش", f"تولید خروجی اکسل ناموفق بود:\n{e}")

    def _on_analysis_ready(self, results):
        self.update_preview(results)
        self.refresh_archive_list()

    def refresh_archive_list(self):
        from core.raw_archive import format_list_label

        self.archive_list.clear()
        items = data_manager.list_archive()
        if not items:
            placeholder = QListWidgetItem("هنوز پرواز خامی در پوشه نیست. پس از تحلیل، اینجا ظاهر می‌شود.")
            placeholder.setFlags(Qt.NoItemFlags)
            self.archive_list.addItem(placeholder)
            return
        for item in items:
            list_item = QListWidgetItem(format_list_label(item))
            list_item.setData(Qt.UserRole, item.get("path") or item.get("name"))
            self.archive_list.addItem(list_item)

    def open_raw_flights_folder(self):
        from core.paths import get_raw_flights_dir
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        folder = get_raw_flights_dir()
        QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    def open_selected_archive(self):
        item = self.archive_list.currentItem()
        path = item.data(Qt.UserRole) if item else None
        if not path:
            QMessageBox.information(self, "پروازهای خام", "ابتدا یک پرواز را از لیست انتخاب کنید.")
            return
        if data_manager.load_from_archive(path):
            self.update_preview(data_manager.analysis_results)
            self.preview.append(f"\nپرواز خام فعال شد:\n{path}")
            QMessageBox.information(
                self, "پرواز فعال شد",
                "دادهٔ خام این پرواز بارگذاری شد و تحلیل دوباره اجرا گردید.\n"
                "نمودارها، شبیه‌ساز و گزارش‌ها از همین داده ساخته می‌شوند.")
        else:
            QMessageBox.critical(
                self, "خطا در باز کردن پرواز",
                f"نتوانستم این پرواز خام را باز کنم:\n{path}")
