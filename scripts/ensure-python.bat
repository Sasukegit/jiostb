@echo off
rem Jio STB Dependency Check

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo ================================================================
    echo  [ERROR] Python 3 was not detected on your system!
    echo ================================================================
    echo.
    echo  To use this toolkit, please install Python:
    echo    1. Download from: https://www.python.org/downloads/
    echo    2. Run installer and CHECK: "Add Python to PATH"
    echo    3. Restart your terminal or computer, then run this again.
    echo.
    echo ================================================================
    echo.
    pause
    exit /b 1
)

python -c "import Crypto, requests, urllib3" >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo [*] Checking and installing required Python packages...
    python -m pip install -r "%~dp0..\requirements.txt"
    if %errorlevel% neq 0 (
        echo.
        echo [!] Warning: pip install encountered an error. Proceeding with fallbacks...
    ) else (
        echo [OK] All required packages are successfully installed!
    )
    echo.
)

exit /b 0
