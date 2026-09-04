# -*- coding: utf-8 -*-
"""
core/hud_report.py
--------------------
موتور کاملاً جدید تولید گزارش PDF -- به‌جای HTML/QTextDocument (که پس‌زمینهٔ
تیرهٔ صفحه را کامل پر نمی‌کرد و صفحه‌بندی‌اش با page-break های غیرقابل‌اعتماد
گاهی یک صفحهٔ کاملاً خالی تولید می‌کرد)، این نسخه کل گزارش را مستقیماً و
تماماً با matplotlib (خروجی PDF برداری/Vector) رسم می‌کند: کنترل کامل روی هر
پیکسل صفحه، پس‌زمینهٔ تیرهٔ یکدست بدون هیچ فاصلهٔ سفید، و صفحه‌بندی دقیق
دستی (هر صفحه = یک Figure مجزا، بدون اتکا به موتور صفحه‌بندی HTML).

طراحی بصری از روی تصویر مرجع HUD/کابین (رابط‌های گرافیکی فضایی/نظامی):
حلقه‌های درصدی نئونی، پنل‌های با گوشهٔ براکت‌دار، پس‌زمینهٔ شبکه‌ای کم‌رنگ،
و نمودارهای با جلوهٔ درخشش (Glow).

تمام متن فارسی از fa_text() (تعریف‌شده در core/report_text.py با
arabic_reshaper + python-bidi) عبور می‌کند تا حروف به‌هم‌نچسبند و راست‌به‌چپ
درست نمایش داده شوند؛ فونت هم همان خانوادهٔ شبنم (assets/Shabnam*.ttf) است.
"""
import math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import Rectangle

# ------------------------------------------------------------------
# پالت رنگی HUD (حالت رنگی -- پیش‌فرض)
# ------------------------------------------------------------------
_COLOR_THEME = dict(
    BG="#070b13", PANEL="#0e1620", PANEL_ALT="#0a121b", BORDER="#1c3a4a", GRID_DOT="#132433",
    CYAN="#22d3ee", ORANGE="#ff9f1c", MAGENTA="#ff2e63", PURPLE="#a855f7", GREEN="#4ade80",
    AMBER="#ffb020", TEXT_MAIN="#e6f4fb", TEXT_DIM="#5f7d90",
)

# پالت خاکستری/سیاه‌سفید کم‌مصرف جوهر برای پرینت -- بدون پرشدگی تیرهٔ تمام‌صفحه
# و بدون لایه‌های درخشش (Glow) که روی چاپگر جوهر بیشتری مصرف می‌کنند؛ فقط
# خطوط نازک و متن روی زمینهٔ سفید.
_BW_THEME = dict(
    BG="#ffffff", PANEL="#ffffff", PANEL_ALT="#eeeeee", BORDER="#999999", GRID_DOT="#e6e6e6",
    CYAN="#1a1a1a", ORANGE="#4d4d4d", MAGENTA="#000000", PURPLE="#333333", GREEN="#5c5c5c",
    AMBER="#666666", TEXT_MAIN="#111111", TEXT_DIM="#5a5a5a",
)

BG = _COLOR_THEME["BG"]
PANEL = _COLOR_THEME["PANEL"]
PANEL_ALT = _COLOR_THEME["PANEL_ALT"]
BORDER = _COLOR_THEME["BORDER"]
GRID_DOT = _COLOR_THEME["GRID_DOT"]
CYAN = _COLOR_THEME["CYAN"]
ORANGE = _COLOR_THEME["ORANGE"]
MAGENTA = _COLOR_THEME["MAGENTA"]
PURPLE = _COLOR_THEME["PURPLE"]
GREEN = _COLOR_THEME["GREEN"]
AMBER = _COLOR_THEME["AMBER"]
TEXT_MAIN = _COLOR_THEME["TEXT_MAIN"]
TEXT_DIM = _COLOR_THEME["TEXT_DIM"]
IS_BW = False


def _apply_theme(bw: bool):
    """جابه‌جایی بین پالت رنگی HUD و پالت خاکستری کم‌مصرف جوهر. چون این
    ثابت‌ها هم به‌صورت مستقیم و هم به‌عنوان مقدار پیش‌فرض چند تابع استفاده
    شده‌اند، توابعی که از آن‌ها به‌عنوان دیفالت استفاده می‌کنند مقدار را
    داخل بدنهٔ خودشان (نه در امضای تابع) از سراسری فعلی می‌خوانند."""
    global BG, PANEL, PANEL_ALT, BORDER, GRID_DOT, CYAN, ORANGE, MAGENTA, PURPLE, GREEN, AMBER
    global TEXT_MAIN, TEXT_DIM, IS_BW
    theme = _BW_THEME if bw else _COLOR_THEME
    BG = theme["BG"]; PANEL = theme["PANEL"]; PANEL_ALT = theme["PANEL_ALT"]
    BORDER = theme["BORDER"]; GRID_DOT = theme["GRID_DOT"]
    CYAN = theme["CYAN"]; ORANGE = theme["ORANGE"]; MAGENTA = theme["MAGENTA"]
    PURPLE = theme["PURPLE"]; GREEN = theme["GREEN"]; AMBER = theme["AMBER"]
    TEXT_MAIN = theme["TEXT_MAIN"]; TEXT_DIM = theme["TEXT_DIM"]
    IS_BW = bw

FIG_W, FIG_H = 8.2677, 11.6929  # A4 دقیق (۲۱۰×۲۹۷ میلی‌متر بر حسب اینچ)
ASPECT = FIG_W / FIG_H       # ضریب اصلاح بیضی‌شدگی برای رسم دایرهٔ واقعی


# ====================================================================
# ابزارهای هندسی پایه (سیستم مختصات صفحه: x,y هر دو در بازهٔ ۰..۱ --
# (۰,۰) گوشهٔ پایین‌چپ، (۱,۱) گوشهٔ بالاراست -- دقیقاً منطبق با کل صفحهٔ A4)
# ====================================================================
def _circle_xy(cx, cy, r, theta0=0.0, theta1=2 * math.pi, n=100):
    """نقاط یک قوس/دایرهٔ بصری واقعی (نه بیضی) در سیستم مختصات صفحهٔ نامتقارن."""
    th = np.linspace(theta0, theta1, n)
    return cx + r * np.cos(th), cy + r * ASPECT * np.sin(th)


def new_page():
    fig = plt.figure(figsize=(FIG_W, FIG_H), facecolor=BG)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    # در حالت سیاه‌وسفید (برای پرینت)، کمی فضای خالی بالای صفحه نگه می‌داریم
    # تا جای منگنه‌زدن باشد -- با کشیدن کمی محدودهٔ y (فراتر از ۱)، کل محتوا
    # (که با مختصات ثابت ۰..۱ چیده شده) بدون تغییر در کد هر صفحه، کمی از
    # لبهٔ بالای فیزیکی کاغذ فاصله می‌گیرد.
    top_margin = 0.040 if IS_BW else 0.0
    ax.set_ylim(0, 1 + top_margin)
    ax.axis("off")
    ax.set_facecolor(BG)
    return fig, ax


def draw_background(ax, page_label=""):
    """پس‌زمینهٔ کامل تیره + شبکهٔ نقطه‌ای کم‌رنگ + براکت‌های تزئینی گوشه‌ها.
    در حالت سیاه‌وسفید (IS_BW) شبکهٔ نقطه‌ای (که مصرف جوهر اضافه و بی‌فایده‌ای
    روی پرینتر دارد) رسم نمی‌شود."""
    ax.add_patch(Rectangle((0, 0), 1, 1, facecolor=BG, edgecolor="none", zorder=0))

    if not IS_BW:
        # شبکهٔ نقطه‌ای کم‌رنگ (تزئینی -- حس تکنولوژیک HUD)
        xs = np.linspace(0.03, 0.97, 34)
        ys = np.linspace(0.03, 0.97, 46)
        gx, gy = np.meshgrid(xs, ys)
        ax.scatter(gx.ravel(), gy.ravel(), s=0.6, color=GRID_DOT, zorder=0.5, linewidths=0)

    # براکت‌های گوشه (چهار گوشهٔ صفحه)
    bl = 0.028
    corners = [(0.018, 0.018, 1, 1), (0.982, 0.018, -1, 1),
               (0.018, 0.982, 1, -1), (0.982, 0.982, -1, -1)]
    for cx, cy, sx, sy in corners:
        ax.plot([cx, cx + sx * bl], [cy, cy], color=CYAN, lw=1.4, alpha=0.55, zorder=2, solid_capstyle="butt")
        ax.plot([cx, cx], [cy, cy + sy * bl], color=CYAN, lw=1.4, alpha=0.55, zorder=2, solid_capstyle="butt")

    if page_label:
        ax.text(0.5, 0.012, page_label, ha="center", va="bottom", fontsize=8,
                 color=TEXT_DIM, zorder=2, family="monospace")


def draw_panel(ax, x, y, w, h, accent=None, fill=None, corner_len=0.014, lw=1.0, alpha_fill=0.92):
    """پنل HUD: مستطیل تیره با حاشیهٔ کم‌رنگ + چهار براکت گوشهٔ رنگی (سبک sci-fi)."""
    if accent is None:
        accent = CYAN
    if fill is None:
        fill = PANEL
    ax.add_patch(Rectangle((x, y), w, h, facecolor=fill, edgecolor=BORDER,
                            linewidth=lw, alpha=alpha_fill, zorder=3))
    corners = [(x, y, 1, 1), (x + w, y, -1, 1), (x, y + h, 1, -1), (x + w, y + h, -1, -1)]
    for cx, cy, sx, sy in corners:
        ax.plot([cx, cx + sx * corner_len], [cy, cy], color=accent, lw=1.6, zorder=4, solid_capstyle="butt")
        ax.plot([cx, cx], [cy, cy + sy * corner_len], color=accent, lw=1.6, zorder=4, solid_capstyle="butt")


def draw_panel_header(ax, x, y, w, text_fa, accent=None, fontprop=None, fontsize=12.5):
    """نوار عنوان بالای پنل (پس‌زمینهٔ رنگی کم‌رنگ + نوار عمودی رنگی سمت راست)."""
    if accent is None:
        accent = CYAN
    h = 0.026
    ax.add_patch(Rectangle((x, y - h), w, h, facecolor=PANEL_ALT, edgecolor="none", zorder=3.5))
    ax.add_patch(Rectangle((x + w - 0.006, y - h), 0.006, h, facecolor=accent, edgecolor="none", zorder=3.6))
    ax.text(x + w - 0.014, y - h / 2, text_fa, ha="right", va="center", fontsize=fontsize,
            color=accent, fontproperties=fontprop, fontweight="bold", zorder=4)
    return y - h  # ارتفاع باقیمانده برای محتوای پنل از این y شروع می‌شود


def measure_label_x(fig, ax, label_texts, gap=0.010):
    """پس از رسم متن‌های برچسب (راست‌چین)، لبهٔ چپ واقعیِ رندرشدهٔ هرکدام را
    اندازه می‌گیرد تا مقدار متناظر بلافاصله (با gap کم) کنار آن (نه در لبهٔ
    دیگر جعبه) چیده شود -- برای رفع فاصلهٔ زیاد و گم‌شدن چشمی بین برچسب و مقدار."""
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    inv = ax.transData.inverted()
    xs = []
    for t in label_texts:
        bbox = t.get_window_extent(renderer=renderer)
        x0_data, _ = inv.transform((bbox.x0, bbox.y0))
        xs.append(x0_data - gap)
    return xs


def draw_logo(ax, image, x_center, y_top, width_data):
    """جاسازی لوگو (PNG مربعی) با ابعاد درست (بدون کشیدگی) در سیستم
    مختصات نامتقارن صفحه؛ width_data بر حسب واحد x (۰..۱) است."""
    h_img, w_img = image.shape[0], image.shape[1]
    aspect_img = h_img / w_img
    # اصلاح برای تفاوت مقیاس x/y صفحه (ASPECT) تا لوگو کشیده به‌نظر نرسد
    height_data = width_data * aspect_img * ASPECT
    x0 = x_center - width_data / 2
    x1 = x_center + width_data / 2
    y1 = y_top
    y0 = y_top - height_data
    ax.imshow(image, extent=(x0, x1, y0, y1), zorder=4, aspect="auto")
    return y0


def draw_ring_gauge(fig, ax, cx, cy, r, frac, color, value_text, label_fa, fontprop=None,
                    label_size=8.6, value_size=13.5, unit_text="", sub_text=""):
    """حلقهٔ درصدی HUD (الهام از آیکون‌های ۱۰۰٪ تصویر مرجع): حلقهٔ نقطه‌چین
    زمینه + کمان توپر به رنگ اصلی به‌اندازهٔ frac + مقدار در مرکز + برچسب زیر.

    unit_text: واحد پارامتر -- کوچک‌تر، کنار عدد داخل حلقه (مثل «m/s»).
    sub_text: واحد دوم (مثل km/h برای سرعت) -- کوچک‌تر داخل همان حلقه."""
    frac = max(0.0, min(1.0, frac))

    # حلقهٔ نقطه‌چین زمینه (کل ۳۶۰ درجه)
    n_dashes = 46
    for i in range(n_dashes):
        a0 = 2 * math.pi * i / n_dashes
        a1 = a0 + (2 * math.pi / n_dashes) * 0.58
        xs, ys = _circle_xy(cx, cy, r, a0, a1, 4)
        ax.plot(xs, ys, color=BORDER, lw=2.8, alpha=0.9, zorder=5, solid_capstyle="butt")

    # کمان مقدار (شروع از بالا -- ۹۰ درجه -- در جهت ساعتگرد)
    start = math.pi / 2
    end = start - 2 * math.pi * frac
    if frac > 0.005:
        xs, ys = _circle_xy(cx, cy, r, start, end, max(2, int(80 * frac)))
        if not IS_BW:
            ax.plot(xs, ys, color=color, lw=7.0, alpha=0.16, zorder=5.4, solid_capstyle="round")
        ax.plot(xs, ys, color=color, lw=3.8, alpha=0.95, zorder=5.6, solid_capstyle="round")
        # نقطهٔ درخشان نوک عقربه
        ax.plot([xs[-1]], [ys[-1]], marker="o", markersize=5.2, color=color, zorder=5.8)

    # ---- عدد + واحدِ کوچکِ «همان خط، کنار عدد» (گروه وسط‌چین) ----
    unit_size = max(7.5, value_size * 0.50)
    fig_w_in = fig.get_size_inches()[0]

    def _half_w(s, fs):   # نصف پهنای متن monospace بر حسب کسرِ محور x
        return len(s) * fs * 0.62 / 72.0 / fig_w_in / 2.0

    half_v = _half_w(value_text, value_size)
    half_u = (_half_w(unit_text, unit_size) if unit_text else 0.0)
    u_gap = 0.0035 if unit_text else 0.0
    left = cx - (half_v + u_gap + half_u)   # لبهٔ راستِ گروهِ عدد+واحد
    ax.text(left, cy + 0.010, value_text, ha="left", va="center", fontsize=value_size,
            color=TEXT_MAIN, fontweight="bold", zorder=6, family="monospace")
    if unit_text:
        # همان خطِ عدد (نه پایین‌تر) -- فقط کوچک‌تر
        ax.text(left + 2 * half_v + u_gap, cy + 0.010, unit_text,
                ha="left", va="center", fontsize=unit_size,
                color=TEXT_MAIN, zorder=6, family="monospace")
    # واحد دوم (مثلاً km/h) -- کوچک‌تر، داخل همان حلقه
    if sub_text:
        ax.text(cx, cy - r * ASPECT * 0.42, sub_text, ha="center", va="center",
                fontsize=max(7.2, value_size * 0.42), color=TEXT_DIM,
                zorder=6, family="monospace")
    ax.text(cx, cy - r * ASPECT - 0.020, label_fa, ha="center", va="top", fontsize=label_size,
            color=TEXT_DIM, fontproperties=fontprop, zorder=6)


def glow_line(ax, x, y, color, lw=2.0, fill=True, zorder=5):
    """رسم خط با جلوهٔ درخشش نئونی (چند لایه با شفافیت کاهشی). در حالت
    سیاه‌وسفید (IS_BW) این لایه‌های اضافه و پرشدگی زیر منحنی (که روی
    پرینتر جوهر زیادی مصرف می‌کنند) حذف می‌شوند و فقط یک خط تمیز می‌ماند."""
    if IS_BW:
        ax.plot(x, y, color=color, lw=lw, zorder=zorder + 0.2, solid_capstyle="round")
        return
    ax.plot(x, y, color=color, lw=lw * 5.5, alpha=0.10, zorder=zorder, solid_capstyle="round")
    ax.plot(x, y, color=color, lw=lw * 2.6, alpha=0.22, zorder=zorder + 0.1, solid_capstyle="round")
    ax.plot(x, y, color=color, lw=lw, zorder=zorder + 0.2, solid_capstyle="round")
    if fill:
        ax.fill_between(x, y, min(y) if len(y) else 0, color=color, alpha=0.10, zorder=zorder - 0.1)


def wrap_fa_lines(raw_text: str, max_chars: int):
    """شکستن متن فارسی (خام -- پیش از fa_text) به چند خط بر اساس تعداد
    نویسهٔ تخمینی هر خط، سپس اعمال fa_text() روی هر خط به‌طور جداگانه --
    چون shaping باید روی هر خط دیداری مستقل انجام شود، نه کل متن یکجا."""
    from core.report_text import fa_text, protect_latin_quantities
    # NBSP داخل کمیت لاتین جلوی شکستن «5.5» از «m/s» را می‌گیرد
    raw_text = protect_latin_quantities(str(raw_text))
    words = raw_text.split(" ")
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if len(trial) <= max_chars or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return [fa_text(ln) for ln in lines]


def style_chart_axes(cax, fontprop=None):
    """چیدمان محورهای HUD برای نمودارهای تعبیه‌شده (inset axes). در حالت
    سیاه‌وسفید، پس‌زمینهٔ نمودار کاملاً سفید (بدون خاکستری) می‌ماند تا
    بزرگ‌ترین سطح صفحه کمترین جوهر را مصرف کند."""
    cax.set_facecolor(BG if IS_BW else PANEL_ALT)
    for spine_name, spine in cax.spines.items():
        if spine_name in ("top", "right"):
            spine.set_visible(False)
        else:
            spine.set_color(CYAN)
            spine.set_alpha(0.35)
    cax.tick_params(colors=TEXT_DIM, labelsize=8.5)
    cax.grid(True, color=BORDER, linestyle="--", alpha=0.5, linewidth=0.6)
    if fontprop:
        for lbl in cax.get_xticklabels() + cax.get_yticklabels():
            lbl.set_fontproperties(fontprop)
            lbl.set_fontsize(8.5)


# ====================================================================
# راه‌اندازی فونت شبنم + fa_text (از core/report_text.py -- لایهٔ Qt-آزاد)
# ====================================================================
def _load_fonts():
    from core.report_text import get_asset_path
    reg_path = get_asset_path("Shabnam.ttf")
    bold_path = get_asset_path("Shabnam-Bold.ttf") or reg_path
    reg_prop = bold_prop = None
    if reg_path:
        fm.fontManager.addfont(reg_path)
        reg_prop = fm.FontProperties(fname=reg_path)
    if bold_path:
        fm.fontManager.addfont(bold_path)
        bold_prop = fm.FontProperties(fname=bold_path)
    plt.rcParams["axes.unicode_minus"] = False
    return reg_prop, bold_prop or reg_prop


# ====================================================================
# صفحهٔ ۱: خلاصهٔ مأموریت + حلقه‌های KPI + مشخصات + نتایج + پیشنهادها
# ====================================================================
def draw_two_col_box(fig, ax, px, top_y, box_w, rows, row_h, reg, label_color=None,
                      value_color=None, fontsize=9.4, zebra=True, pad=0.014):
    """رسم یک ستون label:value با فاصلهٔ اندازه‌گیری‌شدهٔ دقیق بین برچسب و
    مقدار (نه دو سر جعبه) -- برای رفع فاصلهٔ زیاد و خواناتر شدن جدول‌ها."""
    if label_color is None:
        label_color = TEXT_DIM
    if value_color is None:
        value_color = CYAN
    label_texts = []
    for i, (lbl, val) in enumerate(rows):
        ry = top_y - i * row_h
        if zebra and i % 2 == 0:
            ax.add_patch(Rectangle((px, ry - row_h), box_w, row_h, facecolor=PANEL_ALT,
                                    edgecolor="none", alpha=0.6, zorder=3.2))
        t = ax.text(px + box_w - pad, ry - row_h / 2, lbl, ha="right", va="center", fontsize=fontsize,
                     color=label_color, fontproperties=reg, zorder=4)
        label_texts.append(t)
        ax.plot([px, px + box_w], [ry - row_h, ry - row_h], color=BORDER, lw=0.5, alpha=0.5, zorder=3.3)

    value_xs = measure_label_x(fig, ax, label_texts, gap=0.012)
    for i, ((lbl, val), vx) in enumerate(zip(rows, value_xs)):
        ry = top_y - i * row_h
        ax.text(vx, ry - row_h / 2, val, ha="right", va="center", fontsize=fontsize,
                color=value_color, fontproperties=reg, fontweight="bold", zorder=4, family="monospace")
    return top_y - len(rows) * row_h


def draw_suggestions_panel(fig, ax, sx, sy, sw, suggestions, reg, bold, max_height=None):
    """پنل پیشنهادهای اصلاحی (قابل استفادهٔ مجدد در چند صفحه). اولین آیتم
    لیست suggestions معمولاً ارزیابی کلی است و بقیه پیشنهادهای اصلاحی؛
    خروجی: مختصات y پایین پنل رسم‌شده."""
    from core.report_text import fa_text

    line_h = 0.0195
    max_chars_per_line = 100

    wrapped_items = []
    for s in suggestions[:7]:
        lines = wrap_fa_lines(s, max_chars_per_line)[:2]
        wrapped_items.append(lines)
    total_lines = sum(len(lines) for lines in wrapped_items) or 1

    header_h2 = 0.026
    sh = header_h2 + 0.014 + total_lines * line_h + 0.010
    if max_height:
        sh = min(sh, max_height)
    draw_panel(ax, sx, sy - sh, sw, sh, accent=AMBER)
    cy2 = draw_panel_header(ax, sx, sy, sw, fa_text("پیشنهادهای اصلاحی و ارزیابی هوشمند"),
                             accent=AMBER, fontprop=bold, fontsize=11.5)
    if suggestions:
        ry = cy2 - 0.016
        for lines in wrapped_items:
            if ry < sy - sh + 0.010:
                break
            for j, ln in enumerate(lines):
                if j == 0:
                    ax.plot([sx + sw - 0.010], [ry], marker="<", markersize=4.2, color=AMBER, zorder=4)
                ax.text(sx + sw - 0.020, ry, ln, ha="right", va="center", fontsize=9.0,
                        color=TEXT_MAIN, fontproperties=reg, zorder=4)
                ry -= line_h
            ry -= 0.004
        return ry
    else:
        ax.text(sx + sw / 2, cy2 - 0.02, fa_text("دادهٔ کافی برای پیشنهاد هوشمند موجود نیست."),
                ha="center", va="center", fontsize=9.5, color=TEXT_DIM, fontproperties=reg, zorder=4)
        return sy - sh


def _draw_fa_text_warning_banner(ax, detail: str):
    """نوار هشدار روی صفحهٔ اول گزارش وقتی شکل‌دهی متن فارسی خراب باشد.
    عمداً به انگلیسی/ASCII نوشته شده -- اگر fa_text() خراب باشد، هر متن
    فارسی دیگری که این‌جا رسم کنیم هم به همان شکل بهم‌ریخته درمی‌آید و
    غیرقابل‌خواندن می‌شود؛ متن انگلیسی نیازی به reshape/bidi ندارد و در
    هر شرایطی درست و خوانا نمایش داده می‌شود."""
    bx, by, bw_, bh = 0.045, 0.905, 0.91, 0.058
    ax.add_patch(Rectangle((bx, by - bh), bw_, bh, facecolor="#3a0d0d" if not IS_BW else "#ffffff",
                            edgecolor="#ff4d4d", linewidth=1.6, zorder=9))
    detail_short = (detail[:70] + "...") if len(detail) > 70 else detail
    msg1 = "WARNING: Persian text shaping failed -- labels below may show reversed/disconnected letters."
    msg2 = f"Fix: pip install -r requirements.txt (arabic-reshaper, python-bidi)  [{detail_short}]"
    ax.text(bx + bw_ / 2, by - bh * 0.35, msg1, ha="center", va="center", fontsize=9.2,
            color="#ff6666", fontweight="bold", family="monospace", zorder=10)
    ax.text(bx + bw_ / 2, by - bh * 0.74, msg2, ha="center", va="center", fontsize=6.8,
            color="#ff9999" if not IS_BW else "#333333", family="monospace", zorder=10)


def _build_page1(pdf, mission, motor, results, suggestions, reg, bold, fa_ok=True, fa_detail="",
                  logo_img=None):
    from core.report_text import fa_text, to_jalali_date, TERM_TRANSLATIONS

    fig, ax = new_page()
    draw_background(ax, "")

    m, mo = mission, motor
    jalali = to_jalali_date(m.jalali_date or m.date)

    def truncate_fa(text, max_chars):
        text = str(text)
        if len(text) <= max_chars:
            return text
        cut = text[:max_chars - 1].rstrip()
        last_space = cut.rfind(" ")
        if last_space > max_chars * 0.55:  # فقط اگر برش کلمه‌ای منطقی امکان دارد
            cut = cut[:last_space].rstrip()
        return cut + "…"

    # ---------------- جعبهٔ اطلاعات پرتاب (بدون لوگو و بدون عنوان -- فقط محل و تاریخ) ----------------
    box_x, box_w = 0.045, 0.30
    box_y_top = 0.972
    box_row_h = 0.024
    box_h = 2 * box_row_h
    box_bottom = box_y_top - box_h
    draw_panel(ax, box_x, box_bottom, box_w, box_h, accent=CYAN)
    site_line = fa_text(f"محل: {truncate_fa(m.launch_site or '--', 34)}")
    date_line = fa_text(f"تاریخ: {jalali}")
    ax.text(box_x + box_w - 0.014, box_y_top - box_row_h / 2, site_line, ha="right", va="center",
            fontsize=8.8, color=TEXT_MAIN, fontproperties=reg, zorder=4)
    ax.text(box_x + box_w - 0.014, box_y_top - box_row_h - box_row_h / 2, date_line, ha="right", va="center",
            fontsize=8.8, color=CYAN, fontproperties=reg, fontweight="bold", zorder=4, family="monospace")

    # ---------------- عنوان و زیرعنوان (بالا-راست) ----------------
    ax.text(0.955, 0.965, fa_text("گزارش رسمی و تحلیلی پرواز راکت"), ha="right", va="center",
            fontsize=17, color=TEXT_MAIN, fontproperties=bold, fontweight="bold", zorder=4)
    line2 = fa_text(
        f"نام راکت: {m.rocket_name or '--'}   /   شمارهٔ پرواز: {m.flight_number or '--'}   /   "
        f"شمارهٔ موتور: {m.motor_number or '--'}"
    )
    ax.text(0.955, 0.933, line2, ha="right", va="center", fontsize=10.5, color=CYAN,
            fontproperties=reg, zorder=4)

    divider_y = min(box_bottom, 0.918) - 0.014
    ax.plot([0.045, 0.955], [divider_y, divider_y], color=BORDER, lw=1.0, zorder=2)

    if not fa_ok:
        _draw_fa_text_warning_banner(ax, fa_detail)
        divider_y -= 0.066

    # ---------------- حلقه‌های KPI (۳ در ۳) -- ۶ شاخص اصلی + ۳ شاخص فاز فرود ----------------
    # fmt خروجی‌اش (عدد، واحد، واحد دوم) است: واحد کوچک کنار عدد داخل حلقه
    # می‌نشیند و واحد دوم (مثل km/h برای سرعت‌ها) کوچک‌تر زیر عدد داخل حلقه.
    kpi_defs = [
        ("max_g", 20.0, MAGENTA, lambda v: (f"{v:.1f}", "g", "")),
        ("velocity_at_burnout", 200.0, CYAN, lambda v: (f"{v:.0f}", "m/s", f"{v * 3.6:.0f} km/h")),
        ("max_velocity", 200.0, ORANGE, lambda v: (f"{v:.0f}", "m/s", f"{v * 3.6:.0f} km/h")),
        ("max_altitude", 3000.0, PURPLE, lambda v: (f"{v:.0f}", "m", "")),
        ("landing_velocity", 25.0, GREEN, lambda v: (f"{v:.1f}", "m/s", f"{v * 3.6:.0f} km/h")),
        ("parachute_deploy_altitude", 3000.0, CYAN, lambda v: (f"{v:.0f}", "m", "")),
        ("landing_velocity", 25.0, MAGENTA, lambda v: (f"{v:.1f}", "m/s", f"{v * 3.6:.0f} km/h")),
        ("impact_energy_j", 500.0, AMBER, lambda v: (f"{v:.0f}", "J", "")),
        ("descent_rate_reduction", 10.0, GREEN, lambda v: (f"{v:.1f}", "x", "")),
    ]
    cols, rows_n = 3, 3
    grid_x0, grid_x1 = 0.045, 0.955
    grid_y1 = divider_y - 0.018
    row_pitch = 0.186
    grid_y0 = grid_y1 - row_pitch * rows_n
    ring_r = 0.078
    for i, (key, ref_max, color, fmt) in enumerate(kpi_defs):
        col = i % cols
        row = i // cols
        cx = grid_x0 + (grid_x1 - grid_x0) * (col + 0.5) / cols
        cy = grid_y1 - (grid_y1 - grid_y0) * (row + 0.5) / rows_n
        try:
            raw = float(results.get(key) or 0.0)
        except (TypeError, ValueError):
            raw = 0.0
        frac = max(0.0, min(1.0, raw / ref_max))
        v_txt, u_txt, s_txt = fmt(raw)
        draw_ring_gauge(fig, ax, cx, cy, ring_r, frac, color, v_txt,
                        fa_text(TERM_TRANSLATIONS.get(key, key)), fontprop=reg,
                        label_size=9.6, value_size=18.5,
                        unit_text=u_txt, sub_text=s_txt)

    last_row_cy = grid_y1 - (grid_y1 - grid_y0) * (rows_n - 0.5) / rows_n
    # خطِ مقدارِ کامل زیر حلقه‌ها حذف شده (عدد و واحد داخل حلقه‌اند) --
    # فقط برچسب فارسی پارامتر زیر حلقه می‌ماند.
    content_bottom = last_row_cy - ring_r * ASPECT - 0.038

    # ---------------- پنل مشخصات مأموریت (دو باکس کنار هم) ----------------
    px, pw = 0.045, 0.91
    py = content_bottom - 0.018
    header_h, row_h = 0.026, 0.027

    rows_right = [
        (fa_text("محل پرتاب"), fa_text(m.launch_site or "--")),
        (fa_text("تاریخ و ساعت"), fa_text(f"{jalali}  {m.time or ''}")),
        (fa_text("زاویهٔ پرتاب"), fa_text(f"{m.launch_angle} deg")),
        (fa_text("وزن کل راکت"), fa_text(f"{m.total_mass} kg")),
        (fa_text("وزن سوخت"), fa_text(f"{m.propellant_mass} g")),
        (fa_text("قطر چتر"), (fa_text(f"{getattr(m, 'chute_diameter_m', 0) or 0} m") if getattr(m, 'chute_diameter_m', 0) else fa_text("بدون چتر"))),
    ]
    rows_left = [
        (fa_text("شمارهٔ پروژه"), fa_text(m.project_number or "--")),
        (fa_text("نسخهٔ فریم‌ور"), fa_text(f"{m.firmware_version or '--'}")),
        (fa_text("شمارهٔ موتور"), fa_text(m.motor_number or '--')),
        (fa_text("ابعاد نازل"), fa_text(f"{mo.throat_diameter}/{mo.exit_diameter}/{mo.nozzle_length}")),
        (fa_text("فشار محفظهٔ احتراق"), fa_text(f"{mo.chamber_pressure_bar} bar")),
        (fa_text("قطر بدنه"), fa_text(f"{m.body_diameter} m") if getattr(m, 'body_diameter', 0) else "--"),
    ]
    n_rows = len(rows_right)
    panel_h = header_h + row_h * n_rows
    panel_bottom = py - panel_h
    draw_panel(ax, px, panel_bottom, pw, panel_h, accent=CYAN)
    cursor_y = draw_panel_header(ax, px, py, pw, fa_text("مشخصات فنی مأموریت و راکت"), accent=CYAN,
                                  fontprop=bold, fontsize=11.5)

    box_w2 = pw / 2
    ax.plot([px + box_w2, px + box_w2], [panel_bottom, cursor_y], color=BORDER, lw=0.7, alpha=0.7, zorder=3.4)

    draw_two_col_box(fig, ax, px + box_w2, cursor_y, box_w2, rows_right, row_h, reg)
    draw_two_col_box(fig, ax, px, cursor_y, box_w2, rows_left, row_h, reg)

    # ---------------- فوتر ----------------
    draw_footer_logo(ax, logo_img)
    ax.text(0.5, 0.018, fa_text("سامانهٔ کنترل زمینی راکت -- تولید خودکار توسط RocketGCS"),
            ha="center", va="bottom", fontsize=7.5, color=TEXT_DIM, fontproperties=reg, zorder=4)

    pdf.savefig(fig, facecolor=BG)
    plt.close(fig)


# ====================================================================
# صفحهٔ ۲: جدول کامل نتایج و شاخص‌های تحلیلی (پنل دادهٔ بزرگ HUD)
# ====================================================================
# ترتیب و محتوای جدول‌های صفحهٔ ۲ (شاخص‌های پروازی/محیطی) از لایهٔ مشترکِ
# core/report_text.py می‌آید -- همان منبعی که تب «شاخص‌های پرواز» هم از آن
# استفاده می‌کند، تا PDF و UI همیشه هم‌محتوا باشند.
from core.report_text import results_table_rows


def _build_page2(results, suggestions, reg, bold):
    from core.report_text import fa_text

    fig, ax = new_page()
    draw_background(ax, fa_text("صفحهٔ ۲ / نتایج تحلیلی"))

    ax.text(0.955, 0.965, fa_text("جدول کامل نتایج و شاخص‌های تحلیلی پرواز"), ha="right", va="center",
            fontsize=15.5, color=TEXT_MAIN, fontproperties=bold, fontweight="bold", zorder=4)
    ax.text(0.955, 0.940, fa_text("پارامترهای مرتبط با هم کنار هم گروه‌بندی شده‌اند"), ha="right",
            va="center", fontsize=8.8, color=TEXT_DIM, fontproperties=reg, zorder=4)
    ax.plot([0.045, 0.955], [0.918, 0.918], color=BORDER, lw=1.0, zorder=2)

    results = results or {}

    rows_right, rows_left = results_table_rows(results)
    rows_right = [(fa_text(lbl), fa_text(val)) for lbl, val in rows_right]
    rows_left = [(fa_text(lbl), fa_text(val)) for lbl, val in rows_left]

    px, py, pw = 0.045, 0.895, 0.91
    gap = 0.024
    box_w = (pw - gap) / 2
    header_h = 0.030
    row_h = 0.0275  # هم‌اندازه با فاصلهٔ ردیف‌های پنل مشخصات فنی (صفحهٔ ۱) -- فشرده و متعادل

    right_x = px + box_w + gap
    panel_h_r = header_h + row_h * len(rows_right)
    draw_panel(ax, right_x, py - panel_h_r, box_w, panel_h_r, accent=CYAN)
    cur_r = draw_panel_header(ax, right_x, py, box_w, fa_text("شاخص‌های پروازی و صعود"),
                               accent=CYAN, fontprop=bold, fontsize=11)
    draw_two_col_box(fig, ax, right_x, cur_r, box_w, rows_right, row_h, reg,
                      value_color=ORANGE, fontsize=9.4)

    panel_h_l = header_h + row_h * len(rows_left)
    draw_panel(ax, px, py - panel_h_l, box_w, panel_h_l, accent=PURPLE)
    cur_l = draw_panel_header(ax, px, py, box_w, fa_text("شاخص‌های محیطی و فرود"),
                               accent=PURPLE, fontprop=bold, fontsize=11)
    draw_two_col_box(fig, ax, px, cur_l, box_w, rows_left, row_h, reg,
                      value_color=AMBER, fontsize=9.4)

    content_bottom = min(py - panel_h_r, py - panel_h_l)

    # جدول «پیش‌بینی در برابر واقعیت» به ابتدای صفحهٔ ۳ منتقل شد (درخواست
    # کاربر)؛ انتهای صفحهٔ ۲ فقط پنل پیشنهادهای اصلاحی است.
    sug_top = content_bottom - 0.028
    sug_max = sug_top - 0.045

    # ---------------- پنل پیشنهادهای اصلاحی (بعد از جدول کامل نتایج) ----------------
    # اولین آیتم، ارزیابی کلی عملکرد سامانهٔ بازیابی (chute_suggestion) است --
    # یعنی اول ارزیابی، بعد پیشنهادهای اصلاحی الگوریتمی.
    chute_eval = results.get("chute_suggestion")
    combined_suggestions = ([str(chute_eval)] if chute_eval else []) + list(suggestions or [])
    draw_suggestions_panel(fig, ax, px, sug_top, pw, combined_suggestions, reg, bold,
                           max_height=max(0.05, sug_max))

    return fig, ax


# ====================================================================
# صفحات نمودار -- هر نمودار به‌صورت inset axes داخل همان Figure تمام‌صفحه
# (نه تصویر رستری جدا) تا هم برداری/باکیفیت بماند و هم پس‌زمینهٔ تیره
# صفحه هیچ شکافی نداشته باشد.
# ====================================================================
def _chart_panel(fig, ax_bg, x, y, w, h, title_fa, reg, bold, accent=None):
    """پنل HUD برای یک نمودار + inset axes آماده برای رسم داخل آن. مختصات
    ورودی به‌صورت کسر صفحه (۰..۱) هستند و مستقیماً برای add_axes مناسبند."""
    if accent is None:
        accent = CYAN
    draw_panel(ax_bg, x, y, w, h, accent=accent)
    top = draw_panel_header(ax_bg, x, y + h, w, title_fa, accent=accent, fontprop=bold, fontsize=11.5)
    pad_x, pad_b, pad_t = 0.072, 0.052, 0.014
    # چون ax_bg در حالت سیاه‌وسفید کمی کشیده می‌شود (برای فضای منگنه در
    # new_page())، مختصات این پنل (که به همان سیستم دادهٔ ۰..۱ داده شده)
    # باید قبل از دادن به fig.add_axes (که مختصات کسر-figure واقعی می‌خواهد
    # و از کشیدگی ax_bg خبر ندارد) به همان نسبت تبدیل شود -- در غیر این
    # صورت نمودار داخل پنل هم‌راستا با کادر دورش نمی‌ماند.
    margin = 0.040 if IS_BW else 0.0
    scale = 1.0 / (1.0 + margin)
    fig_x = x + pad_x
    fig_w = w - 2 * pad_x
    fig_y = (y + pad_b) * scale
    fig_h = ((top - pad_t) - (y + pad_b)) * scale
    cax = fig.add_axes([fig_x, fig_y, fig_w, fig_h])
    style_chart_axes(cax, fontprop=reg)
    return cax


def _phase_shares(an, idx):
    """سهم زمانی هر مرحلهٔ پرواز -- همان تقسیم‌بندی شیت «تحلیل مراحل پرواز»
    گزارش اکسل (core/excel_export.py::phase_of_index). خروجی: فهرستی از
    (نام مرحله، مدت ثانیه، t شروع، t پایان، درصد از زمان کل) فقط برای
    مراحلی که داده دارند؛ «روی سکو» مثل اکسل جزو زمان پرواز نیست."""
    if an.t is None:
        return []
    n = len(an.t)

    def phase_of(i):
        if idx.get("launch") is not None and i < idx["launch"]:
            return "روی سکو"
        if idx.get("burnout") is not None and i <= idx["burnout"]:
            return "مرحلهٔ رانش"
        if idx.get("apogee") is not None and i <= idx["apogee"]:
            return "سیر صعودی آزاد"
        if idx.get("parachute") is not None and i <= idx["parachute"]:
            return "سقوط آزاد"
        if idx.get("landing") is not None and i < idx["landing"]:
            return "نزول با چتر"
        return "فرود"

    spans = {}
    for i in range(n):
        ph = phase_of(i)
        if ph == "روی سکو":
            continue
        if ph not in spans:
            spans[ph] = [i, i]
        spans[ph][1] = i

    order = ["مرحلهٔ رانش", "سیر صعودی آزاد", "سقوط آزاد", "نزول با چتر", "فرود"]
    rows = []
    for ph in order:
        if ph not in spans:
            continue
        i0, i1 = spans[ph]
        t0, t1 = float(an.t[i0]), float(an.t[i1])
        rows.append([ph, max(t1 - t0, 0.0), t0, t1, 0.0])
    total = sum(r[1] for r in rows)
    if total <= 0:
        return []
    for r in rows:
        r[4] = r[1] / total * 100.0
    return [tuple(r) for r in rows]



def _build_page3_tables(flight_df, results, prediction, reg, bold):
    """صفحهٔ ۳: «پیش‌بینی در برابر واقعیت» در بالای صفحه و زیر آن جدول
    «درصد دقیق هر مرحله» -- هر دو با اندازهٔ سطر و فونت یکسان (درخواست
    کاربر)؛ صفحات نمودار بعد از این صفحه می‌آیند."""
    from core.report_text import fa_text

    comp_rows = []
    if prediction:
        try:
            from core.prediction_compare import compare_snapshot
            comp = compare_snapshot(prediction, results or {})
            comp_rows = [r for r in comp.get("rows", []) if r.get("actual") is not None]
        except Exception:
            comp_rows = []

    shares = []
    if flight_df is not None:
        from core.analysis import FlightAnalyzer
        an = FlightAnalyzer(flight_df, None, None)
        an.detect_events()
        shares = _phase_shares(an, getattr(an, "_idx", {}))

    if not comp_rows and not shares:
        return None

    fig, ax = new_page()
    draw_background(ax, fa_text("صفحهٔ ۳ / پیش‌بینی و مراحل پرواز"))
    ax.text(0.955, 0.955, fa_text("پیش‌بینی در برابر واقعیت و مراحل پرواز"),
            ha="right", va="center", fontsize=14.5, color=TEXT_MAIN,
            fontproperties=bold, fontweight="bold", zorder=4)

    px, pw = 0.045, 0.91
    row_h = 0.024              # هم‌اندازهٔ جدول پیش‌بینی (یکسان در هر دو جدول)
    header_fs, cell_fs = 8.6, 8.4
    cur_top = 0.880

    # ================= پنل ۱: پیش‌بینی در برابر واقعیت =================
    if comp_rows:
        comp_h = 0.030 + 0.018 + row_h * len(comp_rows)
        draw_panel(ax, px, cur_top - comp_h, pw, comp_h, accent=ORANGE)
        draw_panel_header(ax, px, cur_top, pw, fa_text("پیش‌بینی در برابر واقعیت"),
                          accent=ORANGE, fontprop=bold, fontsize=11)
        if prediction.get("fallback"):
            ax.text(px + 0.008, cur_top - 0.015, fa_text(
                "بازسازی‌شده با پارامترهای ثبت‌شدهٔ مأموریت (اسنپ‌شات لحظهٔ پرتاب در دسترس نبود)"),
                ha="left", va="center", fontsize=6.6, color=TEXT_DIM,
                fontproperties=reg, zorder=4)
        cy = cur_top - 0.030
        frac = (0.315, 0.235, 0.235, 0.145)
        xs, cur = [], px + pw
        for f in frac:
            xs.append(cur)
            cur -= f * pw
        for x, h in zip(xs, ("کمیت", "پیش‌بینی", "واقعیت", "اختلاف")):
            ax.text(x - 0.006, cy - 0.009, fa_text(h), ha="right", va="center",
                    fontsize=header_fs, color=TEXT_DIM, fontproperties=bold, zorder=4)
        ax.plot([px, px + pw], [cy - 0.018, cy - 0.018], color=BORDER, lw=0.8, zorder=3.3)

        def _fmt(v, unit, dec):
            return "--" if v is None else fa_text(f"{v:.{dec}f}") + fa_text(" ") + unit

        for i, row in enumerate(comp_rows):
            band_top = cy - 0.018 - row_h * i
            band_bottom = band_top - row_h
            if i % 2 == 0:
                ax.add_patch(Rectangle((px, band_bottom), pw, row_h, facecolor=PANEL_ALT,
                                       edgecolor="none", alpha=0.6, zorder=3.2))
            dec = 1 if row["key"] in ("gmax", "vland", "burn", "tapogee") else 0
            dev = row["dev_pct"]
            dev_txt = ("--" if dev is None
                       else fa_text(("+" if dev > 0 else "\u2212") + f"{abs(dev):.0f}٪"))
            vals = (fa_text(row["label"]), _fmt(row["pred"], row["unit"], dec),
                    _fmt(row["actual"], row["unit"], dec), dev_txt)
            if IS_BW:
                vcolor = TEXT_MAIN
            else:
                vcolor = {"ok": "#35d07f", "minor": AMBER, "major": "#ef5350",
                          "nodata": TEXT_DIM}.get(row["kind"], CYAN)
            ry = (band_top + band_bottom) / 2.0
            for x, v in zip(xs, vals):
                ax.text(x - 0.006, ry, v, ha="right", va="center",
                        fontsize=cell_fs, color=(TEXT_MAIN if x is xs[0] else vcolor),
                        fontproperties=reg, zorder=4)
            if i < len(comp_rows) - 1:
                ax.plot([px, px + pw], [band_bottom, band_bottom], color=BORDER,
                        lw=0.5, alpha=0.5, zorder=3.3)
        cur_top -= comp_h + 0.030

    # ================= پنل ۲: درصد دقیق هر مرحله =================
    if shares:
        from core import palette as _pal
        phase_color = {
            "مرحلهٔ رانش": _pal.COLOR_ERROR,
            "سیر صعودی آزاد": _pal.COLOR_WARN,
            "سقوط آزاد": _pal.COLOR_INFO,
            "نزول با چتر": _pal.COLOR_OK,
            "فرود": _pal.COLOR_MISSING,
        }
        sum_row_h = 0.034
        ph_h = 0.030 + 0.018 + row_h * len(shares) + sum_row_h + 0.014
        draw_panel(ax, px, cur_top - ph_h, pw, ph_h, accent=CYAN)
        draw_panel_header(ax, px, cur_top, pw, fa_text("درصد دقیق هر مرحله"),
                          accent=CYAN, fontprop=bold, fontsize=11)
        cy = cur_top - 0.030
        frac = (0.30, 0.16, 0.16, 0.16, 0.22)
        xs, cur = [], px + pw
        for f in frac:
            xs.append(cur)
            cur -= f * pw
        heads = ("مرحله", "مدت (ثانیه)", "شروع (ثانیه)", "پایان (ثانیه)", "سهم از زمان کل (٪)")
        for x, h in zip(xs, heads):
            ax.text(x - 0.008, cy - 0.009, fa_text(h), ha="right", va="center",
                    fontsize=header_fs, color=TEXT_DIM, fontproperties=bold, zorder=4)
        ax.plot([px, px + pw], [cy - 0.018, cy - 0.018], color=BORDER, lw=0.8, zorder=3.3)

        total_dur = sum(sh[1] for sh in shares)
        for i, (name, dur, t0, t1, pct) in enumerate(shares):
            band_top = cy - 0.018 - row_h * i
            band_bottom = band_top - row_h
            if i % 2 == 0:
                ax.add_patch(Rectangle((px, band_bottom), pw, row_h, facecolor=PANEL_ALT,
                                       edgecolor="none", alpha=0.6, zorder=3.2))
            color = TEXT_MAIN if IS_BW else phase_color.get(name, CYAN)
            ry = (band_top + band_bottom) / 2.0
            vals = (fa_text(name), fa_text(f"{dur:.1f}"), fa_text(f"{t0:.1f}"),
                    fa_text(f"{t1:.1f}"), fa_text(f"{pct:.1f}٪"))
            for j, (x, v) in enumerate(zip(xs, vals)):
                is_name = (j == 0)
                ax.text(x - 0.008, ry, v, ha="right", va="center",
                        fontsize=cell_fs, color=(TEXT_MAIN if is_name else color),
                        fontproperties=(bold if is_name else reg), zorder=4)
            if i < len(shares) - 1:
                ax.plot([px, px + pw], [band_bottom, band_bottom], color=BORDER,
                        lw=0.5, alpha=0.5, zorder=3.3)

        # سطر «مجموع زمان پرواز» -- هم‌سبک بقیهٔ جدول، فقط کمی درشت‌تر
        sum_top = cy - 0.018 - row_h * len(shares)
        sum_bottom = sum_top - sum_row_h
        ax.add_patch(Rectangle((px, sum_bottom), pw, sum_row_h, facecolor=PANEL_ALT,
                               edgecolor="none", alpha=0.75, zorder=3.2))
        ax.plot([px, px + pw], [sum_top, sum_top], color=BORDER, lw=0.8, zorder=3.3)
        sum_ry = (sum_top + sum_bottom) / 2.0
        ax.text(xs[0] - 0.008, sum_ry, fa_text("مجموع زمان پرواز"), ha="right",
                va="center", fontsize=8.8, color=TEXT_MAIN, fontproperties=bold, zorder=4)
        ax.text(xs[1] - 0.008, sum_ry, fa_text(f"{total_dur:.1f}"), ha="right",
                va="center", fontsize=8.8, color=TEXT_MAIN, fontproperties=bold, zorder=4)

    return fig, ax


def _build_chart_pages(flight_df, results, reg, bold):
    """می‌سازد ولی ذخیره نمی‌کند -- فهرستی از (fig, ax) صفحات نمودار را
    برمی‌گرداند تا caller (generate_hud_pdf) بتواند صفحهٔ واقعاً آخر را
    تشخیص دهد و لوگوی پایانی را فقط به همان یکی اضافه کند."""
    from core.report_text import fa_text
    from core.analysis import FlightAnalyzer, G0

    pages = []
    if flight_df is None:
        return pages

    an = FlightAnalyzer(flight_df, None, None)
    an.detect_events()
    idx = getattr(an, "_idx", {})

    # ---------------- صفحهٔ ۳: ارتفاع + سرعت ----------------
    if an.t is not None and (an.alt is not None or an.vel is not None):
        fig, ax = new_page()
        draw_background(ax, fa_text("صفحهٔ ۴ / نمودارهای ارتفاع و سرعت"))
        ax.text(0.955, 0.955, fa_text("نمودارهای تحلیلی پرواز -- فاز اول"), ha="right", va="center",
                fontsize=14.5, color=TEXT_MAIN, fontproperties=bold, fontweight="bold", zorder=4)

        if an.alt is not None:
            cax = _chart_panel(fig, ax, 0.045, 0.530, 0.91, 0.410,
                                fa_text("پروفایل ارتفاع بر حسب زمان"), reg, bold, accent=CYAN)
            glow_line(cax, an.t, an.alt, CYAN, lw=1.8)
            cax.set_xlabel(fa_text("زمان (ثانیه)"), fontproperties=reg, fontsize=9, color=TEXT_DIM)
            cax.set_ylabel(fa_text("ارتفاع (متر)"), fontproperties=reg, fontsize=8.3, color=TEXT_DIM, labelpad=2)

        if an.vel is not None:
            cax = _chart_panel(fig, ax, 0.045, 0.085, 0.91, 0.410,
                                fa_text("پروفایل سرعت بر حسب زمان"), reg, bold, accent=ORANGE)
            glow_line(cax, an.t, an.vel, ORANGE, lw=1.8)
            cax.axhline(0, color=BORDER, lw=0.7, alpha=0.7)
            cax.set_xlabel(fa_text("زمان (ثانیه)"), fontproperties=reg, fontsize=9, color=TEXT_DIM)
            cax.set_ylabel(fa_text("سرعت (m/s)"), fontproperties=reg, fontsize=8.3, color=TEXT_DIM, labelpad=2)

        pages.append((fig, ax))

    # ---------------- صفحهٔ ۴: شتاب (خط) + مقایسهٔ سرعت فازها (میله‌ای) ----------------
    fig, ax = new_page()
    draw_background(ax, fa_text("صفحهٔ ۵ / شتاب و مقایسهٔ فازهای پرواز"))
    ax.text(0.955, 0.955, fa_text("نمودارهای تحلیلی پرواز -- فاز دوم"), ha="right", va="center",
            fontsize=14.5, color=TEXT_MAIN, fontproperties=bold, fontweight="bold", zorder=4)
    made_any = False

    if an.t is not None and an.a_total is not None:
        made_any = True
        cax = _chart_panel(fig, ax, 0.045, 0.530, 0.91, 0.410,
                            fa_text("پروفایل شتاب وارد بر راکت (g)"), reg, bold, accent=MAGENTA)
        g = an.a_total / G0
        glow_line(cax, an.t, g, MAGENTA, lw=1.6, fill=False)
        peak_i = int(np.argmax(g))
        cax.plot([an.t[peak_i]], [g[peak_i]], marker="o", markersize=5, color=MAGENTA, zorder=6)
        cax.annotate(f"{g[peak_i]:.1f}g", xy=(an.t[peak_i], g[peak_i]),
                     xytext=(an.t[peak_i] + (an.t[-1] - an.t[0]) * 0.04, g[peak_i]),
                     fontsize=8.5, color=MAGENTA, fontproperties=reg, fontweight="bold",
                     va="center", family="monospace")
        cax.set_xlabel(fa_text("زمان (ثانیه)"), fontproperties=reg, fontsize=9, color=TEXT_DIM)
        cax.set_ylabel(fa_text("شتاب (g)"), fontproperties=reg, fontsize=8.3, color=TEXT_DIM, labelpad=2)

    # نمودار میله‌ای مقایسهٔ سرعت در فازهای مختلف پرواز -- نوع کاملاً متفاوت
    # از نمودارهای خطی بالا (تنوع بصری خواستهٔ کاربر)
    if an.vel is not None and idx:
        made_any = True
        cax = _chart_panel(fig, ax, 0.045, 0.085, 0.91, 0.410,
                            fa_text("مقایسهٔ سرعت در فازهای کلیدی پرواز"), reg, bold, accent=GREEN)
        phase_defs = [
            (fa_text("پرتاب"), idx.get("launch"), CYAN),
            (fa_text("پایان سوخت"), idx.get("burnout"), ORANGE),
            (fa_text("اوج (Apogee)"), idx.get("apogee"), PURPLE),
            (fa_text("باز شدن چتر"), idx.get("parachute"), AMBER),
            (fa_text("برخورد به زمین"), idx.get("landing"), MAGENTA),
        ]
        labels, values, colors = [], [], []
        for lbl, pidx, color in phase_defs:
            if pidx is None:
                continue
            labels.append(lbl)
            values.append(abs(float(an.vel[pidx])))
            colors.append(color)

        xpos = np.arange(len(values))
        if IS_BW:
            # در حالت سیاه‌وسفید، میلهٔ توپر مصرف جوهر خیلی زیادی دارد (چون
            # پهن و بلند است) -- به‌جای پرشدگی یکدست، فقط کادر دور میله +
            # هاشور (خط‌خط) کم‌جوهر رسم می‌شود؛ هر میله هاشور متفاوتی دارد
            # تا بدون رنگ هم از هم قابل‌تشخیص باشند.
            hatches = ["//", "xx", "\\\\", "..", "oo"]
            bars = cax.bar(xpos, values, facecolor="none", edgecolor=TEXT_MAIN, width=0.56,
                            zorder=5, linewidth=1.1)
            for b, hatch in zip(bars, hatches):
                b.set_hatch(hatch)
            label_colors = [TEXT_MAIN] * len(values)
        else:
            bars = cax.bar(xpos, values, color=colors, width=0.56, zorder=5, edgecolor="none")
            for b, v, c in zip(bars, values, colors):
                cax.add_patch(Rectangle((b.get_x(), 0), b.get_width(), v, facecolor=c, alpha=0.18,
                                         zorder=4.5, transform=cax.transData))
            label_colors = colors
        for b, v, c in zip(bars, values, label_colors):
            cax.text(b.get_x() + b.get_width() / 2, v + max(values) * 0.03, f"{v:.1f}",
                     ha="center", va="bottom", fontsize=8.5, color=c, fontweight="bold",
                     family="monospace", zorder=6)
        cax.set_xticks(xpos)
        cax.set_xticklabels(labels, fontproperties=reg, fontsize=8.2)
        cax.set_ylabel(fa_text("سرعت مطلق (m/s)"), fontproperties=reg, fontsize=8.3, color=TEXT_DIM, labelpad=2)
        cax.set_ylim(0, max(values) * 1.25 if values else 1)

    if made_any:
        pages.append((fig, ax))
    else:
        plt.close(fig)

    # ---------------- صفحهٔ ۶: تحلیل فرود با چتر (دو محوره، تمام‌عرض) ----------------
    p_idx, l_idx = idx.get("parachute"), idx.get("landing")
    if p_idx is not None and l_idx is not None and an.t is not None and p_idx < l_idx:
        chute_page_no_fa = "۶"
        fig, ax = new_page()
        draw_background(ax, fa_text(f"صفحهٔ {chute_page_no_fa} / تحلیل فاز فرود با چتر نجات"))
        ax.text(0.955, 0.955, fa_text("تحلیل فاز فرود با چتر نجات"), ha="right", va="center",
                fontsize=14.5, color=TEXT_MAIN, fontproperties=bold, fontweight="bold", zorder=4)

        # شاخص‌های سرعت برخورد/انرژی جنبشی/نسبت کاهش سرعت به صفحهٔ ۱ منتقل
        # شدند؛ این‌جا فقط نمودار دومحورهٔ فرود، اکنون با فضای کامل صفحه.
        cax = _chart_panel(fig, ax, 0.045, 0.120, 0.91, 0.820,
                            fa_text("ارتفاع و سرعت نزول پس از باز شدن چتر"), reg, bold, accent=CYAN)
        t_rel = an.t[p_idx:l_idx + 1] - an.t[p_idx]
        if an.alt is not None:
            glow_line(cax, t_rel, an.alt[p_idx:l_idx + 1], CYAN, lw=1.7)
            cax.set_ylabel(fa_text("ارتفاع (m)"), fontproperties=reg, fontsize=8.3, color=CYAN, labelpad=2)
        cax.set_xlabel(fa_text("زمان از باز شدن چتر (ثانیه)"), fontproperties=reg, fontsize=9,
                        color=TEXT_DIM)

        if an.vel is not None:
            cax2 = cax.twinx()
            v_desc = np.abs(an.vel[p_idx:l_idx + 1])
            cax2.plot(t_rel, v_desc, color=PURPLE, lw=1.8, alpha=0.9, zorder=6)
            cax2.set_ylabel(fa_text("سرعت نزول (m/s)"), fontproperties=reg, fontsize=8.3, color=PURPLE, labelpad=2)
            cax2.tick_params(colors=PURPLE, labelsize=8.5)
            cax2.spines["right"].set_color(PURPLE)
            cax2.spines["right"].set_alpha(0.5)
            cax2.spines["top"].set_visible(False)
            if reg:
                for lbl in cax2.get_yticklabels():
                    lbl.set_fontproperties(reg)
                    lbl.set_fontsize(8.5)

        pages.append((fig, ax))

    return pages


# ====================================================================
# نقطهٔ ورود اصلی
# ====================================================================
def draw_footer_logo(ax, logo_img):
    """فقط لوگوی کوچک کافنا در پایین صفحه (بدون متن «پایان گزارش») -- برای
    صفحات اول و دوم، تا امضای برند در سراسر گزارش یکدست باشد."""
    if logo_img is not None:
        try:
            draw_logo(ax, logo_img, x_center=0.5, y_top=0.056, width_data=0.034)
        except Exception:
            pass


def draw_closing_footer(ax, logo_img, reg):
    """لوگوی کوچک کافنا + پیام پایانی -- فقط روی صفحهٔ واقعاً آخر گزارش."""
    from core.report_text import fa_text
    if logo_img is not None:
        try:
            draw_logo(ax, logo_img, x_center=0.5, y_top=0.078, width_data=0.042)
        except Exception:
            pass
    ax.text(0.5, 0.028, fa_text("پایان گزارش -- تولید خودکار توسط سامانهٔ کنترل زمینی RocketGCS"),
            ha="center", va="bottom", fontsize=7.3, color=TEXT_DIM, fontproperties=reg, zorder=4)


def generate_hud_pdf(path: str, mission, motor, results: dict, flight_df, suggestions: list,
                      bw: bool = False, prediction=None):
    """تولید کامل گزارش PDF گرافیکی HUD -- تک‌فایل، تماماً با matplotlib.
    لوگوی کافنا دیگر در ابتدای گزارش نیست؛ فقط یک‌بار، کوچک، در پایینِ
    صفحهٔ واقعاً آخر گزارش (هرکدام که باشد: تحلیل چتر / شتاب / نتایج) می‌آید.

    bw=True: نسخهٔ سیاه‌وسفید کم‌مصرف جوهر برای پرینت -- همان چیدمان و
    محتوای دقیق گزارش رنگی، فقط با پالت خاکستری/سیاه و بدون جلوه‌های
    درخشش (Glow) و شبکهٔ نقطه‌ای پرمصرف جوهر."""
    from core.report_text import get_asset_path, fa_text_selftest

    _apply_theme(bw)
    reg, bold = _load_fonts()
    plt.rcParams["font.family"] = (reg.get_name() if reg else "DejaVu Sans")

    fa_ok, fa_detail = fa_text_selftest()

    logo_path = get_asset_path("kafna_logo.png")
    logo_img = None
    if logo_path:
        try:
            logo_img = plt.imread(logo_path)
        except Exception:
            logo_img = None

    with PdfPages(path) as pdf:
        _build_page1(pdf, mission, motor, results or {}, suggestions or [], reg, bold, fa_ok, fa_detail,
                     logo_img)

        page2 = _build_page2(results or {}, suggestions or [], reg, bold)
        page3 = _build_page3_tables(flight_df, results or {}, prediction, reg, bold)
        chart_pages = _build_chart_pages(flight_df, results or {}, reg, bold)
        remaining = [page2] + ([page3] if page3 is not None else []) + chart_pages

        for i, (fig, ax) in enumerate(remaining):
            is_last = (i == len(remaining) - 1)
            if i == 0 and not is_last:
                draw_footer_logo(ax, logo_img)
            if is_last:
                draw_closing_footer(ax, logo_img, reg)
            pdf.savefig(fig, facecolor=BG)
            plt.close(fig)
