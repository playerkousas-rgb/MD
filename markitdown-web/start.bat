@echo off
REM  Start the web UI at http://localhost:8000  (pure ASCII, label style)
setlocal
cd /d "%~dp0"

if not "%PORT%"=="" goto haveport
set "PORT=8000"
:haveport

call "%~dp0_setup.bat"
if errorlevel 1 goto setupfail

echo.
echo   Starting web UI at http://localhost:%PORT%
echo   Close this window to stop the server.
echo.
start "" "http://localhost:%PORT%"
".venv\Scripts\python.exe" -m uvicorn app:app --host 0.0.0.0 --port %PORT%
goto end

:setupfail
echo.
echo   [X] Installation did not finish.

:end
echo.
echo   Press any key to close this window.
pause >nul
exit /b 0
