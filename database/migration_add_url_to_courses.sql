-- Migration: Add URL column to training_courses table
-- Run this if your database already exists and you need to add the URL column

ALTER TABLE training_courses 
ADD COLUMN IF NOT EXISTS url TEXT;

-- Update the cosine_similarity_search_courses function to include URL
CREATE OR REPLACE FUNCTION cosine_similarity_search_courses(
    query_embedding vector(768),
    match_threshold float DEFAULT 0.3,
    match_count int DEFAULT 10
)
RETURNS TABLE (
    id INTEGER,
    title TEXT,
    description TEXT,
    level TEXT,
    prerequisites TEXT[],
    url TEXT,
    similarity float,
    metadata JSONB
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        tc.id,
        tc.title,
        tc.description,
        tc.level,
        tc.prerequisites,
        tc.url,
        1 - (tc.embedding <=> query_embedding) as similarity,
        tc.metadata
    FROM training_courses tc
    WHERE 1 - (tc.embedding <=> query_embedding) > match_threshold
    ORDER BY tc.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

