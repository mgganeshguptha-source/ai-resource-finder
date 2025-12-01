-- ================================================
-- AI Resource Finder Database Schema
-- PostgreSQL with pgvector extension
-- ================================================

-- Enable pgvector extension (run this first if not already enabled)
CREATE EXTENSION IF NOT EXISTS vector;

-- Drop existing tables if recreating
DROP TABLE IF EXISTS allocation_requests CASCADE;
DROP TABLE IF EXISTS training_courses CASCADE;
DROP TABLE IF EXISTS candidate_profiles CASCADE;

-- Table: candidate_profiles
-- Stores CV data with extracted skills, experience, and embeddings
CREATE TABLE candidate_profiles (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    extracted_skills JSONB NOT NULL DEFAULT '{}',
    years_of_experience JSONB NOT NULL DEFAULT '{}',
    domain_tags TEXT[],
    embedding vector(768) NOT NULL,
    cv_s3_key TEXT,
    cv_s3_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Unique constraint on email
    CONSTRAINT unique_candidate_email UNIQUE (email)
);

-- Table: training_courses
-- Stores course catalog with embeddings for semantic search
CREATE TABLE training_courses (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    level TEXT,  -- beginner, intermediate, advanced
    prerequisites TEXT[],
    url TEXT,  -- Course URL/link
    embedding vector(768) NOT NULL,
    metadata JSONB DEFAULT '{}',  -- Additional course metadata
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Unique constraint on title
    CONSTRAINT unique_course_title UNIQUE (title)
);

-- Table: allocation_requests
-- Stores allocation workflow data
CREATE TABLE allocation_requests (
    id SERIAL PRIMARY KEY,
    candidate_id INTEGER NOT NULL,
    requirement_text TEXT NOT NULL,
    match_score NUMERIC(5,2) NOT NULL,  -- Match percentage (0-100)
    user_details JSONB NOT NULL,  -- All form fields (emp_code, emp_name, client_name, etc.)
    status TEXT DEFAULT 'pending',  -- pending, approved, rejected
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    -- Foreign key to candidate_profiles
    CONSTRAINT fk_candidate FOREIGN KEY (candidate_id) 
        REFERENCES candidate_profiles(id) 
        ON DELETE CASCADE
);

-- Indexes for performance
CREATE INDEX idx_candidate_profiles_email ON candidate_profiles(email);
CREATE INDEX idx_candidate_profiles_domain ON candidate_profiles USING GIN(domain_tags);
CREATE INDEX idx_training_courses_level ON training_courses(level);
CREATE INDEX idx_allocation_requests_candidate ON allocation_requests(candidate_id);
CREATE INDEX idx_allocation_requests_status ON allocation_requests(status);
CREATE INDEX idx_allocation_requests_created ON allocation_requests(created_at);

-- Vector similarity search indexes (HNSW for fast approximate nearest neighbor)
CREATE INDEX idx_candidate_profiles_vector ON candidate_profiles 
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX idx_training_courses_vector ON training_courses 
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Function: cosine_similarity_search_candidates
-- Helper function for candidate semantic search
CREATE OR REPLACE FUNCTION cosine_similarity_search_candidates(
    query_embedding vector(768),
    match_threshold float DEFAULT 0.3,
    match_count int DEFAULT 30
)
RETURNS TABLE (
    id INTEGER,
    name TEXT,
    email TEXT,
    extracted_skills JSONB,
    years_of_experience JSONB,
    domain_tags TEXT[],
    similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        cp.id,
        cp.name,
        cp.email,
        cp.extracted_skills,
        cp.years_of_experience,
        cp.domain_tags,
        1 - (cp.embedding <=> query_embedding) as similarity
    FROM candidate_profiles cp
    WHERE 1 - (cp.embedding <=> query_embedding) > match_threshold
    ORDER BY cp.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- Function: cosine_similarity_search_courses
-- Helper function for course semantic search
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
        1 - (tc.embedding <=> query_embedding) as similarity,
        tc.metadata
    FROM training_courses tc
    WHERE 1 - (tc.embedding <=> query_embedding) > match_threshold
    ORDER BY tc.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- Function: update_modified_column
-- Automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_modified_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for automatic timestamp updates
CREATE TRIGGER update_candidate_profiles_timestamp
    BEFORE UPDATE ON candidate_profiles
    FOR EACH ROW
    EXECUTE FUNCTION update_modified_column();

CREATE TRIGGER update_training_courses_timestamp
    BEFORE UPDATE ON training_courses
    FOR EACH ROW
    EXECUTE FUNCTION update_modified_column();

CREATE TRIGGER update_allocation_requests_timestamp
    BEFORE UPDATE ON allocation_requests
    FOR EACH ROW
    EXECUTE FUNCTION update_modified_column();

-- Grant permissions (adjust based on your setup)
-- For service role: full access
-- For anon/authenticated: read-only access
ALTER TABLE candidate_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE training_courses ENABLE ROW LEVEL SECURITY;
ALTER TABLE allocation_requests ENABLE ROW LEVEL SECURITY;

-- Policy: Allow service role full access
CREATE POLICY "Service role has full access to candidate_profiles"
    ON candidate_profiles
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Service role has full access to training_courses"
    ON training_courses
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Service role has full access to allocation_requests"
    ON allocation_requests
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Policy: Allow public read-only access for queries
CREATE POLICY "Public read access to candidate_profiles"
    ON candidate_profiles
    FOR SELECT
    TO anon, authenticated
    USING (true);

CREATE POLICY "Public read access to training_courses"
    ON training_courses
    FOR SELECT
    TO anon, authenticated
    USING (true);

CREATE POLICY "Public read access to allocation_requests"
    ON allocation_requests
    FOR SELECT
    TO anon, authenticated
    USING (true);

-- View: candidate_stats
-- Useful for monitoring and debugging
CREATE OR REPLACE VIEW candidate_stats AS
SELECT 
    COUNT(*) as total_candidates,
    COUNT(DISTINCT domain_tags) as unique_domains,
    AVG(jsonb_array_length(extracted_skills::jsonb)) as avg_skills_per_candidate
FROM candidate_profiles;

-- View: course_stats
CREATE OR REPLACE VIEW course_stats AS
SELECT 
    COUNT(*) as total_courses,
    COUNT(DISTINCT level) as unique_levels,
    level,
    COUNT(*) as count_by_level
FROM training_courses
GROUP BY level;


