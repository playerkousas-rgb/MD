@echo off
REM ===========================================================
REM  One-time installer (called by PDF2MD.bat / start.bat /
REM  convert.bat).  Pure ASCII, label style.
REM  Return: 0 = ready, 1 = failed
REM ===========================================================
setlocal
cd /d "%~dp0"

if exist ".venv\.deps-ok" exit /b 0

set "PYCMD="
where py >nul 2>nul
if not errorlevel 1 set "PYCMD=py"
if not "%PYCMD%"=="" goto foundpy

where python >nul 2>nul
if not errorlevel 1 set "PYCMD=python"
if not "%PYCMD%"=="" goto foundpy

echo.
echo   [X] Python not found.
echo       Install Python 3.11+ from https://www.python.org/downloads/
echo       IMPORTANT: tick "Add python.exe to PATH" on the first screen.
echo.
exit /b 1

:foundpy
echo   Using: %PYCMD%
%PYCMD% -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)"
if not errorlevel 1 goto newpy
echo.
echo   [!] Python older than 3.11.
echo       Still works, but headings/tables need PyMuPDF 2.0 (Python 3.11+).
echo       Upgrading is recommended.
echo.

:newpy
if exist ".venv" goto venvok
echo   [1/3] Creating virtual environment...
%PYCMD% -m venv .venv
if errorlevel 1 goto mkfail

:venvok
if not exist ".venv\Scripts\python.exe" goto mkfail

echo   [2/3] Installing packages (2-4 minutes, one time only)...
".venv\Scripts\python.exe" -m pip install --upgrade pip -q
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if not errorlevel 1 goto installed

echo   [!] Retrying without pinned versions...
".venv\Scripts\python.exe" -m pip install pymupdf rapidocr-onnxruntime opencv-python-headless opencc-python-reimplemented fastapi "uvicorn[standard]" python-multipart markitdown
if errorlevel 1 goto pipfail

:installed
REM rapidocr pulls in the non-headless opencv-python, which overwrites the
REM headless build; "import cv2" then fails with libGL.so.1 and OCR dies.
echo   [3/3] Fixing OpenCV to headless build...
".venv\Scripts\python.exe" -m pip uninstall -y opencv-python >nul 2>nul
".venv\Scripts\python.exe" -m pip install -q --force-reinstall --no-deps opencv-python-headless

echo ok> ".venv\.deps-ok"
echo   [OK] Ready.
exit /b 0

:mkfail
echo.
echo   [X] Could not create the virtual environment .venv
echo       Try running this file from a folder you own (not C:\Program Files).
exit /b 1

:pipfail
echo.
echo   [X] Package installation failed. Check your internet connection.
echo       If you are behind a proxy, configure it for pip first.
exit /b 1
