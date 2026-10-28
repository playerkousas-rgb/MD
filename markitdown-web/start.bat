@echo off
chcp 65001 >nul
REM 一鍵啟動(Windows)
REM   雙擊即可。第一次會自動建立虛擬環境並安裝依賴(約 2-4 分鐘),之後只會啟動。
setlocal
cd /d "%~dp0"

if "%PORT%"=="" set PORT=8000
set READY=.venv\.deps-ok

REM ---------- 1+2. 檢查環境並安裝(共用 _setup.bat) ----------
call "%~dp0_setup.bat"
if errorlevel 1 (
  echo.
  echo [X] 安裝未完成,請看上面的訊息。
  pause
  exit /b 1
)

REM ---------- 3. 啟動 ----------
echo [3/3] 啟動轉換器: http://localhost:%PORT%
echo        ^(關閉此視窗即停止服務^)
start "" "http://localhost:%PORT%"
.\.venv\Scripts\python.exe -m uvicorn app:app --host 0.0.0.0 --port %PORT%

pause
