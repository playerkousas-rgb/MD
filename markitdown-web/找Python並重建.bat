@echo off
REM ===========================================================
REM  Find Python 3.11+ anywhere on this PC and rebuild .venv.
REM  Double click this file.
REM
REM  Why this exists:
REM    winget can report "Python.Python.3.12 already installed"
REM    while `py -3.12` still fails - the interpreter is on disk
REM    but the py launcher has no entry for it. So we do not trust
REM    the launcher: we scan the real install folders.
REM
REM  pymupdf 2.0 declares requires_python = ">=3.11". A .venv made
REM  with 3.10 can only hold pymupdf 1.x, which has no
REM  to_markdown(), so the output is plain text: no headings, no
REM  tables, and nothing warns you.
REM
REM  Pure ASCII, label style.
REM ===========================================================
setlocal
cd /d "%~dp0"
set "PYEXE="

echo.
echo ============================================================
echo    Find Python 3.11+ and rebuild .venv
echo ============================================================
echo.

echo [1] What is in .venv right now
if not exist ".venv\Scripts\python.exe" goto novenv
".venv\Scripts\python.exe" -c "import sys;print('    Python  ',sys.version.split()[0])"
".venv\Scripts\python.exe" -c "import pymupdf;print('    pymupdf ',pymupdf.__version__)" >nul 2>nul
goto scan

:novenv
echo     .venv does not exist yet

:scan
echo.
echo [2] Searching for Python 3.11+ on this PC
call :try_launcher 3.13
if not "%PYEXE%"=="" goto found
call :try_launcher 3.12
if not "%PYEXE%"=="" goto found
call :try_launcher 3.11
if not "%PYEXE%"=="" goto found
call :scan_dir "%LOCALAPPDATA%\Programs\Python"
if not "%PYEXE%"=="" goto found
call :scan_dir "%ProgramFiles%"
if not "%PYEXE%"=="" goto found
call :scan_dir "%ProgramFiles(x86)%"
if not "%PYEXE%"=="" goto found
call :scan_dir "C:"
if not "%PYEXE%"=="" goto found
goto notfound

REM ---------------------------------------------------------------
:try_launcher
py -%~1 -c "import sys" >nul 2>nul
if errorlevel 1 exit /b 0
echo     py launcher has %~1
for /f "delims=" %%p in ('py -%~1 -c "import sys;print(sys.executable)"') do set "PYEXE=%%p"
if exist "%PYEXE%" exit /b 0
set "PYEXE="
exit /b 0

:scan_dir
if not exist "%~1" exit /b 0
for /d %%d in ("%~1\Python3*") do call :check_path "%%~d\python.exe"
exit /b 0

:check_path
if not "%PYEXE%"=="" exit /b 0
if not exist "%~1" exit /b 0
"%~1" -c "import sys; raise SystemExit(0 if sys.version_info[:2] >= (3, 11) else 1)" >nul 2>nul
if errorlevel 1 exit /b 0
set "PYEXE=%~1"
exit /b 0
REM ---------------------------------------------------------------

:found
echo.
echo     FOUND: %PYEXE%
"%PYEXE%" -c "import sys;print('    Version',sys.version.split()[0])"
echo.
echo [3] Removing the old .venv
rmdir /s /q ".venv" >nul 2>nul
if exist ".venv" goto delfail
echo     removed
echo.
echo [4] Creating a new .venv with the Python found above
"%PYEXE%" -m venv .venv
if errorlevel 1 goto mkfail
if not exist ".venv\Scripts\python.exe" goto mkfail
echo     created
echo.
echo [5] Installing packages through _setup.bat
echo     this takes 2 to 4 minutes, please wait
echo.
call "%~dp0_setup.bat"
if errorlevel 1 goto setupfail

echo.
echo ============================================================
echo    Final check
echo ============================================================
echo.
".venv\Scripts\python.exe" _diag_env.py
echo.
".venv\Scripts\python.exe" -c "import pymupdf;p=__import__('pymupdf');print('pymupdf',p.__version__,'| to_markdown:',hasattr(p.open(),'to_markdown'))"
echo.
echo   If the two lines above say "available" and "True", you are done.
echo   Now double click PDF2MD.bat to convert.
echo.
goto end

:notfound
echo.
echo     not found
echo.
echo   ------------------------------------------------------------
echo    [!] No Python 3.11 or newer exists on this PC.
echo.
echo        winget said "already installed" but the interpreter is
echo        not in any standard folder. Check these two commands
echo        in a cmd window and send me the output:
echo.
echo            py -0p
echo            dir "%LOCALAPPDATA%\Programs\Python"
echo.
echo        Then install fresh with:
echo.
echo            winget install -e --id Python.Python.3.12 --force
echo   ------------------------------------------------------------
echo.
goto end

:delfail
echo.
echo   [X] Could not delete .venv. Close every PDF2MD / cmd window.
echo.
goto end

:mkfail
echo.
echo   [X] Could not create .venv with "%PYEXE%"
echo.
goto end

:setupfail
echo.
echo   [X] Package installation failed. Run _diag.bat.
echo.
goto end

:end
echo.
echo   Press any key to close this window.
pause >nul
exit /b 0
