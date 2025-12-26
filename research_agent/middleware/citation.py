"""
Citation middleware for the research agent.

This middleware manages citation tracking and resolution during document generation.
"""

import logging
import re
from typing import Any
from uuid import UUID

from schemas.config import RunConfig
from schemas.models import Citation, CitationAnchor

logger = logging.getLogger(__name__)


class CitationMiddleware:
    """
    Middleware for managing citations.

    This middleware:
    - Tracks citation placeholders during drafting
    - Resolves placeholders to numbered references
    - Generates IEEE-style reference lists
    - Validates citation coverage
    """

    def __init__(self, config: RunConfig | None = None):
        """
        Initialize the citation middleware.

        Args:
            config: Run configuration
        """
        self.config = config
        self._run_id: UUID | None = None
        self._citation_map: dict[UUID, int] = {}  # chunk_id -> citation number
        self._reference_list: list[Citation] = []
        self._anchors: list[CitationAnchor] = []

    def set_run(self, run_id: UUID) -> None:
        """
        Set the current run ID for citation context.

        Args:
            run_id: Current run ID
        """
        self._run_id = run_id

    def get_tools(self) -> list:
        """
        Get the citation tools provided by this middleware.

        Returns:
            List of LangChain tools
        """
        from research_agent.tools.citation import (
            format_citation_tool,
            get_citation_for_claim_tool,
            label_assumption_tool,
            resolve_citations_tool,
            validate_citations_tool,
        )

        return [
            format_citation_tool,
            resolve_citations_tool,
            validate_citations_tool,
            label_assumption_tool,
            get_citation_for_claim_tool,
        ]

    def register_citation(self, chunk_id: UUID, source_id: UUID) -> int:
        """
        Register a citation and get its number.

        Args:
            chunk_id: UUID of the cited chunk
            source_id: UUID of the source

        Returns:
            Citation number (1-indexed)
        """
        if chunk_id in self._citation_map:
            return self._citation_map[chunk_id]

        # Assign next number
        citation_num = len(self._citation_map) + 1
        self._citation_map[chunk_id] = citation_num

        # Create citation record
        citation = Citation(
            run_id=self._run_id,
            chunk_id=chunk_id,
            source_id=source_id,
            citation_number=citation_num,
        )
        self._reference_list.append(citation)

        return citation_num

    def add_anchor(
        self,
        chunk_id: UUID,
        document_id: UUID,
        start_offset: int,
        end_offset: int,
        quoted_text: str | None = None,
    ) -> None:
        """
        Add a citation anchor (location in document).

        Args:
            chunk_id: UUID of the cited chunk
            document_id: UUID of the document
            start_offset: Start character offset
            end_offset: End character offset
            quoted_text: Optional quoted text
        """
        anchor = CitationAnchor(
            chunk_id=chunk_id,
            document_id=document_id,
            start_offset=start_offset,
            end_offset=end_offset,
            quoted_text=quoted_text,
        )
        self._anchors.append(anchor)

    def find_placeholders(self, content: str) -> list[str]:
        """
        Find all citation placeholders in content.

        Args:
            content: Document content

        Returns:
            List of chunk IDs referenced
        """
        pattern = r'\[cite:([a-f0-9-]+)\]'
        return re.findall(pattern, content)

    def resolve_placeholders(self, content: str) -> str:
        """
        Resolve citation placeholders to numbered references.

        Args:
            content: Content with [cite:chunk_id] placeholders

        Returns:
            Content with [1], [2], etc.
        """
        placeholders = self.find_placeholders(content)

        # Deduplicate while preserving order
        unique_chunks = list(dict.fromkeys(placeholders))

        resolved = content
        for chunk_id_str in unique_chunks:
            chunk_id = UUID(chunk_id_str)

            # Get or assign citation number
            if chunk_id not in self._citation_map:
                # Need to look up source - for now just assign number
                citation_num = len(self._citation_map) + 1
                self._citation_map[chunk_id] = citation_num
            else:
                citation_num = self._citation_map[chunk_id]

            # Replace all instances
            resolved = resolved.replace(
                f"[cite:{chunk_id_str}]",
                f"[{citation_num}]"
            )

        return resolved

    def get_citation_coverage(self, content: str) -> dict[str, Any]:
        """
        Calculate citation coverage metrics.

        Args:
            content: Document content

        Returns:
            Coverage metrics
        """
        # Split into sentences
        sentences = re.split(r'[.!?]\s+', content)
        total = len(sentences)

        cited = 0
        assumptions = 0
        numerical_uncited = 0

        for sentence in sentences:
            has_citation = bool(re.search(r'\[\d+\]', sentence))
            has_assumption = bool(re.search(r'\[ASSUMPTION:', sentence))
            has_numbers = bool(re.search(r'\d+%|\$\d+|\d+\s*(million|billion)', sentence))

            if has_citation:
                cited += 1
            if has_assumption:
                assumptions += 1
            if has_numbers and not (has_citation or has_assumption):
                numerical_uncited += 1

        coverage = (cited + assumptions) / total * 100 if total > 0 else 0

        return {
            "total_sentences": total,
            "cited_sentences": cited,
            "assumptions": assumptions,
            "numerical_uncited": numerical_uncited,
            "coverage_percent": round(coverage, 1),
            "meets_target": coverage >= 80,
        }

    def get_reference_list(self) -> list[Citation]:
        """
        Get the list of citations in order.

        Returns:
            Ordered list of Citation objects
        """
        return sorted(self._reference_list, key=lambda c: c.citation_number)

    def get_stats(self) -> dict[str, Any]:
        """
        Get citation statistics.

        Returns:
            Dictionary with citation stats
        """
        return {
            "total_citations": len(self._citation_map),
            "unique_chunks_cited": len(set(self._citation_map.keys())),
            "anchors_count": len(self._anchors),
        }

    def reset(self) -> None:
        """Reset citation tracking for a new document."""
        self._citation_map = {}
        self._reference_list = []
        self._anchors = []
        self._run_id = None


def create_citation_middleware(
    config: RunConfig | None = None,
) -> CitationMiddleware:
    """
    Factory function to create citation middleware.

    Args:
        config: Run configuration

    Returns:
        CitationMiddleware instance
    """
    return CitationMiddleware(config)
