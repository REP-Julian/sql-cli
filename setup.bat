@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
set "RESULT=%ERRORLEVEL%"
echo.
if "%RESULT%"=="0" (
    echo Setup finished. See README.md for how to start SQLCLI.
) else (
    echo Setup stopped with code %RESULT%. Read the message above, fix the issue, then run setup.bat again.
)
echo.
pause
exit /b %RESULT%
