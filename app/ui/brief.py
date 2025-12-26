
"""
Research brief chat UI.

Provides a chat-style interface to collect clarifying questions and
summaries before launching the research agent.
"""

import asyncio
import logging
from typing import Any

import streamlit as st

from research_agent.agent import ResearchAgent
from schemas.config import BriefMessage, ResearchBrief, RunConfig
from storage.supabase import get_supabase_client

logger = logging.getLogger(__name__)


def render_research_brief() -> None:
    """Render the research brief tab with chat and summary controls."""
    run = st.session_state.current_run
    if not run:
        st.info("Select a run to start a research brief")
        return

    brief_state_key = _get_brief_state_key(run.id)
    if brief_state_key not in st.session_state:
        st.session_state[brief_state_key] = _load_brief_state(run.config.brief)

    brief_state: dict[str, Any] = st.session_state[brief_state_key]

    st.subheader("💬 Research Brief")
    st.caption(
        "Use this chat to gather clarifications before launching the agent. "
        "Finalize the brief to enable Start Research."
    )

    _render_chat_history(brief_state)
    _handle_chat_input(run, brief_state)

    st.markdown("---")
    _render_brief_actions(run, brief_state)
    _render_finalization(run, brief_state)


# ---------------------------------------------------------------------------
# Chat handling
# ---------------------------------------------------------------------------


def _render_chat_history(brief_state: dict[str, Any]) -> None:
    """Display the brief conversation."""
    for msg in brief_state["messages"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])


def _handle_chat_input(run, brief_state: dict[str, Any]) -> None:
    """Handle user chat input and agent follow-up."""
    prompt = st.chat_input("Add details or answer the agent's questions", key=f"brief_input_{run.id}")
    if not prompt:
        return

    brief_state["messages"].append({"role": "user", "content": prompt})
    _persist_brief_state(run, brief_state)

    with st.spinner("Letting the agent suggest the next clarifications..."):
        reply = _generate_clarifying_response(run.config, brief_state["messages"])
        if reply:
            brief_state["messages"].append({"role": "assistant", "content": reply})
            _persist_brief_state(run, brief_state)


# ---------------------------------------------------------------------------
# Actions and finalization
# ---------------------------------------------------------------------------


def _render_brief_actions(run, brief_state: dict[str, Any]) -> None:
    """Render action buttons for agent prompts and summaries."""
    col1, col2 = st.columns(2)

    with col1:
        if st.button("🤖 Ask agent for clarifications", use_container_width=True):
            with st.spinner("Generating clarifying questions"):
                reply = _generate_clarifying_response(run.config, brief_state["messages"])
                if reply:
                    brief_state["messages"].append({"role": "assistant", "content": reply})
                    _persist_brief_state(run, brief_state)

    with col2:
        if st.button("🧾 Summarize agreed requirements", use_container_width=True):
            with st.spinner("Summarizing the brief"):
                summary = _summarize_brief(run.config, brief_state["messages"])
                if summary:
                    brief_state["final_summary"] = summary
                    brief_state["finalized"] = False
                    _persist_brief_state(run, brief_state)



def _render_finalization(run, brief_state: dict[str, Any]) -> None:
    """Render finalization controls for the brief."""
    st.markdown("### Finalize Research Brief")
    st.caption(
        "Review the requirements and mark them as final to unlock the research agent."
    )

    current_summary = brief_state.get("final_summary", "")
    updated_summary = st.text_area(
        "Agreed requirements and scope",
        value=current_summary,
        placeholder="Summarize objectives, constraints, success criteria, and sources.",
        height=200,
        key=f"brief_summary_{run.id}",
    )

    cols = st.columns(2)
    with cols[0]:
        if st.button(
            "✅ Finalize brief",
            disabled=not updated_summary.strip(),
            use_container_width=True,
        ):
            brief_state["final_summary"] = updated_summary.strip()
            brief_state["finalized"] = True
            _persist_brief_state(run, brief_state)
            st.success("Brief finalized. You can start research once sources are ready.")

    with cols[1]:
        if st.button(
            "✏️ Reopen for edits",
            disabled=not brief_state.get("finalized", False),
            use_container_width=True,
        ):
            brief_state["finalized"] = False
            _persist_brief_state(run, brief_state)
            st.info("Brief reopened for further edits.")

    if brief_state.get("finalized"):
        st.success("Brief is finalized and ready for the research agent.")
    elif updated_summary.strip():
        st.info("Save and finalize the brief to enable Start Research.")


# ---------------------------------------------------------------------------
# Persistence helpers
# ---------------------------------------------------------------------------


def _load_brief_state(brief: ResearchBrief) -> dict[str, Any]:
    """Convert stored ResearchBrief into a mutable session state dict."""
    return {
        "messages": [m.model_dump() if isinstance(m, BriefMessage) else m for m in brief.messages],
        "final_summary": brief.final_summary or "",
        "finalized": brief.finalized,
    }


def _persist_brief_state(run, brief_state: dict[str, Any]) -> None:
    """Persist brief state to Supabase and session state."""
    brief_model = ResearchBrief(
        messages=[BriefMessage(**m) for m in brief_state.get("messages", [])],
        final_summary=brief_state.get("final_summary") or None,
        finalized=brief_state.get("finalized", False),
    )

    updated_config: RunConfig = run.config.model_copy(update={"brief": brief_model})
    updated_run = run.model_copy(update={"config": updated_config})

    try:
        client = get_supabase_client()
        persisted_run = asyncio.run(client.update_run_config(run.id, updated_config))
        st.session_state.current_run = persisted_run
        updated_run = persisted_run
    except Exception as exc:  # pragma: no cover - defensive logging for UI
        logger.exception("Failed to persist brief state: %s", exc)
        st.error(f"Could not save brief to Supabase: {exc}")

    st.session_state[_get_brief_state_key(run.id)] = _load_brief_state(updated_run.config.brief)


# ---------------------------------------------------------------------------
# LLM helpers
# ---------------------------------------------------------------------------


def _generate_clarifying_response(config: RunConfig, messages: list[dict[str, str]]) -> str:
    """Use the planner model to propose concise clarifying questions."""
    try:
        agent = ResearchAgent(model_config=config.models, run_config=config)
        prompt = _build_clarification_prompt(config, messages)
        return agent.planner_model.predict(prompt)
    except Exception as exc:  # pragma: no cover - model failures handled in UI
        logger.exception("Failed to generate clarifying response: %s", exc)
        st.error(f"Agent failed to generate clarifications: {exc}")
        return ""


def _summarize_brief(config: RunConfig, messages: list[dict[str, str]]) -> str:
    """Use the planner model to summarize the agreed brief."""
    try:
        agent = ResearchAgent(model_config=config.models, run_config=config)
        prompt = _build_summary_prompt(config, messages)
        return agent.planner_model.predict(prompt)
    except Exception as exc:  # pragma: no cover - model failures handled in UI
        logger.exception("Failed to summarize brief: %s", exc)
        st.error(f"Agent failed to summarize the brief: {exc}")
        return ""


def _build_clarification_prompt(config: RunConfig, messages: list[dict[str, str]]) -> str:
    """Format a prompt for generating clarifying questions."""
    conversation = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in messages])
    return (
        "You are preparing a research plan. Based on the conversation, propose up to three "
        "succinct clarifying questions that ensure the objective, constraints, and success "
        "criteria are well understood. Keep it brief and actionable.\n" 
        f"Run title: {config.title}\nObjective: {config.objective}\n"
        f"Conversation so far:\n{conversation}\nQuestions:"
    )


def _build_summary_prompt(config: RunConfig, messages: list[dict[str, str]]) -> str:
    """Format a prompt for summarizing the brief."""
    conversation = "\n".join([f"{m['role'].upper()}: {m['content']}" for m in messages])
    return (
        "Summarize the research brief agreed by the user and assistant. Produce a concise "
        "checklist covering objective, scope, constraints, success criteria, initial sources, "
        "and any open questions. Use bullet points.\n"
        f"Run title: {config.title}\nObjective: {config.objective}\n"
        f"Conversation so far:\n{conversation}\nSummary:"
    )


def _get_brief_state_key(run_id) -> str:
    return f"brief_state_{run_id}"
