"""
Agent tools for the research pipeline.

Tools:
- ingestion: PDF and URL ingestion tools
- retrieval: Hybrid search tools
- citation: Citation formatting tools
"""

from research_agent.tools.citation import (
    format_citation_tool,
    get_citation_for_claim_tool,
    label_assumption_tool,
    resolve_citations_tool,
    validate_citations_tool,
)
from research_agent.tools.ingestion import (
    batch_url_fetch_tool,
    list_sources_tool,
    pdf_ingest_tool,
    url_fetch_tool,
)
from research_agent.tools.retrieval import (
    get_chunk_tool,
    hybrid_search_tool,
    keyword_search_tool,
    multi_query_search_tool,
    reranked_search_tool,
    semantic_search_tool,
)

# All available tools for the agent
ALL_TOOLS = [
    # Ingestion
    pdf_ingest_tool,
    url_fetch_tool,
    batch_url_fetch_tool,
    list_sources_tool,
    # Retrieval
    hybrid_search_tool,
    semantic_search_tool,
    keyword_search_tool,
    reranked_search_tool,
    get_chunk_tool,
    multi_query_search_tool,
    # Citation
    format_citation_tool,
    resolve_citations_tool,
    validate_citations_tool,
    label_assumption_tool,
    get_citation_for_claim_tool,
]

__all__ = [
    # Ingestion tools
    "pdf_ingest_tool",
    "url_fetch_tool",
    "batch_url_fetch_tool",
    "list_sources_tool",
    # Retrieval tools
    "hybrid_search_tool",
    "semantic_search_tool",
    "keyword_search_tool",
    "reranked_search_tool",
    "get_chunk_tool",
    "multi_query_search_tool",
    # Citation tools
    "format_citation_tool",
    "resolve_citations_tool",
    "validate_citations_tool",
    "label_assumption_tool",
    "get_citation_for_claim_tool",
    # All tools list
    "ALL_TOOLS",
]
