"""
Ingestion tools for the research agent.

These tools allow the agent to ingest PDFs and URLs for evidence gathering.
"""

import logging
from pathlib import Path
from typing import Annotated
from uuid import UUID

from langchain_core.tools import tool

from ingestion.pdf import ingest_pdf
from ingestion.url import ingest_url, ingest_urls
from schemas.config import IngestionConfig
from schemas.models import Chunk, Source
from storage.supabase import get_supabase_client

logger = logging.getLogger(__name__)

# Global state for current run (set by middleware)
_current_run_id: UUID | None = None
_current_config: IngestionConfig | None = None


def set_run_context(run_id: UUID, config: IngestionConfig | None = None) -> None:
    """Set the current run context for tools."""
    global _current_run_id, _current_config
    _current_run_id = run_id
    _current_config = config


def get_run_context() -> tuple[UUID | None, IngestionConfig | None]:
    """Get the current run context."""
    return _current_run_id, _current_config


@tool
async def pdf_ingest_tool(
    file_path: Annotated[str, "Path to the PDF file to ingest"],
    title: Annotated[str | None, "Optional title override for the document"] = None,
) -> str:
    """
    Ingest a PDF document for evidence extraction.

    This tool:
    1. Extracts text and structure from the PDF using Docling
    2. Chunks the content with structure preservation
    3. Generates embeddings (with optional contextual enhancement)
    4. Stores chunks in the vector database for search

    Args:
        file_path: Path to the PDF file
        title: Optional title (extracted from PDF if not provided)

    Returns:
        Summary of ingestion results including chunk count
    """
    run_id, config = get_run_context()

    if not run_id:
        return "Error: No active run. Please create a run first."

    try:
        file_path_obj = Path(file_path)

        if not file_path_obj.exists():
            return f"Error: File not found: {file_path}"

        if not file_path_obj.suffix.lower() == ".pdf":
            return f"Error: Expected PDF file, got: {file_path_obj.suffix}"

        # Ingest the PDF
        source, chunks = await ingest_pdf(
            file_path=file_path_obj,
            run_id=run_id,
            config=config,
            title=title,
        )

        # Store in database
        client = get_supabase_client()
        await client.store_source(source)
        await client.store_chunks(chunks)

        return (
            f"Successfully ingested PDF: {source.title}\n"
            f"- Source ID: {source.id}\n"
            f"- Chunks created: {len(chunks)}\n"
            f"- Total tokens: {sum(c.token_count for c in chunks)}\n"
            f"- Pages: {source.metadata.get('page_count', 'unknown')}"
        )

    except Exception as e:
        logger.exception(f"PDF ingestion failed: {e}")
        return f"Error ingesting PDF: {str(e)}"


@tool
async def url_fetch_tool(
    url: Annotated[str, "URL to fetch and ingest"],
    title: Annotated[str | None, "Optional title override"] = None,
) -> str:
    """
    Fetch and ingest content from a URL.

    This tool:
    1. Fetches the web page using crawl4ai
    2. Converts content to markdown
    3. Chunks with smart markdown chunking
    4. Generates embeddings for search

    Args:
        url: URL to fetch
        title: Optional title override

    Returns:
        Summary of ingestion results
    """
    run_id, config = get_run_context()

    if not run_id:
        return "Error: No active run. Please create a run first."

    try:
        # Validate URL format
        if not url.startswith(("http://", "https://")):
            return f"Error: Invalid URL format. URL must start with http:// or https://"

        # Ingest the URL
        source, chunks = await ingest_url(
            url=url,
            run_id=run_id,
            config=config,
            title=title,
        )

        # Store in database
        client = get_supabase_client()
        await client.store_source(source)
        await client.store_chunks(chunks)

        return (
            f"Successfully fetched URL: {source.title}\n"
            f"- Source ID: {source.id}\n"
            f"- Domain: {source.metadata.get('domain', 'unknown')}\n"
            f"- Chunks created: {len(chunks)}\n"
            f"- Total tokens: {sum(c.token_count for c in chunks)}"
        )

    except Exception as e:
        logger.exception(f"URL fetch failed: {e}")
        return f"Error fetching URL: {str(e)}"


@tool
async def batch_url_fetch_tool(
    urls: Annotated[list[str], "List of URLs to fetch and ingest"],
) -> str:
    """
    Fetch and ingest content from multiple URLs.

    This tool processes multiple URLs efficiently using concurrent fetching.

    Args:
        urls: List of URLs to fetch

    Returns:
        Summary of ingestion results for all URLs
    """
    run_id, config = get_run_context()

    if not run_id:
        return "Error: No active run. Please create a run first."

    if not urls:
        return "Error: No URLs provided"

    try:
        # Validate URLs
        valid_urls = []
        invalid_urls = []
        for url in urls:
            if url.startswith(("http://", "https://")):
                valid_urls.append(url)
            else:
                invalid_urls.append(url)

        if invalid_urls:
            logger.warning(f"Skipping invalid URLs: {invalid_urls}")

        if not valid_urls:
            return "Error: No valid URLs provided"

        # Ingest URLs
        results = await ingest_urls(
            urls=valid_urls,
            run_id=run_id,
            config=config,
        )

        # Store in database
        client = get_supabase_client()
        total_chunks = 0

        for source, chunks in results:
            await client.store_source(source)
            await client.store_chunks(chunks)
            total_chunks += len(chunks)

        summary_lines = [
            f"Batch URL ingestion complete:",
            f"- URLs processed: {len(results)}/{len(valid_urls)}",
            f"- Total chunks: {total_chunks}",
        ]

        if invalid_urls:
            summary_lines.append(f"- Invalid URLs skipped: {len(invalid_urls)}")

        for source, chunks in results:
            summary_lines.append(f"  - {source.title}: {len(chunks)} chunks")

        return "\n".join(summary_lines)

    except Exception as e:
        logger.exception(f"Batch URL fetch failed: {e}")
        return f"Error in batch URL fetch: {str(e)}"


@tool
async def list_sources_tool() -> str:
    """
    List all ingested sources for the current run.

    Returns:
        Formatted list of sources with details
    """
    run_id, _ = get_run_context()

    if not run_id:
        return "Error: No active run. Please create a run first."

    try:
        client = get_supabase_client()
        sources = await client.get_sources(run_id)

        if not sources:
            return "No sources ingested yet."

        lines = [f"Ingested sources ({len(sources)} total):"]

        for source in sources:
            lines.append(
                f"- [{source.type.upper()}] {source.title}\n"
                f"  ID: {source.id}\n"
                f"  URI: {source.uri[:80]}{'...' if len(source.uri) > 80 else ''}"
            )

        return "\n".join(lines)

    except Exception as e:
        logger.exception(f"Failed to list sources: {e}")
        return f"Error listing sources: {str(e)}"
