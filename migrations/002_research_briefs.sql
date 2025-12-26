-- =============================================================================
-- RESEARCH BRIEFS - Research Canvas Snapshots
-- =============================================================================
-- Stores intake clarifications for each research run so agents can reference
-- the latest objective, constraints, and open questions during planning.
-- =============================================================================

CREATE TABLE IF NOT EXISTS research_briefs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID REFERENCES runs(id) ON DELETE CASCADE UNIQUE,
    objective TEXT NOT NULL,
    constraints TEXT,
    required_sources TEXT[] DEFAULT '{}',
    open_questions TEXT[] DEFAULT '{}',
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS research_briefs_run_id_idx ON research_briefs(run_id);
CREATE INDEX IF NOT EXISTS research_briefs_updated_at_idx ON research_briefs(updated_at DESC);
