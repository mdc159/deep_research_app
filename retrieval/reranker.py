"""
Reranking using CrossEncoder models for improved precision.

This module provides:
- CrossEncoder-based reranking for search results
- Batch processing for efficiency
- Integration with hybrid search pipeline
"""

import logging
from typing import Any

from sentence_transformers import CrossEncoder

from schemas.config import RetrievalConfig
from schemas.models import SearchResult

logger = logging.getLogger(__name__)


class Reranker:
    """
    Reranker using CrossEncoder models.

    CrossEncoder models score query-document pairs directly,
    providing more accurate relevance scores than bi-encoder
    similarity for the final ranking.

    Typically used to rerank top-50 results from initial retrieval
    down to final top-10.
    """

    def __init__(
        self,
        model_name: str | None = None,
        config: RetrievalConfig | None = None,
    ):
        """
        Initialize the reranker.

        Args:
            model_name: CrossEncoder model name
            config: Retrieval configuration
        """
        self.config = config or RetrievalConfig()
        self.model_name = model_name or self.config.reranker_model
        self._model: CrossEncoder | None = None

    @property
    def model(self) -> CrossEncoder:
        """Lazy initialization of CrossEncoder model."""
        if self._model is None:
            logger.info(f"Loading reranker model: {self.model_name}")
            self._model = CrossEncoder(self.model_name)
            logger.info("Reranker model loaded")
        return self._model

    def rerank(
        self,
        query: str,
        results: list[SearchResult],
        top_k: int | None = None,
    ) -> list[SearchResult]:
        """
        Rerank search results using CrossEncoder.

        Args:
            query: Original search query
            results: List of search results to rerank
            top_k: Number of results to return after reranking

        Returns:
            Reranked list of SearchResult models
        """
        if not results:
            return []

        top_k = top_k or self.config.final_top_k

        # Create query-document pairs
        pairs = [(query, result.content) for result in results]

        # Get CrossEncoder scores
        scores = self.model.predict(pairs)

        # Combine results with scores and sort
        scored_results = list(zip(results, scores))
        scored_results.sort(key=lambda x: x[1], reverse=True)

        # Build reranked results
        reranked = []
        for result, score in scored_results[:top_k]:
            reranked.append(
                SearchResult(
                    chunk_id=result.chunk_id,
                    source_id=result.source_id,
                    content=result.content,
                    contextual_prefix=result.contextual_prefix,
                    page_start=result.page_start,
                    page_end=result.page_end,
                    section_hint=result.section_hint,
                    score=float(score),
                    source_title=result.source_title,
                    source_uri=result.source_uri,
                    search_type=result.search_type,
                )
            )

        logger.info(f"Reranked {len(results)} results to top {len(reranked)}")
        return reranked

    async def rerank_async(
        self,
        query: str,
        results: list[SearchResult],
        top_k: int | None = None,
    ) -> list[SearchResult]:
        """
        Async wrapper for reranking.

        Note: CrossEncoder prediction is CPU-bound, so this just
        wraps the sync method. Consider using a thread pool for
        truly async behavior in production.

        Args:
            query: Original search query
            results: List of search results to rerank
            top_k: Number of results to return after reranking

        Returns:
            Reranked list of SearchResult models
        """
        import asyncio

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, lambda: self.rerank(query, results, top_k)
        )


class RetrievalPipeline:
    """
    Complete retrieval pipeline with hybrid search and reranking.

    This combines:
    1. Hybrid search (vector + keyword with RRF)
    2. Optional CrossEncoder reranking
    """

    def __init__(
        self,
        config: RetrievalConfig | None = None,
    ):
        """
        Initialize the retrieval pipeline.

        Args:
            config: Retrieval configuration
        """
        from retrieval.hybrid_search import HybridSearcher

        self.config = config or RetrievalConfig()
        self.searcher = HybridSearcher(config)
        self._reranker: Reranker | None = None

    @property
    def reranker(self) -> Reranker | None:
        """Lazy initialization of reranker."""
        if self.config.use_reranking and self._reranker is None:
            self._reranker = Reranker(config=self.config)
        return self._reranker

    async def retrieve(
        self,
        query: str,
        run_id: Any = None,
        top_k: int | None = None,
    ) -> list[SearchResult]:
        """
        Execute the full retrieval pipeline.

        1. Hybrid search to get initial_top_k candidates
        2. Rerank (if enabled) to get final_top_k results

        Args:
            query: Search query
            run_id: Optional run ID filter
            top_k: Number of results to return

        Returns:
            List of SearchResult models
        """
        from uuid import UUID

        # Convert run_id if needed
        if run_id is not None and not isinstance(run_id, UUID):
            run_id = UUID(str(run_id))

        top_k = top_k or self.config.final_top_k

        # Step 1: Hybrid search
        if self.config.use_reranking:
            # Get more candidates for reranking
            initial_results = await self.searcher.search(
                query, run_id, self.config.initial_top_k
            )
        else:
            # Get final count directly
            initial_results = await self.searcher.search(query, run_id, top_k)

        if not initial_results:
            return []

        # Step 2: Rerank if enabled
        if self.config.use_reranking and self.reranker:
            results = await self.reranker.rerank_async(query, initial_results, top_k)
            logger.info(
                f"Retrieval: {len(initial_results)} candidates -> "
                f"{len(results)} after reranking"
            )
            return results

        return initial_results[:top_k]


async def retrieve(
    query: str,
    run_id: Any = None,
    config: RetrievalConfig | None = None,
    top_k: int | None = None,
) -> list[SearchResult]:
    """
    Convenience function for retrieval with reranking.

    Args:
        query: Search query
        run_id: Optional run ID filter
        config: Retrieval configuration
        top_k: Number of results to return

    Returns:
        List of SearchResult models
    """
    pipeline = RetrievalPipeline(config)
    return await pipeline.retrieve(query, run_id, top_k)


def get_reranker(config: RetrievalConfig | None = None) -> Reranker:
    """
    Get a reranker instance.

    Args:
        config: Retrieval configuration

    Returns:
        Reranker instance
    """
    return Reranker(config=config)
