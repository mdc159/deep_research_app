"""
Progress log UI component.

Displays real-time progress from agent execution.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any
from uuid import UUID

import streamlit as st

from storage.supabase import get_supabase_client

logger = logging.getLogger(__name__)


def render_progress_log():
    """Render the progress log panel."""
    if not st.session_state.current_run_id:
        st.info("Select a run to view progress")
        return

    st.subheader("📋 Progress Log")

    # Auto-refresh toggle
    auto_refresh = st.checkbox("Auto-refresh", value=True, key="auto_refresh_log")

    if auto_refresh and st.session_state.agent_running:
        st.markdown("🔄 **Live updating...**")

    # Load and display events
    render_event_log()

    # Manual refresh
    if st.button("🔄 Refresh Log", use_container_width=True):
        st.rerun()


def render_event_log():
    """Render the event log."""
    try:
        client = get_supabase_client()
        events = asyncio.run(client.get_events(st.session_state.current_run_id))

        if not events:
            st.info("No events yet. Start the agent to see progress.")
            return

        # Summary stats
        render_event_stats(events)

        st.markdown("---")

        # Event list
        for event in reversed(events[-50:]):  # Show last 50 events, newest first
            render_event_card(event)

    except Exception as e:
        st.error(f"Failed to load events: {e}")
        logger.exception("Event loading failed")


def render_event_stats(events):
    """Render summary statistics for events."""
    # Count by type
    type_counts = {}
    for event in events:
        event_type = event.type
        type_counts[event_type] = type_counts.get(event_type, 0) + 1

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Total Events", len(events))

    with col2:
        tool_calls = type_counts.get("tool_call", 0) + type_counts.get("tool_result", 0)
        st.metric("Tool Calls", tool_calls // 2)

    with col3:
        st.metric("Searches", type_counts.get("search", 0))

    with col4:
        st.metric("Ingestions", type_counts.get("ingestion", 0))


def render_event_card(event):
    """Render a single event card."""
    # Event type icons
    type_icons = {
        "run_start": "🚀",
        "run_complete": "✅",
        "run_error": "❌",
        "tool_call": "🔧",
        "tool_result": "📤",
        "search": "🔍",
        "ingestion": "📥",
        "draft": "✍️",
        "critique": "📝",
        "citation": "📚",
        "node_start": "▶️",
        "node_end": "⏹️",
        "subagent_start": "🤖",
        "subagent_end": "🤖",
    }

    icon = type_icons.get(event.type, "📌")
    timestamp = event.timestamp.strftime("%H:%M:%S") if event.timestamp else ""

    # Determine styling based on event type
    if event.type in ["run_error", "error"]:
        container_style = "error"
    elif event.type in ["run_complete"]:
        container_style = "success"
    else:
        container_style = "info"

    with st.container():
        col1, col2 = st.columns([1, 4])

        with col1:
            st.caption(f"{icon} {timestamp}")

        with col2:
            # Event header
            header = format_event_header(event)
            st.markdown(f"**{header}**")

            # Event details
            if event.payload:
                render_event_details(event)


def format_event_header(event) -> str:
    """Format the event header text."""
    event_type = event.type
    node_name = event.node_name or ""

    headers = {
        "run_start": "Research run started",
        "run_complete": "Research run completed",
        "run_error": "Research run failed",
        "tool_call": f"Calling tool: {node_name}",
        "tool_result": f"Tool result: {node_name}",
        "search": f"Searching: {node_name}",
        "ingestion": f"Ingesting: {node_name}",
        "draft": f"Drafting: {node_name}",
        "critique": f"Critiquing: {node_name}",
        "citation": "Processing citations",
        "node_start": f"Starting: {node_name}",
        "node_end": f"Completed: {node_name}",
        "subagent_start": f"Subagent started: {node_name}",
        "subagent_end": f"Subagent completed: {node_name}",
    }

    return headers.get(event_type, f"{event_type}: {node_name}")


def render_event_details(event):
    """Render event payload details."""
    payload = event.payload

    if not payload:
        return

    # Format based on event type
    if event.type == "tool_call":
        # Show tool arguments
        args = payload.get("args", {})
        if args:
            with st.expander("Arguments", expanded=False):
                st.json(args)

    elif event.type == "tool_result":
        # Show result preview
        result = payload.get("result", "")
        if result:
            preview = str(result)[:200] + "..." if len(str(result)) > 200 else str(result)
            st.caption(preview)

    elif event.type == "search":
        # Show search details
        query = payload.get("query", "")
        results_count = payload.get("results_count", 0)
        st.caption(f"Query: {query[:50]}... | Results: {results_count}")

    elif event.type == "ingestion":
        # Show ingestion details
        source = payload.get("source", "")
        chunks = payload.get("chunks", 0)
        st.caption(f"Source: {source[:30]}... | Chunks: {chunks}")

    elif event.type == "draft":
        # Show draft preview
        section = payload.get("section", "")
        words = payload.get("word_count", 0)
        st.caption(f"Section: {section} | Words: {words}")

    elif event.type in ["run_error", "error"]:
        # Show error details
        error = payload.get("error", "Unknown error")
        st.error(error)

    elif event.type == "run_complete":
        # Show completion summary
        stats = payload.get("stats", {})
        if stats:
            with st.expander("Run Statistics", expanded=True):
                col1, col2 = st.columns(2)

                with col1:
                    st.metric("Sources", stats.get("sources", 0))
                    st.metric("Searches", stats.get("searches", 0))

                with col2:
                    st.metric("Chunks", stats.get("chunks", 0))
                    st.metric("Citations", stats.get("citations", 0))


def render_live_stream():
    """Render live streaming updates from the agent."""
    if not st.session_state.agent_running:
        return

    # Create a placeholder for live updates
    live_placeholder = st.empty()

    # Get events from session state
    events = st.session_state.get("events", [])

    if events:
        with live_placeholder.container():
            st.markdown("### 🔴 Live Updates")

            for event in events[-5:]:  # Show last 5 live events
                render_live_event(event)


def render_live_event(event: dict[str, Any]):
    """Render a live event update."""
    event_type = event.get("type", "unknown")
    data = event.get("data", {})

    icon = {
        "on_tool_start": "🔧",
        "on_tool_end": "✅",
        "on_chat_model_start": "💬",
        "on_chat_model_end": "💬",
        "on_chain_start": "⛓️",
        "on_chain_end": "⛓️",
    }.get(event_type, "📌")

    name = data.get("name", event_type)
    st.caption(f"{icon} {name}")


def push_event(event_type: str, data: dict[str, Any] = None):
    """Push a new event to the session state for live display."""
    if "events" not in st.session_state:
        st.session_state.events = []

    st.session_state.events.append({
        "type": event_type,
        "data": data or {},
        "timestamp": datetime.utcnow(),
    })

    # Keep only last 100 events
    if len(st.session_state.events) > 100:
        st.session_state.events = st.session_state.events[-100:]
