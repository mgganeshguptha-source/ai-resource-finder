-- Update the cosine_similarity_search_courses function to include URL field
-- Run this script in your PostgreSQL database

-- First, drop the existing function since we're changing the return type
-- The error message shows the function signature: (vector,double precision,integer)
DROP FUNCTION IF EXISTS cosine_similarity_search_courses(vector, double precision, integer);

-- Now create the function with the URL field included
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
