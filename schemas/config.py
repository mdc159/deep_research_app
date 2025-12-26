"""
Configuration schemas for the Deep Research App.

This module defines Pydantic models for all configurable aspects of the
research pipeline, including model selection, ingestion, and retrieval settings.
"""

from typing import Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ModelConfig(BaseModel):
    """Per-stage model configuration for the research pipeline."""

    planner: str = Field(
        default="anthropic:claude-sonnet-4-5-20250929",
        description="Model for planning and orchestration",
    )
    drafter: str = Field(
        default="anthropic:claude-sonnet-4-5-20250929",
        description="Model for content generation and drafting",
    )
    critic: str = Field(
        default="anthropic:claude-sonnet-4-5-20250929",
        description="Model for quality review and critique",
    )
    embedder: str = Field(
        default="text-embedding-3-small",
        description="Model for generating embeddings",
    )
    contextualizer: str | None = Field(
        default="anthropic:claude-haiku-3",
        description="Model for contextual embedding generation (optional)",
    )


class IngestionConfig(BaseModel):
    """Configuration for the document ingestion pipeline."""

    # Chunking settings
    chunk_size_tokens: int = Field(
        default=1000,
        ge=100,
        le=4000,
        description="Target chunk size in tokens",
    )
    chunk_overlap_tokens: int = Field(
        default=200,
        ge=0,
        le=500,
        description="Overlap between consecutive chunks in tokens",
    )
    chunking_strategy: Literal["hybrid", "simple", "semantic"] = Field(
        default="hybrid",
        description="Chunking strategy to use",
    )

    # Embedding settings
    embedding_model: str = Field(
        default="text-embedding-3-small",
        description="Embedding model to use",
    )
    embedding_dimensions: int = Field(
        default=1536,
        description="Embedding vector dimensions",
    )
    use_contextual_embeddings: bool = Field(
        default=True,
        description="Whether to use contextual embeddings for improved retrieval",
    )

    # Storage settings
    store_html_snapshots: bool = Field(
        default=True,
        description="Whether to store HTML snapshots of URLs",
    )
    store_pdf_originals: bool = Field(
        default=True,
        description="Whether to store original PDF files",
    )

    def validate_overlap(self) -> "IngestionConfig":
        """Validate that overlap is less than chunk size."""
        if self.chunk_overlap_tokens >= self.chunk_size_tokens:
            raise ValueError("Chunk overlap must be less than chunk size")
        return self


class RetrievalConfig(BaseModel):
    """Configuration for the retrieval pipeline."""

    # Search settings
    search_type: Literal["hybrid", "vector", "keyword"] = Field(
        default="hybrid",
        description="Type of search to perform",
    )
    vector_weight: float = Field(
        default=0.6,
        ge=0.0,
        le=1.0,
        description="Weight for vector search in hybrid mode",
    )
    keyword_weight: float = Field(
        default=0.4,
        ge=0.0,
        le=1.0,
        description="Weight for keyword search in hybrid mode",
    )
    rrf_k: int = Field(
        default=60,
        ge=1,
        le=100,
        description="Constant k for Reciprocal Rank Fusion",
    )

    # Result settings
    initial_top_k: int = Field(
        default=50,
        ge=1,
        le=200,
        description="Number of results before reranking",
    )
    final_top_k: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Number of results after reranking",
    )

    # Reranking settings
    use_reranking: bool = Field(
        default=True,
        description="Whether to use CrossEncoder reranking",
    )
    reranker_model: str = Field(
        default="ms-marco-MiniLM-L-6-v2",
        description="CrossEncoder model for reranking",
    )

    # Query expansion
    use_query_expansion: bool = Field(
        default=False,
        description="Whether to use query expansion",
    )
    expansion_model: str | None = Field(
        default=None,
        description="Model for query expansion",
    )

    def validate_weights(self) -> "RetrievalConfig":
        """Validate that weights sum to 1.0 for hybrid search."""
        if self.search_type == "hybrid":
            total = self.vector_weight + self.keyword_weight
            if not (0.99 <= total <= 1.01):  # Allow small floating point error
                raise ValueError(f"Weights must sum to 1.0, got {total}")
        return self


class RunConfig(BaseModel):
    """Configuration for a research run."""

    title: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Title of the research run",
    )
    objective: str = Field(
        ...,
        min_length=10,
        description="Research objective or question",
    )
    constraints: dict[str, str] = Field(
        default_factory=dict,
        description="Additional constraints for the research",
    )
    output_format: Literal["markdown"] = Field(
        default="markdown",
        description="Output format for the research paper",
    )
    citation_style: Literal["numeric", "author-date"] = Field(
        default="numeric",
        description="Citation style to use",
    )
    models: ModelConfig = Field(
        default_factory=ModelConfig,
        description="Model configuration for each pipeline stage",
    )
    ingestion: IngestionConfig = Field(
        default_factory=IngestionConfig,
        description="Ingestion pipeline configuration",
    )
    retrieval: RetrievalConfig = Field(
        default_factory=RetrievalConfig,
        description="Retrieval pipeline configuration",
    )


class AppSettings(BaseSettings):
    """Application-wide settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # API Keys
    anthropic_api_key: str | None = Field(default=None)
    openai_api_key: str | None = Field(default=None)
    google_api_key: str | None = Field(default=None)
    openrouter_api_key: str | None = Field(default=None)
    tavily_api_key: str | None = Field(default=None)

    # Supabase
    supabase_url: str | None = Field(default=None)
    supabase_key: str | None = Field(default=None)
    supabase_service_key: str | None = Field(default=None)

    # Default models
    planner_model: str = Field(default="anthropic:claude-sonnet-4-5-20250929")
    drafter_model: str = Field(default="anthropic:claude-sonnet-4-5-20250929")
    critic_model: str = Field(default="anthropic:claude-sonnet-4-5-20250929")
    embedding_model: str = Field(default="text-embedding-3-small")
    contextualizer_model: str | None = Field(default="anthropic:claude-haiku-3")

    # Ingestion defaults
    use_contextual_embeddings: bool = Field(default=True)
    chunk_size_tokens: int = Field(default=1000)
    chunk_overlap_tokens: int = Field(default=200)

    # Retrieval defaults
    search_type: str = Field(default="hybrid")
    vector_weight: float = Field(default=0.6)
    keyword_weight: float = Field(default=0.4)
    rrf_k: int = Field(default=60)
    use_reranking: bool = Field(default=True)
    reranker_model: str = Field(default="ms-marco-MiniLM-L-6-v2")

    # Application settings
    log_level: str = Field(default="INFO")
    streamlit_port: int = Field(default=8501)

    # Optional integrations
    redis_url: str | None = Field(default=None)
    langsmith_api_key: str | None = Field(default=None)
    langsmith_project: str | None = Field(default=None)

    def get_model_config(self) -> ModelConfig:
        """Create ModelConfig from environment settings."""
        return ModelConfig(
            planner=self.planner_model,
            drafter=self.drafter_model,
            critic=self.critic_model,
            embedder=self.embedding_model,
            contextualizer=self.contextualizer_model,
        )

    def get_ingestion_config(self) -> IngestionConfig:
        """Create IngestionConfig from environment settings."""
        return IngestionConfig(
            chunk_size_tokens=self.chunk_size_tokens,
            chunk_overlap_tokens=self.chunk_overlap_tokens,
            use_contextual_embeddings=self.use_contextual_embeddings,
            embedding_model=self.embedding_model,
        )

    def get_retrieval_config(self) -> RetrievalConfig:
        """Create RetrievalConfig from environment settings."""
        return RetrievalConfig(
            search_type=self.search_type,  # type: ignore
            vector_weight=self.vector_weight,
            keyword_weight=self.keyword_weight,
            rrf_k=self.rrf_k,
            use_reranking=self.use_reranking,
            reranker_model=self.reranker_model,
        )


# Singleton instance for app settings
_settings: AppSettings | None = None


def get_settings() -> AppSettings:
    """Get the application settings singleton."""
    global _settings
    if _settings is None:
        _settings = AppSettings()
    return _settings
