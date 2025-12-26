"""
Services for the research application.

Services:
- citation: Citation resolution and formatting
- versioning: Document versioning and diff
"""

from services.citation import CitationService
from services.versioning import VersioningService

__all__ = [
    "CitationService",
    "VersioningService",
]
