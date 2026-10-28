@echo off
chcp 65001 >nul
REM 批量把一個資料夾(含子資料夾)的 PDF 轉成 Markdown
REM
REM 用法(兩種都可以):
REM   1. 把資料夾直接拖到這個 .bat 檔案上
REM   2. 雙擊,然後貼上資料夾路徑
setlocal enabledelayedexpansion
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo.
  echo [X] 尚未安裝。請先雙擊 start.bat 完成一次安裝。
  echo.
  pause
  exit /b 1
)
if not exist ".venv\.deps-ok" (
  echo.
  echo [X] 依賴未安裝完成。請先雙擊 start.bat。
  echo.
  pause
  exit /b 1
)

set "SRC=%~1"
if "%SRC%"=="" (
  echo.
  echo 請把要轉換的資料夾拖進來,或貼上路徑後按 Enter:
  set /p SRC=^> 
)
if "%SRC%"=="" (
  echo 沒有輸入路徑。
  pause
  exit /b 1
)
if not exist "%SRC%\" (
  echo.
  echo [X] 找不到資料夾: %SRC%
  pause
  exit /b 1
)

REM 去掉結尾的反斜線
if "%SRC:~-1%"=="\" set "SRC=%SRC:~0,-1%"

REM 輸出路徑 = 來源資料夾旁邊的「<資料夾名>-md」
for %%I in ("%SRC%") do set "NAME=%%~nxI"
set "OUT=%SRC%-md"

echo.
echo 來源: %SRC%
echo 輸出: %OUT%
echo.
.\.venv\Scripts\python.exe batch_convert.py "%SRC%" -o "%OUT%" --ocr auto --workers 2
echo.
echo 完成。檔案在: %OUT%
echo.
pause
