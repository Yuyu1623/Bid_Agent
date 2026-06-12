@echo off
chcp 65001 > nul
cd /d "%~dp0"
call "%~dp0start_dowell.bat"
exit /b %ERRORLEVEL%
