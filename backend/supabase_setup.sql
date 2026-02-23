-- ══════════════════════════════════════════════════════════════════════════════
-- Neykuri v1 — Supabase Database Setup
-- Run this in your Supabase project:
--   Dashboard → SQL Editor → New Query → paste this → Run
-- ══════════════════════════════════════════════════════════════════════════════

-- 1. Create the cloud_records table
CREATE TABLE IF NOT EXISTS cloud_records (
    id           BIGSERIAL PRIMARY KEY,
    patient_id   TEXT      NOT NULL,
    timestamp    TEXT      NOT NULL,
    prediction   TEXT      NOT NULL
                           CHECK (prediction IN (
                               'Kabam', 'Pithakabam', 'Pithalipitham',
                               'Pitham', 'Pithavatham'
                           )),
    confidence   FLOAT8    NOT NULL
                           CHECK (confidence >= 0.0 AND confidence <= 1.0),
    storage_path TEXT      NOT NULL,
    synced_at    TEXT      NOT NULL
);

-- 2. Index for fast patient history queries
CREATE INDEX IF NOT EXISTS idx_cloud_patient
    ON cloud_records (patient_id, id DESC);

-- 3. Enable Row Level Security (RLS) — keeps patient data private
ALTER TABLE cloud_records ENABLE ROW LEVEL SECURITY;

-- 4. Allow only service role to read/write (blocks anon access)
--    Your sync_to_cloud.py uses the SERVICE ROLE key so it can bypass RLS.
--    The anon key cannot access this table at all.
CREATE POLICY "Service role only"
    ON cloud_records
    FOR ALL
    USING (auth.role() = 'service_role');

-- ══════════════════════════════════════════════════════════════════════════════
-- Storage bucket setup (do this in the Supabase Dashboard UI):
--   Storage → New Bucket
--   Name    : neykuri_samples
--   Public  : OFF (private — patient data must be secure)
-- ══════════════════════════════════════════════════════════════════════════════