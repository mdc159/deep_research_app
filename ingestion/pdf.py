"""
PDF ingestion using Docling for structure-aware extraction.

This module provides PDF extraction with:
- Structure preservation (headings, sections, tables)
- Fallback strategies for problematic PDFs
- Metadata extraction (page numbers, heading hierarchy)
"""

import hashlib
import logging
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from docling.document_converter import DocumentConverter
from docling_core.types.doc import DoclingDocument

from schemas.config import IngestionConfig
from schemas.models import Chunk, Source

logger = logging.getLogger(__name__)


class PDFExtractor:
    """
    PDF extractor using Docling for structure-aware extraction.

    Docling preserves document structure including:
    - Heading hierarchy
    - Section boundaries
    - Table structure
    - Page information
    """

    def __init__(self, config: IngestionConfig | None = None):
        """
        Initialize the PDF extractor.

        Args:
            config: Ingestion configuration (optional)
        """
        self.config = config or IngestionConfig()
        self._converter: DocumentConverter | None = None

    @property
    def converter(self) -> DocumentConverter:
        """Lazy initialization of the document converter."""
        if self._converter is None:
            logger.info("Initializing Docling DocumentConverter...")
            self._converter = DocumentConverter()
        return self._converter

    async def extract(
        self,
        file_path: str | Path,
        run_id: UUID,
        title: str | None = None,
    ) -> tuple[Source, DoclingDocument, str]:
        """
        Extract content from a PDF file.

        Args:
            file_path: Path to the PDF file
            run_id: ID of the research run
            title: Optional title (extracted from PDF if not provided)

        Returns:
            Tuple of (Source model, DoclingDocument, markdown content)

        Raises:
            FileNotFoundError: If the PDF file doesn't exist
            ValueError: If extraction fails
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"PDF file not found: {file_path}")

        if not file_path.suffix.lower() == ".pdf":
            raise ValueError(f"Expected PDF file, got: {file_path.suffix}")

        logger.info(f"Extracting PDF: {file_path.name}")

        try:
            # Convert PDF with Docling
            result = self.converter.convert(str(file_path))
            docling_doc = result.document

            # Export to markdown for text processing
            markdown = docling_doc.export_to_markdown()

            # Extract title from document or filename
            extracted_title = title or self._extract_title(docling_doc, file_path)

            # Calculate content hash
            content_hash = self._calculate_hash(markdown)

            # Create Source model
            source = Source(
                id=uuid4(),
                run_id=run_id,
                type="pdf",
                title=extracted_title,
                uri=str(file_path.absolute()),
                content_hash=content_hash,
                metadata={
                    "filename": file_path.name,
                    "file_size": file_path.stat().st_size,
                    "page_count": self._get_page_count(docling_doc),
                    "extraction_method": "docling",
                },
            )

            logger.info(
                f"Extracted PDF: {extracted_title} "
                f"({source.metadata.get('page_count', 'unknown')} pages, "
                f"{len(markdown)} chars)"
            )

            return source, docling_doc, markdown

        except Exception as e:
            logger.error(f"Failed to extract PDF {file_path}: {e}")
            # Try fallback extraction
            return await self._fallback_extract(file_path, run_id, title)

    async def _fallback_extract(
        self,
        file_path: Path,
        run_id: UUID,
        title: str | None = None,
    ) -> tuple[Source, None, str]:
        """
        Fallback extraction using PyPDF2 when Docling fails.

        Args:
            file_path: Path to the PDF file
            run_id: ID of the research run
            title: Optional title

        Returns:
            Tuple of (Source model, None, markdown content)
        """
        logger.warning(f"Using fallback extraction for: {file_path.name}")

        try:
            import pypdf

            reader = pypdf.PdfReader(str(file_path))
            pages_text = []

            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text:
                    pages_text.append(f"## Page {i + 1}\n\n{text}")

            markdown = "\n\n".join(pages_text)
            extracted_title = title or file_path.stem
            content_hash = self._calculate_hash(markdown)

            source = Source(
                id=uuid4(),
                run_id=run_id,
                type="pdf",
                title=extracted_title,
                uri=str(file_path.absolute()),
                content_hash=content_hash,
                metadata={
                    "filename": file_path.name,
                    "file_size": file_path.stat().st_size,
                    "page_count": len(reader.pages),
                    "extraction_method": "pypdf_fallback",
                },
            )

            return source, None, markdown

        except Exception as e:
            logger.error(f"Fallback extraction also failed: {e}")
            raise ValueError(f"Could not extract PDF content: {e}")

    def _extract_title(self, doc: DoclingDocument, file_path: Path) -> str:
        """Extract title from document metadata or filename."""
        # Try to get title from document metadata
        if hasattr(doc, "metadata") and doc.metadata:
            if hasattr(doc.metadata, "title") and doc.metadata.title:
                return doc.metadata.title

        # Fall back to filename without extension
        return file_path.stem.replace("_", " ").replace("-", " ").title()

    def _get_page_count(self, doc: DoclingDocument) -> int | None:
        """Get page count from DoclingDocument if available."""
        try:
            if hasattr(doc, "pages"):
                return len(doc.pages)
        except Exception:
            pass
        return None

    def _calculate_hash(self, content: str) -> str:
        """Calculate SHA-256 hash of content."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()


class PDFIngestionPipeline:
    """
    Complete PDF ingestion pipeline: extract -> chunk -> embed -> store.
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
        self.extractor = PDFExtractor(self.config)
        self._chunker = chunker
        self._embedder = embedder
        self._storage = storage

    async def ingest(
        self,
        file_path: str | Path,
        run_id: UUID,
        title: str | None = None,
        store: bool = True,
    ) -> tuple[Source, list[Chunk]]:
        """
        Ingest a PDF file: extract, chunk, embed, and optionally store.

        Args:
            file_path: Path to the PDF file
            run_id: ID of the research run
            title: Optional title override
            store: Whether to store in database

        Returns:
            Tuple of (Source model, list of Chunk models)
        """
        # Import here to avoid circular imports
        from ingestion.chunker import get_chunker
        from ingestion.embeddings import get_embedder

        # Extract PDF
        source, docling_doc, markdown = await self.extractor.extract(
            file_path, run_id, title
        )

        # Get chunker
        chunker = self._chunker or get_chunker(self.config)

        # Chunk the document
        chunks = await chunker.chunk_document(
            content=markdown,
            source=source,
            docling_doc=docling_doc,
        )

        # Generate embeddings
        if self.config.use_contextual_embeddings:
            embedder = self._embedder or get_embedder(self.config)
            chunks = await embedder.embed_chunks(chunks, markdown)

        # Store if requested
        if store and self._storage:
            await self._storage.store_source(source)
            await self._storage.store_chunks(chunks)

        logger.info(f"Ingested PDF: {source.title} -> {len(chunks)} chunks")

        return source, chunks


async def ingest_pdf(
    file_path: str | Path,
    run_id: UUID,
    config: IngestionConfig | None = None,
    title: str | None = None,
) -> tuple[Source, list[Chunk]]:
    """
    Convenience function to ingest a PDF file.

    Args:
        file_path: Path to the PDF file
        run_id: ID of the research run
        config: Ingestion configuration (optional)
        title: Optional title override

    Returns:
        Tuple of (Source model, list of Chunk models)
    """
    pipeline = PDFIngestionPipeline(config=config)
    return await pipeline.ingest(file_path, run_id, title, store=False)
