"""
Middleware for the research agent.

Middleware components:
- IngestionMiddleware: Manages PDF and URL ingestion
- RetrievalMiddleware: Manages evidence search and caching
- CitationMiddleware: Tracks and resolves citations
- CritiqueMiddleware: Manages document quality critique
"""

from research_agent.middleware.citation import (
    CitationMiddleware,
    create_citation_middleware,
)
from research_agent.middleware.critique import (
    CritiqueMiddleware,
    create_critique_middleware,
)
from research_agent.middleware.ingestion import (
    IngestionMiddleware,
    create_ingestion_middleware,
)
from research_agent.middleware.retrieval import (
    RetrievalMiddleware,
    create_retrieval_middleware,
)

__all__ = [
    # Middleware classes
    "IngestionMiddleware",
    "RetrievalMiddleware",
    "CitationMiddleware",
    "CritiqueMiddleware",
    # Factory functions
    "create_ingestion_middleware",
    "create_retrieval_middleware",
    "create_citation_middleware",
    "create_critique_middleware",
]
