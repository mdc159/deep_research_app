"""
Retrieval tools for the research agent.

These tools allow the agent to search ingested evidence.
"""

import logging
from typing import Annotated
from uuid import UUID

from langchain_core.tools import tool

from retrieval.hybrid_search import HybridSearcher
from retrieval.reranker import RetrievalPipeline
from schemas.config import RetrievalConfig
from schemas.models import SearchResult

logger = logging.getLogger(__name__)

# Global state for current run (set by middleware)
_current_run_id: UUID | None = None
_current_config: RetrievalConfig | None = None


def set_retrieval_context(run_id: UUID, config: RetrievalConfig | None = None) -> None:
    """Set the current retrieval context for tools."""
    global _current_run_id, _current_config
    _current_run_id = run_id
    _current_config = config


def get_retrieval_context() -> tuple[UUID | None, RetrievalConfig | None]:
    """Get the current retrieval context."""
    return _current_run_id, _current_config


def format_search_results(results: list[SearchResult], include_content: bool = True) -> str:
    """Format search results for agent consumption."""
    if not results:
        return "No results found."

    lines = [f"Found {len(results)} results:\n"]

    for i, result in enumerate(results, 1):
        lines.append(f"--- Result {i} (score: {result.score:.4f}) ---")
        lines.append(f"Chunk ID: {result.chunk_id}")
        lines.append(f"Source: {result.source_title}")

        if result.page_start:
            lines.append(f"Location: {result.location_str}")

        if result.section_hint:
            lines.append(f"Section: {result.section_hint}")

        if include_content:
            content = result.content
            if len(content) > 500:
                content = content[:500] + "..."
            lines.append(f"Content:\n{content}")

        lines.append("")

    return "\n".join(lines)


@tool
async def hybrid_search_tool(
    query: Annotated[str, "Search query to find relevant evidence"],
    top_k: Annotated[int, "Number of results to return"] = 10,
) -> str:
    """
    Search ingested evidence using hybrid search (semantic + keyword).

    This tool combines:
    - Vector similarity search for semantic matching
    - Keyword search for exact term matching
    - RRF (Reciprocal Rank Fusion) to merge results

    Use this for finding evidence to support research claims.

    Args:
        query: Search query (can be a question or key terms)
        top_k: Number of results to return (default: 10)

    Returns:
        Formatted search results with chunk IDs for citation
    """
    run_id, config = get_retrieval_context()

    if not run_id:
        return "Error: No active run. Please create a run first."

    try:
        searcher = HybridSearcher(config)
        results = await searcher.search(query, run_id, top_k)

        return format_search_results(results)

    except Exception as e:
        logger.exception(f"Hybrid search failed: {e}")
        return f"Error performing search: {str(e)}"


@tool
async def semantic_search_tool(
    query: Annotated[str, "Search query for semantic matching"],
    top_k: Annotated[int, "Number of results to return"] = 10,
) -> str:
    """
    Search evidence using semantic similarity only.

    Use this when you need conceptual/meaning-based matching,
    especially for paraphrased content or related concepts.

    Args:
        query: Natural language query
        top_k: Number of results (default: 10)

    Returns:
        Formatted search results
    """
    run_id, config = get_retrieval_context()

    if not run_id:
        return "Error: No active run. Please create a run first."

    try:
        # Create config for vector-only search
        vector_config = RetrievalConfig(
            **(config.model_dump() if config else {}),
            search_type="vector",
        )

        searcher = HybridSearcher(vector_config)
        results = await searcher.search(query, run_id, top_k)

        return format_search_results(results)

    except Exception as e:
        logger.exception(f"Semantic search failed: {e}")
        return f"Error performing search: {str(e)}"


@tool
async def keyword_search_tool(
    query: Annotated[str, "Keywords to search for"],
    top_k: Annotated[int, "Number of results to return"] = 10,
) -> str:
    """
    Search evidence using keyword matching only.

    Use this when you need exact term matching,
    especially for specific names, numbers, or technical terms.

    Args:
        query: Keywords to search (use specific terms)
        top_k: Number of results (default: 10)

    Returns:
        Formatted search results
    """
    run_id, config = get_retrieval_context()

    if not run_id:
        return "Error: No active run. Please create a run first."

    try:
        # Create config for keyword-only search
        keyword_config = RetrievalConfig(
            **(config.model_dump() if config else {}),
            search_type="keyword",
        )

        searcher = HybridSearcher(keyword_config)
        results = await searcher.search(query, run_id, top_k)

        return format_search_results(results)

    except Exception as e:
        logger.exception(f"Keyword search failed: {e}")
        return f"Error performing search: {str(e)}"


@tool
async def reranked_search_tool(
    query: Annotated[str, "Search query"],
    initial_k: Annotated[int, "Initial results before reranking"] = 50,
    final_k: Annotated[int, "Final results after reranking"] = 10,
) -> str:
    """
    Search with CrossEncoder reranking for highest precision.

    This tool:
    1. Retrieves initial_k candidates via hybrid search
    2. Reranks using CrossEncoder for better relevance
    3. Returns final_k most relevant results

    Use this for critical evidence where precision matters most.

    Args:
        query: Search query
        initial_k: Candidates for reranking (default: 50)
        final_k: Final results (default: 10)

    Returns:
        Formatted search results with high precision
    """
    run_id, config = get_retrieval_context()

    if not run_id:
        return "Error: No active run. Please create a run first."

    try:
        rerank_config = RetrievalConfig(
            **(config.model_dump() if config else {}),
            use_reranking=True,
            initial_top_k=initial_k,
            final_top_k=final_k,
        )

        pipeline = RetrievalPipeline(rerank_config)
        results = await pipeline.retrieve(query, run_id, final_k)

        return format_search_results(results)

    except Exception as e:
        logger.exception(f"Reranked search failed: {e}")
        return f"Error performing search: {str(e)}"


@tool
async def get_chunk_tool(
    chunk_id: Annotated[str, "UUID of the chunk to retrieve"],
) -> str:
    """
    Get the full content of a specific chunk by ID.

    Use this to retrieve complete evidence for a known chunk,
    especially when you need the full context for citation.

    Args:
        chunk_id: UUID of the chunk

    Returns:
        Full chunk content with metadata
    """
    run_id, _ = get_retrieval_context()

    if not run_id:
        return "Error: No active run. Please create a run first."

    try:
        from storage.supabase import get_supabase_client

        client = get_supabase_client()
        chunk = await client.get_chunk(UUID(chunk_id))

        if not chunk:
            return f"Error: Chunk not found: {chunk_id}"

        lines = [
            f"Chunk: {chunk.id}",
            f"Source ID: {chunk.source_id}",
        ]

        if chunk.page_start:
            if chunk.page_end and chunk.page_end != chunk.page_start:
                lines.append(f"Pages: {chunk.page_start}-{chunk.page_end}")
            else:
                lines.append(f"Page: {chunk.page_start}")

        if chunk.section_hint:
            lines.append(f"Section: {chunk.section_hint}")

        if chunk.heading_hierarchy:
            lines.append(f"Headings: {' > '.join(chunk.heading_hierarchy)}")

        lines.append(f"Tokens: {chunk.token_count}")
        lines.append(f"\nContent:\n{chunk.content}")

        if chunk.contextual_prefix:
            lines.append(f"\nContextual Summary:\n{chunk.contextual_prefix}")

        return "\n".join(lines)

    except Exception as e:
        logger.exception(f"Get chunk failed: {e}")
        return f"Error getting chunk: {str(e)}"


@tool
async def multi_query_search_tool(
    queries: Annotated[list[str], "List of search queries"],
    top_k_per_query: Annotated[int, "Results per query"] = 5,
) -> str:
    """
    Search with multiple queries and combine results.

    Use this for comprehensive evidence gathering across
    multiple angles or formulations of a topic.

    Args:
        queries: List of search queries
        top_k_per_query: Results per query (default: 5)

    Returns:
        Combined unique results from all queries
    """
    run_id, config = get_retrieval_context()

    if not run_id:
        return "Error: No active run. Please create a run first."

    if not queries:
        return "Error: No queries provided"

    try:
        searcher = HybridSearcher(config)
        all_results: dict[UUID, SearchResult] = {}

        for query in queries:
            results = await searcher.search(query, run_id, top_k_per_query)
            for result in results:
                if result.chunk_id not in all_results:
                    all_results[result.chunk_id] = result

        # Sort by score
        sorted_results = sorted(
            all_results.values(),
            key=lambda x: x.score,
            reverse=True,
        )

        lines = [
            f"Multi-query search across {len(queries)} queries:",
            f"Queries: {', '.join(queries[:3])}{'...' if len(queries) > 3 else ''}",
            f"Unique results: {len(sorted_results)}",
            "",
        ]

        return "\n".join(lines) + format_search_results(sorted_results)

    except Exception as e:
        logger.exception(f"Multi-query search failed: {e}")
        return f"Error performing search: {str(e)}"
