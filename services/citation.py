"""
Citation service for resolving and formatting citations.

This service provides:
- Placeholder resolution ([cite:chunk_id] -> [1])
- IEEE-style reference generation
- Citation validation and coverage metrics
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from schemas.models import Citation, CitationAnchor, Chunk, Source

logger = logging.getLogger(__name__)


@dataclass
class ResolvedCitation:
    """A resolved citation with metadata."""

    number: int
    chunk_id: UUID
    source_id: UUID
    source: Source | None
    chunk: Chunk | None
    reference_entry: str


@dataclass
class CitationReport:
    """Report on citation coverage and issues."""

    total_sentences: int
    cited_sentences: int
    assumption_labels: int
    numerical_claims: int
    numerical_cited: int
    coverage_percent: float
    target_met: bool
    issues: list[str]


class CitationService:
    """
    Service for citation management.

    Handles:
    - Finding citation placeholders in text
    - Resolving placeholders to numbered references
    - Generating IEEE-style reference lists
    - Calculating coverage metrics
    """

    def __init__(self):
        """Initialize the citation service."""
        self._citation_map: dict[UUID, int] = {}
        self._resolved: list[ResolvedCitation] = []

    def reset(self) -> None:
        """Reset citation state for a new document."""
        self._citation_map = {}
        self._resolved = []

    def find_placeholders(self, content: str) -> list[str]:
        """
        Find all citation placeholders in content.

        Args:
            content: Document content

        Returns:
            List of chunk IDs found (in order of appearance)
        """
        pattern = r'\[cite:([a-f0-9-]+)\]'
        return re.findall(pattern, content)

    def find_unique_placeholders(self, content: str) -> list[str]:
        """
        Find unique citation placeholders preserving first appearance order.

        Args:
            content: Document content

        Returns:
            List of unique chunk IDs in order of first appearance
        """
        placeholders = self.find_placeholders(content)
        return list(dict.fromkeys(placeholders))

    async def resolve(
        self,
        content: str,
        get_chunk: callable,
        get_source: callable,
    ) -> tuple[str, list[ResolvedCitation]]:
        """
        Resolve citation placeholders to numbered references.

        Args:
            content: Document content with [cite:chunk_id] placeholders
            get_chunk: Async function to get chunk by ID
            get_source: Async function to get source by ID

        Returns:
            Tuple of (resolved content, list of resolved citations)
        """
        self.reset()
        unique_chunks = self.find_unique_placeholders(content)

        if not unique_chunks:
            return content, []

        resolved_content = content
        resolved_citations = []

        for i, chunk_id_str in enumerate(unique_chunks, 1):
            chunk_id = UUID(chunk_id_str)
            self._citation_map[chunk_id] = i

            # Get chunk and source
            chunk = await get_chunk(chunk_id)
            source = None
            if chunk:
                source = await get_source(chunk.source_id)

            # Generate reference entry
            ref_entry = self._format_reference(i, source, chunk)

            resolved = ResolvedCitation(
                number=i,
                chunk_id=chunk_id,
                source_id=source.id if source else chunk.source_id if chunk else UUID(int=0),
                source=source,
                chunk=chunk,
                reference_entry=ref_entry,
            )
            resolved_citations.append(resolved)
            self._resolved.append(resolved)

            # Replace placeholders
            resolved_content = resolved_content.replace(
                f"[cite:{chunk_id_str}]",
                f"[{i}]"
            )

        return resolved_content, resolved_citations

    def _format_reference(
        self,
        number: int,
        source: Source | None,
        chunk: Chunk | None,
    ) -> str:
        """
        Format a reference entry in IEEE style.

        Args:
            number: Citation number
            source: Source model (if available)
            chunk: Chunk model (if available)

        Returns:
            Formatted reference string
        """
        if not source:
            return f"[{number}] Source not found"

        if source.type == "url":
            # Web source format
            domain = source.metadata.get("domain", "") if source.metadata else ""
            accessed = source.captured_at.strftime("%Y-%m-%d") if source.captured_at else "unknown"
            return (
                f'[{number}] "{source.title}," {domain}, '
                f'{source.uri}, Accessed: {accessed}.'
            )

        elif source.type == "pdf":
            # PDF source format
            year = source.captured_at.strftime("%Y") if source.captured_at else ""

            # Add page information if available
            page_info = ""
            if chunk:
                if chunk.page_start:
                    if chunk.page_end and chunk.page_end != chunk.page_start:
                        page_info = f", pp. {chunk.page_start}-{chunk.page_end}"
                    else:
                        page_info = f", p. {chunk.page_start}"

            # Try to get author from metadata
            author = ""
            if source.metadata:
                if "author" in source.metadata:
                    author = source.metadata["author"] + ", "
                elif "authors" in source.metadata:
                    authors = source.metadata["authors"]
                    if isinstance(authors, list):
                        if len(authors) > 2:
                            author = f"{authors[0]} et al., "
                        else:
                            author = " and ".join(authors) + ", "

            return f'[{number}] {author}"{source.title}," {year}{page_info}.'

        else:
            # Generic format
            return f'[{number}] "{source.title}," {source.uri}.'

    def generate_reference_list(
        self,
        citations: list[ResolvedCitation] | None = None,
    ) -> str:
        """
        Generate a formatted reference list.

        Args:
            citations: Optional list of resolved citations (uses internal if not provided)

        Returns:
            Formatted reference list as markdown
        """
        citations = citations or self._resolved

        if not citations:
            return "## References\n\nNo citations found."

        lines = ["## References", ""]
        for citation in sorted(citations, key=lambda c: c.number):
            lines.append(citation.reference_entry)
            lines.append("")

        return "\n".join(lines)

    def calculate_coverage(self, content: str) -> CitationReport:
        """
        Calculate citation coverage metrics.

        Args:
            content: Document content (with resolved citations)

        Returns:
            CitationReport with metrics
        """
        # Split into sentences
        sentences = re.split(r'[.!?]\s+', content)
        total = len(sentences)

        cited = 0
        assumptions = 0
        numerical = 0
        numerical_cited = 0
        issues = []

        for i, sentence in enumerate(sentences):
            has_citation = bool(re.search(r'\[\d+\]', sentence))
            has_assumption = bool(re.search(r'\[ASSUMPTION:', sentence))
            has_placeholder = bool(re.search(r'\[cite:[a-f0-9-]+\]', sentence))
            has_numbers = bool(re.search(
                r'\d+%|\$\d+|\d+\s*(million|billion|thousand|percent)',
                sentence,
                re.IGNORECASE
            ))

            if has_citation:
                cited += 1
            if has_assumption:
                assumptions += 1
            if has_placeholder:
                issues.append(f"Unresolved placeholder in sentence {i + 1}")
            if has_numbers:
                numerical += 1
                if has_citation or has_assumption:
                    numerical_cited += 1
                else:
                    issues.append(
                        f"Numerical claim without citation in sentence {i + 1}: "
                        f"'{sentence[:50]}...'"
                    )

        coverage = (cited + assumptions) / total * 100 if total > 0 else 0

        return CitationReport(
            total_sentences=total,
            cited_sentences=cited,
            assumption_labels=assumptions,
            numerical_claims=numerical,
            numerical_cited=numerical_cited,
            coverage_percent=round(coverage, 1),
            target_met=coverage >= 80,
            issues=issues[:20],  # Limit issues
        )

    def create_citation_models(
        self,
        document_id: UUID,
        resolved: list[ResolvedCitation] | None = None,
        content: str | None = None,
    ) -> list[Citation]:
        """
        Create Citation models for database storage.

        Args:
            document_id: Document ID to link citations
            resolved: Optional list of resolved citations
            content: Optional content to extract anchors from

        Returns:
            List of Citation models
        """
        resolved = resolved or self._resolved
        citations = []

        for r in resolved:
            anchors = []

            # Find anchors in content if provided
            if content:
                pattern = rf'\[{r.number}\]'
                for match in re.finditer(pattern, content):
                    # Get surrounding context
                    start = max(0, match.start() - 100)
                    end = min(len(content), match.end() + 100)
                    context = content[start:end]

                    anchors.append(CitationAnchor(
                        chunk_id=r.chunk_id,
                        document_id=document_id,
                        start_offset=match.start(),
                        end_offset=match.end(),
                        quoted_text=context,
                    ))

            citation = Citation(
                document_id=document_id,
                citation_key=str(r.number),
                source_id=r.source_id,
                reference_entry=r.reference_entry,
                anchors=anchors,
            )
            citations.append(citation)

        return citations

    def get_stats(self) -> dict[str, Any]:
        """
        Get citation statistics.

        Returns:
            Dictionary with stats
        """
        return {
            "total_citations": len(self._resolved),
            "unique_sources": len(set(r.source_id for r in self._resolved)),
        }
