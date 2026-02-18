-- Migration: 002_create_drive_document_repository.sql
-- Purpose: Create tables for Google Drive document repository and access logging
-- Workflow: IamjzfFxjHviJvJg (Google Drive Document Repository)
-- Created: 2026-01-30

-- ============================================================================
-- TABLE: drive_document_repository
-- ============================================================================
-- Stores metadata and extracted content from Google Drive files
-- Used by: sync, get, analyze, search operations in Google Drive Document Repository workflow

CREATE TABLE IF NOT EXISTS drive_document_repository (
    -- Primary key and identification
    id BIGSERIAL PRIMARY KEY,
    drive_file_id VARCHAR(255) UNIQUE NOT NULL,  -- Google Drive file ID (constraint: UNIQUE)
    drive_folder_id VARCHAR(255) NOT NULL,        -- Folder where file resides

    -- File metadata (from Google Drive API)
    file_name VARCHAR(255),                       -- Name of the file
    mime_type VARCHAR(100),                       -- Content type (application/pdf, text/plain, etc.)
    file_size_bytes BIGINT,                       -- File size in bytes
    web_view_link TEXT,                           -- Link to open file in Google Drive UI
    drive_modified_time TIMESTAMPTZ,              -- Last modified timestamp from Drive

    -- Extracted content
    extracted_text TEXT,                          -- Full extracted text content
    text_length INTEGER,                          -- Character count of extracted_text
    extraction_method VARCHAR(50),                -- How text was extracted (auto, error, etc.)
    extraction_status VARCHAR(50),                -- Status (SUCCESS, FAILED)

    -- AI Analysis
    ai_analysis JSONB,                            -- Structured AI analysis results

    -- Access tracking
    access_count INTEGER DEFAULT 0,               -- Number of times document has been accessed
    first_accessed_at TIMESTAMPTZ DEFAULT NOW(),  -- Initial sync timestamp
    last_accessed_at TIMESTAMPTZ DEFAULT NOW(),   -- Last get/search timestamp

    -- Lifecycle timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Constraints
    CONSTRAINT valid_extraction_status CHECK (
        extraction_status IN ('SUCCESS', 'FAILED')
    )
);

-- Indexes for query performance
CREATE INDEX IF NOT EXISTS idx_drive_file_id ON drive_document_repository(drive_file_id);
CREATE INDEX IF NOT EXISTS idx_drive_folder_id ON drive_document_repository(drive_folder_id);
CREATE INDEX IF NOT EXISTS idx_extraction_status ON drive_document_repository(extraction_status);
CREATE INDEX IF NOT EXISTS idx_created_at ON drive_document_repository(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_last_accessed ON drive_document_repository(last_accessed_at DESC);

-- Comment for documentation
COMMENT ON TABLE drive_document_repository IS 'Metadata and extracted content from Google Drive files synced by workflow IamjzfFxjHviJvJg';
COMMENT ON COLUMN drive_document_repository.drive_file_id IS 'Google Drive file ID - used as unique identifier for lookups';
COMMENT ON COLUMN drive_document_repository.extracted_text IS 'Full text content extracted from PDF, DOCX, CSV, TXT files and text from images';
COMMENT ON COLUMN drive_document_repository.extraction_status IS 'SUCCESS when content extracted successfully, FAILED if extraction failed';
COMMENT ON COLUMN drive_document_repository.ai_analysis IS 'JSON object containing AI vision or text analysis results';
COMMENT ON COLUMN drive_document_repository.access_count IS 'Incremented each time the file is accessed via get or search operations';

-- ============================================================================
-- TABLE: drive_access_log
-- ============================================================================
-- Logs all sync and access operations for audit trail
-- Used by: Log Sync Operation node in workflow IamjzfFxjHviJvJg

CREATE TABLE IF NOT EXISTS drive_access_log (
    id BIGSERIAL PRIMARY KEY,
    drive_folder_id VARCHAR(255) NOT NULL,
    operation VARCHAR(50) NOT NULL,               -- 'sync', 'get', 'search', 'analyze'
    files_found INTEGER,                          -- Total files found in folder
    files_processed INTEGER,                      -- Files successfully processed
    files_skipped INTEGER DEFAULT 0,              -- Files skipped (already synced)
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for queries
CREATE INDEX IF NOT EXISTS idx_access_log_folder ON drive_access_log(drive_folder_id);
CREATE INDEX IF NOT EXISTS idx_access_log_operation ON drive_access_log(operation);
CREATE INDEX IF NOT EXISTS idx_access_log_created ON drive_access_log(created_at DESC);

-- Comment for documentation
COMMENT ON TABLE drive_access_log IS 'Audit trail for all drive_document_repository sync and access operations';
COMMENT ON COLUMN drive_access_log.operation IS 'Type of operation performed (sync scans and indexes files)';
COMMENT ON COLUMN drive_access_log.files_found IS 'Total files enumerated in the folder during the operation';
COMMENT ON COLUMN drive_access_log.files_processed IS 'Files that were successfully added or updated in the repository';
COMMENT ON COLUMN drive_access_log.files_skipped IS 'Files skipped because already synced (UPSERT did not insert)';

-- ============================================================================
-- VIEW: v_drive_repository_stats
-- ============================================================================
-- Summary statistics for the document repository

CREATE OR REPLACE VIEW v_drive_repository_stats AS
SELECT
    COUNT(*) as total_documents,
    COUNT(DISTINCT drive_folder_id) as unique_folders,
    SUM(CASE WHEN extraction_status = 'SUCCESS' THEN 1 ELSE 0 END) as successful_extractions,
    SUM(CASE WHEN extraction_status = 'FAILED' THEN 1 ELSE 0 END) as failed_extractions,
    SUM(file_size_bytes) as total_storage_bytes,
    SUM(text_length) as total_text_characters,
    MAX(updated_at) as last_sync,
    ROUND(AVG(access_count)::numeric, 2) as avg_access_count
FROM drive_document_repository;

-- ============================================================================
-- FUNCTION: check_file_needs_processing
-- ============================================================================
-- Check if a file already exists and needs re-processing
-- Used by: Check If Needs Processing node

CREATE OR REPLACE FUNCTION check_file_needs_processing(
    p_drive_file_id VARCHAR,
    p_drive_modified_time TIMESTAMPTZ
)
RETURNS TABLE (
    needs_processing BOOLEAN,
    file_id VARCHAR,
    stored_modified_time TIMESTAMPTZ,
    extraction_status VARCHAR
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        (COALESCE(ddr.drive_modified_time, '1970-01-01'::TIMESTAMPTZ) < p_drive_modified_time
         OR ddr.extraction_status = 'FAILED')::BOOLEAN as needs_processing,
        ddr.drive_file_id,
        ddr.drive_modified_time,
        ddr.extraction_status
    FROM drive_document_repository ddr
    WHERE ddr.drive_file_id = p_drive_file_id
    LIMIT 1;

    -- If no record found, return needs_processing = true
    IF NOT FOUND THEN
        RETURN QUERY SELECT true, p_drive_file_id, NULL::TIMESTAMPTZ, NULL;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- FUNCTION: search_drive_documents
-- ============================================================================
-- Full-text search across extracted document content
-- Used by: Search Documents node

CREATE OR REPLACE FUNCTION search_drive_documents(
    p_search_query TEXT,
    p_folder_id VARCHAR DEFAULT NULL,
    p_limit INTEGER DEFAULT 20
)
RETURNS TABLE (
    drive_file_id VARCHAR,
    file_name VARCHAR,
    mime_type VARCHAR,
    extracted_text TEXT,
    text_length INTEGER,
    extraction_status VARCHAR,
    last_accessed_at TIMESTAMPTZ,
    relevance_score FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        ddr.drive_file_id,
        ddr.file_name,
        ddr.mime_type,
        ddr.extracted_text,
        ddr.text_length,
        ddr.extraction_status,
        ddr.last_accessed_at,
        -- Simple relevance: count of search term occurrences
        (LENGTH(COALESCE(ddr.extracted_text, '')) -
         LENGTH(REPLACE(LOWER(COALESCE(ddr.extracted_text, '')), LOWER(p_search_query), '')))
        / NULLIF(LENGTH(p_search_query), 0)::FLOAT as relevance_score
    FROM drive_document_repository ddr
    WHERE ddr.extraction_status = 'SUCCESS'
      AND (p_folder_id IS NULL OR ddr.drive_folder_id = p_folder_id)
      AND LOWER(COALESCE(ddr.extracted_text, '')) LIKE '%' || LOWER(p_search_query) || '%'
    ORDER BY relevance_score DESC, ddr.last_accessed_at DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- TRIGGER: update_drive_document_timestamp
-- ============================================================================
-- Auto-update the updated_at timestamp on every modification

CREATE OR REPLACE FUNCTION update_drive_document_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_drive_document_timestamp ON drive_document_repository;
CREATE TRIGGER trigger_update_drive_document_timestamp
    BEFORE UPDATE ON drive_document_repository
    FOR EACH ROW
    EXECUTE FUNCTION update_drive_document_timestamp();

-- ============================================================================
-- Notes
-- ============================================================================
-- 1. The drive_file_id uses UNIQUE constraint - Google Drive IDs are globally unique
-- 2. ON CONFLICT (drive_file_id) logic in n8n handles upsert semantics
-- 3. extracted_text can be very large - consider partitioning if table grows beyond 1M rows
-- 4. ai_analysis JSONB field allows flexible schema for different AI providers
-- 5. access_count is incremented in n8n workflow, not automatically by trigger
