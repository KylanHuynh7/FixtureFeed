-- 0004: rate-limit bookkeeping shared by all app instances (serverless hosting
-- runs many short-lived instances, so an in-memory counter doesn't work).
-- Stores a hash of the client IP, never the IP itself.
CREATE TABLE link_events (
    ip_hash text NOT NULL,
    at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX link_events_ip_at_idx ON link_events (ip_hash, at);
