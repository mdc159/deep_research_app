-- Fix type mismatch in search_chunks_keyword function
-- Changes FLOAT to DOUBLE PRECISION for rank column

DROP FUNCTION IF EXISTS search_chunks_keyword(TEXT, INT, UUID);

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
    rank DOUBLE PRECISION
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
        CAST(ts_rank(c.search_content, plainto_tsquery('english', query_text)) AS DOUBLE PRECISION) AS rank
    FROM chunks c
    WHERE
        (run_filter IS NULL OR c.run_id = run_filter)
        AND c.search_content @@ plainto_tsquery('english', query_text)
    ORDER BY rank DESC
    LIMIT match_count;
END;
$$;

COMMENT ON FUNCTION search_chunks_keyword IS 'Full-text keyword search for evidence retrieval';
