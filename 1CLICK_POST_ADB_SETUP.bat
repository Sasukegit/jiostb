@echo off
setlocal
cd /d "%~dp0"
set "PATH=%~dp0bin;%PATH%"

call "%~dp0scripts\ensure-python.bat"
if %errorlevel% neq 0 exit /b 1

echo ================================================================
echo   Launching Jio STB 1-Click Post-ADB Setup ^& Debloater Tool...
echo ================================================================
python "%~dp0post_adb_setup.py"
