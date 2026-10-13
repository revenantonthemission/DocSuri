CREATE TABLE discovery.execution (
    id uuid PRIMARY KEY, account_id uuid, query jsonb NOT NULL,
    query_hash text NOT NULL CHECK (query_hash ~ '^[0-9a-f]{64}$'),
    captured_generation bigint, results jsonb NOT NULL,
    completed_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    relay_state text NOT NULL CHECK (relay_state IN ('none','pending','delivered','suppressed'))
);
