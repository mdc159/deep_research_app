"""
Retrieval pipeline for evidence search.

This package implements hybrid search combining vector similarity
and keyword matching with RRF fusion and optional reranking.

Modules:
- hybrid_search: HybridSearcher with RRF fusion
- reranker: CrossEncoder-based reranking
"""

from retrieval.hybrid_search import HybridSearcher, hybrid_search
from retrieval.reranker import Reranker, RetrievalPipeline, get_reranker, retrieve

__version__ = "0.1.0"

__all__ = [
    # Hybrid Search
    "HybridSearcher",
    "hybrid_search",
    # Reranking
    "Reranker",
    "get_reranker",
    # Pipeline
    "RetrievalPipeline",
    "retrieve",
]
