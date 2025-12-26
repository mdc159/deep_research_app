╔════════════════════════════════════════╗
║   DEEP RESEARCH APP - START HERE      ║
╚════════════════════════════════════════╝

SUPER SIMPLE - JUST RUN THIS:
═════════════════════════════════════════

From PowerShell or Command Prompt:

    RUN.bat

OR from PowerShell only:

    .\RUN.ps1

═════════════════════════════════════════
WHAT HAPPENS:
═════════════════════════════════════════

✅ Automatically runs in WSL (where packages are installed)
✅ Activates virtual environment
✅ Launches Streamlit
✅ Opens at http://localhost:8501

═════════════════════════════════════════
IMPORTANT NOTES:
═════════════════════════════════════════

⏱️  First Launch: 2-3 minutes
    (PyTorch and ML libraries loading)

⚡  After First Time: INSTANT
    (Libraries cached in memory)

🌐  Access App:
    http://localhost:8501
    (Will auto-open in browser)

🛑  Stop Server:
    Press Ctrl+C in the terminal

═════════════════════════════════════════
ALTERNATIVE: Run Directly from WSL
═════════════════════════════════════════

1. Open WSL terminal (type 'wsl' in PowerShell)

2. Navigate to project:
   cd /mnt/x/GitHub/Deep_research_app/deep_research_app

3. Run launcher:
   ./launch.sh

═════════════════════════════════════════
TROUBLESHOOTING:
═════════════════════════════════════════

Problem: "wsl: command not found"
Solution: WSL not installed. Install from Microsoft Store.

Problem: PowerShell execution policy error
Solution: Run as Admin:
    Set-ExecutionPolicy RemoteSigned -Scope CurrentUser

═════════════════════════════════════════

Ready? Just type:  RUN.bat

═════════════════════════════════════════
