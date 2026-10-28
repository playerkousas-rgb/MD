@echo off
REM  Create a desktop shortcut to PDF2MD.bat  (pure ASCII, label style)
setlocal
cd /d "%~dp0"

if exist "%~dp0PDF2MD.bat" goto ok
echo   [X] PDF2MD.bat not found in this folder.
goto end

:ok
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$d=[Environment]::GetFolderPath('Desktop');" ^
  "$l=Join-Path $d 'PDF to Markdown.lnk';" ^
  "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($l);" ^
  "$s.TargetPath='%~dp0PDF2MD.bat';" ^
  "$s.WorkingDirectory='%~dp0';" ^
  "$s.IconLocation='%SystemRoot%\System32\shell32.dll,70';" ^
  "$s.Description='PDF to Markdown with OCR';" ^
  "$s.Save();" ^
  "Write-Host ''; Write-Host ('  [OK] Shortcut created:'); Write-Host ('       ' + $l); Write-Host '  Double click that icon from now on.'"
echo.
echo   Done.

:end
echo.
echo   Press any key to close this window.
pause >nul
