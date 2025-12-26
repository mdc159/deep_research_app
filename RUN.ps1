# Super simple launcher - runs the app in WSL where packages are installed
Write-Host "Starting Deep Research App from WSL..." -ForegroundColor Cyan
Write-Host ""
Write-Host "NOTE: First launch takes 2-3 minutes (ML library loading)" -ForegroundColor Yellow
Write-Host "App will open at http://localhost:8501" -ForegroundColor Green
Write-Host ""

wsl bash -c "cd /mnt/x/GitHub/Deep_research_app/deep_research_app && source .venv/bin/activate && streamlit run app/streamlit_app.py"
