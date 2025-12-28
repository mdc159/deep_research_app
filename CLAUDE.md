# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Deep Research App is a Python research system that transforms PDFs, URLs, and research questions into versioned, citation-backed Markdown papers using the `deepagents` framework with a Streamlit UI.

## Development Commands

```bash
# Install dependencies (uses UV package manager)
uv sync

# Install with dev dependencies
uv sync --dev

# Run the Streamlit app
uv run streamlit run app/streamlit_app.py

# Run tests
uv run pytest tests/ -v

# Run a single test file
uv run pytest tests/test_example.py -v

# Code formatting
uv run black .
uv run ruff check --fix .

# Type checking
uv run mypy .
```

## Architecture

The system uses a multi-agent architecture with middleware for state tracking:

### Agent Pipeline (`research_agent/`)
- **ResearchAgent** (`agent.py`): Main orchestrator that creates a `deepagents` agent with subagents (researcher, drafter, critic)
- **Middleware**: Custom middleware components track state across the pipeline:
  - `IngestionMiddleware`: PDF/URL processing state
  - `RetrievalMiddleware`: Hybrid search state
  - `CitationMiddleware`: Evidence linking state
  - `CritiqueMiddleware`: Quality check state
- **Prompts** (`prompts.py`): System prompts for orchestrator and subagents

### Data Flow
1. **Ingestion** (`ingestion/`): Docling for PDFs, crawl4ai for URLs, structure-aware chunking
2. **Storage** (`storage/`): Supabase with pgvector for vectors, tsvector for keyword search
3. **Retrieval** (`retrieval/`): Hybrid search (vector + keyword) with RRF fusion and CrossEncoder reranking
4. **Citation** (`services/citation.py`): IEEE-style references with source provenance

### Configuration (`schemas/config.py`)
- `ModelConfig`: Per-stage model selection (planner, drafter, critic, embedder)
- `IngestionConfig`: Chunk size, overlap, embedding settings
- `RetrievalConfig`: Search type, weights, reranking settings
- `AppSettings`: Environment-based settings singleton

### UI (`app/`)
- `streamlit_app.py`: Main entry point
- `ui/`: Components for composer, evidence browser, progress tracking, run management

## Database

Uses Supabase PostgreSQL with pgvector extension. Apply migrations from `migrations/001_init.sql` in Supabase SQL Editor.

## Model Specification Format

Models are specified as `provider:model_name`:
- `anthropic:claude-sonnet-4-5-20250929`
- `openai:gpt-4o`
- `google:gemini-pro`

## Required Environment Variables

Copy `.env.example` to `.env` and configure:
- `ANTHROPIC_API_KEY`: For Claude models
- `OPENAI_API_KEY`: For embeddings
- `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`: Database connection
- `TAVILY_API_KEY`: Web search
