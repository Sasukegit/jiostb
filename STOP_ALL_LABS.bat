@echo off
setlocal
cd /d "%~dp0"

echo ==========================================================
echo       STOPPING JIO STB RESEARCH LABS ^& FREEING PORTS
echo ==========================================================
echo.

net session >nul 2>&1
if %errorLevel% == 0 (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop-labs.ps1"
) else (
    echo [i] Requesting Administrator Privileges...
    powershell.exe -NoProfile -Command "Start-Process cmd.exe -ArgumentList '/c \"\"%~f0\"\"' -Verb RunAs"
)
pause
