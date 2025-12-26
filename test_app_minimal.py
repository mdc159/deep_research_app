"""Minimal smoke tests ensuring key modules import correctly."""

import sys
from pathlib import Path

import pytest


@pytest.fixture(scope="session", autouse=True)
def ensure_repo_root_on_path():
    """Ensure the repository root is on ``sys.path`` for imports."""

    repo_root = str(Path(__file__).resolve().parent)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)


@pytest.mark.parametrize(
    "module_path, expected_attributes",
    [
        ("streamlit", ["__version__"]),
        ("schemas.config", ["RunConfig"]),
        ("storage.supabase", ["get_supabase_client"]),
        (
            "app.ui.runs",
            [
                "render_run_details",
                "render_source_ingestion",
                "render_agent_controls",
            ],
        ),
        ("app.ui.evidence", ["render_evidence_browser"]),
        ("app.ui.composer", ["render_document_composer"]),
        ("app.ui.progress", ["render_progress_log"]),
    ],
)
def test_imports_expose_expected_attributes(module_path, expected_attributes):
    module = pytest.importorskip(module_path)
    for attribute in expected_attributes:
        assert hasattr(module, attribute), f"{module_path} missing {attribute}"
