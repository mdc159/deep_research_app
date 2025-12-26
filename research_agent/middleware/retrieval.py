"""
Retrieval middleware for the research agent.

This middleware manages evidence search during agent execution.
"""

import logging
from typing import Any
from uuid import UUID

from schemas.config import RetrievalConfig
from schemas.models import SearchResult

logger = logging.getLogger(__name__)


class RetrievalMiddleware:
    """
    Middleware for managing evidence retrieval.

    This middleware:
    - Sets up retrieval context for tools
    - Caches search results
    - Tracks retrieval statistics
    - Provides search tools to the agent
    """

    def __init__(self, config: RetrievalConfig | None = None):
        """
        Initialize the retrieval middleware.

        Args:
            config: Retrieval configuration
        """
        self.config = config or RetrievalConfig()
        self._run_id: UUID | None = None
        self._search_cache: dict[str, list[SearchResult]] = {}
        self._search_count: int = 0
        self._total_results: int = 0

    def set_run(self, run_id: UUID) -> None:
        """
        Set the current run ID for retrieval context.

        Args:
            run_id: Current run ID
        """
        self._run_id = run_id

        # Update tool context
        from research_agent.tools.retrieval import set_retrieval_context
        set_retrieval_context(run_id, self.config)

    def get_tools(self) -> list:
        """
        Get the retrieval tools provided by this middleware.

        Returns:
            List of LangChain tools
        """
        from research_agent.tools.retrieval import (
            get_chunk_tool,
            hybrid_search_tool,
            keyword_search_tool,
            multi_query_search_tool,
            reranked_search_tool,
            semantic_search_tool,
        )

        return [
            hybrid_search_tool,
            semantic_search_tool,
            keyword_search_tool,
            reranked_search_tool,
            get_chunk_tool,
            multi_query_search_tool,
        ]

    def cache_results(self, query: str, results: list[SearchResult]) -> None:
        """
        Cache search results for a query.

        Args:
            query: Search query
            results: Search results
        """
        self._search_cache[query] = results
        self._search_count += 1
        self._total_results += len(results)

    def get_cached_results(self, query: str) -> list[SearchResult] | None:
        """
        Get cached results for a query.

        Args:
            query: Search query

        Returns:
            Cached results or None
        """
        return self._search_cache.get(query)

    def get_all_retrieved_chunks(self) -> set[UUID]:
        """
        Get all unique chunk IDs retrieved in this session.

        Returns:
            Set of chunk IDs
        """
        chunks = set()
        for results in self._search_cache.values():
            for result in results:
                chunks.add(result.chunk_id)
        return chunks

    def get_stats(self) -> dict[str, Any]:
        """
        Get retrieval statistics.

        Returns:
            Dictionary with retrieval stats
        """
        return {
            "search_count": self._search_count,
            "total_results": self._total_results,
            "unique_chunks": len(self.get_all_retrieved_chunks()),
            "cached_queries": len(self._search_cache),
        }

    def reset(self) -> None:
        """Reset retrieval tracking for a new run."""
        self._search_cache = {}
        self._search_count = 0
        self._total_results = 0
        self._run_id = None


def create_retrieval_middleware(
    config: RetrievalConfig | None = None,
) -> RetrievalMiddleware:
    """
    Factory function to create retrieval middleware.

    Args:
        config: Retrieval configuration

    Returns:
        RetrievalMiddleware instance
    """
    return RetrievalMiddleware(config)
