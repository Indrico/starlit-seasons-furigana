@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0StarlitFurigana\manage.ps1" -Action Uninstall
set "FURIGANA_RESULT=%ERRORLEVEL%"
pause
exit /b %FURIGANA_RESULT%
