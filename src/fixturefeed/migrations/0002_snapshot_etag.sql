-- 0002: remember the HTTP ETag of each download so the next fetch can ask
-- "has it changed?" and get a cheap 304 when it hasn't.
ALTER TABLE snapshots ADD COLUMN http_etag text;
