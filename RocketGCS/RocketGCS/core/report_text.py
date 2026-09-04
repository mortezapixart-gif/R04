# -*- coding: utf-8 -*-
"""
core/report_text.py
-------------------
لایهٔ «متن و قالب‌بندی فارسی» گزارش -- مشترک بین گزارش PDF
(core/hud_report.py) و صفحهٔ گزارش (pages/report.py).

چرا این فایل جدا شده است؟ قبلاً همهٔ این توابع داخل pages/report.py
بودند و همان فایل در بخش پایینی‌اش PySide6 را import می‌کرد؛ در نتیجه
core/hud_report.py (که فقط matplotlib لازم دارد) برای تولید PDF مجبور بود
کل Qt را با خودش بارکند. یعنی موتورِ گزارش به UI وابسته بود و نمی‌شد آن را
جداگانه به برنامهٔ دیگری منتقل کرد.

این ماژول **هیچ وابستگی‌ای به Qt ندارد** (فقط stdlib + matplotlib +
arabic_reshaper/python-bidi اختیاری + core/jalali)؛ پس هم در برنامهٔ اصلی و
هم در هر برنامهٔ دیگری که فقط خروجی PDF/اکسل می‌خواهد قابل استفاده است.
"""
import os
import datetime

# ------------------------------------------------------------
# کتابخانه‌های تصحیح متن فارسی (Reshape + BiDi) برای نمودارهای Matplotlib
# ------------------------------------------------------------
# توجه: نصب خودکار این پکیج‌ها با subprocess در زمان اجرا (روش قبلی) در
# نسخهٔ Build/exe شده با PyInstaller کار نمی‌کند، چون sys.executable در آن
# حالت خودِ RocketGCS.exe است نه پایتون -- و pip هم داخل exe وجود ندارد.
# نتیجه: import ساکت fail می‌شد و fa_text() بدون reshape/bidi به متن خام
# برمی‌گشت، که همان بهم‌ریختگی حروف فارسی داخل نمودارهای PDF بود.
# راه‌حل درست: این دو پکیج در requirements.txt و hiddenimports مربوط به
# RocketGCS.spec اضافه شده‌اند تا همیشه همراه برنامه باشند؛ اینجا فقط
# import می‌کنیم و در صورت نبودن (مثلاً اجرای دستی بدون pip install -r
# requirements.txt) با پیام روشن خطا می‌دهیم به‌جای بهم‌ریختگی خاموش.
# وارد کردن arabic_reshaper و get_display به‌صورت مستقل از هم، چون این دو
# پکیج مسیرهای خرابی کاملاً متفاوتی دارند و قاطی‌کردنشان در یک try واحد،
# علت واقعی را پنهان می‌کرد:
#
#   * arabic_reshaper یک پکیج خالص پایتون است (py3-none-any) و عملاً
#     همیشه نصب می‌شود.
#   * python-bidi از نسخهٔ ۰.۵ به بعد یک اکستنشن کامپایل‌شدهٔ Rust است و
#     برای هر نسخهٔ پایتون به wheel جداگانه نیاز دارد. برای Python 3.14
#     تنها از نسخهٔ ۰.۶.۹ به بعد wheel ویندوزی منتشر شده؛ چون
#     requirements.txt سقف نداشت (python-bidi>=0.4.2)، در عمل ممکن است
#     نسخه‌ای نصب/کش شده باشد که روی ۳.۱۴ قابل ساخت نیست و import آن
#     شکست بخورد -- که نتیجه‌اش دقیقاً همان «ش ر ا ز گ» بود.
#
# برای اینکه گزارش هرگز به‌خاطر نبودِ یک پکیج باینری خراب تولید نشود، یک
# پیاده‌سازی جایگزین خالص پایتون (_fallback_bidi) هم اضافه شده است.
try:
    import arabic_reshaper
    _RESHAPER_AVAILABLE = True
    _RESHAPER_ERROR = ""
except Exception as _e:            # نه فقط ImportError -- خطای زمان بارگذاری هم مهم است
    _RESHAPER_AVAILABLE = False
    _RESHAPER_ERROR = f"{type(_e).__name__}: {_e}"

# python-bidi هر دو API را دارد: bidi.algorithm.get_display (پیاده‌سازی
# پایتون، سازگار با نسخه‌های قدیمی) و bidi.get_display (پیاده‌سازی Rust).
# اولی را ترجیح می‌دهیم چون خالص پایتون است و در نسخه‌های جدید هم باقی مانده.
get_display = None
_BIDI_ERROR = ""
for _import_path in ("algorithm", "top_level"):
    try:
        if _import_path == "algorithm":
            from bidi.algorithm import get_display as _gd
        else:
            from bidi import get_display as _gd
        get_display = _gd
        _BIDI_ERROR = ""
        break
    except Exception as _e:
        _BIDI_ERROR = f"{type(_e).__name__}: {_e}"

_BIDI_IS_FALLBACK = False
if get_display is None:
    # ---- پیاده‌سازی جایگزین خالص پایتون از الگوریتم دوسویه ----
    # این یک BiDi کامل مطابق UAX#9 نیست، اما برای محتوای گزارش (متن فارسی
    # با اعداد/واحدهای لاتین مثل «157.2 m/s») دقیقاً همان نتیجهٔ درست را
    # می‌دهد: ترتیب کاراکترهای راست‌به‌چپ معکوس می‌شود، در حالی که
    # دنباله‌های لاتین/عددی به‌صورت واحد و با ترتیب داخلی خودشان می‌مانند.
    import re as _re
    _RTL_RE = _re.compile(r"[\u0590-\u05FF\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]")
    # دنبالهٔ «خنثی/چپ‌به‌راست» که باید به‌عنوان یک بلوک جابه‌جا شود.
    # بلوک LRE..PDF (عدد+واحد لاتین قفل‌شده) یک توکن اتمی است تا reverse
    # نتواند «5.5» را از «m/s» جدا کند.
    _LTR_RUN_RE = _re.compile(
        r"\u202A[^\u202C]*\u202C|[A-Za-z0-9]+(?:[.,:/_+\-%][A-Za-z0-9]+)*"
    )
    _MIRROR = {"(": ")", ")": "(", "[": "]", "]": "[", "{": "}", "}": "{",
               "<": ">", ">": "<", "«": "»", "»": "«"}

    def get_display(text, *args, **kwargs):   # noqa: F811 -- جایگزین عمدی
        if not text:
            return text
        tokens, last = [], 0
        for m in _LTR_RUN_RE.finditer(text):
            tokens.extend(text[last:m.start()])
            tokens.append(m.group())          # کل دنبالهٔ لاتین = یک توکن اتمی
            last = m.end()
        tokens.extend(text[last:])
        tokens.reverse()
        return "".join(_MIRROR.get(t, t) if len(t) == 1 else t for t in tokens)

    _BIDI_IS_FALLBACK = True

_FA_TEXT_AVAILABLE = _RESHAPER_AVAILABLE and get_display is not None

# اگر import موفق باشد ولی خودِ reshape/get_display موقع اجرا خطا بدهد
# (مثلاً به‌خاطر تفاوت نسخهٔ پکیج در ویندوز)، fa_text() قبلاً این خطا را
# کاملاً بی‌صدا می‌بلعید و بدون هیچ هشداری متن خام (بهم‌ریخته) برمی‌گرداند.
# این دو متغیر آخرین خطای واقعی را برای تشخیص/نمایش در UI نگه می‌دارند.
_FA_TEXT_LAST_ERROR = None
_FA_TEXT_RUNTIME_OK = None  # None = هنوز تست نشده؛ بعد از اولین self-test مقداردهی می‌شود

# استفاده از ماژول داخلی پروژه برای تبدیل تاریخ
from core.jalali import gregorian_date_to_jalali_str
from core.paths import asset_path as _project_asset_path


def get_asset_path(filename: str) -> str:
    """مسیر یک فایل داخل پوشهٔ assets -- با تکیه بر core/paths.py (سازگار با
    هر دو حالت اجرای عادی و نسخهٔ فریزشدهٔ PyInstaller). اگر فایل پیدا نشد
    رشتهٔ خالی برمی‌گردد و فراخوان‌کننده‌ها (لوگو/فونت) بدون آن هم کار می‌کنند.
    """
    p = _project_asset_path(filename)
    return p if os.path.exists(p) else ""


def _matplotlib_shapes_natively() -> bool:
    """آیا خودِ matplotlib توانایی شکل‌دهی متن پیچیده (فارسی/عربی) را دارد؟

    از matplotlib 3.7 به بعد، اگر هنگام ساخت wheel کتابخانهٔ libraqm در
    دسترس باشد، matplotlib کل کار «شکل‌دهی حروف + الگوریتم دوسویه» را
    خودش با HarfBuzz/FriBiDi انجام می‌دهد (نگاه کنید به FT2Font._layout).
    wheel های رسمی matplotlib روی PyPI از نسخهٔ ۳.۱۱ با libraqm ساخته
    می‌شوند.

    این موضوع حیاتی است: اگر matplotlib خودش شکل‌دهی کند و ما هم *از قبل*
    متن را با arabic_reshaper + python-bidi پردازش کرده باشیم، متن **دو
    بار** پردازش می‌شود -- ترتیب یک بار توسط ما و یک بار توسط libraqm
    معکوس می‌شود (یعنی به حالت اول برمی‌گردد) و شکل‌های نمایشیِ
    از پیش‌ساختهٔ ما دوباره شکل‌دهی می‌شوند. نتیجهٔ دقیقش همان چیزی است
    که در گزارش دیده شد: «ﺵﺭﺍﺰﮔ» به‌جای «گزارش».

    پس: اگر libraqm موجود باشد باید متن **خام** به matplotlib داده شود.
    """
    try:
        from matplotlib import ft2font
        return hasattr(ft2font, "__libraqm_version__")
    except Exception:
        return False


_MPL_NATIVE_SHAPING = _matplotlib_shapes_natively()



# ------------------------------------------------------------
# واحد لاتین باید سمت راست عدد بماند (نه «m/s 5.5»).
# واحد فارسی (متر، ثانیه، کیلوگرم، ٪) دست نخورده می‌ماند -- مثل گزارش اکسل.
# ------------------------------------------------------------
import re as _re_qty

_LRE, _PDF, _NBSP = "\u202A", "\u202C", "\u00A0"
# فاصلهٔ داخل پرانتز: در متن راست‌به‌چپ matplotlib/Shabnam، پرانتزِ چپ
# بدون فاصله روی رقم/حرف می‌نشیند. NBSP هم فاصله است هم با split خط نمی‌شکند.
_PAD = "\u00A0"
# طولانی‌ترین واحد اول تا m/s² قبل از m و s جدا match نشود
_LATIN_UNIT = (
    r"m/s²|m/s2|km/h|°C/km|deg/s|N·s|N\.s|kg/m³|W/m²|"
    r"kPa|kJ|hPa|m/s|°C|%RH|mm|cm|kg|Pa|Hz|bar|deg|dBm|rpm|"
    r"m|s|g|J|N|V|x|%"
)
_NUM = (
    r"[+\u2212\-]?"
    r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
    r"|[۰-۹٠-٩]+(?:[٫.][۰-۹٠-٩]+)?"
)
_QTY_RE = _re_qty.compile(
    rf"(?<!\u202A)({_NUM})\s*({_LATIN_UNIT})(?![A-Za-z²³])"
)
# (132.0 m/s) یا (475.2 km/h) -- پرانتز داخل همان بلوک LTR با فاصله
_PAREN_QTY_RE = _re_qty.compile(
    rf"\((?!\u202A)\s*({_NUM})\s*({_LATIN_UNIT})(?![A-Za-z²³])\s*\)"
)
_PAREN_UNIT_RE = _re_qty.compile(
    rf"\((?!\u202A)\s*({_LATIN_UNIT})\s*\)"
)
# (Max G) / (AHT−BMP) -- لاتین بدون حرف فارسی
_PAREN_LATIN_RE = _re_qty.compile(
    r"\((?!\u202A)([^()\u0600-\u06FF]*[A-Za-z][^()\u0600-\u06FF]*)\)"
)
# (اوج) / (لحظه پرتاب) -- فاصله تا پرانتز روی حرف ننشیند
_PAREN_FA_RE = _re_qty.compile(
    r"\((?!\u202A)([^()]*[\u0600-\u06FF][^()]*)\)"
)

_ISOLATE_RE = _re_qty.compile(r"\u202A[^\u202C]*\u202C")


def _sub_outside_isolates(regex, repl, text: str) -> str:
    """جایگزینی فقط بیرون بلوک‌های LRE..PDF (تا تو در تو ساخته نشود)."""
    parts, last = [], 0
    for m in _ISOLATE_RE.finditer(text):
        parts.append(regex.sub(repl, text[last:m.start()]))
        parts.append(m.group())
        last = m.end()
    parts.append(regex.sub(repl, text[last:]))
    return "".join(parts)


def _protect_chunk(chunk: str) -> str:
    """یک تکهٔ خارج از LRE را قفل می‌کند (داخل isolate دست نمی‌زنیم)."""
    def paren_qty(m):
        return f"{_LRE}({_PAD}{m.group(1)}{_NBSP}{m.group(2)}{_PAD}){_PDF}"

    def qty(m):
        return f"{_LRE}{m.group(1)}{_NBSP}{m.group(2)}{_PDF}"

    def paren_unit(m):
        return f"{_LRE}({_PAD}{m.group(1)}{_PAD}){_PDF}"

    def paren_latin(m):
        inner = m.group(1).strip()
        return f"{_LRE}({_PAD}{inner}{_PAD}){_PDF}"

    def paren_fa(m):
        inner = m.group(1).strip()
        return f"({_PAD}{inner}{_PAD})"

    out = _sub_outside_isolates(_PAREN_QTY_RE, paren_qty, chunk)
    out = _sub_outside_isolates(_QTY_RE, qty, out)
    out = _sub_outside_isolates(_PAREN_UNIT_RE, paren_unit, out)
    out = _sub_outside_isolates(_PAREN_LATIN_RE, paren_latin, out)
    return _sub_outside_isolates(_PAREN_FA_RE, paren_fa, out)


def _pad_bare_parens(text: str) -> str:
    """فاصله بعد از «(» و قبل از «)» اگر به حرف/رقم/بلوک چسبیده باشند.

    حتی اگر پرانتز بیرون isolate مانده باشد (مثل «(۳ تا ۸ m/s)») پرانتز
    روی رقم نمی‌نشیند. دوباره‌اعمال بی‌اثر است.
    """
    out = []
    skip = {_PAD, " ", "\t", "\n"}
    for i, ch in enumerate(text):
        if ch == "(":
            out.append("(")
            nxt = text[i + 1] if i + 1 < len(text) else ""
            if nxt and nxt not in skip and nxt != ")":
                out.append(_PAD)
            continue
        if ch == ")":
            prev = out[-1] if out else ""
            if prev and prev not in skip and prev != "(":
                out.append(_PAD)
            out.append(")")
            continue
        out.append(ch)
    return "".join(out)


def protect_latin_quantities(text: str) -> str:
    """عدد + واحد لاتین را یک بلوک چپ‌به‌راست می‌کند تا در RTL جابه‌جا نشوند.

    بین عدد و واحد NBSP می‌گذارد تا شکستن خط آن‌ها را جدا نکند، بعد با
    LRE..PDF می‌پوشاند. پرانتز دور عدد/واحد هم داخل همان بلوک می‌رود و
    دو طرفش فاصله می‌گیرد تا در RTL روی رقم ننشیند. واحد فارسی را لمس
    نمی‌کند. دوباره‌اعمال بی‌اثر است.
    """
    if not text or not isinstance(text, str):
        return text
    parts, last = [], 0
    for m in _ISOLATE_RE.finditer(text):
        parts.append(_protect_chunk(text[last:m.start()]))
        parts.append(m.group())
        last = m.end()
    parts.append(_protect_chunk(text[last:]))
    return _pad_bare_parens("".join(parts))


def fa_text(text: str) -> str:
    """آماده‌سازی متن فارسی برای رسم در Matplotlib.

    دو حالت کاملاً متفاوت دارد:

    ۱) matplotlib با libraqm ساخته شده (نسخه‌های جدید، از جمله ۳.۱۱):
       خودش شکل‌دهی و ترتیب راست‌به‌چپ را انجام می‌دهد، پس متن باید
       **دست‌نخورده** تحویلش شود. هر پیش‌پردازشی اینجا نتیجه را خراب
       می‌کند (پردازش دوباره).

    ۲) matplotlib بدون libraqm (نسخه‌های قدیمی‌تر):
       هیچ پشتیبانی‌ای از متن پیچیده ندارد، پس خودمان باید با
       arabic_reshaper + python-bidi متن را آماده کنیم.
    """
    if not text:
        return ""
    text = protect_latin_quantities(str(text))
    if _MPL_NATIVE_SHAPING:
        # matplotlib خودش شکل‌دهی می‌کند -- فقط کمیت لاتین را قفل کرده‌ایم
        # تا واحد سمت راست عدد بماند (LRE در رشتهٔ خام، نه get_display).
        return text
    if not _FA_TEXT_AVAILABLE:
        # نه matplotlib توانایی‌اش را دارد و نه پکیج‌های کمکی موجودند --
        # متن خام برمی‌گردد و حروف جدا از هم نمایش داده می‌شوند.
        return text
    global _FA_TEXT_LAST_ERROR
    try:
        reshaped = arabic_reshaper.reshape(text)
        return get_display(reshaped)
    except Exception as e:
        # قبلاً این خطا کاملاً بی‌صدا بلعیده می‌شد -- حالا حداقل ثبت می‌شود
        # تا fa_text_selftest() و پیام هشدار UI بتوانند علت واقعی را نشان دهند.
        _FA_TEXT_LAST_ERROR = f"{type(e).__name__}: {e}"
        return str(text)


def fa_text_selftest() -> tuple[bool, str]:
    """آزمایش واقعی (نه فقط بررسی import) که آیا اصلاح متن فارسی واقعاً کار
    می‌کند یا نه -- چون ممکن است import موفق باشد ولی خودِ reshape/bidi موقع
    اجرا (مثلاً روی ویندوز، به‌خاطر تفاوت نسخهٔ پکیج) خطا بدهد و fa_text()
    بدون هیچ نشانه‌ای به متن خام سقوط کند. خروجی: (سالم است؟, پیام تشخیصی)."""
    global _FA_TEXT_LAST_ERROR, _FA_TEXT_RUNTIME_OK

    if _MPL_NATIVE_SHAPING:
        # matplotlib خودش (با libraqm) شکل‌دهی و ترتیب دوسویه را انجام
        # می‌دهد؛ arabic_reshaper/python-bidi اصلاً استفاده نمی‌شوند و
        # نبودشان هم مشکلی ایجاد نمی‌کند.
        from matplotlib import ft2font
        _FA_TEXT_RUNTIME_OK = True
        return True, (
            "سالم -- شکل‌دهی متن فارسی توسط خودِ matplotlib انجام می‌شود "
            f"(libraqm نسخهٔ {ft2font.__libraqm_version__})."
        )

    if not _RESHAPER_AVAILABLE:
        # این حالت واقعاً کشنده است: بدون reshaper حروف هرگز به هم نمی‌چسبند
        # و خروجی به‌شکل «ش ر ا ز گ» در می‌آید.
        _FA_TEXT_RUNTIME_OK = False
        return False, (
            "پکیج arabic-reshaper بارگذاری نشد -- حروف فارسی به‌هم نمی‌چسبند.\n"
            f"علت فنی: {_RESHAPER_ERROR}\n"
            "راه‌حل:  pip install --upgrade --force-reinstall arabic-reshaper"
        )

    sample = "گزارش"  # باید در خروجی درست، حروف به‌هم‌چسبیده و ترتیب راست‌به‌چپ داشته باشد
    _FA_TEXT_LAST_ERROR = None
    try:
        reshaped = arabic_reshaper.reshape(sample)
        result = get_display(reshaped)
    except Exception as e:
        _FA_TEXT_RUNTIME_OK = False
        return False, f"{type(e).__name__}: {e}"

    # بررسی دقیق‌تر از «فقط متفاوت بودن با ورودی»: خروجی درست باید حاوی
    # «شکل‌های نمایشی» (Arabic Presentation Forms، بازه‌های U+FB50..U+FDFF و
    # U+FE70..U+FEFF) باشد. اگر همهٔ حروف هنوز به‌شکل پایه (U+0600..U+06FF)
    # باشند، یعنی reshape انجام نشده و خروجی «ش ر ا ز گ» خواهد شد -- حتی اگر
    # ترتیبشان با ورودی فرق داشته باشد.
    if not result:
        _FA_TEXT_RUNTIME_OK = False
        return False, "خروجی reshape/bidi خالی بود."

    has_presentation = any(0xFB50 <= ord(c) <= 0xFDFF or 0xFE70 <= ord(c) <= 0xFEFF
                            for c in result)
    if not has_presentation:
        _FA_TEXT_RUNTIME_OK = False
        return False, (
            "حروف فارسی شکل‌دهی نشدند (خروجی فاقد Arabic Presentation Forms است) -- "
            "متن گزارش به‌صورت حروف جدا از هم نمایش داده می‌شود.\n"
            "راه‌حل:  pip install --upgrade --force-reinstall arabic-reshaper python-bidi"
        )

    _FA_TEXT_RUNTIME_OK = True
    if _BIDI_IS_FALLBACK:
        # شکل‌دهی حروف درست است و ترتیب هم با پیاده‌سازی داخلی اصلاح می‌شود؛
        # گزارش کاملاً خوانا تولید می‌شود، پس این خطا نیست -- فقط اطلاع‌رسانی.
        return True, (
            "سالم (با پیاده‌سازی داخلیِ ترتیب دوسویه -- پکیج python-bidi بارگذاری نشد.\n"
            f"علت فنی: {_BIDI_ERROR}\n"
            "برای استفاده از پیادهٔ رسمی:  pip install --upgrade python-bidi)"
        )
    return True, "سالم"


def to_jalali_date(date_val) -> str:
    """تبدیل تاریخ میلادی یا رشته‌ای به تاریخ شمسی با ماژول داخلی پروژه"""
    if not date_val or str(date_val).strip().lower() in ["none", "", "null"]:
        return "--"
    
    s = str(date_val).strip()
    if s.startswith(("13", "14")):
        return s

    try:
        for fmt in ["%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%Y"]:
            try:
                dt = datetime.datetime.strptime(s.split()[0], fmt).date()
                return gregorian_date_to_jalali_str(dt)
            except ValueError:
                continue
    except Exception:
        pass

    return s

# دیکشنری ترجمه اصطلاحات فنی به فارسی
TERM_TRANSLATIONS = {
    "max_altitude": "حداکثر ارتفاع (اوج)",
    "max_velocity": "حداکثر سرعت پرواز",
    "velocity_at_burnout": "سرعت در لحظه پایان سوخت",
    "landing_velocity": "سرعت برخورد به زمین (فرود)",
    "max_g": "حداکثر شتاب جی (Max G)",
    "accel_at_landing": "شتاب در لحظه برخورد به زمین",
    "ground_temperature_c": "دمای سطح زمین (لحظه پرتاب)",
    "apogee_temperature_c": "دمای محیط در اوج پرواز",
    # --- رطوبت / UV / اختلاف سنسورها (پیش از این به‌صورت انگلیسی در جدول
    #     «شاخص‌های محیطی و فرود» گزارش PDF می‌نشستند) ---
    "ground_humidity_percent": "رطوبت سطح زمین (لحظه پرتاب)",
    "apogee_humidity_percent": "رطوبت در اوج پرواز",
    "humidity_min_percent": "کمینه رطوبت در طول پرواز",
    "humidity_max_percent": "بیشینه رطوبت در طول پرواز",
    "ground_uv_index": "شاخص تشعشع UV روی زمین (لحظه پرتاب)",
    "apogee_uv_index": "شاخص تشعشع UV در اوج پرواز",
    "uv_index_max": "بیشینه شاخص تشعشع UV",
    "aht_bmp_temp_diff_c": "اختلاف دمای سنسور رطوبت و فشار (AHT−BMP)",
    "estimated_Cd": "ضریب پسا (دراگ) برآوردی از داده",
    "temperature_lapse_rate_c_per_km": "نرخ افت دما با ارتفاع (Lapse Rate)",
    "mpu_self_heating_offset_c": "اختلاف دمای سنسورها (Self-Heating)",
    "dynamic_pressure_max": "حداکثر فشار دینامیکی (Max Q)",
    "max_q_time": "زمان وقوع حداکثر فشار دینامیکی",
    "max_q_velocity": "سرعت در لحظه Max Q",
    "estimated Cd": "ضریب درگ تخمینی راکت (Cd)",
    "parachute_deploy_altitude": "ارتفاع باز شدن چتر نجات",
    "parachute_deploy_time": "زمان باز شدن چتر نجات",
    "velocity_before_chute": "سرعت قبل از باز شدن چتر",
    "velocity_after_chute": "سرعت تثبیت‌شده پس از باز شدن چتر",
    "descent_rate_reduction": "نسبت کاهش سرعت توسط چتر",
    "impact_energy_j": "انرژی جنبشی برخورد به زمین",
    "chute_suggestion": "ارزیابی عملکرد سامانه بازیابی",
}


def format_metric_value(key: str, val) -> str:
    """فرمت‌دهی مقادیر عددی برای جلوگیری از بهم‌ریختگی ترکیب عدد و واحد."""
    if val is None or str(val).strip().lower() in ["none", "", "null"]:
        return "--"

    try:
        num = float(val)
        is_num = True
    except (ValueError, TypeError):
        is_num = False
        num = 0.0

    velocity_keys = [
        "max_velocity", "velocity_at_burnout", "landing_velocity",
        "max_q_velocity", "velocity_before_chute", "velocity_after_chute"
    ]

    if key in velocity_keys and is_num:
        ms = num
        kmh = num * 3.6
        return protect_latin_quantities(f"{ms:.1f} m/s ({kmh:.1f} km/h)")

    if key == "max_altitude" and is_num:
        return protect_latin_quantities(f"{num:.1f} m")
    if key == "max_g" and is_num:
        return protect_latin_quantities(f"{num:.2f} g")
    if key == "accel_at_landing" and is_num:
        return protect_latin_quantities(f"{num:.2f} g")
    if key == "ground_temperature_c" and is_num:
        return protect_latin_quantities(f"{num:.1f} °C")
    if key == "apogee_temperature_c" and is_num:
        return protect_latin_quantities(f"{num:.1f} °C")
    if key == "temperature_lapse_rate_c_per_km" and is_num:
        return protect_latin_quantities(f"{num:.2f} °C/km")
    if key == "mpu_self_heating_offset_c" and is_num:
        return protect_latin_quantities(f"{num:+.1f} °C")
    if key == "aht_bmp_temp_diff_c" and is_num:
        return protect_latin_quantities(f"{num:+.1f} °C")
    if key in ("ground_humidity_percent", "apogee_humidity_percent",
               "humidity_min_percent", "humidity_max_percent") and is_num:
        return protect_latin_quantities(f"{num:.0f} %")
    if key in ("ground_uv_index", "apogee_uv_index", "uv_index_max") and is_num:
        return f"{num:.1f}"
    if key == "estimated_Cd" and is_num:
        return f"{num:.2f}"
    if key == "dynamic_pressure_max" and is_num:
        if num >= 1000:
            return protect_latin_quantities(f"{num/1000:.2f} kPa ({num:.0f} Pa)")
        return protect_latin_quantities(f"{num:.1f} Pa")
    if key == "max_q_time" and is_num:
        return protect_latin_quantities(f"{num:.2f} s")
    if key == "parachute_deploy_altitude" and is_num:
        return protect_latin_quantities(f"{num:.1f} m")
    if key == "parachute_deploy_time" and is_num:
        return protect_latin_quantities(f"{num:.2f} s")
    if key == "descent_rate_reduction" and is_num:
        return protect_latin_quantities(f"{num:.1f}x")
    if key == "impact_energy_j" and is_num:
        if num >= 1000:
            return protect_latin_quantities(f"{num/1000:.2f} kJ ({num:.0f} J)")
        return protect_latin_quantities(f"{num:.1f} J")

    if is_num:
        return f"{num:.2f}"
    return protect_latin_quantities(str(val))


# ================================================================
# جدول‌های «شاخص‌های پروازی و صعود» و «شاخص‌های محیطی و فرود»
# --------------------------------------------------------------
# منبعِ واحدِ این دو جدول، مشترک بین گزارش PDF (core/hud_report.py) و
# تب «شاخص‌های پرواز» (pages/flight_indices.py) -- تا همیشه همان‌ها
# نمایش داده شوند و دو جا از هم جدا نشوند.
# ================================================================
GROUP_ASCENT_KEYS = [
    "max_altitude", "max_velocity", "velocity_at_burnout", "max_g", "accel_at_landing",
    "landing_velocity", "dynamic_pressure_max", "max_q_time", "max_q_velocity", "estimated_Cd",
]

GROUP_DESCENT_KEYS = [
    "ground_temperature_c", "apogee_temperature_c", "temperature_lapse_rate_c_per_km",
    "mpu_self_heating_offset_c", "parachute_deploy_altitude", "parachute_deploy_time",
    "velocity_before_chute", "velocity_after_chute",
    "impact_energy_j",
]

# این دو شاخص دیگر در جدول نمایش داده نمی‌شوند: نسبت کاهش سرعت چتر به‌صورت
# حلقهٔ HUD در صفحهٔ ۱ نشان داده می‌شود، و ارزیابی متنی به‌عنوان اولین آیتم
# پنل «پیشنهادهای اصلاحی» (صفحهٔ ۲) منتقل شده است.
EXCLUDED_FROM_TABLE = {"descent_rate_reduction", "chute_suggestion"}

# حذف به درخواست کاربر: کمینه/بیشینهٔ رطوبت و بیشینهٔ شاخص UV نه در جدول‌های
# گزارش PDF می‌آیند و نه در تب «شاخص‌های پرواز» (بقیهٔ شاخص‌های رطوبت/UV مثل
# مقدار زمین و اوج سرِ جایشان می‌مانند).
HIDDEN_FROM_TABLE = {"humidity_min_percent", "humidity_max_percent", "uv_index_max"}


def results_table_rows_with_keys(results: dict, placeholders: bool = False):
    """نسخهٔ کلیددارِ results_table_rows: ردیف‌ها به‌صورت (کلید، عنوان، مقدار).
    تب «شاخص‌های پرواز» از این نسخه استفاده می‌کند تا tooltip هر پارامتر
    را هم بتواند از روی کلید همان ردیف پیدا کند."""
    results = results or {}

    def build(keys):
        return [(k, protect_latin_quantities(TERM_TRANSLATIONS.get(k, k)),
                 format_metric_value(k, results.get(k)))
                for k in keys if (k in results or placeholders)]

    rows_right = build(GROUP_ASCENT_KEYS)
    rows_left = build(GROUP_DESCENT_KEYS)
    known = set(GROUP_ASCENT_KEYS) | set(GROUP_DESCENT_KEYS) | EXCLUDED_FROM_TABLE | HIDDEN_FROM_TABLE
    for k, v in results.items():
        if k != "events" and k not in known:
            rows_left.append((k, protect_latin_quantities(TERM_TRANSLATIONS.get(k, k)),
                              format_metric_value(k, v)))
    return rows_right, rows_left


def results_table_rows(results: dict, placeholders: bool = False):
    """ساخت ردیف‌های (عنوان فارسی، مقدار قالب‌بندی‌شده) هر دو جدول نتایج.

    خروجی: (ردیف‌های «شاخص‌های پروازی و صعود»، ردیف‌های «شاخص‌های محیطی و فرود»).
    کلیدهای results که در هیچ‌کدام از گروه‌های معلوم نیستند (مثل رطوبت زمین/اوج،
    اختلاف AHT−BMP و Cd برآوردی) به انتهای جدول محیطی اضافه می‌شوند -- همان
    چیدمان گزارش PDF. با placeholders=True کلیدهای استانداردِ غایب هم با
    مقدار «--» می‌آیند (برای نمایش اولیهٔ تب قبل از پرواز).
    """
    rows_right, rows_left = results_table_rows_with_keys(results, placeholders)
    return ([(lbl, val) for _k, lbl, val in rows_right],
            [(lbl, val) for _k, lbl, val in rows_left])
