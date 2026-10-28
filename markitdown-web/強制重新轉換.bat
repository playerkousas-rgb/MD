@echo off
REM ===========================================================
REM  Force re-convert: overwrite existing .md files.
REM  Double click this file when a previous run said
REM  "skipped (already exists)" and the old .md files were
REM  made before the layout engine was available.
REM
REM  Pure ASCII, label style.
REM ===========================================================
setlocal
cd /d "%~dp0"
set "RC=0"

set "PS1=%~dp0convert-pdf.ps1"
if not exist "%PS1%" goto nops1

if exist ".venv\Scripts\python.exe" goto havevenv
echo.
echo   [X] .venv not found. Run PDF2MD.bat once first.
echo.
goto end

:havevenv
echo.
echo   Force re-convert: existing .md files will be replaced.
echo   Your original PDFs are never modified.
echo.

if "%~1"=="" goto pick
powershell -NoProfile -STA -ExecutionPolicy Bypass -File "%PS1%" -Target "%~1" -Force
set "RC=%ERRORLEVEL%"
goto after

:pick
powershell -NoProfile -STA -ExecutionPolicy Bypass -File "%PS1%" -Force
set "RC=%ERRORLEVEL%"

:after
if "%RC%"=="0" goto end
echo.
echo   ------------------------------------------------
echo   Failed. Exit code: %RC%
echo   Details saved to: %~dp0_last-run.log
echo   ------------------------------------------------
goto end

:nops1
set "RC=1"
echo.
echo   [X] convert-pdf.ps1 is missing from this folder.
echo       Unzip the whole folder, not just one file.
goto end

:end
echo.
echo   Press any key to close this window.
pause >nul
exit /b %RC%
