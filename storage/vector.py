"""
Vector search operations using pgvector.

This module provides:
- Vector similarity search
- Keyword search
- Hybrid search with RRF fusion
"""

import logging
from uuid import UUID

from ingestion.embeddings import EmbeddingClient
from schemas.config import RetrievalConfig, get_settings
from schemas.models import SearchResult
from storage.supabase import get_supabase_client

logger = logging.getLogger(__name__)


class VectorSearch:
    """
    Vector similarity search using pgvector.
    """

    def __init__(self, config: RetrievalConfig | None = None):
        """
        Initialize vector search.

        Args:
            config: Retrieval configuration
        """
        self.config = config or RetrievalConfig()
        self.embedding_client = EmbeddingClient()
        self.client = get_supabase_client()

    async def search(
        self,
        query: str,
        run_id: UUID | None = None,
        top_k: int | None = None,
    ) -> list[SearchResult]:
        """
        Perform vector similarity search.

        Args:
            query: Search query
            run_id: Optional run ID filter
            top_k: Number of results to return

        Returns:
            List of SearchResult models ordered by similarity
        """
        top_k = top_k or self.config.initial_top_k

        # Generate query embedding
        query_embedding = await self.embedding_client.embed_single(query)

        # Call the match_chunks RPC function
        params = {
            "query_embedding": query_embedding,
            "match_count": top_k,
        }

        if run_id:
            params["run_filter"] = str(run_id)

        result = self.client.client.rpc("match_chunks", params).execute()

        # Get source information for results
        results = []
        for r in result.data:
            source = await self._get_source_info(UUID(r["source_id"]))

            results.append(
                SearchResult(
                    chunk_id=UUID(r["id"]),
                    source_id=UUID(r["source_id"]),
                    content=r["content"],
                    contextual_prefix=r.get("contextual_prefix"),
                    page_start=r.get("page_start"),
                    page_end=r.get("page_end"),
                    section_hint=r.get("section_hint"),
                    score=r["similarity"],
                    source_title=source.get("title", "Unknown"),
                    source_uri=source.get("uri", ""),
                    search_type="vector",
                )
            )

        logger.info(f"Vector search returned {len(results)} results")
        return results

    async def _get_source_info(self, source_id: UUID) -> dict:
        """Get source title and URI."""
        result = (
            self.client.client.table("sources")
            .select("title, uri")
            .eq("id", str(source_id))
            .execute()
        )

        if result.data:
            return result.data[0]
        return {"title": "Unknown", "uri": ""}


class KeywordSearch:
    """
    Full-text keyword search using tsvector.
    """

    def __init__(self, config: RetrievalConfig | None = None):
        """
        Initialize keyword search.

        Args:
            config: Retrieval configuration
        """
        self.config = config or RetrievalConfig()
        self.client = get_supabase_client()

    async def search(
        self,
        query: str,
        run_id: UUID | None = None,
        top_k: int | None = None,
    ) -> list[SearchResult]:
        """
        Perform keyword search using full-text search.

        Args:
            query: Search query
            run_id: Optional run ID filter
            top_k: Number of results to return

        Returns:
            List of SearchResult models ordered by relevance
        """
        top_k = top_k or self.config.initial_top_k

        # Call the search_chunks_keyword RPC function
        params = {
            "query_text": query,
            "match_count": top_k,
        }

        if run_id:
            params["run_filter"] = str(run_id)

        result = self.client.client.rpc("search_chunks_keyword", params).execute()

        # Get source information for results
        results = []
        for r in result.data:
            source = await self._get_source_info(UUID(r["source_id"]))

            results.append(
                SearchResult(
                    chunk_id=UUID(r["id"]),
                    source_id=UUID(r["source_id"]),
                    content=r["content"],
                    contextual_prefix=r.get("contextual_prefix"),
                    page_start=r.get("page_start"),
                    page_end=r.get("page_end"),
                    section_hint=r.get("section_hint"),
                    score=r["rank"],
                    source_title=source.get("title", "Unknown"),
                    source_uri=source.get("uri", ""),
                    search_type="keyword",
                )
            )

        logger.info(f"Keyword search returned {len(results)} results")
        return results

    async def _get_source_info(self, source_id: UUID) -> dict:
        """Get source title and URI."""
        result = (
            self.client.client.table("sources")
            .select("title, uri")
            .eq("id", str(source_id))
            .execute()
        )

        if result.data:
            return result.data[0]
        return {"title": "Unknown", "uri": ""}


class HybridSearch:
    """
    Hybrid search combining vector and keyword search with RRF fusion.
    """

    def __init__(self, config: RetrievalConfig | None = None):
        """
        Initialize hybrid search.

        Args:
            config: Retrieval configuration
        """
        self.config = config or RetrievalConfig()
        self.vector_search = VectorSearch(config)
        self.keyword_search = KeywordSearch(config)

    async def search(
        self,
        query: str,
        run_id: UUID | None = None,
        top_k: int | None = None,
    ) -> list[SearchResult]:
        """
        Perform hybrid search with RRF fusion.

        Args:
            query: Search query
            run_id: Optional run ID filter
            top_k: Number of results to return

        Returns:
            List of SearchResult models ordered by combined score
        """
        import asyncio

        top_k = top_k or self.config.final_top_k
        initial_k = self.config.initial_top_k

        # Run both searches in parallel
        vector_results, keyword_results = await asyncio.gather(
            self.vector_search.search(query, run_id, initial_k),
            self.keyword_search.search(query, run_id, initial_k),
        )

        # Apply RRF fusion
        fused_results = self._rrf_fusion(vector_results, keyword_results, top_k)

        logger.info(
            f"Hybrid search: {len(vector_results)} vector + {len(keyword_results)} keyword "
            f"-> {len(fused_results)} fused results"
        )

        return fused_results

    def _rrf_fusion(
        self,
        vector_results: list[SearchResult],
        keyword_results: list[SearchResult],
        top_k: int,
    ) -> list[SearchResult]:
        """
        Apply Reciprocal Rank Fusion to combine results.

        RRF score = sum(1 / (k + rank)) for each result list

        Args:
            vector_results: Vector search results
            keyword_results: Keyword search results
            top_k: Number of results to return

        Returns:
            Fused results ordered by RRF score
        """
        scores: dict[UUID, float] = {}
        result_map: dict[UUID, SearchResult] = {}

        k = self.config.rrf_k

        # Score vector results
        for rank, result in enumerate(vector_results):
            chunk_id = result.chunk_id
            rrf_score = self.config.vector_weight * (1.0 / (k + rank + 1))
            scores[chunk_id] = scores.get(chunk_id, 0) + rrf_score
            result_map[chunk_id] = result

        # Score keyword results
        for rank, result in enumerate(keyword_results):
            chunk_id = result.chunk_id
            rrf_score = self.config.keyword_weight * (1.0 / (k + rank + 1))
            scores[chunk_id] = scores.get(chunk_id, 0) + rrf_score
            if chunk_id not in result_map:
                result_map[chunk_id] = result

        # Sort by combined score
        sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)

        # Build final results
        results = []
        for chunk_id in sorted_ids[:top_k]:
            result = result_map[chunk_id]
            # Update score to RRF score and search type
            result.score = scores[chunk_id]
            result.search_type = "hybrid"
            results.append(result)

        return results


def get_hybrid_searcher(config: RetrievalConfig | None = None) -> HybridSearch:
    """
    Get a hybrid search instance.

    Args:
        config: Retrieval configuration

    Returns:
        HybridSearch instance
    """
    return HybridSearch(config)
