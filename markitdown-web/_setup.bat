@echo off
REM ===========================================================
REM  One-time installer (called by PDF2MD.bat / start.bat /
REM  convert.bat).  Pure ASCII, label style, no bracket blocks.
REM  Return: 0 = ready, 1 = failed
REM
REM  Python choice matters:
REM    PyMuPDF 2.0 needs Python 3.11+ (verified on PyPI:
REM    pymupdf 2.0 requires_python = ">=3.11").
REM    With 3.10 you only ever get pymupdf 1.x, which has no
REM    to_markdown(), so output is plain text: no headings,
REM    no tables.  So we look for a 3.11+ interpreter first,
REM    and rebuild .venv if it was made with an older one.
REM ===========================================================
setlocal
cd /d "%~dp0"

set "PYCMD="
set "PYNOTE="

REM ---- 1. prefer a modern interpreter through the py launcher
py -3.13 -c "import sys; raise SystemExit(sys.version_info[0] < 3 or sys.version_info[1] < 13)" >nul 2>nul
if not errorlevel 1 set "PYCMD=py -3.13"
if not "%PYCMD%"=="" goto havelpy

py -3.12 -c "import sys; raise SystemExit(sys.version_info[0] < 3 or sys.version_info[1] < 12)" >nul 2>nul
if not errorlevel 1 set "PYCMD=py -3.12"
if not "%PYCMD%"=="" goto havelpy

py -3.11 -c "import sys; raise SystemExit(sys.version_info[0] < 3 or sys.version_info[1] < 11)" >nul 2>nul
if not errorlevel 1 set "PYCMD=py -3.11"
if not "%PYCMD%"=="" goto havelpy

REM ---- 2. plain py / python, but only if it is 3.11+
py -c "import sys; raise SystemExit(sys.version_info[0] < 3 or sys.version_info[1] < 11)" >nul 2>nul
if not errorlevel 1 set "PYCMD=py"
if not "%PYCMD%"=="" goto havelpy

python -c "import sys; raise SystemExit(sys.version_info[0] < 3 or sys.version_info[1] < 11)" >nul 2>nul
if not errorlevel 1 set "PYCMD=python"
if not "%PYCMD%"=="" goto havelpy

REM ---- 3. no 3.11+ anywhere. Fall back to whatever python exists,
REM         so the user can still convert (as plain text).
py -c "import sys" >nul 2>nul
if not errorlevel 1 set "PYCMD=py"
if not "%PYCMD%"=="" goto oldpy

python -c "import sys" >nul 2>nul
if not errorlevel 1 set "PYCMD=python"
if not "%PYCMD%"=="" goto oldpy

echo.
echo   [X] Python not found.
echo       Install Python 3.12 from https://www.python.org/downloads/
echo       IMPORTANT: tick "Add python.exe to PATH" on the first screen.
echo.
exit /b 1

:oldpy
echo.
echo   ============================================================
echo    [!] No Python 3.11 or newer was found on this PC.
echo.
echo        PyMuPDF 2.0 requires Python 3.11 or newer - official rule -
echo        so the layout engine cannot be installed with %PYCMD%
echo        You can still convert, but the .md files will be
echo        PLAIN TEXT: no headings, no tables.
echo.
echo        To fix:
echo          1. Install Python 3.12 from
echo             https://www.python.org/downloads/
echo          2. Tick "Add python.exe to PATH"
echo          3. Run PDF2MD.bat again
echo        The old .venv is rebuilt automatically.
echo   ============================================================
echo.
echo   Continuing with the older Python so you can still convert.
echo.
set "PYNOTE=old"
goto checkvenv

:havelpy
echo   Using Python: %PYCMD%
goto checkvenv

REM ---- existing venv? use it only if it is 3.11+
:checkvenv
if not exist ".venv\Scripts\python.exe" goto makevenv
".venv\Scripts\python.exe" -c "import sys; raise SystemExit(sys.version_info[0] < 3 or sys.version_info[1] < 11)" >nul 2>nul
if not errorlevel 1 goto venvfresh

REM venv is older than 3.11
if "%PYNOTE%"=="old" goto venvkeep
echo   [!] Existing .venv uses an old Python. Rebuilding it...
goto rebuildvenv

:venvkeep
if exist ".venv\.deps-ok" goto alreadyok
goto install

:venvfresh
if exist ".venv\.deps-ok" goto alreadyok
goto install

:rebuildvenv
rmdir /s /q ".venv" >nul 2>nul
if exist ".venv" goto delfail
goto makevenv

:makevenv
echo   [1/3] Creating virtual environment...
%PYCMD% -m venv .venv
if errorlevel 1 goto mkfail
if not exist ".venv\Scripts\python.exe" goto mkfail

:install
echo   [2/3] Installing packages, 2 to 4 minutes, one time only...
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
goto writeok

:writeok
echo ok> ".venv\.deps-ok"
echo.
".venv\Scripts\python.exe" _diag_env.py
echo.
echo   [OK] Ready.
exit /b 0

:alreadyok
echo   Environment already installed.
exit /b 0

:delfail
echo.
echo   [X] Could not delete the old .venv folder.
echo       Close any window that is using it, then try again.
echo       Or delete markitdown-web\.venv by hand and re-run.
exit /b 1

:mkfail
echo.
echo   [X] Could not create the virtual environment .venv
echo       Try running this from a folder you own, not C:\Program Files.
exit /b 1

:pipfail
echo.
echo   [X] Package installation failed. Check your internet connection.
echo       If you are behind a proxy, configure it for pip first.
exit /b 1
