"""
URL ingestion using crawl4ai for web content fetching.

This module provides web content extraction with:
- Async web crawling
- Markdown conversion
- HTML snapshot storage
- Smart content detection
"""

import hashlib
import logging
from datetime import datetime
from typing import Any
from urllib.parse import urlparse
from uuid import UUID, uuid4

from crawl4ai import AsyncWebCrawler

from schemas.config import IngestionConfig
from schemas.models import Chunk, Source

logger = logging.getLogger(__name__)


class URLFetcher:
    """
    URL fetcher using crawl4ai for web content extraction.

    Features:
    - Async web crawling
    - Automatic markdown conversion
    - JavaScript rendering support
    - HTML snapshot capture
    """

    def __init__(self, config: IngestionConfig | None = None):
        """
        Initialize the URL fetcher.

        Args:
            config: Ingestion configuration (optional)
        """
        self.config = config or IngestionConfig()

    async def fetch(
        self,
        url: str,
        run_id: UUID,
        title: str | None = None,
    ) -> tuple[Source, str, str | None]:
        """
        Fetch content from a URL.

        Args:
            url: URL to fetch
            run_id: ID of the research run
            title: Optional title override

        Returns:
            Tuple of (Source model, markdown content, HTML snapshot or None)

        Raises:
            ValueError: If URL is invalid or fetch fails
        """
        # Validate URL
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(f"Invalid URL: {url}")

        logger.info(f"Fetching URL: {url}")

        try:
            async with AsyncWebCrawler() as crawler:
                result = await crawler.arun(url=url)

                if not result.success:
                    raise ValueError(f"Failed to fetch URL: {result.error_message}")

                markdown = result.markdown or ""
                html_snapshot = result.html if self.config.store_html_snapshots else None

                # Extract or generate title
                extracted_title = title or result.title or self._title_from_url(url)

                # Calculate content hash
                content_hash = self._calculate_hash(markdown)

                # Create Source model
                source = Source(
                    id=uuid4(),
                    run_id=run_id,
                    type="url",
                    title=extracted_title,
                    uri=url,
                    content_hash=content_hash,
                    metadata={
                        "domain": parsed.netloc,
                        "path": parsed.path,
                        "captured_at": datetime.utcnow().isoformat(),
                        "content_length": len(markdown),
                        "has_html_snapshot": html_snapshot is not None,
                    },
                )

                logger.info(
                    f"Fetched URL: {extracted_title} "
                    f"({len(markdown)} chars from {parsed.netloc})"
                )

                return source, markdown, html_snapshot

        except Exception as e:
            logger.error(f"Failed to fetch URL {url}: {e}")
            raise ValueError(f"Could not fetch URL content: {e}")

    async def fetch_multiple(
        self,
        urls: list[str],
        run_id: UUID,
    ) -> list[tuple[Source, str, str | None]]:
        """
        Fetch content from multiple URLs concurrently.

        Args:
            urls: List of URLs to fetch
            run_id: ID of the research run

        Returns:
            List of (Source, markdown, HTML snapshot) tuples
        """
        import asyncio

        results = []
        errors = []

        # Process URLs concurrently with a semaphore to limit concurrency
        semaphore = asyncio.Semaphore(5)  # Max 5 concurrent fetches

        async def fetch_with_semaphore(url: str) -> tuple | None:
            async with semaphore:
                try:
                    return await self.fetch(url, run_id)
                except Exception as e:
                    errors.append((url, str(e)))
                    return None

        tasks = [fetch_with_semaphore(url) for url in urls]
        fetch_results = await asyncio.gather(*tasks)

        for result in fetch_results:
            if result is not None:
                results.append(result)

        if errors:
            logger.warning(f"Failed to fetch {len(errors)} URLs: {errors}")

        return results

    def _title_from_url(self, url: str) -> str:
        """Extract a readable title from URL."""
        parsed = urlparse(url)
        path = parsed.path.strip("/")

        if path:
            # Use the last path segment as title
            segments = path.split("/")
            title = segments[-1]
            # Clean up the title
            title = title.replace("-", " ").replace("_", " ")
            title = title.rsplit(".", 1)[0]  # Remove extension
            return title.title()

        return parsed.netloc

    def _calculate_hash(self, content: str) -> str:
        """Calculate SHA-256 hash of content."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()


class URLIngestionPipeline:
    """
    Complete URL ingestion pipeline: fetch -> chunk -> embed -> store.
    """

    def __init__(
        self,
        config: IngestionConfig | None = None,
        chunker: Any | None = None,
        embedder: Any | None = None,
        storage: Any | None = None,
    ):
        """
        Initialize the ingestion pipeline.

        Args:
            config: Ingestion configuration
            chunker: Chunker instance (lazy loaded if not provided)
            embedder: Embedder instance (lazy loaded if not provided)
            storage: Storage instance (lazy loaded if not provided)
        """
        self.config = config or IngestionConfig()
        self.fetcher = URLFetcher(self.config)
        self._chunker = chunker
        self._embedder = embedder
        self._storage = storage

    async def ingest(
        self,
        url: str,
        run_id: UUID,
        title: str | None = None,
        store: bool = True,
    ) -> tuple[Source, list[Chunk]]:
        """
        Ingest a URL: fetch, chunk, embed, and optionally store.

        Args:
            url: URL to fetch
            run_id: ID of the research run
            title: Optional title override
            store: Whether to store in database

        Returns:
            Tuple of (Source model, list of Chunk models)
        """
        # Import here to avoid circular imports
        from ingestion.chunker import get_chunker
        from ingestion.embeddings import get_embedder

        # Fetch URL
        source, markdown, html_snapshot = await self.fetcher.fetch(url, run_id, title)

        # Get chunker
        chunker = self._chunker or get_chunker(self.config)

        # Chunk the content
        chunks = await chunker.chunk_markdown(
            content=markdown,
            source=source,
        )

        # Generate embeddings
        if self.config.use_contextual_embeddings:
            embedder = self._embedder or get_embedder(self.config)
            chunks = await embedder.embed_chunks(chunks, markdown)

        # Store if requested
        if store and self._storage:
            await self._storage.store_source(source)
            await self._storage.store_chunks(chunks)
            if html_snapshot:
                await self._storage.store_html_snapshot(source.id, html_snapshot)

        logger.info(f"Ingested URL: {source.title} -> {len(chunks)} chunks")

        return source, chunks

    async def ingest_multiple(
        self,
        urls: list[str],
        run_id: UUID,
        store: bool = True,
    ) -> list[tuple[Source, list[Chunk]]]:
        """
        Ingest multiple URLs.

        Args:
            urls: List of URLs to ingest
            run_id: ID of the research run
            store: Whether to store in database

        Returns:
            List of (Source, chunks) tuples
        """
        results = []

        for url in urls:
            try:
                result = await self.ingest(url, run_id, store=store)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to ingest URL {url}: {e}")

        return results


async def ingest_url(
    url: str,
    run_id: UUID,
    config: IngestionConfig | None = None,
    title: str | None = None,
) -> tuple[Source, list[Chunk]]:
    """
    Convenience function to ingest a URL.

    Args:
        url: URL to fetch
        run_id: ID of the research run
        config: Ingestion configuration (optional)
        title: Optional title override

    Returns:
        Tuple of (Source model, list of Chunk models)
    """
    pipeline = URLIngestionPipeline(config=config)
    return await pipeline.ingest(url, run_id, title, store=False)


async def ingest_urls(
    urls: list[str],
    run_id: UUID,
    config: IngestionConfig | None = None,
) -> list[tuple[Source, list[Chunk]]]:
    """
    Convenience function to ingest multiple URLs.

    Args:
        urls: List of URLs to fetch
        run_id: ID of the research run
        config: Ingestion configuration (optional)

    Returns:
        List of (Source, chunks) tuples
    """
    pipeline = URLIngestionPipeline(config=config)
    return await pipeline.ingest_multiple(urls, run_id, store=False)
