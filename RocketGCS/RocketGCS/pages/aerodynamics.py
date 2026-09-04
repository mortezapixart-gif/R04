# -*- coding: utf-8 -*-
"""صفحهٔ تحلیل آیرودینامیک (تقریبی)

چیدمان مثل صفحهٔ ارتفاع/سرعت: کارت‌های فشرده در یک ردیف + دو نمودار کنار هم
(فشار دینامیکی | سرعت) با نشانگر Max-Q و راهنمای شناور موس.
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from ui.style import APP_FONT_FAMILY
import numpy as np
import pyqtgraph as pg
from ui.widgets import CompactStatCard
from core import palette as colors
from core.data_manager import data_manager
from core.report_text import protect_latin_quantities

MAX_Q_TOOLTIP = (
    "Max-Q: لحظه‌ای در طول پرواز که بیشترین فشار دینامیکی (q = ½ρv²) به بدنهٔ راکت وارد می‌شود.\n"
    "این نقطه معمولاً نه در اوج سرعت و نه در اوج ارتفاع رخ می‌دهد، بلکه جایی در میانهٔ مرحلهٔ رانش است؛\n"
    "چون سرعت در حال افزایش و چگالی هوا در حال کاهش است و ترکیب این دو در این لحظه به بیشینه می‌رسد.\n"
    "بحرانی‌ترین نقطهٔ فشار سازه‌ای روی بدنه، فین‌ها و نوک راکت همین‌جاست."
)


class AerodynamicsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setLayoutDirection(Qt.RightToLeft)
        root = QVBoxLayout(self)

        note = QLabel(
            "توجه: فشار دینامیکی با چگالی محلی از فشار و دمای سنسور (وگرنه ISA در "
            "ارتفاع لحظه‌ای) ساخته می‌شود؛ نیروی درگ = q·Cd·A. تقریب مهندسی اولیه است."
        )
        note.setWordWrap(True)
        note.setAlignment(Qt.AlignCenter)
        root.addWidget(note)

        # ---- کارت‌های فشرده (مثل صفحهٔ ارتفاع/سرعت) ----
        grid = QGridLayout()
        self.card_cd = CompactStatCard("ضریب پسا تقریبی (Cd)", "--", tooltip=(
            "ضریب پسا (Drag Coefficient): عددی بدون بعد که میزان مقاومت آیرودینامیکی شکل راکت در برابر هوا را نشان می‌دهد.\n"
            "هرچی این عدد کوچک‌تر باشد، راکت آیرودینامیک‌تر است و انرژی کمتری صرف غلبه بر درگ می‌شود."
        ))
        self.card_drag = CompactStatCard("نیروی درگ (لحظه Max-Q)", "--", tooltip=(
            "نیروی درگ: D = q·Cd·A -- فشار دینامیکی لحظهٔ Max-Q ضربدر ضریب پسا ضربدر سطح مقطع بدنه.\n"
            "اگر Cd از داده برآورد نشده باشد، Cd بدنهٔ آموزشی (۰٫۶ × ضریب مخروط سر) استفاده می‌شود."
        ))
        self.card_maxq = CompactStatCard("زمان و سرعت در لحظهٔ Max-Q", "--", tooltip=MAX_Q_TOOLTIP)
        for i, c in enumerate([self.card_cd, self.card_drag, self.card_maxq]):
            grid.addWidget(c, 0, i)
        for col in range(3):
            grid.setColumnStretch(col, 1)
        root.addLayout(grid)

        # ---- دو نمودار کنار هم (مثل صفحهٔ ارتفاع/سرعت) ----
        pg.setConfigOption("background", "#1a2029")
        pg.setConfigOption("foreground", "#e6ebf1")

        self.q_plot = pg.PlotWidget(title=protect_latin_quantities("فشار دینامیکی بر زمان"))
        self.q_plot.setLabel("bottom", protect_latin_quantities("زمان (s)"))
        self.q_plot.setLabel("left", protect_latin_quantities("فشار دینامیکی (Pa)"), color=colors.PRESSURE)
        self.q_plot.getAxis("left").setTextPen(colors.PRESSURE)
        self.q_plot.showGrid(x=True, y=True, alpha=0.2)
        self.q_curve = self.q_plot.plot(pen=pg.mkPen(colors.PRESSURE, width=2))
        self.q_theory_curve = self.q_plot.plot(
            pen=pg.mkPen(colors.THEORY_LINE, width=2, style=Qt.DashLine))
        self.q_legend = self.q_plot.addLegend()
        self.q_legend.addItem(self.q_curve, "داده واقعی")
        self.q_legend.addItem(self.q_theory_curve, "پیش‌بینی تئوری")

        self.vel_plot = pg.PlotWidget(title=protect_latin_quantities("سرعت بر زمان"))
        self.vel_plot.setLabel("bottom", protect_latin_quantities("زمان (s)"))
        self.vel_plot.setLabel("left", protect_latin_quantities("سرعت (m/s)"), color=colors.VELOCITY)
        self.vel_plot.getAxis("left").setTextPen(colors.VELOCITY)
        self.vel_plot.showGrid(x=True, y=True, alpha=0.2)
        self.vel_curve = self.vel_plot.plot(pen=pg.mkPen(colors.VELOCITY, width=2))

        charts_row = QHBoxLayout()
        charts_row.setSpacing(10)
        charts_row.addWidget(self.q_plot, stretch=1)
        charts_row.addWidget(self.vel_plot, stretch=1)
        root.addLayout(charts_row, stretch=1)

        # ---- خط صفر (خط‌چین) مثل بقیهٔ نمودارهای برنامه ----
        for plot in (self.q_plot, self.vel_plot):
            plot.addLine(y=0, pen=pg.mkPen("#5c6b80", width=1, style=Qt.DashLine))

        # ---- خط عمودی Max-Q روی هر دو نمودار ----
        self.maxq_line_q = pg.InfiniteLine(angle=90, pen=pg.mkPen("#f2c14e", width=1))
        self.maxq_line_vel = pg.InfiniteLine(angle=90, pen=pg.mkPen("#f2c14e", width=1))
        self.maxq_line_q.hide()
        self.maxq_line_vel.hide()
        self.q_plot.addItem(self.maxq_line_q, ignoreBounds=True)
        self.vel_plot.addItem(self.maxq_line_vel, ignoreBounds=True)

        # ---- نشانگرهای متقاطع (Crosshair) همگام -- دقیقاً مثل صفحهٔ سرعت/شتاب:
        # موس روی هر یک از دو نمودار باشد، خطِ هر دو نمودار با هم حرکت می‌کند و
        # باکس پارامترها (زمان + مقدار همان نمودار) دنبال موس می‌آید. ----
        self.q_vline = pg.InfiniteLine(angle=90, pen=pg.mkPen(colors.PRESSURE, width=1))
        self.q_hline = pg.InfiniteLine(angle=0, pen=pg.mkPen(colors.PRESSURE, width=1))
        self.vel_vline = pg.InfiniteLine(angle=90, pen=pg.mkPen(colors.VELOCITY, width=1))
        self.vel_hline = pg.InfiniteLine(angle=0, pen=pg.mkPen(colors.VELOCITY, width=1))
        for line in (self.q_vline, self.q_hline, self.vel_vline, self.vel_hline):
            line.hide()
        self.q_plot.addItem(self.q_vline, ignoreBounds=True)
        self.q_plot.addItem(self.q_hline, ignoreBounds=True)
        self.vel_plot.addItem(self.vel_vline, ignoreBounds=True)
        self.vel_plot.addItem(self.vel_hline, ignoreBounds=True)

        def make_readout(border_color: str) -> pg.TextItem:
            r = pg.TextItem(anchor=(1, 0), color="#e6ebf1",
                            fill=(20, 26, 36, 220), border=pg.mkPen(border_color))
            r.setFont(QFont(APP_FONT_FAMILY, 12))
            r.hide()
            return r
        self.q_readout = make_readout(colors.PRESSURE)
        self.vel_readout = make_readout(colors.VELOCITY)
        self.q_plot.addItem(self.q_readout, ignoreBounds=True)
        self.vel_plot.addItem(self.vel_readout, ignoreBounds=True)

        self._t = self._q = self._vel = None
        self._q_proxy = pg.SignalProxy(self.q_plot.scene().sigMouseMoved, rateLimit=30,
                                       slot=lambda ev: self._on_mouse_moved(ev, self.q_plot))
        self._vel_proxy = pg.SignalProxy(self.vel_plot.scene().sigMouseMoved, rateLimit=30,
                                         slot=lambda ev: self._on_mouse_moved(ev, self.vel_plot))

        data_manager.analysis_ready.connect(self.refresh)

    # ------------------------------------------------------------------
    def refresh(self, results: dict):
        df = data_manager.flight_df
        if df is None:
            return
        from core.analysis import FlightAnalyzer
        an = FlightAnalyzer(df, data_manager.mission)
        if an.t is None or an.vel is None:
            return

        rho = an.local_density()
        q = 0.5 * rho * an.vel ** 2
        self._t, self._q, self._vel = an.t, q, np.abs(an.vel)
        self.q_curve.setData(an.t, q)
        self.vel_curve.setData(an.t, self._vel)

        # منحنی تئوری ساده بر اساس رانش متوسط موتور و جرم کل (تخمین سرعت ایده‌آل بدون درگ)
        mo = data_manager.motor
        mi = data_manager.mission
        rho_ref = float(np.nanmedian(rho)) if np.isfinite(rho).any() else 1.1
        if mo.average_thrust and mi.total_mass:
            a_ideal = (mo.average_thrust / mi.total_mass) - 9.80665
            t_arr = an.t
            v_ideal = np.where(t_arr < mo.burn_time, a_ideal * t_arr,
                               a_ideal * mo.burn_time - 9.80665 * (t_arr - mo.burn_time))
            q_ideal = 0.5 * rho_ref * np.clip(v_ideal, 0, None) ** 2
            self.q_theory_curve.setData(t_arr, q_ideal)
        else:
            self.q_theory_curve.setData([])

        # مقادیر Max-Q مستقیماً از همین q محلی محاسبه می‌شوند (نه از دیکشنری
        # results) تا این کارت‌ها همیشه پر شوند، حتی اگر تحلیل کلی به هر
        # دلیلی کلید مربوطه را تولید نکرده باشد
        max_q_idx = int(np.argmax(q))
        q_max = float(q[max_q_idx])
        t_maxq = float(an.t[max_q_idx])
        self.maxq_line_q.setPos(t_maxq)
        self.maxq_line_vel.setPos(t_maxq)
        self.maxq_line_q.show()
        self.maxq_line_vel.show()

        self.card_maxq.set_value(f"{t_maxq:.2f} s")
        self.card_maxq.set_extra(f"سرعت: {abs(an.vel[max_q_idx]):.1f} m/s")

        area = None
        if mi.body_diameter:
            import math
            area = math.pi * (mi.body_diameter / 2) ** 2
        cd = results.get("estimated_Cd")
        if not cd:
            from core.rocket_physics import BODY_CD, NOSE_CD_FACTOR
            nose = getattr(mi, "nose_cone", None) or "اویو"
            cd = BODY_CD * NOSE_CD_FACTOR.get(nose, 1.0)
        if area:
            drag = q_max * float(cd) * area
            self.card_drag.set_value(f"{drag:.1f} N")
            self.card_drag.set_extra(
                f'<span style="color:{colors.PRESSURE};">فشار دینامیکی بیشینه: {q_max:.0f} Pa  ·  Cd={float(cd):.2f}</span>'
            )
        est = results.get("estimated_Cd")
        self.card_cd.set_value(f"{est:.2f}" if est else "نیازمند مدل دقیق‌تر")

    # ------------------------------------------------------------------
    def _on_mouse_moved(self, ev, plot_widget):
        """کراس‌هیر همگام -- الگوی صفحهٔ سرعت/شتاب: خروج موس = پنهان‌شدن همه."""
        if self._t is None or len(self._t) == 0:
            return
        pos = ev[0]
        if not plot_widget.sceneBoundingRect().contains(pos):
            for item in (self.q_vline, self.q_hline, self.vel_vline, self.vel_hline):
                item.hide()
            self.q_readout.hide()
            self.vel_readout.hide()
            return
        mouse_point = plot_widget.plotItem.vb.mapSceneToView(pos)
        idx = int(np.clip(np.searchsorted(self._t, mouse_point.x()), 0, len(self._t) - 1))
        t_v = float(self._t[idx])

        if self._q is not None:
            q_v = float(self._q[idx])
            self.q_vline.setPos(t_v); self.q_vline.show()
            self.q_hline.setPos(q_v); self.q_hline.show()
            self._place_readout(self.q_readout, self.q_plot, t_v,
                                protect_latin_quantities(
                                    f'<span style="color:#ffffff;">زمان: {t_v:.2f} s</span><br>'
                                    f'<span style="color:{colors.PRESSURE};">فشار دینامیکی: {q_v:.0f} Pa</span>'))

        if self._vel is not None:
            vel_v = float(self._vel[idx])
            self.vel_vline.setPos(t_v); self.vel_vline.show()
            self.vel_hline.setPos(vel_v); self.vel_hline.show()
            self._place_readout(self.vel_readout, self.vel_plot, t_v,
                                protect_latin_quantities(
                                    f'<span style="color:#ffffff;">زمان: {t_v:.2f} s</span><br>'
                                    f'<span style="color:{colors.VELOCITY};">سرعت: {vel_v:.1f} m/s</span>'))

    @staticmethod
    def _place_readout(readout: pg.TextItem, plot_widget, x: float, html: str):
        """باکس گوشهٔ نمودار: در بالای محدودهٔ دید، دنبال موس (افقی) حرکت می‌کند."""
        readout.setHtml(html)
        try:
            y_top = plot_widget.plotItem.vb.viewRange()[1][1]
        except Exception:
            y_top = 0.0
        readout.setPos(x, y_top)
        readout.show()
