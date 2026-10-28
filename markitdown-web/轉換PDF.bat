@echo off
chcp 65001 >nul
REM ============================================================
REM   雙擊我 → 揀資料夾 → 自動轉換 → 自動開結果
REM   也可以把資料夾(或 PDF)直接拖到這個檔案上
REM ============================================================
setlocal
cd /d "%~dp0"

where powershell >nul 2>nul
if errorlevel 1 (
  echo.
  echo [X] 找不到 PowerShell(Windows 7 以下不支援)。
  echo     請改用 start.bat 開網頁版。
  echo.
  pause
  exit /b 1
)

if "%~1"=="" (
  powershell -NoProfile -STA -ExecutionPolicy Bypass -File "%~dp0轉換PDF.ps1"
) else (
  powershell -NoProfile -STA -ExecutionPolicy Bypass -File "%~dp0轉換PDF.ps1" -Target "%~1"
)
