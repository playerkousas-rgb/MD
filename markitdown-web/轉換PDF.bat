@echo off
REM Compatibility alias - the real launcher is PDF2MD.bat
REM (ASCII content only, see the note inside PDF2MD.bat)
call "%~dp0PDF2MD.bat" %*
