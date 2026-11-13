@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -File "%~dp0start_local.ps1" -SetupOnly
if errorlevel 1 pause
