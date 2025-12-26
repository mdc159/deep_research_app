"""
UI components for the Streamlit application.

Modules:
- runs: Run management (create, select, delete)
- evidence: Evidence browser (search, filter, preview)
- composer: Document composer (preview, edit, diff)
- progress: Real-time progress display
"""

from app.ui.composer import render_document_composer
from app.ui.evidence import render_evidence_browser
from app.ui.progress import render_progress_log
from app.ui.runs import render_run_details

__all__ = [
    "render_run_details",
    "render_evidence_browser",
    "render_document_composer",
    "render_progress_log",
]
