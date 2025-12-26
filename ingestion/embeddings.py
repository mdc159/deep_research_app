"""
Embedding generation with optional contextual enhancement.

This module provides:
- Batch embedding generation
- Contextual embedding (LLM-enhanced chunks for better retrieval)
- Multiple provider support (OpenAI, etc.)
"""

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import openai

from schemas.config import IngestionConfig, get_settings
from schemas.models import Chunk

logger = logging.getLogger(__name__)


class EmbeddingClient:
    """
    Unified embedding client with batching and retry logic.

    Supports:
    - OpenAI embeddings (text-embedding-3-small, etc.)
    - Batch processing for efficiency
    - Exponential backoff on rate limits
    """

    def __init__(
        self,
        model: str = "text-embedding-3-small",
        api_key: str | None = None,
    ):
        """
        Initialize the embedding client.

        Args:
            model: Embedding model name
            api_key: OpenAI API key (uses env var if not provided)
        """
        self.model = model
        settings = get_settings()
        self.api_key = api_key or settings.openai_api_key

        if self.api_key:
            openai.api_key = self.api_key

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """
        Create embeddings for multiple texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        max_retries = 3
        retry_delay = 1.0

        for retry in range(max_retries):
            try:
                response = openai.embeddings.create(
                    model=self.model,
                    input=texts,
                )
                return [item.embedding for item in response.data]

            except openai.RateLimitError as e:
                if retry < max_retries - 1:
                    logger.warning(
                        f"Rate limited (attempt {retry + 1}/{max_retries}), "
                        f"retrying in {retry_delay}s..."
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    raise

            except Exception as e:
                if retry < max_retries - 1:
                    logger.warning(
                        f"Embedding error (attempt {retry + 1}/{max_retries}): {e}"
                    )
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    logger.error(f"Failed to create embeddings after {max_retries} attempts: {e}")
                    # Return zero embeddings as fallback
                    return self._fallback_embeddings(texts)

        return self._fallback_embeddings(texts)

    async def embed_single(self, text: str) -> list[float]:
        """
        Create embedding for a single text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        embeddings = await self.embed([text])
        return embeddings[0] if embeddings else [0.0] * 1536

    def _fallback_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generate zero embeddings as fallback."""
        logger.warning(f"Using fallback zero embeddings for {len(texts)} texts")
        return [[0.0] * 1536 for _ in texts]


class ContextualEmbedder:
    """
    Contextual embedding generator that enhances chunks with document context.

    This improves retrieval by prepending a brief context summary to each chunk
    before embedding, following the "Contextual Embeddings" pattern.

    Example transformation:
    - Before: "The revenue grew by 5%"
    - After: "In Q3 2024, Company X's revenue grew by 5%, as reported in their
             quarterly earnings... [original chunk]"
    """

    def __init__(self, config: IngestionConfig | None = None):
        """
        Initialize the contextual embedder.

        Args:
            config: Ingestion configuration
        """
        self.config = config or IngestionConfig()
        self.embedding_client = EmbeddingClient(model=self.config.embedding_model)
        settings = get_settings()
        self.context_model = settings.contextualizer_model or "gpt-4o-mini"

    async def embed_chunks(
        self,
        chunks: list[Chunk],
        full_document: str,
        batch_size: int = 10,
    ) -> list[Chunk]:
        """
        Generate embeddings for chunks with optional contextual enhancement.

        Args:
            chunks: List of chunks to embed
            full_document: Full document text for context generation
            batch_size: Batch size for parallel processing

        Returns:
            Chunks with embeddings populated
        """
        if not chunks:
            return chunks

        if self.config.use_contextual_embeddings:
            # Generate contextual prefixes
            chunks = await self._add_contextual_prefixes(
                chunks, full_document, batch_size
            )

        # Generate embeddings in batches
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]

            # Use full content (with contextual prefix if available)
            texts = [chunk.full_content for chunk in batch]

            embeddings = await self.embedding_client.embed(texts)

            for chunk, embedding in zip(batch, embeddings):
                chunk.embedding = embedding

            logger.debug(f"Embedded batch {i // batch_size + 1}")

        logger.info(f"Generated embeddings for {len(chunks)} chunks")
        return chunks

    async def _add_contextual_prefixes(
        self,
        chunks: list[Chunk],
        full_document: str,
        batch_size: int = 10,
    ) -> list[Chunk]:
        """
        Add contextual prefixes to chunks using LLM.

        Args:
            chunks: Chunks to enhance
            full_document: Full document for context
            batch_size: Batch size for parallel processing

        Returns:
            Chunks with contextual_prefix populated
        """
        logger.info(f"Generating contextual prefixes for {len(chunks)} chunks...")

        # Truncate document for context (avoid token limits)
        doc_context = full_document[:25000]

        # Process in parallel batches
        with ThreadPoolExecutor(max_workers=batch_size) as executor:
            loop = asyncio.get_event_loop()

            async def process_chunk(chunk: Chunk) -> Chunk:
                try:
                    prefix = await self._generate_context(doc_context, chunk.content)
                    chunk.contextual_prefix = prefix
                except Exception as e:
                    logger.warning(f"Failed to generate context for chunk {chunk.chunk_index}: {e}")
                return chunk

            tasks = [process_chunk(chunk) for chunk in chunks]
            chunks = await asyncio.gather(*tasks)

        context_count = sum(1 for c in chunks if c.contextual_prefix)
        logger.info(f"Generated {context_count}/{len(chunks)} contextual prefixes")

        return list(chunks)

    async def _generate_context(
        self,
        document: str,
        chunk: str,
    ) -> str | None:
        """
        Generate contextual prefix for a chunk.

        Args:
            document: Document context
            chunk: Chunk content

        Returns:
            Contextual prefix or None if generation fails
        """
        prompt = f"""<document>
{document}
</document>

Here is the chunk we want to situate within the whole document:
<chunk>
{chunk}
</chunk>

Please give a short succinct context (1-2 sentences) to situate this chunk within the overall document for the purposes of improving search retrieval of the chunk. Answer only with the succinct context and nothing else."""

        try:
            response = openai.chat.completions.create(
                model=self.context_model.split(":")[-1] if ":" in self.context_model else self.context_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that provides concise contextual information.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=200,
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.warning(f"Context generation failed: {e}")
            return None


class SimpleEmbedder:
    """
    Simple embedder without contextual enhancement.

    Use this for faster processing when contextual embeddings are not needed.
    """

    def __init__(self, config: IngestionConfig | None = None):
        """
        Initialize the simple embedder.

        Args:
            config: Ingestion configuration
        """
        self.config = config or IngestionConfig()
        self.embedding_client = EmbeddingClient(model=self.config.embedding_model)

    async def embed_chunks(
        self,
        chunks: list[Chunk],
        full_document: str | None = None,  # Ignored
        batch_size: int = 20,
    ) -> list[Chunk]:
        """
        Generate embeddings for chunks without contextual enhancement.

        Args:
            chunks: List of chunks to embed
            full_document: Ignored (for API compatibility)
            batch_size: Batch size for embedding

        Returns:
            Chunks with embeddings populated
        """
        if not chunks:
            return chunks

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            texts = [chunk.content for chunk in batch]

            embeddings = await self.embedding_client.embed(texts)

            for chunk, embedding in zip(batch, embeddings):
                chunk.embedding = embedding

        logger.info(f"Generated embeddings for {len(chunks)} chunks (simple mode)")
        return chunks


# Factory function
def get_embedder(config: IngestionConfig | None = None) -> ContextualEmbedder | SimpleEmbedder:
    """
    Get the appropriate embedder based on configuration.

    Args:
        config: Ingestion configuration

    Returns:
        ContextualEmbedder or SimpleEmbedder instance
    """
    config = config or IngestionConfig()

    if config.use_contextual_embeddings:
        return ContextualEmbedder(config)
    else:
        return SimpleEmbedder(config)
