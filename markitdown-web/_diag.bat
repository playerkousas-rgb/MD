@echo off
REM Writes _diag.txt with environment info. Send that file if conversion fails.
setlocal
cd /d "%~dp0"
set "OUT=%~dp0_diag.txt"

(
  echo ==== PDF to Markdown diagnostic ====
  echo Date: %DATE% %TIME%
  echo Folder: %~dp0
  echo.
  echo ---- Windows ----
  ver
  echo.
  echo ---- Python ----
  where py 2^>nul
  where python 2^>nul
  py --version 2^>^&1
  python --version 2^>^&1
  echo.
  echo ---- PowerShell ----
  where powershell 2^>nul
  powershell -NoProfile -Command "$PSVersionTable.PSVersion.ToString()" 2^>^&1
  echo.
  echo ---- Conversion environment ----
  ".venv\Scripts\python.exe" _diag_env.py 2^>^&1
  echo.
  echo ---- Files present ----
  dir /b "%~dp0"
  echo.
  echo ---- Installed state ----
  if exist ".venv\.deps-ok" (echo deps: OK) else (echo deps: NOT INSTALLED)
  if exist ".venv\Scripts\python.exe" (echo venv python: present) else (echo venv python: MISSING)
) > "%OUT%" 2>&1

echo.
echo   Written: %OUT%
echo   Please send this file back.
echo.
start "" notepad "%OUT%"
