@echo off
setlocal
cd /d "%~dp0"

echo ==========================================================
echo        JIO STB FOTA LAB - ETHERNET MODE (1-CLICK)
echo ==========================================================
echo.

:: Check for administrative permissions
net session >nul 2>&1
if %errorLevel% == 0 (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-ethernet-lab.ps1"
) else (
    echo [i] Requesting Administrator Privileges...
    powershell.exe -NoProfile -Command "Start-Process cmd.exe -ArgumentList '/c \"\"%~f0\"\"' -Verb RunAs"
)
