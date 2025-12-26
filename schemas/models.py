"""
Data models for the Deep Research App.

This module defines Pydantic models for all core data entities including
runs, sources, chunks, documents, citations, and search results.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from schemas.config import RunConfig


class Run(BaseModel):
    """A research run representing a complete research session."""

    id: UUID = Field(default_factory=uuid4)
    title: str = Field(..., min_length=1, max_length=200)
    objective: str = Field(..., min_length=10)
    constraints: dict[str, str] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    status: Literal["created", "ingesting", "drafting", "reviewing", "complete", "error"] = Field(
        default="created"
    )
    config: RunConfig = Field(...)

    class Config:
        from_attributes = True


class Source(BaseModel):
    """A source document (PDF, URL, or note) ingested for research."""

    id: UUID = Field(default_factory=uuid4)
    run_id: UUID = Field(...)
    type: Literal["pdf", "url", "note"] = Field(...)
    title: str = Field(..., min_length=1)
    uri: str = Field(..., description="URL or storage path")
    captured_at: datetime = Field(default_factory=datetime.utcnow)
    content_hash: str = Field(..., description="Hash of source content for deduplication")
    metadata: dict = Field(default_factory=dict)

    class Config:
        from_attributes = True


class Chunk(BaseModel):
    """A chunk of evidence extracted from a source."""

    id: UUID = Field(default_factory=uuid4)
    source_id: UUID = Field(...)
    run_id: UUID = Field(...)
    chunk_index: int = Field(..., ge=0)
    content: str = Field(..., min_length=1)
    contextual_prefix: str | None = Field(
        default=None,
        description="LLM-generated context for improved retrieval",
    )
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)
    section_hint: str | None = Field(default=None, description="Section title or hint")
    heading_hierarchy: list[str] = Field(
        default_factory=list,
        description="Heading path from document structure",
    )
    content_hash: str = Field(...)
    token_count: int = Field(..., ge=1)
    chunk_method: str = Field(..., description="Method used for chunking")
    embedding: list[float] | None = Field(default=None, description="Vector embedding")
    metadata: dict = Field(default_factory=dict)

    class Config:
        from_attributes = True

    @property
    def full_content(self) -> str:
        """Get the full content including contextual prefix if available."""
        if self.contextual_prefix:
            return f"{self.contextual_prefix}\n---\n{self.content}"
        return self.content


class Document(BaseModel):
    """A versioned research document produced by the pipeline."""

    id: UUID = Field(default_factory=uuid4)
    run_id: UUID = Field(...)
    version: int = Field(..., ge=1)
    title: str = Field(..., min_length=1)
    markdown: str = Field(..., description="Document content in Markdown format")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    change_log: str | None = Field(
        default=None,
        description="Description of changes from previous version",
    )
    config_snapshot: RunConfig = Field(
        ...,
        description="Configuration at time of generation for reproducibility",
    )

    class Config:
        from_attributes = True


class CitationAnchor(BaseModel):
    """An anchor point linking a citation to a specific chunk location."""

    chunk_id: UUID = Field(...)
    page: int | None = Field(default=None)
    quote_start: int | None = Field(default=None, description="Character offset of quote start")
    quote_end: int | None = Field(default=None, description="Character offset of quote end")


class Citation(BaseModel):
    """A citation linking a claim to evidence."""

    id: UUID = Field(default_factory=uuid4)
    document_id: UUID = Field(...)
    citation_key: str = Field(..., description="Citation marker, e.g., [1], [2]")
    source_id: UUID = Field(...)
    reference_entry: str = Field(..., description="Formatted reference entry")
    anchors: list[CitationAnchor] = Field(
        default_factory=list,
        description="Anchor points in the evidence",
    )

    class Config:
        from_attributes = True


class SearchResult(BaseModel):
    """A search result with provenance information."""

    chunk_id: UUID = Field(...)
    source_id: UUID = Field(...)
    content: str = Field(...)
    contextual_prefix: str | None = Field(default=None)
    page_start: int | None = Field(default=None)
    page_end: int | None = Field(default=None)
    section_hint: str | None = Field(default=None)
    score: float = Field(..., description="Relevance score")
    source_title: str = Field(...)
    source_uri: str = Field(...)
    search_type: Literal["vector", "keyword", "hybrid"] = Field(default="hybrid")

    class Config:
        from_attributes = True

    @property
    def location_str(self) -> str:
        """Get a human-readable location string."""
        if self.page_start and self.page_end:
            if self.page_start == self.page_end:
                return f"p. {self.page_start}"
            return f"pp. {self.page_start}-{self.page_end}"
        elif self.page_start:
            return f"p. {self.page_start}"
        return ""


class CritiqueIssue(BaseModel):
    """An issue identified during document critique."""

    type: Literal[
        "missing_citation",
        "weak_claim",
        "math_error",
        "contradiction",
        "unsupported",
        "unclear",
        "incomplete",
    ] = Field(...)
    severity: Literal["error", "warning", "info"] = Field(...)
    location: str = Field(..., description="Section or line reference")
    description: str = Field(..., min_length=10)
    suggestion: str | None = Field(default=None, description="Suggested fix")
    related_chunks: list[UUID] = Field(
        default_factory=list,
        description="Relevant evidence chunks",
    )

    class Config:
        from_attributes = True


class Event(BaseModel):
    """An event in the pipeline for observability."""

    id: UUID = Field(default_factory=uuid4)
    run_id: UUID = Field(...)
    ts: datetime = Field(default_factory=datetime.utcnow)
    type: Literal["node_start", "node_end", "tool_call", "error", "checkpoint"] = Field(...)
    node_name: str | None = Field(default=None)
    payload: dict = Field(default_factory=dict)

    class Config:
        from_attributes = True


class TokenUsage(BaseModel):
    """Token usage tracking for a run or node."""

    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    model: str = Field(...)
    node: str | None = Field(default=None)

    @property
    def total_tokens(self) -> int:
        """Get total tokens used."""
        return self.input_tokens + self.output_tokens


class CostEstimate(BaseModel):
    """Cost estimate for a run."""

    run_id: UUID = Field(...)
    total_input_tokens: int = Field(default=0, ge=0)
    total_output_tokens: int = Field(default=0, ge=0)
    estimated_cost_usd: float = Field(default=0.0, ge=0.0)
    breakdown: dict[str, float] = Field(
        default_factory=dict,
        description="Cost breakdown by model/node",
    )
