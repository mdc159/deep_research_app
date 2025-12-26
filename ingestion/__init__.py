"""
Document ingestion pipeline.

This package handles PDF and URL ingestion, chunking, and embedding generation.

Modules:
- pdf: Docling-based PDF extraction
- url: crawl4ai-based URL fetching
- chunker: Unified chunking with DoclingHybridChunker
- embeddings: Contextual embedding generation
"""

from ingestion.chunker import DoclingHybridChunker, get_chunker
from ingestion.embeddings import (
    ContextualEmbedder,
    EmbeddingClient,
    SimpleEmbedder,
    get_embedder,
)
from ingestion.pdf import PDFExtractor, PDFIngestionPipeline, ingest_pdf
from ingestion.url import URLFetcher, URLIngestionPipeline, ingest_url, ingest_urls

__version__ = "0.1.0"

__all__ = [
    # PDF
    "PDFExtractor",
    "PDFIngestionPipeline",
    "ingest_pdf",
    # URL
    "URLFetcher",
    "URLIngestionPipeline",
    "ingest_url",
    "ingest_urls",
    # Chunking
    "DoclingHybridChunker",
    "get_chunker",
    # Embeddings
    "EmbeddingClient",
    "ContextualEmbedder",
    "SimpleEmbedder",
    "get_embedder",
]
