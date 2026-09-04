# -*- coding: utf-8 -*-
"""صفحهٔ «شتاب / سرعت» -- دو نمودار هم‌گام‌شدهٔ شتاب و سرعت (تب تحلیل پرواز)."""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGridLayout
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
import numpy as np
import pyqtgraph as pg
from ui.widgets import section_title, CompactStatCard
from ui.style import APP_FONT_FAMILY
from core import palette as colors
from core.data_manager import data_manager
from core.analysis import G0
from core.report_text import protect_latin_quantities

G_TOOLTIP = (
    "شتاب بر حسب g: واحد رایج شتاب در هوافضا، نسبت به شتاب جاذبهٔ زمین (g ≈ ۹.۸۱ متر بر مجذور ثانیه).\n"
    "عدد ۱g یعنی شتابی هم‌اندازهٔ جاذبهٔ زمین (مثل راکت ساکن روی سکو)؛ در طول رانش موتور این عدد\n"
    "می‌تواند چند برابر شود، و در سقوط آزاد (Coast) به نزدیک صفر می‌رسد."
)

V_TOOLTIP = (
    "سرعت عمودی راکت از تلفیق داده‌های فشار/شتاب بازسازی می‌شود؛ مقدار منفی یعنی راکت در حال "
    "نزول است. بیشینهٔ سرعت معمولاً درست پیش از خاموشی موتور رخ می‌دهد."
)


class FlightAnalysisPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setLayoutDirection(Qt.RightToLeft)
        root = QVBoxLayout(self)

        # ============================================================
        # شتاب و سرعت -- کارت‌های پارامتر + دو نمودار هم‌گام‌شده
        # ============================================================
        root.addWidget(section_title("شتاب و سرعت بر حسب زمان"))
        grid = QGridLayout()
        self.card_max_g = CompactStatCard("بیشینه شتاب", "--", tooltip=G_TOOLTIP)
        self.card_landing_accel = CompactStatCard("شتاب هنگام برخورد", "--", tooltip=G_TOOLTIP)
        self.card_max_vel = CompactStatCard("بیشینه سرعت", "--", tooltip=V_TOOLTIP)
        self.card_vel_burnout = CompactStatCard("سرعت پایان سوخت", "--", tooltip=V_TOOLTIP)
        self.card_accel_chute = CompactStatCard(
            "شتاب موقع باز شدن چتر", "--", tooltip=(
                "شتاب کل (g) درست در لحظهٔ باز شدن چتر؛ نشان می‌دهد چتر با چه "
                "ضربه‌ای باز می‌شود و چه باری در آن لحظه به سازه و چتر وارد می‌آید."
            ))
        cards = [self.card_max_g, self.card_landing_accel,
                 self.card_max_vel, self.card_vel_burnout, self.card_accel_chute]
        for i, c in enumerate(cards):
            grid.addWidget(c, 0, i)
            grid.setColumnStretch(i, 1)
        root.addLayout(grid)

        pg.setConfigOption("background", "#1a2029")
        pg.setConfigOption("foreground", "#e6ebf1")

        self.accel_plot = pg.PlotWidget(title=protect_latin_quantities("شتاب کل بر حسب زمان (از لحظهٔ پرتاب)"))
        self.accel_plot.setLabel("bottom", protect_latin_quantities("زمان از پرتاب (s)"))
        self.accel_plot.setLabel("left", protect_latin_quantities("شتاب (g)"))
        self.accel_plot.showGrid(x=True, y=True, alpha=0.2)
        self.accel_plot.addLine(y=0, pen=pg.mkPen("#5c6b80", width=1, style=Qt.DashLine))

        self.vel_plot = pg.PlotWidget(title=protect_latin_quantities("سرعت بر حسب زمان -- منفی یعنی نزول"))
        self.vel_plot.setLabel("bottom", protect_latin_quantities("زمان از پرتاب (s)"))
        self.vel_plot.setLabel("left", protect_latin_quantities("سرعت (m/s)"))
        self.vel_plot.showGrid(x=True, y=True, alpha=0.2)
        self.vel_plot.addLine(y=0, pen=pg.mkPen("#5c6b80", width=1, style=Qt.DashLine))

        charts_row = QHBoxLayout()
        charts_row.setSpacing(10)
        charts_row.addWidget(self.accel_plot, stretch=1)
        charts_row.addWidget(self.vel_plot, stretch=1)
        root.addLayout(charts_row, stretch=1)

        # زوم/پن هر نمودار مستقل است (درخواست کاربر)؛ هم‌گام‌سازی فقط برای
        # نشانگر متقاطع (خط عمودی زمان) برقرار است.

        # نشانگرهای متقاطع -- با حرکت موس روی هر نمودار، هر دو حرکت می‌کنند
        self.accel_vline = pg.InfiniteLine(angle=90, pen=pg.mkPen(colors.ACCEL_TOTAL, width=1))
        self.accel_hline = pg.InfiniteLine(angle=0, pen=pg.mkPen(colors.ACCEL_TOTAL, width=1))
        self.vel_vline = pg.InfiniteLine(angle=90, pen=pg.mkPen(colors.VELOCITY, width=1))
        self.vel_hline = pg.InfiniteLine(angle=0, pen=pg.mkPen(colors.VELOCITY, width=1))
        for line in (self.accel_vline, self.accel_hline, self.vel_vline, self.vel_hline):
            line.hide()
        for line in (self.accel_vline, self.accel_hline):
            self.accel_plot.addItem(line, ignoreBounds=True)
        for line in (self.vel_vline, self.vel_hline):
            self.vel_plot.addItem(line, ignoreBounds=True)

        # باکس نشانگر روی هر نمودار (هم‌سبک صفحهٔ ارتفاع/سرعت)
        def make_readout(border_color: str) -> pg.TextItem:
            r = pg.TextItem(anchor=(1, 0), color="#e6ebf1",
                            fill=(20, 26, 36, 220), border=pg.mkPen(border_color))
            r.setFont(QFont(APP_FONT_FAMILY, 12))
            r.hide()
            return r
        self.accel_readout = make_readout(colors.ACCEL_TOTAL)
        self.vel_readout = make_readout(colors.VELOCITY)
        self.accel_plot.addItem(self.accel_readout, ignoreBounds=True)
        self.vel_plot.addItem(self.vel_readout, ignoreBounds=True)

        self._t = self._g = self._vel = None
        self._accel_proxy = pg.SignalProxy(self.accel_plot.scene().sigMouseMoved, rateLimit=30,
                                           slot=lambda ev: self._on_mouse_moved(ev, self.accel_plot))
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
        events = (results or {}).get("events", {})
        t0 = events.get("launch") or 0.0

        if an.t is not None and an.a_total is not None:
            self._t = an.t - t0
            self._g = an.a_total / G0
            self._vel = an.vel if an.vel is not None else None
            zero_pen = pg.mkPen("#5c6b80", width=1, style=Qt.DashLine)
            for plt in (self.accel_plot, self.vel_plot):
                plt.clear()
                plt.addLine(y=0, pen=zero_pen)
            self.accel_plot.plot(self._t, self._g, pen=pg.mkPen(colors.ACCEL_TOTAL, width=2))
            if self._vel is not None:
                self.vel_plot.plot(self._t, self._vel, pen=pg.mkPen(colors.VELOCITY, width=2))
            # آیتم‌های نشانگر بعد از clear دوباره اضافه می‌شوند
            for line in (self.accel_vline, self.accel_hline):
                self.accel_plot.addItem(line, ignoreBounds=True)
            self.accel_plot.addItem(self.accel_readout, ignoreBounds=True)
            for line in (self.vel_vline, self.vel_hline):
                self.vel_plot.addItem(line, ignoreBounds=True)
            self.vel_plot.addItem(self.vel_readout, ignoreBounds=True)

            # کارت‌های پارامترهای شتاب و سرعت
            self.card_max_g.set_value(f"{results.get('max_g', 0):.2f} g")
            if "accel_at_landing" in results:
                self.card_landing_accel.set_value(f"{results['accel_at_landing']:.2f} g")
            if results.get("max_velocity") is not None:
                self.card_max_vel.set_value(
                    f"{results['max_velocity']:.0f} m/s ({results['max_velocity'] * 3.6:.0f} km/h)")
            if results.get("velocity_at_burnout") is not None:
                self.card_vel_burnout.set_value(f"{results['velocity_at_burnout']:.0f} m/s")
            if results.get("accel_at_parachute_g") is not None:
                self.card_accel_chute.set_value(f"{results['accel_at_parachute_g']:.2f} g")

    # ------------------------------------------------------------------
    def _on_mouse_moved(self, ev, source_plot):
        if self._t is None or len(self._t) == 0:
            return
        pos = ev[0]
        if not source_plot.sceneBoundingRect().contains(pos):
            return
        mouse_point = source_plot.plotItem.vb.mapSceneToView(pos)
        idx = int(np.clip(np.searchsorted(self._t, mouse_point.x()), 0, len(self._t) - 1))
        t_v = float(self._t[idx])

        # خط عمودی روی «هر دو» نمودار در همان لحظه (حرکت هم‌گام)
        for vline in (self.accel_vline, self.vel_vline):
            vline.setPos(t_v)
            vline.show()

        g_v = float(self._g[idx])
        self.accel_hline.setPos(g_v)
        self.accel_hline.show()
        self._place_readout(self.accel_readout, self.accel_plot, t_v,
                            protect_latin_quantities(
                                f'<span style="color:#ffffff;">زمان: {t_v:.2f} s</span><br>'
                                f'<span style="color:{colors.ACCEL_TOTAL};">شتاب: {g_v:.2f} g</span>'))
        if self._vel is not None:
            vel_v = float(self._vel[idx])
            self.vel_hline.setPos(vel_v)
            self.vel_hline.show()
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
