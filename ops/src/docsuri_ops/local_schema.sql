CREATE TABLE operations.observation (
    capability text PRIMARY KEY, disposition text NOT NULL,
    observed_at timestamptz NOT NULL, expires_at timestamptz NOT NULL,
    evidence jsonb NOT NULL CHECK (octet_length(evidence::text) <= 8192)
);
CREATE TABLE operations.incident (
    id uuid PRIMARY KEY, category text NOT NULL, correlation_id uuid,
    evidence jsonb NOT NULL CHECK (octet_length(evidence::text) <= 8192),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(), resolved_at timestamptz
);
