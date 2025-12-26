# Launch script for Deep Research App (Windows PowerShell)
# This script activates the virtual environment and starts Streamlit

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Deep Research App Launcher" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if virtual environment exists
$activateScript = $null
if (Test-Path ".venv\Scripts\Activate.ps1") {
    $activateScript = ".venv\Scripts\Activate.ps1"
} elseif (Test-Path ".venv\bin\activate.ps1") {
    $activateScript = ".venv\bin\activate.ps1"
} else {
    Write-Host "ERROR: Virtual environment not found!" -ForegroundColor Red
    Write-Host "Please run: uv venv" -ForegroundColor Yellow
    Write-Host "Then run: uv sync" -ForegroundColor Yellow
    pause
    exit 1
}

Write-Host "[1/3] Activating virtual environment..." -ForegroundColor Green
& $activateScript

Write-Host "[2/3] Checking Streamlit installation..." -ForegroundColor Green
try {
    python -c "import streamlit" 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "Streamlit not installed"
    }
} catch {
    Write-Host "ERROR: Streamlit not installed!" -ForegroundColor Red
    Write-Host "Please run: uv sync" -ForegroundColor Yellow
    pause
    exit 1
}

Write-Host "[3/3] Starting Streamlit application..." -ForegroundColor Green
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "App will open in your browser shortly..." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "NOTE: First launch takes 2-3 minutes due to ML library initialization" -ForegroundColor Yellow
Write-Host "Subsequent launches will be instant!" -ForegroundColor Yellow
Write-Host ""
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Gray
Write-Host ""

streamlit run app\streamlit_app.py
