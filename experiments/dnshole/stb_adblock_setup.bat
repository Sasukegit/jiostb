@echo off
setlocal enabledelayedexpansion
title Jio STB Ad-Killer & DNS Sinkhole Setup
color 0b

echo ======================================================================
echo          Jio STB Ad-Killer ^& DNS Sinkhole Setup Launcher
echo ======================================================================
echo.

set "SCRIPT_DIR=%~dp0"
set "PYTHON_EXE=python"
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python was not found in PATH!
    echo Please install Python 3 or add it to PATH.
    pause
    exit /b 1
)

echo Enter your STB IP address (e.g. 192.168.29.10)
echo Or press ENTER to automatically detect currently connected ADB device:
set /p STB_IP="STB IP [Default: Auto-Detect]: "

if "%STB_IP%"=="" (
    python "%SCRIPT_DIR%stb_adblock_setup.py" --disable-ota
) else (
    python "%SCRIPT_DIR%stb_adblock_setup.py" --ip "%STB_IP%" --disable-ota
)

echo.
echo ======================================================================
echo Process finished. Press any key to exit.
echo ======================================================================
pause >nul
