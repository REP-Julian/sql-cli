@echo off
setlocal
cd /d "%~dp0"
echo SQLCLI setup will check CPU and memory before optional Ollama/model setup.
echo It may recommend a smaller model or skip AI setup to stay under the 80% safety limit.
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
