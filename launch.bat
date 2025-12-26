@echo off
REM Launch script for Deep Research App (Windows)
REM This script activates the virtual environment and starts Streamlit

echo ========================================
echo Deep Research App Launcher
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

echo [1/3] Activating virtual environment...
call %ACTIVATE_SCRIPT%

echo [2/3] Checking Streamlit installation...
python -c "import streamlit" 2>nul
if errorlevel 1 (
    echo ERROR: Streamlit not installed!
    echo Please run: uv sync
    pause
    exit /b 1
)

echo [3/3] Starting Streamlit application...
echo.
echo ========================================
echo App will open in your browser shortly...
echo ========================================
echo.
echo Press Ctrl+C to stop the server
echo.

streamlit run app\streamlit_app.py

pause
