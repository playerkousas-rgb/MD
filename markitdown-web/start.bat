@echo off
chcp 65001 >nul
REM 一鍵啟動(Windows)
REM   雙擊即可。第一次會自動建立虛擬環境並安裝依賴(約 2-4 分鐘),之後只會啟動。
setlocal
cd /d "%~dp0"

if "%PORT%"=="" set PORT=8000
set READY=.venv\.deps-ok

REM ---------- 1. 找 Python ----------
where py >nul 2>nul && (set PYCMD=py) || (
  where python >nul 2>nul && (set PYCMD=python) || (
    echo.
    echo [X] 找不到 Python。
    echo     請先安裝 Python 3.11 或以上: https://www.python.org/downloads/
    echo     安裝時記得勾選 "Add python.exe to PATH"。
    echo.
    pause
    exit /b 1
  )
)

echo [1/3] 使用 %PYCMD%
%PYCMD% -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)"
if errorlevel 1 (
  echo.
  echo [!] 你的 Python 低於 3.11。
  echo     仍然可用,但沒有「版面分析」^<標題/表格^>,轉出來會是純文字。
  echo     建議升級: https://www.python.org/downloads/
  echo.
)

REM ---------- 2. 建立環境 ----------
if not exist .venv (
  echo [2/3] 第一次執行,建立虛擬環境...
  %PYCMD% -m venv .venv
  if errorlevel 1 (
    echo [X] 建立虛擬環境失敗。
    pause
    exit /b 1
  )
)

if not exist "%READY%" (
  echo [2/3] 安裝依賴 ^(約 2-4 分鐘,只需一次^)...
  .\.venv\Scripts\python.exe -m pip install --upgrade pip -q
  .\.venv\Scripts\python.exe -m pip install -r requirements.txt
  if errorlevel 1 (
    echo.
    echo [!] 安裝過程有問題,嘗試不指定版本重試...
    .\.venv\Scripts\python.exe -m pip install pymupdf rapidocr-onnxruntime opencv-python-headless opencc-python-reimplemented fastapi "uvicorn[standard]" python-multipart markitdown
  )
  REM rapidocr 會硬拉非 headless 的 opencv-python,會覆蓋 headless 版,
  REM 導致 import cv2 失敗 → OCR 失效。這裡強制改回 headless。
  echo [2/3] 修正 OpenCV 為 headless 版...
  .\.venv\Scripts\python.exe -m pip uninstall -y opencv-python >nul 2>nul
  .\.venv\Scripts\python.exe -m pip install -q --force-reinstall --no-deps opencv-python-headless

  echo ok> "%READY%"
  echo [2/3] 依賴安裝完成
)

REM ---------- 3. 啟動 ----------
echo [3/3] 啟動轉換器: http://localhost:%PORT%
echo        ^(關閉此視窗即停止服務^)
start "" "http://localhost:%PORT%"
.\.venv\Scripts\python.exe -m uvicorn app:app --host 0.0.0.0 --port %PORT%

pause
