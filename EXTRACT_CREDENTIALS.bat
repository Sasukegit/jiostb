@echo off
setlocal
cd /d "%~dp0"
set "PATH=%~dp0bin;%PATH%"

echo ==========================================================
echo Extracting Jio STB Device Profile & TR-069 Credentials...
echo ==========================================================
python dump_credentials.py
pause
