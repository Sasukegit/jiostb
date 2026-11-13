@echo off
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Requesting Administrator privileges...
    powershell -NoProfile -Command "Start-Process cmd.exe -ArgumentList '/c \"\"%~f0\"\"' -Verb RunAs"
    exit /b
)
cd /d "%~dp0"
echo ==========================================================
echo Starting Jio STB Wi-Fi Hotspot ADB Unlock Lab (Universal)
echo ==========================================================
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start-adb-wifi.ps1" -AcsScript "mock_acs_universal.py"
pause
