# -*- coding: utf-8 -*-
"""صفحهٔ ارتفاع، دما و رطوبت

نمودار ساده و خوانا از داده‌های سنسور دما و رطوبت طی پرواز، در برابر زمان:

    • ارتفاع (محور چپ)
    • دمای محیط (محور راست)
    • رطوبت نسبی (محور راست دوم)

نکته: دمای هر سه ماژول (BMP280، AHT21B و دمای داخلی MPU6050) همچنان در
خروجی اکسل «داده خام پرواز» کنار هم ثبت می‌شوند؛ این نمودار برای خوانایی
فقط دما و رطوبت را نمایش می‌دهد.
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QGridLayout, QLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from ui.style import APP_FONT_FAMILY
import numpy as np
import pyqtgraph as pg
from ui.widgets import CompactStatCard, section_title
from core import palette as colors
from core.data_manager import data_manager
from core.report_text import protect_latin_quantities

ISA_LAPSE_RATE_C_PER_KM = -6.5   # نرخ استاندارد افت دما با ارتفاع در تروپوسفر (ISA)


class AltitudeTemperaturePage(QWidget):
    def __init__(self):
        super().__init__()
        self.setLayoutDirection(Qt.RightToLeft)
        root = QVBoxLayout(self)

        note = QLabel(
            "دما و رطوبت محیط طی پرواز، در برابر ارتفاع و زمان."
        )
        note.setWordWrap(True)
        note.setAlignment(Qt.AlignCenter)
        root.addWidget(note)

        # ---------------- کارت‌های خلاصه: فقط سه باکس درخواستی ----------------
        grid = QGridLayout()
        self.card_temp_range = CompactStatCard("بازهٔ دما (سطح - اوج)", "--")
        self.card_humidity = CompactStatCard("بازهٔ رطوبت (سطح - اوج)", "--")
        self.card_lapse_rate = CompactStatCard("نرخ افت دما", "--", tooltip=(
            "نرخ افت دمای مشاهده‌شده با افزایش ارتفاع، محاسبه‌شده از دمای واقعی طی صعود "
            "(با رگرسیون خطی دما بر حسب ارتفاع). نرخ استاندارد جوّ (ISA) در تروپوسفر ۶.۵- درجه بر "
            "کیلومتر است؛ اختلاف زیاد از این عدد می‌تواند نشانهٔ خطای کالیبراسیون سنسور یا شرایط "
            "جوّی غیراستاندارد روز پرتاب باشد."
        ))
        cards = [self.card_temp_range, self.card_humidity, self.card_lapse_rate]
        cols = 3
        for i, c in enumerate(cards):
            grid.addWidget(c, i // cols, i % cols)
        for col in range(cols):
            grid.setColumnStretch(col, 1)
        root.addLayout(grid)

        root.addWidget(section_title("ارتفاع، دما و رطوبت بر حسب زمان (از لحظهٔ پرتاب)"))

        pg.setConfigOption("background", "#1a2029")
        pg.setConfigOption("foreground", "#e6ebf1")

        self.plot = pg.PlotWidget()
        self.plot_item = self.plot.plotItem
        self.plot.setLabel("bottom", protect_latin_quantities("زمان (s)"))
        self.plot.getAxis("left").setTextPen(colors.ALTITUDE)
        self.plot.setLabel("left", protect_latin_quantities("ارتفاع (m)"), color=colors.ALTITUDE)
        self.plot.showGrid(x=True, y=True, alpha=0.2)
        # خط صفر (خط‌چین) مثل بقیهٔ نمودارهای برنامه
        self.plot.addLine(y=0, pen=pg.mkPen("#5c6b80", width=1, style=Qt.DashLine))
        self.alt_curve = self.plot.plot(pen=pg.mkPen(colors.ALTITUDE, width=2), name="ارتفاع")

        # ---- محور دوم (سمت راست، ستون استاندارد): دما ----
        self.plot.showAxis("right")
        self.temp_axis = self.plot.getAxis("right")
        self.temp_axis.setTextPen(colors.TEMPERATURE)
        self.temp_axis.setLabel(protect_latin_quantities("دما (°C)"), color=colors.TEMPERATURE)
        self.temp_vb = pg.ViewBox()
        self.plot.scene().addItem(self.temp_vb)
        self.temp_axis.linkToView(self.temp_vb)
        self.temp_vb.setXLink(self.plot_item)
        self.temp_curve = pg.PlotCurveItem(pen=pg.mkPen(colors.TEMPERATURE, width=2))
        self.temp_vb.addItem(self.temp_curve)

        # ---- محور سوم: رطوبت نسبی ----
        self.hum_axis = pg.AxisItem("right")
        self.hum_axis.setTextPen(colors.HUMIDITY)
        self.hum_axis.setLabel(protect_latin_quantities("رطوبت (%RH)"), color=colors.HUMIDITY)
        self.plot_item.layout.addItem(self.hum_axis, 2, 3)
        self.hum_vb = pg.ViewBox()
        self.plot.scene().addItem(self.hum_vb)
        self.hum_axis.linkToView(self.hum_vb)
        self.hum_vb.setXLink(self.plot_item)
        self.hum_curve = pg.PlotCurveItem(pen=pg.mkPen(colors.HUMIDITY, width=2))
        self.hum_vb.addItem(self.hum_curve)

        self.plot_item.vb.sigResized.connect(self._sync_views)
        root.addWidget(self.plot, stretch=1)

        # ---- نشانگر تعاملی موس + فیلد کوچک گوشهٔ نمودار ----
        self.hover_line = pg.InfiniteLine(angle=90, pen=pg.mkPen("#7c8ba1", width=1, style=Qt.DashLine))
        self.hover_line.hide()
        self.plot.addItem(self.hover_line, ignoreBounds=True)
        self.readout = pg.TextItem(anchor=(1, 0), color="#e6ebf1", fill=(20, 26, 36, 220), border=pg.mkPen("#4fa3f7"))
        self.readout.setFont(QFont(APP_FONT_FAMILY, 12))
        self.readout.hide()
        self.plot.addItem(self.readout, ignoreBounds=True)

        self._t = self._alt = None
        self._temp = self._humidity = None
        self._proxy = pg.SignalProxy(self.plot.scene().sigMouseMoved, rateLimit=30, slot=self._on_mouse_moved)

        legend = QLabel(
            f'<span style="color:{colors.ALTITUDE};">▬</span> ارتفاع &nbsp;&nbsp;&nbsp; '
            f'<span style="color:{colors.TEMPERATURE};">▬</span> دما &nbsp;&nbsp;&nbsp; '
            f'<span style="color:{colors.HUMIDITY};">▬</span> رطوبت'
        )
        legend.setAlignment(Qt.AlignCenter)
        legend.setTextFormat(Qt.RichText)
        legend.setWordWrap(True)
        root.addWidget(legend)

        data_manager.analysis_ready.connect(self.refresh)

    # ------------------------------------------------------------------
    def _sync_views(self):
        rect = self.plot_item.vb.sceneBoundingRect()
        for vb in (self.temp_vb, self.hum_vb):
            vb.setGeometry(rect)
            vb.linkedViewChanged(self.plot_item.vb, vb.XAxis)

    # ------------------------------------------------------------------
    def refresh(self, _results: dict):
        df = data_manager.flight_df
        if df is None:
            return
        from core.analysis import FlightAnalyzer
        an = FlightAnalyzer(df, data_manager.mission)
        an.detect_events()
        idx = getattr(an, "_idx", {}) or {}

        if an.t is None:
            return

        launch_idx = idx.get("launch") or 0
        apogee_idx = idx.get("apogee")
        t0 = an.t[launch_idx]
        self._t = an.t - t0
        self._alt = an.alt
        # دما از سنسور دما و رطوبت (AHT21B)؛ در نبود آن، BMP280 به‌عنوان جایگزین
        self._temp = an.temp_aht if an.temp_aht is not None else an.temp
        self._humidity = an.humidity

        # ---- رسم منحنی‌ها ----
        self.alt_curve.setData(self._t, self._alt if self._alt is not None else np.zeros_like(self._t))
        if self._temp is not None:
            self.temp_curve.setData(self._t, self._temp)
        if self._humidity is not None:
            self.hum_curve.setData(self._t, self._humidity)
        self._sync_views()

        # ---- کارت‌های خلاصه (بازه‌ها از سطح پرتاب تا اوج) ----
        if self._temp is not None:
            if apogee_idx is not None:
                self.card_temp_range.set_value(
                    f"{self._temp[launch_idx]:.1f} تا {self._temp[apogee_idx]:.1f} °C")

            # نرخ افت دما (Lapse Rate) از روی دمای صعود
            if apogee_idx is not None and apogee_idx > launch_idx and self._alt is not None:
                alt_ascent = self._alt[launch_idx:apogee_idx + 1]
                temp_ascent = self._temp[launch_idx:apogee_idx + 1]
                if len(alt_ascent) > 3 and (np.max(alt_ascent) - np.min(alt_ascent)) > 10:
                    slope_c_per_m = float(np.polyfit(alt_ascent, temp_ascent, 1)[0])
                    slope_c_per_km = slope_c_per_m * 1000
                    self.card_lapse_rate.set_value(f"{slope_c_per_km:.1f} °C/km")
                    self.card_lapse_rate.set_extra(f"استاندارد ISA: {ISA_LAPSE_RATE_C_PER_KM:.1f} °C/km")

        if self._humidity is not None:
            if apogee_idx is not None:
                # علامت درصد کنار هر دو عدد (سطح پرتاب و اوج)
                self.card_humidity.set_value(
                    f"{self._humidity[launch_idx]:.0f}% تا {self._humidity[apogee_idx]:.0f}%")

    # ------------------------------------------------------------------
    def _on_mouse_moved(self, ev):
        if self._t is None or len(self._t) == 0:
            return
        pos = ev[0]
        if not self.plot.sceneBoundingRect().contains(pos):
            self.hover_line.hide()
            self.readout.hide()
            return
        mouse_point = self.plot_item.vb.mapSceneToView(pos)
        idx = int(np.clip(np.searchsorted(self._t, mouse_point.x()), 0, len(self._t) - 1))
        t_v = float(self._t[idx])

        self.hover_line.setPos(t_v)
        self.hover_line.show()

        lines = [protect_latin_quantities(f'<span style="color:#ffffff;">زمان: {t_v:.2f} s</span>')]
        if self._alt is not None:
            lines.append(protect_latin_quantities(f'<span style="color:{colors.ALTITUDE};">ارتفاع: {float(self._alt[idx]):.1f} m</span>'))
        if self._temp is not None:
            lines.append(protect_latin_quantities(f'<span style="color:{colors.TEMPERATURE};">دما: {float(self._temp[idx]):.1f} °C</span>'))
        if self._humidity is not None:
            lines.append(protect_latin_quantities(f'<span style="color:{colors.HUMIDITY};">رطوبت: {float(self._humidity[idx]):.0f} %</span>'))

        (xmin, xmax), (ymin, ymax) = self.plot.getViewBox().viewRange()
        self.readout.setPos(xmax - 0.02 * (xmax - xmin), ymax - 0.04 * (ymax - ymin))
        try:
            self.readout.textItem.setHtml("<br>".join(lines))
        except AttributeError:
            import re
            plain_lines = [re.sub("<[^>]+>", "", line) for line in lines]
            self.readout.setText("\n".join(plain_lines))
        self.readout.show()
