"""
Citation tools for the research agent.

These tools help manage citations and references in research documents.
"""

import logging
import re
from typing import Annotated
from uuid import UUID

from langchain_core.tools import tool

from schemas.models import Citation, CitationAnchor
from storage.supabase import get_supabase_client

logger = logging.getLogger(__name__)

# Global state for citation tracking
_citation_map: dict[UUID, int] = {}  # chunk_id -> citation number
_reference_list: list[dict] = []  # List of reference entries


def reset_citations() -> None:
    """Reset citation tracking for a new document."""
    global _citation_map, _reference_list
    _citation_map = {}
    _reference_list = []


def get_citation_state() -> tuple[dict[UUID, int], list[dict]]:
    """Get current citation state."""
    return _citation_map, _reference_list


@tool
def format_citation_tool(
    chunk_id: Annotated[str, "UUID of the chunk to cite"],
    quote: Annotated[str | None, "Optional quote from the source"] = None,
) -> str:
    """
    Format a citation placeholder for a chunk.

    Use this when writing content to create a citation reference.
    The placeholder will be resolved to a number like [1] later.

    Args:
        chunk_id: UUID of the evidence chunk
        quote: Optional direct quote

    Returns:
        Citation placeholder in format [cite:chunk_id]
    """
    placeholder = f"[cite:{chunk_id}]"

    if quote:
        return f'"{quote}" {placeholder}'
    else:
        return placeholder


@tool
async def resolve_citations_tool(
    markdown: Annotated[str, "Markdown content with citation placeholders"],
) -> str:
    """
    Resolve citation placeholders to numbered references.

    This tool:
    1. Finds all [cite:chunk_id] placeholders
    2. Assigns sequential numbers [1], [2], etc.
    3. Generates IEEE-style reference list
    4. Returns the resolved markdown

    Args:
        markdown: Content with [cite:chunk_id] placeholders

    Returns:
        Resolved markdown with numbered citations and reference list
    """
    reset_citations()

    try:
        client = get_supabase_client()

        # Find all citation placeholders
        pattern = r'\[cite:([a-f0-9-]+)\]'
        matches = re.findall(pattern, markdown)

        if not matches:
            return markdown + "\n\n## References\n\nNo citations found."

        # Deduplicate while preserving order
        unique_chunks = list(dict.fromkeys(matches))

        # Assign citation numbers and build references
        resolved_markdown = markdown
        references = []

        for i, chunk_id_str in enumerate(unique_chunks, 1):
            chunk_id = UUID(chunk_id_str)
            _citation_map[chunk_id] = i

            # Get chunk and source info
            chunk = await client.get_chunk(chunk_id)

            if chunk:
                # Get source for this chunk
                sources = await client.get_sources(chunk.run_id)
                source = next(
                    (s for s in sources if s.id == chunk.source_id),
                    None
                )

                if source:
                    # Format reference entry
                    if source.type == "url":
                        ref_entry = (
                            f'[{i}] "{source.title}," {source.metadata.get("domain", "")}, '
                            f'{source.uri}, Accessed: {source.captured_at.strftime("%Y-%m-%d")}.'
                        )
                    else:  # PDF
                        page_info = ""
                        if chunk.page_start:
                            page_info = f" p. {chunk.page_start}"
                            if chunk.page_end and chunk.page_end != chunk.page_start:
                                page_info = f" pp. {chunk.page_start}-{chunk.page_end}"

                        ref_entry = f'[{i}] "{source.title}," {source.captured_at.strftime("%Y")}.{page_info}'

                    references.append(ref_entry)
                    _reference_list.append({
                        "number": i,
                        "chunk_id": str(chunk_id),
                        "source_id": str(source.id),
                        "entry": ref_entry,
                    })
                else:
                    references.append(f"[{i}] Source not found for chunk {chunk_id}")
            else:
                references.append(f"[{i}] Chunk not found: {chunk_id}")

            # Replace all occurrences of this chunk's placeholder
            resolved_markdown = resolved_markdown.replace(
                f"[cite:{chunk_id_str}]",
                f"[{i}]"
            )

        # Append reference list
        ref_section = "\n\n## References\n\n" + "\n\n".join(references)
        resolved_markdown += ref_section

        return resolved_markdown

    except Exception as e:
        logger.exception(f"Citation resolution failed: {e}")
        return f"Error resolving citations: {str(e)}"


@tool
async def validate_citations_tool(
    markdown: Annotated[str, "Markdown content to validate"],
) -> str:
    """
    Validate citation coverage in a document.

    This tool checks:
    - Percentage of factual claims with citations
    - Missing citations on numerical claims
    - Unresolved placeholders
    - Assumption labels

    Args:
        markdown: Document content to validate

    Returns:
        Validation report with issues and metrics
    """
    try:
        issues = []
        metrics = {
            "total_sentences": 0,
            "cited_sentences": 0,
            "assumptions": 0,
            "unresolved_placeholders": 0,
            "numerical_claims": 0,
            "cited_numerical": 0,
        }

        # Split into sentences (simple heuristic)
        sentences = re.split(r'[.!?]\s+', markdown)
        metrics["total_sentences"] = len(sentences)

        # Check each sentence
        for i, sentence in enumerate(sentences):
            # Check for citations
            has_citation = bool(re.search(r'\[\d+\]', sentence))
            has_placeholder = bool(re.search(r'\[cite:[a-f0-9-]+\]', sentence))
            has_assumption = bool(re.search(r'\[ASSUMPTION:', sentence))

            if has_citation:
                metrics["cited_sentences"] += 1
            if has_assumption:
                metrics["assumptions"] += 1
            if has_placeholder:
                metrics["unresolved_placeholders"] += 1
                issues.append(f"Unresolved citation placeholder in: '{sentence[:50]}...'")

            # Check for numerical claims
            has_numbers = bool(re.search(r'\d+%|\$\d+|\d+\s*(million|billion|thousand)', sentence))
            if has_numbers:
                metrics["numerical_claims"] += 1
                if has_citation or has_assumption:
                    metrics["cited_numerical"] += 1
                else:
                    issues.append(f"Numerical claim without citation: '{sentence[:50]}...'")

        # Calculate coverage
        if metrics["total_sentences"] > 0:
            coverage = (metrics["cited_sentences"] + metrics["assumptions"]) / metrics["total_sentences"] * 100
        else:
            coverage = 0

        numerical_coverage = 0
        if metrics["numerical_claims"] > 0:
            numerical_coverage = metrics["cited_numerical"] / metrics["numerical_claims"] * 100

        # Build report
        report_lines = [
            "## Citation Validation Report",
            "",
            "### Metrics",
            f"- Total sentences: {metrics['total_sentences']}",
            f"- Cited sentences: {metrics['cited_sentences']}",
            f"- Assumptions labeled: {metrics['assumptions']}",
            f"- **Citation coverage: {coverage:.1f}%**",
            "",
            f"- Numerical claims: {metrics['numerical_claims']}",
            f"- Numerical claims cited: {metrics['cited_numerical']}",
            f"- **Numerical coverage: {numerical_coverage:.1f}%**",
            "",
        ]

        if metrics["unresolved_placeholders"] > 0:
            report_lines.append(
                f"⚠️ **Unresolved placeholders: {metrics['unresolved_placeholders']}**"
            )
            report_lines.append("")

        # Target check
        target_met = coverage >= 80
        report_lines.append(
            f"### Target (80% coverage): {'✅ MET' if target_met else '❌ NOT MET'}"
        )
        report_lines.append("")

        if issues:
            report_lines.append("### Issues Found")
            for issue in issues[:10]:  # Limit to first 10
                report_lines.append(f"- {issue}")
            if len(issues) > 10:
                report_lines.append(f"- ... and {len(issues) - 10} more issues")

        return "\n".join(report_lines)

    except Exception as e:
        logger.exception(f"Citation validation failed: {e}")
        return f"Error validating citations: {str(e)}"


@tool
def label_assumption_tool(
    claim: Annotated[str, "The claim being made"],
    reason: Annotated[str, "Brief reason why this is an assumption"],
) -> str:
    """
    Format an assumption label for a claim without evidence.

    Use this when making a claim that cannot be backed by evidence
    but is necessary for the document.

    Args:
        claim: The claim statement
        reason: Why it's an assumption (e.g., "data not available")

    Returns:
        Formatted claim with assumption label
    """
    return f"{claim} [ASSUMPTION: {reason}]"


@tool
async def get_citation_for_claim_tool(
    claim: Annotated[str, "The claim that needs a citation"],
    search_query: Annotated[str | None, "Optional search query"] = None,
) -> str:
    """
    Find and format a citation for a specific claim.

    This tool searches for relevant evidence and provides
    a formatted citation if found.

    Args:
        claim: The claim that needs support
        search_query: Optional custom search query

    Returns:
        Citation placeholder if evidence found, or suggestion
    """
    from research_agent.tools.retrieval import get_retrieval_context

    run_id, config = get_retrieval_context()

    if not run_id:
        return "Error: No active run."

    try:
        from retrieval.reranker import RetrievalPipeline

        query = search_query or claim
        pipeline = RetrievalPipeline(config)
        results = await pipeline.retrieve(query, run_id, top_k=3)

        if not results:
            return (
                f"No evidence found for claim: '{claim}'\n"
                "Consider:\n"
                "- Rephrasing the search query\n"
                "- Marking as [ASSUMPTION: reason]\n"
                "- Ingesting additional sources"
            )

        best = results[0]
        citation = f"[cite:{best.chunk_id}]"

        return (
            f"Found evidence for claim:\n"
            f"- Source: {best.source_title}\n"
            f"- Relevance: {best.score:.3f}\n"
            f"- Citation: {citation}\n\n"
            f"Evidence excerpt:\n{best.content[:300]}..."
        )

    except Exception as e:
        logger.exception(f"Citation search failed: {e}")
        return f"Error finding citation: {str(e)}"
