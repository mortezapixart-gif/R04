@echo off
REM ============================================================
REM build.bat -- ساخت خودکار نسخهٔ اجرایی ویندوز (بدون نیاز به پایتون
REM               روی سیستم کاربر نهایی)
REM
REM این اسکریپت را روی همان سیستمی اجرا کنید که پایتون رویش نصب است
REM (نه سیستم کاربر نهایی). خروجی، پوشهٔ dist\RocketGCS خواهد بود که
REM از همان‌جا (یا بعد از ساخت Setup.exe با Inno Setup) قابل توزیع است.
REM ============================================================

echo [1/4] ساخت محیط مجازی پایتون (venv)...
python -m venv build_env
call build_env\Scripts\activate.bat

echo [2/4] نصب وابستگی‌های پروژه...
pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

echo [3/4] پاک‌سازی ساخت‌های قبلی...
rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul

echo [4/4] ساخت نسخهٔ اجرایی با PyInstaller...
pyinstaller RocketGCS.spec

echo.
echo ============================================================
echo   تمام شد. خروجی در پوشهٔ dist\RocketGCS قرار دارد.
echo   برای تست: dist\RocketGCS\RocketGCS.exe را اجرا کنید.
echo   برای ساخت فایل نصب (Setup.exe)، مرحلهٔ بعد را در راهنما ببینید.
echo ============================================================
pause
