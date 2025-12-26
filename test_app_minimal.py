"""Minimal test to identify import issues."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

print("Step 1: Testing streamlit import...")
import streamlit as st
print("✅ Streamlit imported")

print("\nStep 2: Testing schemas import...")
from schemas.config import RunConfig
print("✅ schemas.config imported")

print("\nStep 3: Testing storage import...")
from storage.supabase import get_supabase_client
print("✅ storage.supabase imported")

print("\nStep 4: Testing UI imports...")
from app.ui.runs import render_run_details
print("✅ app.ui.runs imported")

from app.ui.evidence import render_evidence_browser
print("✅ app.ui.evidence imported")

from app.ui.composer import render_document_composer
print("✅ app.ui.composer imported")

from app.ui.progress import render_progress_log
print("✅ app.ui.progress imported")

print("\n✅ ALL IMPORTS SUCCESSFUL!")
print("The app should be able to start.")
