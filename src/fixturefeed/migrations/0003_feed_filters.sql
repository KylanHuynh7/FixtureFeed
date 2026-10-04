-- 0003: per-feed filters (DECISIONS.md #8: filters are the first post-MVP feature).
ALTER TABLE feeds
    ADD COLUMN side text NOT NULL DEFAULT 'all' CHECK (side IN ('all', 'home', 'away')),
    ADD COLUMN primetime_only boolean NOT NULL DEFAULT false;
