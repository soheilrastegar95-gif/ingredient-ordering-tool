-- Migration: add data snapshots so past versions of the ingredient and
-- recipe lists can be downloaded later.
-- Run this once in the Supabase SQL Editor.

CREATE TABLE IF NOT EXISTS data_snapshots (
    id SERIAL PRIMARY KEY,
    location_id INTEGER NOT NULL REFERENCES locations(id) ON DELETE CASCADE,
    snapshot_type TEXT NOT NULL,          -- 'ingredients' or 'recipes'
    content TEXT NOT NULL,                -- full CSV content at this point in time
    reason TEXT,                          -- the action that produced this version
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_snapshots_lookup
    ON data_snapshots (location_id, snapshot_type, created_at DESC);
