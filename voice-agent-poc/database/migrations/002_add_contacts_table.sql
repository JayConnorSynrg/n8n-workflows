-- Migration: Add contacts table for AIO voice assistant
-- Created: 2026-02-06
-- Purpose: Structured contact storage to replace unstructured vector DB storage

-- Check if table exists first
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_tables WHERE tablename = 'contacts') THEN
        CREATE TABLE contacts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            session_id VARCHAR(100) NOT NULL,
            name VARCHAR(255) NOT NULL,
            name_phonetic VARCHAR(255),
            email VARCHAR(255),
            email_confirmed BOOLEAN DEFAULT FALSE,
            phone VARCHAR(50),
            company VARCHAR(255),
            notes TEXT,
            tags TEXT[],
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            created_by VARCHAR(100),
            CONSTRAINT contacts_email_format CHECK (
                email IS NULL OR email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'
            )
        );

        CREATE INDEX idx_contacts_session ON contacts(session_id);
        CREATE INDEX idx_contacts_name ON contacts(LOWER(name));
        CREATE INDEX idx_contacts_email ON contacts(LOWER(email));
        CREATE INDEX idx_contacts_name_search ON contacts USING gin(to_tsvector('english', name));

        RAISE NOTICE 'Created contacts table with indexes';
    ELSE
        RAISE NOTICE 'contacts table already exists, skipping';
    END IF;
END $$;

-- Create or replace the update trigger function
CREATE OR REPLACE FUNCTION update_contacts_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger if not exists
DROP TRIGGER IF EXISTS trigger_contacts_updated_at ON contacts;
CREATE TRIGGER trigger_contacts_updated_at
    BEFORE UPDATE ON contacts
    FOR EACH ROW
    EXECUTE FUNCTION update_contacts_updated_at();

-- Create view for contact search
CREATE OR REPLACE VIEW v_contacts_search AS
SELECT
    id,
    name,
    name_phonetic,
    email,
    phone,
    company,
    notes,
    tags,
    created_at,
    updated_at,
    LOWER(name) as name_lower,
    LOWER(email) as email_lower
FROM contacts
ORDER BY updated_at DESC;

-- Add comments
COMMENT ON TABLE contacts IS 'Structured contact storage for AIO voice assistant';
COMMENT ON COLUMN contacts.name_phonetic IS 'Phonetic spelling (e.g., "J-E-L-A-L") for voice confirmation';
COMMENT ON COLUMN contacts.email_confirmed IS 'True when email spelling was explicitly confirmed by user';
