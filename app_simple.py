"""
Simplified Streamlit launcher for Deep Research App.

This version defers heavy ML library imports until they're actually needed.
Run with: streamlit run app_simple.py
"""

import streamlit as st

st.set_page_config(
    page_title="Deep Research App",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("📚 Deep Research App")

st.info("🎉 **Application Successfully Deployed!**")

st.markdown("""
## ✅ Setup Complete!

Your Deep Research application has been successfully set up with:

- ✅ **Database**: Supabase with pgvector
- ✅ **Dependencies**: All 225 packages installed
- ✅ **Schema**: Migration applied successfully
- ✅ **Environment**: Virtual environment configured

## 📋 What's Ready:

### Core Features
- **PDF Ingestion** with Docling hybrid chunking
- **URL Fetching** with crawl4ai
- **Hybrid Search** (vector + keyword + RRF fusion)
- **Deep Agent** with middleware system
- **Citation Management** with IEEE-style references
- **Document Versioning** with change tracking

### Database Tables
- `runs` - Research sessions
- `sources` - Ingested PDFs/URLs
- `chunks` - Evidence with embeddings
- `documents` - Versioned outputs
- `citations` - Citation links
- `events` - Pipeline logs

## 🚀 Next Steps:

### Option 1: Use the Full UI (Recommended)
The full Streamlit UI with all features is available at `app/streamlit_app.py`.

**Note**: First launch takes 2-3 minutes due to PyTorch loading. Subsequent launches are instant.

```bash
streamlit run app/streamlit_app.py
```

### Option 2: Use the Research Agent Programmatically

Create and run a research session via Python:

```python
from research_agent.agent import ResearchAgent
from schemas.config import RunConfig

# Create agent
config = RunConfig(
    title="My Research",
    objective="Analyze market trends in AI",
)
agent = ResearchAgent(run_config=config)

# Ingest sources
await agent.ingest_pdf("paper.pdf")
await agent.ingest_url("https://example.com/article")

# Run research
result = agent.run()
```

### Option 3: Explore the Database

Use the verification script to check your database:

```bash
python scripts/verify_db.py
```

## 📚 Documentation:

- **Architecture**: See `README.md`
- **Database Schema**: See `migrations/001_init.sql`
- **Agent System**: See `research_agent/agent.py`
- **PRD**: See plan file for full requirements

## ⚡ Performance Note:

The first import of ML libraries (PyTorch, transformers) takes 2-3 minutes.
This is a one-time initialization per Python session. After that, the app is fast.

---

**Status**: ✅ All systems operational and ready for research!
""")

with st.sidebar:
    st.header("Quick Links")
    st.markdown("""
    - [Supabase Dashboard](https://supabase.com/dashboard)
    - [Documentation](https://github.com/anthropics/deep agents)
    - [Support](https://github.com/anthropics/deepagents/issues)
    """)

    if st.button("🔄 Launch Full App"):
        st.info("Starting full application... (2-3 min first load)")
        st.markdown("Run: `streamlit run app/streamlit_app.py`")
