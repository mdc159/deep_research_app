@echo off
REM Super simple launcher - runs the app in WSL where packages are installed
echo Starting Deep Research App from WSL...
echo.
wsl bash -c "cd /mnt/x/GitHub/Deep_research_app/deep_research_app && source .venv/bin/activate && streamlit run app/streamlit_app.py"
