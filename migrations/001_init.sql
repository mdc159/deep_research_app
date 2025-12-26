-- =============================================================================
-- DEEP RESEARCH APP - Initial Database Schema
-- =============================================================================
-- This migration creates all core tables for the research application.
-- Designed for Supabase with pgvector extension.
-- =============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- =============================================================================
-- RUNS TABLE
-- =============================================================================
-- Represents a complete research session with configuration and status.

CREATE TABLE runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT NOT NULL,
    objective TEXT NOT NULL,
    constraints JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    status TEXT CHECK (status IN ('created', 'ingesting', 'drafting', 'reviewing', 'complete', 'error')) DEFAULT 'created',
    config JSONB NOT NULL  -- RunConfig Pydantic snapshot
);

-- Index for listing runs by status and date
CREATE INDEX runs_status_idx ON runs (status);
CREATE INDEX runs_created_at_idx ON runs (created_at DESC);

-- =============================================================================
-- SOURCES TABLE
-- =============================================================================
-- Represents ingested source documents (PDFs, URLs, notes).

CREATE TABLE sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID REFERENCES runs(id) ON DELETE CASCADE,
    type TEXT CHECK (type IN ('pdf', 'url', 'note')) NOT NULL,
    title TEXT NOT NULL,
    uri TEXT NOT NULL,  -- URL or storage path
    captured_at TIMESTAMPTZ DEFAULT NOW(),
    content_hash TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'
);

-- Index for listing sources by run
CREATE INDEX sources_run_id_idx ON sources (run_id);
CREATE INDEX sources_type_idx ON sources (type);

-- =============================================================================
-- CHUNKS TABLE
-- =============================================================================
-- Represents chunks of evidence extracted from sources.
-- Enhanced for hybrid search with both vector and full-text capabilities.

CREATE TABLE chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID REFERENCES sources(id) ON DELETE CASCADE,
    run_id UUID REFERENCES runs(id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,
    content TEXT NOT NULL,
    contextual_prefix TEXT,  -- From contextual embedding
    page_start INT,
    page_end INT,
    section_hint TEXT,
    heading_hierarchy TEXT[],  -- From Docling structure
    content_hash TEXT NOT NULL,
    token_count INT NOT NULL,
    chunk_method TEXT NOT NULL,  -- 'hybrid', 'simple', etc.
    embedding VECTOR(1536),
    search_content TSVECTOR,  -- For full-text search
    metadata JSONB DEFAULT '{}'
);

-- HNSW index for fast vector similarity search
CREATE INDEX chunks_embedding_idx ON chunks
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- GIN index for full-text search
CREATE INDEX chunks_search_idx ON chunks
    USING gin (search_content);

-- Index for filtering chunks by run
CREATE INDEX chunks_run_id_idx ON chunks (run_id);
CREATE INDEX chunks_source_id_idx ON chunks (source_id);

-- =============================================================================
-- DOCUMENTS TABLE
-- =============================================================================
-- Represents versioned research documents produced by the pipeline.

CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID REFERENCES runs(id) ON DELETE CASCADE,
    version INT NOT NULL,
    title TEXT NOT NULL,
    markdown TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    change_log TEXT,
    config_snapshot JSONB NOT NULL,  -- RunConfig at time of generation
    UNIQUE (run_id, version)
);

-- Index for listing document versions
CREATE INDEX documents_run_id_idx ON documents (run_id);
CREATE INDEX documents_version_idx ON documents (run_id, version DESC);

-- =============================================================================
-- CITATIONS TABLE
-- =============================================================================
-- Links claims in documents to evidence chunks.

CREATE TABLE citations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id) ON DELETE CASCADE,
    citation_key TEXT NOT NULL,  -- [1], [2], etc.
    source_id UUID REFERENCES sources(id),
    reference_entry TEXT NOT NULL,
    anchors JSONB NOT NULL  -- [{chunk_id, page, quote_start, quote_end}]
);

-- Index for listing citations by document
CREATE INDEX citations_document_id_idx ON citations (document_id);
CREATE INDEX citations_source_id_idx ON citations (source_id);

-- =============================================================================
-- EVENTS TABLE
-- =============================================================================
-- Pipeline events for observability and debugging.

CREATE TABLE events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID REFERENCES runs(id) ON DELETE CASCADE,
    ts TIMESTAMPTZ DEFAULT NOW(),
    type TEXT CHECK (type IN ('node_start', 'node_end', 'tool_call', 'error', 'checkpoint')) NOT NULL,
    node_name TEXT,
    payload JSONB DEFAULT '{}'
);

-- Index for querying events by run and time
CREATE INDEX events_run_id_idx ON events (run_id);
CREATE INDEX events_ts_idx ON events (run_id, ts DESC);
CREATE INDEX events_type_idx ON events (type);

-- =============================================================================
-- TRIGGER: Auto-update search_content for hybrid search
-- =============================================================================
-- Automatically generates tsvector from content and contextual_prefix.

CREATE OR REPLACE FUNCTION update_search_content()
RETURNS TRIGGER AS $$
BEGIN
    NEW.search_content := to_tsvector('english', COALESCE(NEW.contextual_prefix, '') || ' ' || NEW.content);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER chunks_search_content_trigger
    BEFORE INSERT OR UPDATE ON chunks
    FOR EACH ROW
    EXECUTE FUNCTION update_search_content();

-- =============================================================================
-- TRIGGER: Auto-update updated_at on runs
-- =============================================================================

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER runs_updated_at_trigger
    BEFORE UPDATE ON runs
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- =============================================================================
-- FUNCTION: Vector similarity search
-- =============================================================================
-- RPC function for vector similarity search with run filtering.

CREATE OR REPLACE FUNCTION match_chunks(
    query_embedding VECTOR(1536),
    match_count INT DEFAULT 10,
    run_filter UUID DEFAULT NULL
)
RETURNS TABLE (
    id UUID,
    source_id UUID,
    run_id UUID,
    content TEXT,
    contextual_prefix TEXT,
    page_start INT,
    page_end INT,
    section_hint TEXT,
    similarity FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id,
        c.source_id,
        c.run_id,
        c.content,
        c.contextual_prefix,
        c.page_start,
        c.page_end,
        c.section_hint,
        1 - (c.embedding <=> query_embedding) AS similarity
    FROM chunks c
    WHERE (run_filter IS NULL OR c.run_id = run_filter)
    ORDER BY c.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- =============================================================================
-- FUNCTION: Keyword search
-- =============================================================================
-- RPC function for full-text keyword search with run filtering.

CREATE OR REPLACE FUNCTION search_chunks_keyword(
    query_text TEXT,
    match_count INT DEFAULT 10,
    run_filter UUID DEFAULT NULL
)
RETURNS TABLE (
    id UUID,
    source_id UUID,
    run_id UUID,
    content TEXT,
    contextual_prefix TEXT,
    page_start INT,
    page_end INT,
    section_hint TEXT,
    rank FLOAT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id,
        c.source_id,
        c.run_id,
        c.content,
        c.contextual_prefix,
        c.page_start,
        c.page_end,
        c.section_hint,
        ts_rank(c.search_content, plainto_tsquery('english', query_text)) AS rank
    FROM chunks c
    WHERE
        (run_filter IS NULL OR c.run_id = run_filter)
        AND c.search_content @@ plainto_tsquery('english', query_text)
    ORDER BY rank DESC
    LIMIT match_count;
END;
$$;

-- =============================================================================
-- ROW LEVEL SECURITY (Optional - for multi-tenant scenarios)
-- =============================================================================
-- Uncomment and configure if you need user-based access control.

-- ALTER TABLE runs ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE sources ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE chunks ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE citations ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE events ENABLE ROW LEVEL SECURITY;

-- =============================================================================
-- COMMENTS
-- =============================================================================

COMMENT ON TABLE runs IS 'Research sessions with configuration and status tracking';
COMMENT ON TABLE sources IS 'Ingested source documents (PDFs, URLs, notes)';
COMMENT ON TABLE chunks IS 'Evidence chunks with embeddings for hybrid search';
COMMENT ON TABLE documents IS 'Versioned research documents with Markdown content';
COMMENT ON TABLE citations IS 'Links between document claims and evidence chunks';
COMMENT ON TABLE events IS 'Pipeline events for observability';

COMMENT ON FUNCTION match_chunks IS 'Vector similarity search for evidence retrieval';
COMMENT ON FUNCTION search_chunks_keyword IS 'Full-text keyword search for evidence retrieval';
