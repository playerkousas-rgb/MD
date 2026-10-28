@echo off
REM ===========================================================
REM  Fix an old .venv / old Python.   Double click this file.
REM
REM  Why this exists:
REM    pymupdf 2.0 declares requires_python = ">=3.11" on PyPI.
REM    A .venv built with Python 3.10 can only ever hold pymupdf 1.x,
REM    which has no to_markdown(), so output is plain text with no
REM    headings and no tables - and nothing warns you.
REM
REM  Pure ASCII, label style, no parenthesised blocks.
REM ===========================================================
setlocal
cd /d "%~dp0"
set "GOOD="

echo.
echo ============================================================
echo    Python check for PDF to Markdown
echo ============================================================
echo.

REM ---- what does the existing .venv use?
if not exist ".venv\Scripts\python.exe" goto novenv
echo   Existing .venv reports:
".venv\Scripts\python.exe" -c "import sys,pymupdf;print('     Python',sys.version.split()[0],'/ pymupdf',pymupdf.__version__)"
goto findnew

:novenv
echo   .venv does not exist yet.

:findnew
echo.
echo   Looking for Python 3.11 or newer on this PC...

py -3.13 -c "import sys" >nul 2>nul
if not errorlevel 1 set "GOOD=py -3.13"
if not "%GOOD%"=="" goto havegood

py -3.12 -c "import sys" >nul 2>nul
if not errorlevel 1 set "GOOD=py -3.12"
if not "%GOOD%"=="" goto havegood

py -3.11 -c "import sys" >nul 2>nul
if not errorlevel 1 set "GOOD=py -3.11"
if not "%GOOD%"=="" goto havegood

python -c "import sys; raise SystemExit(sys.version_info[0] < 3 or sys.version_info[1] < 11)" >nul 2>nul
if not errorlevel 1 set "GOOD=python"
if not "%GOOD%"=="" goto havegood

echo.
echo   ------------------------------------------------------------
echo    [!] No Python 3.11+ found.
echo.
echo        Python 3.12 is NOT installed yet, or this window was
echo        opened BEFORE you installed it.
echo.
echo        Do this, in order:
echo.
echo          1. Close every black cmd window.  ALL of them.
echo             Windows locks PATH when a window opens, so a
echo             window opened before the install cannot see it.
echo.
echo          2. Open a NEW cmd as Administrator and run:
echo.
echo               winget install -e --id Python.Python.3.12
echo.
echo          3. Come back and double click this file again.
echo   ------------------------------------------------------------
echo.
goto end

:havegood
echo   Found: %GOOD%
echo.
echo   Removing the old .venv so it can be rebuilt with a modern Python...
rmdir /s /q ".venv" >nul 2>nul
if exist ".venv" goto delfail
echo   Old .venv removed.
echo.
echo   Running the installer. This takes 2 to 4 minutes. Please wait.
echo.
call "%~dp0_setup.bat"
if errorlevel 1 goto setupfail

echo.
echo ============================================================
echo    Final check
echo ============================================================
echo.
".venv\Scripts\python.exe" _diag_env.py
echo.
".venv\Scripts\python.exe" -c "import sys,pymupdf;p=__import__('pymupdf');print('pymupdf',p.__version__,'| to_markdown:',hasattr(p.open(),'to_markdown'))"
echo.
echo   If the two lines above say 'layout available' and 'True',
echo   you are done - double click PDF2MD.bat and convert.
echo.
goto end

:delfail
echo.
echo   [X] Could not delete .venv - a window is probably using it.
echo       Close every PDF2MD / start / cmd window, then retry.
echo.
goto end

:setupfail
echo.
echo   [X] Installation failed. Run _diag.bat and send _diag.txt
echo.
goto end

:end
echo.
echo   Press any key to close this window.
pause >nul
exit /b 0
