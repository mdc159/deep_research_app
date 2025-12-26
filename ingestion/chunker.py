"""
Unified chunking for documents and markdown content.

This module provides:
- DoclingHybridChunker for PDFs with structure preservation
- Smart markdown chunking for web content
- Fallback chunking for edge cases
"""

import hashlib
import logging
import re
from typing import Any
from uuid import uuid4

from docling.chunking import HybridChunker
from docling_core.types.doc import DoclingDocument
from transformers import AutoTokenizer

from schemas.config import IngestionConfig
from schemas.models import Chunk, Source

logger = logging.getLogger(__name__)


class DoclingHybridChunker:
    """
    Structure-aware chunker using Docling's HybridChunker.

    Features:
    - Respects document structure (headings, sections, tables)
    - Token-aware chunking (fits embedding model limits)
    - Preserves heading hierarchy for context
    - Merges small adjacent chunks
    """

    def __init__(self, config: IngestionConfig | None = None):
        """
        Initialize the chunker.

        Args:
            config: Ingestion configuration
        """
        self.config = config or IngestionConfig()
        self._tokenizer: Any | None = None
        self._chunker: HybridChunker | None = None

    @property
    def tokenizer(self) -> Any:
        """Lazy initialization of tokenizer."""
        if self._tokenizer is None:
            model_id = "sentence-transformers/all-MiniLM-L6-v2"
            logger.info(f"Initializing tokenizer: {model_id}")
            self._tokenizer = AutoTokenizer.from_pretrained(model_id)
        return self._tokenizer

    @property
    def chunker(self) -> HybridChunker:
        """Lazy initialization of HybridChunker."""
        if self._chunker is None:
            self._chunker = HybridChunker(
                tokenizer=self.tokenizer,
                max_tokens=self.config.chunk_size_tokens,
                merge_peers=True,
            )
            logger.info(
                f"HybridChunker initialized (max_tokens={self.config.chunk_size_tokens})"
            )
        return self._chunker

    async def chunk_document(
        self,
        content: str,
        source: Source,
        docling_doc: DoclingDocument | None = None,
    ) -> list[Chunk]:
        """
        Chunk a document using structure-aware chunking.

        Args:
            content: Document content (markdown)
            source: Source model
            docling_doc: Optional DoclingDocument for structure-aware chunking

        Returns:
            List of Chunk models
        """
        if docling_doc is not None:
            return await self._chunk_with_docling(content, source, docling_doc)
        else:
            # Fall back to markdown chunking
            return await self.chunk_markdown(content, source)

    async def _chunk_with_docling(
        self,
        content: str,
        source: Source,
        docling_doc: DoclingDocument,
    ) -> list[Chunk]:
        """
        Chunk using Docling's HybridChunker for structure preservation.

        Args:
            content: Markdown content
            source: Source model
            docling_doc: DoclingDocument with structure

        Returns:
            List of Chunk models
        """
        try:
            chunk_iter = self.chunker.chunk(dl_doc=docling_doc)
            docling_chunks = list(chunk_iter)

            chunks = []
            for i, dc in enumerate(docling_chunks):
                # Get contextualized text (includes heading hierarchy)
                contextualized = self.chunker.contextualize(chunk=dc)
                token_count = len(self.tokenizer.encode(contextualized))

                # Extract heading hierarchy if available
                heading_hierarchy = self._extract_heading_hierarchy(dc)

                # Extract page info if available
                page_start, page_end = self._extract_page_info(dc)

                chunk = Chunk(
                    id=uuid4(),
                    source_id=source.id,
                    run_id=source.run_id,
                    chunk_index=i,
                    content=contextualized.strip(),
                    page_start=page_start,
                    page_end=page_end,
                    section_hint=heading_hierarchy[-1] if heading_hierarchy else None,
                    heading_hierarchy=heading_hierarchy,
                    content_hash=self._calculate_hash(contextualized),
                    token_count=token_count,
                    chunk_method="docling_hybrid",
                    metadata={
                        "source_title": source.title,
                        "has_context": True,
                    },
                )
                chunks.append(chunk)

            logger.info(f"Created {len(chunks)} chunks using DoclingHybridChunker")
            return chunks

        except Exception as e:
            logger.warning(f"Docling chunking failed: {e}, falling back to markdown chunking")
            return await self.chunk_markdown(content, source)

    async def chunk_markdown(
        self,
        content: str,
        source: Source,
    ) -> list[Chunk]:
        """
        Smart markdown chunking that preserves structure.

        Features:
        - Respects code block integrity
        - Preserves paragraph boundaries
        - Follows heading structure
        - Maintains list continuity

        Args:
            content: Markdown content
            source: Source model

        Returns:
            List of Chunk models
        """
        if not content.strip():
            return []

        chunks = []
        current_chunk = []
        current_tokens = 0
        current_heading = None
        heading_hierarchy: list[str] = []

        lines = content.split("\n")
        i = 0

        while i < len(lines):
            line = lines[i]

            # Check for code block
            if line.strip().startswith("```"):
                code_block, end_idx = self._extract_code_block(lines, i)
                code_tokens = len(self.tokenizer.encode(code_block))

                # If code block is too large, split it
                if code_tokens > self.config.chunk_size_tokens:
                    # Save current chunk first
                    if current_chunk:
                        chunks.append(
                            self._create_chunk(
                                current_chunk,
                                source,
                                len(chunks),
                                heading_hierarchy.copy(),
                            )
                        )
                        current_chunk = []
                        current_tokens = 0

                    # Split large code block
                    code_chunks = self._split_large_content(
                        code_block, self.config.chunk_size_tokens
                    )
                    for cc in code_chunks:
                        chunks.append(
                            self._create_chunk(
                                [cc], source, len(chunks), heading_hierarchy.copy()
                            )
                        )
                else:
                    # Check if code block fits in current chunk
                    if current_tokens + code_tokens > self.config.chunk_size_tokens:
                        if current_chunk:
                            chunks.append(
                                self._create_chunk(
                                    current_chunk,
                                    source,
                                    len(chunks),
                                    heading_hierarchy.copy(),
                                )
                            )
                            current_chunk = []
                            current_tokens = 0

                    current_chunk.append(code_block)
                    current_tokens += code_tokens

                i = end_idx + 1
                continue

            # Check for heading
            heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
            if heading_match:
                level = len(heading_match.group(1))
                heading_text = heading_match.group(2).strip()

                # Update heading hierarchy
                heading_hierarchy = heading_hierarchy[: level - 1]
                heading_hierarchy.append(heading_text)
                current_heading = heading_text

            # Calculate line tokens
            line_tokens = len(self.tokenizer.encode(line))

            # Check if we need to start a new chunk
            if current_tokens + line_tokens > self.config.chunk_size_tokens:
                if current_chunk:
                    chunks.append(
                        self._create_chunk(
                            current_chunk,
                            source,
                            len(chunks),
                            heading_hierarchy.copy(),
                        )
                    )
                    current_chunk = []
                    current_tokens = 0

            current_chunk.append(line)
            current_tokens += line_tokens
            i += 1

        # Don't forget the last chunk
        if current_chunk:
            chunks.append(
                self._create_chunk(
                    current_chunk, source, len(chunks), heading_hierarchy.copy()
                )
            )

        logger.info(f"Created {len(chunks)} chunks using smart markdown chunking")
        return chunks

    def _extract_code_block(
        self, lines: list[str], start_idx: int
    ) -> tuple[str, int]:
        """Extract a complete code block from lines."""
        block_lines = [lines[start_idx]]
        i = start_idx + 1

        while i < len(lines):
            block_lines.append(lines[i])
            if lines[i].strip().startswith("```"):
                break
            i += 1

        return "\n".join(block_lines), i

    def _split_large_content(
        self, content: str, max_tokens: int
    ) -> list[str]:
        """Split large content into smaller chunks."""
        chunks = []
        lines = content.split("\n")
        current_chunk = []
        current_tokens = 0

        for line in lines:
            line_tokens = len(self.tokenizer.encode(line))

            if current_tokens + line_tokens > max_tokens and current_chunk:
                chunks.append("\n".join(current_chunk))
                current_chunk = []
                current_tokens = 0

            current_chunk.append(line)
            current_tokens += line_tokens

        if current_chunk:
            chunks.append("\n".join(current_chunk))

        return chunks

    def _create_chunk(
        self,
        lines: list[str],
        source: Source,
        index: int,
        heading_hierarchy: list[str],
    ) -> Chunk:
        """Create a Chunk model from lines."""
        content = "\n".join(lines).strip()
        token_count = len(self.tokenizer.encode(content))

        return Chunk(
            id=uuid4(),
            source_id=source.id,
            run_id=source.run_id,
            chunk_index=index,
            content=content,
            section_hint=heading_hierarchy[-1] if heading_hierarchy else None,
            heading_hierarchy=heading_hierarchy,
            content_hash=self._calculate_hash(content),
            token_count=token_count,
            chunk_method="smart_markdown",
            metadata={
                "source_title": source.title,
            },
        )

    def _extract_heading_hierarchy(self, dc: Any) -> list[str]:
        """Extract heading hierarchy from Docling chunk."""
        try:
            if hasattr(dc, "meta") and hasattr(dc.meta, "headings"):
                return list(dc.meta.headings)
        except Exception:
            pass
        return []

    def _extract_page_info(self, dc: Any) -> tuple[int | None, int | None]:
        """Extract page information from Docling chunk."""
        try:
            if hasattr(dc, "meta"):
                page_start = getattr(dc.meta, "page", None)
                page_end = getattr(dc.meta, "page_end", page_start)
                return page_start, page_end
        except Exception:
            pass
        return None, None

    def _calculate_hash(self, content: str) -> str:
        """Calculate SHA-256 hash of content."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()


# Singleton instance
_chunker: DoclingHybridChunker | None = None


def get_chunker(config: IngestionConfig | None = None) -> DoclingHybridChunker:
    """Get or create the chunker singleton."""
    global _chunker
    if _chunker is None:
        _chunker = DoclingHybridChunker(config)
    return _chunker
