"""
Deep Research App - Streamlit Entry Point.

This is the main entry point for the Streamlit application.
Run with: streamlit run app/streamlit_app.py
"""

import asyncio
import logging
import sys
from pathlib import Path
from uuid import UUID

import streamlit as st

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from schemas.config import RunConfig, get_settings
from storage.supabase import get_supabase_client

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Page config
st.set_page_config(
    page_title="Deep Research App",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)


def init_session_state():
    """Initialize session state variables."""
    if "current_run_id" not in st.session_state:
        st.session_state.current_run_id = None
    if "current_run" not in st.session_state:
        st.session_state.current_run = None
    if "agent_running" not in st.session_state:
        st.session_state.agent_running = False
    if "events" not in st.session_state:
        st.session_state.events = []
    if "document" not in st.session_state:
        st.session_state.document = None


def render_sidebar():
    """Render the sidebar with run management."""
    with st.sidebar:
        st.title("📚 Deep Research")
        st.markdown("---")

        # Run selection
        st.subheader("Research Runs")

        # Create new run
        with st.expander("➕ New Research Run", expanded=not st.session_state.current_run_id):
            render_new_run_form()

        st.markdown("---")

        # Load existing runs
        render_run_list()

        st.markdown("---")

        # Settings
        with st.expander("⚙️ Settings"):
            render_settings()


def render_new_run_form():
    """Render the new run creation form."""
    with st.form("new_run_form"):
        title = st.text_input("Title", placeholder="e.g., Market Analysis 2024")
        objective = st.text_area(
            "Research Objective",
            placeholder="What do you want to research? Be specific about the questions to answer.",
            height=100,
        )
        constraints = st.text_area(
            "Constraints (optional)",
            placeholder="Any constraints or guidelines? e.g., Focus on US market only",
            height=60,
        )

        submitted = st.form_submit_button("Create Run", use_container_width=True)

        if submitted:
            if not title or not objective:
                st.error("Title and objective are required.")
            else:
                create_new_run(title, objective, constraints)


def create_new_run(title: str, objective: str, constraints: str):
    """Create a new research run."""
    try:
        config = RunConfig(
            title=title,
            objective=objective,
            constraints=constraints if constraints else None,
        )

        client = get_supabase_client()
        run = asyncio.run(client.create_run(config))

        st.session_state.current_run_id = run.id
        st.session_state.current_run = run
        st.success(f"Created run: {title}")
        st.rerun()

    except Exception as e:
        st.error(f"Failed to create run: {e}")
        logger.exception("Run creation failed")


def render_run_list():
    """Render the list of existing runs."""
    try:
        client = get_supabase_client()
        runs = asyncio.run(client.get_runs(limit=10))

        if not runs:
            st.info("No runs yet. Create one above!")
            return

        for run in runs:
            col1, col2 = st.columns([3, 1])
            with col1:
                if st.button(
                    f"📁 {run.title}",
                    key=f"run_{run.id}",
                    use_container_width=True,
                    type="secondary" if str(run.id) != str(st.session_state.current_run_id) else "primary",
                ):
                    st.session_state.current_run_id = run.id
                    st.session_state.current_run = run
                    st.rerun()

            with col2:
                status_emoji = {
                    "created": "🆕",
                    "ingesting": "📥",
                    "researching": "🔍",
                    "drafting": "✍️",
                    "complete": "✅",
                    "failed": "❌",
                }.get(run.status, "❓")
                st.caption(status_emoji)

    except Exception as e:
        st.error(f"Failed to load runs: {e}")


def render_settings():
    """Render the settings panel."""
    settings = get_settings()

    st.text_input("Supabase URL", value=settings.supabase_url or "", disabled=True)
    st.text_input("Anthropic API", value="✓ Set" if settings.anthropic_api_key else "Not set", disabled=True)
    st.text_input("OpenAI API", value="✓ Set" if settings.openai_api_key else "Not set", disabled=True)


def render_main_content():
    """Render the main content area."""
    if not st.session_state.current_run_id:
        render_welcome()
        return

    # Two-column layout
    left_col, right_col = st.columns([1, 2])

    with left_col:
        render_left_pane()

    with right_col:
        render_right_pane()


def render_welcome():
    """Render the welcome screen."""
    st.title("Welcome to Deep Research App")
    st.markdown("""
    This application helps you create evidence-backed research papers with:

    - **PDF & URL Ingestion**: Upload PDFs or fetch web content
    - **Hybrid Search**: Semantic and keyword search across your evidence
    - **AI-Powered Drafting**: Generate structured documents with citations
    - **Citation Management**: Automatic IEEE-style references
    - **Version Control**: Track changes across document revisions

    ### Getting Started

    1. Create a new research run in the sidebar
    2. Add sources (PDFs or URLs)
    3. Start the research agent
    4. Review and export your document
    """)


def render_left_pane():
    """Render the left pane with evidence and controls."""
    from app.ui.evidence import render_evidence_browser
    from app.ui.runs import render_run_details
    from app.ui.progress import render_progress_log

    # Tab navigation
    tab1, tab2, tab3 = st.tabs(["📄 Run", "🔍 Evidence", "📋 Log"])

    with tab1:
        render_run_details()

    with tab2:
        render_evidence_browser()

    with tab3:
        render_progress_log()


def render_right_pane():
    """Render the right pane with document composer."""
    from app.ui.composer import render_document_composer

    render_document_composer()


def main():
    """Main application entry point."""
    init_session_state()
    render_sidebar()
    render_main_content()


if __name__ == "__main__":
    main()
