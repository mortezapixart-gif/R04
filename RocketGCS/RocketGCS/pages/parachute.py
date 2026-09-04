# -*- coding: utf-8 -*-
"""صفحهٔ تحلیل چتر -- دو نمودار کنار هم (ارتفاع / سرعت از باز شدن چتر تا فرود)،
دقیقاً با همان رفتار برگهٔ ارتفاع/سرعت: کراس‌هیر، باکس عدد، حرکت موس هم‌گام."""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from ui.style import APP_FONT_FAMILY
import numpy as np
import pyqtgraph as pg
from ui.widgets import CompactStatCard, make_card
from core import palette as colors
from core.data_manager import data_manager
from core.report_text import protect_latin_quantities


class ParachutePage(QWidget):
    def __init__(self):
        super().__init__()
        self.setLayoutDirection(Qt.RightToLeft)
        root = QVBoxLayout(self)

        grid = QGridLayout()
        self.card_deploy_time = CompactStatCard("زمان باز شدن چتر", "--")
        self.card_deploy_alt = CompactStatCard("ارتفاع بازشدن", "--")
        self.card_v_before = CompactStatCard("سرعت قبل چتر", "--")
        self.card_v_after = CompactStatCard("سرعت بعد چتر", "--")
        self.card_reduction = CompactStatCard("کاهش سرعت", "--")
        self.card_v_landing = CompactStatCard("سرعت برخورد", "--")
        self.card_energy = CompactStatCard("انرژی برخورد", "--", tooltip=(
            "انرژی جنبشی راکت در لحظهٔ برخورد با زمین (½ × جرم × سرعت²) -- شاخصی از شدت ضربهٔ فرود؛ "
            "هرچه چتر بهتر ترمز کند، سرعت برخورد و این انرژی کمتر می‌شود."
        ))
        cards = [self.card_deploy_time, self.card_deploy_alt, self.card_v_before, self.card_v_after,
                 self.card_reduction, self.card_v_landing, self.card_energy]
        for i, c in enumerate(cards):
            grid.addWidget(c, i // 7, i % 7)   # همهٔ کارت‌ها در یک ردیف، اندازهٔ یکسان
        for col in range(7):
            grid.setColumnStretch(col, 1)
        root.addLayout(grid)

        self.suggestion_label = QLabel("پیشنهاد: --")
        self.suggestion_label.setWordWrap(True)
        self.suggestion_label.setAlignment(Qt.AlignCenter)
        self.suggestion_label.setStyleSheet("font-size:16px; font-weight:bold; color:#4fd1c5; padding:10px;")
        root.addWidget(make_card(self.suggestion_label))

        pg.setConfigOption("background", "#1a2029")
        pg.setConfigOption("foreground", "#e6ebf1")

        self.alt_plot = pg.PlotWidget(title=protect_latin_quantities(
            "ارتفاع از باز شدن چتر تا برخورد با زمین"))
        self.alt_plot.setLabel("bottom", protect_latin_quantities("زمان از پرتاب (s)"))
        self.alt_plot.setLabel("left", protect_latin_quantities("ارتفاع (m)"))
        self.alt_plot.showGrid(x=True, y=True, alpha=0.2)
        self.alt_plot.addLine(y=0, pen=pg.mkPen("#5c6b80", width=1, style=Qt.DashLine))

        self.vel_plot = pg.PlotWidget(title=protect_latin_quantities(
            "سرعت از باز شدن چتر تا برخورد با زمین -- منفی یعنی نزول"))
        self.vel_plot.setLabel("bottom", protect_latin_quantities("زمان از پرتاب (s)"))
        self.vel_plot.setLabel("left", protect_latin_quantities("سرعت (m/s)"))
        self.vel_plot.showGrid(x=True, y=True, alpha=0.2)
        self.vel_plot.addLine(y=0, pen=pg.mkPen("#5c6b80", width=1, style=Qt.DashLine))

        charts_row = QHBoxLayout()
        charts_row.setSpacing(10)
        charts_row.addWidget(self.alt_plot, stretch=1)
        charts_row.addWidget(self.vel_plot, stretch=1)
        root.addLayout(charts_row, stretch=1)

        # نشانگر لحظهٔ باز شدن چتر روی هر دو نمودار
        deploy_pen = pg.mkPen("#f2c14e", width=2, style=Qt.DashLine)
        self.alt_deploy_line = pg.InfiniteLine(angle=90, pen=deploy_pen)
        self.vel_deploy_line = pg.InfiniteLine(angle=90, pen=deploy_pen)
        self.alt_deploy_text = pg.TextItem("", color="#f2c14e", anchor=(0, 1))
        self.vel_deploy_text = pg.TextItem("", color="#f2c14e", anchor=(0, 1))
        for line in (self.alt_deploy_line, self.vel_deploy_line):
            line.hide()
        for text in (self.alt_deploy_text, self.vel_deploy_text):
            text.hide()
        self.alt_plot.addItem(self.alt_deploy_line, ignoreBounds=True)
        self.alt_plot.addItem(self.alt_deploy_text)
        self.vel_plot.addItem(self.vel_deploy_line, ignoreBounds=True)
        self.vel_plot.addItem(self.vel_deploy_text)

        # کراس‌هیر + باکس عدد -- همان الگوی برگهٔ ارتفاع/سرعت
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

        self.alt_curve = self.alt_plot.plot(pen=pg.mkPen(colors.ALTITUDE, width=2))
        self.vel_curve = self.vel_plot.plot(pen=pg.mkPen(colors.VELOCITY, width=2))

        self._t = self._alt = self._vel = None
        self._alt_proxy = pg.SignalProxy(self.alt_plot.scene().sigMouseMoved, rateLimit=30,
                                          slot=lambda ev: self._on_mouse_moved(ev, self.alt_plot))
        self._vel_proxy = pg.SignalProxy(self.vel_plot.scene().sigMouseMoved, rateLimit=30,
                                          slot=lambda ev: self._on_mouse_moved(ev, self.vel_plot))

        data_manager.analysis_ready.connect(self.refresh)

    def refresh(self, results: dict):
        if "parachute_deploy_time" in results and results["parachute_deploy_time"] is not None:
            self.card_deploy_time.set_value(f"{results['parachute_deploy_time']:.1f} s")
        if "parachute_deploy_altitude" in results and results["parachute_deploy_altitude"] is not None:
            self.card_deploy_alt.set_value(f"{results['parachute_deploy_altitude']:.1f} m")
        if "velocity_before_chute" in results:
            self.card_v_before.set_value(f"{results['velocity_before_chute']:.1f} m/s")
        if "velocity_after_chute" in results:
            self.card_v_after.set_value(f"{results['velocity_after_chute']:.1f} m/s")
        if "descent_rate_reduction" in results and results["descent_rate_reduction"] is not None:
            self.card_reduction.set_value(f"{results['descent_rate_reduction']:.1f} برابر")
        if "landing_velocity" in results:
            v = results["landing_velocity"]
            self.card_v_landing.set_value(f"{v:.1f} m/s")
            self.card_v_landing.set_status("ok" if 3 <= v <= 8 else "warn")
        if "impact_energy_j" in results:
            self.card_energy.set_value(f"{results['impact_energy_j']:.1f} J")
        if "chute_suggestion" in results:
            self.suggestion_label.setText(f"پیشنهاد: {results['chute_suggestion']}")

        self._refresh_descent_charts()

    def _refresh_descent_charts(self):
        df = data_manager.flight_df
        if df is None:
            return
        from core.analysis import FlightAnalyzer
        an = FlightAnalyzer(df, data_manager.mission)
        an.detect_events()
        idx = getattr(an, "_idx", {})
        p_idx = idx.get("parachute")
        l_idx = idx.get("landing")
        if p_idx is None or l_idx is None or an.t is None or p_idx >= l_idx:
            return

        t_slice = an.t[p_idx:l_idx + 1]
        launch_idx = idx.get("launch") or 0
        t0 = an.t[launch_idx]           # زمان از لحظهٔ پرتاب، هماهنگ با سایر نمودارهای برنامه
        t_rel = t_slice - t0
        deploy_t_rel = float(an.t[p_idx] - t0)
        deploy_label = f"{deploy_t_rel:.1f} ثانیه، لحظهٔ باز شدن چتر"
        self._t = t_rel
        self._alt = None
        self._vel = None

        if an.alt is not None:
            alt_slice = an.alt[p_idx:l_idx + 1]
            self.alt_curve.setData(t_rel, alt_slice)
            self.alt_deploy_line.setPos(deploy_t_rel)
            self.alt_deploy_line.show()
            self.alt_deploy_text.setText(deploy_label)
            self.alt_deploy_text.setPos(deploy_t_rel, float(alt_slice[0]))
            self.alt_deploy_text.show()
            self._alt = alt_slice
        if an.vel is not None:
            vel_slice = an.vel[p_idx:l_idx + 1]
            self.vel_curve.setData(t_rel, vel_slice)
            self.vel_deploy_line.setPos(deploy_t_rel)
            self.vel_deploy_line.show()
            self.vel_deploy_text.setText(deploy_label)
            self.vel_deploy_text.setPos(deploy_t_rel, float(vel_slice[0]))
            self.vel_deploy_text.show()
            self._vel = vel_slice

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
        idx = int(np.clip(np.searchsorted(self._t, mouse_point.x()), 0, len(self._t) - 1))
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
