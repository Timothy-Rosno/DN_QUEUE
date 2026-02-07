@echo off
REM Temperature Gateway Launcher
REM Activates virtual environment if present and runs the gateway

cd /d "%~dp0"

REM Check for virtual environment in common locations
if exist ".venv\Scripts\activate.bat" (
    echo Activating virtual environment (.venv)...
    call .venv\Scripts\activate.bat
) else if exist "venv\Scripts\activate.bat" (
    echo Activating virtual environment (venv)...
    call venv\Scripts\activate.bat
) else if exist "..\venv\Scripts\activate.bat" (
    echo Activating virtual environment (../venv)...
    call ..\venv\Scripts\activate.bat
) else if exist "..\.venv\Scripts\activate.bat" (
    echo Activating virtual environment (../.venv)...
    call ..\.venv\Scripts\activate.bat
) else (
    echo No virtual environment found, using system Python...
)

REM Check if gateway_config.json exists
if not exist "gateway_config.json" (
    echo ERROR: gateway_config.json not found!
    echo Copy gateway_config.json.example to gateway_config.json and configure it.
    pause
    exit /b 1
)

REM Run the gateway
echo Starting Temperature Gateway...
python temperature_gateway.py

REM Keep window open if there was an error
if errorlevel 1 (
    echo.
    echo Gateway exited with an error.
    pause
)
