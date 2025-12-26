"""
Ingestion middleware for the research agent.

This middleware manages PDF and URL ingestion during agent execution.
"""

import logging
from typing import Any
from uuid import UUID

from schemas.config import IngestionConfig

logger = logging.getLogger(__name__)


class IngestionMiddleware:
    """
    Middleware for managing document ingestion.

    This middleware:
    - Sets up ingestion context for tools
    - Tracks ingestion progress
    - Provides ingestion tools to the agent
    """

    def __init__(self, config: IngestionConfig | None = None):
        """
        Initialize the ingestion middleware.

        Args:
            config: Ingestion configuration
        """
        self.config = config or IngestionConfig()
        self.ingested_sources: list[UUID] = []
        self.ingested_chunks: int = 0
        self._run_id: UUID | None = None

    def set_run(self, run_id: UUID) -> None:
        """
        Set the current run ID for ingestion context.

        Args:
            run_id: Current run ID
        """
        self._run_id = run_id

        # Update tool context
        from research_agent.tools.ingestion import set_run_context
        set_run_context(run_id, self.config)

    def get_tools(self) -> list:
        """
        Get the ingestion tools provided by this middleware.

        Returns:
            List of LangChain tools
        """
        from research_agent.tools.ingestion import (
            batch_url_fetch_tool,
            list_sources_tool,
            pdf_ingest_tool,
            url_fetch_tool,
        )

        return [
            pdf_ingest_tool,
            url_fetch_tool,
            batch_url_fetch_tool,
            list_sources_tool,
        ]

    def on_source_ingested(self, source_id: UUID, chunk_count: int) -> None:
        """
        Callback when a source is ingested.

        Args:
            source_id: ID of the ingested source
            chunk_count: Number of chunks created
        """
        self.ingested_sources.append(source_id)
        self.ingested_chunks += chunk_count
        logger.info(
            f"Source ingested: {source_id} ({chunk_count} chunks). "
            f"Total: {len(self.ingested_sources)} sources, {self.ingested_chunks} chunks"
        )

    def get_stats(self) -> dict[str, Any]:
        """
        Get ingestion statistics.

        Returns:
            Dictionary with ingestion stats
        """
        return {
            "sources_ingested": len(self.ingested_sources),
            "total_chunks": self.ingested_chunks,
            "source_ids": [str(s) for s in self.ingested_sources],
        }

    def reset(self) -> None:
        """Reset ingestion tracking for a new run."""
        self.ingested_sources = []
        self.ingested_chunks = 0
        self._run_id = None


def create_ingestion_middleware(
    config: IngestionConfig | None = None,
) -> IngestionMiddleware:
    """
    Factory function to create ingestion middleware.

    Args:
        config: Ingestion configuration

    Returns:
        IngestionMiddleware instance
    """
    return IngestionMiddleware(config)
