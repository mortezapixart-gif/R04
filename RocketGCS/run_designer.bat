@echo off
setlocal
REM no __pycache__ folders next to the code
set PYTHONDONTWRITEBYTECODE=1
REM ============================================================
REM  run_designer.bat -- double-click to start Rocket Designer
REM  Same as:  cd RocketDesigner  +  python main.py
REM ============================================================
cd /d "%~dp0RocketDesigner"

REM ---- find a working Python interpreter ----------------------
set PY=python
%PY% --version >nul 2>nul
if %errorlevel%==0 goto found
set PY=py
%PY% --version >nul 2>nul
if %errorlevel%==0 goto found

echo [ERROR] Python was not found on this system.
echo Install it from https://www.python.org/downloads/
echo and enable "Add python.exe to PATH" during installation.
pause
exit /b 1

:found
echo Using interpreter: %PY%

REM ---- install missing dependencies (first run only) ----------
%PY% -c "import PySide6" >nul 2>nul
if %errorlevel%==0 goto run
echo [SETUP] Installing dependencies, please wait ...
%PY% -m pip install PySide6-Essentials
if %errorlevel%==0 goto run
echo [WARN] pip install failed -- trying to start anyway ...

:run
echo Starting Rocket Designer ...
%PY% main.py
if %errorlevel%==0 goto done
echo.
echo ==========================================
echo   THE APP EXITED WITH AN ERROR (see above)
echo ==========================================
pause

:done
endlocal
