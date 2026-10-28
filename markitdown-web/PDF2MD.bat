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

if exist ".venv\.deps-ok" goto ready
echo.
echo   First run: installing, this takes 2-4 minutes.
echo   (only once - later runs start immediately)
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
