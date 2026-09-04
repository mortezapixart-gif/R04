# -*- coding: utf-8 -*-
"""سیستم tooltip اختصاصی برنامه -- جایگزین کامل پنجرهٔ tooltip پیش‌فرض Qt.

چرا این مسیر؟ پنجرهٔ tooltip در Qt (کلاس خصوصی QTipLabel) برای استایل‌دادن
ذاتاً ناپایدار است (تجربهٔ چهار تلاش ناموفق + سورس Qt):
  * سازنده فقط یک‌بار «setPalette(QToolTip::palette())» می‌زند؛
  * اما placeTip در «هر» نمایش «setStyleSheet("/* */")» رویش می‌زند و هر
    استایلی را که گذاشته باشیم پاک می‌کند؛
  * رنگ نهایی بسته به مسیر پالت/استایل‌شیت و زمان‌بندی polish فرق می‌کرد
    (همان «گاهی سیاه، گاهی خاکستری»).

راه‌حل قطعی: اصلاً به QTipLabel اجازهٔ ساخته‌شدن نمی‌دهیم. رویداد ToolTip
در سطح برنامه مصرف (return True) می‌شود و به‌جایش یک QLabel از خودمان --
با استایل ثابت و کاملاً تحت‌کنترل -- کنار نشانگر نمایش داده می‌شود. رنگ در
«همهٔ» برنامه و در «همهٔ» دفعات یکسان است، چون فقط یک پیاده‌سازی وجود دارد.
"""
from PySide6.QtCore import QObject, Qt, QTimer, QEvent
from PySide6.QtGui import QGuiApplication, QFont
from PySide6.QtWidgets import QLabel, QGraphicsDropShadowEffect

from ui.style import APP_FONT_FAMILY

# استایل باکس توضیح -- تنها منبع حقیقت؛ همان خاکستری هماهنگ با تم برنامه.
# نکته: qproperty-alignment حیاتی است -- APP_QSS برای «همهٔ» QLabelها تراز
# AlignCenter می‌گذارد (قاعدهٔ سراسری QLabel) و در لحظهٔ polish ترازِ
# سازنده را له می‌کرد (بازتولید پیکسلی: alignment=132 وسط‌چین!). استایل‌شیتِ
# خودِ ویجت در آبشار QSS بر قاعدهٔ سراسری مقدم است؛ برای همین اینجا صریحاً
# همان تراز مطلق راست را اعلان می‌کنیم.
TIP_STYLE = ("background-color:#232b38; color:#e6ebf1;"
             " border:1px solid #3d4a5c; border-radius:6px;"
             " padding:8px 12px; font-size:13px;"
             " qproperty-alignment: 'AlignRight | AlignVCenter | AlignAbsolute';")
_MAX_WIDTH = 480          # متن‌های طولانی می‌شکنند (word wrap)


class _TipLabel(QLabel):
    """پنجرهٔ tooltip از جنس QLabel خودمان -- استایل‌ش همیشه برقرار است."""

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint
                            | Qt.WindowTransparentForInput)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setStyleSheet(TIP_STYLE)
        self.setFont(QFont(APP_FONT_FAMILY, 9))
        # نکتهٔ حیاتی (اثبات‌شده با آزمون پیکسلی offscreen): در مسیر rich text
        # سندِ متن همیشه به گوشهٔ «چپِ» لیبل میخکوب می‌شود (painter.translate(
        # lr.topLeft())) و تراز لیبل هیچ اثری بر آن ندارد؛ حتی با عرض مینیمالِ
        # سند، فضای مرده سمت راست می‌ماند. اما در مسیر «متن ساده» ترازِ خود
        # لیبل مستقیماً و کامل حاکم است (drawItemText با align|ForceRTL)؛
        # بنابراین متن ساده + تراز مطلق راست = راست‌چین قطعی.
        self.setTextFormat(Qt.PlainText)
        # نکتهٔ حیاتی (سورس qlabel.cpp): در sizeForWidth و paintEvent تراز از
        # مسیر QStyle::visualAlignment(textDirection(), align) می‌گذرد؛ اگر
        # جهتِ لیبل RTL باشد و پرچم AlignAbsolute ست نباشد، Qt تراز را
        # «آینه» می‌کند (AlignRight -> AlignLeft دیداری) و آن‌گاه همان ترازِ
        # تبدیل‌شده به موتور متن تحمیل می‌شود -- دقیقاً علت چپ‌چین‌ماندن با وجود
        # align="right" در HTML. پرچم AlignAbsolute این آینه‌شدن را خنثی می‌کند
        # (مستندات Qt::AlignmentFlag) و QLabel آن را حفظ می‌کند چون داخل
        # AlignHorizontal_Mask است.
        self.setAlignment(Qt.AlignRight | Qt.AlignVCenter | Qt.AlignAbsolute)
        self.setWordWrap(True)
        self.setMaximumWidth(_MAX_WIDTH)
        self.setLayoutDirection(Qt.RightToLeft)
        # سایهٔ نرم زیر باکس -- عمق و خوانایی بهتر روی صفحات
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(18)
        shadow.setOffset(0, 2)
        from PySide6.QtGui import QColor as _QC
        shadow.setColor(_QC(0, 0, 0, 170))
        self.setGraphicsEffect(shadow)
        self._expire = QTimer(self)
        self._expire.setSingleShot(True)
        self._expire.timeout.connect(self.hide)

    def showEvent(self, event):
        super().showEvent(event)
        # سپر دوم: polish (جایی که QSS سراسری اجرا می‌شود) قبل از Show است؛
        # اینجا دوباره تراز را ست می‌کنیم تا هیچ قاعدهٔ QSS ای نتواند لهش کند.
        self.setAlignment(Qt.AlignRight | Qt.AlignVCenter | Qt.AlignAbsolute)

    def popup(self, text: str, global_pos):
        # متن سادهٔ اصلی -- خطوط خالی همان فاصله‌گذاری بخش‌ها هستند و
        # بولت‌های «•» در پاراگراف راست‌به‌چپ خودبه‌خود سمت راست می‌افتند.
        self.setText(text)
        self.adjustSize()
        screen = QGuiApplication.screenAt(global_pos) or QGuiApplication.primaryScreen()
        avail = screen.availableGeometry()
        x = global_pos.x() + 14
        y = global_pos.y() + 18
        if x + self.width() > avail.right():
            x = max(avail.left(), global_pos.x() - self.width() - 14)
        if y + self.height() > avail.bottom():
            y = max(avail.top(), global_pos.y() - self.height() - 18)
        self.move(x, y)
        self.show()
        self.raise_()
        # مثل Qt: مدت نمایش با طول متن کمی بیشتر می‌شود
        self._expire.start(12000 + 40 * max(0, len(text) - 100))


class ToolTipManager(QObject):
    """مدیر سراسری tooltip: رویداد ToolIP ویجت‌ها را مصرف و لیبل خودمان را
    نشان می‌دهد؛ با خروج موس/کلیک/کلید/چرخ، پنهان می‌شود."""

    def __init__(self, app):
        super().__init__(app)
        self._tip = _TipLabel()
        self._source = None      # ویجتی که tooltip اش نمایش داده شده

    def eventFilter(self, obj, event):
        # سپر دفاعی: فیلترِ سطح برنامه هرگز نباید exception بدهد (حتی اگر
        # ویجت مبدأ هم‌زمان destroy شده باشد و مقایسه/فراخوانی شکست بخورد).
        try:
            return self._handle(obj, event)
        except Exception:
            return False

    def _handle(self, obj, event):
        kind = event.type()
        if kind == QEvent.ToolTip:
            try:
                text = obj.toolTip()
            except (AttributeError, RuntimeError):
                return False
            if text:
                self._source = obj
                self._tip.popup(text, event.globalPos())
                return True            # QTipLabel هرگز ساخته نمی‌شود
            self._tip.hide()
            return False
        # پنهان‌سازی: خروج از ویجتِ مبدأ یا تعامل کاربر
        # (نام درست رویداد «Destroy» است؛ «Destroyed» نام سیگنالِ QObject است
        # و به‌عنوان QEvent.Type وجود ندارد.)
        if obj is self._source and kind in (QEvent.Leave, QEvent.Hide, QEvent.Destroy):
            self._tip.hide()
            self._source = None
            return False
        if kind in (QEvent.MouseButtonPress, QEvent.MouseButtonDblClick,
                    QEvent.Wheel, QEvent.KeyPress):
            if self._tip.isVisible():
                self._tip.hide()
                self._source = None
        return False


def install(app) -> ToolTipManager:
    """نصب روی QApplication -- از این به بعد همهٔ tooltipهای برنامه از همین
    یک پیاده‌سازی می‌آیند (رنگ یکسان، همه‌جا، همیشه)."""
    manager = ToolTipManager(app)
    app.installEventFilter(manager)
    app.setProperty("_tooltip_manager", manager)   # مرجع نگه‌داشته شود
    return manager
