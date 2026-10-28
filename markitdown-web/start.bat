@echo off
REM 一鍵啟動(Windows)
cd /d "%~dp0"
if not exist .venv (
  echo Building virtual environment...
  py -m venv .venv
  .\.venv\Scripts\python.exe -m pip install -q --upgrade pip
  echo Installing dependencies...
  .\.venv\Scripts\python.exe -m pip install -q -r requirements.txt
)
if "%PORT%"=="" set PORT=8000
echo Starting: http://localhost:%PORT%
.\.venv\Scripts\python.exe -m uvicorn app:app --host 0.0.0.0 --port %PORT%
