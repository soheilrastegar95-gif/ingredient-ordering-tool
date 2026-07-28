-- Migration: add activity log table for tracking all changes in the app.
-- Run this once in the Supabase SQL Editor.

CREATE TABLE IF NOT EXISTS activity_log (
    id SERIAL PRIMARY KEY,
    location_id INTEGER NOT NULL REFERENCES locations(id) ON DELETE CASCADE,
    action TEXT NOT NULL,
    details TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_activity_log_location_time ON activity_log (location_id, created_at DESC);
