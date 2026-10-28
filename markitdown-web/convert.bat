@echo off
REM ===========================================================
REM  Batch convert a folder and keep this window open for logs.
REM  Drag a folder onto this file, or double click and paste a path.
REM  Pure ASCII, label style (see note in PDF2MD.bat).
REM ===========================================================
setlocal
cd /d "%~dp0"

if exist ".venv\.deps-ok" goto ready
echo   First run: installing, this takes 2-4 minutes.
call "%~dp0_setup.bat"
if errorlevel 1 goto setupfail

:ready
set "SRC=%~1"
if not "%SRC%"=="" goto got

echo.
echo   Drag a folder onto this window, or paste its path.
set "SRC="
set /p "SRC=> "

:got
if "%SRC%"=="" goto nosrc
if not exist "%SRC%\" goto nofolder
if "%SRC:~-1%"=="\" set "SRC=%SRC:~0,-1%"
set "OUT=%SRC%-md"

echo.
echo   Source: %SRC%
echo   Output: %OUT%
echo.
".venv\Scripts\python.exe" "batch_convert.py" "%SRC%" -o "%OUT%" --ocr auto --workers 2
echo.
echo   Done. Files are in: %OUT%
goto end

:setupfail
echo.
echo   [X] Installation failed.
goto end

:nosrc
echo.
echo   Nothing entered.
goto end

:nofolder
echo.
echo   [X] Folder not found: %SRC%
goto end

:end
echo.
echo   Press any key to close this window.
pause >nul
exit /b
