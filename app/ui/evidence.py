"""
Evidence browser UI component.

Displays search interface and evidence chunks from ingested sources.
"""

import asyncio
import logging
from uuid import UUID

import streamlit as st

from retrieval.hybrid_search import HybridSearcher
from schemas.config import RetrievalConfig
from storage.supabase import get_supabase_client

logger = logging.getLogger(__name__)


def render_evidence_browser():
    """Render the evidence browser panel."""
    if not st.session_state.current_run_id:
        st.info("Select a run to browse evidence")
        return

    # Search interface
    render_search_interface()

    st.markdown("---")

    # Results or browse mode
    if "search_results" in st.session_state and st.session_state.search_results:
        render_search_results()
    else:
        render_chunk_browser()


def render_search_interface():
    """Render the search input interface."""
    st.subheader("🔍 Search Evidence")

    col1, col2 = st.columns([3, 1])

    with col1:
        query = st.text_input(
            "Search query",
            placeholder="Enter search terms or questions...",
            key="evidence_search_query",
            label_visibility="collapsed",
        )

    with col2:
        search_clicked = st.button("Search", use_container_width=True)

    # Search options
    with st.expander("Search Options", expanded=False):
        col1, col2, col3 = st.columns(3)

        with col1:
            search_type = st.selectbox(
                "Type",
                ["hybrid", "semantic", "keyword"],
                key="search_type",
            )

        with col2:
            top_k = st.number_input(
                "Results",
                min_value=1,
                max_value=50,
                value=10,
                key="search_top_k",
            )

        with col3:
            use_rerank = st.checkbox("Rerank", key="use_rerank")

    # Execute search
    if search_clicked and query:
        execute_search(query, search_type, top_k, use_rerank)

    # Clear results button
    if "search_results" in st.session_state and st.session_state.search_results:
        if st.button("Clear Results", key="clear_search"):
            st.session_state.search_results = None
            st.rerun()


def execute_search(query: str, search_type: str, top_k: int, use_rerank: bool):
    """Execute a search query."""
    try:
        with st.spinner("Searching..."):
            config = RetrievalConfig(
                search_type=search_type,
                use_reranking=use_rerank,
            )
            searcher = HybridSearcher(config)

            results = asyncio.run(
                searcher.search(
                    query=query,
                    run_id=st.session_state.current_run_id,
                    top_k=top_k,
                )
            )

            st.session_state.search_results = results
            st.session_state.search_query = query

    except Exception as e:
        st.error(f"Search failed: {e}")
        logger.exception("Search failed")


def render_search_results():
    """Render search results."""
    results = st.session_state.search_results
    query = st.session_state.get("search_query", "")

    st.markdown(f"**{len(results)} results for:** *{query}*")

    for i, result in enumerate(results):
        with st.container():
            # Result header
            col1, col2 = st.columns([4, 1])

            with col1:
                title = result.source_title[:50] if result.source_title else "Unknown"
                st.markdown(f"**{i + 1}. {title}**")

            with col2:
                st.caption(f"Score: {result.score:.3f}")

            # Location info
            if result.page_start:
                st.caption(f"📍 {result.location_str}")

            # Content preview
            content = result.content
            if len(content) > 300:
                content = content[:300] + "..."

            st.markdown(f"> {content}")

            # Action buttons
            col1, col2, col3 = st.columns(3)

            with col1:
                if st.button("📋 Copy ID", key=f"copy_{result.chunk_id}"):
                    st.code(str(result.chunk_id))

            with col2:
                if st.button("🔍 View Full", key=f"view_{result.chunk_id}"):
                    show_full_chunk(result.chunk_id)

            with col3:
                if st.button("📎 Cite", key=f"cite_{result.chunk_id}"):
                    citation = f"[cite:{result.chunk_id}]"
                    st.code(citation)

            st.markdown("---")


def render_chunk_browser():
    """Render the chunk browser for browsing without search."""
    try:
        client = get_supabase_client()

        # Get sources first
        sources = asyncio.run(client.get_sources(st.session_state.current_run_id))

        if not sources:
            st.info("No sources ingested yet. Add PDFs or URLs to get started.")
            return

        st.markdown(f"**Browse {len(sources)} sources:**")

        # Source filter
        source_options = {str(s.id): s.title for s in sources}
        selected_source = st.selectbox(
            "Filter by source",
            options=["All"] + list(source_options.keys()),
            format_func=lambda x: "All Sources" if x == "All" else source_options.get(x, x)[:40],
            key="source_filter",
        )

        # Get chunks
        if selected_source == "All":
            chunks = asyncio.run(client.get_chunks(st.session_state.current_run_id))
        else:
            chunks = asyncio.run(client.get_chunks(
                st.session_state.current_run_id,
                source_id=UUID(selected_source)
            ))

        if not chunks:
            st.info("No chunks found")
            return

        # Pagination
        page_size = 10
        total_pages = (len(chunks) + page_size - 1) // page_size
        page = st.number_input("Page", min_value=1, max_value=total_pages, value=1)

        start_idx = (page - 1) * page_size
        end_idx = min(start_idx + page_size, len(chunks))

        st.caption(f"Showing {start_idx + 1}-{end_idx} of {len(chunks)} chunks")

        # Display chunks
        for chunk in chunks[start_idx:end_idx]:
            render_chunk_card(chunk)

    except Exception as e:
        st.error(f"Failed to load chunks: {e}")
        logger.exception("Chunk loading failed")


def render_chunk_card(chunk):
    """Render a single chunk card."""
    with st.container():
        # Header
        col1, col2 = st.columns([3, 1])

        with col1:
            if chunk.section_hint:
                st.markdown(f"**{chunk.section_hint}**")
            else:
                st.markdown(f"**Chunk {str(chunk.id)[:8]}...**")

        with col2:
            if chunk.page_start:
                st.caption(f"p.{chunk.page_start}")

        # Content preview
        content = chunk.content
        if len(content) > 200:
            content = content[:200] + "..."
        st.markdown(f"> {content}")

        # Metadata
        st.caption(f"Tokens: {chunk.token_count} | ID: {str(chunk.id)[:8]}...")

        st.markdown("---")


def show_full_chunk(chunk_id: UUID):
    """Show full chunk content in a modal-like expander."""
    try:
        client = get_supabase_client()
        chunk = asyncio.run(client.get_chunk(chunk_id))

        if not chunk:
            st.error("Chunk not found")
            return

        with st.expander(f"Full content: {str(chunk_id)[:8]}...", expanded=True):
            st.markdown(chunk.content)

            if chunk.contextual_prefix:
                st.markdown("---")
                st.markdown("**Context:**")
                st.markdown(chunk.contextual_prefix)

            st.markdown("---")
            col1, col2, col3 = st.columns(3)

            with col1:
                st.caption(f"Source: {chunk.source_id}")
            with col2:
                st.caption(f"Tokens: {chunk.token_count}")
            with col3:
                if chunk.page_start:
                    st.caption(f"Page: {chunk.page_start}")

    except Exception as e:
        st.error(f"Failed to load chunk: {e}")
