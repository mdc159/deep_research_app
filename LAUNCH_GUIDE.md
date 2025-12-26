# 🚀 Deep Research App - Launch Guide

## Quick Start

### Windows Users

#### Option 1: PowerShell (Recommended)
```powershell
.\launch.ps1
```

#### Option 2: Command Prompt
```cmd
launch.bat
```

#### Option 3: Quick Start (Instant Load)
```cmd
launch_simple.bat
```

### Linux/Mac Users

```bash
./launch.sh
```

---

## Launch Scripts Overview

### Full Application (`launch.bat` / `launch.ps1` / `launch.sh`)

**Features:**
- ✅ Complete UI with all features
- ✅ PDF/URL ingestion
- ✅ Hybrid search (vector + keyword)
- ✅ Deep agent with middleware
- ✅ Citation management
- ✅ Document versioning
- ✅ Real-time progress tracking

**First Launch:** 2-3 minutes (PyTorch initialization)
**Subsequent Launches:** Instant

**Usage:**
```powershell
# PowerShell
.\launch.ps1

# Command Prompt
launch.bat

# Linux/Mac
./launch.sh
```

### Quick Start (`launch_simple.bat`)

**Features:**
- ✅ Deployment status dashboard
- ✅ Quick overview of capabilities
- ✅ Links to documentation
- ⚡ **Loads instantly** (no ML libraries)

**Usage:**
```cmd
launch_simple.bat
```

---

## Troubleshooting

### "Virtual environment not found"

**Solution:**
```bash
# Create virtual environment
uv venv

# Install dependencies
uv sync
```

### "Streamlit not installed"

**Solution:**
```bash
# Activate venv first
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Install dependencies
uv sync
```

### "Script execution disabled" (PowerShell)

**Solution:**
Run PowerShell as Administrator and execute:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then try again:
```powershell
.\launch.ps1
```

### First Launch Takes Too Long

This is **normal behavior**. The first launch loads:
- PyTorch (~2GB)
- Transformers
- Docling
- Other ML libraries

**Total initialization time:** 2-3 minutes

**Subsequent launches:** Instant (libraries are cached)

**Alternative:** Use `launch_simple.bat` for instant access to the deployment dashboard.

---

## Manual Launch

If the scripts don't work, you can launch manually:

### Windows (PowerShell)
```powershell
# Navigate to project directory
cd X:\GitHub\Deep_research_app\deep_research_app

# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Launch Streamlit
streamlit run app\streamlit_app.py
```

### Windows (Command Prompt)
```cmd
# Navigate to project directory
cd X:\GitHub\Deep_research_app\deep_research_app

# Activate virtual environment
.venv\Scripts\activate.bat

# Launch Streamlit
streamlit run app\streamlit_app.py
```

### Linux/Mac
```bash
# Navigate to project directory
cd /path/to/deep_research_app

# Activate virtual environment
source .venv/bin/activate

# Launch Streamlit
streamlit run app/streamlit_app.py
```

---

## Environment Variables

Make sure your `.env` file contains:

```env
# LLM Providers
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

# Supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_KEY=eyJ...

# Search
TAVILY_API_KEY=tvly-...
```

---

## Port Configuration

By default, Streamlit runs on:
- **Local:** http://localhost:8501
- **Network:** http://<your-ip>:8501

To change the port, edit the launch script or run manually:
```bash
streamlit run app/streamlit_app.py --server.port 8080
```

---

## Next Steps After Launch

1. **Create a Research Run**
   - Click "New Research Run" in the sidebar
   - Enter title and objective

2. **Add Sources**
   - Upload PDFs
   - Add URLs

3. **Start Research**
   - Click "Start Research" button
   - Monitor progress in real-time

4. **View Results**
   - Browse evidence in the Evidence tab
   - Review generated document in Composer tab
   - Track progress in Log tab

---

## Support

- **Documentation:** See `README.md`
- **Database:** See `migrations/001_init.sql`
- **Architecture:** See plan file
- **Issues:** Check application logs in the terminal

For detailed architecture and implementation details, refer to the main `README.md` file.
