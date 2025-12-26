"""
Hybrid search combining vector similarity and keyword matching.

This module provides:
- Vector search via pgvector
- Keyword search via tsvector
- RRF (Reciprocal Rank Fusion) for combining results
"""

import asyncio
import logging
from uuid import UUID

from ingestion.embeddings import EmbeddingClient
from schemas.config import RetrievalConfig, get_settings
from schemas.models import SearchResult
from storage.supabase import SupabaseClient, get_supabase_client

logger = logging.getLogger(__name__)


class HybridSearcher:
    """
    Hybrid search combining vector similarity and keyword matching.

    Uses Reciprocal Rank Fusion (RRF) to combine results from both
    search methods, providing robust retrieval for both semantic
    and exact keyword queries.

    RRF formula: score = sum(weight * 1/(k + rank)) for each method
    """

    def __init__(
        self,
        config: RetrievalConfig | None = None,
        client: SupabaseClient | None = None,
    ):
        """
        Initialize the hybrid searcher.

        Args:
            config: Retrieval configuration
            client: Optional Supabase client
        """
        self.config = config or RetrievalConfig()
        self.client = client or get_supabase_client()
        self.embedding_client = EmbeddingClient()

        # Cache for source information
        self._source_cache: dict[UUID, dict] = {}

    async def search(
        self,
        query: str,
        run_id: UUID | None = None,
        top_k: int | None = None,
    ) -> list[SearchResult]:
        """
        Execute hybrid search with RRF fusion.

        Args:
            query: Search query text
            run_id: Optional run ID to filter results
            top_k: Number of results to return (default: config.final_top_k)

        Returns:
            List of SearchResult models ordered by combined RRF score
        """
        top_k = top_k or self.config.final_top_k
        initial_k = self.config.initial_top_k

        # Determine search type
        if self.config.search_type == "vector":
            return await self._vector_search(query, run_id, top_k)
        elif self.config.search_type == "keyword":
            return await self._keyword_search(query, run_id, top_k)
        else:
            # Hybrid search with parallel execution
            vector_results, keyword_results = await asyncio.gather(
                self._vector_search(query, run_id, initial_k),
                self._keyword_search(query, run_id, initial_k),
            )

            # Apply RRF fusion
            fused_results = self._rrf_merge(vector_results, keyword_results, top_k)

            logger.info(
                f"Hybrid search: {len(vector_results)} vector + "
                f"{len(keyword_results)} keyword -> {len(fused_results)} fused"
            )

            return fused_results

    async def _vector_search(
        self,
        query: str,
        run_id: UUID | None,
        top_k: int,
    ) -> list[SearchResult]:
        """
        Perform vector similarity search.

        Args:
            query: Search query
            run_id: Optional run ID filter
            top_k: Number of results

        Returns:
            List of SearchResult models
        """
        # Generate query embedding
        query_embedding = await self.embedding_client.embed_single(query)

        # Build RPC parameters
        params = {
            "query_embedding": query_embedding,
            "match_count": top_k,
        }

        if run_id:
            params["run_filter"] = str(run_id)

        # Execute vector search
        result = self.client.client.rpc("match_chunks", params).execute()

        # Convert to SearchResult models
        results = []
        for r in result.data:
            source_id = UUID(r["source_id"])
            source_info = await self._get_source_info(source_id)

            results.append(
                SearchResult(
                    chunk_id=UUID(r["id"]),
                    source_id=source_id,
                    content=r["content"],
                    contextual_prefix=r.get("contextual_prefix"),
                    page_start=r.get("page_start"),
                    page_end=r.get("page_end"),
                    section_hint=r.get("section_hint"),
                    score=float(r["similarity"]),
                    source_title=source_info.get("title", "Unknown"),
                    source_uri=source_info.get("uri", ""),
                    search_type="vector",
                )
            )

        return results

    async def _keyword_search(
        self,
        query: str,
        run_id: UUID | None,
        top_k: int,
    ) -> list[SearchResult]:
        """
        Perform keyword search using full-text search.

        Args:
            query: Search query
            run_id: Optional run ID filter
            top_k: Number of results

        Returns:
            List of SearchResult models
        """
        # Build RPC parameters
        params = {
            "query_text": query,
            "match_count": top_k,
        }

        if run_id:
            params["run_filter"] = str(run_id)

        # Execute keyword search
        result = self.client.client.rpc("search_chunks_keyword", params).execute()

        # Convert to SearchResult models
        results = []
        for r in result.data:
            source_id = UUID(r["source_id"])
            source_info = await self._get_source_info(source_id)

            results.append(
                SearchResult(
                    chunk_id=UUID(r["id"]),
                    source_id=source_id,
                    content=r["content"],
                    contextual_prefix=r.get("contextual_prefix"),
                    page_start=r.get("page_start"),
                    page_end=r.get("page_end"),
                    section_hint=r.get("section_hint"),
                    score=float(r["rank"]),
                    source_title=source_info.get("title", "Unknown"),
                    source_uri=source_info.get("uri", ""),
                    search_type="keyword",
                )
            )

        return results

    def _rrf_merge(
        self,
        vector_results: list[SearchResult],
        keyword_results: list[SearchResult],
        top_k: int,
    ) -> list[SearchResult]:
        """
        Merge results using Reciprocal Rank Fusion.

        RRF combines rankings from multiple retrieval methods by assigning
        scores based on rank position rather than raw scores, making it
        robust to score distribution differences.

        Formula: RRF(d) = sum(weight * 1/(k + rank(d)))

        Args:
            vector_results: Results from vector search
            keyword_results: Results from keyword search
            top_k: Number of results to return

        Returns:
            Merged and re-ranked results
        """
        scores: dict[UUID, float] = {}
        result_map: dict[UUID, SearchResult] = {}

        k = self.config.rrf_k

        # Score vector results
        for rank, result in enumerate(vector_results):
            chunk_id = result.chunk_id
            rrf_score = self.config.vector_weight * (1.0 / (k + rank + 1))
            scores[chunk_id] = scores.get(chunk_id, 0.0) + rrf_score
            result_map[chunk_id] = result

        # Score keyword results
        for rank, result in enumerate(keyword_results):
            chunk_id = result.chunk_id
            rrf_score = self.config.keyword_weight * (1.0 / (k + rank + 1))
            scores[chunk_id] = scores.get(chunk_id, 0.0) + rrf_score

            # Keep the first occurrence (usually vector result has more info)
            if chunk_id not in result_map:
                result_map[chunk_id] = result

        # Sort by combined RRF score
        sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)

        # Build final results with updated scores
        results = []
        for chunk_id in sorted_ids[:top_k]:
            result = result_map[chunk_id]
            # Create new result with RRF score
            results.append(
                SearchResult(
                    chunk_id=result.chunk_id,
                    source_id=result.source_id,
                    content=result.content,
                    contextual_prefix=result.contextual_prefix,
                    page_start=result.page_start,
                    page_end=result.page_end,
                    section_hint=result.section_hint,
                    score=scores[chunk_id],
                    source_title=result.source_title,
                    source_uri=result.source_uri,
                    search_type="hybrid",
                )
            )

        return results

    async def _get_source_info(self, source_id: UUID) -> dict:
        """
        Get source information with caching.

        Args:
            source_id: Source ID

        Returns:
            Dict with title and uri
        """
        if source_id in self._source_cache:
            return self._source_cache[source_id]

        result = (
            self.client.client.table("sources")
            .select("title, uri")
            .eq("id", str(source_id))
            .execute()
        )

        if result.data:
            info = result.data[0]
            self._source_cache[source_id] = info
            return info

        return {"title": "Unknown", "uri": ""}

    def clear_cache(self) -> None:
        """Clear the source information cache."""
        self._source_cache.clear()


async def hybrid_search(
    query: str,
    run_id: UUID | None = None,
    config: RetrievalConfig | None = None,
    top_k: int | None = None,
) -> list[SearchResult]:
    """
    Convenience function for hybrid search.

    Args:
        query: Search query
        run_id: Optional run ID filter
        config: Retrieval configuration
        top_k: Number of results to return

    Returns:
        List of SearchResult models
    """
    searcher = HybridSearcher(config)
    return await searcher.search(query, run_id, top_k)
