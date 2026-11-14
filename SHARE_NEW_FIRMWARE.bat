@echo off
cd /d "%~dp0"
call "%~dp0scripts\ensure-python.bat"
if %errorlevel% neq 0 exit /b 1

echo ==========================================================
echo Share Discovered Jio Firmware URL to Community Catalog
echo ==========================================================
python share_firmware.py
