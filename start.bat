@echo off
cd /d "%~dp0"

if not exist "%~dp0logs" mkdir "%~dp0logs"

echo.
echo ========================================
echo Bid Tool Launcher
echo ========================================
echo Project dir: %~dp0
echo Startup log: %~dp0logs\startup.log
echo Backend stdout: %~dp0logs\backend.out.log
echo Backend stderr: %~dp0logs\backend.err.log
echo.

where powershell > nul 2> nul
if errorlevel 1 (
    echo PowerShell was not found. Cannot start.
    pause
    exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start.ps1"
set EXIT_CODE=%ERRORLEVEL%

echo.
if not "%EXIT_CODE%"=="0" (
    echo Startup failed. Exit code: %EXIT_CODE%
    echo Please check logs\startup.log, logs\backend.out.log and logs\backend.err.log.
) else (
    echo Bid Tool exited.
)
echo.
pause
exit /b %EXIT_CODE%
