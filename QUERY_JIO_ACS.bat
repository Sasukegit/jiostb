@echo off
setlocal
cd /d "%~dp0"

echo ==========================================================
echo       QUERY JIO TR-069 ACS DIRECTLY (STANDALONE)
echo ==========================================================
echo.
echo Queries real Jio ACS (acs.oss.jio.com) directly from PC
echo without needing the physical STB.
echo.

set /p SVER="Enter Software Version to spoof [Default: STB-JHSD200-11.1.0]: "
if "%SVER%"=="" set SVER=STB-JHSD200-11.1.0

echo.
echo Running query with version: %SVER%
python query_acs_direct.py "%SVER%"

echo.
pause
