@echo off
REM Quick launcher for simplified Deep Research App (Windows)
REM This version loads instantly (no ML libraries)

echo ========================================
echo Deep Research App - Quick Start
echo ========================================
echo.

REM Check if virtual environment exists
if exist ".venv\Scripts\activate.bat" (
    set ACTIVATE_SCRIPT=.venv\Scripts\activate.bat
) else if exist ".venv\bin\activate.bat" (
    set ACTIVATE_SCRIPT=.venv\bin\activate.bat
) else (
    echo ERROR: Virtual environment not found!
    echo Please run: uv venv
    echo Then run: uv sync
    pause
    exit /b 1
)

echo [1/2] Activating virtual environment...
call %ACTIVATE_SCRIPT%

echo [2/2] Starting simplified application...
echo.
echo ========================================
echo App will open in your browser shortly...
echo ========================================
echo.
echo This is a lightweight version that loads instantly.
echo For the full app with all features, use launch.bat
echo.
echo Press Ctrl+C to stop the server
echo.

streamlit run app_simple.py

pause
