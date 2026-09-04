# -*- mode: python ; coding: utf-8 -*-
"""
RocketGCS.spec
-----------------
فایل ساخت (Build Spec) برای PyInstaller -- نرم‌افزار «کامپیوتر پرواز راکت»
را به یک پوشهٔ اجرایی مستقل (بدون نیاز به نصب پایتون) تبدیل می‌کند.

نحوهٔ استفاده (روی ویندوز، داخل پوشهٔ پروژه):
    pyinstaller RocketGCS.spec

خروجی در پوشهٔ dist/RocketGCS ساخته می‌شود.
"""
import os

block_cipher = None
PROJECT_ROOT = os.path.abspath(".")

a = Analysis(
    ["main.py"],
    pathex=[PROJECT_ROOT],
    binaries=[],
    datas=[
        ("assets", "assets"),   # فونت شبنم، لوگو، موزیک خوش‌آمدگویی
    ],
    hiddenimports=[
        # نمای سه‌بعدی مسیر GPS (pages/gps_map.py -- pyqtgraph.opengl اختیاری)
        "pyqtgraph.opengl",
        "PySide6.QtOpenGL",
        "PySide6.QtOpenGLWidgets",
        "OpenGL.GL",
        "OpenGL.GLU",
        "PySide6.QtMultimedia",
        "pandas._libs.tslibs.base",
        # اصلاح متون فارسی (Reshape/BiDi) در نمودارهای گزارش PDF -- بدون این‌ها
        # PyInstaller این پکیج‌ها را داخل exe نمی‌بندد و متن نمودارها در خروجی
        # نهایی به‌هم می‌ریزد (چون در main.py نصب خودکار runtime کار نمی‌کند)
        "arabic_reshaper",
        "bidi",
        "bidi.algorithm",
        "matplotlib.backends.backend_agg",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "PySide6.QtWebEngineWidgets",
        "PySide6.QtWebEngineCore",
        "PySide6.QtQml",
        "PySide6.QtQuick",
        "PySide6.QtQuick3D",
        "PySide6.QtNetwork",
        "PySide6.QtBluetooth",
        "PySide6.QtNfc",
        "PySide6.QtSensors",
        "PySide6.QtPositioning",
        "PySide6.QtTest",
        "PySide6.QtPdf",
        "PySide6.QtPdfWidgets",
    ],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="RocketGCS",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # بدون پنجرهٔ کنسول سیاه پشت برنامه
    icon="assets/rocketgcs.ico",
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="RocketGCS",
)
