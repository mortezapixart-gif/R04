# -*- coding: utf-8 -*-
"""صفحهٔ ارتفاع و سرعت"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGridLayout
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from ui.style import APP_FONT_FAMILY
import numpy as np
import pyqtgraph as pg
from ui.widgets import CompactStatCard
from core import palette as colors
from core.data_manager import data_manager
from core.report_text import protect_latin_quantities

# عرض/ارتفاع قفل‌شدهٔ کارت‌های آماری بالا -- با تغییر مقادیر (حرکت موس)
# کارت‌ها کوچک/بزرگ نمی‌شوند و چیدمان ثابت می‌ماند.
CARD_FIXED_WIDTH = 195


class AltitudeVelocityPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setLayoutDirection(Qt.RightToLeft)
        root = QVBoxLayout(self)

        grid = QGridLayout()
        self.card_max_alt = CompactStatCard("بیشترین ارتفاع", "--")
        self.card_max_vel = CompactStatCard("بیشترین سرعت", "--")
        self.card_vel_burnout = CompactStatCard("سرعت Burnout", "--", tooltip=(
            "سرعت راکت درست در لحظهٔ پایان رانش موتور (وقتی سوخت تمام می‌شود). این عدد معمولاً "
            "نزدیک به بیشترین سرعت کل پرواز است، چون از این لحظه به بعد راکت دیگر شتاب موتور را ندارد "
            "و فقط با درگ هوا و گرانش کند می‌شود."
        ))
        self.card_vel_landing = CompactStatCard("سرعت برخورد", "--")
        cards = [self.card_max_alt, self.card_max_vel,
                 self.card_vel_burnout, self.card_vel_landing]
        for i, c in enumerate(cards):
            c.setFixedWidth(CARD_FIXED_WIDTH)   # اندازهٔ باکس‌ها قفل است
            grid.addWidget(c, i // 4, i % 4)     # همهٔ ۴ کارت در یک ردیف
        for col in range(4):
            grid.setColumnStretch(col, 1)
        grid.setAlignment(Qt.AlignCenter)
        root.addLayout(grid)

        pg.setConfigOption("background", "#1a2029")
        pg.setConfigOption("foreground", "#e6ebf1")

        self.alt_plot = pg.PlotWidget(title=protect_latin_quantities("ارتفاع بر حسب زمان (از لحظهٔ پرتاب)"))
        self.alt_plot.setLabel("bottom", protect_latin_quantities("زمان از پرتاب (s)"))
        self.alt_plot.setLabel("left", protect_latin_quantities("ارتفاع (m)"))
        self.alt_plot.showGrid(x=True, y=True, alpha=0.2)
        self.alt_plot.addLine(y=0, pen=pg.mkPen("#5c6b80", width=1, style=Qt.DashLine))

        self.vel_plot = pg.PlotWidget(title=protect_latin_quantities("سرعت بر حسب زمان -- منفی یعنی نزول"))
        self.vel_plot.setLabel("bottom", protect_latin_quantities("زمان از پرتاب (s)"))
        self.vel_plot.setLabel("left", protect_latin_quantities("سرعت (m/s)"))
        self.vel_plot.showGrid(x=True, y=True, alpha=0.2)
        self.vel_plot.addLine(y=0, pen=pg.mkPen("#5c6b80", width=1, style=Qt.DashLine))

        # دو نمودار کنار هم (مشابه مرکز کنترل پرواز)
        charts_row = QHBoxLayout()
        charts_row.setSpacing(10)
        charts_row.addWidget(self.alt_plot, stretch=1)
        charts_row.addWidget(self.vel_plot, stretch=1)
        root.addLayout(charts_row, stretch=1)

        # نشانگرهای متقاطع (Crosshair) که با حرکت موس روی نمودار دنبال می‌کنند
        self.alt_vline = pg.InfiniteLine(angle=90, pen=pg.mkPen("#4fd1c5", width=1))
        self.alt_hline = pg.InfiniteLine(angle=0, pen=pg.mkPen("#4fd1c5", width=1))
        self.vel_vline = pg.InfiniteLine(angle=90, pen=pg.mkPen("#a970ff", width=1))
        self.vel_hline = pg.InfiniteLine(angle=0, pen=pg.mkPen("#a970ff", width=1))
        for line in (self.alt_vline, self.alt_hline, self.vel_vline, self.vel_hline):
            line.hide()
        self.alt_plot.addItem(self.alt_vline, ignoreBounds=True)
        self.alt_plot.addItem(self.alt_hline, ignoreBounds=True)
        self.vel_plot.addItem(self.vel_vline, ignoreBounds=True)
        self.vel_plot.addItem(self.vel_hline, ignoreBounds=True)

        # باکس کوچک گوشهٔ نمودار (مثل نمودار آیرودینامیک و ارتفاع-دما)
        def make_readout(border_color: str) -> pg.TextItem:
            r = pg.TextItem(anchor=(1, 0), color="#e6ebf1",
                            fill=(20, 26, 36, 220), border=pg.mkPen(border_color))
            r.setFont(QFont(APP_FONT_FAMILY, 12))
            r.hide()
            return r
        self.alt_readout = make_readout(colors.ALTITUDE)
        self.vel_readout = make_readout(colors.VELOCITY)
        self.alt_plot.addItem(self.alt_readout, ignoreBounds=True)
        self.vel_plot.addItem(self.vel_readout, ignoreBounds=True)

        self._t = self._alt = self._vel = None
        self._alt_proxy = pg.SignalProxy(self.alt_plot.scene().sigMouseMoved, rateLimit=30,
                                          slot=lambda ev: self._on_mouse_moved(ev, self.alt_plot))
        self._vel_proxy = pg.SignalProxy(self.vel_plot.scene().sigMouseMoved, rateLimit=30,
                                          slot=lambda ev: self._on_mouse_moved(ev, self.vel_plot))

        data_manager.analysis_ready.connect(self.refresh)

    def refresh(self, results: dict):
        df = data_manager.flight_df
        if df is None:
            return
        from core.analysis import FlightAnalyzer
        an = FlightAnalyzer(df, data_manager.mission)
        events = an.detect_events()
        t0 = events.get("launch") or 0.0
        self._t = (an.t - t0) if an.t is not None else None
        self._alt = an.alt
        self._vel = an.vel

        if self._t is not None and an.alt is not None:
            self.alt_plot.clear()
            self.alt_plot.addLine(y=0, pen=pg.mkPen("#5c6b80", width=1, style=Qt.DashLine))
            self.alt_plot.plot(self._t, an.alt, pen=pg.mkPen(colors.ALTITUDE, width=2))
            self.alt_plot.addItem(self.alt_vline, ignoreBounds=True)
            self.alt_plot.addItem(self.alt_hline, ignoreBounds=True)
            self.alt_plot.addItem(self.alt_readout, ignoreBounds=True)
            self.card_max_alt.set_value(f"{results.get('max_altitude', 0):.1f} m")

        if self._t is not None and an.vel is not None:
            self.vel_plot.clear()
            self.vel_plot.plot(self._t, an.vel, pen=pg.mkPen(colors.VELOCITY, width=2))
            self.vel_plot.addLine(y=0, pen=pg.mkPen("#5c6b80", width=1, style=Qt.DashLine))
            self.vel_plot.addItem(self.vel_vline, ignoreBounds=True)
            self.vel_plot.addItem(self.vel_hline, ignoreBounds=True)
            self.vel_plot.addItem(self.vel_readout, ignoreBounds=True)
            self.card_max_vel.set_value(f"{results.get('max_velocity', 0):.1f} m/s")
            if "velocity_at_burnout" in results:
                self.card_vel_burnout.set_value(f"{results['velocity_at_burnout']:.1f} m/s")
            if "landing_velocity" in results:
                self.card_vel_landing.set_value(f"{results['landing_velocity']:.1f} m/s")

    def _on_mouse_moved(self, ev, plot_widget):
        if self._t is None or len(self._t) == 0:
            return
        pos = ev[0]
        if not plot_widget.sceneBoundingRect().contains(pos):
            for item in (self.alt_vline, self.alt_hline, self.vel_vline, self.vel_hline):
                item.hide()
            self.alt_readout.hide()
            self.vel_readout.hide()
            return
        mouse_point = plot_widget.plotItem.vb.mapSceneToView(pos)
        x = mouse_point.x()
        idx = int(np.clip(np.searchsorted(self._t, x), 0, len(self._t) - 1))
        t_v = float(self._t[idx])

        if self._alt is not None:
            alt_v = float(self._alt[idx])
            self.alt_vline.setPos(t_v); self.alt_vline.show()
            self.alt_hline.setPos(alt_v); self.alt_hline.show()
            self._place_readout(self.alt_readout, self.alt_plot, t_v,
                                protect_latin_quantities(
                                    f'<span style="color:#ffffff;">زمان: {t_v:.2f} s</span><br>'
                                    f'<span style="color:{colors.ALTITUDE};">ارتفاع: {alt_v:.1f} m</span>'))

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
