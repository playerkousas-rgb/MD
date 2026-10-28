@echo off
chcp 65001 >nul
REM 共用安裝步驟(由 start.bat / 轉換PDF.bat 呼叫,不需雙擊這個檔案)
REM   回傳 errorlevel 0 = 已就緒,1 = 失敗
setlocal
cd /d "%~dp0"

if exist ".venv\.deps-ok" exit /b 0

where py >nul 2>nul && (set PYCMD=py) || (
  where python >nul 2>nul && (set PYCMD=python) || (
    echo.
    echo [X] 找不到 Python。
    echo     請先安裝 Python 3.11 或以上: https://www.python.org/downloads/
    echo     安裝時記得勾選 "Add python.exe to PATH"。
    echo.
    exit /b 1
  )
)

%PYCMD% -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)"
if errorlevel 1 (
  echo.
  echo [!] 你的 Python 低於 3.11。
  echo     仍然可用,但沒有「版面分析」^<標題/表格^>,轉出來會是純文字。
  echo     建議升級: https://www.python.org/downloads/
  echo.
)

if not exist .venv (
  echo [安裝] 第一次執行,建立虛擬環境...
  %PYCMD% -m venv .venv
  if errorlevel 1 (
    echo [X] 建立虛擬環境失敗。
    exit /b 1
  )
)

echo [安裝] 安裝依賴 ^(約 2-4 分鐘,只需一次^)...
.\.venv\Scripts\python.exe -m pip install --upgrade pip -q
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
  echo [!] 安裝過程有問題,嘗試不指定版本重試...
  .\.venv\Scripts\python.exe -m pip install pymupdf rapidocr-onnxruntime opencv-python-headless opencc-python-reimplemented fastapi "uvicorn[standard]" python-multipart markitdown
  if errorlevel 1 (
    echo [X] 安裝失敗。請檢查網絡連線。
    exit /b 1
  )
)

REM rapidocr 會硬拉非 headless 的 opencv-python,會覆蓋 headless 版,
REM 導致 import cv2 失敗 → OCR 全部失效。這裡強制改回 headless。
echo [安裝] 修正 OpenCV 為 headless 版...
.\.venv\Scripts\python.exe -m pip uninstall -y opencv-python >nul 2>nul
.\.venv\Scripts\python.exe -m pip install -q --force-reinstall --no-deps opencv-python-headless

echo ok> ".venv\.deps-ok"
echo [安裝] 完成
exit /b 0
