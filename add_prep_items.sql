-- Migration: add "prep items" — ingredients you make in-house that have
-- their own recipe (e.g. pizza sauce, dough, dressing, tabbouleh).
-- Run this once in the Supabase SQL Editor.

-- Mark an ingredient as made in-house, and record how much one batch yields.
ALTER TABLE ingredients ADD COLUMN IF NOT EXISTS is_prep BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE ingredients ADD COLUMN IF NOT EXISTS batch_yield_qty REAL NOT NULL DEFAULT 0;

-- 'stock'   = you make batches ahead; selling a dish deducts the prep item's own stock
-- 'explode' = no separate stock kept; selling a dish deducts the raw components directly
ALTER TABLE ingredients ADD COLUMN IF NOT EXISTS consumption_mode TEXT NOT NULL DEFAULT 'stock';

-- What goes into one batch of a prep item.
CREATE TABLE IF NOT EXISTS prep_recipe_items (
    prep_ingredient_id INTEGER NOT NULL REFERENCES ingredients(id) ON DELETE CASCADE,
    component_ingredient_id INTEGER NOT NULL REFERENCES ingredients(id) ON DELETE CASCADE,
    qty_per_batch REAL NOT NULL,
    PRIMARY KEY (prep_ingredient_id, component_ingredient_id)
);
