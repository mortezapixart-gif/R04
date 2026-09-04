# -*- coding: utf-8 -*-
"""
ui/splash_screen.py
----------------------
صفحهٔ خوش‌آمدگویی ابتدای اجرای برنامه -- یک پنجرهٔ مستقل و جدا از پنجرهٔ
اصلی (نه یک بخش داخلی از فیلدهای معمول برنامه، شبیه دیالوگ‌های هشدار)، با
پس‌زمینهٔ فضایی تیره + میدان ستاره، لوگوی کانون، و ۴ خط متن درخواستی:

    ۱) به نرم‌افزار کامپیوتر پرواز خوش آمدید
    ۲) لوگوی کانون علوم و فناوری‌های نوین ایران
    ۳) کانون علوم و فناوری‌های نوین ایران
    ۴) مرکز سمنان

همراه با یک قطعهٔ موزیک کوتاه (حداکثر ۱۰ ثانیه) با فضای علمی/کیهانی که
کاملاً با کد سنتز شده (assets/welcome_theme.wav، بدون هیچ منبع دارای
کپی‌رایت -- نگاه کنید به gen_welcome_theme.py در ریشهٔ پروژه برای اسکریپت
تولید). با کلیک یا فشردن هر کلیدی می‌توان این صفحه را رد کرد.
"""
import os
import sys
import random

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, Signal, QUrl, QPointF
from PySide6.QtGui import QPixmap, QPainter, QRadialGradient, QColor, QLinearGradient

# پشتیبانی نیتیو ویندوز برای پخش تضمینی WAV در فایل exe -- QSoundEffect به
# پلاگین‌های باینری QtMultimedia نیاز داره که PyInstaller خودکار تشخیص و
# بسته‌بندی نمی‌کنه (چون Import معمولی پایتون نیستن، در زمان اجرا به‌صورت
# پویا بارگذاری می‌شن)؛ در نتیجه توی exe ساخته‌شده صدا بی‌صدا پخش نمی‌شه،
# حتی با اینکه با «python main.py» درست کار می‌کنه. winsound یه ماژول
# استاندارد و همیشه-موجود ویندوزه که مستقیم از API نیتیو ویندوز استفاده
# می‌کنه و به هیچ پلاگین Qt وابسته نیست، پس این مشکل رو کاملاً دور می‌زنه.
_HAS_WINSOUND = False
if sys.platform == "win32":
    try:
        import winsound
        _HAS_WINSOUND = True
    except ImportError:
        _HAS_WINSOUND = False

try:
    from PySide6.QtMultimedia import QSoundEffect
    _HAS_MULTIMEDIA = True
except Exception:
    _HAS_MULTIMEDIA = False

from core.paths import asset_path

LOGO_PATH = asset_path("kafna_logo.png")
THEME_PATH = asset_path("welcome_theme.wav")

FADE_IN_MS = 700
HOLD_MS = 8300          # مدت نمایش کامل پیش از شروع محو شدن (هماهنگ با طول موزیک ~۹ ثانیه)
FADE_OUT_MS = 550


class _StarfieldBackground(QWidget):
    """پس‌زمینهٔ فضایی: گرادیان تیرهٔ کیهانی + میدان ستاره‌های چشمک‌زن ملایم."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stars = [
            (random.uniform(0, 1), random.uniform(0, 1),
             random.uniform(0.6, 2.2), random.uniform(0.25, 0.9))
            for _ in range(160)
        ]

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()

        grad = QRadialGradient(QPointF(w * 0.5, h * 0.35), max(w, h) * 0.85)
        grad.setColorAt(0.0, QColor(24, 38, 58))
        grad.setColorAt(0.55, QColor(11, 18, 32))
        grad.setColorAt(1.0, QColor(6, 9, 16))
        painter.fillRect(self.rect(), grad)

        painter.setPen(Qt.NoPen)
        for fx, fy, radius, alpha in self._stars:
            painter.setBrush(QColor(255, 255, 255, int(alpha * 255)))
            painter.drawEllipse(QPointF(fx * w, fy * h), radius, radius)

        # نوار درخشش ملایم افقی نزدیک وسط برای حس «افق کهکشانی»
        band = QLinearGradient(0, h * 0.62, 0, h * 0.72)
        band.setColorAt(0.0, QColor(79, 163, 247, 0))
        band.setColorAt(0.5, QColor(79, 163, 247, 22))
        band.setColorAt(1.0, QColor(79, 163, 247, 0))
        painter.fillRect(0, int(h * 0.60), w, int(h * 0.14), band)


class SplashScreen(QWidget):
    finished = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setFixedSize(760, 520)
        self._center_on_screen()
        self.setWindowOpacity(0.0)

        self._bg = _StarfieldBackground(self)
        self._bg.setGeometry(self.rect())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 46, 40, 46)
        layout.setSpacing(18)
        layout.setAlignment(Qt.AlignCenter)

        self.line1 = QLabel("به نرم‌افزار کامپیوتر پرواز خوش آمدید")
        self.line1.setAlignment(Qt.AlignCenter)
        self.line1.setWordWrap(True)
        self.line1.setStyleSheet(
            "background: transparent; color: #ffffff; font-size: 22px; font-weight: bold;"
        )

        self.logo = QLabel()
        self.logo.setAlignment(Qt.AlignCenter)
        self.logo.setStyleSheet("background: transparent;")
        if os.path.exists(LOGO_PATH):
            pix = QPixmap(LOGO_PATH)
            if not pix.isNull():
                self.logo.setPixmap(pix.scaledToHeight(150, Qt.SmoothTransformation))

        self.line3 = QLabel("کانون علوم و فناوری‌های نوین ایران")
        self.line3.setAlignment(Qt.AlignCenter)
        self.line3.setStyleSheet(
            "background: transparent; color: #4fd1c5; font-size: 17px; font-weight: bold;"
        )

        self.line4 = QLabel("مرکز سمنان")
        self.line4.setAlignment(Qt.AlignCenter)
        self.line4.setStyleSheet(
            "background: transparent; color: #9fb0c3; font-size: 14px;"
        )

        self.hint = QLabel("برای ورود کلیک کنید...")
        self.hint.setAlignment(Qt.AlignCenter)
        self.hint.setStyleSheet("background: transparent; color: #5c6b80; font-size: 11px;")

        for w in (self.line1, self.logo, self.line3, self.line4):
            layout.addWidget(w)
        layout.addSpacing(10)
        layout.addWidget(self.hint)

        # تنظیم سیستم پخش صدا -- روی ویندوز، winsound همیشه در اولویته چون
        # به پلاگین Qt وابسته نیست (نگاه کنید به توضیح بالای فایل)
        self._sound = None
        self._using_winsound = False

        if os.path.exists(THEME_PATH):
            if _HAS_WINSOUND:
                self._using_winsound = True
            elif _HAS_MULTIMEDIA:
                self._sound = QSoundEffect(self)
                self._sound.setSource(QUrl.fromLocalFile(THEME_PATH))
                self._sound.setVolume(0.55)

        self._closing = False
        self._fade_in_anim = None
        self._fade_out_anim = None
        self._hold_timer = QTimer(self)
        self._hold_timer.setSingleShot(True)
        self._hold_timer.timeout.connect(self._start_fade_out)

    def _center_on_screen(self):
        screen = self.screen()
        if screen is None:
            from PySide6.QtGui import QGuiApplication
            screen = QGuiApplication.primaryScreen()
        geo = screen.availableGeometry() if screen else None
        if geo:
            self.move(geo.center().x() - self.width() // 2, geo.center().y() - self.height() // 2)

    def showEvent(self, event):
        super().showEvent(event)

        if self._using_winsound:
            try:
                winsound.PlaySound(THEME_PATH, winsound.SND_FILENAME | winsound.SND_ASYNC)
            except Exception:
                pass
        elif self._sound is not None:
            self._sound.play()

        self._fade_in_anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade_in_anim.setDuration(FADE_IN_MS)
        self._fade_in_anim.setStartValue(0.0)
        self._fade_in_anim.setEndValue(1.0)
        self._fade_in_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._fade_in_anim.start()

        self._hold_timer.start(HOLD_MS)

    def _start_fade_out(self):
        if self._closing:
            return
        self._closing = True

        if self._using_winsound:
            try:
                winsound.PlaySound(None, winsound.SND_PURGE)
            except Exception:
                pass
        elif self._sound is not None:
            self._sound.stop()

        self._fade_out_anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade_out_anim.setDuration(FADE_OUT_MS)
        self._fade_out_anim.setStartValue(self.windowOpacity())
        self._fade_out_anim.setEndValue(0.0)
        self._fade_out_anim.setEasingCurve(QEasingCurve.InCubic)
        self._fade_out_anim.finished.connect(self._finish)
        self._fade_out_anim.start()

    def _finish(self):
        self.finished.emit()
        self.close()

    def mousePressEvent(self, event):
        self._hold_timer.stop()
        self._start_fade_out()

    def keyPressEvent(self, event):
        self._hold_timer.stop()
        self._start_fade_out()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._bg.setGeometry(self.rect())
