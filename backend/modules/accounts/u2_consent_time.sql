-- Isolated synthetic profile: preserve the first observable decision time.
ALTER TABLE accounts.consent ADD COLUMN effective_at timestamptz NOT NULL DEFAULT clock_timestamp();
