@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "PROJECT_DIR=%%~fI"

if not exist "%PROJECT_DIR%\logs" mkdir "%PROJECT_DIR%\logs"

where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    py -3 "%PROJECT_DIR%\gold_alert.py" >> "%PROJECT_DIR%\logs\gold-price-alert.log" 2>> "%PROJECT_DIR%\logs\gold-price-alert.error.log"
    exit /b %ERRORLEVEL%
)

where python >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    python "%PROJECT_DIR%\gold_alert.py" >> "%PROJECT_DIR%\logs\gold-price-alert.log" 2>> "%PROJECT_DIR%\logs\gold-price-alert.error.log"
    exit /b %ERRORLEVEL%
)

echo Python launcher not found. Install Python 3 and ensure py or python is in PATH. 1>&2
exit /b 1
