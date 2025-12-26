"""
Document composer UI component.

Displays the document preview, editor, and diff views.
"""

import asyncio
import logging
from datetime import datetime
from uuid import UUID

import streamlit as st

from services.citation import CitationService
from services.versioning import VersioningService
from storage.supabase import get_supabase_client

logger = logging.getLogger(__name__)


def render_document_composer():
    """Render the document composer panel."""
    if not st.session_state.current_run_id:
        st.info("Select a run to view documents")
        return

    st.header("📝 Document Composer")

    # Load document versions
    documents = load_documents()

    if not documents:
        render_no_document()
        return

    # Version selector
    render_version_selector(documents)

    # Main tabs
    tab1, tab2, tab3, tab4 = st.tabs(["👁️ Preview", "✏️ Edit", "📊 Diff", "📚 Citations"])

    with tab1:
        render_preview_tab(documents)

    with tab2:
        render_edit_tab(documents)

    with tab3:
        render_diff_tab(documents)

    with tab4:
        render_citations_tab(documents)

    # Export options
    render_export_options(documents)


def load_documents():
    """Load documents for the current run."""
    try:
        client = get_supabase_client()
        documents = asyncio.run(
            client.get_document_versions(st.session_state.current_run_id)
        )
        return documents
    except Exception as e:
        st.error(f"Failed to load documents: {e}")
        return []


def render_no_document():
    """Render the empty state when no document exists."""
    st.info("No document generated yet.")

    st.markdown("""
    To generate a document:

    1. Add sources (PDFs or URLs) in the Run tab
    2. Start the research agent
    3. Wait for the agent to complete its research and drafting

    The agent will automatically:
    - Search your evidence
    - Draft sections with citations
    - Generate a complete document
    """)

    # Option to create a draft manually
    if st.button("📝 Create Manual Draft"):
        create_manual_draft()


def create_manual_draft():
    """Create a manual draft document."""
    try:
        from schemas.config import RunConfig
        from schemas.models import Document
        from uuid import uuid4

        client = get_supabase_client()
        run = st.session_state.current_run

        if not run:
            st.error("No active run")
            return

        # Create initial document
        doc = Document(
            id=uuid4(),
            run_id=run.id,
            version=1,
            title=run.title,
            markdown=f"# {run.title}\n\n## Introduction\n\n[Your content here]\n\n## References\n\nNo citations yet.",
            created_at=datetime.utcnow(),
            change_log="Version 1: Initial draft created manually",
            config_snapshot=RunConfig(
                title=run.title,
                objective=run.objective,
            ),
        )

        asyncio.run(client.store_document(doc))
        st.success("Draft created!")
        st.rerun()

    except Exception as e:
        st.error(f"Failed to create draft: {e}")


def render_version_selector(documents):
    """Render the version selector."""
    if len(documents) <= 1:
        return

    col1, col2 = st.columns([3, 1])

    with col1:
        versions = {d.version: f"v{d.version} - {d.created_at.strftime('%Y-%m-%d %H:%M')}" for d in documents}
        selected_version = st.selectbox(
            "Version",
            options=sorted(versions.keys(), reverse=True),
            format_func=lambda x: versions[x],
            key="selected_version",
        )
        st.session_state.current_document_version = selected_version

    with col2:
        st.caption(f"{len(documents)} versions")


def get_current_document(documents):
    """Get the currently selected document."""
    version = st.session_state.get("current_document_version")

    if version:
        for doc in documents:
            if doc.version == version:
                return doc

    # Default to latest
    return documents[-1] if documents else None


def render_preview_tab(documents):
    """Render the preview tab."""
    doc = get_current_document(documents)

    if not doc:
        st.info("No document to preview")
        return

    # Document metadata
    col1, col2, col3 = st.columns(3)

    with col1:
        st.caption(f"**Title:** {doc.title}")

    with col2:
        st.caption(f"**Version:** {doc.version}")

    with col3:
        st.caption(f"**Created:** {doc.created_at.strftime('%Y-%m-%d %H:%M')}")

    st.markdown("---")

    # Render markdown
    st.markdown(doc.markdown)


def render_edit_tab(documents):
    """Render the edit tab."""
    doc = get_current_document(documents)

    if not doc:
        st.info("No document to edit")
        return

    st.markdown("**Edit the document below:**")

    # Editor
    edited_content = st.text_area(
        "Content",
        value=doc.markdown,
        height=500,
        key="document_editor",
        label_visibility="collapsed",
    )

    # Change description
    change_desc = st.text_input(
        "Change description",
        placeholder="Describe your changes...",
        key="change_description",
    )

    col1, col2 = st.columns(2)

    with col1:
        if st.button("💾 Save as New Version", use_container_width=True, type="primary"):
            save_new_version(doc, edited_content, change_desc)

    with col2:
        if st.button("🔄 Reset", use_container_width=True):
            st.rerun()


def save_new_version(doc, content: str, description: str):
    """Save a new document version."""
    try:
        from services.versioning import VersioningService

        versioning = VersioningService()
        new_doc = versioning.create_revision(
            previous=doc,
            new_markdown=content,
            change_type="edited",
            change_description=description or "Manual edit",
        )

        client = get_supabase_client()
        asyncio.run(client.store_document(new_doc))

        st.success(f"Saved as version {new_doc.version}")
        st.rerun()

    except Exception as e:
        st.error(f"Failed to save: {e}")


def render_diff_tab(documents):
    """Render the diff tab."""
    if len(documents) < 2:
        st.info("Need at least 2 versions to compare")
        return

    col1, col2 = st.columns(2)

    versions = sorted([d.version for d in documents])

    with col1:
        from_version = st.selectbox(
            "From version",
            options=versions[:-1],
            format_func=lambda x: f"v{x}",
            key="diff_from",
        )

    with col2:
        to_options = [v for v in versions if v > from_version]
        to_version = st.selectbox(
            "To version",
            options=to_options,
            format_func=lambda x: f"v{x}",
            key="diff_to",
        )

    if st.button("Compare", use_container_width=True):
        show_diff(documents, from_version, to_version)


def show_diff(documents, from_version: int, to_version: int):
    """Show diff between two versions."""
    from_doc = next((d for d in documents if d.version == from_version), None)
    to_doc = next((d for d in documents if d.version == to_version), None)

    if not from_doc or not to_doc:
        st.error("Version not found")
        return

    versioning = VersioningService()
    diff = versioning.compute_version_diff(from_doc, to_doc)

    # Summary
    st.markdown(f"### Changes: v{from_version} → v{to_version}")
    st.markdown(f"**Summary:** {diff.summary}")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Additions", f"+{diff.additions}")

    with col2:
        st.metric("Deletions", f"-{diff.deletions}")

    with col3:
        st.metric("Modifications", f"~{diff.modifications}")

    # Unified diff
    st.markdown("### Unified Diff")
    st.code(diff.unified_diff, language="diff")

    # Section changes
    section_changes = versioning.get_section_changes(from_doc.markdown, to_doc.markdown)

    if section_changes:
        st.markdown("### Section Changes")
        for section, change in section_changes.items():
            st.markdown(f"- **{section}:** {change}")


def render_citations_tab(documents):
    """Render the citations tab."""
    doc = get_current_document(documents)

    if not doc:
        st.info("No document to analyze")
        return

    # Citation coverage
    citation_service = CitationService()
    report = citation_service.calculate_coverage(doc.markdown)

    st.markdown("### Citation Coverage")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "Coverage",
            f"{report.coverage_percent}%",
            delta="Target: 80%" if report.target_met else "Below target",
            delta_color="normal" if report.target_met else "inverse",
        )

    with col2:
        st.metric("Cited Sentences", report.cited_sentences)

    with col3:
        st.metric("Assumptions", report.assumption_labels)

    # Detailed metrics
    with st.expander("Detailed Metrics"):
        st.markdown(f"- Total sentences: {report.total_sentences}")
        st.markdown(f"- Cited sentences: {report.cited_sentences}")
        st.markdown(f"- Assumptions labeled: {report.assumption_labels}")
        st.markdown(f"- Numerical claims: {report.numerical_claims}")
        st.markdown(f"- Numerical cited: {report.numerical_cited}")

    # Issues
    if report.issues:
        st.markdown("### Issues Found")
        for issue in report.issues[:10]:
            st.warning(issue)

        if len(report.issues) > 10:
            st.caption(f"... and {len(report.issues) - 10} more issues")

    # Citation list
    st.markdown("### Citation List")
    render_citation_list(doc)


def render_citation_list(doc):
    """Render the list of citations in the document."""
    import re

    # Find all citations in the format [N]
    citations = re.findall(r'\[(\d+)\]', doc.markdown)
    unique_citations = sorted(set(int(c) for c in citations))

    if not unique_citations:
        st.info("No resolved citations found")
        return

    # Find references section
    refs_match = re.search(r'## References\s*\n(.*)', doc.markdown, re.DOTALL)

    if refs_match:
        refs_content = refs_match.group(1)
        st.markdown(refs_content)
    else:
        st.info(f"Found {len(unique_citations)} citation references")


def render_export_options(documents):
    """Render export options."""
    doc = get_current_document(documents)

    if not doc:
        return

    st.markdown("---")
    st.subheader("📤 Export")

    col1, col2, col3 = st.columns(3)

    with col1:
        # Markdown download
        st.download_button(
            "📄 Download Markdown",
            data=doc.markdown,
            file_name=f"{doc.title.replace(' ', '_')}_v{doc.version}.md",
            mime="text/markdown",
            use_container_width=True,
        )

    with col2:
        # JSON export
        import json
        export_data = {
            "title": doc.title,
            "version": doc.version,
            "created_at": doc.created_at.isoformat(),
            "markdown": doc.markdown,
            "change_log": doc.change_log,
        }
        st.download_button(
            "📦 Download JSON",
            data=json.dumps(export_data, indent=2),
            file_name=f"{doc.title.replace(' ', '_')}_v{doc.version}.json",
            mime="application/json",
            use_container_width=True,
        )

    with col3:
        if st.button("📋 Copy to Clipboard", use_container_width=True):
            st.code(doc.markdown)
            st.info("Use Ctrl+C to copy")
