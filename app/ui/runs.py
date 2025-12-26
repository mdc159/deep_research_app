"""
Run management UI component.

Displays run details, source ingestion controls, and agent controls.
"""

import asyncio
import logging
from pathlib import Path
from uuid import UUID

import streamlit as st

from schemas.config import RunConfig
from storage.supabase import get_supabase_client

logger = logging.getLogger(__name__)


def render_run_details():
    """Render the run details panel."""
    if not st.session_state.current_run:
        st.info("Select a run from the sidebar")
        return

    run = st.session_state.current_run

    # Run header
    st.subheader(run.title)

    # Status badge
    status_colors = {
        "created": "blue",
        "ingesting": "orange",
        "researching": "orange",
        "drafting": "orange",
        "complete": "green",
        "failed": "red",
    }
    color = status_colors.get(run.status, "gray")
    st.markdown(f"**Status:** :{color}[{run.status.upper()}]")

    # Objective
    st.markdown("**Objective:**")
    st.markdown(f"> {run.objective}")

    if run.constraints:
        st.markdown("**Constraints:**")
        st.markdown(f"> {run.constraints}")

    st.markdown("---")

    # Source ingestion
    render_source_ingestion()

    st.markdown("---")

    # Agent controls
    render_agent_controls()


def render_source_ingestion():
    """Render source ingestion controls."""
    st.subheader("📥 Add Sources")

    # PDF upload
    with st.expander("Upload PDFs", expanded=False):
        uploaded_files = st.file_uploader(
            "Choose PDF files",
            type=["pdf"],
            accept_multiple_files=True,
            key="pdf_uploader",
        )

        if uploaded_files and st.button("Ingest PDFs", key="ingest_pdfs"):
            ingest_pdfs(uploaded_files)

    # URL input
    with st.expander("Add URLs", expanded=False):
        urls_text = st.text_area(
            "Enter URLs (one per line)",
            placeholder="https://example.com/article1\nhttps://example.com/article2",
            key="url_input",
        )

        if st.button("Fetch URLs", key="fetch_urls"):
            if urls_text:
                urls = [u.strip() for u in urls_text.split("\n") if u.strip()]
                fetch_urls(urls)
            else:
                st.warning("Enter at least one URL")

    # Show ingested sources
    render_source_list()


def ingest_pdfs(uploaded_files):
    """Ingest uploaded PDF files."""
    if not st.session_state.current_run_id:
        st.error("No active run")
        return

    try:
        from ingestion.pdf import PDFIngestionPipeline

        progress = st.progress(0)
        status = st.empty()

        pipeline = PDFIngestionPipeline()
        total = len(uploaded_files)

        for i, file in enumerate(uploaded_files):
            status.text(f"Processing {file.name}...")

            # Save to temp file
            temp_path = Path(f"/tmp/{file.name}")
            temp_path.write_bytes(file.read())

            # Ingest
            asyncio.run(pipeline.ingest(
                pdf_path=temp_path,
                run_id=st.session_state.current_run_id,
                title=file.name,
            ))

            progress.progress((i + 1) / total)

            # Cleanup
            temp_path.unlink()

        status.text("✅ All PDFs ingested!")
        st.rerun()

    except Exception as e:
        st.error(f"Ingestion failed: {e}")
        logger.exception("PDF ingestion failed")


def fetch_urls(urls: list[str]):
    """Fetch and ingest URLs."""
    if not st.session_state.current_run_id:
        st.error("No active run")
        return

    try:
        from ingestion.url import URLIngestionPipeline

        progress = st.progress(0)
        status = st.empty()

        pipeline = URLIngestionPipeline()
        total = len(urls)

        for i, url in enumerate(urls):
            status.text(f"Fetching {url[:50]}...")

            asyncio.run(pipeline.ingest(
                url=url,
                run_id=st.session_state.current_run_id,
            ))

            progress.progress((i + 1) / total)

        status.text("✅ All URLs fetched!")
        st.rerun()

    except Exception as e:
        st.error(f"URL fetch failed: {e}")
        logger.exception("URL fetch failed")


def render_source_list():
    """Render the list of ingested sources."""
    if not st.session_state.current_run_id:
        return

    try:
        client = get_supabase_client()
        sources = asyncio.run(client.get_sources(st.session_state.current_run_id))

        if not sources:
            st.info("No sources ingested yet")
            return

        st.markdown(f"**{len(sources)} sources ingested:**")

        for source in sources[:10]:
            icon = "📄" if source.type == "pdf" else "🌐"
            title = source.title[:40] + "..." if len(source.title) > 40 else source.title
            st.caption(f"{icon} {title}")

        if len(sources) > 10:
            st.caption(f"... and {len(sources) - 10} more")

    except Exception as e:
        st.error(f"Failed to load sources: {e}")


def render_agent_controls():
    """Render agent control buttons."""
    st.subheader("🤖 Research Agent")

    if not st.session_state.current_run:
        return

    run = st.session_state.current_run

    # Check if we have sources
    try:
        client = get_supabase_client()
        sources = asyncio.run(client.get_sources(run.id))
        has_sources = len(sources) > 0
    except Exception:
        has_sources = False

    col1, col2 = st.columns(2)

    with col1:
        if st.session_state.agent_running:
            if st.button("⏹️ Stop", use_container_width=True, type="secondary"):
                st.session_state.agent_running = False
                st.rerun()
        else:
            if st.button(
                "▶️ Start Research",
                use_container_width=True,
                type="primary",
                disabled=not has_sources,
            ):
                start_agent()

    with col2:
        if st.button("🔄 Refresh", use_container_width=True):
            refresh_run()

    if not has_sources:
        st.info("Add sources before starting the agent")

    # Agent status
    if st.session_state.agent_running:
        st.markdown("🔄 **Agent is running...**")


def start_agent():
    """Start the research agent."""
    st.session_state.agent_running = True
    st.session_state.events = []

    # The actual agent execution will be handled asynchronously
    # and updates will be pushed via session state
    st.info("Agent started! Watch the progress in the Log tab.")
    st.rerun()


def refresh_run():
    """Refresh the current run data."""
    if not st.session_state.current_run_id:
        return

    try:
        client = get_supabase_client()
        run = asyncio.run(client.get_run(st.session_state.current_run_id))
        st.session_state.current_run = run
        st.rerun()
    except Exception as e:
        st.error(f"Failed to refresh: {e}")
