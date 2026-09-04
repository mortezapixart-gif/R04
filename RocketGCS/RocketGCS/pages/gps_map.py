# -*- coding: utf-8 -*-
"""صفحهٔ نمایش مسیر GPS (نمای سه‌بعدی اختیاری با pyqtgraph.opengl و نمای دوبعدی مسیر)"""
from datetime import datetime, timedelta, timezone
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog, QMessageBox
from PySide6.QtCore import Qt
import numpy as np
import pyqtgraph as pg
from ui.widgets import CompactStatCard, make_card
from core import palette as colors
from core.data_manager import data_manager

try:
    import pyqtgraph.opengl as gl
    HAS_GL = True
except Exception:
    HAS_GL = False

# رنگ‌بندی مسیر در KML -- هماهنگ با بازپخش سه‌بعدی (زرد=صعود، قرمز=سقوط
# آزاد، فیروزه‌ای=نزول با چتر باز)
KML_COLOR_ASCENT = (250, 181, 51)
KML_COLOR_FREEFALL = (240, 84, 79)
KML_COLOR_CHUTE = (79, 209, 197)
KML_MAX_TRACK_POINTS = 1500   # سقف تعداد نقاط gx:Track برای کارایی بهتر گوگل ارث


def _rgb_to_kml(rgb, alpha=255) -> str:
    r, g, b = rgb
    return f"{alpha:02x}{b:02x}{g:02x}{r:02x}"


def _add_kml_button_shadow(widget):
    from PySide6.QtWidgets import QGraphicsDropShadowEffect
    from PySide6.QtGui import QColor
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(22)
    effect.setOffset(0, 4)
    effect.setColor(QColor(52, 168, 83, 120))   # سبز گوگلی کم‌رنگ
    widget.setGraphicsEffect(effect)


class GpsMapPage(QWidget):
    def __init__(self):
        super().__init__()
        self.setLayoutDirection(Qt.RightToLeft)
        root = QVBoxLayout(self)

        # کارت‌های فشردهٔ تک‌خطی: مقدار جلوی عنوان (سبک صفحات تحلیل دیگر)
        info_row = QHBoxLayout()
        self.card_launch = CompactStatCard("نقطه پرتاب", "--", tooltip=(
            "طول و عرض جغرافیایی نقطهٔ آغاز پرواز"))
        self.card_landing = CompactStatCard("نقطه فرود", "--", tooltip=(
            "طول و عرض جغرافیایی نقطهٔ پایان پرواز"))
        self.card_distance = CompactStatCard("فاصله نقطه پرتاب تا فرود", "--", tooltip=(
            "فاصلهٔ خطی (بزرگ‌دایره) میان نقطهٔ پرتاب و نقطهٔ فرود"))
        info_row.addWidget(self.card_launch)
        info_row.addWidget(self.card_landing)
        info_row.addWidget(self.card_distance)
        root.addLayout(info_row)

        row = QHBoxLayout()

        # نمای دوبعدی مسیر (طول/عرض جغرافیایی)
        self.map2d = pg.PlotWidget(title="مسیر روی نقشه (Lat/Lon)")
        self.map2d.setLabel("bottom", "Longitude")
        self.map2d.setLabel("left", "Latitude")
        self.map2d.showGrid(x=True, y=True, alpha=0.2)
        row.addWidget(make_card(self.map2d))

        # باکس کنار نمودار حذف شد -- تا وقتی دادهٔ GPS واقعی نباشد فقط یک باکس
        # خالیِ بی‌محتوا کنار نقشه بود؛ نقشهٔ دوبعدی حالا تمام عرض را می‌گیرد.
        # (نمایش سه‌بعدی در «بازپخش سه‌بعدی» با دادهٔ واقعی موجود است.)
        self.view3d = None

        root.addLayout(row)

        export_row = QHBoxLayout()
        export_row.addStretch()
        self.export_kml_btn = QPushButton("🌍 خروجی KML (گوگل ارث)")
        self.export_kml_btn.setObjectName("KmlExportButton")
        self.export_kml_btn.setMinimumHeight(46)
        self.export_kml_btn.setCursor(Qt.PointingHandCursor)
        self.export_kml_btn.setEnabled(False)
        self.export_kml_btn.clicked.connect(self.export_kml)
        _add_kml_button_shadow(self.export_kml_btn)
        export_row.addWidget(self.export_kml_btn)
        root.addLayout(export_row)

        self._lat = self._lon = self._alt = self._t = None
        self._idx = {}
        data_manager.analysis_ready.connect(self.refresh)

    def refresh(self, _results: dict):
        df = data_manager.flight_df
        if df is None:
            return
        lat = lon = alt = None
        for cand in ("Latitude", "lat"):
            if cand in df.columns:
                lat = df[cand].astype(float).to_numpy(); break
        for cand in ("Longitude", "lon"):
            if cand in df.columns:
                lon = df[cand].astype(float).to_numpy(); break
        for cand in ("GPS_Altitude", "Altitude", "altitude"):
            if cand in df.columns:
                alt = df[cand].astype(float).to_numpy(); break

        if lat is None or lon is None:
            return

        self.map2d.clear()
        self.map2d.plot(lon, lat, pen=pg.mkPen(colors.ALTITUDE, width=2))
        self.map2d.plot([lon[0]], [lat[0]], pen=None, symbol="o", symbolBrush="#35d07f", symbolSize=12)
        self.map2d.plot([lon[-1]], [lat[-1]], pen=None, symbol="x", symbolBrush="#ef5350", symbolSize=12)

        self.card_launch.set_value(f"{lat[0]:.5f}, {lon[0]:.5f}")
        self.card_landing.set_value(f"{lat[-1]:.5f}, {lon[-1]:.5f}")

        # فاصلهٔ خطی (بزرگ‌دایره) بین نقطهٔ پرتاب و نقطهٔ فرود -- فرمول Haversine
        R = 6371000
        phi1, phi2 = np.radians(lat[0]), np.radians(lat[-1])
        dphi = np.radians(lat[-1] - lat[0])
        dlambda = np.radians(lon[-1] - lon[0])
        a = np.sin(dphi / 2) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlambda / 2) ** 2
        distance_m = 2 * R * np.arcsin(np.sqrt(a))
        self.card_distance.set_value(f"{distance_m:.1f} متر")

        if HAS_GL and self.view3d is not None and alt is not None:
            # تبدیل تقریبی lat/lon به متر نسبت به نقطه شروع برای نمایش سه‌بعدی محلی
            x = np.radians(lon - lon[0]) * R * np.cos(np.radians(lat[0]))
            y = np.radians(lat - lat[0]) * R
            z = alt - alt[0]
            pts = np.column_stack([x, y, z])
            self.view3d.items = [i for i in self.view3d.items if isinstance(i, gl.GLGridItem)]
            line = gl.GLLinePlotItem(pos=pts, color=(0.31, 0.82, 0.77, 1.0), width=2, antialias=True)
            self.view3d.addItem(line)

        self._lat, self._lon, self._alt = lat, lon, alt
        try:
            from core.analysis import FlightAnalyzer
            an = FlightAnalyzer(df, data_manager.mission)
            an.detect_events()
            self._idx = getattr(an, "_idx", {}) or {}
            self._t = an.t if an.t is not None else np.arange(len(lat), dtype=float)
        except Exception:
            # این بخش فقط برای خروجی KML لازم است؛ اگر به هر دلیلی خطا بدهد،
            # نباید مانع نمایش نقشه یا کارت‌ها بشود -- فقط دکمهٔ KML غیرفعال می‌ماند
            self._idx = {}
            self._t = np.arange(len(lat), dtype=float)
        else:
            self.export_kml_btn.setEnabled(True)

    # ------------------------------------------------------------------
    def export_kml(self):
        if self._lat is None:
            return
        from core.jalali import jalali_date_for_filename
        from core.paths import build_report_filename
        m = data_manager.mission
        suggested = build_report_filename(
            jalali_date_for_filename(m.jalali_date or m.date),
            m.flight_number or "بدون‌شماره",
            "kml",
        )
        path, _ = QFileDialog.getSaveFileName(self, "خروجی KML", suggested, "KML Files (*.kml)")
        if not path:
            return
        try:
            kml_text = self._build_kml()
            with open(path, "w", encoding="utf-8") as f:
                f.write(kml_text)
        except Exception as exc:
            QMessageBox.warning(self, "خروجی KML ناموفق بود", f"خطا در ساخت فایل KML:\n{exc}")
            return
        QMessageBox.information(self, "خروجی KML آماده شد",
                                 f"فایل با موفقیت ذخیره شد:\n{path}\n\n"
                                 "برای مشاهده، فایل را در Google Earth (Pro یا وب) باز کنید.")

    def _build_kml(self) -> str:
        lat, lon, alt, t = self._lat, self._lon, self._alt, self._t
        n = len(lat)
        alt_for_kml = alt if alt is not None else np.zeros(n)

        launch_idx = self._idx.get("launch") or 0
        apogee_idx = self._idx.get("apogee")
        parachute_idx = self._idx.get("parachute")
        landing_idx = self._idx.get("landing") or (n - 1)

        seg_end_ascent = apogee_idx if apogee_idx is not None else n - 1
        seg_end_freefall = parachute_idx if parachute_idx is not None else seg_end_ascent

        def coord_str(i):
            return f"{lon[i]:.6f},{lat[i]:.6f},{alt_for_kml[i]:.1f}"

        def linestring(i0, i1, color_rgb):
            if i1 <= i0:
                return ""
            coords = " ".join(coord_str(i) for i in range(i0, i1 + 1))
            return f"""
    <Placemark>
      <name>مسیر پرواز</name>
      <Style><LineStyle><color>{_rgb_to_kml(color_rgb)}</color><width>4</width></LineStyle></Style>
      <LineString>
        <altitudeMode>absolute</altitudeMode>
        <coordinates>{coords}</coordinates>
      </LineString>
    </Placemark>"""

        def placemark(i, name, desc, icon_url):
            return f"""
    <Placemark>
      <name>{name}</name>
      <description>{desc}</description>
      <Style><IconStyle><Icon><href>{icon_url}</href></Icon></IconStyle></Style>
      <Point>
        <altitudeMode>absolute</altitudeMode>
        <coordinates>{coord_str(i)}</coordinates>
      </Point>
    </Placemark>"""

        segments = (
            linestring(launch_idx, seg_end_ascent, KML_COLOR_ASCENT) +
            linestring(seg_end_ascent, seg_end_freefall, KML_COLOR_FREEFALL) +
            linestring(seg_end_freefall, n - 1, KML_COLOR_CHUTE)
        )

        markers = placemark(
            launch_idx, "🚀 نقطهٔ پرتاب", "لحظهٔ آغاز پرواز",
            "http://maps.google.com/mapfiles/kml/pushpin/grn-pushpin.png"
        )
        if apogee_idx is not None:
            apogee_alt_agl = float(alt_for_kml[apogee_idx] - alt_for_kml[launch_idx])
            markers += placemark(
                apogee_idx, "🏔 اوج پرواز", f"ارتفاع از نقطهٔ پرتاب: {apogee_alt_agl:.0f} متر",
                "http://maps.google.com/mapfiles/kml/pushpin/ylw-pushpin.png"
            )
        R = 6371000
        phi1, phi2 = np.radians(lat[launch_idx]), np.radians(lat[landing_idx])
        dphi = np.radians(lat[landing_idx] - lat[launch_idx])
        dlambda = np.radians(lon[landing_idx] - lon[launch_idx])
        a = np.sin(dphi / 2) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlambda / 2) ** 2
        landing_dist_m = 2 * R * np.arcsin(np.sqrt(a))
        markers += placemark(
            landing_idx, "🛬 نقطهٔ فرود", f"فاصله از نقطهٔ پرتاب: {landing_dist_m:.0f} متر",
            "http://maps.google.com/mapfiles/kml/pushpin/red-pushpin.png"
        )

        # ---- gx:Track برای امکان پخش زمانی (Time Slider) در گوگل ارث ----
        # چون داده‌ها زمان مطلق واقعی ندارند، از لحظهٔ اجرای این خروجی به‌عنوان
        # مبدأ استفاده و زمان نسبی هر نمونه (ثانیه از پرتاب) به آن اضافه می‌شود
        sample_idx = np.linspace(0, n - 1, min(n, KML_MAX_TRACK_POINTS)).astype(int)
        sample_idx = np.unique(sample_idx)
        base_time = datetime.now(timezone.utc)
        t0 = float(t[launch_idx])

        whens = []
        coords_track = []
        for i in sample_idx:
            when_dt = base_time + timedelta(seconds=float(t[i] - t0))
            whens.append(f"      <when>{when_dt.strftime('%Y-%m-%dT%H:%M:%SZ')}</when>")
            coords_track.append(f"      <gx:coord>{lon[i]:.6f} {lat[i]:.6f} {alt_for_kml[i]:.1f}</gx:coord>")

        alt_values = " ".join(f"{alt_for_kml[i] - alt_for_kml[launch_idx]:.1f}" for i in sample_idx)

        track = f"""
    <Placemark>
      <name>پخش زمانی پرواز</name>
      <Style>
        <IconStyle>
          <Icon><href>http://maps.google.com/mapfiles/kml/shapes/track.png</href></Icon>
          <scale>1.1</scale>
        </IconStyle>
        <LineStyle><color>{_rgb_to_kml((79, 163, 247))}</color><width>3</width></LineStyle>
      </Style>
      <ExtendedData>
        <SchemaData schemaUrl="#flightSchema">
          <gx:SimpleArrayData name="altitude_agl_m">{"".join(f"<gx:value>{v}</gx:value>" for v in alt_values.split())}</gx:SimpleArrayData>
        </SchemaData>
      </ExtendedData>
      <gx:Track>
        <altitudeMode>absolute</altitudeMode>
{chr(10).join(whens)}
{chr(10).join(coords_track)}
      </gx:Track>
    </Placemark>"""

        schema = """
    <Schema id="flightSchema">
      <gx:SimpleArrayField name="altitude_agl_m" type="float">
        <displayName>ارتفاع از پرتاب (متر)</displayName>
      </gx:SimpleArrayField>
    </Schema>"""

        flight_no = data_manager.mission.flight_number or "پرواز"
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2" xmlns:gx="http://www.google.com/kml/ext/2.2">
  <Document>
    <name>مسیر پرواز -- {flight_no}</name>
{schema}
{segments}
{markers}
{track}
  </Document>
</kml>"""

