-- Database Schema

-- AFTER:
-- Database Schema
-- STATUS: REFERENCE ONLY - NOT CURRENTLY USED
--
-- Current implementation uses CSV files (db/leads.csv, db/deals.csv, etc.)
-- This schema is preserved for future PostgreSQL migration.
--
-- Migration path:
--   1. Deploy PostgreSQL container
--   2. Run this schema
--   3. Migrate CSV data using scripts/migrate_csv_to_postgres.py (TODO)
--   4. Update db_handler.py to use SQLAlchemy instead of pandas

CREATE TABLE leads (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    company TEXT,
    industry TEXT,
    status TEXT DEFAULT 'New',
    last_contacted TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- Add missing columns from CSV schema:
    role TEXT,
    company_size TEXT,
    verified_insight TEXT,
    negative_signals TEXT,
    draft_message TEXT,
    confidence_score FLOAT DEFAULT 0.0,
    review_status TEXT DEFAULT 'New'
);
