#!/bin/bash
# Launch script for Deep Research App (Linux/Mac)
# This script activates the virtual environment and starts Streamlit

set -e

echo "========================================"
echo "Deep Research App Launcher"
echo "========================================"
echo ""

# Check if virtual environment exists
if [ ! -f ".venv/bin/activate" ]; then
    echo "ERROR: Virtual environment not found!"
    echo "Please run: uv venv"
    echo "Then run: uv sync"
    exit 1
fi

echo "[1/3] Activating virtual environment..."
source .venv/bin/activate

echo "[2/3] Checking Streamlit installation..."
if ! python -c "import streamlit" 2>/dev/null; then
    echo "ERROR: Streamlit not installed!"
    echo "Please run: uv sync"
    exit 1
fi

echo "[3/3] Starting Streamlit application..."
echo ""
echo "========================================"
echo "App will open in your browser shortly..."
echo "========================================"
echo ""
echo "NOTE: First launch takes 2-3 minutes due to ML library initialization"
echo "Subsequent launches will be instant!"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

streamlit run app/streamlit_app.py
