@echo off
REM ===========================================================
REM  PDF to Markdown - double click this file
REM
REM  Deliberately: pure ASCII + "label style" (no parenthesised
REM  blocks). cmd.exe is unreliable with UTF-8 batch files and
REM  with goto inside ( ) blocks - both cause the window to
REM  flash and vanish with no message.
REM  All Chinese UI text lives in convert-pdf.ps1.
REM ===========================================================
setlocal
cd /d "%~dp0"
set "RC=0"

set "PS1=%~dp0convert-pdf.ps1"
if not exist "%PS1%" goto nops1

where powershell >nul 2>nul
if errorlevel 1 goto nops

REM ---- Decide whether setup is needed.
REM Do NOT just test .venv\.deps-ok: a folder copied from an older run
REM carries an old .venv built with Python 3.10, and that venv can never
REM install PyMuPDF 2.0 (requires_python >=3.11). The result would be
REM plain-text .md with no headings or tables, silently.
if not exist ".venv\Scripts\python.exe" goto needsetup
if not exist ".venv\.deps-ok" goto needsetup
".venv\Scripts\python.exe" -c "import sys; raise SystemExit(0 if sys.version_info[:2] >= (3, 11) else 1)" >nul 2>nul
if errorlevel 1 goto venvold
goto ready

:venvold
echo.
echo   [!] This folder has an old .venv built with Python below 3.11.
echo       PyMuPDF 2.0 needs Python 3.11 or newer, so that venv cannot
echo       produce headings or tables. Setup will try to rebuild it now.
echo.
goto needsetup

:needsetup
echo.
echo   First run: installing, this takes 2-4 minutes.
echo   Only once - later runs start immediately.
echo.
call "%~dp0_setup.bat"
if errorlevel 1 goto setupfail

:ready
if "%~1"=="" goto pick
powershell -NoProfile -STA -ExecutionPolicy Bypass -File "%PS1%" -Target "%~1"
set "RC=%ERRORLEVEL%"
goto after

:pick
powershell -NoProfile -STA -ExecutionPolicy Bypass -File "%PS1%"
set "RC=%ERRORLEVEL%"

:after
if "%RC%"=="0" goto end
echo.
echo   ------------------------------------------------
echo   Failed. Exit code: %RC%
echo   Details saved to: %~dp0_last-run.log
echo   ------------------------------------------------
goto end

:setupfail
set "RC=1"
echo.
echo   [X] Installation did not finish. See messages above.
echo       Tip: run _diag.bat, then send us _diag.txt
goto end

:nops1
set "RC=1"
echo.
echo   [X] convert-pdf.ps1 is missing from this folder.
echo       Did you unzip the whole folder, or only this one file?
echo       PDF2MD.bat and convert-pdf.ps1 must sit in the same folder.
goto end

:nops
set "RC=1"
echo.
echo   [X] Windows PowerShell not found. Windows 7 or newer is required.
goto end

:end
echo.
echo   Press any key to close this window.
pause >nul
exit /b %RC%
