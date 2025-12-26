# Deep Research App

A Python research system that uses the `deepagents` framework with a Streamlit UI.

## Features

- **PDF + URL Ingestion**: Structure-aware chunking with Docling and crawl4ai
- **Hybrid Search**: Vector + keyword search with RRF fusion and CrossEncoder reranking
- **Contextual Embeddings**: LLM-enhanced embeddings for improved retrieval
- **Evidence-First Drafting**: Claims linked to evidence or marked as assumptions
- **Citation Management**: IEEE-style references with source provenance
- **Version Control**: Document versioning with change logs and diffs
- **Model Flexibility**: Swap models per pipeline stage via configuration

## Quick Start

### Prerequisites

- Python 3.12+
- [Astral UV](https://github.com/astral-sh/uv) package manager
- Supabase account (or local PostgreSQL with pgvector)

### Installation

```bash
# Clone and navigate to the project
cd deep_research_app

# Create virtual environment with UV
uv venv

# Activate the environment
source .venv/bin/activate  # Unix/macOS
# or
.venv\Scripts\activate     # Windows

# Install dependencies
uv sync
```

### Configuration

1. Copy the environment template:
   ```bash
   cp .env.example .env
   ```

2. Fill in your API keys in `.env`:
   - `ANTHROPIC_API_KEY` - For Claude models
   - `OPENAI_API_KEY` - For embeddings
   - `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` - For database
   - `TAVILY_API_KEY` - For web search

3. Apply database migrations to Supabase:
   - Go to your Supabase project's SQL Editor
   - Run the contents of `migrations/001_init.sql`

### Running the App

```bash
# Start the Streamlit app
uv run streamlit run app/streamlit_app.py
```

## Project Structure

```
deep_research_app/
├── app/                    # Streamlit UI
│   ├── streamlit_app.py    # Main entry point
│   └── ui/                 # UI components
├── research_agent/         # Agent pipeline
│   ├── agent.py            # create_research_agent()
│   ├── prompts.py          # System prompts
│   ├── tools/              # Agent tools
│   └── middleware/         # Custom middleware
├── ingestion/              # PDF/URL processing
├── retrieval/              # Hybrid search
├── storage/                # Supabase operations
├── schemas/                # Pydantic models
├── migrations/             # SQL migrations
└── tests/                  # Test suite
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      STREAMLIT UI                            │
├──────────────────────┬──────────────────────────────────────┤
│ Left Pane            │ Right Pane                           │
│ - Run Manager        │ - Document Composer                  │
│ - Evidence Browser   │   [Preview] [Edit] [Diff]            │
│ - Run Log            │ - Citation Inspector                 │
└──────────────────────┴──────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  DEEPAGENTS ORCHESTRATOR                     │
│  ├── TodoListMiddleware (planning)                          │
│  ├── IngestionMiddleware (PDF/URL processing)               │
│  ├── RetrievalMiddleware (hybrid search)                    │
│  ├── CitationMiddleware (evidence linking)                  │
│  └── CritiqueMiddleware (quality checks)                    │
│                                                              │
│  Subagents: researcher, drafter, critic                     │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      DATA LAYER                              │
│  Supabase Postgres + pgvector + tsvector                    │
└─────────────────────────────────────────────────────────────┘
```

## Usage

### Creating a Research Run

1. Click "New Run" in the left pane
2. Enter your research objective
3. Upload PDFs or add URLs
4. Click "Draft" to generate the research paper

### Workflow

1. **Plan**: Agent creates a todo list for the research
2. **Ingest**: PDFs/URLs are chunked and embedded
3. **Research**: Evidence is gathered via hybrid search
4. **Draft**: Sections are written with inline citations
5. **Cite**: Citations are resolved to numbered references
6. **Critique**: Quality checks identify issues
7. **Revise**: Issues are addressed, creating new version

## Development

### Running Tests

```bash
uv run pytest tests/ -v
```

### Code Formatting

```bash
uv run black .
uv run ruff check --fix .
```

### Type Checking

```bash
uv run mypy .
```

## License

MIT

## Acknowledgments

Built with:
- [deepagents](https://github.com/deepagents/deepagents) - Agent framework
- [LangChain](https://langchain.com/) - LLM abstraction
- [Docling](https://github.com/DS4SD/docling) - PDF extraction
- [crawl4ai](https://github.com/unclecode/crawl4ai) - Web content fetching
- [Supabase](https://supabase.com/) - Database and vector storage
- [Streamlit](https://streamlit.io/) - UI framework
