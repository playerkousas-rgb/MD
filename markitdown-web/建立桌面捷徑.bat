@echo off
chcp 65001 >nul
REM 在桌面建立「PDF轉Markdown」捷徑(只需執行一次)
setlocal
cd /d "%~dp0"

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$desk=[Environment]::GetFolderPath('Desktop');" ^
  "$lnk=Join-Path $desk 'PDF轉Markdown.lnk';" ^
  "$s=(New-Object -ComObject WScript.Shell).CreateShortcut($lnk);" ^
  "$s.TargetPath='%~dp0轉換PDF.bat';" ^
  "$s.WorkingDirectory='%~dp0';" ^
  "$s.IconLocation='%SystemRoot%\System32\shell32.dll,70';" ^
  "$s.Description='把 PDF 轉成 Markdown(含 OCR)';" ^
  "$s.Save();" ^
  "Write-Host '';Write-Host ('✓ 已在桌面建立捷徑: ' + $lnk) -ForegroundColor Green;" ^
  "Write-Host '  之後直接雙擊桌面那個圖示就可以,不用再開這個資料夾。' -ForegroundColor Gray"

echo.
pause
